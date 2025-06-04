extends Node3D

var rotation_speed = 0.01
var rotation_x = 0.0
var rotation_y = 0.0
var angular_velocity = Vector2.ZERO
var damping = 50.0
var is_spinning = false

func _ready():
	rotation_x = rotation.x
	rotation_y = rotation.y

func spin_object(delta, drag_delta):
	# Update rotation values
	rotation_y -= drag_delta.x * rotation_speed
	rotation_x -= drag_delta.y * rotation_speed
	# Apply rotation
	rotation = Vector3(rotation_x, rotation_y, 0)
	# Set angular velocity for inertia
	angular_velocity = -drag_delta * rotation_speed / delta
	is_spinning = false

func start_inertia():
	is_spinning = true

func stop_inertia():
	is_spinning = false
	angular_velocity = Vector2.ZERO

func _process(delta):
	if is_spinning:
		# Apply angular velocity
		rotation_y += angular_velocity.x * delta
		rotation_x += angular_velocity.y * delta
		rotation_x = clamp(rotation_x, deg_to_rad(-90), deg_to_rad(90))
		rotation = Vector3(rotation_x, rotation_y, 0)
		# Apply damping
		angular_velocity = angular_velocity.move_toward(Vector2.ZERO, damping * delta)
		# Stop spinning if velocity is very low
		if angular_velocity.length() < 0.01:
			stop_inertia() 
