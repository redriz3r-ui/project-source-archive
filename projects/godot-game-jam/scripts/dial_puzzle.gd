extends Node3D

signal dial_solved(dial)

# Dial properties
var current_value = 0
var target_value = 0
var is_interactable = true
var rotation_speed = 5.0

# Visual elements
@onready var dial_mesh = $DialMesh
@onready var number_label = $NumberLabel

func _ready():
	randomize()
	target_value = randi() % 10
	update_visual()

func _input(event):
	if not is_interactable:
		return
		
	if event is InputEventScreenDrag:
		# Calculate rotation based on drag
		var drag_amount = event.relative.x
		rotate_y(drag_amount * 0.01)
		
		# Update value based on rotation
		var new_value = round(rotation_degrees.y / 36) % 10
		if new_value != current_value:
			current_value = new_value
			update_visual()
			check_solution()

func update_visual():
	# Update the number display
	number_label.text = str(current_value)
	
	# Update dial mesh rotation to match value
	var target_rotation = current_value * 36  # 360 degrees / 10 numbers
	dial_mesh.rotation_degrees.y = target_rotation

func check_solution():
	# Signal to parent if this is part of a larger puzzle
	if current_value == target_value:
		emit_signal("dial_solved", self)

func set_target_value(value: int):
	target_value = value % 10
	update_visual()

func set_interactable(value: bool):
	is_interactable = value 
