extends Node

# Game state
var current_score = 0
var time_remaining = 60.0
var boxes_solved = 0
var difficulty_level = 1

# References
@onready var timer = $Timer
@onready var score_label = $UI/ScoreLabel
@onready var time_label = $UI/TimeLabel

func _ready():
	start_game()

func _process(delta):
	time_remaining -= delta
	update_ui()
	
	if time_remaining <= 0:
		game_over()

func start_game():
	current_score = 0
	time_remaining = 60.0
	boxes_solved = 0
	difficulty_level = 1
	spawn_new_box()

func spawn_new_box():
	# Clear any existing box
	for child in get_children():
		if child.is_in_group("mystery_box"):
			child.queue_free()
	
	# Instance new box
	var box_scene = load("res://scenes/mystery_box.tscn")
	var new_box = box_scene.instantiate()
	add_child(new_box)
	
	# Set difficulty-based properties
	new_box.set_difficulty(difficulty_level)

func box_solved():
	boxes_solved += 1
	current_score += 100 * difficulty_level
	time_remaining += 10.0  # Bonus time
	difficulty_level += 1
	
	# Show success effects
	$SuccessEffects.play()
	
	# Spawn next box after a short delay
	await get_tree().create_timer(1.0).timeout
	spawn_new_box()

func update_ui():
	score_label.text = "Score: %d" % current_score
	time_label.text = "Time: %.1f" % time_remaining

func game_over():
	# Show game over screen
	$GameOverScreen.visible = true
	$GameOverScreen.set_score(current_score)
	
	# Stop the game
	get_tree().paused = true 
