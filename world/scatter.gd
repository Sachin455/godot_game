# Draws thousands of copies of small models (trees, rocks, grass...) cheaply.
#
# Instead of one node per tree, it groups copies of the same model that are in
# the same square of the map (a "chunk") into one MultiMeshInstance3D: the
# phone draws the whole group in one go. Chunks far from the camera are skipped
# entirely thanks to view_distance.
#
# If collision_radius > 0 (trees, rocks), it also adds an invisible solid
# cylinder at each copy so the player bumps into it.
#
# The positions live in `instances`, written by tools/layout_island.py.
# @tool so everything also shows up in the editor.
@tool
extends Node3D

## Model path -> flat list of numbers, 5 per copy: x, y, z, rotation (radians), scale.
@export var instances: Dictionary = {}:
	set(value):
		instances = value
		_build()
## Size of each square group, in metres.
@export var chunk_size: float = 32.0
## Copies further than this from the camera aren't drawn.
@export var view_distance: float = 50.0
## Shadows cost extra; worth it for trees, not for tiny plants.
@export var cast_shadows: bool = false
## Radius of the solid cylinder around each copy (0 = walk-through, no collision).
@export var collision_radius: float = 0.0
@export var collision_height: float = 2.0

@export_group("Wind")
## How far the tops sway in the wind (metres). 0 = no wind (rocks).
@export var wind_sway: float = 0.0
## Height in the model where the sway is full (≈ the plant's height).
@export var sway_height: float = 6.0
## How fast the plants move back and forth.
@export var sway_speed: float = 1.3

const FOLIAGE_SHADER := preload("res://world/foliage.gdshader")


func _ready() -> void:
	_build()


func _build() -> void:
	if not is_node_ready():
		return
	# Remove what we built last time. These nodes are never saved into the scene
	# (we don't set their owner); they're rebuilt every time the scene loads.
	for child in get_children():
		child.queue_free()

	for model_path in instances:
		var parts := _mesh_parts(model_path)
		var data: PackedFloat32Array = instances[model_path]
		# Sort the copies into chunks: chunk key -> list of transforms.
		var chunks := {}
		for i in range(0, data.size(), 5):
			var pos := Vector3(data[i], data[i + 1], data[i + 2])
			var basis := Basis(Vector3.UP, data[i + 3]).scaled(Vector3.ONE * data[i + 4])
			var key := Vector2i(floori(pos.x / chunk_size), floori(pos.z / chunk_size))
			if not chunks.has(key):
				chunks[key] = []
			chunks[key].append(Transform3D(basis, pos))
		for key in chunks:
			for part in parts:
				_add_group(part.mesh, part.transform, chunks[key])
			# Collision is only needed while playing, not in the editor.
			if collision_radius > 0.0 and not Engine.is_editor_hint():
				_add_collision(chunks[key])


# A model can contain several meshes; return each with its offset inside the model.
func _mesh_parts(model_path: String) -> Array:
	var scene: PackedScene = load(model_path)
	var root := scene.instantiate()
	var parts := []
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		var offset := Transform3D.IDENTITY
		var node: Node = mi
		while node != root:
			offset = (node as Node3D).transform * offset
			node = node.get_parent()
		var mesh: Mesh = _windy_copy(mi.mesh) if wind_sway > 0.0 else mi.mesh
		parts.append({"mesh": mesh, "transform": offset})
	root.free()
	return parts


# A copy of the mesh whose colours are drawn with the wind shader (foliage.gdshader).
# Each surface keeps its own colour; only the movement is added.
func _windy_copy(mesh: Mesh) -> Mesh:
	var copy: Mesh = mesh.duplicate()
	for i in copy.get_surface_count():
		var original := copy.surface_get_material(i)
		var mat := ShaderMaterial.new()
		mat.shader = FOLIAGE_SHADER
		if original is BaseMaterial3D:
			mat.set_shader_parameter("albedo", original.albedo_color)
		mat.set_shader_parameter("sway", wind_sway)
		mat.set_shader_parameter("sway_height", sway_height)
		mat.set_shader_parameter("speed", sway_speed)
		copy.surface_set_material(i, mat)
	return copy


func _add_group(mesh: Mesh, offset: Transform3D, transforms: Array) -> void:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = transforms.size()
	for i in transforms.size():
		mm.set_instance_transform(i, transforms[i] * offset)
	var group := MultiMeshInstance3D.new()
	group.multimesh = mm
	group.visibility_range_end = view_distance
	group.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast_shadows \
		else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(group)


# One invisible solid body per chunk, with a cylinder for every copy in it.
func _add_collision(transforms: Array) -> void:
	var shape := CylinderShape3D.new()
	shape.radius = collision_radius
	shape.height = collision_height
	var body := StaticBody3D.new()
	for t in transforms:
		var col := CollisionShape3D.new()
		col.shape = shape
		col.position = t.origin + Vector3.UP * collision_height / 2.0
		body.add_child(col)
	add_child(body)
