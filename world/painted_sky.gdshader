// Painted anime-style sky: gradient, puffy cumulus clouds and layered mountain silhouettes.
//
// Everything is drawn in the sky itself (no 3D models), so it's always "infinitely
// far away" and has smooth, painted edges instead of polygons.
//
// Positions on the sky are measured in degrees:
//   az   = direction around you (0 = north, positive = to the right)
//   elev = height above the horizon
// All colours and sizes are uniforms: tweak them in the Inspector
// (WorldEnvironment > Environment > Sky > Sky Material).
shader_type sky;

group_uniforms sky;
uniform vec3 sky_top : source_color = vec3(0.16, 0.38, 0.84);
uniform vec3 sky_horizon : source_color = vec3(0.80, 0.86, 0.96);
uniform vec3 sun_glow : source_color = vec3(1.0, 0.92, 0.78);

group_uniforms clouds;
uniform vec3 cloud_light : source_color = vec3(1.0, 0.99, 0.97);
uniform vec3 cloud_shade : source_color = vec3(0.84, 0.78, 0.92);
uniform float cloud_amount : hint_range(0.0, 1.0) = 0.65; // chance of a cloud in each slot
uniform float cloud_size = 1.0;

group_uniforms mountains;
uniform vec3 far_color : source_color = vec3(0.70, 0.72, 0.89);
uniform vec3 rock_shade : source_color = vec3(0.52, 0.48, 0.66);
uniform vec3 rock_lit : source_color = vec3(0.82, 0.68, 0.72);
uniform vec3 snow_color : source_color = vec3(0.97, 0.96, 1.0);
uniform vec3 hill_color : source_color = vec3(0.32, 0.52, 0.48);
uniform vec3 haze_color : source_color = vec3(0.80, 0.86, 0.96);
uniform float mountain_height = 1.0; // 1 = normal, 2 = twice as tall

group_uniforms time_of_day; // set every frame by the DayNight node (world/day_night.gd)
uniform vec3 light_tint : source_color = vec3(1.0); // multiplies mountains and clouds (orange at sunset, dark blue at night)
uniform float star_amount : hint_range(0.0, 1.0) = 0.0;
uniform float cloud_speed = 0.35; // how fast clouds drift across the sky (degrees per second)

// ---- Noise helpers ---------------------------------------------------------
float hash(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
			mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// "Fractal" noise: several layers of noise, each smaller and fainter.
float fbm(vec2 p) {
	float v = 0.0;
	float amp = 0.5;
	for (int i = 0; i < 4; i++) {
		v += amp * value_noise(p);
		p = p * 2.03 + vec2(17.1, 9.2);
		amp *= 0.5;
	}
	return v;
}

// ---- Mountains ---------------------------------------------------------------
// Each layer is a row of individual peaks around the horizon. Every "slot" of
// azimuth holds one peak with its own position, height and width; the layer's
// outline is the tallest peak at each direction. That gives clear, distinct
// mountains like a painted background, instead of noisy spikes.
// Returns the height (degrees) and, in `side`, which slope we're on:
// -1 = left side of a peak, +1 = right side.
float peaks(float az_deg, float base, float amp, float slot, float seed, out float side, out float peak_h) {
	float h = 0.0;
	side = 0.0;
	peak_h = 0.0;
	float here = floor(az_deg / slot);
	for (float s = here - 2.0; s <= here + 2.0; s += 1.0) {
		float center = (s + 0.5 + (hash(vec2(s, seed)) - 0.5) * 0.7) * slot;
		// taller towards the north (where the camera looks), lower to the south
		float facing = 0.3 + 0.7 * smoothstep(-0.3, 0.7, cos(radians(center)));
		float height = amp * mix(0.4, 1.0, hash(vec2(s, seed + 1.3))) * facing * mountain_height;
		float width = slot * mix(1.0, 1.9, hash(vec2(s, seed + 2.7)));
		float t = 1.0 - abs(az_deg - center) / width;
		if (t > 0.0) {
			float v = height * pow(t, 1.35); // slightly curved (concave) sides
			if (v > h) {
				h = v;
				peak_h = height;
				side = sign(az_deg - center) * smoothstep(0.0, 0.06, abs(az_deg - center) / width);
			}
		}
	}
	// a little roughness along the ridgelines
	h += (fbm(vec2(az_deg * 0.25, seed)) - 0.5) * amp * 0.06;
	return base + h;
}

vec3 mountain_layer(vec3 col, float az_deg, float elev, float aa, float sun_right,
		float base, float amp, float slot, float seed,
		vec3 shade, vec3 lit, bool snowy, float haze) {
	float side;
	float peak_h;
	float h = peaks(az_deg, base, amp, slot, seed, side, peak_h);
	float inside = smoothstep(h + aa, h - aa, elev);
	if (inside <= 0.0) {
		return col;
	}
	// The slope facing the sun is lit, the other side is in shade.
	float light = 0.5 + 0.45 * side * sun_right;
	vec3 c = mix(shade, lit, light);
	// Painterly touches: lighter towards the top, faint vertical gully streaks.
	float up = clamp((elev - base) / max(h - base, 0.3), 0.0, 1.0);
	c *= mix(0.9, 1.04, up);
	c *= 0.95 + 0.05 * value_noise(vec2(az_deg * 1.2, elev * 0.35 + seed));
	if (snowy && peak_h > amp * 0.55) { // snow caps on the tall peaks only
		float snow_line = base + peak_h * 0.68 + (value_noise(vec2(az_deg * 0.9, seed)) - 0.5) * peak_h * 0.1;
		c = mix(c, snow_color * mix(0.84, 1.0, light), smoothstep(snow_line - aa, snow_line + aa, elev));
	}
	c *= light_tint;
	// Soft mist at the foot of each layer, plus overall haze for the far layers.
	float mist = 1.0 - smoothstep(0.0, max(h - base, 0.5) * 0.45, elev - base);
	c = mix(c, haze_color, clamp(haze + mist * 0.35, 0.0, 1.0));
	return mix(col, c, inside);
}

// Low rolling hills in front: smooth noise, no sharp peaks.
vec3 hill_layer(vec3 col, float az, float elev, float aa) {
	vec2 p = vec2(cos(az), sin(az)) * 6.0 + 11.3;
	float h = 0.2 + 2.6 * mountain_height * (value_noise(p) * 0.7 + value_noise(p * 2.1) * 0.3);
	float inside = smoothstep(h + aa, h - aa, elev);
	vec3 c = mix(hill_color * 0.92, hill_color * 1.12, clamp(elev / max(h, 0.3), 0.0, 1.0));
	c = mix(c * light_tint, haze_color, 0.18);
	return mix(col, c, inside);
}

vec3 add_mountains(vec3 col, float az, float elev, float aa, float sun_az) {
	if (elev > 22.0 * mountain_height || elev < -0.5) {
		return col; // nothing up here: skip the work
	}
	float az_deg = degrees(az);
	float sun_right = clamp(sin(sun_az - az) * 2.0, -1.0, 1.0); // +1 = sun is to the right
	col = mountain_layer(col, az_deg, elev, aa, sun_right, 0.8, 16.0, 15.0, 3.1,
			far_color * 0.95, far_color * 1.1, true, 0.4);
	col = mountain_layer(col, az_deg, elev, aa, sun_right, 0.5, 11.0, 9.0, 7.7,
			rock_shade, rock_lit, true, 0.08);
	col = hill_layer(col, az, elev, aa);
	return col;
}

// ---- Clouds --------------------------------------------------------------------
// Cumulus "towers": each slot around the horizon may hold one cloud made of
// round puffs, wide at the flat bottom and heaped up in the middle.
vec3 add_clouds(vec3 col, float az_deg, float elev) {
	if (elev < 0.0 || elev > 40.0) {
		return col;
	}
	float slot = 16.0 * cloud_size; // degrees per cloud slot
	float best = 0.0;   // how much cloud is here (0-1)
	float shade = 0.0;  // 0 = shadowed underside, 1 = sunlit top
	float here = floor(az_deg / slot);
	for (float s = here - 1.0; s <= here + 1.0; s += 1.0) {
		if (hash(vec2(s, 1.7)) > cloud_amount) {
			continue; // empty slot: clear sky
		}
		float center = (s + 0.5 + (hash(vec2(s, 2.3)) - 0.5) * 0.5) * slot;
		float width = slot * mix(0.45, 0.85, hash(vec2(s, 3.9)));
		float bottom = mix(6.0, 20.0, hash(vec2(s, 5.1)));
		float tall = width * mix(0.35, 0.6, hash(vec2(s, 6.6)));
		for (float k = 0.0; k < 6.0; k += 1.0) {
			float t = (k + 0.5) / 6.0 - 0.5; // -0.5 .. 0.5 across the cloud
			float px = center + t * width + (hash(vec2(s, k + 10.0)) - 0.5) * width * 0.2;
			float radius = width * mix(0.16, 0.3, 1.0 - abs(t) * 2.0) * mix(0.8, 1.2, hash(vec2(s, k + 20.0)));
			float py = bottom + (1.0 - abs(t) * 2.0) * tall * 0.6 + radius * 0.4;
			// fluffy edges: wobble the distance with a bit of noise
			float wobble = (value_noise(vec2(az_deg, elev) * 0.6 + s * 3.1) - 0.5) * radius * 0.35;
			float d = length(vec2(az_deg - px, (elev - py) * 1.15)) + wobble;
			float puff = smoothstep(radius, radius * 0.82, d);
			puff *= smoothstep(bottom - 0.3, bottom + 0.6, elev); // flat bottom
			if (puff > best) {
				best = puff;
				shade = clamp((elev - bottom) / (radius + py - bottom) + 0.15, 0.0, 1.0);
			}
		}
	}
	vec3 c = mix(cloud_shade, cloud_light, smoothstep(0.1, 0.75, shade)) * light_tint;
	c = mix(c, sky_horizon, 1.0 - smoothstep(0.0, 8.0, elev) * 0.85); // softer near the horizon
	return mix(col, c, best);
}

// ---- Stars ---------------------------------------------------------------------
// Split the sky into tiny cells; a few random cells hold a star.
float stars(vec3 dir) {
	vec3 p = dir * 220.0;
	vec3 cell = floor(p);
	float h = hash(cell.xy + cell.z * 7.13);
	if (h < 0.996) {
		return 0.0;
	}
	float twinkle = 0.75 + 0.25 * sin(TIME * 2.0 + h * 400.0);
	return smoothstep(0.35, 0.0, length(fract(p) - 0.5)) * twinkle * hash(cell.zy + 3.1);
}

void sky() {
	vec3 sun_dir = LIGHT0_ENABLED ? LIGHT0_DIRECTION : normalize(vec3(0.3, 0.8, 0.5));
	vec3 dir = EYEDIR;
	float az = atan(dir.x, -dir.z);
	float elev = degrees(asin(clamp(dir.y, -1.0, 1.0)));
	float aa = max(fwidth(elev) * 1.2, 0.01); // soft, anti-aliased edges

	// Gradient sky + a soft glow around the sun.
	float up = clamp(dir.y, 0.0, 1.0);
	vec3 col = mix(sky_horizon, sky_top, smoothstep(0.0, 1.0, pow(up, 0.55)));
	float sun = max(dot(dir, sun_dir), 0.0);
	col += sun_glow * (pow(sun, 8.0) * 0.25 + pow(sun, 400.0) * 1.5);

	if (star_amount > 0.0 && dir.y > 0.0) {
		col += vec3(0.9, 0.93, 1.0) * stars(dir) * star_amount * smoothstep(0.0, 0.15, dir.y);
	}

	// Clouds drift slowly around the sky (wrapping round behind you).
	float cloud_az = mod(degrees(az) + 180.0 + TIME * cloud_speed, 360.0) - 180.0;
	col = add_clouds(col, cloud_az, elev);
	col = add_mountains(col, az, elev, aa, atan(sun_dir.x, -sun_dir.z));
	if (elev < 0.0) {
		col = haze_color; // below the horizon: haze (the sea covers this anyway)
	}
	COLOR = col;
}
