extends CPUParticles2D

@onready var spectrum = AudioServer.get_bus_effect_instance(0, 0)

func _process(delta):
	if spectrum is AudioEffectInstance:
		var mid_freq = spectrum.get_magnitude_for_frequency_range(200.0, 1000.0).length()
		self.modulate.a = clamp(0.5 + mid_freq, 0.2, 1.0)  # Stars brighten based on mid frequencies
