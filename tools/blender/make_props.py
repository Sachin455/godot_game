"""Generate the simple low-poly props (trees, rocks, grass, bushes, flowers) and
export each one as its own model for Godot.

Run from the godot_game folder (no Blender window needed):
    /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
        --python tools/blender/make_props.py

Outputs: assets/lowpoly/<Name>.glb  (e.g. Pine_A.glb, Round_B.glb, Rock_A.glb ...)

Style: "minimalist low poly" - a handful of flat-coloured faceted shapes per
prop, no textures. Each tree is only ~70-200 triangles, so thousands are cheap.
Props stand on the ground at height 0 and are about real size (trees ~4-10 m).

Directions in Blender: z is up. The glTF exporter turns that into Godot's y-up.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mesh_utils import make_material  # noqa: E402  (shared helpers)

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT_DIR = os.path.join(ROOT, "assets", "lowpoly")

# ---- Colours (normal screen colours, 0-1) -------------------------------------
TRUNK = (0.45, 0.30, 0.20)
PINE_GREENS = {"A": (0.17, 0.40, 0.29), "B": (0.24, 0.50, 0.31), "C": (0.20, 0.45, 0.36)}
ROUND_GREENS = {"A": (0.40, 0.62, 0.27), "B": (0.29, 0.53, 0.26), "C": (0.47, 0.67, 0.30)}
ROCK_GREYS = {"A": (0.60, 0.60, 0.62), "B": (0.55, 0.54, 0.55), "C": (0.66, 0.64, 0.62)}
GRASS = {"A": (0.42, 0.66, 0.28), "B": (0.55, 0.72, 0.30)}
BUSH = (0.31, 0.56, 0.28)
FLOWERS = {"A": (0.96, 0.56, 0.70), "B": (0.99, 0.85, 0.30), "C": (0.98, 0.97, 0.94)}
STEM = (0.36, 0.60, 0.26)
OAK_GREENS = {"A": (0.33, 0.55, 0.25), "B": (0.42, 0.60, 0.24)}
POPLAR_GREENS = {"A": (0.50, 0.66, 0.26), "B": (0.38, 0.58, 0.27)}
PALM_TRUNK = (0.62, 0.50, 0.36)
PALM_LEAVES = {"A": (0.33, 0.62, 0.30), "B": (0.40, 0.67, 0.28)}
COCONUT = (0.40, 0.28, 0.18)
# ------------------------------------------------------------------------------


class Prop:
    """Builds one prop out of simple shapes, one material per colour."""

    def __init__(self, seed):
        self.bm = bmesh.new()
        self.colors = []
        self.rng = random.Random(seed)

    def _material_index(self, rgb):
        if rgb not in self.colors:
            self.colors.append(rgb)
        return self.colors.index(rgb)

    def _finish(self, verts, rgb, jitter):
        for v in verts:  # nudge corners a little so nothing looks machine-perfect
            v.co += Vector([self.rng.uniform(-jitter, jitter) for _ in range(3)])
        index = self._material_index(rgb)
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = index

    def cone(self, base_z, height, radius_bottom, radius_top, rgb, segments=7, jitter=0.0,
             offset=(0, 0), tilt=(0, 0)):
        m = (Matrix.Translation((offset[0], offset[1], base_z + height / 2))
             @ Matrix.Rotation(tilt[0], 4, "X") @ Matrix.Rotation(tilt[1], 4, "Y"))
        verts = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segments,
                                      radius1=radius_bottom, radius2=radius_top, depth=height,
                                      matrix=m)["verts"]
        self._finish(verts, rgb, jitter)

    def blob(self, center, size, rgb, jitter=0.0, subdivisions=1, rot=None):
        m = Matrix.Translation(center) @ (rot or Matrix.Identity(4)) @ Matrix.Diagonal((*size, 1.0))
        verts = bmesh.ops.create_icosphere(self.bm, subdivisions=subdivisions, radius=1.0,
                                           matrix=m)["verts"]
        self._finish(verts, rgb, jitter)

    def export(self, name):
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        for i, rgb in enumerate(self.colors):
            mesh.materials.append(make_material(f"{name}_{i}", rgb))
        for f in self.bm.faces:
            f.smooth = False  # flat shading = the low-poly look
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT_DIR, name + ".glb"),
                                  export_format="GLB", export_yup=True, export_apply=True)
        print(f"{name}: {len(mesh.polygons)} faces")


def pine(name, green, seed):
    """Stacked faceted cones on a short trunk."""
    p = Prop(seed)
    r = p.rng
    p.cone(0, 1.3, 0.22, 0.16, TRUNK, segments=6)
    tiers = r.choice((3, 4))
    z, radius = 1.0, r.uniform(1.5, 1.8)
    for i in range(tiers):
        h = r.uniform(1.7, 2.0) * (1 - i * 0.12)
        p.cone(z, h, radius, 0.0, green, segments=r.choice((6, 7, 8)), jitter=0.08)
        z += h * 0.55
        radius *= 0.74
    p.export(name)


def round_tree(name, green, seed):
    """A slightly bent trunk with a few faceted leaf blobs on top."""
    p = Prop(seed)
    r = p.rng
    p.cone(0, 2.4, 0.24, 0.16, TRUNK, segments=6, tilt=(r.uniform(-0.06, 0.06), r.uniform(-0.06, 0.06)))
    main = r.uniform(1.6, 1.9)
    p.blob((0, 0, 3.3), (main, main, main * 0.85), green, jitter=0.12)
    for _ in range(r.choice((1, 2))):
        a = r.uniform(0, math.tau)
        s = main * r.uniform(0.55, 0.7)
        p.blob((math.cos(a) * main * 0.7, math.sin(a) * main * 0.7, 3.0 + r.uniform(-0.2, 0.5)),
               (s, s, s * 0.85), green, jitter=0.1)
    p.export(name)


def tall_pine(name, green, seed):
    """A tall, slim pine: more tiers, narrower, ~10 m."""
    p = Prop(seed)
    r = p.rng
    p.cone(0, 2.0, 0.24, 0.17, TRUNK, segments=6)
    z, radius = 1.6, r.uniform(1.4, 1.6)
    for i in range(r.choice((5, 6))):
        h = r.uniform(2.0, 2.3) * (1 - i * 0.09)
        p.cone(z, h, radius, 0.0, green, segments=r.choice((6, 7)), jitter=0.07)
        z += h * 0.6
        radius *= 0.8
    p.export(name)


def oak(name, green, seed):
    """A big, wide tree: thick trunk and a broad canopy of several blobs (~6 m tall, 6 m wide)."""
    p = Prop(seed)
    r = p.rng
    p.cone(0, 2.8, 0.36, 0.24, TRUNK, segments=6)
    p.blob((0, 0, 4.3), (2.3, 2.3, 1.6), green, jitter=0.15)
    for i in range(r.choice((3, 4))):
        a = math.tau * i / 4 + r.uniform(-0.4, 0.4)
        s = r.uniform(1.3, 1.6)
        p.blob((math.cos(a) * 1.9, math.sin(a) * 1.9, 3.8 + r.uniform(-0.2, 0.4)), (s, s, s * 0.8),
               green, jitter=0.12)
    p.export(name)


def poplar(name, green, seed):
    """A tall, slim, column-shaped tree (~8 m)."""
    p = Prop(seed)
    r = p.rng
    p.cone(0, 1.8, 0.2, 0.14, TRUNK, segments=6)
    tall = r.uniform(3.0, 3.6)
    p.blob((0, 0, 1.3 + tall), (r.uniform(0.95, 1.15), r.uniform(0.95, 1.15), tall), green, jitter=0.12)
    p.export(name)


def palm(name, leaves, seed):
    """A beach palm: a curved trunk made of segments, drooping fronds and coconuts."""
    p = Prop(seed)
    r = p.rng
    pos = Vector((0, 0, 0))
    lean = 0.0
    radius = 0.2
    for _ in range(6):  # each trunk piece leans a little more than the one below
        lean += r.uniform(0.05, 0.09)
        seg = 1.0
        direction = Vector((math.sin(lean), 0, math.cos(lean)))
        center = pos + direction * seg / 2
        p.cone(center.z - seg / 2, seg + 0.05, radius, radius * 0.88, PALM_TRUNK, segments=6,
               offset=(center.x, center.y), tilt=(0, lean))
        pos += direction * seg
        radius *= 0.9
    fronds = r.randint(6, 8)
    for k in range(fronds):
        a = math.tau * k / fronds + r.uniform(-0.2, 0.2)
        droop = r.uniform(0.3, 0.55)
        out = Vector((math.cos(a), math.sin(a), -0.25)) * 1.1
        rot = Matrix.Rotation(a, 4, "Z") @ Matrix.Rotation(droop, 4, "Y")
        p.blob(pos + out, (1.5, 0.32, 0.06), leaves, rot=rot)
    for k in range(r.randint(2, 3)):
        a = r.uniform(0, math.tau)
        p.blob(pos + Vector((math.cos(a) * 0.25, math.sin(a) * 0.25, -0.25)), (0.14, 0.14, 0.14), COCONUT)
    p.export(name)


def rock(name, grey, seed):
    p = Prop(seed)
    r = p.rng
    p.blob((0, 0, 0.25), (r.uniform(0.7, 0.9), r.uniform(0.55, 0.75), r.uniform(0.45, 0.6)),
           grey, jitter=0.15)
    if r.random() < 0.6:
        p.blob((0.55, 0.2, 0.1), (0.4, 0.35, 0.3), grey, jitter=0.08)
    p.export(name)


def grass(name, green, seed):
    """A tuft of thin 3-sided blades leaning outwards."""
    p = Prop(seed)
    r = p.rng
    for _ in range(r.randint(5, 7)):
        a = r.uniform(0, math.tau)
        d = r.uniform(0.0, 0.12)
        lean = r.uniform(0.15, 0.4)
        p.cone(0, r.uniform(0.35, 0.6), 0.045, 0.0, green, segments=3,
               offset=(math.cos(a) * d, math.sin(a) * d),
               tilt=(-math.sin(a) * lean, math.cos(a) * lean))
    p.export(name)


def bush(name, seed):
    p = Prop(seed)
    r = p.rng
    for _ in range(r.randint(2, 3)):
        s = r.uniform(0.4, 0.6)
        p.blob((r.uniform(-0.35, 0.35), r.uniform(-0.35, 0.35), s * 0.6), (s, s, s * 0.8), BUSH,
               jitter=0.06)
    p.export(name)


def flowers(name, petal, seed):
    """A few stems with little faceted flower heads."""
    p = Prop(seed)
    r = p.rng
    for _ in range(r.randint(3, 5)):
        x, y = r.uniform(-0.2, 0.2), r.uniform(-0.2, 0.2)
        h = r.uniform(0.25, 0.45)
        p.cone(0, h, 0.02, 0.015, STEM, segments=3, offset=(x, y))
        p.blob((x, y, h + 0.04), (0.07, 0.07, 0.05), petal, subdivisions=1)
    p.export(name)


os.makedirs(OUT_DIR, exist_ok=True)
for i, (key, green) in enumerate(PINE_GREENS.items()):
    pine(f"Pine_{key}", green, seed=10 + i)
for i, (key, green) in enumerate(ROUND_GREENS.items()):
    round_tree(f"Round_{key}", green, seed=20 + i)
for i, (key, green) in enumerate(PINE_GREENS.items()):
    tall_pine(f"PineTall_{key}", green, seed=70 + i)
for i, (key, green) in enumerate(OAK_GREENS.items()):
    oak(f"Oak_{key}", green, seed=80 + i)
for i, (key, green) in enumerate(POPLAR_GREENS.items()):
    poplar(f"Poplar_{key}", green, seed=90 + i)
for i, (key, leaves) in enumerate(PALM_LEAVES.items()):
    palm(f"Palm_{key}", leaves, seed=95 + i)
for i, (key, grey) in enumerate(ROCK_GREYS.items()):
    rock(f"Rock_{key}", grey, seed=30 + i)
for i, (key, green) in enumerate(GRASS.items()):
    grass(f"Grass_{key}", green, seed=40 + i)
bush("Bush_A", seed=50)
bush("Bush_B", seed=51)
for i, (key, petal) in enumerate(FLOWERS.items()):
    flowers(f"Flowers_{key}", petal, seed=60 + i)
print("Props exported")
