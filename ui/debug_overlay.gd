# A small performance readout for testing on phones:
# frames per second, triangles drawn and draw calls (how many separate things
# the graphics chip is asked to draw). Turn it off with show_stats in the Inspector.
extends Label

@export var show_stats: bool = true
## How often to refresh the numbers (seconds).
@export var refresh: float = 0.5

var _timer := 0.0


func _ready() -> void:
	visible = show_stats


func _process(delta: float) -> void:
	if not show_stats:
		return
	_timer -= delta
	if _timer > 0.0:
		return
	_timer = refresh
	var triangles := Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
	var draw_calls := Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
	text = "FPS %d   |   %dk triangles   |   %d draw calls" % [
		Engine.get_frames_per_second(), int(triangles / 1000.0), int(draw_calls)]
