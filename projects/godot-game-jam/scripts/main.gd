extends Node2D

var is_dragging = false
var drag_start_pos = Vector2.ZERO
var current_drag_pos = Vector2.ZERO
var unravel_progress = 0.0
var current_object = null

func _ready():
	# Initialize the game
	current_object = $UnravelableObject

func _input(event):
	if event is InputEventScreenTouch:
		if event.pressed:
			# Start dragging
			is_dragging = true
			drag_start_pos = event.position
			current_drag_pos = event.position
			if current_object:
				current_object.start_unravel(Vector2.ZERO)
		else:
			# End dragging
			is_dragging = false
			if current_object:
				current_object.stop_unravel()
			check_unravel_progress()
	
	elif event is InputEventScreenDrag and is_dragging:
		# Update drag position
		current_drag_pos = event.position
		update_unravel_visual()

func update_unravel_visual():
	# Calculate the distance and direction of the drag
	var drag_vector = current_drag_pos - drag_start_pos
	var drag_distance = drag_vector.length()
	
	# Update unravel progress based on drag distance
	unravel_progress = min(drag_distance / 200.0, 1.0)  # 200 pixels for full unravel
	
	# Update the visual state of the unravelable object
	if current_object:
		current_object.update_unravel(unravel_progress)

func check_unravel_progress():
	# Check if the object is fully unraveled
	if unravel_progress >= 1.0:
		complete_unravel()

func complete_unravel():
	# Handle the completion of unraveling
	print("Object fully unraveled!")
	# Add completion effects, scoring, or next level logic here 