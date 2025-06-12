extends Node2D

class_name Zombie

# Zombie properties
var velocity: Vector2
var sprite: Sprite2D
var is_exploded = false
var explosion_timer = 0.0
const EXPLOSION_DURATION = 0.5
const MOVE_SPEED = 50.0
const WANDER_RADIUS = 100.0
const WANDER_CHANGE_TIME = 2.0
var wander_timer = 0.0
var target_pos: Vector2
var world_pos: Vector2  # Actual position in world coordinates
var camera_offset: Vector2  # Reference to camera offset
const ZOMBIE_SCALE = Vector2(3.0, 3.0)  # Make zombies 3x bigger

# Grid properties
const GRID_CELL_SIZE = 375
const PERSPECTIVE_STRENGTH = 0.3
const PERSPECTIVE_CENTER_Y = 0.5
const VIEWPORT_SIZE = Vector2(1080, 1920)

func _init(start_pos: Vector2):
	world_pos = start_pos
	position = start_pos  # Initial screen position
	velocity = Vector2.ZERO
	target_pos = world_pos
	camera_offset = Vector2.ZERO
	
	# Create sprite
	sprite = Sprite2D.new()
	sprite.texture = load("res://zombie.png")
	sprite.centered = true
	sprite.scale = ZOMBIE_SCALE  # Apply the scale
	add_child(sprite)

func _process(delta):
	if is_exploded:
		# Keep dead body fixed at explosion location (no perspective skew)
		position = world_pos - camera_offset
		return
	
	# Update wander behavior
	wander_timer += delta
	if wander_timer >= WANDER_CHANGE_TIME:
		wander_timer = 0.0
		# Choose new random direction
		var angle = randf_range(0, TAU)
		target_pos = world_pos + Vector2(cos(angle), sin(angle)) * WANDER_RADIUS
	
	# Move towards target
	var direction = (target_pos - world_pos).normalized()
	velocity = direction * MOVE_SPEED
	world_pos += velocity * delta
	
	# Calculate perspective offset
	var perspective_offset = (world_pos.y - camera_offset.y - VIEWPORT_SIZE.y * PERSPECTIVE_CENTER_Y) * PERSPECTIVE_STRENGTH
	
	# Update screen position with perspective
	position = world_pos - camera_offset + Vector2(perspective_offset, 0)
	
	# Update sprite
	sprite.position = Vector2.ZERO  # Sprite is relative to zombie position
	sprite.flip_h = velocity.x < 0  # Flip sprite based on movement direction

func update_camera_offset(new_offset: Vector2):
	camera_offset = new_offset
	if is_exploded:
		# Keep dead body fixed at explosion location (no perspective skew)
		position = world_pos - camera_offset
		return
	# Recalculate position with perspective
	var perspective_offset = (world_pos.y - camera_offset.y - VIEWPORT_SIZE.y * PERSPECTIVE_CENTER_Y) * PERSPECTIVE_STRENGTH
	position = world_pos - camera_offset + Vector2(perspective_offset, 0)

func explode():
	is_exploded = true
	sprite.texture = load("res://zombie_boom.png")
	velocity = Vector2.ZERO
	# Hide the zombie's own sprite so only the main scene's dead body is visible
	sprite.visible = false
	# Don't queue_free() - leave the node in place 
