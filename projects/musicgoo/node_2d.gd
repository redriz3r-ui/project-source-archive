extends Node2D

@onready var player = $AudioStreamPlayer2D
@onready var spectrum = AudioServer.get_bus_effect_instance(0, 0)
@onready var wave = $Wave
@onready var camera = $Camera2D 

const PHI = 1.6180339887 # Golden ratio

var points = 100 # More points for smoother wave
var base_amplitude = 40.0 # Taller baseline
var base_frequency = 0.1 # More compressed waves
var loud_amplitude = base_amplitude * PHI 
var loud_frequency = base_frequency * PHI 
var wave_speed = 3.0 # Faster animation speed
var loudness_threshold = 0.02 # More sensitive to sound energy

var current_amplitude = base_amplitude 
var current_frequency = base_frequency 

func _ready():
	var music_file = load("res://aboutu.wav") # Convert MP3 to OGG
	if music_file:
		player.stream = music_file
		player.play()
		print("Music Loaded")
	else:
		print("Audio file failed to load!")
	
	if wave == null:
		print("Wave node not found!")
		return

	wave.points = PackedVector2Array()
	wave.width = 2.5 # Thicker line
	wave.default_color = Color(0.0, 1.0, 1.0)

	var viewport_size = get_viewport_rect().size
	for i in range(points):
		var x = i * (viewport_size.x / (points - 1))
		var y = viewport_size.y / 2
		wave.add_point(Vector2(x, y))

	var bg = ColorRect.new()
	bg.size = viewport_size
	bg.color = Color(0.05, 0.05, 0.05) # Even darker background
	add_child(bg)
	move_child(bg, 0)

	if camera:
		camera.position = viewport_size / 2
		camera.zoom = Vector2(1, 1)
		camera.make_current()

func _process(delta):
	if spectrum is AudioEffectInstance:
		var low_freq = spectrum.get_magnitude_for_frequency_range(0.0, 150.0).length()
		var mid_freq = spectrum.get_magnitude_for_frequency_range(150.0, 500.0).length()
		var high_freq = spectrum.get_magnitude_for_frequency_range(500.0, 2000.0).length()
		
		var energy = (low_freq * 1.2) + (mid_freq * 0.8) + (high_freq * 0.5) 
		print("Energy: ", energy) # Debugging
		
		var is_loud = energy > loudness_threshold

		current_amplitude = lerp(current_amplitude, loud_amplitude if is_loud else base_amplitude, 0.15)
		current_frequency = lerp(current_frequency, loud_frequency if is_loud else base_frequency, 0.15)
		
		var viewport_size = get_viewport_rect().size
		var time = Time.get_ticks_msec() * 0.001

		var new_points = PackedVector2Array()
		for i in range(points):
			var x = i * (viewport_size.x / (points - 1))
			
			# Sinusoidal wave with a distortion effect
			var distortion = sin(time * 2 + i * 0.1) * (energy * 5)
			var y = viewport_size.y / 2 + (current_amplitude + distortion) * sin(current_frequency * x + time * wave_speed)
			
			y = clamp(y, 20, viewport_size.y - 20)
			new_points.append(Vector2(x, y))

		wave.points = new_points
		wave.default_color = Color(0.0, 0.7 + (energy * 2), 1.0 - (energy * 2)) # Color shift based on intensity
