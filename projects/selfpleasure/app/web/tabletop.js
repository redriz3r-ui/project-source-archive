const tabletop = (id) => document.getElementById(id);
const armedStates = new Set(["ARMED", "ACTIVE", "COOLDOWN"]);
let busy = false;
let streaming = false;
let armedHere = false;
let clickTarget = null;
let selectedId = null;
let inventoryKey = "";
let emergencyPending = false;
let refreshing = false;
const points = {base: null, end: null};

async function tabletopApi(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {"Content-Type": "application/json", ...(options.headers || {})}
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function showError(error) {
  tabletop("tabletop-message").textContent = error.message || String(error);
  tabletop("tabletop-message").hidden = false;
}

function clearError() { tabletop("tabletop-message").hidden = true; }

async function action(work) {
  if (busy) return;
  busy = true;
  clearError();
  try { await work(); }
  catch (error) { showError(error); }
  finally { busy = false; await refresh(); }
}

function renderInventory(data) {
  const devices = (data.available_devices || []).filter((device) => !device.simulated);
  const key = JSON.stringify(devices);
  const chooser = tabletop("tabletop-device");
  if (key !== inventoryKey) {
    chooser.replaceChildren(new Option("Choose Intiface device", ""),
      ...devices.map((device) => new Option(device.name, device.id)));
    inventoryKey = key;
  }
  if (data.selected_device && !data.selected_device.simulated) {
    chooser.value = data.selected_device.id;
    selectedId = data.selected_device.id;
  } else {
    selectedId = null;
  }
  const feature = tabletop("tabletop-feature");
  const indexes = data.selected_device && !data.selected_device.simulated ?
    data.selected_device.vibration_features : [];
  const old = feature.value;
  const featureKey = `${selectedId || ""}:${indexes.join(",")}`;
  if (feature.dataset.key !== featureKey) {
    feature.replaceChildren(new Option(indexes.length ? "Choose vibration feature" : "No vibration output", ""),
      ...indexes.map((index) => new Option(`Vibration feature ${index}`, String(index))));
    feature.dataset.key = featureKey;
    if (old !== "" && indexes.includes(Number(old))) feature.value = old;
  }
}

function stateCopy(response) {
  if (response.state === "ARMED") return ["ARMED — waiting for valid movement", "Only fresh tracked stroke updates can authorize output."];
  if (response.state === "ACTIVE") return ["OUTPUT ACTIVE — command lease running", "This short command expires unless another fresh valid update is accepted."];
  if (response.state === "COOLDOWN") return ["ARMED — command expired", "No old movement is queued; waiting for a fresh valid update."];
  if (response.state === "EMERGENCY_STOP") return ["EMERGENCY STOP — commands blocked", response.disarm_reason || "Emergency Stop pressed."];
  if (response.state === "ERROR") return ["FAULT — commands blocked", response.error || response.disarm_reason || "A safety fault disarmed the mode."];
  return ["DISARMED — no output", response.disarm_reason || "Start & Arm is required."];
}

async function refresh() {
  if (busy || refreshing) return;
  refreshing = true;
  try {
    const data = await tabletopApi("/api/hand/session/status");
    const response = data.response;
    if (armedHere && response.session_managed && armedStates.has(response.state)) {
      try { await tabletopApi("/api/hand/session/heartbeat", {method: "POST"}); }
      catch (error) { armedHere = false; showError(error); }
    }
    if (!armedStates.has(response.state)) armedHere = false;
    renderInventory(data);
    const cameraLive = data.camera.status === "running" && data.camera.mode === "hand";
    const tracking = data.camera.hand?.state || "UNKNOWN";
    const [state, reason] = stateCopy(response);
    tabletop("tabletop-state").textContent = state;
    tabletop("tabletop-state").dataset.state = response.state;
    tabletop("tabletop-reason").textContent = reason;
    tabletop("tabletop-intiface").textContent = data.intiface_connected ? "Connected" : "Not connected";
    tabletop("tabletop-device-status").textContent = data.selected_device && !data.selected_device.simulated ?
      data.selected_device.name : "None selected";
    tabletop("tabletop-tracking").textContent = !cameraLive ? "Camera off" :
      data.tracking_ready ? "Ready" : tracking === "TRACKED" ? "Stabilizing" : tracking.replaceAll("_", " ").toLowerCase();
    tabletop("tabletop-camera-help").textContent = !cameraLive ?
      "Start & Arm starts the camera first. It cannot arm until the saved axis and hand are tracked." :
      data.tracking_ready ? "Tracking is valid. Keep the stationary prop and your hand in view." :
      "Mark and save the prop axis, then keep one hand visible along it.";
    tabletop("tabletop-axis-status").textContent = data.camera.hand?.base && data.camera.hand?.endpoint ?
      "Axis saved. Tracking must be Ready before arming." : "Set and save both axis endpoints.";
    tabletop("tabletop-lockout").textContent = data.real_device_output_enabled ?
      "Real output is available only for an explicitly confirmed supervised off-body trial." :
      "Real output remains locked until supervised physical stop validation passes.";

    if (cameraLive && !streaming) {
      tabletop("tabletop-preview").src = `/api/camera/stream?session=${Date.now()}`;
      tabletop("tabletop-preview").hidden = false;
      tabletop("tabletop-placeholder").hidden = true;
      streaming = true;
    } else if (!cameraLive && streaming) {
      tabletop("tabletop-preview").removeAttribute("src");
      tabletop("tabletop-preview").hidden = true;
      tabletop("tabletop-placeholder").hidden = false;
      streaming = false;
    }

    const active = armedStates.has(response.state);
    const featureChosen = tabletop("tabletop-feature").value !== "";
    tabletop("tabletop-connect").disabled = busy || data.intiface_connected || active;
    tabletop("tabletop-scan").disabled = busy || !data.intiface_connected || active;
    tabletop("tabletop-device").disabled = busy || active;
    tabletop("tabletop-feature").disabled = busy || active;
    tabletop("tabletop-arm").disabled = busy || active ||
      (cameraLive && (!data.real_device_output_enabled || !data.intiface_connected || !selectedId ||
                      !featureChosen || !data.tracking_ready));
    tabletop("tabletop-stop").disabled = busy;
    for (const id of ["tabletop-set-base", "tabletop-set-end", "tabletop-save-axis"])
      tabletop(id).disabled = busy || !cameraLive || active;
  } catch (error) { showError(error); }
  finally { refreshing = false; }
}

tabletop("tabletop-connect").addEventListener("click", () => action(async () => {
  await tabletopApi("/api/intiface/connect", {method: "POST"});
}));
tabletop("tabletop-scan").addEventListener("click", () => action(async () => {
  await tabletopApi("/api/intiface/scan", {method: "POST"});
}));
tabletop("tabletop-device").addEventListener("change", () => action(async () => {
  const id = tabletop("tabletop-device").value;
  if (!id) throw new Error("Choose an Intiface device.");
  await tabletopApi("/api/devices/select", {method: "POST", body: JSON.stringify({device_id: id})});
}));

for (const [id, target] of [["tabletop-set-base", "base"], ["tabletop-set-end", "end"]]) {
  tabletop(id).addEventListener("click", () => {
    clickTarget = target;
    tabletop("tabletop-axis-status").textContent = `Click the prop ${target === "base" ? "base" : "far end"} in the preview.`;
  });
}
tabletop("tabletop-preview").addEventListener("click", (event) => {
  if (!clickTarget) return;
  const box = event.currentTarget.getBoundingClientRect();
  points[clickTarget] = {
    x: Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)),
    y: Math.max(0, Math.min(1, (event.clientY - box.top) / box.height))
  };
  tabletop("tabletop-axis-status").textContent = `${clickTarget === "base" ? "Base" : "Far end"} marked.`;
  clickTarget = null;
});
tabletop("tabletop-save-axis").addEventListener("click", () => action(async () => {
  if (!points.base || !points.end) throw new Error("Mark both Base and Far end first.");
  await tabletopApi("/api/hand/calibration", {method: "POST", body: JSON.stringify({
    base_x: points.base.x, base_y: points.base.y,
    endpoint_x: points.end.x, endpoint_y: points.end.y, marker_anchor: false
  })});
}));

tabletop("tabletop-arm").addEventListener("click", () => action(async () => {
  const status = await tabletopApi("/api/hand/session/status");
  if (status.camera.status === "inactive") {
    await tabletopApi("/api/camera/mode", {method: "POST", body: JSON.stringify({mode: "hand"})});
    await tabletopApi("/api/camera/overlay", {method: "POST", body: JSON.stringify({enabled: true})});
    await tabletopApi("/api/camera/start", {method: "POST"});
    return;
  }
  if (!status.real_device_output_enabled)
    throw new Error("Real output is locked until supervised physical stop validation passes.");
  const feature = tabletop("tabletop-feature").value;
  if (!status.tracking_ready || !selectedId || feature === "")
    throw new Error("Tracking, Intiface device, and vibration feature must all be ready.");
  if (!window.confirm("Confirm this supervised test is off-body on a table, physical power-off is within reach, and the selected feature passed its physical stop preflight.")) return;
  await tabletopApi("/api/tabletop/arm", {method: "POST", body: JSON.stringify({
    feature_index: Number(feature), off_body_confirmed: true,
    manual_preflight_confirmed: true, physical_power_off_ready: true
  })});
  armedHere = true;
}));

tabletop("tabletop-stop").addEventListener("click", () => action(async () => {
  armedHere = false;
  await tabletopApi("/api/control/stop", {method: "POST"});
}));
async function emergencyStop() {
  if (emergencyPending) return;
  emergencyPending = true;
  armedHere = false;
  try { await tabletopApi("/api/emergency-stop", {method: "POST"}); }
  catch (error) { showError(error); }
  finally { emergencyPending = false; await refresh(); }
}
tabletop("tabletop-emergency").addEventListener("click", emergencyStop);
tabletop("tabletop-emergency-bottom").addEventListener("click", emergencyStop);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") { event.preventDefault(); emergencyStop(); }
});
window.addEventListener("pagehide", () => {
  if (armedHere) navigator.sendBeacon("/api/hand/session/finish", new Blob([], {type: "application/json"}));
});

refresh();
setInterval(refresh, 300);
