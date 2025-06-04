extends Node3D

var is_dragging = false
var last_mouse_pos = Vector2.ZERO
var unravelable_object = null

func _ready():
	unravelable_object = $UnravelableObject3D

func _input(event):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				is_dragging = true
				last_mouse_pos = event.position
				if unravelable_object:
					unravelable_object.stop_inertia()
			else:
				is_dragging = false
				if unravelable_object:
					unravelable_object.start_inertia()
	elif event is InputEventMouseMotion and is_dragging:
		var drag_delta = event.position - last_mouse_pos
		last_mouse_pos = event.position
		if unravelable_object:
			unravelable_object.spin_object(get_process_delta_time(), drag_delta)
	# Touch support
	elif event is InputEventScreenTouch:
		if event.pressed:
			is_dragging = true
			last_mouse_pos = event.position
			if unravelable_object:
				unravelable_object.stop_inertia()
		else:
			is_dragging = false
			if unravelable_object:
				unravelable_object.start_inertia()
	elif event is InputEventScreenDrag and is_dragging:
		var drag_delta = event.position - last_mouse_pos
		last_mouse_pos = event.position
		if unravelable_object:
			unravelable_object.spin_object(get_process_delta_time(), drag_delta) 
