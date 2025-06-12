extends Node2D

class_name ExplosionParticles

# Particle properties
var particles = []
const MAX_PARTICLES = 100
const PARTICLE_LIFETIME = 1.0
const GRAVITY = Vector2(0, 500)
const DRAG = 0.98

# Particle types
enum ParticleType { DEBRIS, SMOKE, SPARK }
const PARTICLE_COLORS = {
	ParticleType.DEBRIS: Color(0.5, 0.3, 0.2),
	ParticleType.SMOKE: Color(0.3, 0.3, 0.3),
	ParticleType.SPARK: Color(1.0, 0.7, 0.3)
}

# Flash effect
var flash_alpha = 0.0
const FLASH_DURATION = 0.1

# Mask properties
const MASK_HEIGHT = 200  # Height of the visible area
const VIGNETTE_SOFTNESS = 50  # How soft the vignette edge is

func _ready():
	# Don't create particles automatically
	pass

func create_explosion(center: Vector2):
	# Clear any existing particles
	particles.clear()
	
	# Create flash
	flash_alpha = 1.0
	
	# Create particles
	for i in range(MAX_PARTICLES):
		var particle = {
			"position": center + Vector2(
				randf_range(-50, 50),  # Keep initial spread smaller
				randf_range(-50, 0)    # Start particles above center
			),
			"velocity": Vector2(
				randf_range(-300, 300),
				randf_range(-400, -100)  # More upward initial velocity
			),
			"type": randi() % 3,  # Random type
			"size": randf_range(2, 6),
			"lifetime": PARTICLE_LIFETIME,
			"alpha": 1.0
		}
		particles.append(particle)
	
	# Make sure we're visible
	visible = true
	# Force a redraw
	queue_redraw()

func _process(delta):
	# Update flash
	if flash_alpha > 0:
		flash_alpha = max(0, flash_alpha - delta / FLASH_DURATION)
	
	# Update particles
	var i = 0
	while i < particles.size():
		var p = particles[i]
		
		# Update position and velocity
		p.position += p.velocity * delta
		p.velocity += GRAVITY * delta
		p.velocity *= DRAG
		
		# Update lifetime and alpha
		p.lifetime -= delta
		p.alpha = p.lifetime / PARTICLE_LIFETIME
		
		# Remove dead particles
		if p.lifetime <= 0:
			particles.remove_at(i)
		else:
			i += 1
	
	# Force redraw every frame while we have particles
	if particles.size() > 0:
		queue_redraw()

func get_vignette_alpha(pos: Vector2) -> float:
	# Calculate distance from center
	var dist_from_center = pos.length()
	
	# Calculate distance from mask line
	var dist_from_mask = abs(pos.y - MASK_HEIGHT)
	
	# Combine both distances for vignette effect
	var vignette = 1.0
	vignette *= smoothstep(0, VIGNETTE_SOFTNESS, MASK_HEIGHT - pos.y)  # Mask line fade
	vignette *= smoothstep(0, VIGNETTE_SOFTNESS, 200 - dist_from_center)  # Radial fade
	
	return vignette

func _draw():
	# Draw flash with vignette
	if flash_alpha > 0:
		# Draw multiple circles with decreasing alpha for vignette effect
		for i in range(3):
			var radius = 100 - i * 20
			var alpha = flash_alpha * (1.0 - float(i) / 3.0)
			draw_circle(Vector2.ZERO, radius, Color(1, 1, 1, alpha))
	
	# Draw particles with vignette
	for p in particles:
		if p.position.y < MASK_HEIGHT + VIGNETTE_SOFTNESS:  # Include softness in check
			var color = PARTICLE_COLORS[p.type]
			color.a = p.alpha * get_vignette_alpha(p.position)
			draw_circle(p.position, p.size, color)
	
	# Debug visualization (uncomment to see)
	# draw_line(Vector2(-500, MASK_HEIGHT), Vector2(500, MASK_HEIGHT), Color(1, 0, 0, 0.3))
	# draw_circle(Vector2.ZERO, 200, Color(1, 0, 0, 0.1)) 
