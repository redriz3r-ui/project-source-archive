extends Node

var current_track: String = ""
var audio_player: AudioStreamPlayer2D

func _ready():
	audio_player = AudioStreamPlayer2D.new()
	add_child(audio_player)

func play_track(track_path: String):
	if track_path == current_track:
		return
		
	var stream = load(track_path)
	if stream:
		audio_player.stream = stream
		audio_player.play()
		current_track = track_path 