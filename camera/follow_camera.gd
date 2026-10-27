# A fixed-angle camera that smoothly follows a target (the player).
# It never rotates while playing: it only slides along with the target,
# like the camera in "Just Keep Fishing".
extends Camera3D

## The node to follow. Set it in the Inspector (drag the Player onto it).
@export var target: Node3D
## Where the camera sits relative to the target. y = height, z = distance behind.
@export var offset: Vector3 = Vector3(0, 3.2, 9)
## The camera aims this high above the target's feet. Higher = looks more towards
## the horizon (more sky and distant mountains, less ground around the player).
@export var look_height: float = 1.5
## How quickly the camera catches up. Higher = tighter, lower = floatier.
@export var follow_speed: float = 5.0


func _ready() -> void:
	if target == null:
		push_warning("FollowCamera has no target set")
		return
	snap_to_target()


## Jump straight to the right spot and aim at the target (no smooth glide).
## The angle set here stays the same for the whole game.
## Call this after teleporting the target, e.g. when the player spawns.
func snap_to_target() -> void:
	global_position = target.global_position + offset
	look_at(target.global_position + Vector3.UP * look_height)


# Same fixed rate as the player, so the camera and player move in step (no jitter).
func _physics_process(delta: float) -> void:
	if target == null:
		return
	var wanted := target.global_position + offset
	# lerp = move a fraction of the way there each frame, which gives smooth easing.
	global_position = global_position.lerp(wanted, clampf(follow_speed * delta, 0.0, 1.0))
