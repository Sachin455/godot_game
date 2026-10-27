# The island scene's script.
# The terrain model stores a colour for every triangle (made in Blender by
# tools/blender/make_island.py). This gives it a material that shows those
# colours, so the ground gets its soft meadow / forest / sand patches.
@tool
extends Node3D

const TERRAIN_MATERIAL := preload("res://world/terrain_material.tres")


func _ready() -> void:
	for node in $Terrain.find_children("*", "MeshInstance3D", true, false):
		(node as MeshInstance3D).material_override = TERRAIN_MATERIAL
