extends Node2D

var player: PickleballPlayer
var opponent: PickleballPlayer
var current_match = null
var match_in_progress = false

# Match settings
var match_types = {
	"casual": {
		"name": "Casual Match",
		"description": "A friendly match with no stakes",
		"points_to_win": 11,
		"win_by_two": true
	},
	"tournament": {
		"name": "Tournament Match",
		"description": "A competitive tournament match",
		"points_to_win": 21,
		"win_by_two": true
	},
	"practice": {
		"name": "Practice Match",
		"description": "Focus on specific techniques",
		"points_to_win": 15,
		"win_by_two": false
	}
}

func _ready():
	# Initialize players
	player = PickleballPlayer.new()
	opponent = PickleballPlayer.new()
	add_child(player)
	add_child(opponent)

func start_match(match_type: String) -> void:
	if match_in_progress:
		print("Match already in progress!")
		return
		
	if not match_type in match_types:
		print("Invalid match type!")
		return
		
	current_match = match_types[match_type]
	match_in_progress = true
	
	print("Starting ", current_match.name)
	print(current_match.description)
	
	# Simulate the match
	await simulate_match()
	
	match_in_progress = false
	print("Match complete!")

func simulate_match() -> void:
	var player_score = 0
	var opponent_score = 0
	var serving = true  # true = player serves, false = opponent serves
	
	while true:
		# Simulate a point
		var point_winner = simulate_point(serving)
		
		if point_winner:
			player_score += 1
		else:
			opponent_score += 1
		
		# Check for match end
		if check_match_end(player_score, opponent_score):
			break
		
		# Switch serve every 2 points
		if (player_score + opponent_score) % 2 == 0:
			serving = !serving
	
	# Record match results
	var match_data = {
		"type": current_match.name,
		"player_score": player_score,
		"opponent_score": opponent_score,
		"winner": "player" if player_score > opponent_score else "opponent",
		"timestamp": Time.get_unix_time_from_system()
	}
	
	player.record_match(match_data)
	
	# Award experience based on match performance
	var exp_gain = calculate_experience_gain(match_data)
	player.gain_experience(exp_gain)

func simulate_point(serving: bool) -> bool:
	# Calculate point winner based on player stats and serving
	var player_win_chance = calculate_win_chance(serving)
	return randf() < player_win_chance

func calculate_win_chance(serving: bool) -> float:
	var base_chance = 0.5
	
	# Factor in player stats
	var player_power = player.get_stat("power") / 100.0
	var player_accuracy = player.get_stat("accuracy") / 100.0
	var player_technique = 0.0
	
	# Average technique stats
	for tech in player.stats.technique:
		player_technique += player.stats.technique[tech]
	player_technique /= player.stats.technique.size()
	player_technique /= 100.0
	
	# Calculate final chance
	var chance = base_chance
	chance += (player_power * 0.2)
	chance += (player_accuracy * 0.2)
	chance += (player_technique * 0.1)
	
	# Serving advantage
	if serving:
		chance += 0.1
	
	return clamp(chance, 0.1, 0.9)

func check_match_end(player_score: int, opponent_score: int) -> bool:
	if current_match.win_by_two:
		return (player_score >= current_match.points_to_win and player_score >= opponent_score + 2) or \
			   (opponent_score >= current_match.points_to_win and opponent_score >= player_score + 2)
	else:
		return player_score >= current_match.points_to_win or opponent_score >= current_match.points_to_win

func calculate_experience_gain(match_data: Dictionary) -> float:
	var base_exp = 50.0
	
	# Bonus for winning
	if match_data.winner == "player":
		base_exp *= 1.5
	
	# Bonus for close matches
	var score_diff = abs(match_data.player_score - match_data.opponent_score)
	if score_diff <= 2:
		base_exp *= 1.2
	
	# Bonus for tournament matches
	if match_data.type == "Tournament Match":
		base_exp *= 2.0
	
	return base_exp

func get_match_history() -> Array:
	return player.get_match_history()

func get_player_stats() -> Dictionary:
	return player.get_player_summary() 