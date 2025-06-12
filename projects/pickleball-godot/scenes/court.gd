extends Node2D

# Game mode
enum GameMode {
	CPU_VS_USER,  # CPU vs User (default)
	CPU_VS_CPU    # CPU vs CPU
}
var current_mode = GameMode.CPU_VS_USER

# Real pickleball court dimensions (in feet)
const COURT_WIDTH_FT = 20.0
const COURT_HEIGHT_FT = 44.0
const KITCHEN_FT = 7.0
const SERVICE_FT = 15.0

# Scale: 1 foot = 20 pixels
const FT_TO_PX = 20.0
const COURT_WIDTH = COURT_WIDTH_FT * FT_TO_PX # 400 px
const COURT_HEIGHT = COURT_HEIGHT_FT * FT_TO_PX # 880 px
const KITCHEN_DIST = KITCHEN_FT * FT_TO_PX # 140 px
const SERVICE_DIST = SERVICE_FT * FT_TO_PX # 300 px
const LINE_WIDTH = 4

# Perspective settings
const PERSPECTIVE_STRENGTH = 0.2  # How strong the perspective effect is
const PERSPECTIVE_CENTER_Y = COURT_HEIGHT * 0.5  # Center at net/kitchen
const PERSPECTIVE_HORIZONTAL_STRENGTH = 0.1  # How strong the horizontal perspective effect is
const PERSPECTIVE_DISTANCE_SCALE = 0.8  # How much distance affects perspective

# Player properties
var player2_pos = Vector2(COURT_WIDTH/2, COURT_HEIGHT*0.2)
var player1_pos = Vector2(COURT_WIDTH/2, COURT_HEIGHT*0.8)  # Add player1 position
const PLAYER_SIZE = 28
const PLAYER_SHADOW_OFFSET = 10
const PLAYER_SPEED = 500

# Ball properties
var ball_pos = Vector2(COURT_WIDTH/2, COURT_HEIGHT/2)
var ball_velocity = Vector2.ZERO
const BALL_SIZE = 12
const BALL_SHADOW_OFFSET = 6
const BALL_SPEED = 400
# Ball vertical (z) physics
var ball_z = 0.0 # height above court
var ball_vz = 0.0 # vertical velocity
const GRAVITY = -1200.0
const BOUNCE_ENERGY = 0.7

# Hit detection properties
const HIT_HEIGHT_THRESHOLD = 200.0  # Increased from 100 to 200
const HIT_DISTANCE_MULTIPLIER = 1.5  # New multiplier for hit distance
const PLAYER_HIT_RADIUS = PLAYER_SIZE * 1.5  # Increased hit radius

# Ring shadow properties
const RING_MAX_RADIUS = 100.0
const RING_MIN_RADIUS = 30.0
const RING_MAX_HEIGHT = 500.0  # Height at which ring starts appearing
var ring_radius = RING_MAX_RADIUS
var ring_alpha = 0.0

# Timing system
const PERFECT_HIT_HEIGHT = 50.0  # Height at which perfect hit is possible
const PERFECT_HIT_WINDOW = 20.0  # Window of opportunity for perfect hit
var can_perfect_hit = false
var perfect_hit_active = false

var last_hitter = 0
var hit_cooldown = 0.0
var serve_timer = 0.0
var game_started = false

# Shot types and mechanics
enum ShotType {
	DRIVE,      # Standard hit
	DINK,       # Soft kitchen shot
	VOLLEY,     # Quick air hit
	LOB,        # High arcing shot
	TOPSPIN,    # Dipping shot
	SLICE,      # Backspin shot
	BLOCK       # Defensive block
}

# Shot properties
const SHOT_SPEEDS = {
	ShotType.DRIVE: 1.0,    # Base speed
	ShotType.DINK: 0.8,     # Much slower
	ShotType.VOLLEY: 1.3,   # Faster than normal
	ShotType.LOB: 0.8,      # Moderate speed
	ShotType.TOPSPIN: 1.1,  # Slightly faster
	ShotType.SLICE: 0.9,    # Slightly slower
	ShotType.BLOCK: 0.7     # Defensive speed
}

const SHOT_ARC_MULTIPLIERS = {
	ShotType.DRIVE: 1.0,    # Normal arc
	ShotType.DINK: 0.8,     # Very low arc
	ShotType.VOLLEY: 0.5,   # Low arc
	ShotType.LOB: 1.4,      # High arc
	ShotType.TOPSPIN: 0.7,  # Medium-low arc
	ShotType.SLICE: 1.2,    # Medium-high arc
	ShotType.BLOCK: 0.4     # Very low arc
}

# CPU movement properties
const RETURN_TO_HOME_DELAY = 0.1  # Seconds to wait before returning home
const HOVER_RADIUS = 0  # How far they'll move from last hit position

# CPU state tracking
var cpu2_last_hit_pos = Vector2(COURT_WIDTH/2, COURT_HEIGHT*0.2) # Start at home
var cpu2_hit_timer = 0.0

# Double bounce rule tracking
var bounce_on_p1_side = false
var bounce_on_p2_side = false
var double_bounce_active = true
var last_bounce_side = 0 # 0 = none, 1 = player1 side, 2 = player2 side

# Mouse hit properties
var mouse_pos = Vector2.ZERO
var can_hit = false

# Sprite properties
var player1_sprite: Sprite2D  # Add player1 sprite
var player2_sprite: Sprite2D  # Rename player_sprite to player2_sprite
var ball_sprite: Sprite2D
var shadow_sprite: Sprite2D
const BASE_SPRITE_SCALE = Vector2(1.0, 1.0)
const BASE_SHAD0W_SPRITE_SCALE = Vector2(0.6, 0.6)

# Trajectory preview properties
var show_trajectory = false
var trajectory_points = []
const TRAJECTORY_POINTS = 20
const TRAJECTORY_DURATION = 1.0  # How far ahead to show trajectory
const TRAJECTORY_ALPHA = 0.5     # How visible the trajectory line is

# Shot type colors for visualization
const SHOT_COLORS = {
	ShotType.DRIVE: Color(1.0, 0.0, 0.0),    # Red
	ShotType.DINK: Color(0.0, 1.0, 0.0),     # Green
	ShotType.VOLLEY: Color(0.0, 0.0, 1.0),   # Blue
	ShotType.LOB: Color(1.0, 1.0, 0.0),      # Yellow
	ShotType.TOPSPIN: Color(1.0, 0.5, 0.0),  # Orange
	ShotType.SLICE: Color(0.5, 0.0, 1.0),    # Purple
	ShotType.BLOCK: Color(0.5, 0.5, 0.5)     # Gray
}

# Debug properties
var current_shot_type = ShotType.DRIVE
var debug_text = ""
var debug_font: Font

func _ready():
	# Create sprites
	player1_sprite = Sprite2D.new()
	player2_sprite = Sprite2D.new()
	ball_sprite = Sprite2D.new()
	shadow_sprite = Sprite2D.new()
	
	# Load textures
	player1_sprite.texture = load("res://champ.png")
	player2_sprite.texture = load("res://player.png")
	ball_sprite.texture = load("res://ball.png")
	shadow_sprite.texture = load("res://shadow.png")
	
	# Create debug font
	debug_font = ThemeDB.fallback_font
	
	# Add sprites to scene
	add_child(player1_sprite)
	add_child(player2_sprite)
	add_child(ball_sprite)
	add_child(shadow_sprite)
	
	# Set initial scales
	player1_sprite.scale = BASE_SPRITE_SCALE
	player2_sprite.scale = BASE_SPRITE_SCALE
	ball_sprite.scale = BASE_SPRITE_SCALE
	shadow_sprite.scale = BASE_SPRITE_SCALE
	
	player1_sprite.centered = true
	player2_sprite.centered = true
	ball_sprite.centered = true
	shadow_sprite.centered = true
	
	var viewport_size = get_viewport().size

	# Get the y position to focus on (e.g., ball or player)
	var focus_y = ball_pos.y

	# Calculate a perspective zoom factor based on distance from net
	var net_y = PERSPECTIVE_CENTER_Y
	var dist_from_net = abs(focus_y - net_y)
	var perspective_zoom_factor = 1.0 + (dist_from_net / COURT_HEIGHT) * PERSPECTIVE_DISTANCE_SCALE

	# Calculate transformed bounds as before
	var top_left = apply_perspective(Vector2(0, 0))
	var top_right = apply_perspective(Vector2(COURT_WIDTH, 0))
	var bottom_left = apply_perspective(Vector2(0, COURT_HEIGHT))
	var bottom_right = apply_perspective(Vector2(COURT_WIDTH, COURT_HEIGHT))

	var min_x = min(top_left.x, bottom_left.x)
	var max_x = max(top_right.x, bottom_right.x)
	var min_y = min(top_left.y, top_right.y)
	var max_y = max(bottom_left.y, bottom_right.y)

	var transformed_width = max_x - min_x
	var transformed_height = max_y - min_y

	var zoom_x = transformed_width / viewport_size.x
	var zoom_y = transformed_height / viewport_size.y
	var zoom = max(zoom_x, zoom_y)  * 1.5  # Add padding

	$Camera2D.zoom = Vector2(zoom, zoom)
	$Camera2D.position = Vector2(COURT_WIDTH/2, COURT_HEIGHT/2)
	$Camera2D.make_current()
	
	# Initialize game state
	ball_velocity = Vector2.ZERO
	ball_z = 0.0
	ball_vz = 0.0
	serve_timer = 0.5
	game_started = false
	bounce_on_p1_side = false
	bounce_on_p2_side = false
	double_bounce_active = true
	last_bounce_side = 0

func _input(event):
	if event is InputEventKey:
		if event.pressed and event.keycode == KEY_TAB:
			# Toggle game mode
			current_mode = GameMode.CPU_VS_CPU if current_mode == GameMode.CPU_VS_USER else GameMode.CPU_VS_USER
			print("Game mode: ", "CPU vs CPU" if current_mode == GameMode.CPU_VS_CPU else "CPU vs User")
	
	if current_mode == GameMode.CPU_VS_USER:
		if event is InputEventMouseMotion:
			mouse_pos = event.position
			# Update trajectory when mouse moves
			if can_hit:
				update_trajectory_preview()
		elif event is InputEventMouseButton:
			if event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
				if can_hit and ball_z < HIT_HEIGHT_THRESHOLD and hit_cooldown == 0.0:  # Increased height threshold
					# Check if mouse is in bottom half of court
					if mouse_pos.y > COURT_HEIGHT/2:
						# Kitchen volley rule: prevent volley if in kitchen, unless last bounce was on their side
						if is_in_kitchen(mouse_pos) and ball_z > 0.0 and last_bounce_side != 1:
							print("Can't volley in kitchen!")
							return
						# Double bounce rule: prevent volley if not satisfied
						if double_bounce_active and ball_z > 0.0:
							print("Need to let it bounce first!")
							return
						
						var target_x = randf_range(PLAYER_SIZE, COURT_WIDTH - PLAYER_SIZE)
						var target_y = COURT_HEIGHT * 0.15  # Near Player 2's baseline
						var target = Vector2(target_x, target_y)
						handle_player_hit(mouse_pos, target, true)
						show_trajectory = false
						trajectory_points.clear()

func _process(delta):
	# Update CPU hit timer
	cpu2_hit_timer = max(0.0, cpu2_hit_timer - delta)
	
	# CPU for Player 2 (top)
	var player2_home = Vector2(COURT_WIDTH/2, COURT_HEIGHT*0.2)
	if ball_pos.y < COURT_HEIGHT/2 and ball_velocity.y < 0:
		# If the ball is in the kitchen and on the ground, go for it!
		if is_in_kitchen(ball_pos) and ball_z == 0.0:
			var dir2 = (ball_pos - player2_pos).normalized()
			player2_pos += dir2 * PLAYER_SPEED * delta
		else:
			var dir2 = (ball_pos - player2_pos).normalized()
			player2_pos += dir2 * PLAYER_SPEED * delta
		if (ball_pos - player2_pos).length() < PLAYER_SIZE + BALL_SIZE:
			cpu2_last_hit_pos = player2_pos
			cpu2_hit_timer = RETURN_TO_HOME_DELAY
	else:
		if cpu2_hit_timer > 0:
			var hover_offset = Vector2(
				randf_range(-HOVER_RADIUS, HOVER_RADIUS),
				randf_range(-HOVER_RADIUS, HOVER_RADIUS)
			)
			var target_pos = cpu2_last_hit_pos + hover_offset
			# Clamp to top half
			target_pos.x = clamp(target_pos.x, PLAYER_SIZE, COURT_WIDTH - PLAYER_SIZE)
			target_pos.y = clamp(target_pos.y, PLAYER_SIZE, COURT_HEIGHT/2 - PLAYER_SIZE)
			var dir2 = (target_pos - player2_pos).normalized()
			player2_pos += dir2 * PLAYER_SPEED * 0.5 * delta
		else:
			var dir2 = (player2_home - player2_pos).normalized()
			player2_pos += dir2 * PLAYER_SPEED * delta
	
	# CPU for Player 1 (bottom) in CPU vs CPU mode
	if current_mode == GameMode.CPU_VS_CPU:
		var player1_home = Vector2(COURT_WIDTH/2, COURT_HEIGHT*0.8)
		if ball_pos.y > COURT_HEIGHT/2 and ball_velocity.y > 0:
			# If the ball is in the kitchen and on the ground, go for it!
			if is_in_kitchen(ball_pos) and ball_z == 0.0:
				var dir1 = (ball_pos - player1_pos).normalized()
				player1_pos += dir1 * PLAYER_SPEED * delta
			else:
				var dir1 = (ball_pos - player1_pos).normalized()
				player1_pos += dir1 * PLAYER_SPEED * delta
			if (ball_pos - player1_pos).length() < PLAYER_SIZE + BALL_SIZE:
				var target_x = randf_range(PLAYER_SIZE, COURT_WIDTH - PLAYER_SIZE)
				var target_y = COURT_HEIGHT * 0.15  # Near Player 2's baseline
				var target = Vector2(target_x, target_y)
				handle_player_hit(player1_pos, target, true)
		else:
			var dir1 = (player1_home - player1_pos).normalized()
			player1_pos += dir1 * PLAYER_SPEED * delta
	
	# Clamp Player 2 to top half
	player2_pos.x = clamp(player2_pos.x, PLAYER_SIZE, COURT_WIDTH - PLAYER_SIZE)
	player2_pos.y = clamp(player2_pos.y, PLAYER_SIZE, COURT_HEIGHT/2 - PLAYER_SIZE)
	
	# Clamp Player 1 to bottom half
	player1_pos.x = clamp(player1_pos.x, PLAYER_SIZE, COURT_WIDTH - PLAYER_SIZE)
	player1_pos.y = clamp(player1_pos.y, COURT_HEIGHT/2 + PLAYER_SIZE, COURT_HEIGHT - PLAYER_SIZE)

	# Serve logic at start
	if not game_started:
		serve_timer -= delta
		if serve_timer <= 0.0:
			# Player serves from bottom
			var angle = randf_range(-PI/6, PI/6)  # Serve with a slight random angle
			ball_pos = Vector2(COURT_WIDTH/2, COURT_HEIGHT*0.8)
			ball_velocity = Vector2(sin(angle), -cos(angle)) * BALL_SPEED
			ball_vz = -500.0
			ball_z = 0.0
			game_started = true
			# Reset double bounce rule
			bounce_on_p1_side = false
			bounce_on_p2_side = false
			double_bounce_active = true

	# Serve the ball with Spacebar if stopped or stuck (keep for testing)
	if game_started and ((ball_z == 0.0 and ball_vz == 0.0 and ball_velocity.length() < 1.0) or ball_z > 100):
		if Input.is_action_just_pressed("ui_accept"):
			var angle = randf_range(-PI/4, PI/4)
			ball_velocity = Vector2(cos(angle), sin(angle)) * BALL_SPEED
			ball_vz = -500.0
			ball_z = 0.0

	# Ball movement
	ball_pos += ball_velocity * delta
	# Ball vertical physics
	ball_vz += GRAVITY * delta
	ball_z += ball_vz * delta

	# Only clamp to ground, not to a max height
	if ball_z < 0.0:
		ball_z = 0.0
		if abs(ball_vz) > 60:
			ball_vz = -ball_vz * BOUNCE_ENERGY
		else:
			ball_vz = 0.0
		# Track bounces for double bounce rule
		if ball_pos.y > COURT_HEIGHT/2:
			bounce_on_p1_side = true
			last_bounce_side = 1
		else:
			bounce_on_p2_side = true
			last_bounce_side = 2
		# If both sides have bounced, disable double bounce rule
		if bounce_on_p1_side and bounce_on_p2_side:
			double_bounce_active = false

	# If the ball is stuck high up (e.g., > 1000), reset it
	if ball_z > 1000:
		ball_z = 0.0
		ball_vz = 0.0
		ball_velocity = Vector2.ZERO

	# Ball collision with walls
	if ball_pos.x <= BALL_SIZE or ball_pos.x >= COURT_WIDTH - BALL_SIZE:
		ball_velocity.x *= -1
	if ball_pos.y <= BALL_SIZE or ball_pos.y >= COURT_HEIGHT - BALL_SIZE:
		ball_velocity.y *= -1

	# Ball collision with CPU player (only if ball is low)
	if ball_z < HIT_HEIGHT_THRESHOLD and hit_cooldown == 0.0:  # Increased height threshold
		# Player 2 (top) hits toward bottom side
		if (ball_pos - player2_pos).length() < PLAYER_HIT_RADIUS + BALL_SIZE * HIT_DISTANCE_MULTIPLIER and last_hitter != 2 and ball_velocity.y < 0:
			# Kitchen volley rule: prevent volley if in kitchen, unless last bounce was on their side
			if is_in_kitchen(player2_pos) and ball_z > 0.0 and last_bounce_side != 2:
				pass # Do nothing, can't volley in kitchen
			# Double bounce rule: prevent volley if not satisfied
			elif double_bounce_active and ball_z > 0.0:
				pass # Do nothing, can't volley until both sides have bounced
			else:
				var target_x = randf_range(PLAYER_SIZE, COURT_WIDTH - PLAYER_SIZE)
				var target_y = COURT_HEIGHT * 0.85  # Near bottom baseline
				var target = Vector2(target_x, target_y)
				handle_player_hit(player2_pos, target, false)

	# Update ring shadow properties based on ball height
	if ball_z > 0:
		ring_alpha = clamp(ball_z / RING_MAX_HEIGHT, 0.0, 0.5)
		ring_radius = lerp(RING_MIN_RADIUS, RING_MAX_RADIUS, ball_z / RING_MAX_HEIGHT)
		
		# Update perfect hit state
		can_perfect_hit = abs(ball_z - PERFECT_HIT_HEIGHT) < PERFECT_HIT_WINDOW
	else:
		ring_alpha = 0.0
		can_perfect_hit = false

	# Keep ball in bounds
	ball_pos.x = clamp(ball_pos.x, BALL_SIZE, COURT_WIDTH - BALL_SIZE)
	ball_pos.y = clamp(ball_pos.y, BALL_SIZE, COURT_HEIGHT - BALL_SIZE)

	# Update can_hit based on ball position and mouse with increased range
	can_hit = (ball_pos - mouse_pos).length() < PLAYER_HIT_RADIUS + BALL_SIZE * HIT_DISTANCE_MULTIPLIER

	# Update sprite positions and scales
	update_sprite_transforms()
	
	queue_redraw()

func update_sprite_transforms():
	# Calculate perspective positions
	var player1_perspective_pos = apply_perspective(player1_pos)
	var player2_perspective_pos = apply_perspective(player2_pos)
	var ball_perspective_pos = apply_perspective(ball_pos)
	
	# Calculate perspective scales based on distance from net
	var player1_scale = calculate_perspective_scale(player1_pos.y)
	var player2_scale = calculate_perspective_scale(player2_pos.y)
	var ball_scale = calculate_perspective_scale(ball_pos.y)
	
	# Update player sprites
	player1_sprite.position = player1_perspective_pos
	player1_sprite.scale = BASE_SPRITE_SCALE * player1_scale * 2
	
	player2_sprite.position = player2_perspective_pos
	player2_sprite.scale = BASE_SPRITE_SCALE * player2_scale * 2
	
	# Update ball sprite
	ball_sprite.position = ball_perspective_pos - Vector2(0, ball_z)
	ball_sprite.scale = BASE_SPRITE_SCALE * ball_scale
	
	# Update shadow sprite
	shadow_sprite.position = ball_perspective_pos + Vector2(0, BALL_SHADOW_OFFSET)
	shadow_sprite.scale = BASE_SHAD0W_SPRITE_SCALE * ball_scale
	shadow_sprite.modulate.a = 0.3 * (1.0 - ball_z / 1000.0)  # Fade shadow based on height

func calculate_perspective_scale(y_pos: float) -> float:
	var dist_from_net = abs(y_pos - PERSPECTIVE_CENTER_Y)
	var t = dist_from_net / COURT_HEIGHT
	return 1.0 - pow(t, 8.5) * PERSPECTIVE_STRENGTH  # Exponential falloff

func get_ring_color() -> Color:
	if ball_z <= 0:
		return Color(0.2, 0.2, 0.2, 0.0)
	
	# Calculate how close we are to perfect hit height
	var height_ratio = 1.0 - clamp(abs(ball_z - PERFECT_HIT_HEIGHT) / PERFECT_HIT_WINDOW, 0.0, 1.0)
	
	if height_ratio > 0.9:  # Perfect timing
		return Color(0.0, 1.0, 0.0, ring_alpha)  # Bright green
	elif height_ratio > 0.7:  # Good timing
		return Color(0.0, 0.8, 0.2, ring_alpha)  # Green-yellow
	elif height_ratio > 0.4:  # Okay timing
		return Color(0.8, 0.8, 0.0, ring_alpha)  # Yellow
	else:  # Poor timing
		return Color(1.0, 0.0, 0.0, ring_alpha)  # Red

func apply_perspective(pos: Vector2) -> Vector2:
	# Calculate distance from net/kitchen center
	var dist_from_net = abs(pos.y - PERSPECTIVE_CENTER_Y)
	var dist_from_center_x = pos.x - COURT_WIDTH/2
	
	# Calculate perspective scale based on distance from net
	var distance_scale = 1.0 + (dist_from_net / COURT_HEIGHT) * PERSPECTIVE_DISTANCE_SCALE
	
	# Apply vertical perspective scaling to x coordinate
	var vertical_scale = 1.0 + (dist_from_net / COURT_HEIGHT) * PERSPECTIVE_STRENGTH
	var new_x = COURT_WIDTH/2 + (pos.x - COURT_WIDTH/2) * vertical_scale * distance_scale
	
	# Apply horizontal perspective scaling to y coordinate
	var horizontal_scale = 1.0 + (abs(dist_from_center_x) / COURT_WIDTH) * PERSPECTIVE_HORIZONTAL_STRENGTH
	var new_y = pos.y * horizontal_scale
	
	# Adjust y position based on distance from net
	if pos.y < PERSPECTIVE_CENTER_Y:
		new_y = PERSPECTIVE_CENTER_Y - (PERSPECTIVE_CENTER_Y - new_y) * distance_scale
	else:
		new_y = PERSPECTIVE_CENTER_Y + (new_y - PERSPECTIVE_CENTER_Y) * distance_scale
	
	return Vector2(new_x, new_y)

func _draw():
	# Draw court background with perspective
	var top_left = apply_perspective(Vector2(0, 0))
	var top_right = apply_perspective(Vector2(COURT_WIDTH, 0))
	var bottom_left = apply_perspective(Vector2(0, COURT_HEIGHT))
	var bottom_right = apply_perspective(Vector2(COURT_WIDTH, COURT_HEIGHT))
	
	# Draw court background
	var points = PackedVector2Array([top_left, top_right, bottom_right, bottom_left])
	draw_colored_polygon(points, Color(0.1, 0.6, 0.2))
	
	# Draw kitchen zones with perspective
	var kitchen_top = apply_perspective(Vector2(0, (COURT_HEIGHT/2) - KITCHEN_DIST))
	var kitchen_bottom = apply_perspective(Vector2(0, (COURT_HEIGHT/2) + KITCHEN_DIST))
	var kitchen_top_right = apply_perspective(Vector2(COURT_WIDTH, (COURT_HEIGHT/2) - KITCHEN_DIST))
	var kitchen_bottom_right = apply_perspective(Vector2(COURT_WIDTH, (COURT_HEIGHT/2) + KITCHEN_DIST))
	
	# Top kitchen
	var top_kitchen_points = PackedVector2Array([
		apply_perspective(Vector2(0, (COURT_HEIGHT/2) - KITCHEN_DIST)),
		apply_perspective(Vector2(COURT_WIDTH, (COURT_HEIGHT/2) - KITCHEN_DIST)),
		apply_perspective(Vector2(COURT_WIDTH, COURT_HEIGHT/2)),
		apply_perspective(Vector2(0, COURT_HEIGHT/2))
	])
	draw_colored_polygon(top_kitchen_points, Color(0.8, 0.9, 0.5, 0.7))
	
	# Bottom kitchen
	var bottom_kitchen_points = PackedVector2Array([
		apply_perspective(Vector2(0, COURT_HEIGHT/2)),
		apply_perspective(Vector2(COURT_WIDTH, COURT_HEIGHT/2)),
		apply_perspective(Vector2(COURT_WIDTH, (COURT_HEIGHT/2) + KITCHEN_DIST)),
		apply_perspective(Vector2(0, (COURT_HEIGHT/2) + KITCHEN_DIST))
	])
	draw_colored_polygon(bottom_kitchen_points, Color(0.8, 0.9, 0.5, 0.7))
	
	# Draw service boxes with perspective
	var service_top = apply_perspective(Vector2(0, (COURT_HEIGHT/2) - KITCHEN_DIST - SERVICE_DIST))
	var service_bottom = apply_perspective(Vector2(0, (COURT_HEIGHT/2) + KITCHEN_DIST + SERVICE_DIST))
	
	# Top service box
	var top_service_points = PackedVector2Array([
		service_top,
		apply_perspective(Vector2(COURT_WIDTH, (COURT_HEIGHT/2) - KITCHEN_DIST - SERVICE_DIST)),
		apply_perspective(Vector2(COURT_WIDTH, (COURT_HEIGHT/2) - KITCHEN_DIST)),
		kitchen_top
	])
	draw_colored_polygon(top_service_points, Color(0.2, 0.7, 0.4, 0.3))
	
	# Bottom service box
	var bottom_service_points = PackedVector2Array([
		kitchen_bottom,
		apply_perspective(Vector2(COURT_WIDTH, (COURT_HEIGHT/2) + KITCHEN_DIST)),
		service_bottom,
		apply_perspective(Vector2(0, (COURT_HEIGHT/2) + KITCHEN_DIST + SERVICE_DIST))
	])
	draw_colored_polygon(bottom_service_points, Color(0.2, 0.7, 0.4, 0.3))
	
	# Draw lines with perspective
	# Outer lines
	draw_line(top_left, top_right, Color.WHITE, LINE_WIDTH)
	draw_line(top_right, bottom_right, Color.WHITE, LINE_WIDTH)
	draw_line(bottom_right, bottom_left, Color.WHITE, LINE_WIDTH)
	draw_line(bottom_left, top_left, Color.WHITE, LINE_WIDTH)
	
	# Net
	var net_top = apply_perspective(Vector2(0, COURT_HEIGHT/2 - 2))
	var net_bottom = apply_perspective(Vector2(0, COURT_HEIGHT/2 + 2))
	draw_line(net_top, apply_perspective(Vector2(COURT_WIDTH, COURT_HEIGHT/2 - 2)), Color(0.95,0.95,0.95), 4)
	draw_line(net_bottom, apply_perspective(Vector2(COURT_WIDTH, COURT_HEIGHT/2 + 2)), Color(0.95,0.95,0.95), 4)
	
	# Center line
	draw_line(apply_perspective(Vector2(COURT_WIDTH/2, 0)), apply_perspective(Vector2(COURT_WIDTH/2, COURT_HEIGHT)), Color.WHITE, LINE_WIDTH)
	
	# Kitchen lines
	draw_line(kitchen_top, kitchen_top_right, Color.WHITE, LINE_WIDTH)
	draw_line(kitchen_bottom, kitchen_bottom_right, Color.WHITE, LINE_WIDTH)
	
	# Draw ring shadow with timing-based color
	if ring_alpha > 0:
		var ring_color = get_ring_color()
		draw_arc(ball_sprite.position, ring_radius, 0, TAU, 32, ring_color, 4.0)
	
	# Draw mouse hit indicator if can hit and in CPU vs User mode
	if can_hit and current_mode == GameMode.CPU_VS_USER:
		var mouse_perspective_pos = apply_perspective(mouse_pos)
		# Draw larger hit radius indicator
		draw_circle(mouse_perspective_pos, PLAYER_HIT_RADIUS, Color(1, 1, 1, 0.2))
		draw_circle(mouse_perspective_pos, PLAYER_SIZE, Color(1, 1, 1, 0.3))

	# Draw trajectory preview with improved visualization
	if show_trajectory and trajectory_points.size() > 1:
		# Draw main trajectory line with shot type color
		var base_color = SHOT_COLORS[current_shot_type]
		for i in range(trajectory_points.size() - 1):
			var alpha = TRAJECTORY_ALPHA * (1.0 - float(i) / trajectory_points.size())
			var color = Color(base_color.r, base_color.g, base_color.b, alpha)
			draw_line(trajectory_points[i], trajectory_points[i + 1], color, 2.0)
		
		# Draw bounce points
		for i in range(1, trajectory_points.size() - 1):
			var prev_point = trajectory_points[i - 1]
			var curr_point = trajectory_points[i]
			var next_point = trajectory_points[i + 1]
			
			# If there's a sharp angle, it's likely a bounce
			var angle = abs(prev_point.direction_to(curr_point).angle_to(curr_point.direction_to(next_point)))
			if angle > 0.5:  # Adjust this threshold as needed
				draw_circle(curr_point, 3, base_color)

	# Draw debug text
	if debug_text != "":
		draw_string(debug_font, Vector2(10, 30), debug_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color.WHITE)

func handle_player_hit(player_pos: Vector2, target: Vector2, is_player1: bool) -> void:
	var hit_dir = (target - ball_pos).normalized()
	var distance = (target - ball_pos).length()
	
	# Determine shot type based on timing and position
	current_shot_type = determine_shot_type(is_player1, ball_pos, ball_velocity)
	
	# Debug output
	var shot_names = {
		ShotType.DRIVE: "Drive",
		ShotType.DINK: "Dink",
		ShotType.VOLLEY: "Volley",
		ShotType.LOB: "Lob",
		ShotType.TOPSPIN: "Topspin",
		ShotType.SLICE: "Slice",
		ShotType.BLOCK: "Block"
	}
	debug_text = "Shot: " + shot_names[current_shot_type]
	print(debug_text)
	
	# Apply perfect hit bonus if timing is right
	if can_perfect_hit:
		perfect_hit_active = true
		# Perfect hits have more control and power
		ball_velocity = hit_dir * (BALL_SPEED * SHOT_SPEEDS[current_shot_type] * 1.2)
		ball_vz = -clamp(400 + distance, 600, 1000) * SHOT_ARC_MULTIPLIERS[current_shot_type]
		debug_text += " (Perfect!)"
	else:
		perfect_hit_active = false
		ball_velocity = hit_dir * (BALL_SPEED * SHOT_SPEEDS[current_shot_type])
		ball_vz = -clamp(300 + distance, 500, 900) * SHOT_ARC_MULTIPLIERS[current_shot_type]
	
	ball_pos = player_pos + hit_dir * (PLAYER_SIZE + BALL_SIZE + 1)
	last_hitter = 1 if is_player1 else 2
	
	# Update trajectory after hit
	update_trajectory_preview()
	show_trajectory = true

func determine_shot_type(is_player1: bool, ball_pos: Vector2, ball_velocity: Vector2) -> ShotType:
	var player_pos = mouse_pos if is_player1 else player2_pos
	
	# Check if in kitchen
	var in_kitchen = is_in_kitchen(player_pos)
	
	# Determine shot based on situation
	if in_kitchen:
		# In kitchen - prefer dinks and volleys
		if ball_z < 100:  # Low ball
			return ShotType.DINK
		else:  # High ball
			return ShotType.VOLLEY
	elif ball_velocity.length() > BALL_SPEED * 1.2:
		# Fast incoming ball - block or slice
		return ShotType.BLOCK if randf() < 0.6 else ShotType.SLICE
	elif ball_pos.y < COURT_HEIGHT * 0.3 or ball_pos.y > COURT_HEIGHT * 0.7:
		# Deep in court - consider lob
		return ShotType.DINK if randf() < 0.4 else ShotType.DRIVE
	else:
		# Normal situation - mix of shots
		var shots = [ShotType.DRIVE, ShotType.TOPSPIN, ShotType.SLICE]
		return shots[randi() % shots.size()]

func is_in_kitchen(pos: Vector2) -> bool:
	var kitchen_y1 = COURT_HEIGHT/2 - KITCHEN_DIST
	var kitchen_y2 = COURT_HEIGHT/2 + KITCHEN_DIST
	return pos.y > kitchen_y1 and pos.y < kitchen_y2

func update_trajectory_preview():
	trajectory_points.clear()
	var hit_dir = (mouse_pos - ball_pos).normalized()
	var distance = (mouse_pos - ball_pos).length()
	
	# Determine shot type based on timing and position
	current_shot_type = determine_shot_type(true, ball_pos, ball_velocity)
	
	# Calculate initial velocity with more realistic physics
	var initial_velocity = hit_dir * (BALL_SPEED * SHOT_SPEEDS[current_shot_type])
	var initial_vz = -clamp(300 + distance, 500, 900) * SHOT_ARC_MULTIPLIERS[current_shot_type]
	
	# Simulate trajectory with smaller time steps for accuracy
	var sim_pos = ball_pos
	var sim_vel = initial_velocity
	var sim_z = ball_z
	var sim_vz = initial_vz
	var time_step = TRAJECTORY_DURATION / (TRAJECTORY_POINTS * 4)  # Smaller time steps for accuracy
	
	# Add initial point
	var perspective_pos = apply_perspective(sim_pos) - Vector2(0, sim_z)
	trajectory_points.append(perspective_pos)
	
	# Simulate until we have enough points or ball goes out of bounds
	while trajectory_points.size() < TRAJECTORY_POINTS:
		# Update position and velocity
		sim_pos += sim_vel * time_step
		sim_vz += GRAVITY * time_step
		sim_z += sim_vz * time_step
		
		# Handle bounce with energy loss
		if sim_z < 0.0:
			sim_z = 0.0
			sim_vz = -sim_vz * BOUNCE_ENERGY
			# Reduce horizontal velocity on bounce
			sim_vel *= 0.95
		
		# Add point to trajectory
		perspective_pos = apply_perspective(sim_pos) - Vector2(0, sim_z)
		trajectory_points.append(perspective_pos)
		
		# Stop if ball goes out of bounds or stops moving
		if (sim_pos.x < 0 or sim_pos.x > COURT_WIDTH or 
			sim_pos.y < 0 or sim_pos.y > COURT_HEIGHT or
			(sim_vel.length() < 50 and sim_z < 1.0)):
			break
		
		# Add more points around bounces for smoother visualization
		if sim_z < 1.0 and sim_vz < 0:
			var bounce_pos = sim_pos
			var bounce_z = 0.0
			var bounce_perspective = apply_perspective(bounce_pos) - Vector2(0, bounce_z)
			trajectory_points.append(bounce_perspective)
