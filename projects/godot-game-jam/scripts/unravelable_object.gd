extends Node2D

var unravel_progress = 0.0
var is_being_unraveled = false
var original_scale = Vector2.ONE
var unravel_direction = Vector2.ZERO

func _ready():
	original_scale = scale
	$UnravelProgress.hide()

func start_unravel(direction: Vector2):
	is_being_unraveled = true
	unravel_direction = direction.normalized()
	$UnravelProgress.show()

func update_unravel(progress: float):
	unravel_progress = progress
	$UnravelProgress.value = progress * 100
	
	# Update visual appearance based on progress
	scale = original_scale * (1.0 - progress * 0.5)  # Shrink slightly as it unravels
	rotation = progress * PI  # Rotate as it unravels
	
	# Add some visual effects
	modulate.a = 1.0 - progress * 0.3  # Slight fade
	modulate.r = 1.0 - progress * 0.5  # Shift color as it unravels

func stop_unravel():
	is_being_unraveled = false
	if unravel_progress >= 1.0:
		complete_unravel()
	else:
		# Reset if not fully unraveled
		scale = original_scale
		rotation = 0
		modulate = Color.WHITE
		$UnravelProgress.hide()

func complete_unravel():
	# Add completion effects
	var tween = create_tween()
	tween.tween_property(self, "modulate:a", 0.0, 0.5)
	tween.tween_callback(queue_free) 