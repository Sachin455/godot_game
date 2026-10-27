"""Write world/island.tscn: the Blender island plus forests, rocks, plants and the spawn point.

Run from the godot_game folder after make_island.py (and make_props.py once):
    python3 tools/layout_island.py

Uses tools/generated/island_heights.json (made by make_island.py): ground height,
slope and type, the forest patches, and the spawn point.
Trees, rocks and plants are stored as position lists that world/scatter.gd draws
in bulk, so thousands of them stay cheap.
Note: this overwrites world/island.tscn, so hand-placed changes there are lost.
"""
import json
import math
import random

SEED = 7               # change for a different arrangement
SPAWN_CLEAR = 6.0      # keep this radius around the player's start empty
LP = "res://assets/lowpoly/%s.glb"

FOREST_SPACING = 11.0  # m² of ground per tree inside a forest (lower = denser)
MEADOW_TREES = 160     # lone trees out in the open
PALMS = 160            # palm trees along the beaches
ROCKS = 120
DECOR = [  # (model, scale range, how many, where: "any" / "forest" / "meadow")
    ("Grass_A", (0.9, 1.4), 2500, "any"),
    ("Grass_B", (0.9, 1.4), 1500, "meadow"),
    ("Bush_A", (0.8, 1.3), 250, "forest"),
    ("Bush_B", (0.8, 1.3), 250, "any"),
    ("Flowers_A", (0.9, 1.3), 300, "meadow"),
    ("Flowers_B", (0.9, 1.3), 300, "meadow"),
    ("Flowers_C", (0.9, 1.3), 300, "meadow"),
]
PEBBLES = 220

hm = json.load(open("tools/generated/island_heights.json"))
X_MIN, Z_MIN, STEP = hm["x_min"], hm["z_min"], hm["step"]
COLS, ROWS = hm["cols"], hm["rows"]
SPAWN = hm["spawn"]
FORESTS = hm["forests"]
rng = random.Random(SEED)


def sample(x, z):
    """(height, slope in degrees, zone letter) at a point. Height is smoothly interpolated."""
    fx, fz = (x - X_MIN) / STEP, (z - Z_MIN) / STEP
    c = max(0, min(int(fx), COLS - 2))
    r = max(0, min(int(fz), ROWS - 2))
    tx, tz = fx - c, fz - r
    h = lambda cc, rr: hm["heights"][rr * COLS + cc]
    height = (h(c, r) * (1 - tx) * (1 - tz) + h(c + 1, r) * tx * (1 - tz)
              + h(c, r + 1) * (1 - tx) * tz + h(c + 1, r + 1) * tx * tz)
    i = min(round(fz), ROWS - 1) * COLS + min(round(fx), COLS - 1)
    return height, hm["slopes"][i], hm["zones"][i]


def in_forest(x, z):
    return any(math.hypot(x - fx, z - fz) < fr for fx, fz, fr in FORESTS)


# Fast "is anything too close?" check: remember placed things in 4 m grid cells.
CELL = 4.0
placed = {}


def is_free(x, z, gap):
    if math.hypot(x - SPAWN[0], z - SPAWN[2]) < SPAWN_CLEAR:
        return False
    cx, cz = int(x // CELL), int(z // CELL)
    for i in range(cx - 1, cx + 2):
        for j in range(cz - 1, cz + 2):
            for px, pz, pgap in placed.get((i, j), ()):
                if math.hypot(x - px, z - pz) < (gap + pgap) / 2:
                    return False
    return True


def try_spot(x, z, gap, zones="G", max_slope=25.0, min_h=-99.0, max_h=99.0):
    """Return (x, y, z) if the spot is suitable and free (and claim it), else None."""
    h, slope, zn = sample(x, z)
    if zn not in zones or slope > max_slope or not (min_h <= h <= max_h):
        return None
    if not is_free(x, z, gap):
        return None
    placed.setdefault((int(x // CELL), int(z // CELL)), []).append((x, z, gap))
    return x, h - 0.05, z  # sink a touch so nothing floats on slopes


def random_point():
    return (rng.uniform(X_MIN + 1, X_MIN + (COLS - 1) * STEP - 1),
            rng.uniform(Z_MIN + 1, Z_MIN + (ROWS - 1) * STEP - 1))


def random_spot(gap, tries=20000, where="any", **kw):
    for _ in range(tries):
        x, z = random_point()
        if where == "forest" and not in_forest(x, z):
            continue
        if where == "meadow" and in_forest(x, z):
            continue
        spot = try_spot(x, z, gap, **kw)
        if spot:
            return spot
    return None


instances = {"Trees": {}, "Rocks": {}, "Decor": {}}


def add(group, model, spot, scale):
    instances[group].setdefault(LP % model, []).extend(
        [spot[0], spot[1], spot[2], rng.uniform(0, math.tau), scale])


# Tree types: (model names, size range). Mixing types and sizes makes the
# forest roof go up and down instead of being one flat height.
TREE_TYPES = {
    "pine": (["Pine_A", "Pine_B", "Pine_C"], (0.75, 1.3)),
    "tall_pine": (["PineTall_A", "PineTall_B", "PineTall_C"], (0.85, 1.35)),
    "round": (["Round_A", "Round_B", "Round_C"], (0.7, 1.25)),
    "oak": (["Oak_A", "Oak_B"], (0.8, 1.25)),
    "poplar": (["Poplar_A", "Poplar_B"], (0.85, 1.25)),
}
NORTH_MIX = {"pine": 40, "tall_pine": 30, "round": 15, "oak": 5, "poplar": 10}   # cool / high
SOUTH_MIX = {"pine": 15, "tall_pine": 10, "round": 35, "oak": 25, "poplar": 15}  # warm / low


def pick_tree(z, h):
    """Returns (model, scale). Pines up north and high up, broadleaf trees in the south."""
    mix = NORTH_MIX if (z < -40 or h > 4) else SOUTH_MIX
    kind = rng.choices(list(mix), weights=list(mix.values()))[0]
    models, (s0, s1) = TREE_TYPES[kind]
    scale = rng.uniform(s0, s1)
    if rng.random() < 0.15:  # some young trees
        scale *= rng.uniform(0.5, 0.7)
    return rng.choice(models), scale


def near_beach(x, z):
    """True if there's sand within ~6 m (good palm tree spots)."""
    return any(sample(x + dx, z + dz)[2] == "S"
               for dx, dz in ((6, 0), (-6, 0), (0, 6), (0, -6), (4, 4), (-4, -4), (4, -4), (-4, 4)))


# ---- Trees: fill the forest patches, then a few lone meadow trees --------------
trees = 0
for fx, fz, fr in FORESTS:
    for _ in range(int(math.pi * fr * fr / FOREST_SPACING)):
        a, d = rng.uniform(0, math.tau), fr * math.sqrt(rng.random())
        spot = try_spot(fx + d * math.cos(a), fz + d * math.sin(a), gap=2.6, max_slope=32)
        if spot:
            model, scale = pick_tree(spot[2], spot[1])
            add("Trees", model, spot, scale)
            trees += 1
for _ in range(MEADOW_TREES):
    spot = random_spot(gap=7.0, max_slope=25, where="meadow")
    if spot:
        model, scale = pick_tree(spot[2], spot[1])
        add("Trees", model, spot, scale)
        trees += 1
palms = 0
for _ in range(PALMS * 500):  # try many spots; keep the ones right behind a beach
    if palms >= PALMS:
        break
    x, z = random_point()
    if sample(x, z)[2] == "G" and near_beach(x, z):
        spot = try_spot(x, z, gap=4.0, max_slope=20)
        if spot:
            add("Trees", f"Palm_{rng.choice('AB')}", spot, rng.uniform(0.85, 1.2))
            palms += 1

# ---- Rocks --------------------------------------------------------------------
for _ in range(ROCKS):
    spot = random_spot(gap=3.0, zones="GR", max_slope=40)
    if spot:
        add("Rocks", f"Rock_{rng.choice('ABC')}", spot, rng.uniform(0.8, 1.8))

# ---- Small plants and beach pebbles (no collision) -----------------------------
plants = 0
for model, (s0, s1), count, where in DECOR:
    for _ in range(count):
        spot = random_spot(gap=1.0, tries=300, where=where, max_slope=32)
        if spot:
            add("Decor", model, spot, rng.uniform(s0, s1))
            plants += 1
for _ in range(PEBBLES):
    spot = random_spot(gap=1.5, tries=2000, zones="S", max_slope=20, min_h=-0.55)
    if spot:
        add("Decor", f"Rock_{rng.choice('ABC')}", (spot[0], spot[1] + 0.02, spot[2]),
            rng.uniform(0.15, 0.3))
        plants += 1

# ---- Write the scene ----------------------------------------------------------
SCATTER = {  # node name -> extra settings for world/scatter.gd
    "Trees": "view_distance = 160.0\ncast_shadows = true\ncollision_radius = 0.35\ncollision_height = 3.0\n"
             "wind_sway = 0.25\nsway_height = 7.0\nsway_speed = 1.1\n",
    "Rocks": "view_distance = 120.0\ncast_shadows = true\ncollision_radius = 0.7\ncollision_height = 1.2\n",
    "Decor": "view_distance = 55.0\nwind_sway = 0.12\nsway_height = 0.5\nsway_speed = 1.8\n",
}
fmt = lambda vals: ", ".join(f"{round(v, 3):g}" for v in vals)
out = ["[gd_scene load_steps=4 format=3]\n",
       '[ext_resource type="PackedScene" path="res://assets/island/island.glb" id="1_island"]',
       '[ext_resource type="Script" path="res://world/scatter.gd" id="2_scatter"]',
       '[ext_resource type="Script" path="res://world/island.gd" id="3_island"]',
       '\n[node name="Island" type="Node3D"]\nscript = ExtResource("3_island")\n',
       '[node name="Terrain" parent="." instance=ExtResource("1_island")]\n',
       '[node name="PlayerSpawn" type="Marker3D" parent="."]\n'
       f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {SPAWN[0]:g}, {SPAWN[1] + 0.1:.2f}, {SPAWN[2]:.2f})\n"]
for group, settings in SCATTER.items():
    body = ",\n".join(f'"{path}": PackedFloat32Array({fmt(vals)})'
                      for path, vals in sorted(instances[group].items()))
    out.append(f'[node name="{group}" type="Node3D" parent="."]\nscript = ExtResource("2_scatter")\n'
               f"{settings}instances = {{\n{body}\n}}\n")

with open("world/island.tscn", "w") as f:
    f.write("\n".join(out))
print(f"Wrote world/island.tscn: {trees} trees + {palms} palms, "
      f"{sum(len(v) // 5 for v in instances['Rocks'].values())} rocks, {plants} plants")
