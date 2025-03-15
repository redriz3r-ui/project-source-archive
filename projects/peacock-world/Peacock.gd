extends CharacterBody3D

var speed = 4.0
var jump_velocity = 6.0
var gravity = ProjectSettings.get_setting("physics/3d/default_gravity")
var tail_fanned = false

@onready var tail = $Tail  # Links to Tail node

func _physics_process(delta):
	if not is_on_floor():
		velocity.y -= gravity * delta

	var input_dir = Vector3.ZERO
	input_dir.x = Input.get_axis("ui_left", "ui_right")
	input_dir.z = Input.get_axis("ui_up", "ui_down")
	if input_dir != Vector3.ZERO:
		input_dir = input_dir.normalized()
	
	velocity.x = input_dir.x * speed
	velocity.z = input_dir.z * speed

	if Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = jump_velocity

	# Tail Fan
	if Input.is_action_just_pressed("ui_select"):  # Shift
		tail_fanned = !tail_fanned
		if tail_fanned:
			tail.scale = Vector3(4.0, 2.0, 1.0)  # Fan out
		else:
			tail.scale = Vector3(2.0, 1.0, 1.0)  # Fold back

	move_and_slide()
