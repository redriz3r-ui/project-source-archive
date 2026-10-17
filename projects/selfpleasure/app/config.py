"""Application configuration with privacy-preserving defaults."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "SelfPleasure"
    host: str = "127.0.0.1"
    port: int = 8000
    intiface_url: str = "ws://127.0.0.1:12345"
    max_intensity: float = 0.5
    max_duration_seconds: float = 5.0
    command_timeout_seconds: float = 2.0
    stop_timeout_seconds: float = 2.0
    scan_seconds: float = 3.0
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_target_fps: int = 24
    camera_enabled: bool = False
    # Physical stop failed in a supervised 0.1-second real-device preflight.
    # Keep all real output disabled until that hardware path is independently validated.
    real_device_output_enabled: bool = False
    # Explicit process-only off-body manual diagnostics; never authorizes automation.
    real_device_manual_bench_enabled: bool = False


settings = Settings()
