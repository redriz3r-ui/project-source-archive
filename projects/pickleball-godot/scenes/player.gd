extends Node2D

class_name PickleballPlayer

# Player Stats
var stats = {
	"power": 50,        # Affects shot speed and power
	"accuracy": 50,     # Affects shot placement
	"speed": 50,        # Affects movement speed
	"reaction": 50,     # Affects response time
	"endurance": 50,    # Affects stamina
	"technique": {      # Individual shot techniques
		"drive": 50,
		"dink": 50,
		"volley": 50,
		"lob": 50,
		"topspin": 50,
		"slice": 50,
		"block": 50
	}
}

# Experience and Leveling
var experience = 0
var level = 1
var experience_to_next_level = 100

# Training History
var training_history = []
var match_history = []

# Current State
var current_stamina = 100
var is_training = false
var current_training_type = ""

func _init():
	# Initialize player with default stats
	pass

func train(stat_type: String, duration: float) -> void:
	if current_stamina < 20:
		print("Not enough stamina to train!")
		return
		
	is_training = true
	current_training_type = stat_type
	current_stamina -= 20
	
	# Simulate training session
	await get_tree().create_timer(duration).timeout
	
	# Apply training results
	var improvement = randf_range(1.0, 3.0)
	if stat_type in stats:
		stats[stat_type] = min(100, stats[stat_type] + improvement)
	elif stat_type in stats.technique:
		stats.technique[stat_type] = min(100, stats.technique[stat_type] + improvement)
	
	# Record training session
	training_history.append({
		"type": stat_type,
		"duration": duration,
		"improvement": improvement,
		"timestamp": Time.get_unix_time_from_system()
	})
	
	# Gain experience
	gain_experience(10)
	
	is_training = false
	current_training_type = ""

func gain_experience(amount: float) -> void:
	experience += amount
	while experience >= experience_to_next_level:
		level_up()

func level_up() -> void:
	level += 1
	experience -= experience_to_next_level
	experience_to_next_level *= 1.5
	
	# Small stat boost on level up
	for stat in stats:
		if stat != "technique":
			stats[stat] = min(100, stats[stat] + 1)
	
	print("Level up! Now level ", level)

func record_match(match_data: Dictionary) -> void:
	match_history.append(match_data)

func get_stat(stat_type: String) -> float:
	if stat_type in stats:
		return stats[stat_type]
	elif stat_type in stats.technique:
		return stats.technique[stat_type]
	return 0.0

func get_training_history() -> Array:
	return training_history

func get_match_history() -> Array:
	return match_history

func get_player_summary() -> Dictionary:
	return {
		"level": level,
		"experience": experience,
		"experience_to_next_level": experience_to_next_level,
		"stats": stats,
		"current_stamina": current_stamina,
		"training_sessions": training_history.size(),
		"matches_played": match_history.size()
	} 