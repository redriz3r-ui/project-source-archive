"""Composition root for long-lived application services."""

from dataclasses import dataclass
from collections.abc import Callable

from app.camera import CameraService
from app.config import Settings
from app.devices.buttplug_client import ButtplugClientLike, IntifaceGateway
from app.devices.registry import DeviceRegistry
from app.diagnostics import LatencyRecorder
from app.evaluation.service import EvaluationService
from app.evaluation.stroke import StrokeEvaluationService
from app.events import EventBus
from app.safety import SafetyController
from app.triggers import TriggerEngine
from app.triggers.automation import AutomationController
from app.triggers.hand_response import HandResponseController
from app.triggers.store import RuleStore
from app.vision import VisionService


@dataclass(slots=True)
class Services:
    settings: Settings
    events: EventBus
    camera: CameraService
    vision: VisionService
    devices: DeviceRegistry
    intiface: IntifaceGateway
    triggers: TriggerEngine
    safety: SafetyController
    automation: AutomationController
    hand_response: HandResponseController
    rules: RuleStore
    evaluation: EvaluationService
    stroke_evaluation: StrokeEvaluationService
    latency: LatencyRecorder


def build_services(
    settings: Settings, client_factory: Callable[[str], ButtplugClientLike] | None = None,
    camera: CameraService | None = None,
    rules: RuleStore | None = None,
    evaluation: EvaluationService | None = None,
    stroke_evaluation: StrokeEvaluationService | None = None,
) -> Services:
    devices = DeviceRegistry()
    latency = LatencyRecorder()
    safety = SafetyController(devices, settings, latency=latency)
    camera_service = camera or CameraService(settings)
    camera_service.set_latency_recorder(latency)
    gateway_ref: list[IntifaceGateway] = []
    automation = AutomationController(
        devices, safety,
        camera_running=lambda: camera_service.status == "running" and camera_service.mode == "oral",
        intiface_connected=lambda: bool(gateway_ref and gateway_ref[0].state.connected),
        latency=latency,
    )
    hand_response = HandResponseController(
        devices, safety,
        camera_running=lambda: camera_service.status == "running" and camera_service.mode == "hand",
        on_session_expired=camera_service.stop,
        intiface_connected=lambda: bool(gateway_ref and gateway_ref[0].state.connected),
    )
    def disconnected(identifier: str | None = None) -> None:
        safety.device_lost(identifier)
        automation.device_lost(identifier)
        hand_response.device_lost(identifier)

    gateway_options = {"client_factory": client_factory} if client_factory else {}
    gateway = IntifaceGateway(
        settings.intiface_url, devices,
        on_disconnect=disconnected,
        on_device_removed=disconnected,
        **gateway_options,
    )
    gateway_ref.append(gateway)
    return Services(
        settings=settings,
        events=EventBus(),
        camera=camera_service,
        vision=VisionService(),
        devices=devices,
        intiface=gateway,
        triggers=TriggerEngine(),
        safety=safety,
        automation=automation,
        hand_response=hand_response,
        rules=rules or RuleStore(),
        evaluation=evaluation or EvaluationService(),
        stroke_evaluation=stroke_evaluation or StrokeEvaluationService(),
        latency=latency,
    )
