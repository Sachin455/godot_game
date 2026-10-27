# A floating touch joystick for phones.
#
# Put a thumb anywhere on the left part of the screen: the joystick appears
# under it. Dragging presses the same move_* input actions as the keyboard,
# so the player script works with both without any changes.
# Pushing it partway gives a smaller strength (the player walks instead of runs).
extends Control

## How far (in pixels) the knob can move from the centre.
@export var radius: float = 110.0
## Touches starting left of this fraction of the screen width control the joystick.
@export_range(0.1, 1.0) var touch_area: float = 0.5
## Ignore tiny movements near the centre (fraction of the radius).
@export_range(0.0, 0.9) var dead_zone: float = 0.12
@export var base_color: Color = Color(1, 1, 1, 0.22)
@export var knob_color: Color = Color(1, 1, 1, 0.6)

var _touch_index := -1      # which finger is using the joystick (-1 = none)
var _center := Vector2.ZERO  # where the finger first touched
var _knob := Vector2.ZERO    # knob offset from the centre


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE  # never block touches for other buttons


# _input sees every touch on the screen, not only ones on top of this Control.
func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed and _touch_index == -1 \
				and event.position.x < get_viewport_rect().size.x * touch_area:
			_touch_index = event.index
			_center = event.position
			_set_knob(Vector2.ZERO)
		elif not event.pressed and event.index == _touch_index:
			_touch_index = -1
			_set_knob(Vector2.ZERO)
	elif event is InputEventScreenDrag and event.index == _touch_index:
		_set_knob((event.position - _center).limit_length(radius))


func _set_knob(offset: Vector2) -> void:
	_knob = offset
	var v := offset / radius
	if v.length() < dead_zone:
		v = Vector2.ZERO
	# Turn the stick direction into the four movement actions, with strength 0-1.
	_press("move_right", maxf(v.x, 0.0))
	_press("move_left", maxf(-v.x, 0.0))
	_press("move_back", maxf(v.y, 0.0))
	_press("move_forward", maxf(-v.y, 0.0))
	queue_redraw()


func _press(action: String, strength: float) -> void:
	if strength > 0.0:
		Input.action_press(action, strength)
	else:
		Input.action_release(action)


func _draw() -> void:
	if _touch_index == -1:
		return  # only visible while a finger is on it
	draw_circle(_center, radius, base_color, true, -1.0, true)
	draw_circle(_center, radius, Color(1, 1, 1, 0.35), false, 3.0, true)
	draw_circle(_center + _knob, radius * 0.42, knob_color, true, -1.0, true)
