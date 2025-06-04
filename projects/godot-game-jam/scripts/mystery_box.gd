extends Node3D

# Puzzle state
var is_locked = true
var current_puzzle_type = ""
var solution = []
var difficulty = 1

# Rotation control
var rotation_speed = 2.0
var is_rotating = false
var target_rotation = Vector3.ZERO

func _ready():
	# Initialize the box
	randomize()
	setup_puzzle()

func _process(delta):
	if is_rotating:
		# Smoothly rotate towards target
		rotation = rotation.lerp(target_rotation, delta * rotation_speed)

func _input(event):
	if event is InputEventScreenDrag:
		# Handle touch rotation
		rotate_y(-event.relative.x * 0.01)
		rotate_object_local(Vector3.RIGHT, -event.relative.y * 0.01)
	elif event is InputEventScreenTouch and event.pressed:
		# Handle tap interactions
		check_interaction(event.position)

func setup_puzzle():
	# This will be expanded to handle different puzzle types
	current_puzzle_type = "dial"  # For now, just dial puzzles
	generate_solution()

func generate_solution():
	# Generate a random 3-digit solution
	solution = []
	for i in range(3):
		solution.append(randi() % 10)
	
	# Set the target values for each dial
	for i in range(3):
		var dial = $DialContainer.get_child(i)
		if dial:
			dial.set_target_value(solution[i])

func check_interaction(position: Vector2):
	# This will be expanded to handle different interaction types
	pass

func set_difficulty(level: int):
	difficulty = level
	# Adjust puzzle parameters based on difficulty
	rotation_speed = 2.0 + (level * 0.2)  # Slightly faster rotation at higher difficulties
	setup_puzzle()

func unlock():
	if is_locked:
		is_locked = false
		# Play unlock animation/effects
		$AnimationPlayer.play("unlock")
		# Signal to PuzzleManager that this box is solved
		get_parent().box_solved() 
