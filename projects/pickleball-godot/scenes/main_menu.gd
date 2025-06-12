extends Control

# References to other scenes
# var training_scene: Node
# var simulation_scene: Node
# var current_scene: Node

# UI Elements
@onready var main_menu = $MainMenu
@onready var training_menu = $TrainingMenu
@onready var match_menu = $MatchMenu
@onready var stats_menu = $StatsMenu

# Player reference
var player: PickleballPlayer

# Preload scenes
var training_scene_preload = preload("res://scenes/training.tscn")
var simulation_scene_preload = preload("res://scenes/simulation.tscn")

func _ready():
	# Initialize player
	player = PickleballPlayer.new()
	add_child(player)
	
	# Initialize scenes
	# training_scene = training_scene_preload.instantiate()
	# simulation_scene = simulation_scene_preload.instantiate()
	
	# Connect signals
	$MainMenu/StartTraining.pressed.connect(_on_start_training_pressed)
	$MainMenu/StartMatch.pressed.connect(_on_start_match_pressed)
	$MainMenu/ViewStats.pressed.connect(_on_view_stats_pressed)
	$MainMenu/Quit.pressed.connect(_on_quit_pressed)
	
	# Training menu buttons
	$TrainingMenu/Back.pressed.connect(_on_training_back_pressed)
	for drill in get_available_drills():
		var button = Button.new()
		button.text = drill.name
		button.pressed.connect(_on_drill_selected.bind(drill.type))
		$TrainingMenu/DrillList.add_child(button)
	
	# Match menu buttons
	$MatchMenu/Back.pressed.connect(_on_match_back_pressed)
	for match_type in get_available_matches():
		var button = Button.new()
		button.text = match_type.name
		button.pressed.connect(_on_match_selected.bind(match_type.type))
		$MatchMenu/MatchList.add_child(button)
	
	# Stats menu
	$StatsMenu/Back.pressed.connect(_on_stats_back_pressed)
	update_stats_display()

func _on_start_training_pressed():
	main_menu.hide()
	training_menu.show()

func _on_start_match_pressed():
	main_menu.hide()
	match_menu.show()

func _on_view_stats_pressed():
	main_menu.hide()
	stats_menu.show()
	update_stats_display()

func _on_quit_pressed():
	get_tree().quit()

func _on_training_back_pressed():
	training_menu.hide()
	main_menu.show()

func _on_match_back_pressed():
	match_menu.hide()
	main_menu.show()

func _on_stats_back_pressed():
	stats_menu.hide()
	main_menu.show()

func _on_drill_selected(drill_type: String):
	var training_scene = preload("res://scenes/training.tscn").instantiate()
	get_tree().root.add_child(training_scene)
	training_scene.start_training(drill_type)
	update_stats_display()

func _on_match_selected(match_type: String):
	var simulation_scene = preload("res://scenes/simulation.tscn").instantiate()
	get_tree().root.add_child(simulation_scene)
	simulation_scene.start_match(match_type)
	update_stats_display()

func get_available_drills() -> Array:
	return [
		{"type": "power", "name": "Power Training"},
		{"type": "accuracy", "name": "Accuracy Training"},
		{"type": "speed", "name": "Speed Training"},
		{"type": "reaction", "name": "Reaction Training"},
		{"type": "endurance", "name": "Endurance Training"},
		{"type": "technique_drive", "name": "Drive Practice"},
		{"type": "technique_dink", "name": "Dink Practice"},
		{"type": "technique_volley", "name": "Volley Practice"},
		{"type": "technique_lob", "name": "Lob Practice"},
		{"type": "technique_topspin", "name": "Topspin Practice"},
		{"type": "technique_slice", "name": "Slice Practice"},
		{"type": "technique_block", "name": "Block Practice"}
	]

func get_available_matches() -> Array:
	return [
		{"type": "casual", "name": "Casual Match"},
		{"type": "tournament", "name": "Tournament Match"},
		{"type": "practice", "name": "Practice Match"}
	]

func update_stats_display():
	var stats = player.get_player_summary()
	
	# Update level and experience
	$StatsMenu/LevelLabel.text = "Level: " + str(stats.level)
	$StatsMenu/ExpLabel.text = "Experience: " + str(stats.experience) + "/" + str(stats.experience_to_next_level)
	
	# Update base stats
	$StatsMenu/BaseStats/PowerBar.value = stats.stats.power
	$StatsMenu/BaseStats/AccuracyBar.value = stats.stats.accuracy
	$StatsMenu/BaseStats/SpeedBar.value = stats.stats.speed
	$StatsMenu/BaseStats/ReactionBar.value = stats.stats.reaction
	$StatsMenu/BaseStats/EnduranceBar.value = stats.stats.endurance
	
	# Update technique stats
	$StatsMenu/TechniqueStats/DriveBar.value = stats.stats.technique.drive
	$StatsMenu/TechniqueStats/DinkBar.value = stats.stats.technique.dink
	$StatsMenu/TechniqueStats/VolleyBar.value = stats.stats.technique.volley
	$StatsMenu/TechniqueStats/LobBar.value = stats.stats.technique.lob
	$StatsMenu/TechniqueStats/TopspinBar.value = stats.stats.technique.topspin
	$StatsMenu/TechniqueStats/SliceBar.value = stats.stats.technique.slice
	$StatsMenu/TechniqueStats/BlockBar.value = stats.stats.technique.block
	
	# Update history
	$StatsMenu/History/TrainingSessionsLabel.text = "Training Sessions: " + str(stats.training_sessions)
	$StatsMenu/History/MatchesPlayedLabel.text = "Matches Played: " + str(stats.matches_played)
	
	# Update stamina
	$StatsMenu/StaminaBar.value = stats.current_stamina
