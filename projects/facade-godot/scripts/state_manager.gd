class_name StateManager
extends Node

# Relationship stats
var trust: float = 50.0
var tension: float = 50.0
var affection: float = 50.0
var communication: float = 50.0

# Game state
var current_day: int = 1
var current_time: String = "morning"
var current_location: String = "home"
var last_interaction: Dictionary = {}
var relationship_status: String = "neutral"  # neutral, friendly, romantic, hostile

# Test Scenario: "The Coffee Shop Incident"
var scenario_active: bool = true
var scenario_step: int = 0
var scenario_completed: bool = false

const SCENARIO_STEPS = {
	0: {
		"description": "You're at the coffee shop when you see Alex and Robin having an argument. They seem upset.",
		"location": "cafe",
		"time": "morning",
		"goal": "Help resolve the conflict between Alex and Robin",
		"success_condition": "Get both trust and communication above 70",
		"failure_condition": "Tension goes above 80"
	},
	1: {
		"description": "Alex is accusing Robin of forgetting their anniversary. Robin looks hurt and defensive.",
		"location": "cafe",
		"time": "morning",
		"goal": "Calm down Alex and comfort Robin",
		"success_condition": "Reduce tension below 40 and increase trust above 60",
		"failure_condition": "Affection drops below 30"
	},
	2: {
		"description": "The situation is tense. Both are looking to you for support.",
		"location": "cafe",
		"time": "morning",
		"goal": "Find a way to bring them together",
		"success_condition": "Get both trust and affection above 75",
		"failure_condition": "Communication drops below 40"
	}
}

# Character states
var alex_state: Dictionary = {
	"mood": "angry",
	"trust_level": 50.0,
	"affection_level": 50.0
}

var robin_state: Dictionary = {
	"mood": "sad",
	"trust_level": 50.0,
	"affection_level": 50.0
}

const RESPONSES = {
	"talk": {
		"alex": "I'm listening...",
		"robin": "Go on...",
		"both": "Tell us more...",
		"self": "What's on your mind?"
	},
	"accuse": {
		"alex": "I can't believe you're blaming me for this!",
		"robin": "Why are you pointing fingers at me?",
		"both": "This isn't helping anyone..."
	},
	"comfort": {
		"alex": "Thank you for understanding...",
		"robin": "I appreciate you saying that.",
		"both": "We'll get through this together."
	},
	"deflect": {
		"alex": "Don't try to change the subject.",
		"robin": "That's not what we're talking about.",
		"both": "We need to face this head on."
	},
	"confront": {
		"alex": "I need to know what's going on.",
		"robin": "Let's talk about this properly.",
		"both": "We should discuss this calmly."
	},
	"support": {
		"alex": "I'm here for you.",
		"robin": "We can work this out together.",
		"both": "Together we're stronger."
	},
	"neutral": {
		"alex": "I'm listening...",
		"robin": "Go on...",
		"both": "Tell us more..."
	},
	"romantic": {
		"alex": "I feel the same way...",
		"robin": "That's so sweet of you to say.",
		"both": "We make a great pair."
	},
	"hostile": {
		"alex": "I don't want to talk to you right now.",
		"robin": "Leave me alone.",
		"both": "We need some space."
	}
}

const LOCATIONS = {
	"home": "You're at home, a safe and comfortable space.",
	"cafe": "You're at the local cafe, a cozy place to talk.",
	"park": "You're in the park, surrounded by nature.",
	"work": "You're at work, a professional environment."
}

const TIMES = {
	"morning": "The sun is rising, bringing new possibilities.",
	"afternoon": "The day is in full swing.",
	"evening": "The sun is setting, creating a romantic atmosphere.",
	"night": "The stars are out, making everything feel more intimate."
}

# Signal for UI updates
signal state_changed

func _ready() -> void:
	update_relationship_status()
	if scenario_active:
		start_scenario()

func start_scenario() -> void:
	change_location(SCENARIO_STEPS[0].location)
	current_time = SCENARIO_STEPS[0].time
	update_ui()

func update_ui() -> void:
	# Emit signal to notify UI of state changes
	emit_signal("state_changed", get_state_summary())

func apply_intent(intent: Dictionary) -> void:
	last_interaction = intent
	
	# Update stats based on intent
	match intent.action:
		"romantic_love":
			affection += 10 * intent.intensity
			trust += 5 * intent.intensity
			tension -= 5 * intent.intensity
		"emotional_hate":
			affection -= 10 * intent.intensity
			trust -= 5 * intent.intensity
			tension += 10 * intent.intensity
		"social_offer":
			trust += 5 * intent.intensity
			communication += 5 * intent.intensity
		"social_ask":
			communication += 5 * intent.intensity
		"physical_hug", "physical_kiss":
			affection += 8 * intent.intensity
			trust += 3 * intent.intensity
		"emotional_apologize":
			tension -= 8 * intent.intensity
			trust += 5 * intent.intensity
		"talk":
			communication += 2 * intent.intensity
			tension -= 1 * intent.intensity
	
	# Update character states
	if intent.name != "":
		var character = intent.name
		if character == "alex":
			alex_state.trust_level += 5 * intent.intensity
			alex_state.affection_level += 5 * intent.intensity
		elif character == "robin":
			robin_state.trust_level += 5 * intent.intensity
			robin_state.affection_level += 5 * intent.intensity
	
	# Clamp all values between 0 and 100
	trust = clamp(trust, 0, 100)
	tension = clamp(tension, 0, 100)
	affection = clamp(affection, 0, 100)
	communication = clamp(communication, 0, 100)
	
	update_relationship_status()
	check_scenario_progress()
	update_ui()

func check_scenario_progress() -> void:
	if not scenario_active:
		return
		
	var current_step = SCENARIO_STEPS[scenario_step]
	
	# Check for success
	if current_step.success_condition == "Get both trust and communication above 70":
		if trust >= 70 and communication >= 70:
			advance_scenario()
	elif current_step.success_condition == "Reduce tension below 40 and increase trust above 60":
		if tension <= 40 and trust >= 60:
			advance_scenario()
	elif current_step.success_condition == "Get both trust and affection above 75":
		if trust >= 75 and affection >= 75:
			advance_scenario()
	
	# Check for failure
	if current_step.failure_condition == "Tension goes above 80":
		if tension >= 80:
			scenario_failed()
	elif current_step.failure_condition == "Affection drops below 30":
		if affection <= 30:
			scenario_failed()
	elif current_step.failure_condition == "Communication drops below 40":
		if communication <= 40:
			scenario_failed()

func advance_scenario() -> void:
	scenario_step += 1
	if scenario_step >= SCENARIO_STEPS.size():
		scenario_completed = true
		scenario_active = false
	else:
		var next_step = SCENARIO_STEPS[scenario_step]
		change_location(next_step.location)
		current_time = next_step.time
	update_ui()

func scenario_failed() -> void:
	scenario_active = false
	scenario_completed = false
	update_ui()

func update_relationship_status() -> void:
	if affection >= 75 and trust >= 75:
		relationship_status = "romantic"
	elif tension >= 75 or trust <= 25:
		relationship_status = "hostile"
	elif affection >= 50 and trust >= 50:
		relationship_status = "friendly"
	else:
		relationship_status = "neutral"

func get_response(intent: Dictionary) -> String:
	# Get the appropriate response based on the action and target
	var action = intent.action
	var target = intent.target
	
	# If the action isn't in our responses, default to "talk"
	if not RESPONSES.has(action):
		action = "talk"
	
	# If the target isn't in our responses for this action, default to "both"
	if not RESPONSES[action].has(target):
		target = "both"
	
	var response = RESPONSES[action][target]
	var location_desc = LOCATIONS[current_location]
	var time_desc = TIMES[current_time]
	
	if scenario_active:
		var current_step = SCENARIO_STEPS[scenario_step]
		return "%s\n\n%s\n%s\n\nGoal: %s" % [response, location_desc, time_desc, current_step.goal]
	
	return "%s\n\n%s\n%s" % [response, location_desc, time_desc]

func advance_time() -> void:
	match current_time:
		"morning":
			current_time = "afternoon"
		"afternoon":
			current_time = "evening"
		"evening":
			current_time = "night"
		"night":
			current_time = "morning"
			current_day += 1
	update_ui()

func change_location(new_location: String) -> void:
	if LOCATIONS.has(new_location):
		current_location = new_location
		update_ui()

func check_ending() -> String:
	# If scenario just completed, return the ending once
	if scenario_completed:
		scenario_completed = false  # Prevent repeated ending triggers
		return "scenario_success"
	elif not scenario_active and scenario_step >= SCENARIO_STEPS.size():
		return "scenario_success"
	elif not scenario_active and scenario_step < SCENARIO_STEPS.size():
		return "scenario_failure"
	elif current_day > 7:  # Game ends after 7 days
		if relationship_status == "romantic":
			return "happy_ending"
		elif relationship_status == "hostile":
			return "fallout"
		else:
			return "neutral_ending"
	return ""

func get_state_summary() -> Dictionary:
	return {
		"day": current_day,
		"time": current_time,
		"location": current_location,
		"relationship_status": relationship_status,
		"stats": {
			"trust": trust,
			"tension": tension,
			"affection": affection,
			"communication": communication
		},
		"character_states": {
			"alex": alex_state,
			"robin": robin_state
		},
		"scenario": {
			"active": scenario_active,
			"step": scenario_step,
			"completed": scenario_completed
		}
	} 
