extends Control

@onready var ending_label = $EndingLabel
@onready var restart_button = $RestartButton

var ending_type: String

func _ready() -> void:
	match ending_type:
		"confession":
			ending_label.text = "The suspect confesses! Your approach built enough trust to break through their defenses."
		"breakdown":
			ending_label.text = "The suspect breaks down under pressure. The truth comes out, but at a cost."
		"partial":
			ending_label.text = "You got some answers, but the suspect is still holding back. Partial success."
		"neutral":
			ending_label.text = "The interrogation ends with no breakthrough. The suspect remains guarded."
		"tension_max":
			ending_label.text = "Tension reached its peak. The suspect refuses to cooperate further."
		"trust_max":
			ending_label.text = "You've gained the suspect's complete trust. They are now fully cooperative."
		"timeout":
			ending_label.text = "Time's up! The interrogation ends before you could get a clear answer."
		_:
			ending_label.text = "The interrogation is over."

func _on_RestartButton_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/InterrogationScene.tscn") 