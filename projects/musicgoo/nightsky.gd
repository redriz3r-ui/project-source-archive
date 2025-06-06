extends Node2D

enum GameState { MENU, GAME_LOOP, TEST, GAME_OVER, PAUSED, GAME_2 }
var current_state: GameState = GameState.MENU

# Vector CRT visual effects
const VECTOR_GLOW_WIDTH_MULTIPLIER: float = 2.0  # How much wider the glow line is
const VECTOR_GLOW_ALPHA: float = 0.3  # Transparency of the glow
const VECTOR_GLOW_ENABLED: bool = true  # Toggle for the effect
const VECTOR_FLICKER_INTENSITY: float = 0.2  # How much the lines flicker (0.0 to disable)

# Mobile controls
var virtual_joystick: Control
var joystick_outer: TextureRect
var joystick_inner: TextureRect
var joystick_active: bool = false
var joystick_origin: Vector2
var joystick_direction: Vector2 = Vector2.ZERO
const JOYSTICK_RADIUS: float = 120.0  # Increased from 80.0
const JOYSTICK_DEAD_ZONE: float = 0.2
# Dynamic joystick variables
var touch_joystick_id: int = -1  # Store the touch ID that activated the joystick

# Music control UI
var music_menu_button: TextureButton
var music_menu_container: Control
var music_menu_open: bool = false
var prev_button: TextureButton
var next_button: TextureButton
var pause_button: TextureButton
const MUSIC_BUTTON_SIZE: Vector2 = Vector2(50, 50)
const MUSIC_MENU_PADDING: float = 10.0
# Game Over UI buttons
var game_over_buttons_container: HBoxContainer = null
var restart_button: Button = null
var return_menu_button: Button = null

# Sound effects
var point_sound: AudioStreamPlayer
var explosion_sound: AudioStreamPlayer
var laser_sound: AudioStreamPlayer
var asteroid_hit_sound: AudioStreamPlayer      # New - for hitting asteroids
var asteroid_spawn_sound: AudioStreamPlayer    # New - for game over
var respawn_sound: AudioStreamPlayer           # New - for restarting
var laser_safe_sound: AudioStreamPlayer        # New - when laser becomes safe
var countdown_sound: AudioStreamPlayer         # New - for power-up ending
# Dictionary to track individual asteroid sound players
var asteroid_sound_players = {}
var sfx_capture: AudioEffectCapture
var flash_timer: float = 0.0
var last_flash_intensity: float = 0.0

# Progressive difficulty variables
var current_difficulty: float = 1.0
var base_asteroid_speed: float = 150.0  # Changed to positive for downward movement
var base_spawn_interval: float = 2.0
var base_negative_chance: float = 0.3
var base_power_up_interval: float = 15.0
var enemy_spawn_interval: float = 2.0
var power_up_spawn_interval: float = 15.0  # Added missing variable
const MAX_DIFFICULTY: float = 5.0  # Increased max difficulty
const DIFFICULTY_THRESHOLD: int = 1000  # Lowered threshold for faster difficulty ramp
const EARLY_GAME_SCALE: float = 0.0003  # Increased early game scaling
const LATE_GAME_SCALE: float = 0.0005    # Reduced late game scaling to prevent difficulty from maxing out too quickly

var audio_player: AudioStreamPlayer2D
var star_container: Node2D
var starfield: CPUParticles2D
var background: ColorRect
var speed_label: Label
var player_ship: Sprite2D
var enemies = []
var bullets = []
var current_laser_count: int = 0  # Track how many lasers have appeared

var instructions_left: Label
var instructions_right: Label
var instructions_top: Label

var disco_ball_container: Node2D
const DISCO_BALL_RADIUS: float = 220.0
const GRID_LINES: int = 4
var grid_lines: Array = []
var shimmer_timer: float = 0.0



var score_label: Label
var coins = []
const COIN_SPAWN_INTERVAL: float = 3.0
var coin_spawn_timer: float = 0.0
const COIN_SPEED: float = 100.0
const COIN_RADIUS: float = 10.0
const COIN_SCORE_VALUE: int = 10

var title_label: Label
var glow_label: Label
var glow_labels: Array = []

# Combo UI elements
var combo_container: Control
var combo_meter: Line2D
var combo_fill: Line2D
var combo_timer_fill: Line2D  # Added missing variable
var combo_label: Label
var combo_counter: Label
const METER_HEIGHT: float = 200.0  # Vertical meter height
const METER_WIDTH: float = 8.0     # Meter thickness
const METER_PADDING: float = 20.0
var combo_pulse_timer: float = 0.0
const COMBO_PULSE_SPEED: float = 4.0  # Faster pulses
var combo_segments: Array[Line2D] = []
const COMBO_SEGMENTS: Array[Dictionary] = [
	{"threshold": 2, "multiplier": 1.5, "color": Color(0, 1, 0)},    # Green
	{"threshold": 4, "multiplier": 2.0, "color": Color(1, 1, 0)},    # Yellow
	{"threshold": 6, "multiplier": 2.5, "color": Color(1, 0.5, 0)},  # Orange
	{"threshold": 8, "multiplier": 3.0, "color": Color(1, 0, 0)},    # Red
	{"threshold": MAX_COMBO, "multiplier": 4.0, "color": Color(1, 0, 1)}  # Magenta
]
var last_combo: int = 0  # Track combo changes for effects
var combo_drain_effect: bool = false  # Added missing variable

var ship_velocity = Vector2.ZERO
const MAX_SHIP_SPEED: float = 500.0
const ACCELERATION: float = 15.0
const DECELERATION: float = 8.0
const TILT_ANGLE: float = 0.2
const MAX_TILT_ANGLE: float = 0.8
const TILT_INCREASE_RATE: float = 1.5
var tilt_timer: float = 0.0

var gravity: float = 600.0
var thrust: float = 800.0
var vertical_velocity: float = 0.0
const MAX_VERTICAL_SPEED: float = 400.0

var score: int = 0
var game_over_label: Label
var is_game_over: bool = false
const SHIP_RADIUS: float = 20.0

	# --- PLAYER STATS SYSTEM ---
var player_stats = {}
var stats_menu_container = null

# Combo system variables
var current_combo: int = 0
var combo_timer: float = 0.0
const COMBO_TIMEOUT: float = 2.0
const MAX_COMBO: int = 10
const BASE_COMBO_MULTIPLIER: float = 0.5

var spectrum
var camera_position = Vector3.ZERO
var camera_yaw = 0.0
var camera_pitch = 0.0
var camera_roll = 0.0
var mouse_sensitivity = 0.1
var current_speed = 100.0
var velocity = Vector3.ZERO
var drag_delay = 0.0

const PLAYER_SPEED: float = 200.0
# Remove the fixed bounds
# const PLAYER_BOUNDS: Vector2 = Vector2(100, 100)
const SHIP_MARGIN: float = 5.0  # Smaller margin for more playable area
# ENEMY_SPAWN_INTERVAL is now a variable declared at the top
var spawn_timer: float = 0.0

var wave_patterns = [
	{"type": "gap", "y": 0.3, "size": "Small"},
	{"type": "double", "y1": 0.2, "y2": 0.8, "size": "Medium"},
	{"type": "tunnel", "y": 0.5, "size": "Large"}
]

var FIRING_COOLDOWN: float = 0.1  # Reduced from 0.2
const DEFAULT_FIRING_COOLDOWN: float = 0.1  # Reduced from 0.2
var firing_timer: float = 0.0

var viewport_size: Vector2

# Remove the waveform constants
const STAR_COUNT = 250
const STAR_MIN_SIZE = 1.0
const STAR_MAX_SIZE = 3.0
const Z_FAR = 1000.0
const Z_NEAR = 10.0
const FOV = 90.0
const PITCH_LIMIT = 89.0
const ROLL_SPEED = 90.0
const YAW_LIMIT = 0.2
const MAX_SPEED = 1000.0
const MIN_SPEED = 100.0
const SPEED_INCREMENT = 50.0
const MIN_VELOCITY_THRESHOLD = 0.5
const DRAG_DELAY_TIME = 1.0
const PARALLAX_SPEED_MIN = 20.0
const PARALLAX_SPEED_MAX = 50.0
const ACCENT_STAR_MAX_SIZE = 12.0
const ACCENT_STAR_RATIO = 0.6

# Remove waveform-related constants
# const WAVEFORM_LENGTH = 50
# const WAVEFORM_SPACING = 20.0
# const WAVEFORM_BASE_RADIUS = 20.0
# const WAVEFORM_MAX_RADIUS = 50.0
# const WAVEFORM_SPOKES = 8

var distance_score_timer: float = 0.0
const DISTANCE_SCORE_INTERVAL: float = 0.5
const DISTANCE_SCORE_AMOUNT: int = 1

var power_ups = []
const POWER_UP_SPAWN_INTERVAL: float = 10.0
var power_up_spawn_timer: float = 0.0
const FLAG_SPACING: float = 60.0
const FLAG_HEIGHT: float = 40.0
const FLAG_SPEED: float = -80.0
const POWER_UP_DURATION: float = 5.0
var power_up_timer: float = 0.0
var is_power_up_active: bool = false

var asteroids = []
var stars = []
# Remove these arrays
# var waveform_points = []
# var waveform_lines = []

# New variables from simpler game logic
var game_time: float = 0.0
var max_enemies: int = 5
var heat: float = 0.0
const MAX_HEAT: float = 100.0
const HEAT_PER_SHOT: float = 20.0
const COOL_DOWN_RATE: float = 30.0
var fuel: float = 100.0
const FUEL_DRAIN_RATE: float = 5.0
const FUEL_PER_COIN: float = 20.0
var laser_spawn_timer: float = 0.0
const LASER_SPAWN_INTERVAL: float = 8.0  # Changed from 15.0 to 8.0 seconds
var lasers: Array = []
var high_score: int = 0
var chaser: Node2D
var pause_ui_button: TextureButton
var pause_menu_container: Control
var main_menu_container: Control
var game_select_menu_container: Control
var music_player_menu_container: Control  # <-- Added global declaration

# Add near the top with other constants
const SCORE_THRESHOLD_FOR_SAFE_PASSAGE: int = 150  # Adjust this value as needed
const LASER_NORMAL_SPEED: float = -100.0
const LASER_SAFE_SPEED: float = -300.0

# Add near the top:
const BASE_SHIP_ROTATION = -PI / 2

@export var music_files: Array[String] = [
	"res://songs/BIANCA.mp3",
	"res://songs/Soul.mp3",
	"res://songs/Squid.mp3",
	"res://songs/Blast.mp3"
	
]
var current_track = 0

# --- STARFIELD VISUAL PROFILE SYSTEM ---
# Map each track (filename, uppercase, no path) to a visual profile
var track_visual_profiles = {
	"BIANCA.MP3": {
		"palette": [
			Color(0.18, 0.30, 0.90, 1),
			Color(0.20, 0.40, 0.90, 1),
			Color(0.22, 0.45, 0.93, 1),
				Color(1, 0.5, 0, 1),    # Bright orange
			Color(0.23, 0.49, 0.93, 1),
			Color(0.25, 0.53, 0.93, 1),
			Color(0.26, 0.58, 0.93, 1)
		],
		"reactivity": "pulse",
		"effect": "comet"
	},
	"COSBY.MP3": {
		"palette": [
			Color(0.545, 0.0, 0.0, 1),   #8b0000
			Color(0.698, 0.0, 0.0, 1),   #b20000
			Color(0.804, 0.0, 0.0, 1),  #cd0000
			Color(0.871, 0.0, 0.0, 1),  #de0000
			Color(0.933, 0.0, 0.0, 1),   #ee0000
			Color(1.0, 0.0, 0.0, 1)     #ff0000
		],
		"reactivity": "color_shift",
		"effect": "star_trails"
	},
	"SOUL.MP3": {
		"palette": [
			Color(0.4, 0.0, 0.4, 1),    # Deep purple
			Color(0.6, 0.0, 0.6, 1),    # Medium purple
			Color(0.8, 0.0, 0.8, 1),    # Bright purple
			Color(0.9, 0.2, 0.9, 1),    # Light purple
			Color(1.0, 0.4, 1.0, 1),    # Pink-purple
			Color(1.0, 0.6, 1.0, 1)     # Light pink
		],
		"reactivity": "wave",
		"effect": "nebula"
	},
	"SQUID.MP3": {
		"palette": [
			Color(0.0, 0.8, 0.8, 1),    # Cyan
			Color(0.2, 0.9, 0.9, 1),    # Light cyan
			Color(0.4, 1.0, 1.0, 1),    # Bright cyan
			Color(0.6, 0.8, 1.0, 1),    # Sky blue
			Color(0.8, 0.6, 1.0, 1),    # Lavender
			Color(1.0, 0.4, 1.0, 1)     # Pink
		],
		"reactivity": "tentacle",
		"effect": "swirl"
	},
	"BLAST.MP3": {
		"palette": [
			Color(1.0, 0.0, 0.0, 1),    # Red
			Color(1.0, 0.5, 0.0, 1),    # Orange
			Color(1.0, 1.0, 0.0, 1),    # Yellow
			Color(0.0, 1.0, 0.0, 1),    # Green
			Color(0.0, 0.0, 1.0, 1),    # Blue
			Color(0.5, 0.0, 1.0, 1)     # Purple
		],
		"reactivity": "explosion",
		"effect": "fireworks"
	},
	"COUSIN.MP3": {
		"palette": [
			Color(0.2, 0.8, 0.2, 1),    # Forest green
			Color(0.4, 0.9, 0.4, 1),    # Light green
			Color(0.6, 1.0, 0.6, 1),    # Bright green
			Color(0.8, 0.8, 0.2, 1),    # Yellow-green
			Color(1.0, 0.6, 0.2, 1),    # Orange
			Color(1.0, 0.4, 0.0, 1)     # Red-orange
		],
		"reactivity": "bounce",
		"effect": "spiral"
	},
	"ICE.MP3": {
		"palette": [
			Color(0.8, 0.8, 1.0, 1),    # Light blue
			Color(0.6, 0.8, 1.0, 1),    # Sky blue
			Color(0.4, 0.8, 1.0, 1),    # Medium blue
			Color(0.2, 0.8, 1.0, 1),    # Deep blue
			Color(0.0, 0.8, 1.0, 1),    # Ocean blue
			Color(0.0, 0.6, 0.8, 1)     # Dark blue
		],
		"reactivity": "crystal",
		"effect": "snowfall"
	}
}

var current_visual_profile = null

func set_starfield_profile():
	var track_name = music_files[current_track].get_file().to_upper()
	current_visual_profile = track_visual_profiles.get(track_name, null)
	if current_visual_profile:
		for star in stars:
			var color = current_visual_profile.palette[randi() % current_visual_profile.palette.size()]
			star.set_meta("base_color", color)

var Asteroid = {
	"vertices": [
		Vector3(10, 0, 0), Vector3(-10, 0, 0), Vector3(0, 10, 0), Vector3(0, -10, 0),
		Vector3(0, 0, 10), Vector3(0, 0, -10), Vector3(5, 5, 5), Vector3(-5, -5, -5)
	],
	"edges": [
		[0, 2], [0, 3], [0, 4], [0, 5], [1, 2], [1, 3], [1, 4], [1, 5],
		[2, 4], [2, 5], [3, 4], [3, 5]
	],
	"position": Vector3.ZERO,
	"rotation": Vector3.ZERO,
	"move_velocity": Vector3.ZERO,
	"angular_velocity": Vector3.ZERO,
	"line_node": null
}

func create_asteroid():
	var asteroid = Asteroid.duplicate()
	return asteroid

func generate_placeholder_ship_texture() -> Texture:
	var image = Image.create(128, 128, false, Image.FORMAT_RGBA8)
	var vertices = [
		Vector2(96, 64), Vector2(48, 40), Vector2(48, 88), Vector2(40, 48),
		Vector2(40, 80), Vector2(64, 64)
	]
	var edges = [
		[0, 1], [0, 2], [1, 3], [2, 4], [3, 4], [1, 5], [2, 5]
	]
	
	# First draw the glow effect with a wider stroke if enabled
	if VECTOR_GLOW_ENABLED:
		for edge in edges:
			var v1 = vertices[edge[0]]
			var v2 = vertices[edge[1]]
			var avg_x = (v1.x + v2.x) / 2.0
			var brightness = lerp(0.5, 1.0, avg_x / 128.0)
			var glow_color = Color(0, brightness, 0, VECTOR_GLOW_ALPHA)
			var dx = int(v2.x) - int(v1.x)
			var dy = int(v2.y) - int(v1.y)
			var steps = max(abs(dx), abs(dy))
			if steps == 0:
				continue
			var x_inc = dx / float(steps)
			var y_inc = dy / float(steps)
			var x = v1.x
			var y = v1.y
			for i in range(steps + 1):
				var px = int(x)
				var py = int(y)
				if px >= 0 and px < 128 and py >= 0 and py < 128:
					# Draw a wider stroke for glow (3-5 pixels)
					for ox in range(-4, 5):
						for oy in range(-4, 5):
							var tx = px + ox
							var ty = py + oy
							if tx >= 0 and tx < 128 and ty >= 0 and ty < 128:
								# Fade glow based on distance from center line
								var dist = sqrt(ox * ox + oy * oy)
								if dist <= 4.0:
									var fade = 1.0 - (dist / 4.0)
									var pixel_color = glow_color
									pixel_color.a *= fade
									# Only set if empty or blend with existing
									var current = image.get_pixel(tx, ty)
									if current.a < 0.01:
										image.set_pixel(tx, ty, pixel_color)
									else:
										var blended = current.blend(pixel_color)
										image.set_pixel(tx, ty, blended)
				x += x_inc
				y += y_inc
	
	# Then draw the main lines
	for edge in edges:
		var v1 = vertices[edge[0]]
		var v2 = vertices[edge[1]]
		var avg_x = (v1.x + v2.x) / 2.0
		var brightness = lerp(0.5, 1.0, avg_x / 128.0)
		var line_color = Color(0, brightness, 0, 1)
		var dx = int(v2.x) - int(v1.x)
		var dy = int(v2.y) - int(v1.y)
		var steps = max(abs(dx), abs(dy))
		if steps == 0:
			continue
		var x_inc = dx / float(steps)
		var y_inc = dy / float(steps)
		var x = v1.x
		var y = v1.y
		for i in range(steps + 1):
			var px = int(x)
			var py = int(y)
			if px >= 0 and px < 128 and py >= 0 and py < 128:
				for ox in range(-1, 2):
					for oy in range(-1, 2):
						var tx = px + ox
						var ty = py + oy
						if tx >= 0 and tx < 128 and ty >= 0 and ty < 128:
							image.set_pixel(tx, ty, line_color)
			x += x_inc
			y += y_inc
	return ImageTexture.create_from_image(image)

func create_power_up(y_pos: float) -> Node2D:
	var power_up = Node2D.new()
	var flag1 = Line2D.new()
	flag1.width = 2.0
	flag1.default_color = Color(0, 1, 0)
	flag1.add_point(Vector2(-FLAG_SPACING / 2, -FLAG_HEIGHT / 2))
	flag1.add_point(Vector2(-FLAG_SPACING / 2, FLAG_HEIGHT / 2))
	power_up.add_child(flag1)
	var flag2 = Line2D.new()
	flag2.width = 2.0
	flag2.default_color = Color(0, 1, 0)
	flag2.add_point(Vector2(FLAG_SPACING / 2, -FLAG_HEIGHT / 2))
	flag2.add_point(Vector2(FLAG_SPACING / 2, FLAG_HEIGHT / 2))
	power_up.add_child(flag2)
	power_up.position = Vector2(viewport_size.x + 50, y_pos)
	power_up.set_meta("velocity", Vector2(FLAG_SPEED, 0))
	power_up.set_meta("passed", false)
	add_child(power_up)
	return power_up

# Laser difficulty scaling
const BASE_LASER_THRESHOLD: int = 150  # Initial points needed
const MIN_SCORE_GAP: int = 100  # Minimum points needed beyond current score
const SCORE_PERCENT_INCREASE: float = 0.25  # Each laser requires 25% more than current score

func calculate_laser_requirement(current_score: int) -> int:
	# For the chaser (first laser), keep it simple
	if current_laser_count == 0:
		return BASE_LASER_THRESHOLD
	
	# For subsequent lasers, scale based on current score
	var base_requirement = current_score * (1.0 + SCORE_PERCENT_INCREASE)
	
	# Ensure there's at least MIN_SCORE_GAP points to achieve
	var min_requirement = current_score + MIN_SCORE_GAP
	
	# Return the larger of the two requirements
	return max(int(base_requirement), min_requirement)

func create_laser() -> Node2D:
	var laser = Node2D.new()
	
	# Add glow line with vector CRT effect if enabled
	if VECTOR_GLOW_ENABLED:
		var glow_line = Line2D.new()
		glow_line.name = "GlowLine"
		glow_line.width = 5.0 * VECTOR_GLOW_WIDTH_MULTIPLIER
		glow_line.default_color = Color(1, 0, 0, VECTOR_GLOW_ALPHA)  # Starts red with glow alpha
		glow_line.add_point(Vector2(0, 0))
		glow_line.add_point(Vector2(viewport_size.x, 0))  # Horizontal line
		laser.add_child(glow_line)
	
	# Add main line
	var line = Line2D.new()
	line.name = "MainLine"
	line.width = 5.0
	line.default_color = Color(1, 0, 0)  # Starts red
	line.add_point(Vector2(0, 0))
	line.add_point(Vector2(viewport_size.x, 0))  # Horizontal line
	laser.add_child(line)

	# Create a Control node for label
	var label_container = Control.new()
	label_container.position = Vector2(viewport_size.x / 2 - 50, 10)  # Centered above laser
	label_container.size = Vector2(100, 30)

	# Add background panel
	var panel = ColorRect.new()
	panel.color = Color(0, 0, 0, 0.5)
	panel.size = Vector2(100, 30)
	label_container.add_child(panel)
	var custom_font = load("res://ARCADECLASSIC.TTF")

	# Points needed label
	var required_score = calculate_laser_requirement(score)
	current_laser_count += 1
	var points_label = Label.new()
	points_label.text = str(required_score - score) + " more points"
	points_label.add_theme_color_override("font_color", Color(1, 1, 1))
	points_label.add_theme_font_size_override("font_size", 20)
	points_label.add_theme_font_override("font", custom_font)
	points_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	points_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	points_label.size = Vector2(100, 30)
	label_container.add_child(points_label)
	laser.add_child(label_container)

	laser.position = Vector2(0, -50)  # Spawn just above the screen
	laser.set_meta("velocity", Vector2(0, 100.0))  # Move down
	laser.set_meta("required_score", required_score)
	laser.set_meta("is_safe", false)
	laser.set_meta("has_glow", VECTOR_GLOW_ENABLED)
	return laser

func update_state_visuals():
	match current_state:
		GameState.MENU:
			clear_gameplay_objects() # Clean up gameplay objects when entering menu
			# Only show the main menu, hide the track label
			if speed_label:
				speed_label.visible = false
			if score_label:
				score_label.visible = false
			if game_over_label:
				game_over_label.visible = false
			if player_ship:
				player_ship.visible = false
			if combo_container:
				combo_container.visible = false
			if chaser:
				chaser.visible = false
			if disco_ball_container:
				disco_ball_container.visible = true
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
			if pause_ui_button:
				pause_ui_button.visible = false
			if main_menu_container:
				main_menu_container.visible = true
				reset_menu_button_colors(main_menu_container)
			if pause_menu_container:
				pause_menu_container.visible = false
			if game_select_menu_container:
				game_select_menu_container.visible = false
			if $CanvasLayer.has_node("GameOverButtonsContainer"):
				$CanvasLayer.get_node("GameOverButtonsContainer").visible = false
			if title_label:
				title_label.visible = true
			if glow_label:
				glow_label.visible = true
			if stats_menu_container:
				stats_menu_container.visible = false
			if music_player_menu_container:
				music_player_menu_container.visible = false
			for glow in glow_labels:
				glow.visible = true
		GameState.GAME_LOOP:
			speed_label.visible = true
			if score_label:
				score_label.visible = true
			if game_over_label:
				game_over_label.visible = false
			if player_ship:
				player_ship.visible = true
			if chaser:
				chaser.visible = true
			if combo_container:
				combo_container.visible = true
			if disco_ball_container:
				disco_ball_container.visible = false
			if title_label:
				title_label.visible = false
			if glow_label:
				glow_label.visible = false
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
			if pause_ui_button:
				pause_ui_button.visible = true
			if pause_menu_container:
				pause_menu_container.visible = false
			if main_menu_container:
				main_menu_container.visible = false
			if game_select_menu_container:
				game_select_menu_container.visible = false
			if stats_menu_container:
				stats_menu_container.visible = false
			if music_player_menu_container:
				music_player_menu_container.visible = false
			if $CanvasLayer.has_node("GameOverButtonsContainer"):
				$CanvasLayer.get_node("GameOverButtonsContainer").visible = false
			for glow in glow_labels:
				glow.visible = false
		GameState.TEST:
			speed_label.visible = true
			if score_label:
				score_label.visible = false
			if game_over_label:
				game_over_label.visible = false
			if player_ship:
				player_ship.visible = false
			if combo_container:
				combo_container.visible = false
			if disco_ball_container:
				disco_ball_container.visible = false
			if title_label:
				title_label.visible = false
			if glow_label:
				glow_label.visible = false
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
			if pause_ui_button:
				pause_ui_button.visible = false
			if pause_menu_container:
				pause_menu_container.visible = false
			if main_menu_container:
				main_menu_container.visible = false
			if game_select_menu_container:
				game_select_menu_container.visible = false
			if stats_menu_container:
				stats_menu_container.visible = false
			if music_player_menu_container:
				music_player_menu_container.visible = false
			if $CanvasLayer.has_node("GameOverButtonsContainer"):
				$CanvasLayer.get_node("GameOverButtonsContainer").visible = false
			for glow in glow_labels:
				glow.visible = false
		GameState.GAME_OVER:
			speed_label.visible = false
			if score_label:
				score_label.visible = false
				if score > high_score:
					high_score = score
				game_over_label.text = "Game Over\nScore: " + str(score) + "\nHigh Score: " + str(high_score)
				game_over_label.visible = true
			if player_ship:
				player_ship.visible = false
			if combo_container:
				combo_container.visible = false
			if disco_ball_container:
				disco_ball_container.visible = false
			if title_label:
				title_label.visible = false
			if glow_label:
				glow_label.visible = false
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
			if pause_ui_button:
				pause_ui_button.visible = false
			if pause_menu_container:
				pause_menu_container.visible = false
			if main_menu_container:
				main_menu_container.visible = false
			if game_select_menu_container:
				game_select_menu_container.visible = false
			if stats_menu_container:
				stats_menu_container.visible = false
			if music_player_menu_container:
				music_player_menu_container.visible = false
			if $CanvasLayer.has_node("GameOverButtonsContainer"):
				$CanvasLayer.get_node("GameOverButtonsContainer").visible = true
			for glow in glow_labels:
				glow.visible = false
		GameState.PAUSED:
			speed_label.visible = false
			if score_label:
				score_label.visible = false
			if game_over_label:
				game_over_label.visible = false
			if player_ship:
				player_ship.visible = false
			if combo_container:
				combo_container.visible = false
			if disco_ball_container:
				disco_ball_container.visible = false
			if title_label:
				title_label.visible = false
			if glow_label:
				glow_label.visible = false
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
			if pause_ui_button:
				pause_ui_button.visible = true
			if pause_menu_container:
				pause_menu_container.visible = true
				reset_menu_button_colors(pause_menu_container)
			if main_menu_container:
				main_menu_container.visible = false
			if game_select_menu_container:
				game_select_menu_container.visible = false
			if stats_menu_container:
				stats_menu_container.visible = false
			if music_player_menu_container:
				music_player_menu_container.visible = false
			if $CanvasLayer.has_node("GameOverButtonsContainer"):
				$CanvasLayer.get_node("GameOverButtonsContainer").visible = false
			for glow in glow_labels:
				glow.visible = false

func _ready():
	# Set proper viewport handling for mobile devices
	viewport_size = DisplayServer.window_get_size()
	
	# Debug prints
	print("Window size: ", DisplayServer.window_get_size())
	print("Viewport size: ", get_viewport_rect().size)
	
	# Determine if we're on mobile by checking aspect ratio or OS features
	var aspect_ratio = viewport_size.x / viewport_size.y
	var is_mobile = aspect_ratio < 0.8 || aspect_ratio > 2.2 || OS.has_feature("mobile")
	
	# Create virtual joystick for mobile
	if is_mobile:
		create_virtual_joystick()
	

	# --- Ensure stats menu is created ---
	load_player_stats()
	
	# Enable and configure the Camera2D
	var camera = $StarContainer/Camera2D
	if camera:
		print("Camera2D found, setting up...")
		
		# Set initial zoom directly for mobile
		if is_mobile:
			# Set a reasonable fixed zoom for mobile to avoid being too zoomed in
			camera.zoom = Vector2(0.7, 0.7)  # Default zoom out to see more of the game area
			
			# For mobile, increase star count and emission radius for better visuals on tall screens
			if starfield:
				starfield.amount = 800  # More stars for mobile
				starfield.emission_sphere_radius = 300.0  # Larger emission area for wider field of view
				
			# Set stretch mode optimized for mobile
			get_tree().root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
			get_tree().root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
		else:
			get_tree().root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
			get_tree().root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
		
		print("Camera position set to: ", camera.position)
	else:
		push_error("Camera2D not found at $StarContainer/Camera2D!")
	
	get_tree().root.content_scale_factor = 1.0
	
	# Force update viewport size immediately
	_on_viewport_size_changed()
	
	# Ensure we're responding to orientation and size changes
	get_viewport().size_changed.connect(_on_viewport_size_changed)
	

	audio_player = $AudioPlayer
	if not audio_player:
		push_error("AudioPlayer node not found at $AudioPlayer!")
		return
	audio_player.bus = "Master"
	background = $Background
	if not background:
		push_error("Background node not found at $Background!")
		return

	star_container = $StarContainer
	if not star_container:
		push_error("StarContainer node not found at $StarContainer!")
		return

	starfield = $StarContainer/Starfield
	if not starfield:
		push_error("Starfield node not found at $StarContainer/Starfield!")
		return


	speed_label = $CanvasLayer/SpeedLabel
	if not speed_label:
		push_error("SpeedLabel node not found at $CanvasLayer/SpeedLabel!")
		return
		
	game_over_label = Label.new()
	game_over_label.name = "GameOverLabel"
	var theme = Theme.new()
	var font = FontFile.new()
	var font_resource = load("res://ARCADECLASSIC.TTF")
	if font_resource and font_resource is FontFile:
		font = font_resource
	else:
		font = SystemFont.new()
	theme.set_font("font", "Label", font)
	theme.set_font_size("font_size", "Label", 48)
	theme.set_color("font_color", "Label", Color(1, 0, 0))
	game_over_label.set_theme(theme)
	game_over_label.text = "Game Over\nScore: 0\nTap to Restart"
	game_over_label.anchor_left = 0.5
	game_over_label.anchor_top = 0.5
	game_over_label.anchor_right = 0.5
	game_over_label.anchor_bottom = 0.5
	$CanvasLayer.add_child(game_over_label)
	game_over_label = $CanvasLayer/GameOverLabel
	await get_tree().process_frame
	var game_over_size = game_over_label.get_rect().size
	game_over_label.offset_left = -game_over_size.x / 2
	game_over_label.offset_top = -game_over_size.y / 2
	game_over_label.visible = false

	score_label = $CanvasLayer/ScoreLabel
	if not score_label:
		push_error("ScoreLabel node not found at $CanvasLayer/ScoreLabel!")
		return
	score_label.add_theme_font_size_override("font_size", 48)  # or any size you want
	score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	# Move to top right
	score_label.position = Vector2(
		viewport_size.x - score_label.get_rect().size.x - 50,
		50
	)
	score_label.visible = false
	
	
		# After $CanvasLayer is set up in _ready()
	instructions_left = Label.new()
	instructions_left.name = "instructions_left"
	instructions_left.text = "Drag left side \n for movement"
	instructions_left.add_theme_font_size_override("font_size", 28)
	instructions_left.add_theme_color_override("font_color", Color(1,1,1))
	instructions_left.add_theme_font_override("font", font_resource)
	instructions_left.modulate = Color(1,1,1,0)
	instructions_left.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	instructions_left.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	instructions_left.position = Vector2(60, viewport_size.y/2 + 400)
	$CanvasLayer.add_child(instructions_left)

	instructions_right = Label.new()
	instructions_right.name = "instructions_right"
	instructions_right.text = "Tap right side \nto shoot"
	instructions_right.add_theme_font_size_override("font_size", 28)
	instructions_right.add_theme_color_override("font_color", Color(1,1,1))
	instructions_right.add_theme_font_override("font", font_resource)
	instructions_right.modulate = Color(1,1,1,0)
	instructions_right.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	instructions_right.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	instructions_right.position = Vector2(viewport_size.x - 300, viewport_size.y / 2 - -400)
	$CanvasLayer.add_child(instructions_right)

	instructions_top = Label.new()
	instructions_top.name = "instructions_top"
	instructions_top.text = "Destroy, collect, score!\nReach the goal to clear lasers."
	instructions_top.add_theme_font_size_override("font_size", 36)
	instructions_top.add_theme_color_override("font_color", Color(1,1,1))
	instructions_top.add_theme_font_override("font", font_resource)
	instructions_top.modulate = Color(1,1,1,0)
	instructions_top.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	instructions_top.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	instructions_top.position = Vector2(viewport_size.x / 2 - 260, 300)
	$CanvasLayer.add_child(instructions_top)

	# Initialize combo UI
	combo_container = Control.new()
	combo_container.position = Vector2(20, 100)
	combo_container.size = Vector2(100, METER_HEIGHT)
	$CanvasLayer.add_child(combo_container)

	# Create vertical meter background
	combo_meter = Line2D.new()
	combo_meter.width = METER_WIDTH
	combo_meter.default_color = Color(0.2, 0.2, 0.2, 0.8)
	combo_meter.add_point(Vector2(0, 0))
	combo_meter.add_point(Vector2(0, METER_HEIGHT))
	combo_container.add_child(combo_meter)

	# Create meter fill
	combo_fill = Line2D.new()
	combo_fill.width = METER_WIDTH - 2
	combo_fill.default_color = Color(1, 1, 1)
	combo_fill.add_point(Vector2(0, METER_HEIGHT))
	combo_fill.add_point(Vector2(0, METER_HEIGHT))
	combo_container.add_child(combo_fill)

	# Create timer drain effect
	combo_timer_fill = Line2D.new()
	combo_timer_fill.width = METER_WIDTH - 2
	combo_timer_fill.default_color = Color(1, 1, 1, 0.3)  # Semi-transparent overlay
	combo_timer_fill.add_point(Vector2(0, METER_HEIGHT))
	combo_timer_fill.add_point(Vector2(0, METER_HEIGHT))
	combo_container.add_child(combo_timer_fill)

	# Add segment markers (now horizontal lines)
	for i in range(COMBO_SEGMENTS.size()):
		var segment = Line2D.new()
		var y_pos = METER_HEIGHT * (1.0 - float(COMBO_SEGMENTS[i].threshold) / MAX_COMBO)
		segment.width = 2.0
		segment.default_color = COMBO_SEGMENTS[i].color.darkened(0.5)
		segment.add_point(Vector2(-5, y_pos))
		segment.add_point(Vector2(5, y_pos))
		combo_container.add_child(segment)
		combo_segments.append(segment)

	# Create dynamic combo counter
	combo_counter = Label.new()
	combo_counter.text = "0"
	combo_counter.add_theme_font_size_override("font_size", 48)
	combo_counter.add_theme_font_override("font", font_resource)
	combo_counter.position = Vector2(METER_WIDTH + 10, METER_HEIGHT / 2 - 24)
	combo_container.add_child(combo_counter)

	# Create multiplier label
	combo_label = Label.new()
	combo_label.text = "x1.0"
	combo_label.add_theme_font_size_override("font_size", 24)
	combo_label.add_theme_font_override("font", font_resource)
	combo_label.position = Vector2(METER_WIDTH + 10, METER_HEIGHT / 2 + 24)
	combo_container.add_child(combo_label)

	# Add glow effect
	var glow = Line2D.new()
	glow.width = METER_WIDTH + 4
	glow.default_color = Color(1, 1, 1, 0.2)
	glow.add_point(Vector2(0, 0))
	glow.add_point(Vector2(0, METER_HEIGHT))
	combo_container.add_child(glow)

	var spectrum_effect = AudioEffectSpectrumAnalyzer.new()
	spectrum_effect.fft_size = 512
	if AudioServer.get_bus_effect_count(0) == 0:
		AudioServer.add_bus_effect(0, spectrum_effect, 0)
	elif not (AudioServer.get_bus_effect(0, 0) is AudioEffectSpectrumAnalyzer):
		AudioServer.remove_bus_effect(0, 0)
		AudioServer.add_bus_effect(0, spectrum_effect, 0)
	spectrum = AudioServer.get_bus_effect_instance(0, 0)

	var capture = AudioServer.get_bus_effect(0, 1)
	if not capture is AudioEffectCapture:
		capture = AudioEffectCapture.new()
		AudioServer.add_bus_effect(0, capture, 1)

	viewport_size = get_viewport_rect().size

	var canvas_layer = $CanvasLayer


	var grid_size: int = 10
	var grid_image = Image.create(viewport_size.x, 60, false, Image.FORMAT_RGBA8)
	for x in range(0, viewport_size.x, grid_size):
		for y in range(0, 60, grid_size):
			for i in range(grid_size):
				if x + i < viewport_size.x:
					grid_image.set_pixel(x + i, y, Color(0.2, 0.2, 0.2, 1))
					grid_image.set_pixel(x + i, y + grid_size - 1, Color(0.2, 0.2, 0.2, 1))
				if y + i < 60:
					grid_image.set_pixel(x, y + i, Color(0.2, 0.2, 0.2, 1))
					grid_image.set_pixel(x + grid_size - 1, y + i, Color(0.2, 0.2, 0.2, 1))
	
	var grid_texture_rect = TextureRect.new()
	grid_texture_rect.size = Vector2(viewport_size.x, 60)
	var grid_texture = ImageTexture.create_from_image(grid_image)
	grid_texture_rect.texture = grid_texture


	var overlay = ColorRect.new()
	overlay.size = Vector2(viewport_size.x, 60)
	overlay.color = Color(0, 0, 0, 0.8)


	var border = Line2D.new()
	border.width = 4.0
	border.default_color = Color(0, 1, 1)
	var border_points = [
		Vector2(0, 0), Vector2(viewport_size.x, 0),
		Vector2(viewport_size.x, 60), Vector2(0, 60), Vector2(0, 0)
	]
	for point in border_points:
		border.add_point(point)
	var gradient = Gradient.new()
	gradient.colors = [Color(0, 1, 1, 1), Color(0, 1, 0.5, 1)]
	var gradient_texture = GradientTexture1D.new()
	gradient_texture.gradient = gradient
	border.gradient = gradient_texture



	disco_ball_container = Node2D.new()
	disco_ball_container.position = Vector2(viewport_size.x / 2, 300)
	add_child(disco_ball_container)
	
	title_label = Label.new()
	title_label.text = "Shoot !\nAsteroid !\nLaser !"  # Change this to your actual game title
	title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	title_label.add_theme_font_size_override("font_size", 80)
	title_label.add_theme_color_override("font_color", Color(0, 1, 0))  # Green
	title_label.position = Vector2(170, 200)  # Centered on screen
	$CanvasLayer.add_child(title_label)
	await get_tree().process_frame  # Wait for the label to be sized
	title_label.pivot_offset = title_label.size / 2
	
	# Set custom font
	var custom_font = load("res://ARCADECLASSIC.TTF")  # Use your font path
	title_label.add_theme_font_override("font", custom_font)

	# --- Add static neon green glow effect (retro style) ---
	var glow_radius = 6
	var glow_steps = 2
	var glow_alpha = 0.35
	glow_labels.clear()  # Clear any existing glow labels
	for i in range(glow_steps):
		var angle = i * (2 * PI / glow_steps)
		var offset = Vector2(cos(angle), sin(angle)) * glow_radius
		var glow_label = Label.new()
		glow_label.text = title_label.text
		glow_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		glow_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		glow_label.add_theme_font_size_override("font_size", 80)
		glow_label.add_theme_color_override("font_color", Color(0, 1, 0, glow_alpha))
		glow_label.position = title_label.position + offset
		glow_label.pivot_offset = title_label.pivot_offset
		glow_label.add_theme_font_override("font", custom_font)
		$CanvasLayer.add_child(glow_label)
		glow_labels.append(glow_label)

	var points = []
	var num_points = 32
	for i in range(num_points):
		var angle = i * (2 * PI / num_points)
		points.append(Vector2(cos(angle) * DISCO_BALL_RADIUS, sin(angle) * DISCO_BALL_RADIUS))


	for i in range(GRID_LINES):
		var h_line = Line2D.new()
		h_line.width = 1.0
		h_line.default_color = Color(1, 1, 1, 1.5)
		var h_y = (float(i) / (GRID_LINES - 1) - 0.5) * 2 * DISCO_BALL_RADIUS
		var h_points = []
		for t in range(-DISCO_BALL_RADIUS, DISCO_BALL_RADIUS + 1, 2):
			var x = t
			var y = h_y
			var dist = sqrt(x * x + y * y)
			if dist <= DISCO_BALL_RADIUS:
				var curve_factor = sqrt(1 - (dist / DISCO_BALL_RADIUS) * (dist / DISCO_BALL_RADIUS))
				y *= curve_factor
				h_points.append(Vector2(x, y))
		h_line.points = h_points
		disco_ball_container.add_child(h_line)
		grid_lines.append(h_line)

		var v_line = Line2D.new()
		v_line.width = 1.0
		v_line.default_color = Color(1, 1, 1, 0.5)
		var v_x = (float(i) / (GRID_LINES - 1) - 0.5) * 2 * DISCO_BALL_RADIUS
		var v_points = []
		for t in range(-DISCO_BALL_RADIUS, DISCO_BALL_RADIUS + 1, 2):
			var x = v_x
			var y = t
			var dist = sqrt(x * x + y * y)
			if dist <= DISCO_BALL_RADIUS:
				var curve_factor = sqrt(1 - (dist / DISCO_BALL_RADIUS) * (dist / DISCO_BALL_RADIUS))
				x *= curve_factor
				v_points.append(Vector2(x, y))
		v_line.points = v_points
		disco_ball_container.add_child(v_line)
		grid_lines.append(v_line)

	for i in range(5):
		var asteroid = create_asteroid()
		asteroid.position = get_random_spherical_position(Z_FAR / 2) + camera_position
		asteroid.move_velocity = Vector3(randf_range(-50, 50), randf_range(-50, 50), randf_range(-50, 50))
		asteroid.angular_velocity = Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1))
		asteroids.append(asteroid)
		var line = Line2D.new()
		line.width = 2.0
		line.default_color = Color(1, 1, 1, 1)
		star_container.add_child(line)
		asteroid.line_node = line

	camera_position = Vector3.ZERO
	background.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	background.size_flags_vertical = Control.SIZE_EXPAND_FILL
	background.size = get_viewport_rect().size
	background.color = Color(0, 0, 0)

	if AudioServer.get_bus_effect_count(0) > 0:
		spectrum = AudioServer.get_bus_effect_instance(0, 0)

	if music_files.size() > 0:
		var music_file = load(music_files[current_track])
		if music_file:
			audio_player.stream = music_file
			audio_player.play()
		else:
			push_warning("Failed to load music file: " + music_files[current_track])
	
	# Re-add these important lines that were accidentally removed
	viewport_size = get_viewport_rect().size
	var center = viewport_size / 2
	
	for i in range(STAR_COUNT):
		var star = ColorRect.new()
		var size = randf_range(STAR_MIN_SIZE, STAR_MAX_SIZE)
		star.size = Vector2(size, size)
		var star_pos_3d = get_random_spherical_position(Z_FAR) + camera_position
		star.set_meta("pos_3d", star_pos_3d)
		# 60% main (white), 40% accent (colored)
		if randf() < (1.0 - ACCENT_STAR_RATIO):
			star.set_meta("type", "main")
			star.set_meta("base_color", Color(1, 1, 1, 1))
			star.color = Color(1, 1, 1, 1.0)
		else:
			star.set_meta("type", "accent")
			var palette = null
			if current_visual_profile and current_visual_profile.has("palette"):
				palette = current_visual_profile.palette
			if palette and palette.size() > 0:
				var accent_color = palette[randi() % palette.size()]
				star.set_meta("base_color", accent_color)
				star.color = accent_color
			else:
				# fallback: random color
				var accent_color = Color(randf(), randf(), randf(), 1)
				star.set_meta("base_color", accent_color)
				star.color = accent_color
		star_container.add_child(star)
		stars.append(star)
	set_starfield_profile() # <-- Add this after star creation
	
	# Remove waveform tunnel initialization
	# for i in range(WAVEFORM_LENGTH):
	# 	var spoke_points = []
	# 	var spoke_lines = []
	# 	for j in range(WAVEFORM_SPOKES):
	# 		 spoke_points.append(Vector3.ZERO)
	# 		 var line = Line2D.new()
	# 		 line.width = 2.0
	# 		 line.default_color = Color(1, 1, 1, 1)
	# 		 star_container.add_child(line)
	# 		 spoke_lines.append(line)
	# 	waveform_points.append(spoke_points)
	# 	waveform_lines.append(spoke_lines)
	
	player_ship = Sprite2D.new()
	player_ship.texture = generate_placeholder_ship_texture()
	player_ship.position = Vector2(viewport_size.x / 2, viewport_size.y - SHIP_MARGIN)
	player_ship.scale = Vector2(1, 1)
	add_child(player_ship)

	# Initialize chaser with laser behavior (visual guide)
	chaser = Node2D.new()
	
	# Add glow line first if enabled
	if VECTOR_GLOW_ENABLED:
		var glow_line = Line2D.new()
		glow_line.name = "GlowLine"
		glow_line.width = 5.0 * VECTOR_GLOW_WIDTH_MULTIPLIER
		glow_line.default_color = Color(1, 0, 0, VECTOR_GLOW_ALPHA)
		glow_line.add_point(Vector2(0, 0))
		glow_line.add_point(Vector2(viewport_size.x, 0))
		chaser.add_child(glow_line)
	
	var line = Line2D.new()
	line.name = "MainLine"
	line.width = 5.0
	line.default_color = Color(1, 0, 0)
	line.add_point(Vector2(0, 0))
	line.add_point(Vector2(viewport_size.x, 0))
	chaser.add_child(line)
	
	# Add the same label setup as regular lasers
	var label_container = Control.new()
	label_container.position = Vector2(viewport_size.x / 2 - 50, 10)
	label_container.size = Vector2(100, 30)
	
	# Add background panel
	var panel = ColorRect.new()
	panel.color = Color(0, 0, 0, 0.5)
	panel.size = Vector2(100, 30)
	label_container.add_child(panel)
	
	# Set initial text for the visual guide
	var points_label = Label.new()
	points_label.text = "Goal: " + str(BASE_LASER_THRESHOLD) + " points"
	points_label.add_theme_color_override("font_color", Color(1, 1, 1))
	points_label.add_theme_font_size_override("font_size", 20)
	points_label.add_theme_font_override("font", font_resource)
	points_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	points_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	points_label.size = Vector2(100, 30)
	label_container.add_child(points_label)
	chaser.add_child(label_container)
	
	chaser.position = Vector2(0, -50)
	chaser.set_meta("velocity", Vector2(0, 100.0))
	chaser.set_meta("required_score", BASE_LASER_THRESHOLD)
	chaser.set_meta("is_safe", false)
	add_child(chaser)

	starfield.position = center
	update_state_visuals()

	# In _ready(), after creating player_ship:
	player_ship.position = Vector2(viewport_size.x / 2, viewport_size.y - SHIP_MARGIN)
	player_ship.rotation = BASE_SHIP_ROTATION  # Face up

	print("[DEBUG][_ready] viewport_size: ", viewport_size)
	print("[DEBUG][_ready] player_ship: ", player_ship)
	if player_ship:
		print("[DEBUG][_ready] player_ship.position: ", player_ship.position)

	# Initialize sound effects
	point_sound = AudioStreamPlayer.new()
	point_sound.stream = load("res://point_up.mp3")
	point_sound.volume_db = -10.0
	point_sound.bus = "SFX"
	add_child(point_sound)
	
	explosion_sound = AudioStreamPlayer.new()
	explosion_sound.stream = load("res://asteroid_explode.mp3")
	explosion_sound.volume_db = -8.0
	explosion_sound.bus = "SFX"
	add_child(explosion_sound)
	
	laser_sound = AudioStreamPlayer.new()
	print("DEBUG: Initializing laser sound")
	var laser_sound_file = load("res://fire_laser.mp3")
	if laser_sound_file:
		print("DEBUG: Laser sound file loaded successfully")
		laser_sound.stream = laser_sound_file
		laser_sound.volume_db = -5.0  # Slightly louder
		laser_sound.bus = "SFX"
	else:
		print("DEBUG: Failed to load laser sound file")
	add_child(laser_sound)
	print("DEBUG: Laser sound initialized: ", laser_sound)

	# New sound effects
	asteroid_hit_sound = AudioStreamPlayer.new()
	asteroid_hit_sound.stream = load("res://asteroid_hit_2.mp3")
	asteroid_hit_sound.volume_db = -7.0
	asteroid_hit_sound.bus = "SFX"
	add_child(asteroid_hit_sound)

	asteroid_spawn_sound = AudioStreamPlayer.new()
	asteroid_spawn_sound.stream = load("res://asteroid_spawn.mp3")
	asteroid_spawn_sound.volume_db = -8.0
	asteroid_spawn_sound.bus = "SFX"
	add_child(asteroid_spawn_sound)

	respawn_sound = AudioStreamPlayer.new()
	respawn_sound.stream = load("res://respawn.mp3")
	respawn_sound.volume_db = -7.0
	respawn_sound.bus = "SFX"
	add_child(respawn_sound)

	laser_safe_sound = AudioStreamPlayer.new()
	laser_safe_sound.stream = load("res://laser_safe.mp3")
	laser_safe_sound.volume_db = -9.0  # Lower volume since it's a bit long
	laser_safe_sound.bus = "SFX"
	add_child(laser_safe_sound)

	countdown_sound = AudioStreamPlayer.new()
	countdown_sound.stream = load("res://countdown_timer_end.mp3")
	countdown_sound.volume_db = -8.0
	countdown_sound.bus = "SFX"
	add_child(countdown_sound)

	# SFX bus is usually index 1 if it's right after Master
	var effect = AudioServer.get_bus_effect(1, 0)
	if effect is AudioEffectCapture:
		sfx_capture = effect
	else:
		sfx_capture = null

	# Create pause button (top left)
	pause_ui_button = TextureButton.new()
	pause_ui_button.size = Vector2(50, 50)
	pause_ui_button.position = Vector2(30, 30)
	# Draw pause icon (two vertical bars)
	var pause_img = Image.create(60, 60, false, Image.FORMAT_RGBA8)
	pause_img.fill(Color(0, 0, 0, 0))
	for x in range(12, 20):
		for y in range(10, 40):
			pause_img.set_pixel(x, y, Color(1, 1, 1, 0.8))
	for x in range(30, 38):
		for y in range(10, 40):
			pause_img.set_pixel(x, y, Color(1, 1, 1, 0.8))
	var pause_tex = ImageTexture.create_from_image(pause_img)
	pause_ui_button.texture_normal = pause_tex
	pause_ui_button.pressed.connect(_on_pause_button_pressed)
	$CanvasLayer.add_child(pause_ui_button)
	pause_ui_button.visible = false

	# Create pause menu container (centered, hidden by default)
	pause_menu_container = Control.new()
	pause_menu_container.name = "PauseMenuContainer"
	pause_menu_container.size = Vector2(320, 320)
	pause_menu_container.position = Vector2((viewport_size.x - 320) / 2, (viewport_size.y - 320) / 2)
	pause_menu_container.visible = false
	$CanvasLayer.add_child(pause_menu_container)

	var button_labels = ["Resume", "Music Player", "Settings", "Menu"]
	for i in range(button_labels.size()):
		var btn = ColorRect.new()
		btn.size = Vector2(240, 48)
		btn.position = Vector2(40, 40 + i * 64)
		btn.color = Color(1, 1, 1, 0.95)  # White box by default
		btn.name = button_labels[i].replace(" ", "_").to_lower()
		btn.mouse_filter = Control.MOUSE_FILTER_STOP
		
		var lbl = Label.new()
		lbl.text = button_labels[i]
		lbl.size = btn.size
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		lbl.add_theme_color_override("font_color", Color(0,0,0))  # Black text by default
		# Use existing font_resource and theme
		if font_resource and font_resource is FontFile:
			lbl.set_theme(theme)
		else:
			lbl.add_theme_font_override("font", SystemFont.new())
		lbl.add_theme_font_size_override("font_size", 36)
		btn.add_child(lbl)
		
		btn.gui_input.connect(_on_pause_menu_button_input.bind(btn, lbl))
		pause_menu_container.add_child(btn)

	# Create main menu container (centered, hidden by default)
	main_menu_container = Control.new()
	main_menu_container.name = "MainMenuContainer"
	main_menu_container.size = Vector2(360, 400)
	main_menu_container.position = Vector2((viewport_size.x - 360) / 2, (viewport_size.y - 400) / 2)
	main_menu_container.visible = false
	$CanvasLayer.add_child(main_menu_container)

	var main_menu_labels = ["Start Game", "Stats", "Music Player", "Settings"]
	for i in range(main_menu_labels.size()):
		var btn = ColorRect.new()
		btn.size = Vector2(280, 64)
		btn.position = Vector2(40, 40 + i * 80)
		btn.color = Color(1, 1, 1, 0.95)
		btn.name = main_menu_labels[i].replace(" ", "_").to_lower()
		btn.mouse_filter = Control.MOUSE_FILTER_STOP
		var lbl = Label.new()
		lbl.text = main_menu_labels[i]
		lbl.size = btn.size
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		lbl.add_theme_color_override("font_color", Color(0,0,0))
		if font_resource and font_resource is FontFile:
			lbl.set_theme(theme)
		else:
			lbl.add_theme_font_override("font", SystemFont.new())
		lbl.add_theme_font_size_override("font_size", 36)
		btn.add_child(lbl)
		btn.gui_input.connect(_on_main_menu_button_input.bind(btn, lbl))
		main_menu_container.add_child(btn)

	# Create game select menu (hidden by default)
	game_select_menu_container = Control.new()
	game_select_menu_container.name = "GameSelectMenuContainer"
	game_select_menu_container.size = Vector2(320, 220)
	game_select_menu_container.position = Vector2((viewport_size.x - 320) / 2, (viewport_size.y - 220) / 2)
	game_select_menu_container.visible = false
	$CanvasLayer.add_child(game_select_menu_container)

	var game_select_labels = ["Game 1", "Game 2", "Back"]
	for i in range(game_select_labels.size()):
		var btn = ColorRect.new()
		btn.size = Vector2(240, 56)
		btn.position = Vector2(40, 30 + i * 64)
		btn.color = Color(1, 1, 1, 0.95)
		btn.name = game_select_labels[i].replace(" ", "_").to_lower()
		btn.mouse_filter = Control.MOUSE_FILTER_STOP
		var lbl = Label.new()
		lbl.text = game_select_labels[i]
		lbl.size = btn.size
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		lbl.add_theme_color_override("font_color", Color(0,0,0))
		if font_resource and font_resource is FontFile:
			lbl.set_theme(theme)
		else:
			lbl.add_theme_font_override("font", SystemFont.new())
		lbl.add_theme_font_size_override("font_size", 32)
		btn.add_child(lbl)
		btn.gui_input.connect(_on_game_select_menu_button_input.bind(btn, lbl))
		game_select_menu_container.add_child(btn)

	# At the very end, ensure the main menu is shown on launch
	set_game_state(GameState.MENU)

	# 2. Add a new music_player_menu_container styled like the other menus, after main_menu_container and game_select_menu_container creation in _ready()
	music_player_menu_container = Control.new()
	music_player_menu_container.name = "MusicPlayerMenuContainer"
	music_player_menu_container.size = Vector2(360, 320)
	music_player_menu_container.position = Vector2((viewport_size.x - 360) / 2, (viewport_size.y - 320) / 2)
	music_player_menu_container.visible = false
	$CanvasLayer.add_child(music_player_menu_container)

	# Add 'Now playing' label
	var music_song_label = Label.new()
	music_song_label.name = "SongLabel"
	music_song_label.text = "Now playing:\n" + music_files[current_track].get_file()
	music_song_label.add_theme_font_size_override("font_size", 18)
	music_song_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	music_song_label.size = Vector2(music_player_menu_container.size.x, 40)
	music_song_label.position = Vector2(0, 40)
	music_player_menu_container.add_child(music_song_label)

	# Add HBoxContainer for text buttons
	var hbox = HBoxContainer.new()
	hbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.position = Vector2(0, 100)
	hbox.size = Vector2(music_player_menu_container.size.x, 48)

	# Previous button
	var prev_btn = Button.new()
	prev_btn.text = "Previous"
	prev_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var prev_lambda = func():
		change_track(-1)
		get_viewport().set_input_as_handled()
	prev_btn.pressed.connect(prev_lambda)
	hbox.add_child(prev_btn)

	# Pause/Play button
	var playpause_btn = Button.new()
	playpause_btn.text = "Pause" if audio_player.playing and not audio_player.stream_paused else "Play"
	playpause_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var playpause_lambda = func():
		if audio_player.playing and not audio_player.stream_paused:
			audio_player.stream_paused = true
			
			playpause_btn.text = "Play"
		else:
			audio_player.stream_paused = false
			
			playpause_btn.text = "Pause"
		get_viewport().set_input_as_handled()
	playpause_btn.pressed.connect(playpause_lambda)
	hbox.add_child(playpause_btn)

	# Next button
	var next_btn = Button.new()
	next_btn.text = "Next"
	next_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var next_lambda = func():
		change_track(1)
		get_viewport().set_input_as_handled()
	next_btn.pressed.connect(next_lambda)
	hbox.add_child(next_btn)

	music_player_menu_container.add_child(hbox)
	

	# Add Back button (styled like other menus)
	var back_btn = ColorRect.new()
	back_btn.size = Vector2(120, 48)
	back_btn.position = Vector2((music_player_menu_container.size.x - 120) / 2, 200)
	back_btn.color = Color(1, 1, 1, 0.95)
	back_btn.name = "back"
	back_btn.mouse_filter = Control.MOUSE_FILTER_STOP
	var back_lbl = Label.new()
	back_lbl.text = "Back"
	back_lbl.size = back_btn.size
	back_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	back_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	back_lbl.add_theme_color_override("font_color", Color(0,0,0))
	back_lbl.add_theme_font_size_override("font_size", 28)
	back_btn.add_child(back_lbl)
	back_btn.gui_input.connect(_on_music_player_menu_button_input.bind(back_btn, back_lbl))
	music_player_menu_container.add_child(back_btn)
	
	music_song_label.add_theme_font_override("font", font_resource)
	back_lbl.add_theme_font_override("font", font_resource)
	for btn in hbox.get_children():
		if btn is Button:
			btn.add_theme_font_override("font", font_resource)

	# --- Create Game Over Buttons Container ---
	game_over_buttons_container = HBoxContainer.new()
	game_over_buttons_container.name = "GameOverButtonsContainer"
	game_over_buttons_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	# Center the container horizontally and position it below the Game Over label
	game_over_buttons_container.anchor_left = 0.5
	game_over_buttons_container.anchor_right = 0.5
	game_over_buttons_container.anchor_top = 0.5
	game_over_buttons_container.anchor_bottom = 0.5
	game_over_buttons_container.offset_left = -200  # Half of estimated width (adjust as needed)
	game_over_buttons_container.offset_top = 90    # Distance below center (adjust as needed)
	game_over_buttons_container.visible = false
	$CanvasLayer.add_child(game_over_buttons_container)

	return_menu_button = Button.new()
	return_menu_button.text = "Menu"
	return_menu_button.add_theme_font_size_override("font_size", 64)
	if font_resource and font_resource is FontFile:
		return_menu_button.add_theme_font_override("font", font_resource)
	return_menu_button.pressed.connect(_on_return_menu_button_pressed)
	game_over_buttons_container.add_child(return_menu_button)
	
	restart_button = Button.new()
	restart_button.text = "Restart"
	restart_button.add_theme_font_size_override("font_size", 64)
	if font_resource and font_resource is FontFile:
		restart_button.add_theme_font_override("font", font_resource)
	restart_button.pressed.connect(_on_restart_button_pressed)
	game_over_buttons_container.add_child(restart_button)





	# Move these functions to the top level, not inside any function
func save_player_stats():
	var file = FileAccess.open("user://player_stats.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(player_stats))
		file.close()

func load_player_stats():
	var file = FileAccess.open("user://player_stats.json", FileAccess.READ)
	if file:
		var data = file.get_as_text()
		var parsed = JSON.parse_string(data)
		if typeof(parsed) == TYPE_DICTIONARY:
			player_stats = parsed
		file.close()
	ensure_player_stats_keys()
	# Sync high_score from player_stats
	if player_stats.has("highest_score"):
		high_score = player_stats["highest_score"]
	else:
		high_score = 0
	# --- Create Stats Menu Container ---
	stats_menu_container = Control.new()
	stats_menu_container.name = "StatsMenuContainer"
	stats_menu_container.size = Vector2(400, 520) # Increased size for better fit
	stats_menu_container.position = Vector2((viewport_size.x - 400) / 2, (viewport_size.y - 520) / 2)
	stats_menu_container.visible = false
	$CanvasLayer.add_child(stats_menu_container)

	# Add background panel
	var stats_panel = ColorRect.new()
	stats_panel.size = stats_menu_container.size
	stats_panel.color = Color(0, 0, 0, 0.8)
	stats_menu_container.add_child(stats_panel)



	# Add stats label (Arcade Classic font)
	var stats_theme = Theme.new()
	var stats_font = load("res://ARCADECLASSIC.TTF")
	if stats_font and stats_font is FontFile:
		stats_theme.set_font("font", "Label", stats_font)
		stats_theme.set_font_size("font_size", "Label", 48)
		stats_theme.set_color("font_color", "Label", Color(0, 1, 1))
	var stats_label = Label.new()
	stats_label.name = "StatsLabel"
	stats_label.theme = stats_theme
	stats_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	stats_label.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	stats_label.size = Vector2(stats_menu_container.size.x, stats_menu_container.size.y - 60)
	stats_label.position = Vector2(0, 20)
	stats_menu_container.add_child(stats_label)
	update_stats_label()

	# Add Back button
	var stats_back_btn = ColorRect.new()
	stats_back_btn.size = Vector2(120, 48)
	stats_back_btn.position = Vector2((stats_menu_container.size.x - 120) / 2, stats_menu_container.size.y - 60)
	stats_back_btn.color = Color(1, 1, 1, 0.95)
	stats_back_btn.name = "back"
	stats_back_btn.mouse_filter = Control.MOUSE_FILTER_STOP
	var stats_back_lbl = Label.new()
	stats_back_lbl.text = "Back"
	stats_back_lbl.size = stats_back_btn.size
	stats_back_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	stats_back_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	stats_back_lbl.add_theme_color_override("font_color", Color(0,0,0))
	stats_back_lbl.add_theme_font_size_override("font_size", 32)
	# Use Arcade Classic font for the back button label
	if stats_font and stats_font is FontFile:
		stats_back_lbl.add_theme_font_override("font", stats_font)
	stats_back_btn.add_child(stats_back_lbl)
	stats_back_btn.gui_input.connect(_on_stats_menu_button_input.bind(stats_back_btn, stats_back_lbl))
	stats_menu_container.add_child(stats_back_btn)


func create_music_control_button(position: Vector2, type: String, callback: Callable) -> TextureButton:
	var button = TextureButton.new()
	button.size = MUSIC_BUTTON_SIZE
	button.position = position
	
	# Generate button icon
	var button_image = Image.create(int(MUSIC_BUTTON_SIZE.x), int(MUSIC_BUTTON_SIZE.y), false, Image.FORMAT_RGBA8)
	button_image.fill(Color(0, 0, 0, 0))  # Transparent background
	
	# Draw appropriate icon based on type
	var icon_size = int(MUSIC_BUTTON_SIZE.x * 0.6)
	var margin = int((MUSIC_BUTTON_SIZE.x - icon_size) / 2)
	
	match type:
		"prev":
			# Draw previous track icon (double triangle pointing left)
			for x in range(icon_size):
				for y in range(icon_size):
					var rel_x = float(x) / icon_size
					var rel_y = float(y) / icon_size
					
					# First triangle
					if rel_x <= 0.4 and rel_y >= 0.5 - rel_x and rel_y <= 0.5 + rel_x:
						button_image.set_pixel(margin + x, margin + y, Color(1, 1, 1, 0.8))
					
					# Second triangle
					if rel_x >= 0.4 and rel_x <= 0.8 and rel_y >= 0.9 - rel_x and rel_y <= rel_x + 0.1:
						button_image.set_pixel(margin + x, margin + y, Color(1, 1, 1, 0.8))
		
		"pause":
			# Draw pause icon (two parallel lines)
			var bar_width = int(icon_size * 0.25)
			var bar_spacing = int(icon_size * 0.2)
			var bar_start_x = int((MUSIC_BUTTON_SIZE.x - (bar_width * 2 + bar_spacing)) / 2)
			
			for i in range(2):
				var bar_x = bar_start_x + i * (bar_width + bar_spacing)
				for x in range(bar_width):
					for y in range(icon_size):
						button_image.set_pixel(bar_x + x, margin + y, Color(1, 1, 1, 0.8))
		
		"next":
			# Draw next track icon (double triangle pointing right)
			for x in range(icon_size):
				for y in range(icon_size):
					var rel_x = float(x) / icon_size
					var rel_y = float(y) / icon_size
					
					# First triangle
					if rel_x >= 0.6 and rel_y >= 1.5 - rel_x and rel_y <= rel_x - 0.5:
						button_image.set_pixel(margin + x, margin + y, Color(1, 1, 1, 0.8))
					
					# Second triangle
					if rel_x >= 0.2 and rel_x <= 0.6 and rel_y >= 1.1 - rel_x and rel_y <= rel_x - 0.1:
						button_image.set_pixel(margin + x, margin + y, Color(1, 1, 1, 0.8))
	
	var button_texture = ImageTexture.create_from_image(button_image)
	button.texture_normal = button_texture
	
	# Create pressed texture (slightly darker)
	var pressed_image = button_image.duplicate()
	for x in range(pressed_image.get_width()):
		for y in range(pressed_image.get_height()):
			var color = pressed_image.get_pixel(x, y)
			pressed_image.set_pixel(x, y, color.darkened(0.3))
	
	var pressed_texture = ImageTexture.create_from_image(pressed_image)
	button.texture_pressed = pressed_texture
	
	# Add hover effect texture (slightly brighter)
	var hover_image = button_image.duplicate()
	for x in range(hover_image.get_width()):
		for y in range(hover_image.get_height()):
			var color = hover_image.get_pixel(x, y)
			if color.a > 0:
				hover_image.set_pixel(x, y, color.lightened(0.3))
	
	var hover_texture = ImageTexture.create_from_image(hover_image)
	button.texture_hover = hover_texture
	
	# Connect the button's pressed signal to the callback
	button.pressed.connect(callback)
	
	return button

func toggle_music_menu():
	music_menu_open = !music_menu_open
	music_menu_container.visible = music_menu_open
	
	# Create a slight animation effect
	if music_menu_open:
		music_menu_container.modulate = Color(1, 1, 1, 0)
		var tween = create_tween()
		tween.tween_property(music_menu_container, "modulate", Color(1, 1, 1, 1), 0.2)
	
	# Update the pause button icon based on current audio state
	update_pause_button()

func toggle_music_playback():
	if audio_player.playing:
		audio_player.stream_paused = true
	else:
		audio_player.stream_paused = false
	
	# Update button appearance
	update_pause_button()

func change_track(direction: int):
	current_track = (current_track + direction + music_files.size()) % music_files.size()
	var music_file = load(music_files[current_track])
	if music_file:
		audio_player.stream = music_file
		audio_player.play()


		# Update the song label in the new menu
		var song_label = music_player_menu_container.get_node("SongLabel")
		if song_label:
			song_label.text = "Now playing:\n" + music_files[current_track].get_file()
	else:
		push_warning("Failed to load music file: " + music_files[current_track])
	update_state_visuals()
	set_starfield_profile()
	# Hide other menus if music player menu is open
	if music_player_menu_container and music_player_menu_container.visible:
		if main_menu_container:
			main_menu_container.visible = false
		if pause_menu_container:
			pause_menu_container.visible = false

func update_pause_button():
	if not pause_button:
		return
		
	# Generate appropriate icon based on current playback state
	var button_image = Image.create(int(MUSIC_BUTTON_SIZE.x), int(MUSIC_BUTTON_SIZE.y), false, Image.FORMAT_RGBA8)
	button_image.fill(Color(0, 0, 0, 0))  # Transparent background
	
	var icon_size = int(MUSIC_BUTTON_SIZE.x * 0.6)
	var margin = int((MUSIC_BUTTON_SIZE.x - icon_size) / 2)
	
	if audio_player.playing and not audio_player.stream_paused:
		# Draw pause icon (two parallel lines)
		var bar_width = int(icon_size * 0.25)
		var bar_spacing = int(icon_size * 0.2)
		var bar_start_x = int((MUSIC_BUTTON_SIZE.x - (bar_width * 2 + bar_spacing)) / 2)
		
		for i in range(2):
			var bar_x = bar_start_x + i * (bar_width + bar_spacing)
			for x in range(bar_width):
				for y in range(icon_size):
					button_image.set_pixel(bar_x + x, margin + y, Color(1, 1, 1, 0.8))
	else:
		# Draw play icon (triangle pointing right)
		for x in range(icon_size):
			for y in range(icon_size):
				var rel_x = float(x) / icon_size
				var rel_y = float(y) / icon_size
				
				if rel_y >= 0.5 - rel_x * 0.5 and rel_y <= 0.5 + rel_x * 0.5:
					button_image.set_pixel(margin + x, margin + y, Color(1, 1, 1, 0.8))
	
	var button_texture = ImageTexture.create_from_image(button_image)
	pause_button.texture_normal = button_texture
	
	# Create pressed texture (slightly darker)
	var pressed_image = button_image.duplicate()
	for x in range(pressed_image.get_width()):
		for y in range(pressed_image.get_height()):
			var color = pressed_image.get_pixel(x, y)
			pressed_image.set_pixel(x, y, color.darkened(0.3))
	
	var pressed_texture = ImageTexture.create_from_image(pressed_image)
	pause_button.texture_pressed = pressed_texture
	
	# Add hover effect texture (slightly brighter)
	var hover_image = button_image.duplicate()
	for x in range(hover_image.get_width()):
		for y in range(hover_image.get_height()):
			var color = hover_image.get_pixel(x, y)
			if color.a > 0:
				hover_image.set_pixel(x, y, color.lightened(0.3))
	
	var hover_texture = ImageTexture.create_from_image(hover_image)
	pause_button.texture_hover = hover_texture


func update_speed_label():
	if speed_label:
		var yaw_deg = round(camera_yaw)
		var pitch_deg = round(camera_pitch)
		var roll_deg = round(camera_roll)
		speed_label.text = "Speed: %d\nYaw: %d°\nPitch: %d°\nRoll: %d°" % [current_speed, yaw_deg, pitch_deg, roll_deg]

func _input(event):
	# Prevent global input handling when the music player menu is open
	if music_player_menu_container and music_player_menu_container.visible:
		return

	if event is InputEventKey and event.pressed:
		print("Key pressed: ", event.as_text())
		
	if event.is_action_pressed("toggle_fullscreen"):
		if DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN:
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		else:
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)

	# Dynamic joystick touch handling
	if virtual_joystick:
		if event is InputEventScreenTouch:
			var touch_position = event.position
			
			# Check if touch is on left or right half of the screen
			var is_left_side = touch_position.x < (viewport_size.x / 2)
			
			if event.pressed:
				if is_left_side and not joystick_active:
					# Create joystick at touch position if on left side
					joystick_active = true
					touch_joystick_id = event.index
					joystick_origin = touch_position
					# Position the joystick at the touch point
					virtual_joystick.global_position = touch_position - Vector2(JOYSTICK_RADIUS, JOYSTICK_RADIUS)
					# Reset inner joystick to center
					joystick_inner.position = Vector2(
						JOYSTICK_RADIUS - joystick_inner.size.x/2, 
						JOYSTICK_RADIUS - joystick_inner.size.y/2
					)
					# Make joystick visible
					virtual_joystick.visible = true
					get_viewport().set_input_as_handled()
				elif not is_left_side and current_state == GameState.GAME_LOOP and not is_game_over:
					# Shoot if touch is on right side
					shoot_bullet()
					get_viewport().set_input_as_handled()
			elif joystick_active and event.index == touch_joystick_id:  # Released the joystick touch
				reset_joystick()
				virtual_joystick.visible = false
				get_viewport().set_input_as_handled()
		
		elif event is InputEventScreenDrag:
			# Only process drags for the touch that activated the joystick
			if joystick_active and event.index == touch_joystick_id:
				# Update joystick position based on drag
				var drag_position = event.position
				
				var drag_vector = drag_position - joystick_origin
				var distance = drag_vector.length()
				
				# Limit the joystick movement to its radius
				if distance > JOYSTICK_RADIUS:
					drag_vector = drag_vector.normalized() * JOYSTICK_RADIUS
					distance = JOYSTICK_RADIUS
				
				# Update inner circle position
				joystick_inner.position = Vector2(
					JOYSTICK_RADIUS + drag_vector.x - joystick_inner.size.x/2, 
					JOYSTICK_RADIUS + drag_vector.y - joystick_inner.size.y/2
				)
				
				# Calculate normalized direction if outside dead zone
				if distance > JOYSTICK_RADIUS * JOYSTICK_DEAD_ZONE:
					joystick_direction = drag_vector.normalized() * (distance / JOYSTICK_RADIUS)
				else:
					joystick_direction = Vector2.ZERO
				
				get_viewport().set_input_as_handled()

	# Remove tap/Enter to start game in MENU state
	# (No longer allow starting game from tap or Enter in GameState.MENU)

	if event.is_action_pressed("next_track"):
		current_track = (current_track + 1) % music_files.size()
		var music_file = load(music_files[current_track])
		if music_file:
			audio_player.stream = music_file
			audio_player.play()
		else:
			push_warning("Failed to load music file: " + music_files[current_track])
		update_state_visuals()

	if event.is_action_pressed("prev_track"):
		current_track = (current_track - 1 + music_files.size()) % music_files.size()
		var music_file = load(music_files[current_track])
		if music_file:
			audio_player.stream = music_file
			audio_player.play()
		else:
			push_warning("Failed to load music file: " + music_files[current_track])
		update_state_visuals()

	if current_state == GameState.MENU:
		# No longer allow starting game from Enter or tap in menu
		pass

	if current_state == GameState.GAME_LOOP:
		if event.is_action_pressed("ui_cancel"):
			set_game_state(GameState.MENU)
			return

	if current_state == GameState.GAME_OVER:
		if event.is_action_pressed("ui_accept"):
			if respawn_sound:
				respawn_sound.play()
			reset_game_variables()
			set_game_state(GameState.GAME_LOOP)
			return

	if current_state == GameState.TEST:
		if event.is_action_pressed("ui_cancel"):
			set_game_state(GameState.MENU)
			return
		if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
			camera_yaw -= event.relative.x * mouse_sensitivity * YAW_LIMIT
			camera_pitch -= event.relative.y * mouse_sensitivity
			camera_pitch = clamp(camera_pitch, -PITCH_LIMIT, PITCH_LIMIT)
		if event is InputEventMouseButton:
			if event.button_index == MOUSE_BUTTON_WHEEL_UP:
				current_speed = min(current_speed + SPEED_INCREMENT, MAX_SPEED)
			elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				current_speed = max(current_speed - SPEED_INCREMENT, MIN_SPEED)

	if event.is_action_pressed("pause"):
		if current_state == GameState.GAME_LOOP:
			set_game_state(GameState.PAUSED)
			return
		elif current_state == GameState.PAUSED:
			set_game_state(GameState.GAME_LOOP)
			return

func get_random_spherical_position(radius: float) -> Vector3:
	var theta = randf_range(0, 2 * PI)
	var phi = randf_range(0, PI)
	var r = radius
	var x = r * sin(phi) * cos(theta)
	var y = r * sin(phi) * sin(theta)
	var z = r * cos(phi)
	return Vector3(x, y, z)

func shoot_bullet():
	# Check if we can fire (respect cooldown only, remove heat restriction)
	if firing_timer > 0:
		return
	# Increment shots fired
	ensure_player_stats_keys()
	player_stats["shots_fired"] += 1
	save_player_stats()
	
	var bullet = CPUParticles2D.new()
	bullet.emitting = true
	bullet.amount = 1
	bullet.lifetime = 0.01
	bullet.one_shot = false
	bullet.explosiveness = 0.9
	bullet.initial_velocity_min = 50
	bullet.initial_velocity_max = 500
	bullet.direction = Vector2(0, -1)  # Shoot up
	
	# Double the bullet size if power-up is active
	var size_multiplier = 2.0 if "DOUBLE_POWER" in active_double_power_ups else 1.0
	bullet.scale_amount_min = 5.0 * (1.0  * 2.0) * size_multiplier
	bullet.scale_amount_max = 5.0 * (1.0  * 2.0) * size_multiplier
	
	bullet.color = Color(1, 1, 0, 1)
	bullet.position = player_ship.position + Vector2(0, -player_ship.texture.get_height() / 2)  # Spawn centered above the ship
	add_child(bullet)
	bullets.append({"node": bullet, "velocity": Vector2(0, -500)})
	
	var muzzle_flash = CPUParticles2D.new()
	muzzle_flash.emitting = true
	muzzle_flash.amount = 1
	muzzle_flash.lifetime = 0.3
	muzzle_flash.one_shot = true
	muzzle_flash.explosiveness = 0.1
	muzzle_flash.initial_velocity_min = 500
	muzzle_flash.initial_velocity_max = 1000
	muzzle_flash.direction = Vector2(0, -1)
	muzzle_flash.spread = 50.0
	muzzle_flash.gravity = Vector2.ZERO
	muzzle_flash.scale_amount_min = 0.5 * size_multiplier
	muzzle_flash.scale_amount_max = 1.0 * size_multiplier
	muzzle_flash.color = Color(1, 1, 1, 1)
	muzzle_flash.position = player_ship.position + Vector2(0, -player_ship.texture.get_height() / 2 + 5)
	add_child(muzzle_flash)
	
	# Always play the sound, don't check kick value
	if laser_sound:
		print("DEBUG: Playing laser sound")
		laser_sound.play()
	else:
		print("DEBUG: Laser sound is null!")
		
	# Apply cooldown only, no heat increase
	firing_timer = FIRING_COOLDOWN

var shape_templates = {
	"tetrahedron": {
		"vertices": [
			Vector3(0, 0, 1), Vector3(1, 0, -0.5), Vector3(-0.5, 0.866, -0.5), Vector3(-0.5, -0.866, -0.5)
		],
		"faces": [
			[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]
		]
	},
	"cube": {
		"vertices": [
			Vector3(-1, -1, -1), Vector3(1, -1, -1), Vector3(1, 1, -1), Vector3(-1, 1, -1),
			Vector3(-1, -1, 1), Vector3(1, -1, 1), Vector3(1, 1, 1), Vector3(-1, 1, 1)
		],
		"faces": [
			[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
			[0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
			[0, 3, 7], [0, 7, 4], [1, 2, 6], [1, 6, 5]
		]
	},
	"simplified_dodecahedron": {
		"vertices": [
			Vector3(0, 0, 1), Vector3(1, 0, -0.5), Vector3(-0.5, 0.866, -0.5),
			Vector3(-0.5, -0.866, -0.5), Vector3(0, 0, -1)
		],
		"faces": [
			[0, 1, 2], [0, 1, 3], [0, 2, 3], [4, 1, 2], [4, 1, 3]
		]
	}
}

func create_coin(x_pos: float) -> Node2D:
	var coin = Node2D.new()
	var coin_shape = Polygon2D.new()
	var points = []
	var num_points = 16
	for i in range(num_points):
		var angle = i * (2 * PI / num_points)
		points.append(Vector2(cos(angle) * COIN_RADIUS, sin(angle) * COIN_RADIUS))
	coin_shape.polygon = points
	coin_shape.color = Color(1, 1, 0)
	coin.add_child(coin_shape)
	coin.position = Vector2(x_pos, -SHIP_MARGIN)
	coin.set_meta("velocity", Vector2(0, COIN_SPEED))
	coin.set_meta("radius", COIN_RADIUS)
	add_child(coin)
	return coin

func generate_asteroid_shape(scale_factor: float) -> Dictionary:
	var shape_names = shape_templates.keys()
	var selected_shape = shape_names[randi() % shape_names.size()]
	var template = shape_templates[selected_shape]
	
	var base_radius = 10.0 * scale_factor
	var vertices = []
	for vertex in template.vertices:
		vertices.append(vertex * base_radius)
	
	for i in range(vertices.size()):
		var offset = Vector3(
			randf_range(-base_radius * 0.3, base_radius * 0.3),
			randf_range(-base_radius * 0.3, base_radius * 0.3),
			randf_range(-base_radius * 0.3, base_radius * 0.3)
		)
		vertices[i] += offset
		vertices[i] = vertices[i].normalized() * base_radius * randf_range(0.7, 1.3)
	
	var faces = template.faces.duplicate()
	
	var edge_set = {}
	for face in faces:
		for j in range(3):
			var v1 = face[j]
			var v2 = face[(j + 1) % 3]
			var edge = [min(v1, v2), max(v1, v2)]
			edge_set[str(edge)] = edge
	var edges = edge_set.values()
	
	return {"vertices": vertices, "edges": edges, "faces": faces}

func create_asteroid_node(size: String, x_pos: float) -> Node2D:
	var size_data = {
		"Large": {"scale_factor": 9.0, "hp": 3, "line_width": 3.0, "tier": "Large", "points": 100},
		"Medium": {"scale_factor": 6.0, "hp": 2, "line_width": 2.0, "tier": "Medium", "points": 50},
		"Small": {"scale_factor": 3.5, "hp": 1, "line_width": 1.5, "tier": "Small", "points": 10}
	}[size]
	var asteroid = Node2D.new()
	var custom_font = load("res://ARCADECLASSIC.TTF")
	
	# Create container for the labels
	var label_container = Control.new()
	asteroid.add_child(label_container)
	
	# Increase negative asteroid chance with difficulty
	var negative_chance = min(base_negative_chance * current_difficulty, 0.6)  # Caps at 60% chance
	var is_negative = size == "Large" and randf() < negative_chance
	var points = size_data.points
	if is_negative:
		points = -points
	var point_text = ("+" if points > 0 else "") + str(points)
	
	# Create multiple overlapping labels for bold effect
	var offsets = [
		Vector2(0, 0),
		Vector2(1, 0),
		Vector2(0.5, 0)
	]
	
	for offset in offsets:
		var point_label = Label.new()
		point_label.text = point_text
		point_label.add_theme_color_override("font_color", Color(1, 0, 0) if is_negative else Color(1, 1, 1))
		point_label.add_theme_font_size_override("font_size", 24)
		point_label.add_theme_font_override("font", custom_font)
		point_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		point_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		point_label.position = offset
		label_container.add_child(point_label)
	
	var scale_factor = size_data.scale_factor
	var shape = generate_asteroid_shape(scale_factor)
	
	# Add glow effect line (added before the main line so it appears behind)
	if VECTOR_GLOW_ENABLED:
		var glow_line = Line2D.new()
		glow_line.name = "GlowLine"
		glow_line.width = size_data.line_width * VECTOR_GLOW_WIDTH_MULTIPLIER
		# Main color with reduced alpha for glow
		var main_color = Color(1, 1, 1, 1) if is_negative else Color(1, 0.2, 0.2, 1)
		glow_line.default_color = Color(main_color.r, main_color.g, main_color.b, VECTOR_GLOW_ALPHA)
		asteroid.add_child(glow_line)
	
	var line = Line2D.new()
	line.name = "MainLine"
	line.width = size_data.line_width
	# Set initial color based on whether it's negative or positive
	line.default_color = Color(1, 1, 1, 1) if is_negative else Color(1, 0.2, 0.2, 1)
	asteroid.add_child(line)
	
	# Create an audio player for this asteroid
	var sound_player = AudioStreamPlayer.new()
	if asteroid_hit_sound and asteroid_hit_sound.stream:
		sound_player.stream = asteroid_hit_sound.stream
	sound_player.volume_db = -10.0  # Start a bit quieter than main sounds
	sound_player.pitch_scale = 1.2   # Start with higher pitch (approaching)
	asteroid.add_child(sound_player)
	
	asteroid.position = Vector2(x_pos, -SHIP_MARGIN)
	# Scale asteroid speed with difficulty and add horizontal movement
	var base_speed = base_asteroid_speed * current_difficulty
	var velocity = Vector2(randf_range(-50.0, 50.0), base_speed)  # Increased horizontal movement range
	var rotation_speed = randf_range(1.0, 2.0)
	
	asteroid.set_meta("vertices_3d", shape.vertices)
	asteroid.set_meta("edges", shape.edges)
	asteroid.set_meta("faces", shape.faces)
	asteroid.set_meta("velocity", velocity)
	asteroid.set_meta("original_velocity", velocity)
	asteroid.set_meta("rotation", Vector3.ZERO)
	asteroid.set_meta("angular_velocity", Vector3(
		randf_range(-rotation_speed, rotation_speed),
		randf_range(-rotation_speed, rotation_speed),
		randf_range(-rotation_speed, rotation_speed)
	))
	asteroid.set_meta("radius", 15.0 * scale_factor)
	asteroid.set_meta("hp", size_data.hp)
	asteroid.set_meta("size_tier", size_data.tier)
	asteroid.set_meta("is_vibrating", false)
	asteroid.set_meta("vibrate_timer", 0.0)
	asteroid.set_meta("is_debris", false)
	asteroid.set_meta("points", points)
	asteroid.set_meta("is_negative", is_negative)
	asteroid.set_meta("has_glow", VECTOR_GLOW_ENABLED)
	
	# Store the sound player in our dictionary using asteroid instance_id as key
	asteroid_sound_players[asteroid.get_instance_id()] = sound_player
	
	# Create tween to adjust pitch based on position as it moves down
	var tween = create_tween()
	# Calculate estimated time to reach bottom of screen
	var screen_height = viewport_size.y
	var distance_to_bottom = screen_height + SHIP_MARGIN
	var time_to_bottom = distance_to_bottom / velocity.y
	time_to_bottom = max(time_to_bottom, 1.0) # Ensure it's at least 1 second
	
	# Tween the pitch from high (1.2) to low (0.8) over time
	tween.tween_property(sound_player, "pitch_scale", 0.8, time_to_bottom)
	
	return asteroid

func spawn_enemy():
	if enemies.size() >= max_enemies:
		return
	var size_tiers = ["Large", "Medium", "Small"]
	var size = size_tiers[randi() % size_tiers.size()]
	var x_pos = randf_range(SHIP_MARGIN, viewport_size.x - SHIP_MARGIN)
	var asteroid = create_asteroid_node(size, x_pos)
	asteroid.position.y = -SHIP_MARGIN
	add_child(asteroid)
	enemies.append(asteroid)

func spawn_enemy_wave():
	if enemies.size() >= max_enemies:
		return
	var pattern = wave_patterns[randi() % wave_patterns.size()]
	var new_enemies = []
	match pattern.type:
		"gap":
			var asteroid = create_asteroid_node(pattern.size, viewport_size.x * pattern.y)
			new_enemies.append(asteroid)
		"double":
			if enemies.size() + 2 > max_enemies:
				return
			var asteroid1 = create_asteroid_node(pattern.size, viewport_size.x * pattern.y1)
			var asteroid2 = create_asteroid_node(pattern.size, viewport_size.x * pattern.y2)
			new_enemies.append_array([asteroid1, asteroid2])
		"tunnel":
			var asteroid = create_asteroid_node(pattern.size, viewport_size.x * pattern.y)
			new_enemies.append(asteroid)
	for asteroid in new_enemies:
		add_child(asteroid)
	enemies.append_array(new_enemies)
	var kick = spectrum.get_magnitude_for_frequency_range(50.0, 500.0).length()
	if kick > 0.1:
		for enemy in new_enemies:
			flash_asteroid(enemy)

func create_floating_score(position: Vector2, points: int, is_negative: bool) -> Node2D:
	var floating_score = Node2D.new()
	floating_score.position = position
	
	# Create container for the floating labels
	var label_container = Control.new()
	floating_score.add_child(label_container)
	var custom_font = load("res://ARCADECLASSIC.TTF")
	
	var point_text = ("+" if points > 0 else "") + str(points)
	
	# Create multiple overlapping labels for bold effect (same as asteroid labels)
	var offsets = [
		Vector2(0, 0),
		Vector2(1, 0),
		Vector2(0.5, 0)
	]
	
	for offset in offsets:
		var point_label = Label.new()
		point_label.text = point_text
		point_label.add_theme_color_override("font_color", Color(1, 0, 0) if is_negative else Color(1, 1, 1))
		point_label.add_theme_font_size_override("font_size", 32)  # Slightly larger than asteroid labels
		point_label.add_theme_font_override("font", custom_font)
		point_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		point_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		point_label.position = offset
		label_container.add_child(point_label)
	
	# Create a tween for the animation
	var tween = create_tween()
	tween.set_parallel(true)  # Allow multiple properties to animate simultaneously
	
	# Move upward and slightly random horizontal
	var end_pos = Vector2(randf_range(-30, 30), -100)
	tween.tween_property(floating_score, "position", floating_score.position + end_pos, 1.0).set_ease(Tween.EASE_OUT)
	
	# Scale up
	tween.tween_property(floating_score, "scale", Vector2(1.5, 1.5), 0.2).set_ease(Tween.EASE_OUT)
	
	# Fade out
	for label in label_container.get_children():
		tween.tween_property(label, "modulate:a", 0.0, 1.0).set_ease(Tween.EASE_IN)
	
	# Delete after animation
	tween.tween_callback(floating_score.queue_free).set_delay(1.0)
	
	return floating_score

func flake_asteroid(asteroid: Node2D, hit_point: Vector2):
	var hp = asteroid.get_meta("hp", 1)
	var is_negative = asteroid.get_meta("is_negative", false)
	
	# Store original state for negative asteroids if not already stored
	if is_negative and not asteroid.has_meta("original_vertices_3d"):
		asteroid.set_meta("original_vertices_3d", asteroid.get_meta("vertices_3d", []).duplicate(true))
		asteroid.set_meta("original_edges", asteroid.get_meta("edges", []).duplicate(true))
		asteroid.set_meta("original_faces", asteroid.get_meta("faces", []).duplicate(true))
		asteroid.set_meta("original_hp", hp)
	
	hp -= 1
	asteroid.set_meta("hp", hp)
	
	# Play asteroid hit sound on the global node
	if hp > 0:
		if asteroid_hit_sound:
			asteroid_hit_sound.play()
	
	var vertices_3d = asteroid.get_meta("vertices_3d", [])
	var edges = asteroid.get_meta("edges", [])
	var faces = asteroid.get_meta("faces", [])
	var scale_factor = asteroid.get_meta("radius", 15.0) / 15.0
	var is_debris = asteroid.get_meta("is_debris", false)
	
	if hp <= 0:
		# Play explosion sound on the global node with pitch adjustment if needed
		if explosion_sound:
			explosion_sound.pitch_scale = lerp(1.2, 0.8, clamp(asteroid.position.y / viewport_size.y, 0.0, 1.0))
			explosion_sound.play()
		var base_points = asteroid.get_meta("points", 0)
		# Apply combo multiplier
		var combo_multiplier = 1.0 + (current_combo * BASE_COMBO_MULTIPLIER)
		# Apply 2x multiplier if active
		var points = base_points * combo_multiplier * (2 if "DOUBLE_POWER" in active_double_power_ups else 1)
		var floating_score = create_floating_score(asteroid.global_position, points, is_negative)
		add_child(floating_score)
		# Show combo text if combo is active
		if current_combo > 0:
			var combo_text = create_combo_text(asteroid.global_position, current_combo)
			add_child(combo_text)
		score += points
		update_score_label()
		# Clean up from our dictionary
		asteroid_sound_players.erase(asteroid.get_instance_id())
		spawn_split_particles(asteroid.global_position, asteroid.get_meta("velocity", Vector2.ZERO))
		asteroid.queue_free()
		enemies.erase(asteroid)
		# Increment asteroids destroyed
		ensure_player_stats_keys()
		player_stats["asteroids_destroyed"] += 1
		save_player_stats()
		return
	else:
		# If not destroyed, start regeneration timer for negative asteroids
		if is_negative:
			asteroid.set_meta("regen_timer", 2.0)
			asteroid.set_meta("is_regenerating", true)
	
	if not is_debris and faces.size() > 1:
		var face_idx = randi() % faces.size()
		var selected_face = faces[face_idx]
		var fragment_vertices = []
		var fragment_edges = []
		var selected_indices = selected_face
		for idx in selected_indices:
			fragment_vertices.append(vertices_3d[idx])
		fragment_edges = [[0, 1], [1, 2], [2, 0]]
		var debris = Node2D.new()
		var line = Line2D.new()
		line.width = asteroid.get_meta("line_width", 1.0) * 0.7
		line.default_color = Color(1, 0.2, 0.2, 0.7)
		debris.add_child(line)
		debris.position = asteroid.global_position
		var direction = (debris.global_position - hit_point).normalized()
		var debris_velocity = asteroid.get_meta("velocity", Vector2.ZERO) + direction * randf_range(500.0, 1000.0)
		debris.set_meta("vertices_3d", fragment_vertices)
		debris.set_meta("edges", fragment_edges)
		debris.set_meta("velocity", debris_velocity)
		debris.set_meta("rotation", asteroid.get_meta("rotation", Vector3.ZERO))
		debris.set_meta("angular_velocity", asteroid.get_meta("angular_velocity", Vector3.ZERO))
		debris.set_meta("radius", 5.0 * scale_factor)
		debris.set_meta("hp", 1)
		debris.set_meta("lifetime", randf_range(0.8, 1.5))
		debris.set_meta("initial_lifetime", debris.get_meta("lifetime"))
		add_child(debris)
		var new_faces = []
		for i in range(faces.size()):
			if i != face_idx:
				new_faces.append(faces[i])
		asteroid.set_meta("faces", new_faces)
		var edge_set = {}
		for face in new_faces:
			for j in range(3):
				var v1 = face[j]
				var v2 = face[(j + 1) % 3]
				var edge = [min(v1, v2), max(v1, v2)]
				edge_set[str(edge)] = edge
		var new_edges = edge_set.values()
		asteroid.set_meta("edges", new_edges)
		var used_vertices = {}
		for face in new_faces:
			for idx in face:
				used_vertices[idx] = true
		var new_vertices = []
		var index_map = {}
		var new_idx = 0
		for i in range(vertices_3d.size()):
			if i in used_vertices:
				index_map[i] = new_idx
				new_vertices.append(vertices_3d[i])
				new_idx += 1
		var remapped_edges = []
		for edge in new_edges:
			if edge[0] in index_map and edge[1] in index_map:
				remapped_edges.append([index_map[edge[0]], index_map[edge[1]]])
		asteroid.set_meta("vertices_3d", new_vertices)
		asteroid.set_meta("edges", remapped_edges)
		asteroid.set_meta("radius", max(5.0, scale_factor * 15.0 * 0.8))
	spawn_split_particles(asteroid.global_position, asteroid.get_meta("velocity", Vector2.ZERO))

func flash_asteroid(asteroid: Node2D):
	var line = asteroid.get_child(1) as Line2D  # Changed from 0 to 1
	if line:  # Add a null check
		var original_color = line.default_color
		line.default_color = Color(1, 1, 1, 1)
		var tween = create_tween()
		tween.tween_property(line, "default_color", original_color, 0.2)

func vibrate_asteroid(asteroid: Node2D, delta: float):
	if not asteroid.get_meta("is_vibrating", false):
		return Vector2.ZERO
	var vibrate_timer = asteroid.get_meta("vibrate_timer", 0.0)
	vibrate_timer -= delta
	if vibrate_timer <= 0:
		asteroid.set_meta("is_vibrating", false)
		asteroid.set_meta("vibrate_timer", 0.0)
		return Vector2.ZERO
	asteroid.set_meta("vibrate_timer", vibrate_timer)
	var offset = Vector2(randf_range(-3.0, 3.0), randf_range(-3.0, 3.0))
	return offset

func slow_asteroid_velocity(asteroid: Node2D):
	var current_velocity = asteroid.get_meta("velocity", Vector2.ZERO)
	asteroid.set_meta("velocity", current_velocity * 0.5)
	var timer = get_tree().create_timer(0.5)
	timer.timeout.connect(func():
		if is_instance_valid(asteroid):
			asteroid.set_meta("velocity", asteroid.get_meta("original_velocity", current_velocity))
	)

func split_asteroid(asteroid: Node2D):
	var size_tier = asteroid.get_meta("size_tier", "Medium")
	var parent_velocity = asteroid.get_meta("velocity", Vector2.ZERO)
	var parent_position = asteroid.global_position
	
	var new_asteroids = []
	if size_tier == "Large":
		new_asteroids = [
			{"scale_factor": 6.0, "hp": 2, "tier": "Medium", "line_width": 2.0},
			{"scale_factor": 6.0, "hp": 2, "tier": "Medium", "line_width": 2.0},
			{"scale_factor": 6.0, "hp": 2, "tier": "Medium", "line_width": 2.0}
		]
	elif size_tier == "Medium":
		new_asteroids = [
			{"scale_factor": 3.5, "hp": 1, "tier": "Small", "line_width": 1.5},
			{"scale_factor": 3.5, "hp": 1, "tier": "Small", "line_width": 1.5}
		]
	if new_asteroids.is_empty():
		spawn_split_particles(parent_position, parent_velocity)
		return
		
	for data in new_asteroids:
		var new_asteroid = Node2D.new()
		var shape = generate_asteroid_shape(data.scale_factor)
		var vertices_3d = shape.vertices
		var edges = shape.edges
		var line = Line2D.new()
		line.width = data.line_width
		line.default_color = Color(1, 0.2, 0.2, 1)
		new_asteroid.add_child(line)
		var offset = Vector2(randf_range(-10.0, 10.0), randf_range(-10.0, 10.0))
		new_asteroid.global_position = parent_position + offset
		var split_velocity = Vector2(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0)).normalized() * randf_range(300.0, 600.0)
		var new_velocity = parent_velocity + split_velocity
		var rotation_speed = randf_range(1.0, 2.0)
		new_asteroid.set_meta("vertices_3d", vertices_3d)
		new_asteroid.set_meta("edges", edges)
		new_asteroid.set_meta("velocity", new_velocity)
		new_asteroid.set_meta("original_velocity", new_velocity)
		new_asteroid.set_meta("rotation", Vector3.ZERO)
		new_asteroid.set_meta("angular_velocity", Vector3(
			randf_range(-rotation_speed, rotation_speed),
			randf_range(-rotation_speed, rotation_speed),
			randf_range(-rotation_speed, rotation_speed)
		))
		new_asteroid.set_meta("radius", 15.0 * data.scale_factor)
		new_asteroid.set_meta("hp", data.hp)
		new_asteroid.set_meta("size_tier", data.tier)
		new_asteroid.set_meta("is_vibrating", false)
		new_asteroid.set_meta("vibrate_timer", 0.0)
		add_child(new_asteroid)
		enemies.append(new_asteroid)
	
	spawn_split_particles(parent_position, parent_velocity)

func spawn_split_particles(position: Vector2, parent_velocity: Vector2):
	var explosion = CPUParticles2D.new()
	explosion.emitting = true
	explosion.amount = 30
	explosion.lifetime = 0.6
	explosion.one_shot = true
	explosion.explosiveness = 0.9
	explosion.initial_velocity_min = 300.0
	explosion.initial_velocity_max = 700.0
	explosion.spread = 180.0
	explosion.gravity = Vector2.ZERO
	explosion.scale_amount_min = 1.0
	explosion.scale_amount_max = 3.0
	explosion.color = Color(1.0, 0.5, 0.0, 1.0)
	explosion.position = position
	add_child(explosion)
	var timer = get_tree().create_timer(explosion.lifetime)
	timer.timeout.connect(func(): if is_instance_valid(explosion): explosion.queue_free())
	
	for i in range(4):
		var debris = Node2D.new()
		var shape = generate_asteroid_shape(0.3)
		var line = Line2D.new()
		line.width = 0.5
		line.default_color = Color(1, 0.2, 0.2, 0.7)
		for edge in shape.edges:
			line.add_point(Vector2(shape.vertices[edge[0]].x, shape.vertices[edge[0]].y))
			line.add_point(Vector2(shape.vertices[edge[1]].x, shape.vertices[edge[1]].y))
		debris.add_child(line)
		debris.position = position + Vector2(randf_range(-5.0, 5.0), randf_range(-5.0, 5.0))
		var debris_velocity = parent_velocity + Vector2(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0)).normalized() * randf_range(400.0, 800.0)
		debris.set_meta("velocity", debris_velocity)
		debris.set_meta("lifetime", randf_range(0.8, 1.5))
		debris.set_meta("initial_lifetime", debris.get_meta("lifetime"))
		add_child(debris)

func update_score_label():
	if score_label:
		var score_text = "Score: " + str(score)

		# Only show points needed if a laser is present
		if lasers.size() > 0:
			var next_required_score = null
			for laser in lasers:
				var req = laser.get_meta("required_score", 0)
				if req > score and (next_required_score == null or req < next_required_score):
					next_required_score = req
			if next_required_score == null:
				# fallback: show the first laser's threshold if none are active (shouldn't happen)
				next_required_score = SCORE_THRESHOLD_FOR_SAFE_PASSAGE
			var points_needed = max(0, next_required_score - score)
			score_text += "\nPoints needed: " + str(points_needed)

		# Add power-up status
		for type in active_double_power_ups:
			score_text += "\n" + DOUBLE_POWER_TYPES[type].symbol + ": " + str(int(active_double_power_ups[type])) + "s"

		score_label.text = score_text

		# Ensure the label stays within screen bounds
		var label_size = score_label.get_rect().size
		score_label.position.x = min(score_label.position.x, viewport_size.x - label_size.x - 30)

func _process(delta):
	if current_state == GameState.PAUSED:
		return
	
	# Remove the noisy per-frame debug print for now
	background.size = get_viewport_rect().size

	# Update music UI if necessary
	if music_menu_container and music_menu_container.visible:
		# Update pause button in case playback state changed externally
		update_pause_button()
		
		# Update song label
		var song_label = music_menu_container.get_node_or_null("SongLabel")
		if song_label:
			song_label.text = "Now playing:\n" + music_files[current_track].get_file()

	# DEBUG: Draw lines at the top and bottom gameplay margins
	# Remove this debug visualization code completely
	if has_node("DebugLineTop"):
		var debug_line_top = get_node("DebugLineTop")
		debug_line_top.queue_free()
	
	if has_node("DebugLineBottom"):
		var debug_line_bottom = get_node("DebugLineBottom")
		debug_line_bottom.queue_free()

	# DEBUG: Print viewport size and player ship position every 1 second
	var _debug_timer: float = 0.0
	_debug_timer += delta
	if _debug_timer > 1.0:
		# Comment out debug prints
		# print("[DEBUG] viewport_size type: ", typeof(viewport_size), " value: ", viewport_size)
		# print("[DEBUG] player_ship type: ", typeof(player_ship), " value: ", player_ship)
		# if player_ship:
		#    print("[DEBUG] Player ship position: ", player_ship.position)
		# else:
		#    print("[DEBUG] Player ship is null")
		# print("[DEBUG] SHIP_MARGIN: ", SHIP_MARGIN)
		_debug_timer = 0.0



	disco_ball_container.rotation += 0.2 * delta

	shimmer_timer += delta
	for i in range(grid_lines.size()):
		var line = grid_lines[i] as Line2D
		var shimmer = sin(shimmer_timer * 4.0 + i * 0.5) * 0.5 + 0.5
		line.default_color = Color(1, 1, 1, shimmer)

	if not spectrum:
		return

	var capture = AudioServer.get_bus_effect(0, 1) as AudioEffectCapture
	if not capture:
		return

	var kick = spectrum.get_magnitude_for_frequency_range(50.0, 500.0).length()
	var hi_hat = spectrum.get_magnitude_for_frequency_range(1000.0, 4000.0).length()
	var mid_freq = spectrum.get_magnitude_for_frequency_range(500.0, 1000.0).length()
	var viewport_size = get_viewport_rect().size
	var center = viewport_size / 2


	starfield.position = project_3d_to_2d(camera_position, viewport_size, center)
	starfield.modulate.a = clamp(0.5 + mid_freq, 0.2, 1.0)
	starfield.speed_scale = 1.0 + hi_hat * 2.0
	starfield.amount = int(lerp(100, 500, kick))

	for child in get_children():
		if child.has_meta("lifetime"):
			var lifetime = child.get_meta("lifetime") - delta
			child.set_meta("lifetime", lifetime)
			if lifetime <= 0:
				child.queue_free()
			else:
				var debris_velocity = child.get_meta("velocity", Vector2.ZERO)
				child.position += debris_velocity * delta
				var line = child.get_child(0)
				var initial_lifetime = child.get_meta("initial_lifetime", 1.0)
				line.modulate.a = lifetime / initial_lifetime
				var vertices_3d = child.get_meta("vertices_3d", [])
				var edges = child.get_meta("edges", [])
				var rotation = child.get_meta("rotation", Vector3.ZERO)
				var angular_velocity = child.get_meta("angular_velocity", Vector3.ZERO)
				rotation += angular_velocity * delta
				child.set_meta("rotation", rotation)
				var vertices_2d = []
				var yaw_matrix = Basis(Vector3(0, 1, 0), rotation.y)
				var pitch_matrix = Basis(Vector3(1, 0, 0), rotation.x)
				var roll_matrix = Basis(Vector3(0, 0, 1), rotation.z)
				var transform = yaw_matrix * pitch_matrix * roll_matrix
				for vertex in vertices_3d:
					var rotated_vertex = transform * vertex
					vertices_2d.append(Vector2(rotated_vertex.x, rotated_vertex.y))
				line.clear_points()
				for edge in edges:
					line.add_point(vertices_2d[edge[0]])
					line.add_point(vertices_2d[edge[1]])

	var bass = spectrum.get_magnitude_for_frequency_range(20.0, 200.0).length()
	var mid = spectrum.get_magnitude_for_frequency_range(200.0, 4000.0).length()
	var high = spectrum.get_magnitude_for_frequency_range(4000.0, 20000.0).length()
	var music_buffer = capture.get_buffer(512)
	var avg_amplitude = 0.0
	for sample in music_buffer:
		avg_amplitude += abs(sample.x)
	avg_amplitude = clamp(avg_amplitude / 512.0, 0.0, 1.0) * 2.0

	for asteroid in asteroids:
		asteroid.position += asteroid.move_velocity * delta
		asteroid.rotation += asteroid.angular_velocity * delta
		var rotated_vertices = []
		var yaw_matrix = Basis(Vector3(0, 1, 0), deg_to_rad(-camera_yaw + asteroid.rotation.y))
		var pitch_matrix = Basis(Vector3(1, 0, 0), deg_to_rad(-camera_pitch + asteroid.rotation.x))
		var roll_matrix = Basis(Vector3(0, 0, 1), deg_to_rad(-camera_roll + asteroid.rotation.z))
		var transform = yaw_matrix * pitch_matrix * roll_matrix
		for vertex in asteroid.vertices:
			var relative_pos = transform * vertex
			var world_pos = relative_pos + asteroid.position - camera_position
			rotated_vertices.append(project_3d_to_2d(world_pos, viewport_size, center))
		var line = asteroid.line_node
		line.clear_points()
		for edge in asteroid.edges:
			var v1 = rotated_vertices[edge[0]]
			var v2 = rotated_vertices[edge[1]]
			if v1 != Vector2(-1000, -1000) and v2 != Vector2(-1000, -1000):
				line.add_point(v1)
				line.add_point(v2)

	for star in stars:
		var star_type = star.get_meta("type", "main")
		var pos_3d = star.get_meta("pos_3d")
		var relative_pos = pos_3d - camera_position
		var depth_factor = (Z_FAR - relative_pos.z) / (Z_FAR - Z_NEAR)
		depth_factor = clamp(depth_factor, 0.0, 1.0)
		var parallax_speed = lerp(PARALLAX_SPEED_MIN, PARALLAX_SPEED_MAX, depth_factor)
		relative_pos.z -= parallax_speed * delta
		var yaw_matrix_star = Basis(Vector3(0, 1, 0), deg_to_rad(-camera_yaw))
		var pitch_matrix_star = Basis(Vector3(1, 0, 0), deg_to_rad(-camera_pitch))
		var roll_matrix_star = Basis(Vector3(0, 0, 1), deg_to_rad(-camera_roll))
		relative_pos = (yaw_matrix_star * pitch_matrix_star * roll_matrix_star) * relative_pos
		if (pos_3d - camera_position).length() > Z_FAR:
			pos_3d = camera_position + get_random_spherical_position(Z_FAR)
		star.position = project_3d_to_2d(relative_pos, viewport_size, center)
		var scale = clamp((Z_FAR - relative_pos.z) / (Z_FAR - Z_NEAR), 0.0, 1.0)
		if star_type == "main":
			# White, twinkling only
			star.color = Color(1, 1, 1)
			var twinkle_amount = sin(Time.get_ticks_msec() * 0.005 + randf_range(0, 2 * PI)) * 0.3
			star.color.a = clamp(lerp(0.3, 1.0, scale) + twinkle_amount, 0.1, 1.0)
			var base_size = (STAR_MIN_SIZE + STAR_MAX_SIZE) / 2.0
			star.size = Vector2(base_size, base_size) * (0.8 + twinkle_amount * 0.2)
		else:
			# Accent: audio-reactive
			var base_color = star.get_meta("base_color", Color(1,1,1,1))
			star.color = base_color.lerp(Color(0,0,0), 1.0 - scale)
			if current_visual_profile:
				match current_visual_profile.reactivity:
					"pulse":
						if kick > 0.1:
							var base_accent_size = 10.0
							var pulse_size = base_accent_size + kick * (ACCENT_STAR_MAX_SIZE - base_accent_size)
							pulse_size = clamp(pulse_size, base_accent_size, ACCENT_STAR_MAX_SIZE)
							star.size = Vector2(pulse_size, pulse_size)
							star.color = star.color.lightened(kick * 0.5)
						else:
							star.size = Vector2(8.0, 8.0)
					"color_shift":
						if mid_freq > 0.01:
							star.color = star.color.lerp(Color(1,1,1), mid_freq)
			# Twinkle for accent stars too
			var twinkle_pulse = randf_range(0.4, 0.8) if hi_hat > 0.02 else 0.0
			var twinkle_amount = sin(Time.get_ticks_msec() * 0.005 + randf_range(0, 2 * PI)) * 0.3
			star.color.a = clamp(lerp(0.3, 1.0, scale) + twinkle_amount + twinkle_pulse, 0.1, 1.0)
		star.set_meta("pos_3d", pos_3d)

	match current_state:
		GameState.MENU:
			pass

		GameState.GAME_LOOP:
			player_stats["time_played"] += delta
			game_time += delta
			update_difficulty()  # Update difficulty each frame
			
			# Update combo timer
			if current_combo > 0:
				combo_timer -= delta
				if combo_timer <= 0:
					current_combo = 0
					# Show combo end effect
					var combo_end = create_combo_text(Vector2(viewport_size.x / 2, viewport_size.y / 2), 0)
					combo_end.get_child(0).get_child(0).text = "COMBO ENDED!"
					add_child(combo_end)

			# Update combo UI
			if combo_container and combo_fill and combo_label:
				# Check for combo changes
				if current_combo != last_combo:
					if current_combo > last_combo:
						# Combo increased - add impact effect
						combo_counter.scale = Vector2(1.5, 1.5)
						var tween = create_tween()
						tween.tween_property(combo_counter, "scale", Vector2(1, 1), 0.2).set_ease(Tween.EASE_OUT)
						
						# Flash the meter
						combo_fill.modulate = Color(2, 2, 2)
						tween.parallel().tween_property(combo_fill, "modulate", Color(1, 1, 1), 0.3)
						
						# Reset timer fill position
						combo_timer_fill.set_point_position(0, Vector2(0, METER_HEIGHT))
						combo_timer_fill.set_point_position(1, Vector2(0, METER_HEIGHT))
						combo_drain_effect = false
					last_combo = current_combo

				# Update meter fill
				var fill_height = (float(current_combo) / MAX_COMBO) * METER_HEIGHT
				combo_fill.set_point_position(0, Vector2(0, METER_HEIGHT))
				combo_fill.set_point_position(1, Vector2(0, METER_HEIGHT - fill_height))
				
				# Update timer drain effect
				if current_combo > 0:
					var time_ratio = clamp(combo_timer / COMBO_TIMEOUT, 0.0, 1.0)
					var timer_height = fill_height * time_ratio
					combo_timer_fill.set_point_position(0, Vector2(0, METER_HEIGHT))
					combo_timer_fill.set_point_position(1, Vector2(0, METER_HEIGHT - timer_height))
					# Update timer fill color based on remaining time
					var warning_color = Color(1, 0, 0, 0.4)  
					var normal_color = Color(1, 1, 1, 0.3)  
					combo_timer_fill.default_color = normal_color.lerp(warning_color, 1.0 - time_ratio)
				else:
					combo_timer_fill.set_point_position(0, Vector2(0, METER_HEIGHT))
					combo_timer_fill.set_point_position(1, Vector2(0, METER_HEIGHT))
					combo_drain_effect = false

				# Update counter and multiplier
				combo_counter.text = str(current_combo)
				var current_multiplier = 1.0
				var current_color = Color(1, 1, 1)
				
				# Find current multiplier and color
				for segment in COMBO_SEGMENTS:
					if current_combo >= segment.threshold:
						current_multiplier = segment.multiplier
						current_color = segment.color
				
				combo_label.text = "x" + str(current_multiplier)
				
				# Add pulsing effect when combo is active
				if current_combo > 0:
					combo_pulse_timer += delta * COMBO_PULSE_SPEED
					var pulse = sin(combo_pulse_timer) * 0.2 + 0.8
					
					# Pulse the fill color
					combo_fill.default_color = current_color
					combo_fill.modulate = Color(1, 1, 1, pulse)
					
					# Update counter color and effect
					combo_counter.add_theme_color_override("font_color", current_color)
					combo_label.add_theme_color_override("font_color", current_color)
					
					# Make the counter pulse slightly
					var counter_pulse = sin(combo_pulse_timer * 2) * 0.1 + 1.0
					combo_counter.scale = Vector2(counter_pulse, counter_pulse)
					
					# Add urgency effect when combo timer is low
					if combo_timer < COMBO_TIMEOUT * 0.3:  # Last 30% of time
						var urgency_pulse = sin(combo_pulse_timer * 8) * 0.3 + 0.7
						combo_counter.modulate.a = urgency_pulse
						combo_label.modulate.a = urgency_pulse
					else:
						combo_counter.modulate.a = 1.0
						combo_label.modulate.a = 1.0
					
					# Update segment visibility
					for i in range(combo_segments.size()):
						var segment = combo_segments[i]
						var threshold = COMBO_SEGMENTS[i].threshold
						if current_combo >= threshold:
							# Make passed thresholds glow
							var segment_pulse = sin(combo_pulse_timer * 2 + i) * 0.3 + 0.7
							segment.default_color = COMBO_SEGMENTS[i].color
							segment.modulate.a = segment_pulse
						else:
							segment.default_color = COMBO_SEGMENTS[i].color.darkened(0.7)
							segment.modulate.a = 0.5
					
					# Add screen shake for high combos
					if current_combo >= MAX_COMBO * 0.7:
						var shake = sin(combo_pulse_timer * 4) * 2
						combo_container.position.x = METER_PADDING + shake
				else:
					# Reset everything when no combo
					combo_fill.default_color = Color(0.5, 0.5, 0.5)
					combo_counter.add_theme_color_override("font_color", Color(0.5, 0.5, 0.5))
					combo_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.5))
					combo_counter.scale = Vector2(1, 1)
					combo_counter.modulate.a = 1.0
					combo_label.modulate.a = 1.0
					combo_container.position.x = METER_PADDING
					for segment in combo_segments:
						segment.modulate.a = 0.3

			max_enemies = 8 + int(current_difficulty * 4)  # More aggressive scaling
			
			camera_position.x += current_speed * delta
			camera_position.z += current_speed * delta
			camera_yaw = 0.0
			
			var input_dir = Vector2.ZERO
			
			# Combine keyboard and virtual joystick input
			if Input.is_action_pressed("ui_up"):
				input_dir.y = -1
			if Input.is_action_pressed("ui_down"):
				input_dir.y = 1
			if Input.is_action_pressed("ui_left"):
				input_dir.x = -1
			if Input.is_action_pressed("ui_right"):
				input_dir.x = 1
				
			# Add joystick input if available
			if joystick_active and joystick_direction != Vector2.ZERO:
				input_dir = joystick_direction
			
			var target_velocity = input_dir.normalized() * MAX_SHIP_SPEED
			ship_velocity = ship_velocity.lerp(target_velocity, ACCELERATION * delta)
			
			player_ship.position += ship_velocity * delta
			# Use full viewport size with a small margin for the ship's size
			player_ship.position.x = clamp(player_ship.position.x, SHIP_MARGIN, viewport_size.x - SHIP_MARGIN)
			player_ship.position.y = clamp(player_ship.position.y, SHIP_MARGIN, viewport_size.y - SHIP_MARGIN)
			
			# Update distance calculations to use ship margin instead of fixed bounds
			var distance_to_left = player_ship.position.x - SHIP_MARGIN
			var distance_to_right = (viewport_size.x - SHIP_MARGIN) - player_ship.position.x
			var distance_to_top = player_ship.position.y - SHIP_MARGIN
			var distance_to_bottom = (viewport_size.y - SHIP_MARGIN) - player_ship.position.y
			var tilt_reduction_range = 50.0
			var tilt_reduction_factor_x = min(
				clamp(distance_to_left / tilt_reduction_range, 0.0, 1.0),
				clamp(distance_to_right / tilt_reduction_range, 0.0, 1.0)
			)
			var tilt_reduction_factor_y = min(
				clamp(distance_to_top / tilt_reduction_range, 0.0, 1.0),
				clamp(distance_to_bottom / tilt_reduction_range, 0.0, 1.0)
			)
			var adjusted_max_tilt_angle = MAX_TILT_ANGLE
			if input_dir.y != 0:
				adjusted_max_tilt_angle = lerp(0.2, MAX_TILT_ANGLE, tilt_reduction_factor_y)
			if input_dir.x != 0:
				tilt_timer += TILT_INCREASE_RATE * delta
				tilt_timer = clamp(tilt_timer, 0.0, (adjusted_max_tilt_angle - TILT_ANGLE) / TILT_INCREASE_RATE)
			else:
				tilt_timer -= TILT_INCREASE_RATE * delta * 2.0
				tilt_timer = max(tilt_timer, 0.0)
			var current_tilt_angle = TILT_ANGLE + (tilt_timer * TILT_INCREASE_RATE)
			current_tilt_angle = min(current_tilt_angle, adjusted_max_tilt_angle)
			var tilt = input_dir.x * current_tilt_angle - input_dir.y * current_tilt_angle * 0.5
			player_ship.rotation = lerp(player_ship.rotation, BASE_SHIP_ROTATION + tilt, 10.0 * delta)

			laser_spawn_timer += delta
			if laser_spawn_timer >= LASER_SPAWN_INTERVAL:
				var laser = create_laser()
				add_child(laser)
				lasers.append(laser)
				laser_spawn_timer -= LASER_SPAWN_INTERVAL

			# Update lasers with more informative labels
			for laser_node in lasers.duplicate():
				var velocity = laser_node.get_meta("velocity")
				var required_score = laser_node.get_meta("required_score")
				var points_needed = max(0, required_score - score)
				
				# Apply vector flicker effect
				var flicker = 1.0
				if VECTOR_FLICKER_INTENSITY > 0:
					flicker = randf_range(1.0 - VECTOR_FLICKER_INTENSITY, 1.0 + VECTOR_FLICKER_INTENSITY)
				
				# Get the lines - try with node name first, fall back to index
				var main_line = laser_node.get_node_or_null("MainLine")
				if not main_line:
					main_line = laser_node.get_child(0) as Line2D
				
				var glow_line = laser_node.get_node_or_null("GlowLine") as Line2D
				
				# Get label container (should be after the line nodes)
				var label_child_index = 1
				if glow_line:
					label_child_index = 2
				var label_container = laser_node.get_child(label_child_index) as Control
				
				# The points_label is now the second child of the container (after the panel)
				var points_label = label_container.get_child(1) as Label
				
				if score >= required_score:
					if not laser_node.get_meta("is_safe", false):
						# First time turning green
						if main_line:
							main_line.default_color = Color(0, 1, 0)
						if glow_line:
							glow_line.default_color = Color(0, 1, 0, VECTOR_GLOW_ALPHA)
						
						if points_label:  # Add null check
							points_label.text = "SAFE"
						laser_node.set_meta("is_safe", true)
						# Play laser safe sound
						if laser_safe_sound:
							laser_safe_sound.play()
						# Set to faster speed
						laser_node.set_meta("velocity", Vector2(0, 400.0))
						# Start fade out timer
						laser_node.set_meta("fade_timer", 2.5)
				elif score < required_score:
					# Show red laser with points needed and percentage
					if main_line:
						main_line.default_color = Color(1, 0, 0)
					if glow_line:
						glow_line.default_color = Color(1, 0, 0, VECTOR_GLOW_ALPHA)
						
					var progress = int((float(score) / required_score) * 100)
					if points_label:  # Add null check
						points_label.text = str(points_needed) + " more (" + str(progress) + "%)"

				# Update position with current velocity
				laser_node.position += laser_node.get_meta("velocity") * delta

				# Fade out green lasers
				if laser_node.get_meta("is_safe", false):
					var fade_timer = laser_node.get_meta("fade_timer", 1.0)
					fade_timer -= delta
					laser_node.set_meta("fade_timer", fade_timer)
					
					var fade_alpha = clamp(fade_timer, 0.0, 1.0)
					if main_line:
						main_line.modulate.a = fade_alpha * flicker
					if glow_line:
						glow_line.modulate.a = fade_alpha * flicker
					
					label_container.modulate.a = fade_alpha
					if fade_timer <= 0.0:
						# Increment lasers cleared
						ensure_player_stats_keys()
						player_stats["lasers_cleared"] += 1
						save_player_stats()
						laser_node.queue_free()
						lasers.erase(laser_node)
						continue

				# Collision check using center hitbox for lasers
				if not laser_node.get_meta("is_safe", false):
					var ship_center = get_ship_center_hitbox()
					var laser_poly = get_laser_polygon(laser_node)
					if polygons_intersect(ship_center, laser_poly):
						print("Collision with laser at position: ", laser_node.position, " | type: ", "SAFE" if laser_node.get_meta("is_safe", false) else "UNSAFE")
						is_game_over = true
						# Play game over sound
						if asteroid_spawn_sound:
							asteroid_spawn_sound.play()
						current_state = GameState.GAME_OVER
						update_state_visuals()
						break

				# Cleanup off-screen lasers (bottom)
				if laser_node.position.y > viewport_size.y + 50:
					laser_node.queue_free()
					lasers.erase(laser_node)

			# Reset laser count when game over or returning to menu
			if is_game_over or current_state == GameState.MENU:
				current_laser_count = 0

			# Update chaser (left laser)
			if current_state == GameState.GAME_LOOP:
				# Apply vector flicker effect
				var chaser_flicker = 1.0
				if VECTOR_FLICKER_INTENSITY > 0:
					chaser_flicker = randf_range(1.0 - VECTOR_FLICKER_INTENSITY, 1.0 + VECTOR_FLICKER_INTENSITY)
				
				# Get the lines - try with node name first, fall back to index
				var main_line = chaser.get_node_or_null("MainLine")
				if not main_line:
					main_line = chaser.get_child(0) as Line2D
				
				var glow_line = chaser.get_node_or_null("GlowLine") as Line2D
				
				# Get label container (should be after the line nodes)
				var label_child_index = 1
				if glow_line:
					label_child_index = 2
				var label_container = chaser.get_child(label_child_index) as Control
				var points_label = label_container.get_child(1) as Label
				
				if score >= BASE_LASER_THRESHOLD:
					if not chaser.get_meta("is_safe", false):
						if main_line:
							main_line.default_color = Color(0, 1, 0)
						if glow_line:
							glow_line.default_color = Color(0, 1, 0, VECTOR_GLOW_ALPHA)
						
						if points_label:  # Add null check
							points_label.text = "GOAL REACHED!"
						chaser.set_meta("is_safe", true)
						# Play laser safe sound
						if laser_safe_sound:
							laser_safe_sound.play()
						# Set to faster speed downward
						chaser.set_meta("velocity", Vector2(0, 400.0))
				else:
					if main_line:
						main_line.default_color = Color(1, 0, 0)
					if glow_line:
						glow_line.default_color = Color(1, 0, 0, VECTOR_GLOW_ALPHA)
					
					if points_label:  # Add null check
						points_label.text = "Goal: " + str(BASE_LASER_THRESHOLD) + " points"
				
				# Apply flicker to both lines
				if main_line and VECTOR_FLICKER_INTENSITY > 0:
					main_line.modulate.a = chaser_flicker
				if glow_line and VECTOR_FLICKER_INTENSITY > 0:
					glow_line.modulate.a = chaser_flicker
				
				# Update position with current velocity
				chaser.position += chaser.get_meta("velocity") * delta
				
				# No collision check for the chaser laser - it's just a visual guide

			# Update power-ups
			update_double_power_ups(delta)
			
			# Spawn power-ups
			double_power_spawn_timer += delta
			if double_power_spawn_timer >= DOUBLE_POWER_SPAWN_INTERVAL:
				var x_pos = randf_range(SHIP_MARGIN, viewport_size.x - SHIP_MARGIN)
				var power_up = create_double_power_up("DOUBLE_POWER", x_pos)
				add_child(power_up)
				double_power_spawn_timer = 0.0
			
			# Update existing power-ups
			for child in get_children():
				if child.has_meta("type"):  # This is a power-up
					var velocity = child.get_meta("velocity")
					child.position += velocity * delta
					
					# Check collision with player
					if child.position.distance_to(player_ship.position) < 30:
						apply_double_power_up(child.get_meta("type"))
						child.queue_free()
					
					# Remove if off screen (bottom)
					if child.position.y > viewport_size.y + 50:
						child.queue_free()

			spawn_timer += delta
			if spawn_timer >= enemy_spawn_interval:
				print('Spawning enemy, current enemies:', enemies.size(), 'max_enemies:', max_enemies)
				if randf() < 0.3:
					spawn_enemy()
				else:
					spawn_enemy_wave()
				spawn_timer -= enemy_spawn_interval

			if not is_game_over:
				distance_score_timer += delta
				if distance_score_timer >= DISTANCE_SCORE_INTERVAL:
					score += DISTANCE_SCORE_AMOUNT
					distance_score_timer -= DISTANCE_SCORE_INTERVAL
					update_score_label()

			# Update collision checks
			if not is_game_over:
				var ship_poly = get_ship_polygon()
				for enemy in enemies:
					var asteroid_poly = get_asteroid_polygon(enemy)
					if polygons_intersect(ship_poly, asteroid_poly):
						print("Collision with asteroid at position: ", enemy.position, " | vertices: ", enemy.get_meta("vertices_3d", []))
						is_game_over = true
						# Play game over sound
						if asteroid_spawn_sound:
							asteroid_spawn_sound.play()
						current_state = GameState.GAME_OVER
						update_state_visuals()
						break

			for enemy in enemies:
				var velocity = enemy.get_meta("velocity", Vector2(-150, 0))
				var vibrate_offset = vibrate_asteroid(enemy, delta)
				enemy.position += velocity * delta + vibrate_offset
				
				# Handle regeneration for negative asteroids
				if enemy.get_meta("is_negative", false) and enemy.get_meta("is_regenerating", false):
					var regen_timer = enemy.get_meta("regen_timer", 0.0)
					if regen_timer > 0:
						regen_timer -= delta
						enemy.set_meta("regen_timer", regen_timer)
						
						# Visual feedback during regeneration
						var line = enemy.get_child(1) as Line2D
						if line:
							var pulse = (sin(Time.get_ticks_msec() * 0.01) + 1.0) / 2.0
							line.default_color = Color(1, 0, 0).lerp(Color(1, 1, 1), pulse)
						
						if regen_timer <= 0:
							# Restore original state
							enemy.set_meta("hp", enemy.get_meta("original_hp"))
							enemy.set_meta("vertices_3d", enemy.get_meta("original_vertices_3d").duplicate(true))
							enemy.set_meta("edges", enemy.get_meta("original_edges").duplicate(true))
							enemy.set_meta("faces", enemy.get_meta("original_faces").duplicate(true))
							enemy.set_meta("is_regenerating", false)
							
							# Visual feedback for regeneration
							var particles = CPUParticles2D.new()
							particles.emitting = true
							particles.amount = 20
							particles.lifetime = 0.5
							particles.one_shot = true
							particles.explosiveness = 0.8
							particles.direction = Vector2(0, -1)
							particles.spread = 180.0
							particles.initial_velocity_min = 100
							particles.initial_velocity_max = 200
							particles.scale_amount_min = 2.0
							particles.scale_amount_max = 4.0
							particles.color = Color(1, 1, 1)  # White particles for regeneration
							particles.position = enemy.position
							add_child(particles)
							
							if line:
								line.default_color = Color(1, 1, 1)  # Stay white after regeneration
		
				# Update asteroid rendering
				var vertices_3d = enemy.get_meta("vertices_3d", [])
				var edges = enemy.get_meta("edges", [])
				var rotation = enemy.get_meta("rotation", Vector3.ZERO)
				var angular_velocity = enemy.get_meta("angular_velocity", Vector3.ZERO)
				rotation += angular_velocity * delta
				enemy.set_meta("rotation", rotation)
				var vertices_2d = []
				var vertices_transformed = []
				var yaw_matrix = Basis(Vector3(0, 1, 0), rotation.y)
				var pitch_matrix = Basis(Vector3(1, 0, 0), rotation.x)
				var roll_matrix = Basis(Vector3(0, 0, 1), rotation.z)
				var transform = yaw_matrix * pitch_matrix * roll_matrix
				for vertex in vertices_3d:
					var rotated_vertex = transform * vertex
					vertices_2d.append(Vector2(rotated_vertex.x, rotated_vertex.y))
					vertices_transformed.append(rotated_vertex)
				
				var scale_factor = enemy.get_meta("radius", 15.0) / 15.0
				var base_line_width = enemy.get_meta("line_width", 1.0)
				
				# Add vector flicker effect - slight random variation in brightness
				var flicker = 1.0
				if VECTOR_FLICKER_INTENSITY > 0:
					flicker = randf_range(1.0 - VECTOR_FLICKER_INTENSITY, 1.0 + VECTOR_FLICKER_INTENSITY)
				
				# Check if enemy has glow effect
				var has_glow = enemy.get_meta("has_glow", VECTOR_GLOW_ENABLED)
				
				# Update glow line if it exists (should be second child, index 1)
				if has_glow:
					var glow_line = enemy.get_node_or_null("GlowLine") as Line2D
					if glow_line:
						glow_line.clear_points()
						for edge in edges:
							var v1_3d = vertices_transformed[edge[0]]
							var v2_3d = vertices_transformed[edge[1]]
							var z_avg = (v1_3d.z + v2_3d.z) / 2.0
							var depth_factor = clamp((z_avg + 15.0 * scale_factor) / (30.0 * scale_factor), 0.5, 2.0)
							glow_line.width = base_line_width * depth_factor * VECTOR_GLOW_WIDTH_MULTIPLIER
							
							# Only update alpha if it's not a negative asteroid that has regenerated
							if not (enemy.get_meta("is_negative", false) and not enemy.get_meta("is_regenerating", false)):
								var alpha = VECTOR_GLOW_ALPHA * depth_factor * flicker
								var current_color = glow_line.default_color
								glow_line.default_color = Color(current_color.r, current_color.g, current_color.b, alpha)
							
							glow_line.add_point(vertices_2d[edge[0]])
							glow_line.add_point(vertices_2d[edge[1]])
				
				# Get the main line and update it (should be third child, index 2 if glow exists, or 1 if no glow)
				var line = enemy.get_node_or_null("MainLine") as Line2D
				if line:
					line.clear_points()
					for edge in edges:
						var v1_3d = vertices_transformed[edge[0]]
						var v2_3d = vertices_transformed[edge[1]]
						var z_avg = (v1_3d.z + v2_3d.z) / 2.0
						var depth_factor = clamp((z_avg + 15.0 * scale_factor) / (30.0 * scale_factor), 0.5, 2.0)
						line.width = base_line_width * depth_factor
						
						# Only update alpha if it's not a negative asteroid that has regenerated
						if not (enemy.get_meta("is_negative", false) and not enemy.get_meta("is_regenerating", false)):
							var base_alpha = depth_factor * flicker
							var current_color = line.default_color
							line.default_color = Color(current_color.r, current_color.g, current_color.b, base_alpha)
						
						line.add_point(vertices_2d[edge[0]])
						line.add_point(vertices_2d[edge[1]])
				
				# Update the label position (first child)
				var label_container = enemy.get_child(0) as Control
				if label_container:
					label_container.position = Vector2(-label_container.size.x / 2, -label_container.size.y / 2)
				
				if enemy.position.x < -50 or enemy.position.y > viewport_size.y + 50:
					# Clean up sound player from dictionary
					asteroid_sound_players.erase(enemy.get_instance_id())
					enemy.queue_free()
					if enemy in enemies:
						enemies.erase(enemy)
					print('Enemy removed, enemies left:', enemies.size())

			coin_spawn_timer += delta
			if coin_spawn_timer >= COIN_SPAWN_INTERVAL:
				var x_pos = randf_range(SHIP_MARGIN, viewport_size.x - SHIP_MARGIN)
				var coin = create_coin(x_pos)
				coins.append(coin)
				coin_spawn_timer -= COIN_SPAWN_INTERVAL

			for coin in coins.duplicate():
				var coin_velocity = coin.get_meta("velocity", Vector2(0, COIN_SPEED))
				coin.position += coin_velocity * delta
				var distance = player_ship.position.distance_to(coin.global_position)
				var coin_radius = coin.get_meta("radius", COIN_RADIUS)
				if distance < (SHIP_RADIUS + coin_radius):
					# Play point sound when collecting coins
					if point_sound:
						point_sound.play()
					
					# Apply 2x multiplier to coin value if active
					var coin_value = COIN_SCORE_VALUE * (2 if "DOUBLE_POWER" in active_double_power_ups else 1)
					score += coin_value
					update_score_label()
					
					# Create floating score effect for coins too
					var floating_score = create_floating_score(coin.global_position, coin_value, false)
					add_child(floating_score)
					
					coin.queue_free()
					coins.erase(coin)
					# Increment coins collected
					ensure_player_stats_keys()
					player_stats["coins_collected"] += coin_value
					save_player_stats()
				elif coin.position.y > viewport_size.y + 50:
					coin.queue_free()
					coins.erase(coin)

			if not is_game_over:
				update_score_label()

			# Shooting mechanics - remove auto-fire logic
			firing_timer -= delta

			# Update bullets
			for bullet in bullets.duplicate():
				bullet.node.position += bullet.velocity * delta
				for enemy in enemies:
					# Use vertical distance-based collision for bullets
					var distance = bullet.node.position.distance_to(enemy.position)
					var hit_radius = enemy.get_meta("radius", 15.0)
					if distance < hit_radius:
						flash_asteroid(enemy)
						enemy.set_meta("is_vibrating", true)
						enemy.set_meta("vibrate_timer", 0.3)
						slow_asteroid_velocity(enemy)
						flake_asteroid(enemy, bullet.node.global_position)
						if not enemy.get_meta("is_negative", false):
							current_combo = min(current_combo + 1, MAX_COMBO)
							combo_timer = COMBO_TIMEOUT
						bullet.node.queue_free()
						bullets.erase(bullet)
						break
				if bullet.node.position.y < -50:
					bullet.node.queue_free()
					bullets.erase(bullet)

		GameState.TEST:
			var input_velocity = Vector3.ZERO
			if Input.is_action_pressed("ui_right"): input_velocity.x += 1.0
			if Input.is_action_pressed("ui_left"): input_velocity.x -= 1.0
			if Input.is_action_pressed("ui_up"): input_velocity.z += 1.0
			if Input.is_action_pressed("ui_down"): input_velocity.z -= 1.0
			if Input.is_action_pressed("ui_select"): input_velocity.z += 2.0
			if Input.is_action_pressed("roll_left"):
				camera_roll += ROLL_SPEED * delta
			if Input.is_action_pressed("roll_right"):
				camera_roll -= ROLL_SPEED * delta
			var yaw_rad = deg_to_rad(camera_yaw)
			var pitch_rad = deg_to_rad(camera_pitch)
			var forward = Vector3(sin(yaw_rad) * cos(pitch_rad), -sin(pitch_rad), cos(yaw_rad) * cos(pitch_rad)).normalized()
			var right = Vector3(cos(yaw_rad), 0, -sin(yaw_rad)).normalized()
			var up = forward.cross(right).normalized()
			var roll_matrix = Basis(forward, deg_to_rad(camera_roll))
			right = roll_matrix * right
			up = roll_matrix * up
			var target_velocity = (forward * input_velocity.z + right * input_velocity.x + up * input_velocity.y) * current_speed
			velocity = velocity.lerp(target_velocity, ACCELERATION * delta)
			if input_velocity == Vector3.ZERO:
				drag_delay += delta
				if drag_delay >= DRAG_DELAY_TIME and velocity.length() > MIN_VELOCITY_THRESHOLD:
					velocity = velocity.lerp(Vector3.ZERO, DECELERATION * delta)
				elif drag_delay >= DRAG_DELAY_TIME and velocity.length() <= MIN_VELOCITY_THRESHOLD:
					velocity = Vector3.ZERO
			else:
				drag_delay = 0.0
			camera_position += velocity * delta
 
	update_speed_label()

	# --- SFX WEIGHTED BACKGROUND COLOR (subtle, only when SFX active) ---
	var sfx_weights = {
		point_sound: 0.5,
		explosion_sound: 5.0,
		# laser_sound: 0.2,  # Removed to prevent laser from causing background flash
		asteroid_hit_sound: 4.0,
		asteroid_spawn_sound: 1.5,
		respawn_sound: 1.0,
		laser_safe_sound: 5.0,
		countdown_sound: 0.8
	}
	var total_weight = 2.0
	for sfx in sfx_weights.keys():
		if sfx and sfx.playing:
			total_weight += sfx_weights[sfx]

	var base_color = Color(0, 0, 0) # dark blue/black
	var sfx_color = Color(1, 0.5, 0.2) # soft orange flash, tweak as you like
	var intensity = clamp(total_weight / 10.0, 0.0, 0.5) # max 25% blend

	if total_weight > 0.0:
		background.color = base_color.lerp(sfx_color, intensity)
	else:
		background.color = base_color

	# --- SFX WAVEFORM FLASH LOGIC (no duplicates) ---
	var did_flash = false
	if sfx_capture and (
		(asteroid_hit_sound and asteroid_hit_sound.playing) or
		(explosion_sound and explosion_sound.playing)
	):
		var sfx_buffer = sfx_capture.get_buffer(512)
		var sfx_avg_amplitude = 0.0
		for sample in sfx_buffer:
			sfx_avg_amplitude += abs(sample.x)
		sfx_avg_amplitude = clamp(sfx_avg_amplitude / 512.0, 0.0, 1.0) * 2.0

		var sfx_base_color = Color(0, 0, 0)
		var sfx_flash_color = Color(1, 0.5, 0.2)
		var flash_threshold = 0.1

		if sfx_avg_amplitude > flash_threshold:
			flash_timer = lerp(0.1, 0.5, sfx_avg_amplitude)
			last_flash_intensity = clamp(sfx_avg_amplitude, 0.0, 0.25)
		else:
			if flash_timer > 0.0:
				flash_timer -= delta
				last_flash_intensity = last_flash_intensity * (flash_timer / lerp(0.1, 0.5, last_flash_intensity))
			else:
				last_flash_intensity = 0.0

		if last_flash_intensity > 0.0:
			background.color = sfx_base_color.lerp(sfx_flash_color, last_flash_intensity)
			did_flash = true

	# If not flashing, set to base color
	if not did_flash:
		background.color = Color(0, 0, 0)

func project_3d_to_2d(pos_3d, viewport_size, center):
	if pos_3d.z <= Z_NEAR:
		return Vector2(-1000, -1000)
	var fov_rad = deg_to_rad(FOV)
	var scale = (viewport_size.x / 2.0) / (pos_3d.z * tan(fov_rad / 2.0))
	return center + Vector2(pos_3d.x, pos_3d.y) * scale

const DOUBLE_POWER_TYPES = {
	"DOUBLE_POWER": {
		"color": Color(1, 0.5, 0),  # Orange
		"duration": 10.0,  # 10 seconds
		"symbol": "2X"
	},
	"TIME_FREEZE": {
		"color": Color(0, 0.8, 1),  # Light blue
		"duration": 5.0,  # 5 seconds
		"symbol": "⌛"  # Hourglass symbol
	}
}

var active_double_power_ups = {}
var double_power_spawn_timer: float = 0.0
const DOUBLE_POWER_SPAWN_INTERVAL: float = 15.0  # Spawn every 15 seconds
const TIME_FREEZE_SPAWN_INTERVAL: float = 20.0  # Spawn every 20 seconds
var time_freeze_spawn_timer: float = 10.0  # Start at 10 to offset from double power spawns

func create_double_power_up(type: String, x_pos: float) -> Node2D:
	var power_up = Node2D.new()
	var power_up_data = DOUBLE_POWER_TYPES[type]
	var ship_margin = 20.0
	
	if type == "TIME_FREEZE":
		# Create hourglass shape
		var hourglass = Line2D.new()
		hourglass.width = 2.0
		hourglass.default_color = power_up_data.color
		
		# Define hourglass points
		var size = 20.0
		var points = [
			Vector2(-size/2, -size),  # Top left
			Vector2(size/2, -size),   # Top right
			Vector2(0, 0),            # Center
			Vector2(-size/2, size),   # Bottom left
			Vector2(size/2, size),    # Bottom right
			Vector2(-size/2, -size)   # Back to top left to close shape
		]
		
		# Add cross lines for detail
		points.append_array([
			Vector2(-size/2, -size),  # Top horizontal line
			Vector2(size/2, -size)
		])
		points.append_array([
			Vector2(-size/2, size),   # Bottom horizontal line
			Vector2(size/2, size)
		])
		
		hourglass.points = points
		power_up.add_child(hourglass)
		
		# Add "sand" particles
		var particles = CPUParticles2D.new()
		particles.emitting = true
		particles.amount = 10
		particles.lifetime = 1.0
		particles.emission_shape = CPUParticles2D.EMISSION_SHAPE_POINT
		particles.direction = Vector2(0, 1)
		particles.gravity = Vector2(0, 98)
		particles.initial_velocity_min = 20
		particles.initial_velocity_max = 40
		particles.scale_amount_min = 2.0
		particles.scale_amount_max = 3.0
		particles.color = power_up_data.color
		power_up.add_child(particles)
	else:
		# Original power-up visual (2X)
		var symbol = Label.new()
		symbol.text = power_up_data.symbol
		symbol.add_theme_color_override("font_color", power_up_data.color)
		symbol.add_theme_font_size_override("font_size", 24)
		symbol.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		symbol.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		power_up.add_child(symbol)
		
		# Create glow effect
		var glow = Line2D.new()
		glow.width = 2.0
		glow.default_color = power_up_data.color
		var glow_points = []
		var num_points = 8
		var radius = 20.0
		for i in range(num_points + 1):
			var angle = (float(i) / num_points) * 2 * PI
			glow_points.append(Vector2(cos(angle) * radius, sin(angle) * radius))
		glow.points = glow_points
		power_up.add_child(glow)
	
	# Spawn at random x, off the top edge
	power_up.position = Vector2(x_pos, -SHIP_MARGIN)
	# Move downward
	power_up.set_meta("velocity", Vector2(0, 100))
	power_up.set_meta("type", type)
	return power_up

func apply_double_power_up(type: String):
	var power_up_data = DOUBLE_POWER_TYPES[type]
	active_double_power_ups[type] = power_up_data.duration
	
	match type:
		"DOUBLE_POWER":
			FIRING_COOLDOWN = DEFAULT_FIRING_COOLDOWN / 2.0  # Double fire rate
		"TIME_FREEZE":
			# Freeze all lasers
			for laser in lasers:
				laser.set_meta("original_velocity", laser.get_meta("velocity"))
				laser.set_meta("velocity", Vector2.ZERO)
			# Also freeze the chaser if it exists
			if chaser:
				chaser.set_meta("original_velocity", chaser.get_meta("velocity"))
				chaser.set_meta("velocity", Vector2.ZERO)

func update_double_power_ups(delta: float):
	var keys_to_remove = []
	for type in active_double_power_ups:
		active_double_power_ups[type] -= delta
		
		# Play countdown sound when power-up is 2 seconds from ending
		if active_double_power_ups[type] <= 2.0 and active_double_power_ups[type] > 1.9 and countdown_sound:
			countdown_sound.play()
			
		if active_double_power_ups[type] <= 0:
			keys_to_remove.append(type)
			
			# Reset effects
			match type:
				"DOUBLE_POWER":
					FIRING_COOLDOWN = DEFAULT_FIRING_COOLDOWN
				"TIME_FREEZE":
					# Restore laser velocities
					for laser in lasers:
						if laser.has_meta("original_velocity"):
							laser.set_meta("velocity", laser.get_meta("original_velocity"))
					# Also restore chaser velocity
					if chaser and chaser.has_meta("original_velocity"):
						chaser.set_meta("velocity", chaser.get_meta("original_velocity"))
	
	for key in keys_to_remove:
		active_double_power_ups.erase(key)

func update_difficulty():
	# Calculate difficulty based on score
	if score < DIFFICULTY_THRESHOLD:
		current_difficulty = 1.0 + score * EARLY_GAME_SCALE
	else:
		var excess_score = score - DIFFICULTY_THRESHOLD
		current_difficulty = 1.0 + DIFFICULTY_THRESHOLD * EARLY_GAME_SCALE + excess_score * LATE_GAME_SCALE
	
	current_difficulty = min(current_difficulty, MAX_DIFFICULTY)
	
	# Update spawn intervals based on difficulty
	enemy_spawn_interval = max(0.5, base_spawn_interval / sqrt(current_difficulty))  # Added minimum spawn interval
	power_up_spawn_interval = max(5.0, base_power_up_interval / current_difficulty)  # Added minimum spawn interval

# Add these helper functions for polygon collision detection
func point_in_polygon(point: Vector2, polygon_points: Array[Vector2]) -> bool:
	var inside = false
	var j = polygon_points.size() - 1
	for i in range(polygon_points.size()):
		if ((polygon_points[i].y > point.y) != (polygon_points[j].y > point.y) and
			point.x < (polygon_points[j].x - polygon_points[i].x) * (point.y - polygon_points[i].y) / 
			(polygon_points[j].y - polygon_points[i].y) + polygon_points[i].x):
			inside = !inside
		j = i
	return inside

func line_segments_intersect(p1: Vector2, p2: Vector2, p3: Vector2, p4: Vector2) -> bool:
	var denominator = (p4.y - p3.y) * (p2.x - p1.x) - (p4.x - p3.x) * (p2.y - p1.y)
	if denominator == 0:
		return false
	var ua = ((p4.x - p3.x) * (p1.y - p3.y) - (p4.y - p3.y) * (p1.x - p3.x)) / denominator
	var ub = ((p2.x - p1.x) * (p1.y - p3.y) - (p2.y - p1.y) * (p1.x - p3.x)) / denominator
	return ua >= 0 && ua <= 1 && ub >= 0 && ub <= 1

func polygons_intersect(polygon1: Array[Vector2], polygon2: Array[Vector2]) -> bool:
	# Check if any point from polygon1 is inside polygon2
	for point in polygon1:
		if point_in_polygon(point, polygon2):
			return true
	# Check if any point from polygon2 is inside polygon1
	for point in polygon2:
		if point_in_polygon(point, polygon1):
			return true
	# Check if any line segments intersect
	var j1 = polygon1.size() - 1
	var j2 = polygon2.size() - 1
	for i1 in range(polygon1.size()):
		for i2 in range(polygon2.size()):
			if line_segments_intersect(polygon1[j1], polygon1[i1], polygon2[j2], polygon2[i2]):
				return true
			j2 = i2
		j1 = i1
		j2 = polygon2.size() - 1
	return false

func get_ship_polygon() -> Array[Vector2]:
	var ship_points: Array[Vector2] = []
	var vertices = [
		Vector2(96, 64), Vector2(48, 40), Vector2(48, 88), Vector2(40, 48),
		Vector2(40, 80), Vector2(64, 64)
	]
	for vertex in vertices:
		var centered = vertex - Vector2(64, 64)
		var rotated = centered.rotated(-PI / 2)  # Always face up
		var final = rotated + player_ship.position
		ship_points.append(final)
	return ship_points

func get_asteroid_polygon(enemy: Node2D) -> Array[Vector2]:
	var asteroid_points: Array[Vector2] = []
	var vertices_3d = enemy.get_meta("vertices_3d", [])
	var rotation = enemy.get_meta("rotation", Vector3.ZERO)
	var yaw_matrix = Basis(Vector3(0, 1, 0), rotation.y)
	var pitch_matrix = Basis(Vector3(1, 0, 0), rotation.x)
	var roll_matrix = Basis(Vector3(0, 0, 1), rotation.z)
	var transform = yaw_matrix * pitch_matrix * roll_matrix
	for vertex in vertices_3d:
		var rotated_vertex = transform * vertex
		var point = Vector2(rotated_vertex.x, rotated_vertex.y) + enemy.position
		asteroid_points.append(point)
	return asteroid_points

func get_laser_polygon(laser_node: Node2D) -> Array[Vector2]:
	var laser_points: Array[Vector2] = []
	var height = 5.0  # Same as the line width
	var half_height = height / 2.0
	# Create a thin horizontal rectangle for the laser
	laser_points.append(laser_node.position + Vector2(0, -half_height))
	laser_points.append(laser_node.position + Vector2(viewport_size.x, -half_height))
	laser_points.append(laser_node.position + Vector2(viewport_size.x, half_height))
	laser_points.append(laser_node.position + Vector2(0, half_height))
	return laser_points

func get_ship_center_hitbox() -> Array[Vector2]:
	var ship_center: Array[Vector2] = []
	var center = player_ship.position
	var size = 20.0
	# Create a small diamond shape in the center of the ship, always oriented up
	ship_center.append(center + Vector2(size, 0).rotated(BASE_SHIP_ROTATION))
	ship_center.append(center + Vector2(0, size).rotated(BASE_SHIP_ROTATION))
	ship_center.append(center + Vector2(-size, 0).rotated(BASE_SHIP_ROTATION))
	ship_center.append(center + Vector2(0, -size).rotated(BASE_SHIP_ROTATION))
	return ship_center

func create_combo_text(position: Vector2, combo: int) -> Node2D:
	var combo_node = Node2D.new()
	combo_node.position = position + Vector2(0, -30)  # Position above the score
	
	var label_container = Control.new()
	combo_node.add_child(label_container)
	
	var custom_font = load("res://ARCADECLASSIC.TTF")
	
	var combo_text = "x" + str(combo) + " COMBO!"
	
	# Create multiple overlapping labels for bold effect
	var offsets = [
		Vector2(0, 0),
		Vector2(1, 0),
		Vector2(0.5, 0)
	]
	
	for offset in offsets:
		var label = Label.new()
		label.text = combo_text
		# Color intensity increases with combo
		var color_intensity = min(1.0, 0.5 + (float(combo) / MAX_COMBO) * 0.5)
		label.add_theme_color_override("font_color", Color(1, color_intensity, 0))
		label.add_theme_font_size_override("font_size", 24)
		label.add_theme_font_override("font", custom_font)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		label.position = offset
		label_container.add_child(label)
	
	# Create a tween for the animation
	var tween = create_tween()
	tween.set_parallel(true)
	
	# Move upward and fade out
	tween.tween_property(combo_node, "position", combo_node.position + Vector2(0, -50), 1.0).set_ease(Tween.EASE_OUT)
	tween.tween_property(combo_node, "scale", Vector2(1.5, 1.5), 0.2).set_ease(Tween.EASE_OUT)
	
	# Fade out all labels
	for label in label_container.get_children():
		tween.tween_property(label, "modulate:a", 0.0, 1.0).set_ease(Tween.EASE_IN)
	
	# Delete after animation
	tween.tween_callback(combo_node.queue_free).set_delay(1.0)
	
	return combo_node

func reset_fuel():
	fuel = 100.0

# Add new function to handle viewport size changes
func _on_viewport_size_changed():
	# Get the actual screen/window size
	var window_size = DisplayServer.window_get_size()
	
	# Update viewport size based on the physical screen
	viewport_size = get_viewport_rect().size
	print("[DEBUG][_on_viewport_size_changed] viewport_size: ", viewport_size)
	print("[DEBUG][_on_viewport_size_changed] window_size: ", window_size)
	
	# Update camera to properly handle the viewport
	var camera = $StarContainer/Camera2D
	if camera:
		camera.position = Vector2(viewport_size.x / 2, viewport_size.y / 2)
		print("[DEBUG][_on_viewport_size_changed] camera.position: ", camera.position)
		
		# Determine if we're on mobile by checking aspect ratio
		var aspect_ratio = viewport_size.x / viewport_size.y
		var is_mobile = aspect_ratio < 0.8 || aspect_ratio > 2.2 || OS.has_feature("mobile")
		
		if is_mobile:
			# For mobile, we want to fill the screen but not zoom in too much
			# Reference size based on your screenshot (portrait orientation)
			var target_width = 540  # Wider reference width to zoom out
			var target_height = 960  # Shorter reference height to zoom out
			
			# Calculate zoom to fill the entire screen
			var width_ratio = viewport_size.x / target_width
			var height_ratio = viewport_size.y / target_height
			
			# Use the SMALLER ratio to ensure we see more of the game area
			var zoom_factor = min(width_ratio, height_ratio) * 0.7  # Reduce zoom by 30%
			camera.zoom = Vector2(zoom_factor, zoom_factor)
			
			# Adjust content scale mode for mobile
			get_tree().root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
			get_tree().root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND
		else:
			# For desktop/larger screens, use standard zoom calculation
			var target_width = 1142  # Reference width from your scene
			var target_height = 662  # Reference height from your scene
			var width_ratio = viewport_size.x / target_width
			var height_ratio = viewport_size.y / target_height
			var zoom_factor = min(width_ratio, height_ratio)
			camera.zoom = Vector2(zoom_factor, zoom_factor)
		
		print("[DEBUG][_on_viewport_size_changed] camera.zoom: ", camera.zoom)
	
	# Update all position-dependent elements
	if background:
		background.size = viewport_size
	
	# Calculate the playable area to use full width
	var playable_width = viewport_size.x
	var playable_height = viewport_size.y
	
	# Center star container (no need to change position as camera is in StarContainer)
	if starfield:
		starfield.position = Vector2.ZERO  # Position relative to StarContainer now
	
	if player_ship:
		player_ship.position = Vector2(playable_width / 2, playable_height - SHIP_MARGIN)
		print("[DEBUG][_on_viewport_size_changed] player_ship.position: ", player_ship.position)
	

	
	# Update laser positions to span full width
	for laser in lasers:
		var line = laser.get_child(0) as Line2D
		if line:
			line.clear_points()
			line.add_point(Vector2(0, 0))
			line.add_point(Vector2(playable_width, 0))
		
		# Update label position
		var label_container = laser.get_child(1) as Control
		if label_container:
			label_container.position = Vector2(playable_width / 2 - 50, 10)
	
	# Update chaser to span full width
	if chaser:
		var line = chaser.get_child(0) as Line2D
		if line:
			line.clear_points()
			line.add_point(Vector2(0, 0))
			line.add_point(Vector2(playable_width, 0))
		
		# Update label position
		var label_container = chaser.get_child(1) as Control
		if label_container:
			label_container.position = Vector2(playable_width / 2 - 50, 10)
	
	# Update disco ball position
	if disco_ball_container:
		disco_ball_container.position = Vector2(playable_width - 50, 50)
	
	# Remove references to debug lines since they no longer exist
	
	
	if score_label:
		score_label.position = Vector2(
			playable_width - score_label.get_rect().size.x - 40,
			40
		)
	
	if game_over_label:
		var game_over_size = game_over_label.get_rect().size
		game_over_label.position = Vector2(playable_width / 2, playable_height / 2)
		game_over_label.offset_left = -game_over_size.x / 2
		game_over_label.offset_top = -game_over_size.y / 2

	# Update joystick position for mobile - ensure it stays in bottom left
	if virtual_joystick:
		var margin = JOYSTICK_RADIUS / 2
		# Move it up with 50 pixels of extra space (reduced from 100)
		virtual_joystick.position = Vector2(margin, viewport_size.y - JOYSTICK_RADIUS * 2 - margin - 50)
		print("[DEBUG][_on_viewport_size_changed] Updated joystick position: ", virtual_joystick.position)

	# Update music control button position
	if music_menu_button:
		music_menu_button.position = Vector2(viewport_size.x - MUSIC_BUTTON_SIZE.x - MUSIC_MENU_PADDING, MUSIC_MENU_PADDING)
	
	# Update music menu container position
	if music_menu_container:
		music_menu_container.position = Vector2(
			viewport_size.x - music_menu_container.size.x - MUSIC_MENU_PADDING,
			MUSIC_BUTTON_SIZE.y + MUSIC_MENU_PADDING * 2
		)

func create_virtual_joystick():
	# Create joystick container
	virtual_joystick = Control.new()
	virtual_joystick.name = "VirtualJoystick"
	virtual_joystick.size = Vector2(JOYSTICK_RADIUS * 2, JOYSTICK_RADIUS * 2)
	
	# Initially hide the joystick until first touch
	virtual_joystick.visible = false
	
	# Create outer circle (background)
	joystick_outer = TextureRect.new()
	joystick_outer.size = Vector2(JOYSTICK_RADIUS * 2, JOYSTICK_RADIUS * 2)
	joystick_outer.pivot_offset = Vector2(JOYSTICK_RADIUS, JOYSTICK_RADIUS)
	
	# Create outer circle texture
	var outer_image = Image.create(int(JOYSTICK_RADIUS * 2), int(JOYSTICK_RADIUS * 2), false, Image.FORMAT_RGBA8)
	outer_image.fill(Color(0, 0, 0, 0))  # Start with transparent image
	
	# Draw circle
	for x in range(int(JOYSTICK_RADIUS * 2)):
		for y in range(int(JOYSTICK_RADIUS * 2)):
			var dx = x - JOYSTICK_RADIUS
			var dy = y - JOYSTICK_RADIUS
			var distance = sqrt(dx * dx + dy * dy)
			if distance <= JOYSTICK_RADIUS and distance >= JOYSTICK_RADIUS - 4:
				outer_image.set_pixel(x, y, Color(0.5, 0.5, 0.5, 0.5))  # Gray semi-transparent circle
	
	var outer_texture = ImageTexture.create_from_image(outer_image)
	joystick_outer.texture = outer_texture
	virtual_joystick.add_child(joystick_outer)
	
	# Create inner circle (handle)
	joystick_inner = TextureRect.new()
	var inner_size = JOYSTICK_RADIUS * 0.6
	joystick_inner.size = Vector2(inner_size, inner_size)
	joystick_inner.pivot_offset = Vector2(inner_size/2, inner_size/2)
	joystick_inner.position = Vector2(JOYSTICK_RADIUS - inner_size/2, JOYSTICK_RADIUS - inner_size/2)
	
	# Create inner circle texture
	var inner_image = Image.create(int(inner_size), int(inner_size), false, Image.FORMAT_RGBA8)
	inner_image.fill(Color(0, 0, 0, 0))  # Start with transparent image
	
	# Draw filled circle
	for x in range(int(inner_size)):
		for y in range(int(inner_size)):
			var dx = x - inner_size/2
			var dy = y - inner_size/2
			var distance = sqrt(dx * dx + dy * dy)
			if distance <= inner_size/2:
				inner_image.set_pixel(x, y, Color(0.7, 0.7, 0.7, 0.7))  # Lighter gray semi-transparent circle
	
	var inner_texture = ImageTexture.create_from_image(inner_image)
	joystick_inner.texture = inner_texture
	virtual_joystick.add_child(joystick_inner)
	
	# Add to the canvas layer for consistent positioning
	$CanvasLayer.add_child(virtual_joystick)
	
	# Debug print for joystick position
	print("[DEBUG] Joystick created")

func reset_joystick():
	joystick_active = false
	joystick_direction = Vector2.ZERO
	touch_joystick_id = -1
	if joystick_inner:
		joystick_inner.position = Vector2(
			JOYSTICK_RADIUS - joystick_inner.size.x/2, 
			JOYSTICK_RADIUS - joystick_inner.size.y/2
		)

func _on_pause_button_pressed():
	if current_state == GameState.GAME_LOOP:
		current_state = GameState.PAUSED
		update_state_visuals()
	elif current_state == GameState.PAUSED:
		current_state = GameState.GAME_LOOP
		update_state_visuals()

func _on_pause_menu_button_input(event, btn, lbl):
	reset_menu_button_colors(pause_menu_container)
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(1,1,1,0.95)
		lbl.add_theme_color_override("font_color", Color(0,0,0))
		match btn.name:
			"resume":
				set_game_state(GameState.GAME_LOOP)
			"music_player":
				pause_menu_container.visible = false
				music_player_menu_container.visible = true
			"settings":
				pass
			"menu":
				set_game_state(GameState.MENU)
	elif event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(0,0,0,0.8)
		lbl.add_theme_color_override("font_color", Color(1,1,1))

func _on_main_menu_button_input(event, btn, lbl):
	reset_menu_button_colors(main_menu_container)
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(1,1,1,0.95)
		lbl.add_theme_color_override("font_color", Color(0,0,0))
		match btn.name:
			"start_game":
				main_menu_container.visible = false
				game_select_menu_container.visible = true
			"stats":
				if main_menu_container:
					main_menu_container.visible = false
				if music_player_menu_container:
					music_player_menu_container.visible = false
				if pause_menu_container:
					pause_menu_container.visible = false
				if stats_menu_container:
					var viewport_size = get_viewport_rect().size
					stats_menu_container.size = Vector2(400, 520) # Increased size for better fit
					stats_menu_container.position = Vector2((viewport_size.x - 400) / 2, (viewport_size.y - 520) / 2)
					stats_menu_container.visible = true
					stats_menu_container.move_to_front() # bring to front
					# Only set the color for the background panel, not all ColorRects
					for child in stats_menu_container.get_children():
						if child is ColorRect and child != null and child.position == Vector2(0, 0):
							child.color = Color(0, 0, 0, 1)
					print("[DEBUG] Stats menu container set visible and centered.")
					update_stats_label()
			"music_player":
				main_menu_container.visible = false
				music_player_menu_container.visible = true
			"settings":
				pass
	elif event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(0,0,0,0.8)
		lbl.add_theme_color_override("font_color", Color(1,1,1))

func _on_game_select_menu_button_input(event, btn, lbl):
	reset_menu_button_colors(game_select_menu_container)
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(1,1,1,0.95)
		lbl.add_theme_color_override("font_color", Color(0,0,0))
		match btn.name:
			"game_1":
				reset_game_variables()
				set_game_state(GameState.GAME_LOOP)
				game_select_menu_container.visible = false
			"game_2":
				# Temporarily change label to 'Coming Soon!' and revert after 1.5s
				var original_text = lbl.text
				lbl.text = "Coming Soon!"
				await get_tree().create_timer(1.5).timeout
				lbl.text = original_text
			"back":
				game_select_menu_container.visible = false
				main_menu_container.visible = true
	elif event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(0,0,0,0.8)
		lbl.add_theme_color_override("font_color", Color(1,1,1))

# 5. Add handler for the Back button in the music player menu
var last_menu: String = "main"
func _on_music_player_menu_button_input(event, btn, lbl):
	reset_menu_button_colors(music_player_menu_container)
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(1,1,1,0.95)
		lbl.add_theme_color_override("font_color", Color(0,0,0))
		if btn.name == "back":
			music_player_menu_container.visible = false
			if pause_menu_container.visible == false and main_menu_container.visible == false:
				if current_state == GameState.PAUSED:
					pause_menu_container.visible = true
				else:
					main_menu_container.visible = true
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(1,1,1,0.95)
		lbl.add_theme_color_override("font_color", Color(0,0,0))
		if btn.name == "back":
			music_player_menu_container.visible = false
			if pause_menu_container.visible == false and main_menu_container.visible == false:
				if current_state == GameState.PAUSED:
					pause_menu_container.visible = true
				else:
					main_menu_container.visible = true
	elif event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(0,0,0,0.7)
		lbl.add_theme_color_override("font_color", Color(1,1,1))

# --- Centralized State Management ---
func set_game_state(new_state: GameState):
	# Increment games played when starting a new game
	ensure_player_stats_keys()
	if new_state == GameState.GAME_LOOP and current_state != GameState.GAME_LOOP:
		player_stats["games_played"] += 1
	current_state = new_state
	update_state_visuals()
	if new_state == GameState.GAME_LOOP:
		show_instructions()

func reset_game_variables():
	# Reset all gameplay variables, clear arrays, reset timers, etc.
	score = 0
	game_time = 0.0
	heat = 0.0
	max_enemies = 5
	laser_spawn_timer = 0.0
	current_laser_count = 0
	is_game_over = false
	reset_fuel()
	for enemy in enemies:
		enemy.queue_free()
	enemies.clear()
	asteroid_sound_players.clear()
	for bullet in bullets:
		bullet.node.queue_free()
	bullets.clear()
	for power_up in power_ups:
		power_up.queue_free()
	power_ups.clear()
	for coin in coins:
		coin.queue_free()
	coins.clear()
	for laser in lasers:
		laser.queue_free()
	lasers.clear()
	power_up_spawn_timer = 0.0
	is_power_up_active = false
	power_up_timer = 0.0
	player_ship.position = Vector2(viewport_size.x / 2, viewport_size.y - SHIP_MARGIN)
	ship_velocity = Vector2.ZERO
	player_ship.rotation = BASE_SHIP_ROTATION
	tilt_timer = 0.0
	firing_timer = 0.0
	spawn_timer = 0.0
	coin_spawn_timer = 0.0
	chaser.position = Vector2(0, -50)
	active_double_power_ups.clear()
	combo_timer = 0.0
	current_combo = 0
	last_combo = 0
	combo_drain_effect = false

func handle_game_over():
	# Increment deaths
	ensure_player_stats_keys()
	player_stats["deaths"] += 1
	# Sync high_score and player_stats["highest_score"]
	if score > high_score:
		high_score = score
		player_stats["highest_score"] = high_score
	elif high_score > player_stats["highest_score"]:
		player_stats["highest_score"] = high_score
	# Save all stats at game over
	save_player_stats()
	update_stats_label()

func _on_restart_button_pressed():
	handle_game_over()
	if respawn_sound:
		respawn_sound.play()
	reset_game_variables()
	set_game_state(GameState.GAME_LOOP)

func _on_return_menu_button_pressed():
	handle_game_over()
	set_game_state(GameState.MENU)

# Remove all in-game calls to save_player_stats() for incremental stat changes
# In shoot_bullet():
#   player_stats["shots_fired"] += 1
#   # save_player_stats() <-- REMOVED
# In flake_asteroid():
#   player_stats["asteroids_destroyed"] += 1
#   # save_player_stats() <-- REMOVED
# In coin collection logic:
#   player_stats["coins_collected"] += coin_value
#   # save_player_stats() <-- REMOVED
# In laser fade-out logic:
#   player_stats["lasers_cleared"] += 1
#   # save_player_stats() <-- REMOVED

func update_stats_label():
	if stats_menu_container and stats_menu_container.has_node("StatsLabel"):
		var l = stats_menu_container.get_node("StatsLabel")
		print("[DEBUG] Updating stats label:", l)
		# Format time played
		var total_seconds = int(player_stats["time_played"])
		var hours = total_seconds / 3600
		var minutes = (total_seconds % 3600) / 60
		var seconds = total_seconds % 60
		var time_str = "%02d:%02d:%02d" % [hours, minutes, seconds]
		l.text = (
			"STATS\n" +
			"Highest Score: " + str(int(high_score)) + "\n" +
			"Games Played: " + str(int(player_stats["games_played"])) + "\n" +
			"Time Played: " + time_str + "\n" +
			"Asteroids Destroyed: " + str(int(player_stats["asteroids_destroyed"])) + "\n" +
			"Shots Fired: " + str(int(player_stats["shots_fired"])) + "\n" +
			"Lasers Cleared: " + str(int(player_stats["lasers_cleared"]))
		)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_TOP
		l.position = Vector2((stats_menu_container.size.x - l.size.x) / 2, 20)
		print("[DEBUG] Stats label text set to:", l.text)

# Helper to ensure all player_stats keys exist
func ensure_player_stats_keys():
	var defaults = {
		"highest_score": 0,
		"games_played": 0,
		"coins_collected": 0,
		"asteroids_destroyed": 0,
		"deaths": 0,
		"shots_fired": 0,
		"lasers_cleared": 0,
		"time_played": 0.0
	}
	for key in defaults.keys():
		if not player_stats.has(key):
			player_stats[key] = defaults[key]

func _on_stats_menu_button_input(event, btn, lbl):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(1,1,1,0.95)
		lbl.add_theme_color_override("font_color", Color(0,0,0))
		if btn.name == "back":
			stats_menu_container.visible = false
			if main_menu_container:
				main_menu_container.visible = true
	elif event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		btn.color = Color(0,0,0,0.7)
		lbl.add_theme_color_override("font_color", Color(1,1,1))

func reset_menu_button_colors(menu_container):
	if not menu_container:
		return
	for btn in menu_container.get_children():
		if btn is ColorRect:
			btn.color = Color(1,1,1,0.95)
			# Reset label color
			if btn.get_child_count() > 0 and btn.get_child(0) is Label:
				btn.get_child(0).add_theme_color_override("font_color", Color(0,0,0))

func clear_gameplay_objects():
	for enemy in enemies:
		enemy.queue_free()
	enemies.clear()
	for bullet in bullets:
		bullet.node.queue_free()
	bullets.clear()
	for power_up in power_ups:
		power_up.queue_free()
	power_ups.clear()
	for coin in coins:
		coin.queue_free()
	coins.clear()
	for laser in lasers:
		laser.queue_free()
	lasers.clear()
	
func show_instructions():
	var fade_time = 0.7
	for label in [instructions_left, instructions_right, instructions_top]:
		var tween = create_tween()
		tween.tween_property(label, "modulate:a", 1.0, fade_time)
	await get_tree().create_timer(3.5).timeout
	for label in [instructions_left, instructions_right, instructions_top]:
		var tween = create_tween()
		tween.tween_property(label, "modulate:a", 0.0, fade_time)
