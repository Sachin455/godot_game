"""Generate the low-poly island (beaches, hills, forests' ground, ponds, river,
northern mountains) and export it for Godot.

Run from the godot_game folder (no Blender window needed, takes ~30 s):
    /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
        --python tools/blender/make_island.py

Outputs:
    assets/island/island.glb             the island, split into square chunks (+ collision
                                         + invisible shoreline wall)
    tools/generated/island_heights.json  height/zone samples + spawn point, for layout_island.py

How it works: the island is a grid of points. Each point's height is
    coast (beach sloping into the sea) + rolling hills + mountains,
then ponds and the river are carved in. Every triangle is coloured by its
height and steepness: sand, grass or rock. Water is the sea plane in Godot:
anything carved below WATER_LEVEL shows water.

Coordinates: we think in Godot terms (x right, z towards the camera, y up).
North (top of the screen) is -z. Blender is z-up, so a Godot point (x, y, z)
goes to Blender (x, -z, y); the glTF exporter converts it back.
"""
import json
import math
import os
import random

import sys

import bmesh
import bpy
from mathutils import Vector, noise

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mesh_utils import make_material, split_at_height, srgb_to_linear  # noqa: E402  (shared helpers)

# ---- Settings you can tweak -------------------------------------------------
SEED = 3              # change for a different coastline and hills
RADIUS = 100.0        # average distance from the centre to the south/east/west shore (m)
NORTH_STRETCH = 0.5   # the north half reaches this much further (0.5 = 50% longer)
GRID_STEP = 2.0       # distance between grid points; bigger = chunkier and cheaper
CHUNK_CELLS = 16      # grid cells per chunk side (16 * 2 m = 32 m chunks)
WATER_LEVEL = -0.6    # must match the Water node's height in main.tscn

# Beach, measured in metres from the shoreline (+ = inland, - = out at sea).
COAST = [(-99, -2.6), (-8, -2.6), (-4, -1.6), (0, -0.7), (3, -0.45), (5, -0.25),
         (6, 0.0), (99, 0.0)]

# Rolling hills from smooth noise.
HILL_HEIGHT = 5.0     # tallest hills (m)
HILL_SIZE = 45.0      # typical distance between hilltops (m); bigger = broader hills
FLAT_NEAR_COAST = 25  # hills fade out within this many metres of the beach
SPAWN_INLAND = 4.0    # player starts this far inland from the south shoreline
FLAT_NEAR_SPAWN = 20  # and the ground is flat within this distance of the start

# Mountains: (x, z, height, radius). North is negative z.
MOUNTAINS = [(-70, -110, 22, 26), (-40, -128, 30, 30), (-8, -138, 36, 32), (25, -130, 32, 30),
             (55, -115, 26, 28), (80, -95, 18, 22), (-90, -85, 15, 20)]

# Ponds: (x, z, radius). The river starts at the first pond and flows to the sea.
PONDS = [(-30, -30, 9), (35, 10, 7), (-55, 30, 6)]
RIVER = [(-30, -30), (-10, -15), (5, -25), (30, -30), (55, -20), (80, -30), (110, -35)]
RIVER_WIDTH = 6.0     # water width (m)
RIVER_BANKS = 5.0     # how wide the sloping banks are on each side (m)
RIVER_DEPTH = -1.0    # river bed height (water is at -0.6, so it's wadeable)
POND_DEPTH = -1.5

ROCK_SLOPE = 46.0     # faces steeper than this (degrees) are rock
ROCK_HEIGHT = 17.0    # faces higher than this are rock (mountain tops)
SAND_HEIGHT = -0.2    # faces lower than this are sand
WALL_INLAND = 1.5     # invisible wall sits this far inland from the shoreline

# Forest patches: the ground under them is darker, and layout_island.py fills them with trees.
FOREST_PATCHES = 34
SPAWN_MEADOW = 45.0   # no forest this close to the start point
FOREST_RADIUS = (14.0, 40.0)

# Ground colours (normal screen colours). Every triangle gets its own colour,
# mixed from these with soft noise, so the ground has gentle patches like a painting.
PALETTE = {
    "meadow": (0.58, 0.78, 0.34),        # sunny yellow-green
    "deep": (0.36, 0.62, 0.29),          # richer green patches
    "forest_floor": (0.26, 0.48, 0.25),  # dark green under the trees
    "high_grass": (0.42, 0.60, 0.36),    # cooler green high up the mountains
    "sand": (0.98, 0.88, 0.63),
    "wet_sand": (0.87, 0.76, 0.55),      # just above the water line
    "seabed": (0.78, 0.74, 0.58),        # under water (visible once the water is see-through)
    "rock": (0.62, 0.61, 0.62),
    "rock_dark": (0.50, 0.50, 0.54),
}

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
# The grid is a rectangle covering the island plus some sea floor.
MARGIN = 12.0
X_MIN, X_MAX = -RADIUS * 1.2 - MARGIN, RADIUS * 1.2 + MARGIN
Z_MIN, Z_MAX = -RADIUS * 1.2 * (1 + NORTH_STRETCH) - MARGIN, RADIUS * 1.2 + MARGIN
# ------------------------------------------------------------------------------

rng = random.Random(SEED)
waves = [(k, rng.uniform(0.03, 0.07), rng.uniform(0, math.tau)) for k in (2, 3, 5, 7, 11)]


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def shore_radius(a):
    """Distance from the centre to the shoreline in direction a (radians)."""
    wobble = 1.0 + sum(amp * math.sin(k * a + ph) for k, amp, ph in waves)
    north = max(0.0, -math.sin(a))  # 1 when pointing north (-z), 0 on the southern half
    return RADIUS * wobble * (1.0 + NORTH_STRETCH * north)


def inland_distance(x, z):
    """Metres from the shoreline: positive on land, negative at sea (approximate)."""
    return shore_radius(math.atan2(z, x)) - math.hypot(x, z)


def lerp_table(table, v):
    for (v0, h0), (v1, h1) in zip(table, table[1:]):
        if v <= v1:
            return h0 + (h1 - h0) * (v - v0) / (v1 - v0)
    return table[-1][1]


SPAWN = (0.0, shore_radius(math.pi / 2) - SPAWN_INLAND)  # due south (+z)


def distance_to_river(x, z):
    best = 1e9
    for (ax, az), (bx, bz) in zip(RIVER, RIVER[1:]):
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)))
        best = min(best, math.hypot(x - (ax + t * dx), z - (az + t * dz)))
    return best


def height(x, z):
    inland = inland_distance(x, z)
    h = lerp_table(COAST, inland)

    # Rolling hills: two layers of smooth noise, only the bumps that stick up.
    p = Vector((x / HILL_SIZE, z / HILL_SIZE, SEED))
    n = noise.noise(p) + 0.5 * noise.noise(p * 2.1)
    hills = HILL_HEIGHT * max(0.0, n) ** 1.3
    hills *= smoothstep(6, FLAT_NEAR_COAST, inland)
    hills *= smoothstep(FLAT_NEAR_SPAWN * 0.5, FLAT_NEAR_SPAWN,
                        math.hypot(x - SPAWN[0], z - SPAWN[1]))
    h += hills
    if inland > 6:  # tiny bumps so flat ground isn't perfectly flat
        h += 0.08 * noise.noise(Vector((x * 0.3, z * 0.3, SEED + 5)))

    for mx, mz, mh, mr in MOUNTAINS:
        t = math.hypot(x - mx, z - mz) / mr
        if t < 1.0:
            ridge = 1.0 + 0.3 * noise.noise(Vector((x * 0.08, z * 0.08, SEED + 10)))
            h += mh * (1.0 - t) ** 1.6 * ridge

    # Carve the river: bed in the middle, banks sloping up to the original ground.
    d = distance_to_river(x, z)
    s = smoothstep(RIVER_WIDTH / 2, RIVER_WIDTH / 2 + RIVER_BANKS, d)
    h = RIVER_DEPTH * (1 - s) + h * s if h > RIVER_DEPTH else h

    # Carve ponds the same way.
    for px, pz, pr in PONDS:
        d = math.hypot(x - px, z - pz)
        s = smoothstep(pr * 0.6, pr + 5.0, d)
        if h > POND_DEPTH:
            h = POND_DEPTH * (1 - s) + h * s
    return h


def zone(h, slope_deg):
    """What the ground is: 'Water' (under the water line), 'Sand', 'Grass' or 'Rock'."""
    if h < WATER_LEVEL:
        return "Water"
    if h < SAND_HEIGHT:
        return "Sand"
    if slope_deg > ROCK_SLOPE or h > ROCK_HEIGHT:
        return "Rock"
    return "Grass"


def to_blender(x, y, z):
    return (x, -z, y)


def pick_forests():
    """Choose forest patch centres on gentle, dry land away from the start point."""
    frng = random.Random(SEED + 100)
    forests = []
    tries = 0
    while len(forests) < FOREST_PATCHES and tries < 20000:
        tries += 1
        x, z = frng.uniform(X_MIN, X_MAX), frng.uniform(Z_MIN, Z_MAX)
        h = height(x, z)
        r = frng.uniform(*FOREST_RADIUS)
        # keep an open meadow in front of the start point, so the first view
        # looks out over the island towards the mountains
        if (inland_distance(x, z) > 12 and 0.0 <= h < 14.0
                and math.hypot(x - SPAWN[0], z - SPAWN[1]) > SPAWN_MEADOW + r):
            forests.append((round(x, 1), round(z, 1), round(r, 1)))
    return forests


FORESTS = pick_forests()


def forest_amount(x, z):
    """1 deep inside a forest patch, 0 outside, smooth in between."""
    return max((smoothstep(r, r * 0.6, math.hypot(x - fx, z - fz)) for fx, fz, r in FORESTS),
               default=0.0)


def mix(c1, c2, t):
    return tuple(a + (b - a) * t for a, b in zip(c1, c2))


def ground_color(kind, x, z, h):
    """The colour of one triangle (normal screen colour)."""
    P = PALETTE
    if kind == "Water":
        c = P["seabed"]
    elif kind == "Sand":
        c = P["wet_sand"] if h < -0.42 else P["sand"]
    elif kind == "Rock":
        c = mix(P["rock"], P["rock_dark"], 0.5 + 0.5 * noise.noise(Vector((x / 20, z / 20, SEED + 30))))
    else:
        patches = 0.5 + 0.5 * noise.noise(Vector((x / 35, z / 35, SEED + 20)))
        c = mix(P["meadow"], P["deep"], patches * 0.8)
        c = mix(c, P["forest_floor"], forest_amount(x, z) * 0.85)
        c = mix(c, P["high_grass"], smoothstep(6, 16, h))
    shade = rng.uniform(0.96, 1.04)  # each triangle a touch lighter/darker = faceted look
    return tuple(min(1.0, v * shade) for v in c)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def build_terrain():
    """One mesh object per chunk, so Godot can skip chunks that are off screen."""
    # One plain white material: the colour comes from each triangle's own colour.
    material = make_material("Terrain", (1.0, 1.0, 1.0))
    cols = int((X_MAX - X_MIN) / GRID_STEP) + 1
    rows = int((Z_MAX - Z_MIN) / GRID_STEP) + 1

    # Work out every grid point once (with a little random nudge so the triangles
    # look hand-made), so neighbouring chunks share exactly the same edge points.
    points = []
    for row in range(rows):
        line = []
        for col in range(cols):
            x = X_MIN + col * GRID_STEP
            z = Z_MIN + row * GRID_STEP
            if 0 < row < rows - 1 and 0 < col < cols - 1:
                x += rng.uniform(-0.3, 0.3) * GRID_STEP
                z += rng.uniform(-0.3, 0.3) * GRID_STEP
            line.append((x, height(x, z), z))
        points.append(line)

    chunks = 0
    for r0 in range(0, rows - 1, CHUNK_CELLS):
        for c0 in range(0, cols - 1, CHUNK_CELLS):
            r1, c1 = min(r0 + CHUNK_CELLS, rows - 1), min(c0 + CHUNK_CELLS, cols - 1)
            block = [points[r][c] for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
            if all(p[1] <= COAST[0][1] + 0.01 for p in block):
                continue  # flat sea floor only: nothing worth drawing
            build_chunk(f"Chunk_{r0 // CHUNK_CELLS:02d}_{c0 // CHUNK_CELLS:02d}",
                        points, r0, r1, c0, c1, material)
            chunks += 1
    print("terrain chunks:", chunks)


def build_chunk(name, points, r0, r1, c0, c1, material):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name + "-col", mesh)  # "-col" = Godot adds trimesh collision
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(material)
    bm = bmesh.new()
    color_layer = bm.loops.layers.float_color.new("Col")
    # Points are identified by a key: (r, c) for grid points, or ("cut", keyA, keyB)
    # for a point where the beach line crosses the edge between two grid points.
    pos = {(r, c): points[r][c] for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
    verts = {}

    def vert(key):
        if key not in verts:
            verts[key] = bm.verts.new(to_blender(*pos[key]))
        return verts[key]

    for r in range(r0, r1):
        for c in range(c0, c1):
            a, b, cc, d = (r, c), (r, c + 1), (r + 1, c + 1), (r + 1, c)
            # alternate the diagonal so the pattern doesn't look striped
            tris = ((a, b, cc), (a, cc, d)) if (r + c) % 2 == 0 else ((a, b, d), (b, cc, d))
            for tri in tris:
                for piece in split_at_height(tri, pos, SAND_HEIGHT):
                    bm.faces.new([vert(k) for k in piece])
    bm.normal_update()
    if sum(f.normal.z for f in bm.faces) < 0:  # make faces point up
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.normal_update()
    for f in bm.faces:
        center = f.calc_center_median()  # Blender (x, y, z) = Godot (x, -z, height)
        slope = math.degrees(math.acos(max(-1.0, min(1.0, f.normal.z))))
        kind = zone(center.z, slope)
        rgb = ground_color(kind, center.x, -center.y, center.z)
        linear = tuple(srgb_to_linear(c) for c in rgb) + (1.0,)
        for loop in f.loops:  # same colour on every corner = one flat colour per triangle
            loop[color_layer] = linear
        f.smooth = False  # flat shading = the low-poly look
    bm.to_mesh(mesh)
    bm.free()
    mesh.color_attributes.active_color = mesh.color_attributes["Col"]


def build_shoreline_wall(segments=160):
    """An invisible ring wall that stops the player walking into the sea."""
    mesh = bpy.data.meshes.new("Bounds")
    obj = bpy.data.objects.new("Bounds-colonly", mesh)  # "-colonly" = collision only, not drawn
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bottom, top = [], []
    for i in range(segments):
        a = math.tau * i / segments
        r = shore_radius(a) - WALL_INLAND
        x, z = r * math.cos(a), r * math.sin(a)
        bottom.append(bm.verts.new(to_blender(x, -2.0, z)))
        top.append(bm.verts.new(to_blender(x, max(height(x, z), 0.0) + 3.0, z)))
    for i in range(segments):
        j = (i + 1) % segments
        f = bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
        # Godot only collides on the side a face points to, so point it inwards.
        to_center = -f.calc_center_median()
        to_center.z = 0
        if f.normal.dot(to_center) < 0:
            f.normal_flip()
    bm.to_mesh(mesh)
    bm.free()


def export_heights(step=1.0):
    """Sample height, slope and zone on a regular grid for layout_island.py."""
    cols = int((X_MAX - X_MIN) / step) + 1
    rows = int((Z_MAX - Z_MIN) / step) + 1
    # heights first, then slopes from neighbouring samples (much faster than re-sampling)
    grid = [[height(X_MIN + c * step, Z_MIN + r * step) for c in range(cols)] for r in range(rows)]
    heights, slopes, zones = [], [], []
    for r in range(rows):
        for c in range(cols):
            h = grid[r][c]
            dx = (grid[r][min(c + 1, cols - 1)] - grid[r][max(c - 1, 0)]) / (2 * step)
            dz = (grid[min(r + 1, rows - 1)][c] - grid[max(r - 1, 0)][c]) / (2 * step)
            slope = math.degrees(math.atan(math.hypot(dx, dz)))
            heights.append(round(h, 2))
            slopes.append(round(slope))
            zones.append(zone(h, slope)[0])  # 'W', 'S', 'G' or 'R'
    out_dir = os.path.join(ROOT, "tools", "generated")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "island_heights.json"), "w") as f:
        json.dump({"x_min": X_MIN, "z_min": Z_MIN, "step": step, "cols": cols, "rows": rows,
                   "spawn": [SPAWN[0], height(*SPAWN), SPAWN[1]], "forests": FORESTS,
                   "heights": heights, "slopes": slopes, "zones": "".join(zones)}, f)


def export_model():
    out_dir = os.path.join(ROOT, "assets", "island")
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(out_dir, "island.glb"),
        export_format="GLB",
        export_yup=True,
        export_apply=True,
        export_vertex_color="NAME",  # include the per-triangle colours ("Col")
        export_vertex_color_name="Col",
    )


clear_scene()
build_terrain()
build_shoreline_wall()
export_model()
export_heights()
print("Island exported")
