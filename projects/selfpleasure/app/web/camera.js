const byId = (id) => document.getElementById(id);
let streamAttached = false;
let pending = false;
let eventSource = null;
let lastEventSequence = 0;
let calibrationLoaded = false;
let dragStart = null;
let selectedAutomationDevice = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function report(error) { byId("message").textContent = error.message || String(error); }
function percent(value) { return `${Math.round(value * 100)}%`; }
function say(value, suffix = "") { return value == null ? "—" : `${value}${suffix}`; }

function applyCalibration(calibration) {
  byId("tracking-mode").value = calibration.mode;
  byId("near-distance").value = calibration.near_distance_mouth_widths;
  byId("sensitivity").value = calibration.sensitivity;
  byId("near-distance-value").value = Number(calibration.near_distance_mouth_widths).toFixed(1);
  byId("sensitivity-value").value = Number(calibration.sensitivity).toFixed(2);
  byId("marker-calibration").textContent = calibration.marker_hue == null
    ? "Marker color not calibrated." : `Marker hue calibrated: ${calibration.marker_hue} / 180.`;
  byId("mouth-calibration").textContent = calibration.mouth_width_reference == null
    ? "No mouth reference saved." : `Neutral mouth reference saved; width ${calibration.mouth_width_reference.toFixed(3)} of image.`;
  byId("selection-help").textContent = calibration.mode === "marker"
    ? "Hold the marker in view, then click its center in the preview."
    : "Drag a rectangle around the visible object in the preview. Redraw it if tracking is lost.";
}

function appendEvent(change) {
  if (change.sequence <= lastEventSequence) return;
  lastEventSequence = change.sequence;
  const item = document.createElement("li");
  const time = new Date(change.timestamp).toLocaleTimeString();
  item.textContent = `${time} · ${change.previous_state} → ${change.state} · score ${change.confidence.toFixed(2)}`;
  byId("event-log").prepend(item);
  while (byId("event-log").children.length > 50) byId("event-log").lastElementChild.remove();
}

function connectEvents() {
  if (eventSource) return;
  eventSource = new EventSource(`/api/interaction/events/stream?after=${lastEventSequence}`);
  eventSource.addEventListener("interaction", (event) => {
    appendEvent(JSON.parse(event.data));
  });
}

function disconnectEvents() {
  if (eventSource) eventSource.close();
  eventSource = null;
}

async function refresh() {
  const state = await api("/api/camera/status");
  const active = state.status === "starting" || state.status === "running";
  byId("camera-state").textContent = `${state.status}${state.mode === "hand" ? " · Hand mode" : ""}`;
  byId("camera-index").value = String(state.camera_index);
  byId("camera-index").disabled = active || pending;
  byId("face-state").textContent = state.face_detected ? "Yes" : "No";
  byId("mouth-state").textContent = state.mouth_detected ? "Yes" : "No";
  byId("mouth-position").textContent = state.mouth_detected
    ? `X ${percent(state.mouth_x)}, Y ${percent(state.mouth_y)}` : "—";
  byId("mouth-openness").textContent = state.mouth_detected
    ? `${state.mouth_openness.toFixed(2)} (gap / width)` : "—";
  byId("face-quality").textContent = state.face_detected ? state.face_tracking_quality.toFixed(2) : "—";
  byId("head-motion").textContent = state.face_detected ? `${state.head_motion.toFixed(2)} image widths/s` : "—";
  byId("object-state").textContent = state.object_detected ? `Yes (${state.object_mode})` : "No";
  byId("object-position").textContent = state.object_detected
    ? `X ${percent(state.object_x)}, Y ${percent(state.object_y)}` : "—";
  byId("marker-axis").textContent = say(state.marker_axis_degrees == null ? null : state.marker_axis_degrees.toFixed(0), "°");
  byId("object-distance").textContent = say(state.distance_mouth_widths, " mouth widths");
  byId("object-bearing").textContent = say(state.bearing_degrees, "°");
  byId("interaction-state").textContent = state.interaction_state;
  byId("interaction-confidence").textContent = state.interaction_confidence.toFixed(2);
  byId("fps").textContent = state.fps.toFixed(1);
  byId("start").disabled = active || pending;
  byId("stop").disabled = !active || pending;
  byId("calibrate-mouth").disabled = !state.mouth_detected || pending;
  byId("overlay").checked = state.overlay_enabled;
  if (active && !streamAttached) {
    byId("preview").src = `/api/camera/stream?session=${Date.now()}`;
    byId("preview").hidden = false;
    byId("preview-placeholder").hidden = true;
    streamAttached = true;
    connectEvents();
  } else if (!active && streamAttached) {
    byId("preview").removeAttribute("src");
    byId("preview").hidden = true;
    byId("preview-placeholder").hidden = false;
    streamAttached = false;
    disconnectEvents();
  }
  if (!active) byId("preview-placeholder").textContent = state.status === "error" ? "Camera error" : "Camera inactive";
  if (state.error) byId("message").textContent = state.error;
  await refreshAutomation();
}

async function refreshAutomation() {
  const [automation, status, devices] = await Promise.all([
    api("/api/automation/status"), api("/api/status"), api("/api/devices")
  ]);
  byId("automation-state").textContent = automation.state;
  const selected = devices.find((device) => device.id === status.device);
  byId("automation-device").textContent = selected ? `${selected.name}${selected.simulated ? " (simulated)" : ""}` : "None";
  if (selectedAutomationDevice !== status.device) {
    selectedAutomationDevice = status.device;
    const featureSelect = byId("automation-feature");
    featureSelect.replaceChildren();
    for (const feature of selected?.vibration_features || []) {
      const option = document.createElement("option");
      option.value = String(feature);
      option.textContent = `Vibration feature ${feature}`;
      featureSelect.append(option);
    }
    if (!featureSelect.options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No vibration feature selected";
      featureSelect.append(option);
    }
  }
  const armed = ["ARMED", "ACTIVE", "COOLDOWN"].includes(automation.state);
  byId("automation-arm").disabled = armed || status.evaluation_active || !selected || !selected.vibration_features.length || byId("camera-state").textContent !== "running";
  byId("automation-disarm").disabled = !armed;
  for (const id of ["automation-feature", "automation-pattern", "automation-intensity", "automation-duration", "automation-cooldown"]) {
    byId(id).disabled = armed;
  }
  if (automation.error) byId("automation-message").textContent = automation.error;
}

byId("automation-intensity").addEventListener("input", () => {
  byId("automation-intensity-value").value = percent(Number(byId("automation-intensity").value));
});

byId("automation-arm").addEventListener("click", async () => {
  try {
    const feature = byId("automation-feature").value;
    if (feature === "") throw new Error("Select a vibration feature first.");
    await api("/api/automation/arm", {method: "POST", body: JSON.stringify({
      feature_index: Number(feature),
      pattern: byId("automation-pattern").value,
      intensity: Number(byId("automation-intensity").value),
      duration: Number(byId("automation-duration").value),
      cooldown: Number(byId("automation-cooldown").value),
      minimum_confidence: 0.6
    })});
    byId("automation-message").textContent = "Automation armed. Bounded patterns only while detection remains valid.";
    await refreshAutomation();
  } catch (error) { byId("automation-message").textContent = error.message; }
});

byId("automation-disarm").addEventListener("click", async () => {
  try {
    await api("/api/automation/disarm", {method: "POST"});
    byId("automation-message").textContent = "Automation disarmed; stop attempted.";
    await refreshAutomation();
  } catch (error) { byId("automation-message").textContent = error.message; }
});

byId("automation-emergency").addEventListener("click", async () => {
  try {
    await api("/api/emergency-stop", {method: "POST"});
    byId("automation-message").textContent = "Emergency stop latched. Use the device's physical power control if needed.";
    await refreshAutomation();
  } catch (error) { byId("automation-message").textContent = error.message; }
});

async function saveCalibration() {
  const calibration = await api("/api/calibration/settings", {
    method: "POST",
    body: JSON.stringify({
      mode: byId("tracking-mode").value,
      near_distance_mouth_widths: Number(byId("near-distance").value),
      sensitivity: Number(byId("sensitivity").value)
    })
  });
  applyCalibration(calibration);
  byId("message").textContent = "Numeric calibration saved locally. No image was saved.";
}

function normalizedPoint(event) {
  const bounds = byId("preview-container").getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
    y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height))
  };
}

function drawSelection(start, end) {
  const selection = byId("roi-selection");
  selection.hidden = false;
  selection.style.left = `${Math.min(start.x, end.x) * 100}%`;
  selection.style.top = `${Math.min(start.y, end.y) * 100}%`;
  selection.style.width = `${Math.abs(start.x - end.x) * 100}%`;
  selection.style.height = `${Math.abs(start.y - end.y) * 100}%`;
}

byId("start").addEventListener("click", async () => {
  pending = true;
  try {
    lastEventSequence = 0;
    byId("event-log").replaceChildren();
    await api("/api/camera/mode", {method: "POST", body: JSON.stringify({mode: "oral"})});
    await api("/api/camera/start", { method: "POST" });
    byId("message").textContent = "Starting local camera and recognition…";
  } catch (error) { report(error); }
  finally { pending = false; await refresh(); }
});

byId("stop").addEventListener("click", async () => {
  pending = true;
  try {
    await api("/api/camera/stop", { method: "POST" });
    byId("message").textContent = "Camera stopped; preview cleared.";
  } catch (error) { report(error); }
  finally { pending = false; await refresh(); }
});

byId("overlay").addEventListener("change", async (event) => {
  try {
    await api("/api/camera/overlay", { method: "POST", body: JSON.stringify({ enabled: event.target.checked }) });
  } catch (error) { report(error); }
});

byId("camera-index").addEventListener("change", async (event) => {
  try {
    await api("/api/camera/input", {method: "POST", body: JSON.stringify({index: Number(event.target.value)})});
    byId("message").textContent = `Camera input ${event.target.value} selected. Press Start Camera to test it.`;
  } catch (error) { report(error); await refresh(); }
});

byId("calibrate-mouth").addEventListener("click", async () => {
  try {
    applyCalibration(await api("/api/calibration/mouth", { method: "POST" }));
    byId("message").textContent = "Neutral mouth reference saved locally.";
  } catch (error) { report(error); }
});

byId("tracking-mode").addEventListener("change", () => saveCalibration().catch(report));
byId("save-calibration").addEventListener("click", () => saveCalibration().catch(report));
byId("near-distance").addEventListener("input", () => {
  byId("near-distance-value").value = Number(byId("near-distance").value).toFixed(1);
});
byId("sensitivity").addEventListener("input", () => {
  byId("sensitivity-value").value = Number(byId("sensitivity").value).toFixed(2);
});

byId("preview-container").addEventListener("click", async (event) => {
  if (!streamAttached || byId("tracking-mode").value !== "marker") return;
  try {
    const point = normalizedPoint(event);
    applyCalibration(await api("/api/calibration/marker", {
      method: "POST", body: JSON.stringify(point)
    }));
    byId("message").textContent = "Marker color calibrated. Watch the object tracking box.";
  } catch (error) { report(error); }
});

byId("preview-container").addEventListener("pointerdown", (event) => {
  if (!streamAttached || byId("tracking-mode").value !== "roi") return;
  dragStart = normalizedPoint(event);
  byId("preview-container").setPointerCapture(event.pointerId);
  drawSelection(dragStart, dragStart);
});
byId("preview-container").addEventListener("pointermove", (event) => {
  if (dragStart) drawSelection(dragStart, normalizedPoint(event));
});
byId("preview-container").addEventListener("pointerup", async (event) => {
  if (!dragStart) return;
  const end = normalizedPoint(event);
  const start = dragStart;
  dragStart = null;
  byId("roi-selection").hidden = true;
  try {
    await api("/api/calibration/roi", {
      method: "POST",
      body: JSON.stringify({
        x: Math.min(start.x, end.x), y: Math.min(start.y, end.y),
        width: Math.abs(start.x - end.x), height: Math.abs(start.y - end.y)
      })
    });
    byId("message").textContent = "Object rectangle set. Redraw if tracking is lost.";
  } catch (error) { report(error); }
});

Promise.all([api("/api/calibration"), api("/api/interaction/events")]).then(([calibration, events]) => {
  applyCalibration(calibration);
  calibrationLoaded = true;
  for (const event of events) appendEvent(event);
  return refresh();
}).catch(report);
setInterval(() => { if (calibrationLoaded) refresh().catch(report); }, 500);
