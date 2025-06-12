extends Node

signal trust_changed(new_value: int)
signal tension_changed(new_value: int)
signal time_changed(new_value: float)
signal dialogue_advanced(new_dialogue: Dictionary)
signal game_over(reason: String)

var trust: int = 50
var tension: int = 50
var time_remaining: float = 300.0  # 5 minutes in seconds
var current_dialogue_index: int = 0
var current_path: String = "main"  # Track which dialogue path we're on

# Debug tracking
var path_history: Array = []
var choice_history: Array = []

# Sample dialogue data with branching paths
var dialogue_data = {
	"main": [
		{
			"suspect": "What do you want from me?",
			"choices": [
				{ "text": "Just trying to understand you", "trust": 10, "tension": -5, "next_path": "trusting" },
				{ "text": "Where were you last night?", "trust": 0, "tension": 5, "next_path": "suspicious" },
				{ "text": "We already know you lied", "trust": -5, "tension": 15, "next_path": "hostile" }
			]
		}
	],
	"trusting": [
		{
			"suspect": "I was at home, alone. Why do you care?",
			"choices": [
				{ "text": "We just want the truth.", "trust": 5, "tension": 0 },
				{ "text": "Your neighbor saw you leave.", "trust": -5, "tension": 10 },
				{ "text": "Help us help you.", "trust": 10, "tension": -5 }
			]
		},
		{
			"suspect": "Fine, I left for a bit. But I didn't do anything!",
			"choices": [
				{ "text": "Then tell us what really happened.", "trust": 10, "tension": 0 },
				{ "text": "We can check the cameras.", "trust": 0, "tension": 10 },
				{ "text": "Lying won't help you.", "trust": -10, "tension": 15 }
			]
		}
	],
	"suspicious": [
		{
			"suspect": "I was at the store. I needed some air.",
			"choices": [
				{ "text": "Why didn't you say so before?", "trust": 5, "tension": 0 },
				{ "text": "What did you buy?", "trust": 0, "tension": 5 },
				{ "text": "Are you sure that's all?", "trust": -5, "tension": 10 }
			]
		},
		{
			"suspect": "I bought some snacks. That's it. Can I go now?",
			"choices": [
				{ "text": "Not yet. We have more questions.", "trust": 0, "tension": 5 },
				{ "text": "If you're innocent, help us understand.", "trust": 10, "tension": -5 },
				{ "text": "People saw you arguing outside.", "trust": -5, "tension": 10 }
			]
		}
	],
	"hostile": [
		{
			"suspect": "I don't have to tell you anything!",
			"choices": [
				{ "text": "Calm down, we're just trying to help.", "trust": 5, "tension": -5 },
				{ "text": "Your attitude isn't helping.", "trust": -5, "tension": 10 },
				{ "text": "We have evidence against you.", "trust": -10, "tension": 15 }
			]
		},
		{
			"suspect": "Fine! I was at the bar, okay? Happy now?",
			"choices": [
				{ "text": "Why didn't you say so earlier?", "trust": 5, "tension": -5 },
				{ "text": "Who were you with?", "trust": 0, "tension": 5 },
				{ "text": "You're still hiding something.", "trust": -10, "tension": 15 }
			]
		}
	]
}

func _ready() -> void:
	print("[DEBUG] Interrogation started")
	print("[DEBUG] Initial state - Trust: %d, Tension: %d" % [trust, tension])
	_print_ending_requirements()

func _print_ending_requirements() -> void:
	print("\n[DEBUG] Ending Requirements:")
	print("- Confession: Trust >= 80, Tension <= 30")
	print("- Breakdown: Trust <= 20, Tension >= 80")
	print("- Partial: Trust >= 60, Tension >= 60")
	print("- Neutral: Default ending if no other conditions met")
	print("- Tension Max: Tension reaches 100")
	print("- Trust Max: Trust reaches 100")
	print("- Timeout: Time runs out\n")

func _process(delta: float) -> void:
	if time_remaining > 0:
		time_remaining -= delta
		emit_signal("time_changed", time_remaining)
		if time_remaining <= 0:
			_handle_timeout()

func _handle_timeout() -> void:
	print("[DEBUG] Timeout reached - Ending interrogation")
	emit_signal("game_over", "timeout")

func make_choice(choice_index: int) -> void:
	var current_path_data = dialogue_data[current_path]
	if current_dialogue_index >= current_path_data.size():
		return
		
	var current_dialogue = current_path_data[current_dialogue_index]
	var choice = current_dialogue["choices"][choice_index]
	
	# Track choice history
	choice_history.append({
		"path": current_path,
		"dialogue_index": current_dialogue_index,
		"choice": choice["text"],
		"trust_change": choice["trust"],
		"tension_change": choice["tension"]
	})
	
	# Update stats
	var old_trust = trust
	var old_tension = tension
	trust = clamp(trust + choice["trust"], 0, 100)
	tension = clamp(tension + choice["tension"], 0, 100)
	
	# Debug print
	print("\n[DEBUG] Choice made: %s" % choice["text"])
	print("[DEBUG] Stats changed - Trust: %d -> %d, Tension: %d -> %d" % [
		old_trust, trust,
		old_tension, tension
	])
	print("[DEBUG] Current path: %s, Dialogue index: %d" % [current_path, current_dialogue_index])
	
	# Emit signals for UI updates
	emit_signal("trust_changed", trust)
	emit_signal("tension_changed", tension)
	
	# Check for path change
	if choice.has("next_path"):
		var old_path = current_path
		current_path = choice["next_path"]
		current_dialogue_index = 0
		path_history.append(old_path)
		print("[DEBUG] Path changed: %s -> %s" % [old_path, current_path])
		emit_signal("dialogue_advanced", dialogue_data[current_path][0])
		return
	
	# Advance dialogue
	current_dialogue_index += 1
	if current_dialogue_index < current_path_data.size():
		emit_signal("dialogue_advanced", current_path_data[current_dialogue_index])
	else:
		_handle_dialogue_end()
	
	# Check for game over conditions
	if tension >= 100:
		_handle_tension_max()
	elif trust >= 100:
		_handle_trust_max()

func _handle_dialogue_end() -> void:
	var ending = _determine_ending()
	print("\n[DEBUG] Dialogue ended")
	print("[DEBUG] Final stats - Trust: %d, Tension: %d" % [trust, tension])
	print("[DEBUG] Path history: %s" % str(path_history))
	print("[DEBUG] Ending determined: %s" % ending)
	emit_signal("game_over", ending)

func _determine_ending() -> String:
	var ending = "neutral"
	
	# Adjusted thresholds for achievability
	if trust >= 80 and tension <= 40:
		ending = "confession"
		print("[DEBUG] Confession ending triggered - High trust, low/moderate tension")
	elif trust <= 25 and tension >= 80:
		ending = "breakdown"
		print("[DEBUG] Breakdown ending triggered - Low trust, high tension")
	elif trust >= 60 and tension >= 55:
		ending = "partial"
		print("[DEBUG] Partial ending triggered - Moderate trust and tension")
	
	return ending

func _handle_tension_max() -> void:
	print("[DEBUG] Tension max reached - Ending interrogation")
	emit_signal("game_over", "tension_max")

func _handle_trust_max() -> void:
	print("[DEBUG] Trust max reached - Ending interrogation")
	emit_signal("game_over", "trust_max")

func get_current_dialogue() -> Dictionary:
	var current_path_data = dialogue_data[current_path]
	if current_dialogue_index < current_path_data.size():
		return current_path_data[current_dialogue_index]
	return {} 
