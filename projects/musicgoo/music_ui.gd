extends Control

@onready var audio_player = get_node("/root/NightSky/AudioPlayer")  # Find AudioPlayer dynamically
@onready var song_label = get_node("/root/NightSky/MusicUI/VBOX/SongLabel")
@onready var artist_label = get_node("/root/NightSky/MusicUI/VBOX/ArtistLabel")
@onready var time_label = get_node("root/nightsky/MusicUI/VBOX/TimeLabel")
@onready var progress_bar = get_node("root/nightsky/MusicUI/VBOX/ProgressBar")


var song_length = 180.0  # Default to 3 minutes if length is unknown

func _ready():
	# Check if UI elements exist before setting them
	if song_label:
		song_label.text = "Now Playing: Unknown Track"
	if artist_label:
		artist_label.text = "Artist: Unknown"
	if progress_bar:
		progress_bar.max_value = song_length  # Default 3 mins

func _process(delta):
	if audio_player and audio_player.playing:
		var current_time = audio_player.get_playback_position()
		
		if progress_bar:
			progress_bar.value = current_time  # Sync bar with song

		if time_label:
			time_label.text = "%02d:%02d / %02d:%02d" % [
				int(current_time) / 60, int(current_time) % 60,
				int(song_length) / 60, int(song_length) % 60
			]
