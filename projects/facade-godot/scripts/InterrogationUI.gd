extends Control

@onready var trust_label = $MarginContainer/VBoxContainer/StatsPanel/HBoxContainer/TrustContainer/TrustLabel
@onready var trust_bar = $MarginContainer/VBoxContainer/StatsPanel/HBoxContainer/TrustContainer/TrustBar
@onready var tension_label = $MarginContainer/VBoxContainer/StatsPanel/HBoxContainer/TensionContainer/TensionLabel
@onready var tension_bar = $MarginContainer/VBoxContainer/StatsPanel/HBoxContainer/TensionContainer/TensionBar
@onready var timer_label = $MarginContainer/VBoxContainer/StatsPanel/HBoxContainer/TimerContainer/TimerLabel
@onready var timer_bar = $MarginContainer/VBoxContainer/StatsPanel/HBoxContainer/TimerContainer/TimerBar
@onready var suspect_dialogue = $MarginContainer/VBoxContainer/DialoguePanel/VBoxContainer/SuspectDialogue
@onready var choice_buttons = $MarginContainer/VBoxContainer/DialoguePanel/VBoxContainer/ChoiceButtons
@onready var replay_button = $MarginContainer/VBoxContainer/DialoguePanel/VBoxContainer/ChoiceButtons/ReplayButton

var state_manager: Node

func _ready() -> void:
	state_manager = get_parent()
	
	# Connect signals
	state_manager.trust_changed.connect(_on_trust_changed)
	state_manager.tension_changed.connect(_on_tension_changed)
	state_manager.time_changed.connect(_on_time_changed)
	state_manager.dialogue_advanced.connect(_on_dialogue_advanced)
	state_manager.game_over.connect(_on_game_over)
	
	# Connect button signals
	for i in range(choice_buttons.get_child_count()):
		var button = choice_buttons.get_child(i)
		if button.name.begins_with("Choice"):
			button.pressed.connect(_on_choice_pressed.bind(i))
	
	replay_button.pressed.connect(_on_replay_pressed)
	replay_button.visible = false
	
	# Initialize UI with first dialogue
	_on_dialogue_advanced(state_manager.get_current_dialogue())

func _on_trust_changed(new_value: int) -> void:
	trust_label.text = "Trust: %d" % new_value
	trust_bar.value = new_value

func _on_tension_changed(new_value: int) -> void:
	tension_label.text = "Tension: %d" % new_value
	tension_bar.value = new_value

func _on_time_changed(new_value: float) -> void:
	var minutes = int(new_value) / 60
	var seconds = int(new_value) % 60
	timer_label.text = "Time: %d:%02d" % [minutes, seconds]
	timer_bar.value = (new_value / 300.0) * 100  # 300 seconds = 5 minutes

func _on_dialogue_advanced(dialogue: Dictionary) -> void:
	if dialogue.is_empty():
		suspect_dialogue.text = "[Interrogation Over]\nNo more questions."
		for i in range(choice_buttons.get_child_count()):
			var button = choice_buttons.get_child(i)
			if button.name.begins_with("Choice"):
				button.visible = false
		replay_button.visible = true
		return
		
	suspect_dialogue.text = dialogue["suspect"]
	
	# Update choice buttons
	for i in range(choice_buttons.get_child_count()):
		var button = choice_buttons.get_child(i)
		if i < dialogue["choices"].size():
			button.text = dialogue["choices"][i]["text"]
			button.visible = true
		else:
			button.visible = false
	replay_button.visible = false

func _on_choice_pressed(choice_index: int) -> void:
	state_manager.make_choice(choice_index)

func _on_replay_pressed() -> void:
	# Reset the state manager and UI
	state_manager.trust = 50
	state_manager.tension = 50
	state_manager.time_remaining = 300.0
	state_manager.current_dialogue_index = 0
	state_manager.emit_signal("trust_changed", state_manager.trust)
	state_manager.emit_signal("tension_changed", state_manager.tension)
	state_manager.emit_signal("time_changed", state_manager.time_remaining)
	state_manager.emit_signal("dialogue_advanced", state_manager.get_current_dialogue()) 

func _on_game_over(reason: String) -> void:
	var ending_scene = preload("res://scenes/InterrogationEnding.tscn").instantiate()
	ending_scene.ending_type = reason
	get_tree().root.add_child(ending_scene)
	get_tree().current_scene.queue_free() 