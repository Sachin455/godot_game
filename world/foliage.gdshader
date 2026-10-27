// Wind for trees, palms, bushes, grass and flowers.
//
// Moves each vertex sideways a little, more the higher it is on the plant:
// trunks and stems stay put, tree tops and grass tips sway. Every plant gets
// its own timing from where it stands, so a forest doesn't move in lockstep,
// and a slow "gust" wave makes the wind come and go.
// Everything happens on the graphics chip, so it's very cheap.
shader_type spatial;

uniform vec3 albedo : source_color = vec3(1.0);
uniform float sway = 0.2;          // how far the top moves (metres)
uniform float sway_height = 6.0;   // height (in the model) where the sway is full
uniform float speed = 1.3;         // how fast it moves back and forth
uniform vec2 wind_direction = vec2(1.0, 0.3);

void vertex() {
	// Where this plant stands in the world (for MultiMesh copies this is each copy).
	vec3 origin = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float phase = origin.x * 0.21 + origin.z * 0.17;
	float gust = 0.55 + 0.45 * sin(TIME * 0.35 + origin.x * 0.015 + origin.z * 0.01);
	float wave = sin(TIME * speed + phase) * 0.8 + sin(TIME * speed * 2.3 + phase * 1.7) * 0.2;
	// Bend more towards the top: 0 at the base, 1 at sway_height (squared = a curve).
	float bend = clamp(VERTEX.y / sway_height, 0.0, 1.0);
	bend *= bend;
	// The wind blows the same way for everyone, but each copy is rotated
	// differently, so turn the world wind direction into this model's own space.
	vec3 wind_world = normalize(vec3(wind_direction.x, 0.0, wind_direction.y));
	vec3 wind_local = normalize(inverse(mat3(MODEL_MATRIX)) * wind_world);
	VERTEX += wind_local * (wave * 0.6 + 0.4 * gust) * sway * gust * bend;
}

void fragment() {
	ALBEDO = albedo;
	ROUGHNESS = 1.0;
}
