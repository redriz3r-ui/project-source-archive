extends Node

var score = 0
var high_score = 0

func _ready():
	pass

func add_score(points: int):
	score += points
	if score > high_score:
		high_score = score 