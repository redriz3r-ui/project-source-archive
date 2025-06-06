extends Node2D
const SHOOTING_STAR_SPEED = 400
const SHOOTING_STAR_LIFETIME = 1.0
func spawn_shooting_star():
	var star = ColorRect.new()
	star.size = Vector2(randf_range(3, 6), 1)  # Small thin streak
	star.color = Color(1, 1, 1, 1.0)
	add_child(star)

	var start_pos = Vector2(randf_range(0, get_viewport_rect().size.x), -10)
	var end_pos = start_pos + Vector2(randf_range(100, 300), randf_range(100, 300))

	star.position = start_pos

	var tween = get_tree().create_tween()
	tween.tween_property(star, "position", end_pos, SHOOTING_STAR_LIFETIME).set_trans(Tween.TRANS_LINEAR)
	tween.tween_callback(star.queue_free)  # Destroy after animation

func _process(delta):
	if randf() < 0.01:  # Random chance per frame
		spawn_shooting_star()
