"""Generate the player character (a chunky toy-style castaway) with a skeleton and
animations, and export it for Godot.

Run from the godot_game folder (no Blender window needed):
    /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
        --python tools/blender/make_character.py

Add `-- --preview` at the end to also render preview pictures into
tools/generated/character_preview/.

Outputs:
    assets/character/player.glb   mesh + skeleton + animations: Idle, Walk, Run, Chop

How it works: the body is made of chunky boxes (like a toy figure). Each box is
glued 100% to one bone of a simple skeleton, so moving a bone moves that body
part as a solid piece - no tricky bending skin. Animations are bone rotations
calculated with sine waves (for loops) or a few key poses (for the chop).

Directions in Blender: z is up and the character faces +y. The glTF exporter
turns that into Godot's y-up, facing -z (Godot's "forward").
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---- Look: tweak these and re-run -------------------------------------------
COLORS = {  # normal screen colours (0-1)
    "Skin": (0.96, 0.76, 0.60),
    "Hair": (0.42, 0.26, 0.16),
    "Shirt": (0.95, 0.92, 0.84),
    "Shorts": (0.33, 0.53, 0.76),
    "Eyes": (0.15, 0.12, 0.12),
    "Hat": (0.93, 0.80, 0.48),
    "HatBand": (0.78, 0.33, 0.27),
}
WEAR_HAT = True
HEAD_SIZE = 0.42      # metres; big head = cuter
BODY_WIDTH = 0.46
BEVEL = 0.025         # rounds off box edges a little; 0 = sharp boxes
FPS = 30

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
# ------------------------------------------------------------------------------

# Bones: name -> (head position, tail position, parent). Limbs point downwards.
SHOULDER_Z, HIP_Z = 1.24, 0.72
ARM_X, LEG_X = BODY_WIDTH / 2 + 0.08, 0.12
BONES = {
    "Hips": ((0, 0, HIP_Z), (0, 0, 0.85), None),
    "Torso": ((0, 0, 0.82), (0, 0, 1.30), "Hips"),
    "Head": ((0, 0, 1.30), (0, 0, 1.30 + HEAD_SIZE), "Torso"),
    "Arm.R": ((ARM_X, 0, SHOULDER_Z), (ARM_X, 0, 0.62), "Torso"),
    "Arm.L": ((-ARM_X, 0, SHOULDER_Z), (-ARM_X, 0, 0.62), "Torso"),
    "Leg.R": ((LEG_X, 0, HIP_Z), (LEG_X, 0, 0.05), "Hips"),
    "Leg.L": ((-LEG_X, 0, HIP_Z), (-LEG_X, 0, 0.05), "Hips"),
}
BONE_NAMES = list(BONES)
MATERIAL_NAMES = list(COLORS)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_material(name):
    mat = bpy.data.materials.new(name)
    r, g, b = (srgb_to_linear(c) for c in COLORS[name])
    mat.diffuse_color = (r, g, b, 1.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
    return mat


# ---- Body ---------------------------------------------------------------------
class Body:
    """Collects chunky parts into one mesh, remembering which bone each belongs to."""

    def __init__(self):
        self.bm = bmesh.new()
        self.deform = self.bm.verts.layers.deform.verify()

    def _finish_part(self, verts, bone, material, bevel):
        # Colour the faces and glue every vertex 100% to its bone. Do this before
        # bevelling: the bevel copies both onto the new rounded-edge geometry.
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = MATERIAL_NAMES.index(material)
        for v in verts:
            v[self.deform][BONE_NAMES.index(bone)] = 1.0
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, segments=1,
                            affect="EDGES", clamp_overlap=True)

    def box(self, center, size, bone, material, bevel=BEVEL, taper=1.0):
        """A box. taper < 1 makes the top narrower than the bottom."""
        verts = bmesh.ops.create_cube(self.bm, size=1.0)["verts"]
        for v in verts:
            scale = taper if v.co.z > 0 else 1.0
            v.co = Vector((center[0] + v.co.x * size[0] * scale,
                           center[1] + v.co.y * size[1] * scale,
                           center[2] + v.co.z * size[2]))
        self._finish_part(verts, bone, material, bevel)

    def disc(self, center, radius_bottom, radius_top, height, bone, material, segments=10):
        """A low-poly cylinder (used for the hat)."""
        verts = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segments,
                                      radius1=radius_bottom, radius2=radius_top, depth=height,
                                      matrix=Matrix.Translation(center))["verts"]
        self._finish_part(verts, bone, material, 0)


def build_body(body):
    hs = HEAD_SIZE
    hz = 1.30 + hs / 2 + 0.02  # head centre height
    # Legs: shorts on the thigh, skin below, chunky bare feet pointing forward (+y).
    for side, bone in ((1, "Leg.R"), (-1, "Leg.L")):
        x = side * LEG_X
        body.box((x, 0, 0.56), (0.21, 0.22, 0.32), bone, "Shorts")
        body.box((x, 0, 0.24), (0.16, 0.17, 0.34), bone, "Skin")
        body.box((x, 0.04, 0.04), (0.17, 0.27, 0.08), bone, "Skin")
    body.box((0, 0, 0.76), (BODY_WIDTH - 0.04, 0.26, 0.18), "Hips", "Shorts")
    # Torso: shirt, a bit narrower at the shoulders.
    body.box((0, 0, 1.05), (BODY_WIDTH, 0.28, 0.48), "Torso", "Shirt", taper=0.92)
    body.box((0, 0, 1.31), (0.14, 0.12, 0.06), "Torso", "Skin")  # neck
    # Arms: short sleeve, skin forearm, hand.
    for side, bone in ((1, "Arm.R"), (-1, "Arm.L")):
        x = side * ARM_X
        body.box((x, 0, 1.13), (0.16, 0.17, 0.24), bone, "Shirt")
        body.box((x, 0, 0.86), (0.12, 0.13, 0.32), bone, "Skin")
        body.box((x, 0, 0.66), (0.13, 0.14, 0.11), bone, "Skin")
    # Head: big box, eyes, nose, hair.
    body.box((0, 0, hz), (hs, hs * 0.95, hs), "Head", "Skin", bevel=BEVEL * 1.6)
    front = hs * 0.95 / 2
    for side in (1, -1):
        body.box((side * hs * 0.2, front + 0.005, hz + 0.01), (0.05, 0.03, 0.08), "Head", "Eyes", 0)
    body.box((0, front + 0.02, hz - 0.06), (0.06, 0.05, 0.06), "Head", "Skin", 0)
    body.box((0, -0.02, hz + hs / 2 + 0.03), (hs + 0.04, hs + 0.02, 0.1), "Head", "Hair")
    body.box((0, -hs / 2 - 0.02, hz + 0.05), (hs + 0.04, 0.08, hs * 0.75), "Head", "Hair")
    for side in (1, -1):  # messy tufts above the ears
        body.box((side * (hs / 2 + 0.015), -0.1, hz + 0.13), (0.04, hs * 0.45, 0.12), "Head", "Hair")
    body.box((0.08, front - 0.02, hz + hs / 2 - 0.02), (0.22, 0.08, 0.08), "Head", "Hair")  # fringe
    if WEAR_HAT:
        top = hz + hs / 2 + 0.08
        body.disc((0, 0, top), hs * 0.95, hs * 0.95, 0.04, "Head", "Hat")
        body.disc((0, 0, top + 0.09), hs * 0.58, hs * 0.5, 0.15, "Head", "Hat")
        body.disc((0, 0, top + 0.05), hs * 0.59, hs * 0.58, 0.05, "Head", "HatBand")


# ---- Skeleton -----------------------------------------------------------------
def build_skeleton_and_mesh():
    arm_data = bpy.data.armatures.new("Skeleton")
    rig = bpy.data.objects.new("Player", arm_data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent) in BONES.items():
        b = arm_data.edit_bones.new(name)
        b.head, b.tail, b.roll = head, tail, 0.0
        if parent:
            b.parent = arm_data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh = bpy.data.meshes.new("Body")
    obj = bpy.data.objects.new("Body", mesh)
    bpy.context.collection.objects.link(obj)
    for name in MATERIAL_NAMES:
        mesh.materials.append(make_material(name))
    for name in BONE_NAMES:
        obj.vertex_groups.new(name=name)
    body = Body()
    build_body(body)
    for f in body.bm.faces:
        f.smooth = False  # flat shading = the low-poly look
    body.bm.normal_update()
    body.bm.to_mesh(mesh)
    body.bm.free()
    obj.parent = rig
    obj.modifiers.new("Armature", "ARMATURE").object = rig
    print("character triangles:", sum(len(p.vertices) - 2 for p in mesh.polygons))
    return rig


# ---- Animation helpers ----------------------------------------------------------
def find_signs(rig):
    """Work out which rotation direction swings each bone 'forward' (+y) or 'outward'.

    Bone axes depend on how Blender orients each bone, so instead of guessing we
    test: rotate a little, see where the bone's tip went, and remember the sign.
    """
    signs = {}
    for name in BONE_NAMES:
        pb = rig.pose.bones[name]
        pb.rotation_mode = "XYZ"
        rest_tail = pb.tail.copy()
        pb.rotation_euler = (0.3, 0, 0)
        bpy.context.view_layer.update()
        forward = 1 if pb.tail.y > rest_tail.y else -1
        pb.rotation_euler = (0, 0, 0.3)
        bpy.context.view_layer.update()
        outward = 1 if (pb.tail.x - rest_tail.x) * (1 if pb.head.x >= 0 else -1) > 0 else -1
        pb.rotation_euler = (0, 0, 0)
        signs[name] = (forward, outward)
    bpy.context.view_layer.update()
    return signs


def pose_to_keys(rig, signs, frame, pose):
    """pose: bone -> (forward swing deg, twist deg, outward swing deg); 'bob' -> hips height."""
    for name in BONE_NAMES:
        fwd, twist, out = pose.get(name, (0, 0, 0))
        f_sign, o_sign = signs[name]
        pb = rig.pose.bones[name]
        pb.rotation_euler = (math.radians(fwd) * f_sign, math.radians(twist),
                             math.radians(out) * o_sign)
        pb.keyframe_insert("rotation_euler", frame=frame)
    hips = rig.pose.bones["Hips"]
    hips.location = (0, pose.get("bob", 0.0), 0)  # bone-local y = up for the upright hips bone
    hips.keyframe_insert("location", frame=frame)


def make_action(rig, signs, name, frames, pose_at, samples=None):
    """Create one animation. pose_at(t) gives the pose at t = 0..1 through the clip."""
    rig.animation_data_create()
    action = bpy.data.actions.new(name)
    rig.animation_data.action = action
    keys = samples or [i / 8 for i in range(9)]
    for t in keys:
        pose_to_keys(rig, signs, 1 + round(t * frames), pose_at(t))
    # Store it on its own NLA track so the exporter writes it as a separate animation.
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 1, action)
    rig.animation_data.action = None
    return action


def build_animations(rig):
    signs = find_signs(rig)
    tau = math.tau

    def idle(t):
        s = math.sin(tau * t)
        return {"bob": 0.012 * s, "Torso": (1.5 * s, 0, 0), "Head": (-2 * s, 0, 0),
                "Arm.R": (2 * s, 0, 4), "Arm.L": (2 * s, 0, 4)}

    def walk(t):
        s = math.sin(tau * t)
        return {"bob": 0.025 * abs(math.cos(tau * t)) - 0.0125, "Torso": (3, 5 * s, 0),
                "Leg.R": (28 * s, 0, 0), "Leg.L": (-28 * s, 0, 0),
                "Arm.R": (-24 * s, 0, 5), "Arm.L": (24 * s, 0, 5)}

    def run(t):
        s = math.sin(tau * t)
        return {"bob": 0.05 * abs(math.cos(tau * t)) - 0.025, "Torso": (12, 8 * s, 0),
                "Head": (-6, 0, 0), "Leg.R": (50 * s, 0, 0), "Leg.L": (-50 * s, 0, 0),
                "Arm.R": (-45 * s, 0, 8), "Arm.L": (45 * s, 0, 8)}

    chop_keys = {  # t -> pose: raise both hands overhead, then swing down in front
        0.0: {},
        0.35: {"Torso": (-6, -12, 0), "Arm.R": (165, 0, -8), "Arm.L": (160, 0, -8), "Head": (-8, 0, 0)},
        0.55: {"Torso": (14, 6, 0), "Arm.R": (45, 0, -6), "Arm.L": (40, 0, -6), "Head": (6, 0, 0),
               "bob": -0.04},
        0.75: {"Torso": (10, 4, 0), "Arm.R": (35, 0, -6), "Arm.L": (30, 0, -6), "bob": -0.03},
        1.0: {},
    }

    make_action(rig, signs, "Idle", 2 * FPS, idle)
    make_action(rig, signs, "Walk", round(0.8 * FPS), walk)
    make_action(rig, signs, "Run", round(0.5 * FPS), run)
    make_action(rig, signs, "Chop", round(0.7 * FPS), lambda t: chop_keys[t], list(chop_keys))


# ---- Output ---------------------------------------------------------------------
def export():
    out_dir = os.path.join(ROOT, "assets", "character")
    os.makedirs(out_dir, exist_ok=True)
    bpy.context.scene.render.fps = FPS
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(out_dir, "player.glb"),
        export_format="GLB",
        export_yup=True,
        export_apply=False,  # keep the skeleton working (don't bake the pose into the mesh)
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
    )


def render_previews(rig):
    """Render a few pictures to check the look and poses."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_object_outline = True
    scene.render.resolution_x = scene.render.resolution_y = 600
    scene.world = bpy.data.worlds.new("Sky")
    scene.world.color = (0.62, 0.84, 0.95)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 70
    out_dir = os.path.join(ROOT, "tools", "generated", "character_preview")
    os.makedirs(out_dir, exist_ok=True)
    shots = [("front_idle", "Idle", 1, (0, 6, 1.1)), ("threequarter_walk", "Walk", 7, (4, 4.5, 1.6)),
             ("side_chop_raise", "Chop", 8, (6, 0.5, 1.2)), ("side_chop_hit", "Chop", 12, (6, 0.5, 1.2)),
             ("side_run", "Run", 4, (6, 1.5, 1.2))]
    for fname, anim, frame, cam_pos in shots:
        rig.animation_data.action = bpy.data.actions[anim]
        scene.frame_set(frame)
        cam.location = cam_pos
        direction = Vector((0, 0, 0.95)) - Vector(cam_pos)
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(out_dir, fname + ".png")
        bpy.ops.render.render(write_still=True)
    rig.animation_data.action = None
    print("previews in", out_dir)


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
player = build_skeleton_and_mesh()
build_animations(player)
export()
if "--preview" in sys.argv:
    render_previews(player)
print("Character exported")
