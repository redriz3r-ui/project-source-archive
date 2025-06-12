extends Control

@onready var ending_label = $EndingLabel
@onready var restart_button = $RestartButton

var ending_type: String

func _ready() -> void:
	# Set ending text based on type
	match ending_type:
		"confession":
			ending_label.text = "Through building trust and maintaining a calm atmosphere, the suspect has confessed to their involvement. They seem relieved to have finally told the truth."
		"breakdown":
			ending_label.text = "The intense pressure and lack of trust has caused the suspect to break down emotionally. They're now willing to talk, but the situation has become more complicated."
		"partial":
			ending_label.text = "The suspect has revealed some information, but their trust and tension levels suggest they're still holding back. This might be enough to proceed, but there are still unanswered questions."
		"neutral":
			ending_label.text = "The interrogation has ended without any significant breakthrough. The suspect remains guarded, and you'll need to find other ways to uncover the truth."
		"tension_max":
			ending_label.text = "The situation has become too tense. The suspect has become completely uncooperative, and the interrogation must end here."
		"trust_max":
			ending_label.text = "You've gained the suspect's complete trust. They're now willing to cooperate fully with the investigation."
		"timeout":
			ending_label.text = "Time has run out. The interrogation must end here, leaving many questions unanswered."
		"reconciliation":
			ending_label.text = "Through understanding and support, you've helped Alex and Robin reconcile their differences. They've learned to trust each other again."
		"fallout":
			ending_label.text = "The tension has become too much. Alex and Robin's relationship has reached a breaking point, and they've decided to go their separate ways."

func _on_restart_button_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/main.tscn")
