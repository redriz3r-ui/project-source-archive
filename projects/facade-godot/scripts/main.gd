extends Node

@onready var input_field = $UI/MarginContainer/VBoxContainer/InputContainer/InputField
@onready var response_label = $UI/MarginContainer/VBoxContainer/ResponseLabel
@onready var stats_label = $UI/MarginContainer/VBoxContainer/StatsLabel
@onready var time_label = $UI/MarginContainer/VBoxContainer/TimeLocationContainer/TimeLabel
@onready var location_label = $UI/MarginContainer/VBoxContainer/TimeLocationContainer/LocationLabel
@onready var scenario_label = $UI/MarginContainer/VBoxContainer/ScenarioLabel

var gpt_client: GPTClient
var state_manager: StateManager
var game_ended: bool = false

func _ready() -> void:
	gpt_client = GPTClient.new()
	add_child(gpt_client)
	
	state_manager = StateManager.new()
	add_child(state_manager)
	
	# Connect signals
	input_field.text_submitted.connect(_on_input_submitted)
	state_manager.state_changed.connect(_on_state_changed)
	
	# Initial UI update
	_on_state_changed(state_manager.get_state_summary())
	print("[MAIN] Game initialized.")

func _on_input_submitted(text: String) -> void:
	if game_ended:
		print("[MAIN] Input ignored: game has ended.")
		return
	if text.strip_edges().is_empty():
		print("[MAIN] Empty input ignored.")
		return
	print("[MAIN] User input: %s" % text)
	
	# Handle special commands
	if text.begins_with("go to "):
		var location = text.substr(6).strip_edges().to_lower()
		print("[MAIN] Command: go to %s" % location)
		state_manager.change_location(location)
		_check_and_handle_ending()
		return
	elif text == "next":
		print("[MAIN] Command: next (advance time)")
		state_manager.advance_time()
		_check_and_handle_ending()
		return
	
	# Parse the input
	var intent = gpt_client.parse_input(text)
	print("[MAIN] Parsed intent: %s" % str(intent))
	
	# Apply the intent and get response
	state_manager.apply_intent(intent)
	var response = state_manager.get_response(intent)
	print("[MAIN] Response: %s" % response)
	
	# Update response label
	response_label.text = response
	
	# Clear input field
	input_field.text = ""

	# Check for ending after every input
	_check_and_handle_ending()

func _check_and_handle_ending() -> void:
	var ending = state_manager.check_ending()
	if ending != "":
		print("[MAIN] Ending detected: %s" % ending)
		_handle_ending(ending)

func _on_state_changed(state_summary: Dictionary) -> void:
	print("[MAIN] State changed: %s" % str(state_summary))
	# Update stats
	stats_label.text = "Trust: %d\nTension: %d\nAffection: %d\nCommunication: %d" % [
		state_summary.stats.trust,
		state_summary.stats.tension,
		state_summary.stats.affection,
		state_summary.stats.communication
	]
	
	# Update time and location
	time_label.text = "Day %d - %s" % [state_summary.day, state_summary.time]
	location_label.text = "Location: %s" % state_summary.location
	
	# Update scenario information if active
	if state_summary.scenario.active:
		var current_step = state_summary.scenario.step
		var step_info = state_manager.SCENARIO_STEPS[current_step]
		print("[MAIN] Scenario step: %d, Goal: %s" % [current_step + 1, step_info.goal])
		scenario_label.text = "Scenario Step %d\nGoal: %s" % [
			current_step + 1,
			step_info.goal
		]
	else:
		print("[MAIN] No active scenario.")
		scenario_label.text = ""

func _handle_ending(ending: String) -> void:
	game_ended = true
	input_field.editable = false
	print("[MAIN] Game ended with ending: %s" % ending)
	match ending:
		"scenario_success":
			response_label.text = "Congratulations! You successfully resolved the conflict between Alex and Robin!"
		"scenario_failure":
			response_label.text = "The situation escalated beyond repair. The conflict couldn't be resolved."
		"happy_ending":
			response_label.text = "You've built a strong and loving relationship!"
		"fallout":
			response_label.text = "The relationship has deteriorated beyond repair."
		"neutral_ending":
			response_label.text = "The relationship remains unchanged."
