"""Open the exported island in Blender's window for a look.

    /Applications/Blender.app/Contents/MacOS/Blender --python tools/blender/view_island.py
"""
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
GLB = os.path.normpath(os.path.join(HERE, "..", "..", "assets", "island", "island.glb"))

# Remove Blender's default cube, camera and light.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

bpy.ops.import_scene.gltf(filepath=GLB)

# The shoreline wall is invisible in the game, so hide it here too.
for obj in bpy.data.objects:
    if obj.name.startswith("Bounds"):
        obj.hide_set(True)


def setup_view():
    """Show real material colours and zoom to fit the island."""
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        space.shading.type = "SOLID"
        space.shading.color_type = "MATERIAL"
        region = next(r for r in area.regions if r.type == "WINDOW")
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.view3d.view_all()
    return None  # run once


# The window isn't ready while this script runs, so set the view a moment later.
bpy.app.timers.register(setup_view, first_interval=0.5)
