extends Node2D

const CLOUD_COUNT = 10  # More clouds for a full nebula effect
const CLOUD_MAX_RADIUS = 500.0  
const CLOUD_MIN_RADIUS = 200.0  
const FOV = 90.0  
const Z_FAR = 2000.0  
const Z_NEAR = 200.0  
const WARP_SPEED = 1.5  

var viewport_size
var camera_position = Vector3.ZERO  
var clouds = []

class NebulaCloud:
	var position: Vector3  
	var size: float  
	var alpha: float  
	var oscillation_speed: float  
	var phase_shift: float  

	func _init(pos: Vector3, sz: float):
		position = pos  
		size = sz  
		alpha = randf_range(0.3, 0.6)  
		oscillation_speed = randf_range(0.5, 2.0)  
		phase_shift = randf_range(0, 2 * PI)  

func _ready():
	viewport_size = get_viewport_rect().size  
	z_index = 2  

	for i in range(CLOUD_COUNT):
		var pos_3d = Vector3(
			randf_range(-viewport_size.x * 2, viewport_size.x * 2),
			randf_range(-viewport_size.y * 2, viewport_size.y * 2),
			randf_range(Z_NEAR, Z_FAR)  
		)
		var size = randf_range(CLOUD_MIN_RADIUS, CLOUD_MAX_RADIUS)  
		clouds.append(NebulaCloud.new(pos_3d, size))  

func _process(delta):
	for cloud in clouds:
		cloud.position.z -= WARP_SPEED * delta  # Move clouds slowly for depth
		if cloud.position.z < Z_NEAR:  
			cloud.position.z = Z_FAR  
		cloud.position.x += sin(cloud.phase_shift + Time.get_ticks_msec() * 0.001 * cloud.oscillation_speed) * 5.0  
		cloud.position.y += cos(cloud.phase_shift + Time.get_ticks_msec() * 0.001 * cloud.oscillation_speed) * 5.0  

	queue_redraw()  

func _draw():
	for cloud in clouds:
		var relative_pos = cloud.position - camera_position  
		var screen_pos = project_3d_to_2d(relative_pos)  
		var depth_factor = (Z_FAR - cloud.position.z) / (Z_FAR - Z_NEAR)  

		draw_wireframe_circle(screen_pos, cloud.size * depth_factor, cloud.alpha * depth_factor)  

func draw_wireframe_circle(center: Vector2, radius: float, alpha: float):
	var segments = 10  
	var step = TAU / segments  
	var points = []

	for i in range(segments + 1):
		var angle = i * step  
		var point = center + Vector2(cos(angle), sin(angle)) * radius  
		points.append(point)  

	for i in range(points.size() - 1):
		draw_line(points[i], points[i + 1], Color(0.5, 0.2, 0.8, alpha), 1)  

func project_3d_to_2d(pos_3d):
	if pos_3d.z <= Z_NEAR:
		return Vector2(-1000, -1000)  

	var fov_rad = deg_to_rad(FOV)  
	var scale = (viewport_size.x / 2.0) / (pos_3d.z * tan(fov_rad / 2.0))  

	return Vector2(
		viewport_size.x / 2 + pos_3d.x * scale,
		viewport_size.y / 2 + pos_3d.y * scale
	)
