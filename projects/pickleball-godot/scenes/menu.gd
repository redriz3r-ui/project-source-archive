extends Control

var player: PickleballPlayer
var training_scene: Node
var simulation_scene: Node

func _ready():
	# Initialize player
	player = PickleballPlayer.new()
	add_child(player)
	
	# Initialize scenes
	training_scene = load("res://scenes/training.tscn").instantiate()
	simulation_scene = load("res://scenes/simulation.tscn").instantiate()
	
	# Hide scenes initially
	training_scene.visible = true
	simulation_scene.visible = true
	add_child(training_scene)
	add_child(simulation_scene)
	
	# Connect buttons
	$VBoxContainer/TrainButton.pressed.connect(_on_train_pressed)
	$VBoxContainer/SimulateButton.pressed.connect(_on_simulate_pressed)
	$VBoxContainer/StatsButton.pressed.connect(_on_stats_pressed)
	$VBoxContainer/BackButton.pressed.connect(_on_back_pressed)
	
	# Hide back button initially
	$VBoxContainer/BackButton.visible = true

func _on_train_pressed():
	$VBoxContainer/MainButtons.visible = false
	$VBoxContainer/BackButton.visible = true
	training_scene.visible = true
	simulation_scene.visible = false

func _on_simulate_pressed():
	$VBoxContainer/MainButtons.visible = false
	$VBoxContainer/BackButton.visible = true
	training_scene.visible = false
	simulation_scene.visible = true

func _on_stats_pressed():
	$VBoxContainer/MainButtons.visible = false
	$VBoxContainer/BackButton.visible = true
	$VBoxContainer/StatsPanel.visible = true
	_update_stats_display()

func _on_back_pressed():
	$VBoxContainer/MainButtons.visible = true
	$VBoxContainer/BackButton.visible = false
	training_scene.visible = false
	simulation_scene.visible = false
	$VBoxContainer/StatsPanel.visible = false

func _update_stats_display():
	var stats = player.get_player_summary()
	
	# Update level and experience
	$VBoxContainer/StatsPanel/LevelLabel.text = "Level: " + str(stats.level)
	$VBoxContainer/StatsPanel/ExpLabel.text = "Experience: " + str(stats.experience) + "/" + str(stats.experience_to_next_level)
	
	# Update main stats
	$VBoxContainer/StatsPanel/PowerLabel.text = "Power: " + str(stats.stats.power)
	$VBoxContainer/StatsPanel/AccuracyLabel.text = "Accuracy: " + str(stats.stats.accuracy)
	$VBoxContainer/StatsPanel/SpeedLabel.text = "Speed: " + str(stats.stats.speed)
	$VBoxContainer/StatsPanel/ReactionLabel.text = "Reaction: " + str(stats.stats.reaction)
	$VBoxContainer/StatsPanel/EnduranceLabel.text = "Endurance: " + str(stats.stats.endurance)
	
	# Update technique stats
	$VBoxContainer/StatsPanel/TechniqueLabel.text = "Techniques:"
	$VBoxContainer/StatsPanel/DriveLabel.text = "Drive: " + str(stats.stats.technique.drive)
	$VBoxContainer/StatsPanel/DinkLabel.text = "Dink: " + str(stats.stats.technique.dink)
	$VBoxContainer/StatsPanel/VolleyLabel.text = "Volley: " + str(stats.stats.technique.volley)
	$VBoxContainer/StatsPanel/LobLabel.text = "Lob: " + str(stats.stats.technique.lob)
	$VBoxContainer/StatsPanel/TopspinLabel.text = "Topspin: " + str(stats.stats.technique.topspin)
	$VBoxContainer/StatsPanel/SliceLabel.text = "Slice: " + str(stats.stats.technique.slice)
	$VBoxContainer/StatsPanel/BlockLabel.text = "Block: " + str(stats.stats.technique.block)
	
	# Update history
	$VBoxContainer/StatsPanel/TrainingLabel.text = "Training Sessions: " + str(stats.training_sessions)
	$VBoxContainer/StatsPanel/MatchesLabel.text = "Matches Played: " + str(stats.matches_played) 
