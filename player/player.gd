# The player: walks with the move_* input actions, turns to face where
# it walks, falls with gravity, and plays the matching character animation.
# CharacterBody3D is Godot's node for "things you control with code"
# that still bump into walls and stand on floors.
extends CharacterBody3D

## How fast the player moves at full input (metres per second).
@export var move_speed: float = 5.0
## How quickly the player turns to face the walking direction. Higher = snappier.
@export var turn_speed: float = 12.0
## Below this speed we play Walk, above it Run (m/s).
@export var run_threshold: float = 3.0
## The ground speed each animation looks right at; used to speed animations up/down.
@export var walk_anim_speed: float = 1.6
@export var run_anim_speed: float = 4.3
## How long animations take to blend into each other (seconds).
@export var blend_time: float = 0.15

# The character model's AnimationPlayer (found automatically in _ready).
var _anim: AnimationPlayer


func _ready() -> void:
	_anim = $Model.find_children("*", "AnimationPlayer", true, false)[0]
	# The looping animations need to be told to loop; Chop plays once.
	for anim_name in ["Idle", "Walk", "Run"]:
		_anim.get_animation(anim_name).loop_mode = Animation.LOOP_LINEAR
	_anim.play("Idle")


# _physics_process runs at a fixed rate (60 times a second by default).
# Movement code goes here so it behaves the same on fast and slow phones.
func _physics_process(delta: float) -> void:
	# Gravity: if we're in the air, speed up downwards.
	if not is_on_floor():
		velocity += get_gravity() * delta

	# Read the input actions as a 2D direction (x = left/right, y = forward/back).
	# Works for keyboard now and the touch joystick later, because both
	# trigger the same actions.
	# Small dead zone here: the touch joystick already ignores tiny movements itself.
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back", 0.05)

	# Turn the 2D input into a 3D direction on the ground.
	# The camera never rotates, so "forward" on screen is always -Z in the world.
	var direction := Vector3(input.x, 0.0, input.y)

	velocity.x = direction.x * move_speed
	velocity.z = direction.z * move_speed

	# Smoothly turn to face where we're walking (only while actually moving).
	if direction.length() > 0.1:
		var target_angle := atan2(-direction.x, -direction.z)
		rotation.y = lerp_angle(rotation.y, target_angle, turn_speed * delta)

	# Godot moves the body, slides it along walls and updates is_on_floor().
	move_and_slide()
	_update_animation()


# Pick Idle / Walk / Run from how fast we're really moving over the ground.
func _update_animation() -> void:
	var ground_speed := Vector2(velocity.x, velocity.z).length()
	var wanted := "Idle"
	var anim_speed := 1.0
	if ground_speed > run_threshold:
		wanted = "Run"
		anim_speed = ground_speed / run_anim_speed
	elif ground_speed > 0.2:
		wanted = "Walk"
		anim_speed = ground_speed / walk_anim_speed
	if _anim.current_animation != wanted:
		_anim.play(wanted, blend_time)
	_anim.speed_scale = anim_speed
