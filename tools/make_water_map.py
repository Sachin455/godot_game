"""Write the water depth map + water material used by world/water.gdshader.

Run from the godot_game folder after make_island.py:
    python3 tools/make_water_map.py

Outputs:
    assets/island/water_depth.png   grayscale: black = shoreline, white = MAX_DEPTH or deeper
    world/water_material.tres       the water material, set up to read that map

The water shader uses the depth to colour itself (pale see-through shallows,
turquoise, deep blue) and to draw foam where it meets the land. Because the
island is generated, we know the depth everywhere in advance, which is much
cheaper on phones than measuring it every frame.
"""
import json
import struct
import zlib
from collections import deque

WATER_LEVEL = -0.6  # must match make_island.py and the Water node in main.tscn
MAX_DEPTH = 6.0     # depth that counts as fully "deep" (white in the map)
SEA_FLOOR = -2.6    # the flat sea floor height in make_island.py
DEEPEN = 0.12       # out past the slope, the sea gets this much deeper per metre

hm = json.load(open("tools/generated/island_heights.json"))
cols, rows, step = hm["cols"], hm["rows"], hm["step"]

heights = hm["heights"]

# The island's sea floor is flat after a few metres, but the water should keep
# getting deeper (and bluer) further out. So for flat-floor spots, measure how
# far they are from the nearest slope/shore (a "flood fill" outwards) and add depth.
far = [-1] * (cols * rows)
queue = deque()
for i, h in enumerate(heights):
    if h > SEA_FLOOR + 0.01:  # land, beach or sloping sea floor: distance 0
        far[i] = 0
        queue.append(i)
while queue:
    i = queue.popleft()
    r, c = divmod(i, cols)
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and far[nr * cols + nc] < 0:
            far[nr * cols + nc] = far[i] + 1
            queue.append(nr * cols + nc)

# One grey value per grid point: how deep the water is there.
rows_bytes = []
for r in range(rows):
    line = bytearray([0])  # PNG "no filter" marker at the start of each row
    for c in range(cols):
        i = r * cols + c
        depth = WATER_LEVEL - heights[i] + max(far[i], 0) * step * DEEPEN
        v = round(max(0.0, min(1.0, depth / MAX_DEPTH)) * 255)
        line += bytes((v, v, v))  # same value in red, green and blue
    rows_bytes.append(bytes(line))


def png_chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


png = (b"\x89PNG\r\n\x1a\n"
       + png_chunk(b"IHDR", struct.pack(">IIBBBBB", cols, rows, 8, 2, 0, 0, 0))  # 8-bit RGB
       + png_chunk(b"IDAT", zlib.compress(b"".join(rows_bytes), 9))
       + png_chunk(b"IEND", b""))
with open("assets/island/water_depth.png", "wb") as f:
    f.write(png)

# The map's pixel centres sit on the grid points, so the map starts half a step earlier.
origin = (hm["x_min"] - step / 2, hm["z_min"] - step / 2)
size = (cols * step, rows * step)
with open("world/water_material.tres", "w") as f:
    f.write(f"""[gd_resource type="ShaderMaterial" load_steps=5 format=3]

[ext_resource type="Shader" path="res://world/water.gdshader" id="1_shader"]
[ext_resource type="Texture2D" path="res://assets/island/water_depth.png" id="2_depth"]

[sub_resource type="FastNoiseLite" id="Noise_ripples"]
frequency = 0.02

[sub_resource type="NoiseTexture2D" id="NoiseTex_ripples"]
width = 256
height = 256
seamless = true
noise = SubResource("Noise_ripples")

[resource]
render_priority = 0
shader = ExtResource("1_shader")
shader_parameter/depth_map = ExtResource("2_depth")
shader_parameter/map_origin = Vector2({origin[0]:.2f}, {origin[1]:.2f})
shader_parameter/map_size = Vector2({size[0]:.2f}, {size[1]:.2f})
shader_parameter/max_depth = {MAX_DEPTH}
shader_parameter/noise_tex = SubResource("NoiseTex_ripples")
""")
print(f"Wrote water_depth.png ({cols}x{rows}) and water_material.tres")
