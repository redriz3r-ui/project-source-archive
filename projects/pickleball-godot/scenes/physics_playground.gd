extends Node2D

# Ball properties
var ball_pos = Vector2(600, 800)
var ball_velocity = Vector2.ZERO
const BALL_SIZE = 18
const BALL_SHADOW_OFFSET = 10
const THROW_POWER_MULTIPLIER = 2.0  # Adjust this to control throw power
const MIN_THROW_VELOCITY = 5.0    # Minimum velocity for a throw to register

# Touch control properties
var touch_index = -1  # Track which touch is controlling the ball
var targeting_touch_index = -1  # Track which touch is controlling targeting
const TOUCH_RADIUS = 150.0  # Increased from 50 to 150 for easier grabbing
const TARGETING_AREA_WIDTH = 1.0  # Full screen width for targeting

# Stats tracking
var zombies_killed = 0
var waves_survived = 0
var stats_label: Label

# Rifle properties
var is_targeting = false
var selected_zombie = null
var targeting_timer = 0.0
const TARGETING_DURATION = 0.5  # How long to hold to confirm target
var bullets = []
const BULLET_SPEED = 2000.0
const BULLET_SIZE = 4
const TARGETING_RADIUS = 100.0  # How close to zombie to be able to target

# Grenade properties
var is_exploded = false
var stopped_moving_timer = 0.0
const STOPPED_MOVING_THRESHOLD = 0.1  # How long to wait before exploding
const EXPLOSION_RADIUS = 200.0  # Increased from 100 to 200
const EXPLOSION_DURATION = 0.5
var explosion_timer = 0.0
var explosion_radius = 0.0
var has_been_thrown = false

# Zombie properties
var zombies = []
const ZOMBIE_COUNT = 10
const ZOMBIE_SPAWN_RADIUS = 500.0

# Ball vertical (z) physics
var ball_z = 0.0 # height above ground
var ball_vz = 0.0 # vertical velocity
const GRAVITY = -1000.0  # Reduced gravity for more floaty feel
const BOUNCE_ENERGY = 0.6
const FRICTION = 0.20
const VERTICAL_THROW_MULTIPLIER = 1.5  # How much vertical velocity to add based on throw power

# Hill generation
const HILL_FREQUENCY = 0.01  # Controls how often hills repeat
const HILL_AMPLITUDE = 100.0  # Maximum height of hills
const HILL_PHASE = 0.0  # Phase offset for hills
var hill_heights = {}  # Cache for hill heights

# Throwing system
var is_dragging = false
var drag_start_pos = Vector2.ZERO
var drag_current_pos = Vector2.ZERO
var last_drag_pos = Vector2.ZERO
var drag_time = 0.0
const MAX_DRAG_TIME = 0.5  # Maximum time to consider for throw power

# Grid settings
const GRID_CELL_SIZE = 375
const COURSE_WIDTH = 1080
const COURSE_HEIGHT = 3200

# Course elements
var hole_pos = Vector2(400, 100)
const HOLE_RADIUS = 24

# Ring shadow properties
const RING_MAX_RADIUS = 100.0
const RING_MIN_RADIUS = 30.0
const RING_MAX_HEIGHT = 500.0
var ring_radius = RING_MAX_RADIUS
var ring_alpha = 0.0

# Sprite properties
var ball_sprite: Sprite2D
var shadow_sprite: Sprite2D
const BASE_SPRITE_SCALE = Vector2(3.0, 3.0)
const BASE_SHADOW_SPRITE_SCALE = Vector2(0.2, 0.2)

# Camera offset
var camera_offset = Vector2.ZERO
const VIEWPORT_SIZE = Vector2(1080, 1920) # Size of the visible area

# New explosion particles system
var explosion_particles: ExplosionParticles

# Perspective settings
const PERSPECTIVE_STRENGTH = 0.3  # How strong the perspective effect is
const PERSPECTIVE_CENTER_Y = 0.5  # Where the perspective center is (0-1)
const PERSPECTIVE_SCALE = 0.8     # How much to scale objects in the distance

# Add dead bodies layer
var dead_bodies_layer: Node2D
var dead_bodies = [] # Array of {sprite: Sprite2D, world_pos: Vector2}

# Add for predicted trajectory
var predicted_trajectory = []

# Girl properties
var girl_pos = Vector2.ZERO
var girl_sprite: Sprite2D
var girl_eaten = false
const GIRL_RADIUS = 24
const GIRL_EATEN_RADIUS = 24
const GIRL_EATEN_DISTANCE = 40  # Distance at which zombies eat the girl

func _ready():
	ball_sprite = Sprite2D.new()
	shadow_sprite = Sprite2D.new()
	ball_sprite.texture = load("res://grenade.png")
	shadow_sprite.texture = load("res://shadow.png")
	add_child(ball_sprite)
	add_child(shadow_sprite)
	ball_sprite.centered = true
	shadow_sprite.centered = true
	
	# Create explosion particles system
	explosion_particles = ExplosionParticles.new()
	add_child(explosion_particles)
	explosion_particles.visible = false
	
	# Create stats UI
	stats_label = Label.new()
	stats_label.position = Vector2(20, 20)
	stats_label.add_theme_font_size_override("font_size", 24)
	add_child(stats_label)
	update_stats_display()
	
	# Spawn initial zombies
	spawn_zombies()
	
	# Add dead bodies layer
	dead_bodies_layer = Node2D.new()
	add_child(dead_bodies_layer)
	
	# Place girl at random spot near ball spawn
	var angle = randf_range(0, TAU)
	var distance = randf_range(500, 840) # Increased min/max distance
	girl_pos = ball_pos + Vector2(cos(angle), sin(angle)) * distance
	girl_sprite = Sprite2D.new()
	girl_sprite.texture = load("res://girl.png")
	girl_sprite.centered = true
	girl_sprite.scale = Vector2(2.5, 2.5)
	add_child(girl_sprite)

func spawn_zombies():
	for i in range(ZOMBIE_COUNT):
		var angle = randf_range(0, TAU)
		var distance = randf_range(0, ZOMBIE_SPAWN_RADIUS)
		var spawn_pos = ball_pos + Vector2(cos(angle), sin(angle)) * distance
		var zombie = Zombie.new(spawn_pos)
		add_child(zombie)
		zombies.append(zombie)

func _input(event):
	if event is InputEventScreenTouch:
		var world_pos = event.position + camera_offset
		
		if event.pressed:
			# Check if touch is near the ball first
			if touch_index == -1 and (world_pos - ball_pos).length() < TOUCH_RADIUS:
				touch_index = event.index
				start_drag(world_pos)
			# If not near ball, allow targeting from anywhere
			elif targeting_touch_index == -1:
				targeting_touch_index = event.index
				start_targeting(world_pos)
		else:  # Touch released
			if event.index == touch_index:
				end_drag()
				touch_index = -1
			elif event.index == targeting_touch_index:
				end_targeting()
				targeting_touch_index = -1
	
	elif event is InputEventScreenDrag:
		var world_pos = event.position + camera_offset
		if event.index == touch_index:
			update_drag(world_pos)
		elif event.index == targeting_touch_index:
			# Update targeting position
			selected_zombie = find_closest_zombie(world_pos)
	
	elif event is InputEventMouseButton:  # Keep mouse support for testing
		var world_pos = event.position + camera_offset
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				if (world_pos - ball_pos).length() < TOUCH_RADIUS:
					start_drag(world_pos)
				else:
					start_targeting(world_pos)
			else:
				if is_targeting:
					end_targeting()
				else:
					end_drag()
	
	elif event is InputEventMouseMotion and is_dragging:  # Keep mouse support for testing
		var world_pos = event.position + camera_offset
		update_drag(world_pos)

func start_drag(pos: Vector2):
	if (pos - ball_pos).length() < BALL_SIZE * 2:  # Only start drag if near the ball
		is_dragging = true
		drag_start_pos = pos
		drag_current_pos = pos
		last_drag_pos = pos
		drag_time = 0.0

func update_drag(pos: Vector2):
	if is_dragging:
		drag_current_pos = pos
		drag_time += get_process_delta_time()
		# Update predicted trajectory
		var drag_vector = drag_start_pos - drag_current_pos
		var drag_distance = drag_vector.length()
		var drag_duration = min(drag_time, MAX_DRAG_TIME)
		if drag_distance > 10:
			var throw_power = drag_distance * THROW_POWER_MULTIPLIER
			var throw_direction = drag_vector.normalized()
			var velocity = throw_direction * throw_power
			var vertical_throw = throw_power * VERTICAL_THROW_MULTIPLIER
			if throw_direction.y < 0:
				vertical_throw *= 1.5
			var vz = -vertical_throw
			predicted_trajectory = get_predicted_trajectory(ball_pos, velocity, vz)
		else:
			predicted_trajectory = []

func end_drag():
	if is_dragging:
		var drag_vector = drag_start_pos - drag_current_pos
		var drag_distance = drag_vector.length()
		var drag_duration = min(drag_time, MAX_DRAG_TIME)
		
		if drag_distance > 10:  # Minimum drag distance to register a throw
			var throw_power = drag_distance * THROW_POWER_MULTIPLIER
			var throw_direction = drag_vector.normalized()
			
			# Apply the throw with more vertical component
			ball_velocity = throw_direction * throw_power
			
			# Add vertical velocity based on throw power and direction
			var horizontal_speed = throw_power
			var vertical_throw = horizontal_speed * VERTICAL_THROW_MULTIPLIER
			
			# Add more vertical velocity for upward throws
			if throw_direction.y < 0:  # If throwing upward
				vertical_throw *= 1.5
			
			ball_vz = -vertical_throw  # Negative because up is negative in Godot
			has_been_thrown = true
		
		is_dragging = false
		predicted_trajectory = []

func start_targeting(pos: Vector2):
	is_targeting = true
	targeting_timer = 0.0
	selected_zombie = find_closest_zombie(pos)

func end_targeting():
	if is_targeting and selected_zombie != null and targeting_timer >= TARGETING_DURATION:
		var direction = (selected_zombie.world_pos - ball_pos).normalized()
		shoot(direction)
	is_targeting = false
	selected_zombie = null
	targeting_timer = 0.0

func find_closest_zombie(pos: Vector2):
	var closest_zombie = null
	var closest_distance = TARGETING_RADIUS
	
	for zombie in zombies:
		if !zombie.is_exploded:
			var distance = (zombie.world_pos - pos).length()
			if distance < closest_distance:
				closest_distance = distance
				closest_zombie = zombie
	
	return closest_zombie

func shoot(direction: Vector2):
	var bullet = {
		"position": ball_pos,
		"velocity": direction * BULLET_SPEED,
		"lifetime": 1.0  # Bullets disappear after 1 second
	}
	bullets.append(bullet)

func get_terrain_height(pos: Vector2) -> float:
	# Use multiple sine waves to create more natural-looking hills
	var x = pos.x
	var y = pos.y
	
	# Generate a unique key for this position
	var key = str(int(x / GRID_CELL_SIZE)) + "," + str(int(y / GRID_CELL_SIZE))
	
	# Check if we've already calculated this height
	if hill_heights.has(key):
		return hill_heights[key]
	
	# Combine multiple sine waves for more natural terrain
	var height = 0.0
	height += sin(x * HILL_FREQUENCY) * HILL_AMPLITUDE
	height += sin(y * HILL_FREQUENCY * 0.7) * HILL_AMPLITUDE * 0.8
	height += sin((x + y) * HILL_FREQUENCY * 0.5) * HILL_AMPLITUDE * 0.6
	
	# Store the calculated height
	hill_heights[key] = height
	return height

func _process(delta):
	# Handle targeting
	if is_targeting and selected_zombie != null:
		targeting_timer += delta

	# Update bullets
	var bullets_to_remove = []
	for bullet in bullets:
		bullet.position += bullet.velocity * delta
		bullet.lifetime -= delta
		
		# Check for zombie hits
		for zombie in zombies:
			if !zombie.is_exploded and (bullet.position - zombie.world_pos).length() < 30:  # Hit radius
				zombie.explode()
				add_dead_body(zombie.world_pos)
				zombies.erase(zombie)
				bullets_to_remove.append(bullet)
				break
		
		# Remove bullets that are too old or out of bounds
		if bullet.lifetime <= 0 or bullet.position.x < 0 or bullet.position.x > COURSE_WIDTH or bullet.position.y < 0 or bullet.position.y > COURSE_HEIGHT:
			bullets_to_remove.append(bullet)
	
	# Remove dead bullets
	for bullet in bullets_to_remove:
		bullets.erase(bullet)

	# Get the terrain height at the ball's position
	var terrain_height = get_terrain_height(ball_pos)

	# Update ball physics
	ball_pos += ball_velocity * delta
	ball_vz += GRAVITY * delta
	ball_z += ball_vz * delta

	# Ball bounces on terrain (ball_z is height above terrain)
	if ball_z < 0.0:
		ball_z = 0.0
		if abs(ball_vz) > 60:
			ball_vz = -ball_vz * BOUNCE_ENERGY
		else:
			ball_vz = 0.0
			ball_velocity *= FRICTION

			# Only apply slope when ball is on ground
			var slope = get_terrain_slope(ball_pos)
			ball_velocity += slope * delta * 100.0  # Adjust multiplier as needed

	# Check if ball has stopped moving
	if has_been_thrown and ball_velocity.length() < 1.0 and ball_vz == 0.0 and !is_exploded:
		stopped_moving_timer += delta
		if stopped_moving_timer >= STOPPED_MOVING_THRESHOLD:
			explode()
	else:
		stopped_moving_timer = 0.0

	# Update explosion
	if is_exploded:
		explosion_timer += delta
		if explosion_timer >= EXPLOSION_DURATION:
			respawn_ball()
			is_exploded = false
			explosion_timer = 0.0
			explosion_radius = 0.0
			
			# Only spawn new zombies if all zombies are eliminated
			if zombies.size() == 0:
				waves_survived += 1
				update_stats_display()
				spawn_zombies()

	# Boundary checks
	if ball_pos.x <= BALL_SIZE or ball_pos.x >= COURSE_WIDTH - BALL_SIZE:
		ball_velocity.x *= -0.8
	if ball_pos.y <= BALL_SIZE or ball_pos.y >= COURSE_HEIGHT - BALL_SIZE:
		ball_velocity.y *= -0.8

	ball_pos.x = clamp(ball_pos.x, BALL_SIZE, COURSE_WIDTH - BALL_SIZE)
	ball_pos.y = clamp(ball_pos.y, BALL_SIZE, COURSE_HEIGHT - BALL_SIZE)

	# Camera follows the ball
	camera_offset = ball_pos - VIEWPORT_SIZE / 2
	camera_offset.x = clamp(camera_offset.x, 0, COURSE_WIDTH - VIEWPORT_SIZE.x)
	camera_offset.y = clamp(camera_offset.y, 0, COURSE_HEIGHT - VIEWPORT_SIZE.y)

	# Update zombie positions and keep them in bounds
	for zombie in zombies:
		zombie.update_camera_offset(camera_offset)
		# Keep zombies within bounds
		zombie.world_pos.x = clamp(zombie.world_pos.x, BALL_SIZE, COURSE_WIDTH - BALL_SIZE)
		zombie.world_pos.y = clamp(zombie.world_pos.y, BALL_SIZE, COURSE_HEIGHT - BALL_SIZE)

	# Update sprite positions
	if !is_exploded:
		# Ball is drawn above terrain by ball_z
		ball_sprite.position = ball_pos - camera_offset - Vector2(0, ball_z)
		ball_sprite.scale = BASE_SPRITE_SCALE
		# Shadow is always on terrain
		shadow_sprite.position = ball_pos - camera_offset + Vector2(0, BALL_SHADOW_OFFSET)
		shadow_sprite.scale = BASE_SHADOW_SPRITE_SCALE
		shadow_sprite.modulate.a = 0.3 * (1.0 - ball_z / 1000.0)
	else:
		# Hide ball and shadow during explosion
		ball_sprite.modulate.a = 0.0
		shadow_sprite.modulate.a = 0.0

	if ball_z > 0:
		ring_alpha = clamp(ball_z / RING_MAX_HEIGHT, 0.0, 0.5)
		ring_radius = lerp(RING_MIN_RADIUS, RING_MAX_RADIUS, ball_z / RING_MAX_HEIGHT)
	else:
		ring_alpha = 0.0

	# Update dead body sprite positions
	for body in dead_bodies:
		body.sprite.position = body.world_pos - camera_offset

	# Check if girl is eaten by any zombie
	if !girl_eaten:
		for zombie in zombies:
			if (zombie.world_pos - girl_pos).length() < GIRL_EATEN_DISTANCE:
				girl_eaten = true
				girl_sprite.texture = load("res://girl_eaten.png")
				break
	# Update girl sprite screen position (her world position is fixed)
	girl_sprite.position = girl_pos - camera_offset

	queue_redraw()

func get_terrain_slope(pos: Vector2) -> Vector2:
	# Calculate the slope of the terrain at the given position
	var h = 1.0  # Small offset for derivative calculation
	var height_right = get_terrain_height(pos + Vector2(h, 0))
	var height_left = get_terrain_height(pos - Vector2(h, 0))
	var height_up = get_terrain_height(pos + Vector2(0, h))
	var height_down = get_terrain_height(pos - Vector2(0, h))
	
	var slope_x = (height_right - height_left) / (2 * h)
	var slope_y = (height_up - height_down) / (2 * h)
	
	return Vector2(slope_x, slope_y)

func explode():
	is_exploded = true
	explosion_timer = 0.0
	explosion_radius = 0.0
	ball_velocity = Vector2.ZERO
	ball_vz = 0.0
	
	# Create explosion particles
	explosion_particles.position = ball_pos - camera_offset  # Adjust for camera offset
	explosion_particles.visible = true
	explosion_particles.create_explosion(Vector2.ZERO)
	
	# Hide the ball and shadow
	ball_sprite.visible = false
	shadow_sprite.visible = false
	
	# Check for zombies in explosion radius
	var zombies_to_remove = []
	for zombie in zombies:
		var distance = zombie.world_pos.distance_to(ball_pos)
		if distance < EXPLOSION_RADIUS and !zombie.is_exploded:
			print("Zombie hit! Distance: ", distance)  # Debug print
			zombie.explode()
			add_dead_body(zombie.world_pos)
			zombies_to_remove.append(zombie)
			zombies_killed += 1
			update_stats_display()
	# Remove exploded zombies from the list immediately
	for z in zombies_to_remove:
		zombies.erase(z)

func respawn_ball():
	ball_pos = Vector2(400, 1100)
	ball_velocity = Vector2.ZERO
	ball_z = 0.0
	ball_vz = 0.0
	ball_sprite.modulate.a = 1.0
	shadow_sprite.modulate.a = 0.3
	has_been_thrown = false
	
	# Show the ball and shadow again
	ball_sprite.visible = true
	shadow_sprite.visible = true
	explosion_particles.visible = false
	
	# Only spawn new zombies if all zombies are eliminated
	if zombies.size() == 0:
		waves_survived += 1
		update_stats_display()
		spawn_zombies()

func add_dead_body(world_pos: Vector2):
	var sprite = Sprite2D.new()
	sprite.texture = load("res://zombie_boom.png")
	sprite.centered = true
	sprite.scale = Vector2(3.0, 3.0)
	dead_bodies_layer.add_child(sprite)
	dead_bodies.append({"sprite": sprite, "world_pos": world_pos})

func _draw():
	# Draw grid background with perspective
	for x in range(0, COURSE_WIDTH, GRID_CELL_SIZE):
		var x_draw = x - camera_offset.x
		if x_draw >= 0 and x_draw <= VIEWPORT_SIZE.x:
			var start_y = 0
			var end_y = VIEWPORT_SIZE.y
			var start_scale = 1.0
			var end_scale = PERSPECTIVE_SCALE
			
			# Apply perspective transformation
			var start_pos = Vector2(x_draw, start_y)
			var end_pos = Vector2(x_draw, end_y)
			var perspective_offset = (end_y - start_y) * PERSPECTIVE_STRENGTH
			end_pos.x += perspective_offset
			
			draw_line(start_pos, end_pos, Color(0.3, 0.5, 0.3, 0.5))
	
	for y in range(0, COURSE_HEIGHT, GRID_CELL_SIZE):
		var y_draw = y - camera_offset.y
		if y_draw >= 0 and y_draw <= VIEWPORT_SIZE.y:
			var start_x = 0
			var end_x = VIEWPORT_SIZE.x
			var perspective_offset = (y_draw - VIEWPORT_SIZE.y * PERSPECTIVE_CENTER_Y) * PERSPECTIVE_STRENGTH
			
			# Apply perspective transformation
			var start_pos = Vector2(start_x, y_draw)
			var end_pos = Vector2(end_x, y_draw)
			start_pos.x += perspective_offset
			end_pos.x += perspective_offset
			
			draw_line(start_pos, end_pos, Color(0.3, 0.5, 0.3, 0.5))
	
	# Draw terrain height visualization with perspective
	for x in range(0, COURSE_WIDTH, GRID_CELL_SIZE):
		for y in range(0, COURSE_HEIGHT, GRID_CELL_SIZE):
			var pos = Vector2(x, y)
			var height = get_terrain_height(pos)
			var alpha = clamp(height / HILL_AMPLITUDE, 0.0, 0.3)
			var color = Color(0.2, 0.4, 0.2, alpha)
			
			# Apply perspective transformation
			var perspective_offset = (pos.y - camera_offset.y - VIEWPORT_SIZE.y * PERSPECTIVE_CENTER_Y) * PERSPECTIVE_STRENGTH
			var transformed_pos = pos - camera_offset + Vector2(perspective_offset, 0)
			
			draw_rect(Rect2(transformed_pos, Vector2(GRID_CELL_SIZE, GRID_CELL_SIZE)), color)
	
	# Draw hole with perspective
	var hole_screen_pos = hole_pos - camera_offset
	var hole_perspective_offset = (hole_screen_pos.y - VIEWPORT_SIZE.y * PERSPECTIVE_CENTER_Y) * PERSPECTIVE_STRENGTH
	hole_screen_pos.x += hole_perspective_offset
	draw_circle(hole_screen_pos, HOLE_RADIUS, Color(0.1, 0.1, 0.1))
	draw_arc(hole_screen_pos, HOLE_RADIUS, 0, TAU, 32, Color(0.2, 0.2, 0.2), 2.0)
	
	# Draw ring shadow with perspective
	if ring_alpha > 0:
		var ring_pos = ball_sprite.position
		var ring_perspective_offset = (ring_pos.y - VIEWPORT_SIZE.y * PERSPECTIVE_CENTER_Y) * PERSPECTIVE_STRENGTH
		ring_pos.x += ring_perspective_offset
		draw_arc(ring_pos, ring_radius, 0, TAU, 32, Color(0.2, 0.2, 0.2, ring_alpha), 4.0)
	
	# Draw drag line when dragging with perspective
	if is_dragging:
		var start_screen = drag_start_pos - camera_offset
		var current_screen = drag_current_pos - camera_offset
		
		# Apply perspective to drag line
		var start_perspective_offset = (start_screen.y - VIEWPORT_SIZE.y * PERSPECTIVE_CENTER_Y) * PERSPECTIVE_STRENGTH
		var current_perspective_offset = (current_screen.y - VIEWPORT_SIZE.y * PERSPECTIVE_CENTER_Y) * PERSPECTIVE_STRENGTH
		
		start_screen.x += start_perspective_offset
		current_screen.x += current_perspective_offset
		
		draw_line(start_screen, current_screen, Color(1, 1, 1, 0.5), 2.0)
		draw_circle(start_screen, 5, Color(1, 1, 1, 0.8))
		draw_circle(current_screen, 5, Color(1, 1, 1, 0.8))
	
	# Draw predicted trajectory arc
	if is_dragging and predicted_trajectory.size() > 1:
		for i in range(predicted_trajectory.size() - 1):
			draw_line(predicted_trajectory[i], predicted_trajectory[i+1], Color(1, 0.7, 0.2, 0.7), 8.0)

	# Draw bullets
	for bullet in bullets:
		var bullet_screen_pos = bullet.position - camera_offset
		draw_circle(bullet_screen_pos, BULLET_SIZE, Color(1, 1, 0))  # Yellow bullets
	
	# Draw targeting UI
	if is_targeting and selected_zombie != null:
		var zombie_screen_pos = selected_zombie.world_pos - camera_offset
		var targeting_progress = targeting_timer / TARGETING_DURATION
		
		# Draw targeting circle
		draw_arc(zombie_screen_pos, 30, 0, TAU * targeting_progress, 32, Color(1, 0, 0, 0.8), 3.0)
		
		# Draw line from player to target
		var player_screen_pos = ball_pos - camera_offset
		draw_line(player_screen_pos, zombie_screen_pos, Color(1, 0, 0, 0.5), 2.0)
		
		# Draw targeting reticle
		draw_circle(zombie_screen_pos, 5, Color(1, 0, 0, 0.8))
	
	# Draw girl (handled by sprite, but can add extra effects here if needed)

func get_predicted_trajectory(start_pos, start_velocity, start_vz, steps := 60, step_time := 0.05):
	var points = []
	var pos = start_pos
	var velocity = start_velocity
	var vz = start_vz
	var z = ball_z
	var ground_hits = 0
	for i in range(steps):
		pos += velocity * step_time
		vz += GRAVITY * step_time
		z += vz * step_time
		if z < 0.0:
			z = 0.0
			ground_hits += 1
			if abs(vz) > 60:
				vz = -vz * BOUNCE_ENERGY
			else:
				vz = 0.0
				velocity *= FRICTION
			if ground_hits == 3:
				break
		points.append(pos - camera_offset - Vector2(0, z))
		if velocity.length() < 1.0 and vz == 0.0:
			break
	return points 

func update_stats_display():
	stats_label.text = "Zombies Killed: " + str(zombies_killed) + "\nWaves Survived: " + str(waves_survived)
