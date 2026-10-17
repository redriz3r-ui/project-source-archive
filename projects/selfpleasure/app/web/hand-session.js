const sessionEl = (id) => document.getElementById(id);
const activeStates = new Set(["ARMED", "ACTIVE", "COOLDOWN"]);
let sessionBusy = false;
let sessionStreaming = false;
let sessionClickTarget = null;
let sessionPreviewKey = null;
let sessionArmedHere = false;
let sessionInitialCheck = true;
let sessionRefreshing = false;
let previousSent = 0;
let cameraIndexInitialized = false;
let emergencyPending = false;
let sessionSelectedDeviceId = null;
let sessionSelectedReal = false;
let sessionDeviceInventoryKey = null;
let sessionFeatureKey = null;

async function sessionApi(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {"Content-Type": "application/json", ...(options.headers || {})}
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.detail || `Request failed (${response.status})`);
  return value;
}

function sessionError(error) {
  const message = sessionEl("session-message");
  message.textContent = error.message || String(error);
  message.hidden = false;
}

function sessionClearError() { sessionEl("session-message").hidden = true; }

function sessionSettings() {
  return {
    feature_index: Number(sessionEl("session-feature").value),
    intensity: Number(sessionEl("session-intensity").value) / 100,
    duration: Number(sessionEl("session-duration").value),
    cooldown: Number(sessionEl("session-cooldown").value),
    minimum_confidence: 0.5,
    mode: sessionEl("session-mode").value,
    style: sessionEl("session-style").value,
    real_pilot: sessionSelectedReal,
    manual_preflight_confirmed: sessionEl("session-manual-check").checked,
    physical_power_off_ready: sessionEl("session-power-check").checked
  };
}

function sessionSettingsKey() {
  const {manual_preflight_confirmed, physical_power_off_ready, ...settings} = sessionSettings();
  return JSON.stringify({device_id: sessionSelectedDeviceId, ...settings});
}

function sessionUpdateModeHelp() {
  const durationOptions = sessionEl("session-duration").options || [];
  const cooldownOptions = sessionEl("session-cooldown").options || [];
  if (sessionSelectedReal) {
    sessionEl("session-mode-help").textContent =
      "Supervised real pilot: one short crisp response per completed stroke. Follow movement is disabled until physical validation.";
    sessionEl("session-intensity").max = "20";
    if (Number(sessionEl("session-intensity").value) > 20) sessionEl("session-intensity").value = "20";
    sessionEl("session-intensity-value").value = `${sessionEl("session-intensity").value}%`;
    sessionEl("session-mode").value = "ONE_RESPONSE";
    sessionEl("session-style").value = "CRISP";
    sessionEl("session-duration").max = "0.12";
    if (Number(sessionEl("session-duration").value) > 0.12) sessionEl("session-duration").value = "0.12";
    sessionEl("session-cooldown").min = "0.5";
    if (Number(sessionEl("session-cooldown").value) < 0.5) sessionEl("session-cooldown").value = "0.5";
    for (const option of durationOptions) option.disabled = Number(option.value) > 0.12;
    for (const option of cooldownOptions) option.disabled = Number(option.value) < 0.5;
    return;
  }
  sessionEl("session-intensity").max = "30";
  const following = sessionEl("session-mode").value === "FOLLOW_MOVEMENT";
  sessionEl("session-mode-help").textContent = following ?
    "Fresh hand movement can produce short, rate-limited pulses. Old or busy updates are skipped; this is not continuous output." :
    "A completed stroke produces one bounded response. Rapid strokes during a response or cooldown are skipped.";
  sessionEl("session-duration").max = following ? "0.12" : "0.5";
  sessionEl("session-cooldown").min = following ? "0.08" : "0.25";
  for (const option of durationOptions) option.disabled = Number(option.value) > (following ? 0.12 : 0.5);
  for (const option of cooldownOptions) option.disabled = Number(option.value) < (following ? 0.08 : 0.25);
}

function sessionRenderDevices(devices, selected) {
  const wantsReal = sessionEl("session-source-real")?.checked;
  const visibleDevices = sessionEl("session-source-real") ?
    devices.filter((device) => wantsReal ? !device.simulated : device.simulated) : devices;
  const inventory = JSON.stringify(visibleDevices);
  const chooser = sessionEl("session-device-select");
  if (inventory !== sessionDeviceInventoryKey) {
    const options = [new Option("Choose device", "")];
    for (const device of visibleDevices) {
      options.push(new Option(`${device.name}${device.simulated ? " (simulator)" : " (real)"}`,
                              device.id));
    }
    chooser.replaceChildren(...options);
    sessionDeviceInventoryKey = inventory;
    chooser.value = visibleDevices.some((device) => device.id === selected?.id) ? selected.id : "";
  }
  const feature = sessionEl("session-feature");
  const featureKey = `${selected?.id || ""}:${(selected?.vibration_features || []).join(",")}`;
  if (featureKey !== sessionFeatureKey) {
    const features = selected?.vibration_features || [];
    feature.replaceChildren(new Option(features.length ? "Choose vibration feature" :
      "No vibration output", ""), ...features.map((index) =>
      new Option(`Vibration feature ${index}`, String(index))));
    feature.value = "";
    sessionFeatureKey = featureKey;
  }
}

function sessionStateText(state) {
  return {
    DISARMED: ["DISARMED — commands blocked", "The app will not send new output. Verify a real device has physically stopped."],
    PAUSED: ["PAUSED — commands blocked", "The camera stays on. Verify physical stop before any new Arm action."],
    ARMED: ["ARMED — waiting for a stroke", "The selected device may respond while tracking remains valid."],
    ACTIVE: ["OUTPUT ACTIVE — bounded pulse", "A short bounded response is running now."],
    COOLDOWN: ["ARMED — resting between pulses", "No new pulse is authorized during cooldown; verify physical behavior."],
    EMERGENCY_STOP: ["EMERGENCY STOP — commands blocked", "Stop was attempted. Verify the device physically stopped; use its power control if not."],
    ERROR: ["ERROR — commands blocked", "Stop was attempted. Verify physical stop before doing anything else."],
  }[state] || ["UNKNOWN — output state unclear", "Stop the session and check the app."];
}

function sessionRenderPattern(preview) {
  const host = sessionEl("session-pattern-preview");
  const description = document.createElement("p");
  description.textContent = preview.explanation;
  const bars = document.createElement("div");
  bars.className = "session-pattern-bars";
  bars.setAttribute("aria-hidden", "true");
  for (const step of preview.steps) {
    const bar = document.createElement("span");
    bar.style.flex = String(Math.max(0.1, step.duration));
    bar.style.height = `${Math.max(2, step.intensity / preview.maximum_intensity * 100)}%`;
    if (step.intensity === 0) bar.style.background = "#435560";
    bars.append(bar);
  }
  const foot = document.createElement("p");
  foot.className = "hint";
  foot.textContent = `At most ${Math.round(preview.maximum_intensity * 100)}% for ${preview.maximum_duration.toFixed(2)} seconds. Preview only — no device output.`;
  host.replaceChildren(description, bars, foot);
}

function sessionPoint(event) {
  const rectangle = sessionEl("session-preview").getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(100, (event.clientX - rectangle.left) / rectangle.width * 100)),
    y: Math.max(0, Math.min(100, (event.clientY - rectangle.top) / rectangle.height * 100))
  };
}

async function sessionRefresh() {
  if (sessionRefreshing) return;
  sessionRefreshing = true;
  try {
    let data = await sessionApi("/api/hand/session/status");
    let response = data.response;
    if (sessionInitialCheck && response.session_managed && activeStates.has(response.state) && !sessionArmedHere) {
      await sessionApi("/api/hand/response/disarm", {method: "POST"});
      data = await sessionApi("/api/hand/session/status");
      response = data.response;
      sessionError(new Error("A previous session was disarmed. Press Arm again only after checking tracking."));
    }
    sessionInitialCheck = false;
    if (sessionArmedHere && response.session_managed && activeStates.has(response.state)) {
      await sessionApi("/api/hand/session/heartbeat", {method: "POST"});
    }
    if (!activeStates.has(response.state)) sessionArmedHere = false;

    const camera = data.camera;
    const cameraLive = camera.status === "running" && camera.mode === "hand";
    const simulated = data.selected_device?.simulated === true;
    const selectedFeatures = data.selected_device?.vibration_features || [];
    const selectedId = data.selected_device?.id || null;
    const selectionChanged = selectedId !== sessionSelectedDeviceId;
    if (selectionChanged) {
      const wasReal = sessionSelectedReal;
      sessionSelectedDeviceId = selectedId;
      sessionSelectedReal = Boolean(data.selected_device && !simulated);
      if (wasReal && !sessionSelectedReal && sessionEl("session-connect")) {
        sessionEl("session-duration").value = "0.18";
        sessionEl("session-cooldown").value = "0.3";
      }
      if (selectedId && sessionEl("session-source-real")) {
        sessionEl(sessionSelectedReal ? "session-source-real" : "session-source-sim").checked = true;
        sessionDeviceInventoryKey = null;
      }
      sessionEl("session-manual-check").checked = false;
      sessionEl("session-power-check").checked = false;
      sessionPreviewKey = null;
      sessionUpdateModeHelp();
    }
    sessionRenderDevices(data.available_devices || [], data.selected_device);
    if (selectionChanged && (data.available_devices || []).some((device) => device.id === selectedId))
      sessionEl("session-device-select").value = selectedId || "";
    const sourceChoiceReal = Boolean(sessionEl("session-source-real")?.checked);
    sessionEl("session-real-preflight").hidden = !sessionSelectedReal ||
      (Boolean(sessionEl("session-connect")) && !sourceChoiceReal);
    if (sessionEl("unified-response"))
      sessionEl("unified-response").hidden = sessionSelectedReal || sourceChoiceReal;
    sessionEl("session-real-lockout").hidden = !sessionSelectedReal;
    if (sessionEl("session-bench-info")) {
      sessionEl("session-real-lockout").textContent = data.real_device_manual_bench_enabled ?
        "Camera automation is locked. Only the off-body manual bench test below is available." :
        "Real output is locked. Restart in off-body manual bench mode for supervised diagnostics.";
      sessionEl("session-bench-info").hidden = !data.real_device_manual_bench_enabled;
    }
    const tracked = data.tracking_ready;
    let [stateText, stateHelp] = sessionStateText(response.state);
    let displayState = response.state;
    if (sessionEl("session-connect")) {
      if (data.manual_test_running) {
        stateText = "MANUAL TEST ACTIVE — check physical stop";
        stateHelp = "A bounded manual command is in progress. Emergency Stop is above; physical power-off is the fallback.";
        displayState = "ACTIVE";
      } else if (data.manual_activation_enabled) {
        stateText = "MANUAL TEST READY — output can start";
        stateHelp = "The next Test vibration click can activate the selected feature. Camera automation remains disarmed.";
        displayState = "ARMED";
      } else if (response.state === "DISARMED") {
        stateHelp = sessionSelectedReal ?
          "Camera automation is locked. Manual bench testing needs a separate enable action; verify physical stop." :
          "Simulator response is disarmed. Start the camera, calibrate, then choose Arm when ready.";
      }
    }
    const stateNode = sessionEl("session-armed-status");
    stateNode.textContent = stateText;
    stateNode.dataset.state = displayState;
    sessionEl("session-state-explanation").textContent = stateHelp;
    sessionEl("session-device").textContent = data.selected_device ?
      `${data.selected_device.name} ${simulated ? "(simulator)" :
        data.real_device_manual_bench_enabled ? "(real · manual bench)" : "(real · locked)"}` : "None selected";
    sessionEl("session-intiface").textContent = data.intiface_connected ? "Connected" : "Not connected";
    sessionEl("session-camera").textContent = cameraLive ? "On · Hand mode" :
      camera.status === "running" ? "On · other mode" : "Off";
    const quality = camera.hand?.tracking_confidence || 0;
    const qualityPercent = Math.round(quality * 100);
    sessionEl("session-quality").value = qualityPercent;
    sessionEl("session-quality-value").textContent = `${qualityPercent}%`;
    sessionEl("session-tracking-status").textContent = !cameraLive ? "Camera off" :
      tracked ? "Tracking ready" : "Tracking uncertain";
    sessionEl("session-tracking-explanation").textContent = !cameraLive ?
      "Start the hand camera to check tracking." : tracked ?
      "Hand and calibrated axis are visible. Arming is your choice." :
      `State: ${camera.hand?.state || "UNKNOWN"}. No response is authorized until tracking is steady.`;
    sessionEl("session-quality-advice").textContent = tracked ?
      "Ready for an explicit arm after device preflight and response preview." :
      "Keep the prop steady, improve lighting, and make sure your hand and the axis stay in view.";
    if (!cameraIndexInitialized) {
      sessionEl("session-camera-index").value = String(camera.camera_index);
      cameraIndexInitialized = true;
    }
    sessionEl("session-strokes").textContent = String(response.stroke_count);
    sessionEl("session-sent").textContent = String(response.submitted_response_count);
    sessionEl("session-completed").textContent = String(response.completed_response_count);
    sessionEl("session-pending").textContent = String(response.pending_response_count);
    if (response.submitted_response_count > previousSent) {
      sessionEl("session-feedback-line").textContent = response.active_stroke_id == null ?
        "A bounded response was sent to the selected device." :
        `Stroke #${response.active_stroke_id}: bounded response sent to the selected device.`;
    } else if (!activeStates.has(response.state)) {
      sessionEl("session-feedback-line").textContent = "No response is authorized.";
    }
    previousSent = response.submitted_response_count;
    if (response.error) sessionError(new Error(response.error));

    const unified = Boolean(sessionEl("session-connect"));
    const choosingReal = Boolean(sessionEl("session-source-real")?.checked);
    sessionEl("session-simulator").hidden = unified && choosingReal;
    sessionEl("session-simulator").disabled = sessionBusy || activeStates.has(response.state);
    if (unified) {
      sessionEl("session-connect").hidden = !choosingReal || data.intiface_connected;
      sessionEl("session-connect").disabled = sessionBusy || activeStates.has(response.state);
      sessionEl("session-disconnect").hidden = !choosingReal || !data.intiface_connected;
      sessionEl("session-disconnect").disabled = sessionBusy || data.manual_test_running || activeStates.has(response.state);
      sessionEl("session-scan").hidden = !choosingReal || !data.intiface_connected;
      sessionEl("session-scan").disabled = sessionBusy || data.manual_test_running || activeStates.has(response.state);
      sessionEl("session-camera-stop").disabled = sessionBusy || camera.status === "inactive";
    }
    sessionEl("session-prepare").disabled = sessionBusy || camera.status !== "inactive" || activeStates.has(response.state);
    sessionEl("session-prepare").textContent = cameraLive ? "Camera running" :
      camera.status === "running" ? "Finish other camera mode" : "Start hand camera";
    sessionEl("session-device-select").disabled = sessionBusy || activeStates.has(response.state);
    sessionEl("session-select-device").disabled = sessionBusy || activeStates.has(response.state);
    sessionEl("session-camera-start").disabled = sessionBusy || camera.status !== "inactive";
    sessionEl("session-camera-index").disabled = sessionBusy || camera.status !== "inactive";
    for (const id of ["session-set-base", "session-set-end", "session-save-axis"])
      sessionEl(id).disabled = sessionBusy || !cameraLive || activeStates.has(response.state);
    sessionEl("session-preview-pattern").disabled = sessionBusy || activeStates.has(response.state);
    const featureChosen = sessionEl("session-feature").value !== "";
    const selectedFeature = Number(sessionEl("session-feature").value);
    const realReady = !sessionSelectedReal || (data.real_pilot_available &&
      sessionEl("session-manual-check").checked && sessionEl("session-power-check").checked);
    const sourceMatches = !unified || (Boolean(selectedId) && choosingReal === sessionSelectedReal);
    sessionEl("session-preflight-test").disabled = sessionBusy ||
      !(unified ? data.real_device_manual_bench_enabled && data.manual_activation_enabled : data.real_device_output_enabled) ||
      data.manual_test_running ||
      activeStates.has(response.state) || !sessionSelectedReal || !data.intiface_connected ||
      !featureChosen || !selectedFeatures.includes(selectedFeature) || !sessionEl("session-power-check").checked;
    if (unified) {
      const benchReady = data.real_device_manual_bench_enabled && sessionSelectedReal &&
        data.intiface_connected && featureChosen && selectedFeatures.includes(selectedFeature) &&
        sessionEl("session-power-check").checked && !data.manual_test_running &&
        !activeStates.has(response.state) && !sessionBusy;
      sessionEl("session-bench-enable").disabled = !benchReady;
      sessionEl("session-bench-intensity").disabled = !benchReady;
      sessionEl("session-bench-duration").disabled = !benchReady;
      sessionEl("session-bench-stop").disabled = sessionBusy;
      if (data.manual_control_error) sessionEl("session-bench-note").textContent = data.manual_control_error;
    }
    sessionEl("session-arm").disabled = sessionBusy || data.manual_test_running ||
      !sourceMatches || !featureChosen || !selectedFeatures.includes(selectedFeature) || !realReady ||
      !tracked || activeStates.has(response.state);
    sessionEl("session-arm").textContent = response.state === "PAUSED" ? "Arm again" :
      sessionSelectedReal ? (data.real_device_output_enabled ? "Arm real-device pilot" : "Real automation locked") :
      data.selected_device ? "Arm simulator" : "Arm hand response";
    sessionEl("session-arm").hidden = activeStates.has(response.state);
    sessionEl("session-pause").disabled = sessionBusy || !activeStates.has(response.state);
    sessionEl("session-pause").hidden = !activeStates.has(response.state);
    sessionEl("session-disarm").disabled = sessionBusy || !activeStates.has(response.state);
    sessionEl("session-next-step").textContent = !sourceMatches ?
      "Choose a device from the selected source." :
      sessionSelectedReal && !data.real_device_output_enabled ?
      (data.real_device_manual_bench_enabled ?
        "Real-device automation is locked. Use the off-body manual test above, or choose simulator for hand response." :
        "Real-device output is locked. Choose simulator for hand response.") :
      !cameraLive ?
      "Start the hand camera when ready. This does not activate the device." :
      !data.selected_device ? "Choose your device below, then mark the object's movement axis." :
      !featureChosen || !selectedFeatures.includes(selectedFeature) ? "Choose a supported vibration feature below." :
      !tracked ? "Mark the base and far end on the preview, save the axis, and wait for Tracking ready." :
      sessionSelectedReal && !sessionEl("session-power-check").checked ?
        "Confirm that the physical power-off control is within reach." :
      sessionSelectedReal && !sessionEl("session-manual-check").checked ?
        "Run the short manual test below and confirm the device physically stopped." :
      activeStates.has(response.state) ? "Responding only to fresh, tracked strokes. Pause or Emergency Stop at any time." :
      "Ready. Press Arm once; the response preview is checked without output first.";
    sessionEl("session-finish").disabled = sessionBusy;
    for (const id of ["session-intensity", "session-mode", "session-style", "session-duration", "session-cooldown"])
      sessionEl(id).disabled = sessionBusy || activeStates.has(response.state);
    sessionEl("session-mode").disabled ||= sessionSelectedReal;
    sessionEl("session-style").disabled ||= sessionSelectedReal;
    sessionEl("session-feature").disabled = sessionBusy || activeStates.has(response.state);
    sessionEl("session-overlay").checked = camera.overlay_enabled;
    sessionEl("session-overlay").disabled = sessionBusy || !cameraLive;
    if (cameraLive && !sessionStreaming) {
      sessionEl("session-preview").src = `/api/camera/stream?session=${Date.now()}`;
      sessionEl("session-preview").hidden = false;
      sessionEl("session-placeholder").hidden = true;
      sessionStreaming = true;
    } else if (!cameraLive && sessionStreaming) {
      sessionEl("session-preview").removeAttribute("src");
      sessionEl("session-preview").hidden = true;
      sessionEl("session-placeholder").hidden = false;
      sessionStreaming = false;
    }
  } catch (error) { sessionError(error); }
  finally { sessionRefreshing = false; }
}

async function sessionAction(action) {
  if (sessionBusy) return;
  sessionBusy = true;
  sessionClearError();
  try { await action(); }
  catch (error) { sessionError(error); }
  finally { sessionBusy = false; await sessionRefresh(); }
}

sessionEl("session-intensity").addEventListener("input", () => {
  sessionEl("session-intensity-value").value = `${sessionEl("session-intensity").value}%`;
  sessionPreviewKey = null;
});
for (const id of ["session-mode", "session-style", "session-duration", "session-cooldown"]) {
  sessionEl(id).addEventListener("change", () => {
    if (id === "session-mode") {
      const follow = sessionEl(id).value === "FOLLOW_MOVEMENT";
      sessionEl("session-duration").value = follow ? "0.08" : "0.18";
      sessionEl("session-cooldown").value = follow ? "0.08" : "0.30";
      sessionUpdateModeHelp();
    }
    sessionPreviewKey = null;
  });
}
sessionEl("session-feature").addEventListener("change", () => { sessionPreviewKey = null; });
sessionEl("session-select-device").addEventListener("click", () => sessionAction(async () => {
  const deviceId = sessionEl("session-device-select").value;
  if (!deviceId) throw new Error("Choose an available device first.");
  await sessionApi("/api/devices/select", {method: "POST", body: JSON.stringify({device_id: deviceId})});
}));
sessionEl("session-device-select").addEventListener("change", () => {
  if (sessionEl("session-device-select").value) sessionEl("session-select-device").click();
});
sessionEl("session-prepare").addEventListener("click", () => sessionAction(async () => {
  const state = await sessionApi("/api/hand/session/status");
  if (state.camera.status === "running" && state.camera.mode !== "hand")
    throw new Error("Finish the other camera mode before starting Hand session.");
  if (!sessionEl("session-connect") && !state.intiface_connected)
    await sessionApi("/api/intiface/connect", {method: "POST"});
  if (state.camera.status === "inactive") {
    await sessionApi("/api/camera/mode", {method: "POST", body: JSON.stringify({mode: "hand"})});
    await sessionApi("/api/camera/input", {method: "POST", body: JSON.stringify({index: Number(sessionEl("session-camera-index").value)})});
    await sessionApi("/api/camera/start", {method: "POST"});
  }
}));
sessionEl("session-simulator").addEventListener("click", () => sessionAction(async () => {
  const simulator = await sessionApi("/api/devices/simulated", {method: "POST"});
  await sessionApi("/api/devices/select", {method: "POST", body: JSON.stringify({device_id: simulator.id})});
}));
if (sessionEl("session-connect")) {
  for (const id of ["session-source-sim", "session-source-real"])
    sessionEl(id).addEventListener("change", () => {
      sessionDeviceInventoryKey = null;
      sessionRefresh();
    });
  sessionEl("session-connect").addEventListener("click", () => sessionAction(async () => {
    await sessionApi("/api/intiface/connect", {method: "POST"});
  }));
  sessionEl("session-disconnect").addEventListener("click", () => sessionAction(async () => {
    await sessionApi("/api/intiface/disconnect", {method: "POST"});
  }));
  sessionEl("session-scan").addEventListener("click", () => sessionAction(async () => {
    await sessionApi("/api/intiface/scan", {method: "POST"});
  }));
  sessionEl("session-camera-stop").addEventListener("click", () => sessionAction(async () => {
    await sessionApi("/api/camera/stop", {method: "POST"});
    sessionArmedHere = false;
  }));
  sessionEl("session-bench-enable").addEventListener("click", () => sessionAction(async () => {
    if (!sessionEl("session-power-check").checked)
      throw new Error("Confirm the device is off-body and physical power-off is reachable.");
    await sessionApi("/api/control/enable", {method: "POST",
      body: JSON.stringify({off_body_confirmed: true})});
    sessionEl("session-bench-note").textContent = "One manual test enabled. Press Test vibration when ready.";
  }));
  sessionEl("session-bench-stop").addEventListener("click", () => sessionAction(async () => {
    await sessionApi("/api/control/stop", {method: "POST"});
    sessionEl("session-bench-note").textContent = "Stop attempted. Verify the device physically stopped.";
  }));
}
sessionEl("session-camera-start").addEventListener("click", () => sessionAction(async () => {
  await sessionApi("/api/camera/mode", {method: "POST", body: JSON.stringify({mode: "hand"})});
  await sessionApi("/api/camera/input", {method: "POST", body: JSON.stringify({index: Number(sessionEl("session-camera-index").value)})});
  await sessionApi("/api/camera/overlay", {method: "POST", body: JSON.stringify({enabled: false})});
  await sessionApi("/api/camera/start", {method: "POST"});
}));
for (const [id, target] of [["session-set-base", "base"], ["session-set-end", "end"]]) {
  sessionEl(id).addEventListener("click", () => {
    sessionClickTarget = target;
    sessionEl("session-quality-advice").textContent = `Click the ${target === "base" ? "base" : "far end"} in the preview, or enter coordinates below.`;
  });
}
sessionEl("session-preview").addEventListener("click", (event) => {
  if (!sessionClickTarget) return;
  const point = sessionPoint(event);
  sessionEl(sessionClickTarget === "base" ? "session-base-x" : "session-end-x").value = String(Math.round(point.x));
  sessionEl(sessionClickTarget === "base" ? "session-base-y" : "session-end-y").value = String(Math.round(point.y));
  sessionClickTarget = null;
});
sessionEl("session-save-axis").addEventListener("click", () => sessionAction(async () => {
  const ids = ["session-base-x", "session-base-y", "session-end-x", "session-end-y"];
  if (ids.some((id) => sessionEl(id).value === "")) throw new Error("Mark both the base and far end first.");
  const values = ids.map((id) => Number(sessionEl(id).value) / 100);
  if (values.some((value) => !Number.isFinite(value) || value < 0 || value > 1))
    throw new Error("Axis coordinates must be between 0% and 100%.");
  await sessionApi("/api/hand/calibration", {method: "POST", body: JSON.stringify({
    base_x: values[0], base_y: values[1], endpoint_x: values[2], endpoint_y: values[3],
    marker_anchor: false
  })});
  sessionPreviewKey = null;
}));
sessionEl("session-overlay").addEventListener("change", (event) => sessionAction(async () => {
  await sessionApi("/api/camera/overlay", {method: "POST", body: JSON.stringify({enabled: event.target.checked})});
}));
sessionEl("session-preview-pattern").addEventListener("click", () => sessionAction(async () => {
  const key = sessionSettingsKey();
  const preview = await sessionApi("/api/hand/session/preview", {method: "POST",
    body: JSON.stringify(sessionSettings())});
  if (preview.device_command_sent !== false) throw new Error("Preview safety check failed.");
  sessionRenderPattern(preview);
  sessionPreviewKey = key;
}));
sessionEl("session-preflight-test").addEventListener("click", () => sessionAction(async () => {
  if (!sessionEl("session-power-check").checked) throw new Error("Confirm the physical power-off control is within reach.");
  if (sessionEl("session-bench-enable")) {
    const intensity = Number(sessionEl("session-bench-intensity").value);
    const duration = Number(sessionEl("session-bench-duration").value);
    if (!window.confirm(`Send one off-body ${Math.round(intensity * 100)}% vibration test for at most ${duration} seconds? Use physical power-off if it does not stop.`)) return;
    await sessionApi("/api/control/test", {method: "POST", body: JSON.stringify({
      feature_index: Number(sessionEl("session-feature").value), intensity, duration,
      off_body_confirmed: true
    })});
    sessionEl("session-power-check").checked = false;
    sessionEl("session-bench-note").textContent = "Test sent. Verify physical stop before another test.";
    return;
  }
  if (!window.confirm("Send one 20% vibration command for 0.1 second to the selected feature? Press Emergency Stop or use physical power-off if it does not stop.")) return;
  sessionEl("session-manual-check").checked = false;
  const result = await sessionApi("/api/hand/session/preflight-test", {method: "POST",
    body: JSON.stringify({feature_index: Number(sessionEl("session-feature").value), physical_power_off_ready: true})});
  if (result.started) sessionError(new Error("Manual test sent. Wait for it to stop physically, then check the confirmation box."));
}));
sessionEl("session-arm").addEventListener("click", () => sessionAction(async () => {
  if (sessionPreviewKey !== sessionSettingsKey()) {
    const preview = await sessionApi("/api/hand/session/preview", {method: "POST",
      body: JSON.stringify(sessionSettings())});
    if (preview.device_command_sent !== false) throw new Error("Preview safety check failed.");
    sessionRenderPattern(preview);
    sessionPreviewKey = sessionSettingsKey();
  }
  if (sessionSelectedReal && !window.confirm(
    "Supervised real-device pilot: one short bounded response per completed stroke. Keep physical power-off in reach. Arm now?")) return;
  await sessionApi("/api/hand/session/arm", {method: "POST",
    body: JSON.stringify(sessionSettings())});
  sessionArmedHere = true;
}));
sessionEl("session-pause").addEventListener("click", () => sessionAction(async () => {
  await sessionApi("/api/hand/session/pause", {method: "POST"});
  sessionArmedHere = false;
}));
sessionEl("session-disarm").addEventListener("click", () => sessionAction(async () => {
  await sessionApi("/api/hand/response/disarm", {method: "POST"});
  sessionArmedHere = false;
}));
sessionEl("session-finish").addEventListener("click", () => sessionAction(async () => {
  await sessionApi("/api/hand/session/finish", {method: "POST"});
  sessionArmedHere = false;
  sessionEl("session-feedback-line").textContent = "Session finished. Stop attempted and camera closed; verify physical stop.";
}));
async function sessionEmergency() {
  if (emergencyPending) return;
  emergencyPending = true;
  sessionArmedHere = false;
  sessionClearError();
  try { await sessionApi("/api/emergency-stop", {method: "POST"}); }
  catch (error) { sessionError(error); }
  finally { emergencyPending = false; await sessionRefresh(); }
}
sessionEl("session-emergency").addEventListener("click", sessionEmergency);
sessionEl("session-quit").addEventListener("click", async () => {
  if (!window.confirm("Quit SelfPleasure? Output will stop and the camera will close.")) return;
  try { await sessionApi("/api/application/quit", {method: "POST"}); }
  catch (error) { sessionError(error); }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") { event.preventDefault(); sessionEmergency(); }
});
window.addEventListener("pagehide", () => {
  if (sessionArmedHere || sessionStreaming) {
    navigator.sendBeacon("/api/hand/session/finish", new Blob([], {type: "application/json"}));
  }
});
sessionApi("/api/hand/calibration").then((axis) => {
  if (axis.base) {
    sessionEl("session-base-x").value = String(Math.round(axis.base[0] * 100));
    sessionEl("session-base-y").value = String(Math.round(axis.base[1] * 100));
  }
  if (axis.endpoint) {
    sessionEl("session-end-x").value = String(Math.round(axis.endpoint[0] * 100));
    sessionEl("session-end-y").value = String(Math.round(axis.endpoint[1] * 100));
  }
}).catch(sessionError).finally(sessionRefresh);
sessionUpdateModeHelp();
sessionApi("/api/status").then((status) => {
  sessionEl("session-quit").hidden = !status.desktop_app;
}).catch(sessionError);
setInterval(sessionRefresh, 350);
