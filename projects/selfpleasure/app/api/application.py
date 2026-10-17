"""Local dashboard and device control API."""

import asyncio
import json
import time
from dataclasses import asdict
from collections.abc import Callable
from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StrictBool
from typing import Literal
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings, settings as default_settings
from app.camera import CameraService, CameraStatus
from app.devices.buttplug_client import ButtplugClientLike
from app.devices.simulated import SimulatedDevice
from app.evaluation.service import EvaluationService
from app.evaluation.stroke import StrokeEvaluationService
from app.services import Services, build_services
from app.triggers.automation import AutomationRule, AutomationState
from app.triggers.hand_response import (
    HandResponseRule, HandResponseState, HandResponseMode, ResponseStyle,
    preview_hand_rule, validate_real_pilot_rule,
)
from app.triggers.patterns import Pattern, build_pattern
from app.triggers.session import SessionSettings
from app.triggers.store import RuleStore


class Selection(BaseModel):
    device_id: str


class ManualTest(BaseModel):
    intensity: float = 0.2
    duration: float = 1.0
    feature_index: int | None = None
    off_body_confirmed: StrictBool = False


class ManualEnable(BaseModel):
    off_body_confirmed: StrictBool = False


class OverlaySetting(BaseModel):
    enabled: bool


class CameraInput(BaseModel):
    index: int


class CameraMode(BaseModel):
    mode: Literal["oral", "hand"]


class HandAxis(BaseModel):
    base_x: float
    base_y: float
    endpoint_x: float
    endpoint_y: float
    marker_anchor: bool = False


class MarkerPoint(BaseModel):
    x: float
    y: float


class RoiSelection(BaseModel):
    x: float
    y: float
    width: float
    height: float


class CalibrationSettings(BaseModel):
    mode: Literal["marker", "roi"]
    near_distance_mouth_widths: float
    sensitivity: float


class SessionOptions(BaseModel):
    opening_pulses: int = 2
    middle_pulses: int = 4
    buildup_pulses: int = 3
    include_buildup: bool = False


class AutomationSettings(BaseModel):
    feature_index: int | None = None
    intensity: float = 0.2
    duration: float = 2.0
    cooldown: float = 1.0
    minimum_confidence: float = 0.6
    rule_id: str | None = None
    pattern: Literal["SHORT_PULSE", "GENTLE_PULSE", "RHYTHMIC_PULSE", "GRADUAL_RAMP"] = "SHORT_PULSE"
    session: SessionOptions | None = None


class RuleSettings(BaseModel):
    name: str
    trigger: Literal["INTERACTION_ACTIVE"] = "INTERACTION_ACTIVE"
    action: Literal["VIBRATE"] = "VIBRATE"
    pattern: Literal["SHORT_PULSE", "GENTLE_PULSE", "RHYTHMIC_PULSE", "GRADUAL_RAMP"] = "SHORT_PULSE"
    feature_index: int
    intensity: float = 0.2
    duration: float = 2.0
    cooldown: float = 1.0
    minimum_confidence: float = 0.6


class RuleEnabled(BaseModel):
    enabled: bool


class EvaluationConsent(BaseModel):
    consent: bool


class EvaluationLabel(BaseModel):
    label: Literal["INTENDED", "NO_INTERACTION", "UNCERTAIN"]


class StrokeEvaluationLabel(BaseModel):
    label: Literal["STROKES", "NO_STROKES", "UNCERTAIN"]


class HandResponseSettings(BaseModel):
    feature_index: int = 0
    intensity: float = 0.2
    duration: float = 0.18
    cooldown: float = 0.3
    minimum_confidence: float = 0.5
    mode: Literal["ONE_RESPONSE", "MOTION_SHAPED", "FOLLOW_MOVEMENT"] = "ONE_RESPONSE"
    style: Literal["GENTLE", "CRISP", "RAMP"] = "CRISP"
    real_pilot: StrictBool = False
    manual_preflight_confirmed: StrictBool = False
    physical_power_off_ready: StrictBool = False


class HandPreflightTest(BaseModel):
    feature_index: int
    physical_power_off_ready: StrictBool


class TabletopArm(BaseModel):
    feature_index: int
    off_body_confirmed: StrictBool = False
    manual_preflight_confirmed: StrictBool = False
    physical_power_off_ready: StrictBool = False


def create_app(
    settings: Settings = default_settings,
    client_factory: Callable[[str], ButtplugClientLike] | None = None,
    camera: CameraService | None = None,
    rules: RuleStore | None = None,
    evaluation: EvaluationService | None = None,
    stroke_evaluation: StrokeEvaluationService | None = None,
) -> FastAPI:
    services = build_services(settings, client_factory, camera, rules, evaluation, stroke_evaluation)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        def enqueue(event):
            if queue.full():
                if services.camera.mode == "hand":
                    if services.stroke_evaluation.active:
                        services.stroke_evaluation.fail("Stroke event queue overflow; evaluation paused")
                    if services.hand_response.state in {
                        HandResponseState.ARMED, HandResponseState.ACTIVE, HandResponseState.COOLDOWN,
                    }:
                        asyncio.create_task(services.hand_response.fail("Stroke event queue overflow"))
                elif services.evaluation.active:
                    services.evaluation.fail("Vision event queue overflow; evaluation stopped recording")
                else:
                    asyncio.create_task(services.automation.fail("Vision event queue overflow"))
            else:
                queue.put_nowait(event)

        async def capture_evaluation(event):
            if event.topic == "camera_stopped":
                services.evaluation.note_camera_stopped(event.payload.get("observed_at"))
                services.stroke_evaluation.note_camera_stopped()
            else:
                services.evaluation.ingest(event)
                services.stroke_evaluation.ingest(event)
        services.camera.set_event_sink(lambda event: loop.call_soon_threadsafe(enqueue, event))
        for topic in ("interaction_started", "interaction_continued", "interaction_ended",
                      "tracking_lost", "vision_observation", "camera_stopped",
                      "stroke_observation", "stroke_started", "stroke_updated", "stroke_completed",
                      "stroke_tracking_lost"):
            if topic not in {"stroke_observation", "stroke_started", "stroke_updated",
                             "stroke_completed", "stroke_tracking_lost"}:
                services.events.subscribe(topic, services.automation.handle_event)
            services.events.subscribe(topic, capture_evaluation)
            if topic in {"stroke_observation", "stroke_started", "stroke_updated",
                         "stroke_completed", "stroke_tracking_lost", "camera_stopped"}:
                services.events.subscribe(topic, services.hand_response.handle_event)
        async def consume_events():
            while True:
                event = await queue.get()
                try:
                    await services.events.publish(event)
                except Exception as exc:
                    if services.camera.mode == "hand" and services.stroke_evaluation.active:
                        services.stroke_evaluation.fail(f"Stroke event handling failed: {exc}")
                    elif services.camera.mode == "hand":
                        if services.hand_response.state in {
                            HandResponseState.ARMED, HandResponseState.ACTIVE,
                            HandResponseState.COOLDOWN,
                        }:
                            await services.hand_response.fail(f"Stroke event handling failed: {exc}")
                    elif services.evaluation.active:
                        services.evaluation.fail(f"Evaluation event handling failed: {exc}")
                    else:
                        await services.automation.fail(f"Vision event handling failed: {exc}")

        consumer = asyncio.create_task(consume_events())
        try:
            yield
        finally:
            services.camera.set_event_sink(None)
            services.evaluation.discard()  # Unsaved numeric drafts never persist on shutdown.
            services.stroke_evaluation.discard()
            services.safety.exit_evaluation_mode()
            await services.hand_response.shutdown()
            await services.automation.shutdown()
            await services.safety.shutdown()
            await services.camera.shutdown()
            await services.intiface.shutdown()
            consumer.cancel()
            try:
                await consumer
            except asyncio.CancelledError:
                pass

    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    application.state.services = services
    application.state.desktop_exit = None
    web_dir = files("app.web")
    application.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    @application.middleware("http")
    async def reject_foreign_origins(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site API access rejected"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            allowed_origins = {
                f"http://127.0.0.1:{settings.port}",
                f"http://localhost:{settings.port}",
            }
            if origin and origin not in allowed_origins:
                return JSONResponse({"detail": "Foreign origin rejected"}, status_code=403)
        response = await call_next(request)
        if (request.url.path.startswith("/api/evaluation") or
                request.url.path.startswith("/api/stroke-evaluation") or
                request.url.path.startswith("/api/hand/") or
                request.url.path.startswith("/api/diagnostics") or
                request.url.path in {"/evaluate", "/hand/evaluate"}):
            response.headers["Cache-Control"] = "no-store"
        return response

    def require_not_evaluating(current: Services) -> None:
        if current.evaluation.active or current.stroke_evaluation.active:
            raise HTTPException(409, "Device control is disabled during evaluation")

    @application.get("/", include_in_schema=False)
    async def hand_home() -> FileResponse:
        return FileResponse(web_dir.joinpath("unified.html"))

    @application.get("/dashboard", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(web_dir.joinpath("index.html"))

    @application.get("/devices", include_in_schema=False)
    async def device_page() -> FileResponse:
        return FileResponse(web_dir.joinpath("devices.html"))

    @application.get("/camera", include_in_schema=False)
    async def camera_page() -> FileResponse:
        return FileResponse(web_dir.joinpath("camera.html"))

    @application.get("/hand", include_in_schema=False)
    async def hand_page() -> FileResponse:
        return FileResponse(web_dir.joinpath("hand.html"))

    @application.get("/hand/evaluate", include_in_schema=False)
    async def hand_evaluation_page() -> FileResponse:
        return FileResponse(web_dir.joinpath("hand-evaluate.html"))

    @application.get("/hand/session", include_in_schema=False)
    async def hand_session_page() -> FileResponse:
        return FileResponse(web_dir.joinpath("hand-session.html"))

    @application.get("/rules", include_in_schema=False)
    async def rules_page() -> FileResponse:
        return FileResponse(web_dir.joinpath("rules.html"))

    @application.get("/evaluate", include_in_schema=False)
    async def evaluation_page() -> FileResponse:
        return FileResponse(web_dir.joinpath("evaluate.html"))

    @application.get("/api/status")
    async def status(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        return {
            "application": "running",
            "intiface": "connected" if current.intiface.state.connected else "not_connected",
            "intiface_error": current.intiface.state.error,
            "scanning": current.intiface.state.scanning,
            "camera": current.camera.status,
            "device": current.devices.selected_id,
            "activation_enabled": current.safety.activation_enabled,
            "test_running": current.safety.running,
            "control_error": current.safety.last_error,
            "rules_error": current.rules.load_error,
            "emergency_stop_latched": current.safety.emergency_stop_latched,
            "evaluation_active": current.evaluation.active,
            "max_intensity": current.settings.max_intensity,
            "max_duration": current.settings.max_duration_seconds,
            "real_device_output_enabled": current.safety.real_device_output_enabled,
            "real_device_manual_bench_enabled": current.safety.real_device_manual_bench_enabled,
            "privacy": {"records_video": False, "uploads_video": False},
            "desktop_app": request.app.state.desktop_exit is not None,
        }

    @application.post("/api/application/quit")
    async def quit_desktop(request: Request) -> dict[str, bool]:
        callback = request.app.state.desktop_exit
        if callback is None:
            raise HTTPException(404, "Desktop launcher is not active")
        current: Services = request.app.state.services
        await current.hand_response.disarm()
        await current.automation.disarm()
        await current.safety.stop("shutdown")
        await current.camera.stop()
        asyncio.get_running_loop().call_later(0.25, callback)
        return {"quitting": True}

    @application.get("/api/diagnostics/latency")
    async def latency_report(request: Request) -> dict[str, object]:
        return request.app.state.services.latency.report()

    @application.get("/api/diagnostics/latency/traces")
    async def latency_traces(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        return {"clock_domain": "host_monotonic_ns", "numeric_only": True,
                "traces": current.latency.traces(),
                "stop_traces": current.latency.stop_traces()}

    @application.post("/api/diagnostics/latency/start")
    async def latency_start(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        current.latency.start()
        return current.latency.report()

    @application.post("/api/diagnostics/latency/stop")
    async def latency_stop(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        current.latency.stop()
        return current.latency.report()

    @application.get("/api/devices")
    async def devices(request: Request) -> list[dict[str, object]]:
        current: Services = request.app.state.services
        return [
            {
                "id": device.identifier,
                "name": device.name,
                "simulated": device.simulated,
                "capabilities": device.capabilities,
                "vibration_features": list(getattr(current.devices.get(device.identifier), "vibration_features", ())),
                "can_vibrate": any(value.lower() == "vibrate" for value in device.capabilities),
                "status": device.status,
            }
            for device in current.devices.list()
        ]

    @application.get("/api/dashboard")
    async def dashboard_data(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        return {
            "status": await status(request),
            "camera": current.camera.snapshot(),
            "automation": current.automation.snapshot(),
            "hand_response": current.hand_response.snapshot(),
            "devices": await devices(request),
            "rules": current.rules.list(),
        }

    @application.get("/api/evaluation/status")
    async def evaluation_status(request: Request) -> dict[str, object]:
        return request.app.state.services.evaluation.snapshot()

    @application.get("/api/stroke-evaluation/status")
    async def stroke_evaluation_status(request: Request) -> dict[str, object]:
        return request.app.state.services.stroke_evaluation.snapshot()

    @application.post("/api/stroke-evaluation/start")
    async def stroke_evaluation_start(data: EvaluationConsent, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.camera.mode != "hand" or current.camera.status != CameraStatus.RUNNING:
            raise HTTPException(409, "Start Hand Stroke camera mode first")
        if current.automation.state not in {
            AutomationState.DISARMED, AutomationState.EMERGENCY_STOP, AutomationState.ERROR,
        } or current.hand_response.state in {
            HandResponseState.ARMED, HandResponseState.ACTIVE, HandResponseState.COOLDOWN,
        } or current.evaluation.active:
            raise HTTPException(409, "Disarm automation and stop oral evaluation first")
        try:
            current.safety.enter_evaluation_mode()
            try:
                return current.stroke_evaluation.start(data.consent)
            except Exception:
                current.safety.exit_evaluation_mode()
                raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/stroke-evaluation/label")
    async def stroke_evaluation_label(data: StrokeEvaluationLabel, request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.stroke_evaluation.label(data.label)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/stroke-evaluation/mark")
    async def stroke_evaluation_mark(request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.stroke_evaluation.mark_stroke()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/stroke-evaluation/stop")
    async def stroke_evaluation_stop(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        try:
            result = current.stroke_evaluation.stop()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        current.safety.exit_evaluation_mode()
        return result

    @application.post("/api/stroke-evaluation/discard")
    async def stroke_evaluation_discard(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.evaluation.active:
            raise HTTPException(409, "Stop oral evaluation before discarding a stroke draft")
        current.stroke_evaluation.discard()
        current.safety.exit_evaluation_mode()
        return current.stroke_evaluation.snapshot()

    @application.post("/api/stroke-evaluation/save")
    async def stroke_evaluation_save(data: EvaluationConsent, request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.stroke_evaluation.save(data.consent)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, f"Could not save numeric stroke session: {exc}") from exc

    @application.get("/api/stroke-evaluation/draft")
    async def stroke_evaluation_draft(request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.stroke_evaluation.draft_detail()
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @application.get("/api/stroke-evaluation/sessions")
    async def stroke_evaluation_sessions(request: Request) -> list[dict[str, object]]:
        return request.app.state.services.stroke_evaluation.list_saved()

    @application.get("/api/stroke-evaluation/sessions/{identifier}")
    async def stroke_evaluation_session(identifier: str, request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.stroke_evaluation.saved(identifier)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @application.delete("/api/stroke-evaluation/sessions/{identifier}")
    async def stroke_evaluation_delete(identifier: str, request: Request) -> dict[str, object]:
        try:
            request.app.state.services.stroke_evaluation.delete(identifier)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"deleted": True}

    @application.post("/api/evaluation/start")
    async def evaluation_start(data: EvaluationConsent, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.camera.status != CameraStatus.RUNNING or current.camera.mode != "oral":
            raise HTTPException(409, "Start oral camera mode before evaluation")
        if current.automation.state not in {
            AutomationState.DISARMED, AutomationState.EMERGENCY_STOP, AutomationState.ERROR,
        }:
            raise HTTPException(409, "Disarm automation before evaluation")
        if current.evaluation.active:
            raise HTTPException(409, "Evaluation is already active")
        if data.consent is not True:
            raise HTTPException(422, "Explicit consent to collect numeric observations is required")
        try:
            current.safety.enter_evaluation_mode()
            try:
                return current.evaluation.start(data.consent)
            except Exception:
                current.safety.exit_evaluation_mode()
                raise
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @application.post("/api/evaluation/label")
    async def evaluation_label(data: EvaluationLabel, request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.evaluation.set_label(data.label)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/evaluation/stop")
    async def evaluation_stop(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        try:
            result = current.evaluation.stop()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        current.safety.exit_evaluation_mode()
        return result

    @application.post("/api/evaluation/discard")
    async def evaluation_discard(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.stroke_evaluation.active:
            raise HTTPException(409, "Stop stroke evaluation before discarding an oral draft")
        current.evaluation.discard()
        current.safety.exit_evaluation_mode()
        return current.evaluation.snapshot()

    @application.post("/api/evaluation/save")
    async def evaluation_save(data: EvaluationConsent, request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.evaluation.save(data.consent)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, f"Could not save local evaluation: {exc}") from exc

    @application.get("/api/evaluation/draft")
    async def evaluation_draft(request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.evaluation.draft_detail()
        except KeyError as exc:
            raise HTTPException(404, "No numeric draft to review") from exc

    @application.get("/api/evaluation/sessions")
    async def evaluation_sessions(request: Request) -> list[dict[str, object]]:
        return request.app.state.services.evaluation.list_saved()

    @application.get("/api/evaluation/sessions/{identifier}")
    async def evaluation_session(identifier: str, request: Request) -> dict[str, object]:
        try:
            return request.app.state.services.evaluation.saved(identifier)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, "Evaluation session not found") from exc

    @application.delete("/api/evaluation/sessions/{identifier}")
    async def evaluation_delete(identifier: str, request: Request) -> dict[str, object]:
        try:
            request.app.state.services.evaluation.delete(identifier)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, "Evaluation session not found") from exc
        return {"deleted": True}

    @application.post("/api/intiface/connect")
    async def connect(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        try:
            await current.intiface.connect()
        except Exception as exc:
            raise HTTPException(503, f"Intiface connection failed: {exc}") from exc
        return {"connected": True}

    @application.post("/api/intiface/scan")
    async def scan(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        if current.safety.running:
            raise HTTPException(409, "Stop the current test before scanning")
        try:
            await current.intiface.scan(current.settings.scan_seconds)
        except Exception as exc:
            raise HTTPException(503, f"Intiface scan failed: {exc}") from exc
        return {"devices": len(current.devices.list())}

    @application.post("/api/intiface/disconnect")
    async def disconnect(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        await current.hand_response.disarm("device_lost")
        await current.automation.disarm()
        await current.intiface.shutdown()
        return {"connected": False}

    @application.post("/api/devices/simulated", status_code=201)
    async def initialize_simulator(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        if current.hand_response.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                           HandResponseState.COOLDOWN}:
            raise HTTPException(409, "Disarm hand responses before replacing the simulator")
        device = current.devices.add(SimulatedDevice())
        return {"id": device.identifier, "name": device.name, "status": device.status}

    @application.post("/api/devices/select")
    async def select_device(selection: Selection, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        if current.automation.state not in {AutomationState.DISARMED, AutomationState.EMERGENCY_STOP, AutomationState.ERROR}:
            raise HTTPException(409, "Disarm automation before selecting another device")
        if current.hand_response.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                           HandResponseState.COOLDOWN}:
            raise HTTPException(409, "Disarm hand responses before selecting another device")
        if current.safety.running:
            raise HTTPException(409, "Stop the current test before selecting another device")
        current.safety.activation_enabled = False
        try:
            device = current.devices.select(selection.device_id)
        except KeyError as exc:
            raise HTTPException(404, "Device not found") from exc
        return {"id": device.identifier, "name": device.name}

    @application.post("/api/control/enable")
    async def enable_one_test(request: Request,
                              data: ManualEnable | None = None) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        if current.automation.state not in {AutomationState.DISARMED, AutomationState.EMERGENCY_STOP, AutomationState.ERROR}:
            raise HTTPException(409, "Disarm automation before manual testing")
        if current.hand_response.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                           HandResponseState.COOLDOWN}:
            raise HTTPException(409, "Disarm hand responses before manual testing")
        try:
            current.safety.enable_activation(
                off_body_confirmed=data.off_body_confirmed if data else False)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"enabled": True}

    @application.post("/api/control/test", status_code=202)
    async def test_vibration(test: ManualTest, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        if current.automation.state not in {AutomationState.DISARMED, AutomationState.EMERGENCY_STOP, AutomationState.ERROR}:
            raise HTTPException(409, "Disarm automation before manual testing")
        if current.hand_response.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                           HandResponseState.COOLDOWN}:
            raise HTTPException(409, "Disarm hand responses before manual testing")
        try:
            await current.safety.start_test(test.intensity, test.duration, test.feature_index,
                                            off_body_confirmed=test.off_body_confirmed)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"started": True, "intensity": test.intensity, "duration": test.duration}

    @application.post("/api/control/stop")
    async def stop(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        await current.hand_response.disarm("user_stop")
        await current.automation.disarm()
        return {"stopped": True}

    @application.post("/api/emergency-stop")
    async def emergency_stop(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        await current.hand_response.emergency_stop()
        await current.automation.emergency_stop()
        return {"stopped": True, "activation_enabled": False}

    @application.get("/api/automation/status")
    async def automation_status(request: Request) -> dict[str, object]:
        return request.app.state.services.automation.snapshot()

    @application.get("/api/hand/response/status")
    async def hand_response_status(request: Request) -> dict[str, object]:
        return request.app.state.services.hand_response.snapshot()

    @application.get("/api/hand/session/status")
    async def hand_session_status(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        camera_state = current.camera.snapshot()
        selected = (current.devices.get(current.devices.selected_id)
                    if current.devices.selected_id else None)
        features = tuple(getattr(selected, "vibration_features", ())) if selected else ()
        quality = camera_state["hand"]["tracking_confidence"]
        stroke = camera_state["stroke"]
        ready = (camera_state["status"] == "running" and camera_state["mode"] == "hand"
                 and camera_state["hand"]["state"] == "TRACKED" and quality >= 0.5
                 and stroke is not None and stroke["hand_position"] is not None
                 and time.monotonic_ns() - stroke["timestamp_ns"] <=
                 current.hand_response.TABLETOP_TRACKING_GAP_NS)
        return {
            "camera": camera_state, "response": current.hand_response.snapshot(),
            "selected_device": ({"id": selected.info.identifier, "name": selected.info.name,
                                 "simulated": selected.info.simulated,
                                 "vibration_features": features} if selected else None),
            "available_devices": [{"id": device.identifier, "name": device.name,
                                    "simulated": device.simulated,
                                    "vibration_features": tuple(getattr(
                                        current.devices.get(device.identifier), "vibration_features", ()))}
                                   for device in current.devices.list()],
            "intiface_connected": current.intiface.state.connected,
            "manual_test_running": current.safety.running,
            "manual_activation_enabled": current.safety.activation_enabled,
            "manual_control_error": current.safety.last_error,
            "tracking_ready": ready,
            "real_pilot_available": bool(selected and not selected.info.simulated
                                         and current.intiface.state.connected and features
                                         and current.safety.real_device_output_enabled),
            "real_device_output_enabled": current.safety.real_device_output_enabled,
            "real_device_manual_bench_enabled": current.safety.real_device_manual_bench_enabled,
            "manual_max_intensity": current.safety.max_intensity,
            "manual_max_duration": current.safety.max_duration_seconds,
            "general_real_mode_supported": False,
        }

    @application.post("/api/hand/session/preview")
    async def hand_session_preview(data: HandResponseSettings) -> dict[str, object]:
        try:
            rule = HandResponseRule(data.feature_index, data.intensity, data.duration,
                                    data.cooldown, data.minimum_confidence,
                                    HandResponseMode(data.mode), ResponseStyle(data.style))
            if data.real_pilot:
                validate_real_pilot_rule(rule)
            return preview_hand_rule(rule, settings.max_intensity, settings.max_duration_seconds)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @application.post("/api/hand/session/preflight-test", status_code=202)
    async def hand_preflight_test(data: HandPreflightTest, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        selected = (current.devices.get(current.devices.selected_id)
                    if current.devices.selected_id else None)
        if not current.safety.real_device_output_enabled:
            raise HTTPException(409, "Real-device output is locked after a failed physical stop")
        if not data.physical_power_off_ready:
            raise HTTPException(409, "Confirm physical power-off is within reach")
        if not current.intiface.state.connected or selected is None or selected.info.simulated:
            raise HTTPException(409, "Connect and select a real device first")
        if data.feature_index not in getattr(selected, "vibration_features", ()):
            raise HTTPException(409, "Select an advertised vibration feature")
        if current.hand_response.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                           HandResponseState.COOLDOWN} or current.automation.state in {
                                               AutomationState.ARMED, AutomationState.ACTIVE,
                                               AutomationState.COOLDOWN}:
            raise HTTPException(409, "Disarm automation before manual preflight")
        try:
            current.safety.enable_activation()
            await current.safety.start_test(intensity=0.2, duration=0.1,
                                            feature_index=data.feature_index)
        except (RuntimeError, ValueError) as exc:
            await current.safety.stop("preflight_failed")
            raise HTTPException(409, str(exc)) from exc
        return {"started": True, "intensity": 0.2, "duration": 0.1}

    @application.post("/api/hand/session/pause")
    async def hand_session_pause(request: Request) -> dict[str, object]:
        controller = request.app.state.services.hand_response
        try:
            await controller.pause()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return controller.snapshot()

    @application.post("/api/hand/session/finish")
    async def hand_session_finish(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        await current.hand_response.disarm()
        await current.automation.disarm()
        await current.camera.stop()
        current.stroke_evaluation.note_camera_stopped()
        return {"response": current.hand_response.snapshot(),
                "camera": current.camera.snapshot(), "finished": True}

    @application.post("/api/hand/response/arm")
    async def hand_response_arm(data: HandResponseSettings, request: Request) -> dict[str, object]:
        return await arm_hand(data, request, managed=False)

    async def arm_hand(data: HandResponseSettings, request: Request,
                       *, managed: bool) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        if data.real_pilot and not managed:
            raise HTTPException(409, "Real hand pilot requires the managed session page")
        if data.real_pilot and not (data.manual_preflight_confirmed and data.physical_power_off_ready):
            raise HTTPException(409, "Confirm the physical stop control and successful short manual preflight")
        if current.automation.state in {AutomationState.ARMED, AutomationState.ACTIVE,
                                        AutomationState.COOLDOWN}:
            raise HTTPException(409, "Disarm oral automation before arming hand responses")
        try:
            await current.hand_response.arm(HandResponseRule(
                feature_index=data.feature_index, intensity=data.intensity,
                duration=data.duration, cooldown=data.cooldown,
                minimum_confidence=data.minimum_confidence, mode=HandResponseMode(data.mode),
                style=ResponseStyle(data.style),
            ), session_managed=managed, real_pilot=data.real_pilot)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return current.hand_response.snapshot()

    @application.post("/api/hand/session/arm")
    async def hand_session_arm(data: HandResponseSettings, request: Request) -> dict[str, object]:
        return await arm_hand(data, request, managed=True)

    @application.post("/api/tabletop/arm")
    async def tabletop_arm(data: TabletopArm, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        if not (data.off_body_confirmed and data.manual_preflight_confirmed
                and data.physical_power_off_ready):
            raise HTTPException(409, "Confirm off-body setup, physical power-off access, and successful physical stop preflight")
        selected = current.devices.get(current.devices.selected_id) if current.devices.selected_id else None
        if selected is None or selected.info.simulated or not current.intiface.state.connected:
            raise HTTPException(409, "Select a connected Intiface device for tabletop mode")
        if current.automation.state in {AutomationState.ARMED, AutomationState.ACTIVE,
                                        AutomationState.COOLDOWN}:
            raise HTTPException(409, "Disarm other automation before tabletop mode")
        try:
            await current.hand_response.arm(HandResponseRule(
                feature_index=data.feature_index, intensity=0.2, duration=0.08,
                cooldown=0.08, minimum_confidence=0.5,
                mode=HandResponseMode.FOLLOW_MOVEMENT, style=ResponseStyle.CRISP,
            ), session_managed=True, real_pilot=True, tabletop=True)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return current.hand_response.snapshot()

    @application.post("/api/hand/session/heartbeat")
    async def hand_session_heartbeat(request: Request) -> dict[str, object]:
        controller = request.app.state.services.hand_response
        try:
            controller.heartbeat()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"lease_active": True}

    @application.post("/api/hand/response/disarm")
    async def hand_response_disarm(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        await current.hand_response.disarm()
        return current.hand_response.snapshot()

    @application.get("/api/patterns/preview")
    async def pattern_preview(pattern: Pattern = Pattern.SHORT_PULSE,
                              intensity: float = 0.2, duration: float = 2.0) -> dict[str, object]:
        try:
            if duration > min(settings.max_duration_seconds, 2.0):
                raise ValueError("Pattern duration exceeds the configured limit")
            steps = build_pattern(pattern, intensity, duration, settings.max_intensity)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"pattern": pattern, "steps": [step.as_dict() for step in steps],
                "duration": duration, "maximum_intensity": intensity,
                "device_command_sent": False}

    @application.post("/api/automation/arm")
    async def automation_arm(data: AutomationSettings, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_not_evaluating(current)
        controller = current.automation
        try:
            if data.rule_id is not None:
                selected = current.rules.get(data.rule_id)
                if selected is None or not selected.enabled:
                    raise RuntimeError("Choose an enabled rule before arming")
                rule = selected.automation_rule()
            else:
                if data.feature_index is None:
                    raise ValueError("Choose a vibration feature or enabled rule")
                rule = AutomationRule(
                    feature_index=data.feature_index, intensity=data.intensity,
                    duration=data.duration, cooldown=data.cooldown,
                    minimum_confidence=data.minimum_confidence, pattern=Pattern(data.pattern),
                )
            session = SessionSettings(**data.session.model_dump()) if data.session else None
            await controller.arm(rule, session=session)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return controller.snapshot()

    @application.post("/api/automation/disarm")
    async def automation_disarm(request: Request) -> dict[str, object]:
        controller = request.app.state.services.automation
        await controller.disarm()
        return controller.snapshot()

    def require_rules_disarmed(current: Services) -> None:
        if current.automation.state in {AutomationState.ARMED, AutomationState.ACTIVE, AutomationState.COOLDOWN}:
            raise HTTPException(409, "Disarm automation before changing rules")

    @application.get("/api/rules")
    async def list_rules(request: Request) -> list[dict[str, object]]:
        return request.app.state.services.rules.list()

    @application.post("/api/rules", status_code=201)
    async def create_rule(data: RuleSettings, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_rules_disarmed(current)
        try:
            rule = current.rules.create(**data.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, f"Could not save local rule: {exc}") from exc
        return asdict(rule)

    @application.put("/api/rules/{identifier}")
    async def update_rule(identifier: str, data: RuleSettings, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_rules_disarmed(current)
        try:
            rule = current.rules.update(identifier, **data.model_dump())
        except KeyError as exc:
            raise HTTPException(404, "Rule not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, f"Could not save local rule: {exc}") from exc
        return asdict(rule)

    @application.post("/api/rules/{identifier}/enabled")
    async def enable_rule(identifier: str, data: RuleEnabled, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_rules_disarmed(current)
        try:
            rule = current.rules.set_enabled(identifier, data.enabled)
        except KeyError as exc:
            raise HTTPException(404, "Rule not found") from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, f"Could not save local rule: {exc}") from exc
        return asdict(rule)

    @application.delete("/api/rules/{identifier}")
    async def delete_rule(identifier: str, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        require_rules_disarmed(current)
        try:
            current.rules.delete(identifier)
        except KeyError as exc:
            raise HTTPException(404, "Rule not found") from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, f"Could not save local rule: {exc}") from exc
        return {"deleted": True}

    @application.get("/api/camera/status")
    async def camera_status(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        return current.camera.snapshot()

    @application.post("/api/camera/start", status_code=202)
    async def camera_start(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        try:
            current.camera.start()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "starting"}

    @application.post("/api/camera/stop")
    async def camera_stop(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.hand_response.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                           HandResponseState.COOLDOWN}:
            await current.hand_response.disarm()
        if not current.evaluation.active and not current.stroke_evaluation.active:
            await current.automation.disarm()
        await current.camera.stop()
        current.evaluation.note_camera_stopped()
        current.stroke_evaluation.note_camera_stopped()
        return current.camera.snapshot()

    @application.post("/api/camera/overlay")
    async def camera_overlay(setting: OverlaySetting, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        current.camera.set_overlay(setting.enabled)
        return {"overlay_enabled": setting.enabled}

    @application.post("/api/camera/input")
    async def camera_input(setting: CameraInput, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        try:
            current.camera.set_camera_index(setting.index)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"camera_index": current.camera.camera_index}

    @application.post("/api/camera/mode")
    async def camera_mode(data: CameraMode, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.evaluation.active or current.stroke_evaluation.active or current.automation.state in {
            AutomationState.ARMED, AutomationState.ACTIVE, AutomationState.COOLDOWN,
        } or current.hand_response.state in {
            HandResponseState.ARMED, HandResponseState.ACTIVE, HandResponseState.COOLDOWN,
        }:
            raise HTTPException(409, "Stop evaluation and disarm automation before changing camera mode")
        try:
            current.camera.set_mode(data.mode)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"mode": current.camera.mode}

    @application.get("/api/hand/calibration")
    async def hand_calibration(request: Request) -> dict[str, object]:
        return asdict(request.app.state.services.camera.hand_calibration.snapshot())

    @application.post("/api/hand/calibration")
    async def set_hand_calibration(data: HandAxis, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.stroke_evaluation.active:
            raise HTTPException(409, "Stop stroke evaluation before changing calibration")
        if current.hand_response.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                           HandResponseState.COOLDOWN}:
            raise HTTPException(409, "Disarm hand responses before changing calibration")
        if current.camera.mode != "hand" or current.camera.status != CameraStatus.RUNNING:
            raise HTTPException(409, "Start Hand Stroke camera mode before calibrating its axis")
        try:
            return current.camera.update_hand_calibration(
                base=(data.base_x, data.base_y),
                endpoint=(data.endpoint_x, data.endpoint_y),
                marker_anchor=data.marker_anchor,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @application.get("/api/hand/events")
    async def hand_events(request: Request) -> list[dict[str, object]]:
        return request.app.state.services.camera.stroke_events()

    @application.get("/api/calibration")
    async def calibration(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        return current.camera.calibration_snapshot()

    @application.post("/api/calibration/settings")
    async def calibration_settings(data: CalibrationSettings, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        try:
            return current.camera.update_calibration(**data.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @application.post("/api/calibration/mouth")
    async def calibration_mouth(request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        try:
            return current.camera.calibrate_mouth()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/calibration/marker")
    async def calibration_marker(point: MarkerPoint, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.stroke_evaluation.active:
            raise HTTPException(409, "Stop stroke evaluation before changing the marker")
        if current.hand_response.state in {HandResponseState.ARMED, HandResponseState.ACTIVE,
                                           HandResponseState.COOLDOWN}:
            raise HTTPException(409, "Disarm hand responses before changing the marker")
        try:
            return current.camera.calibrate_marker(point.x, point.y)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/calibration/roi")
    async def calibration_roi(selection: RoiSelection, request: Request) -> dict[str, object]:
        current: Services = request.app.state.services
        if current.camera.status != CameraStatus.RUNNING:
            raise HTTPException(409, "Start the camera before selecting an object region")
        try:
            return current.camera.update_calibration(
                mode="roi", manual_roi=(selection.x, selection.y, selection.width, selection.height),
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @application.get("/api/interaction/events")
    async def interaction_events(request: Request, after: int = 0) -> list[dict[str, object]]:
        current: Services = request.app.state.services
        return current.camera.events_after(max(0, after))

    @application.get("/api/interaction/events/stream")
    async def interaction_event_stream(request: Request, after: int = 0) -> StreamingResponse:
        current: Services = request.app.state.services
        if current.camera.status not in {CameraStatus.STARTING, CameraStatus.RUNNING}:
            raise HTTPException(409, "Start the camera first")

        async def events():
            sequence = max(0, after)
            while not await request.is_disconnected():
                changes = await asyncio.to_thread(current.camera.wait_for_event, sequence, 1.0)
                for change in changes:
                    sequence = change["sequence"]
                    yield f"id: {sequence}\nevent: interaction\ndata: {json.dumps(change)}\n\n"
                if current.camera.status not in {CameraStatus.STARTING, CameraStatus.RUNNING}:
                    break

        return StreamingResponse(
            events(), media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @application.get("/api/camera/stream")
    async def camera_stream(request: Request) -> StreamingResponse:
        current: Services = request.app.state.services
        if current.camera.status not in {CameraStatus.STARTING, CameraStatus.RUNNING}:
            raise HTTPException(409, "Start the camera first")

        async def frames():
            sequence = 0
            while not await request.is_disconnected():
                result = await asyncio.to_thread(current.camera.wait_for_frame, sequence, 1.0)
                if result is None:
                    if current.camera.status not in {CameraStatus.STARTING, CameraStatus.RUNNING}:
                        break
                    continue
                sequence, image = result
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + image + b"\r\n"

        return StreamingResponse(
            frames(), media_type="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    return application
