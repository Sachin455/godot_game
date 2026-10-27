"""Small helpers shared by the Blender generator scripts in this folder."""
import bpy


def srgb_to_linear(c):
    """Blender stores colours as 'linear' light values; we write normal screen (sRGB) colours."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_material(name, rgb):
    """A plain, flat-coloured material. rgb is a normal screen colour (0-1 each)."""
    mat = bpy.data.materials.new(name)
    r, g, b = (srgb_to_linear(c) for c in rgb)
    mat.diffuse_color = (r, g, b, 1.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
    return mat


def split_at_height(tri, pos, level):
    """Cut a triangle along the line where the ground is exactly `level` high.

    Without this, every triangle is one colour, and a border between colours
    (sand/grass, rock/snow) looks like a saw blade. Cutting along the exact
    height gives a smooth border that follows the terrain.

    tri is 3 point keys, pos maps key -> (x, height, z). Returns 1 triangle
    (no cut) or 3 pieces. New cut points are added to `pos` and reused by the
    neighbouring triangle, so the mesh has no cracks.
    """
    above = [pos[k][1] >= level for k in tri]
    if all(above) or not any(above):
        return [tri]
    # Find the corner that is alone on its side, and rotate it to the front
    # (rotating keeps the triangle's winding, so it still faces up).
    lone = next(i for i in range(3) if above.count(above[i]) == 1)
    a, b, c = tri[lone:] + tri[:lone]

    def cut(k1, k2):
        key = ("cut", level) + tuple(sorted((k1, k2), key=str))
        if key not in pos:
            p1, p2 = pos[k1], pos[k2]
            t = (level - p1[1]) / (p2[1] - p1[1])
            pos[key] = tuple(p1[i] + (p2[i] - p1[i]) * t for i in range(3))
        return key

    ab, ac = cut(a, b), cut(a, c)
    return [(a, ab, ac), (ab, b, c), (ab, c, ac)]


def split_at_heights(tri, pos, levels):
    """split_at_height for several levels in a row (e.g. a grass line and a snow line)."""
    pieces = [tri]
    for level in levels:
        pieces = [p for piece in pieces for p in split_at_height(piece, pos, level)]
    return pieces
