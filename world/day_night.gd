# Day and night: moves the sun across the sky and changes the colours of the
# sky, haze, light, distant mountains, clouds and water as time passes.
#
# Time of day runs from 0 to 24 (hours). The colour gradients below go from
# midnight (left, 0.0) through sunrise (0.25), noon (0.5), sunset (0.75) back
# to midnight (right, 1.0). Click a gradient in the Inspector to edit it.
#
# Other scripts can read `hour`, `is_night` and `day`, and listen for the
# `new_day` signal (e.g. hunger, or wolves that come out at night).
extends Node

signal new_day(day: int)

@export var sun: DirectionalLight3D
@export var world_environment: WorldEnvironment
@export var water: MeshInstance3D

@export_group("Time")
## Real minutes for one full day (24 hours). Lower = faster days.
@export var day_length_minutes: float = 10.0
## The hour the game starts at.
@export_range(0.0, 24.0) var start_hour: float = 9.0
## Stop time (handy for screenshots or testing a certain hour).
@export var paused: bool = false

@export_group("Sun and moon")
## How high the sun climbs at noon (degrees above the horizon).
@export_range(10.0, 85.0) var max_sun_height: float = 60.0
@export var sun_energy: float = 1.1
@export var moon_energy: float = 0.22
@export var ambient_energy: float = 0.7

@export_group("Colours")
@export var sky_top: Gradient
@export var sky_horizon: Gradient   ## also used for the haze (fog)
@export var light_color: Gradient   ## sunlight, then moonlight at night
@export var ambient_color: Gradient ## the colour of shadows
@export var scenery_tint: Gradient  ## darkens/tints far mountains, clouds and water

var hour: float = 9.0
var day: int = 1
var is_night: bool = false


func _ready() -> void:
	hour = start_hour
	_apply()


func _process(delta: float) -> void:
	if paused:
		return
	hour += delta * 24.0 / (day_length_minutes * 60.0)
	if hour >= 24.0:
		hour -= 24.0
		day += 1
		new_day.emit(day)
	_apply()


func _apply() -> void:
	var t := hour / 24.0  # 0..1 through the day
	# The sun goes round in a circle: rises in the east (+x) at 6:00, is highest
	# in the south (+z, behind the camera) at 12:00, sets in the west at 18:00.
	var angle := (t - 0.25) * TAU
	var tilt := deg_to_rad(max_sun_height)
	var to_sun := Vector3(cos(angle), sin(angle) * sin(tilt), sin(angle) * cos(tilt)).normalized()
	is_night = to_sun.y < 0.0
	# At night the same light becomes the moon, on the opposite side of the sky.
	var to_light := -to_sun if is_night else to_sun
	if sun:
		sun.basis = Basis.looking_at(-to_light, Vector3.UP)  # the light shines along its -Z
		sun.light_color = light_color.sample(t)
		# Fade the light out near the horizon, so the sun/moon swap is invisible.
		var strength := smoothstep(0.0, 0.25, to_light.y)
		sun.light_energy = (moon_energy if is_night else sun_energy) * strength
		sun.shadow_enabled = strength > 0.05

	var horizon := sky_horizon.sample(t)
	var tint := scenery_tint.sample(t)
	if world_environment:
		var env := world_environment.environment
		env.ambient_light_color = ambient_color.sample(t)
		env.ambient_light_energy = ambient_energy
		env.fog_light_color = horizon
		var sky_mat := env.sky.sky_material as ShaderMaterial
		if sky_mat:
			sky_mat.set_shader_parameter("sky_top", sky_top.sample(t))
			sky_mat.set_shader_parameter("sky_horizon", horizon)
			sky_mat.set_shader_parameter("haze_color", horizon)
			sky_mat.set_shader_parameter("light_tint", tint)
			sky_mat.set_shader_parameter("sun_glow", light_color.sample(t))
			sky_mat.set_shader_parameter("star_amount", smoothstep(0.0, 0.25, -to_sun.y))
	if water:
		var water_mat := water.get_active_material(0) as ShaderMaterial
		if water_mat:
			water_mat.set_shader_parameter("light_tint", tint)
