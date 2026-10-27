# The main scene's script: sets up the start of the game.
extends Node3D


func _ready() -> void:
	# Put the player on the island's spawn point (a Marker3D written by
	# tools/layout_island.py), then move the camera there instantly so it
	# doesn't glide across the whole map on the first frame.
	$Player.global_position = $Island/PlayerSpawn.global_position
	$FollowCamera.snap_to_target()
