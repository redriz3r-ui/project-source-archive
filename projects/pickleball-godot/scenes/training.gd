extends Node2D

var player: PickleballPlayer
var current_drill = null
var drill_types = {
	"power": {
		"name": "Power Training",
		"description": "Practice powerful drives and smashes",
		"duration": 300.0,  # 5 minutes
		"stamina_cost": 20
	},
	"accuracy": {
		"name": "Accuracy Training",
		"description": "Focus on shot placement and precision",
		"duration": 300.0,
		"stamina_cost": 15
	},
	"speed": {
		"name": "Speed Training",
		"description": "Improve movement speed and agility",
		"duration": 240.0,  # 4 minutes
		"stamina_cost": 25
	},
	"reaction": {
		"name": "Reaction Training",
		"description": "Enhance reaction time and reflexes",
		"duration": 180.0,  # 3 minutes
		"stamina_cost": 20
	},
	"endurance": {
		"name": "Endurance Training",
		"description": "Build stamina and lasting power",
		"duration": 600.0,  # 10 minutes
		"stamina_cost": 30
	},
	"technique": {
		"drive": {
			"name": "Drive Practice",
			"description": "Master the drive shot",
			"duration": 240.0,
			"stamina_cost": 15
		},
		"dink": {
			"name": "Dink Practice",
			"description": "Perfect the soft kitchen shot",
			"duration": 240.0,
			"stamina_cost": 15
		},
		"volley": {
			"name": "Volley Practice",
			"description": "Improve quick air shots",
			"duration": 180.0,
			"stamina_cost": 20
		},
		"lob": {
			"name": "Lob Practice",
			"description": "Practice high arcing shots",
			"duration": 240.0,
			"stamina_cost": 15
		},
		"topspin": {
			"name": "Topspin Practice",
			"description": "Master dipping shots",
			"duration": 240.0,
			"stamina_cost": 15
		},
		"slice": {
			"name": "Slice Practice",
			"description": "Practice backspin shots",
			"duration": 240.0,
			"stamina_cost": 15
		},
		"block": {
			"name": "Block Practice",
			"description": "Improve defensive blocks",
			"duration": 180.0,
			"stamina_cost": 20
		}
	}
}

func _ready():
	# Initialize player
	player = PickleballPlayer.new()
	add_child(player)

func start_training(drill_type: String) -> void:
	if player.is_training:
		print("Already in training!")
		return
		
	if drill_type in drill_types:
		current_drill = drill_types[drill_type]
	elif drill_type in drill_types.technique:
		current_drill = drill_types.technique[drill_type]
	else:
		print("Invalid drill type!")
		return
		
	print("Starting ", current_drill.name)
	print(current_drill.description)
	
	# Start the training session
	await player.train(drill_type, current_drill.duration)
	
	print("Training complete!")
	print("Check your stats for improvements!")

func get_available_drills() -> Array:
	var available = []
	
	# Add basic drills
	for drill_type in drill_types:
		if drill_type != "technique":
			available.append({
				"type": drill_type,
				"name": drill_types[drill_type].name,
				"description": drill_types[drill_type].description
			})
	
	# Add technique drills
	for tech_type in drill_types.technique:
		available.append({
			"type": "technique_" + tech_type,
			"name": drill_types.technique[tech_type].name,
			"description": drill_types.technique[tech_type].description
		})
	
	return available

func get_player_stats() -> Dictionary:
	return player.get_player_summary()

func get_training_history() -> Array:
	return player.get_training_history() 
