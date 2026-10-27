// Stylised water: colour by depth, white foam at the shore, rolling foam lines
// and gentle ripples.
//
// The depth comes from a pre-made map (assets/island/water_depth.png, written by
// tools/make_water_map.py): black = shoreline, white = deep. That's much cheaper
// on phones than measuring depth every frame.
// The water is opaque; the "see-through" shallows are faked with a sandy tint.
// Tweak everything in the Inspector: Water node > material.
shader_type spatial;
render_mode unshaded;

uniform sampler2D depth_map : filter_linear, repeat_disable;
uniform vec2 map_origin;           // world x/z of the map's top-left corner
uniform vec2 map_size;             // metres covered by the map
uniform float max_depth = 6.0;     // depth stored as "white" in the map

group_uniforms colours;
uniform vec3 shore_tint : source_color = vec3(0.80, 0.90, 0.74); // sand showing through
uniform vec3 shallow_color : source_color = vec3(0.45, 0.88, 0.85);
uniform vec3 mid_color : source_color = vec3(0.15, 0.67, 0.80);
uniform vec3 deep_color : source_color = vec3(0.07, 0.40, 0.70);
uniform vec3 foam_color : source_color = vec3(1.0, 1.0, 1.0);

group_uniforms foam;
uniform float foam_width = 0.12;   // water depth (m) covered by the solid foam edge
uniform float wave_lines = 1.6;    // how close together the rolling foam lines are
uniform float wave_speed = 0.3;    // how fast they roll towards the beach
uniform float wave_reach = 1.5;    // how far out (metres of depth) the lines appear

group_uniforms time_of_day;
uniform vec3 light_tint : source_color = vec3(1.0); // set by the DayNight node: darker at night

group_uniforms ripples;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform float ripple_strength : hint_range(0.0, 1.0) = 0.45;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	// How deep is the water here? Outside the map it's the open sea: deep.
	// Past the map's edge, fade smoothly into deep water instead of a hard line.
	vec2 uv = (world_pos.xz - map_origin) / map_size;
	vec2 outside = max(max(-uv, uv - 1.0), 0.0) * map_size; // metres beyond the edge
	float depth = texture(depth_map, clamp(uv, 0.0, 1.0)).r * max_depth;
	depth = mix(depth, max_depth, smoothstep(0.0, 40.0, length(outside)));

	// Two slowly drifting noise layers: used for ripples and to wobble the foam.
	vec2 p = world_pos.xz * 0.04;
	float n1 = texture(noise_tex, p + vec2(TIME * 0.010, TIME * 0.006)).r;
	float n2 = texture(noise_tex, p * 1.7 - vec2(TIME * 0.008, -TIME * 0.011)).r;

	// Colour by depth: sandy see-through edge -> turquoise -> deep blue.
	vec3 col = mix(shallow_color, mid_color, smoothstep(0.3, 2.2, depth));
	col = mix(col, deep_color, smoothstep(2.2, max_depth, depth));
	col = mix(shore_tint, col, smoothstep(0.0, 0.3, depth));

	// Ripples: light streaks where the two noise layers line up.
	float ripple = smoothstep(0.58, 0.66, (n1 + n2) * 0.5);
	col = mix(col, col * 1.15 + vec3(0.06), ripple * ripple_strength);

	// Foam: a solid band right at the shore with a wobbly edge...
	float wobble = (n1 - 0.5) * 0.12;
	float edge = 1.0 - smoothstep(foam_width * 0.6, foam_width, depth + wobble);
	// ...plus thin lines rolling in towards the beach, fading out further away.
	float phase = fract(depth * wave_lines + TIME * wave_speed + n2 * 0.5);
	float line = smoothstep(0.0, 0.04, phase) * (1.0 - smoothstep(0.07, 0.13, phase));
	line *= 1.0 - smoothstep(foam_width, wave_reach, depth);
	col = mix(col, foam_color, max(edge, line * 0.85));

	ALBEDO = col * light_tint;
}
