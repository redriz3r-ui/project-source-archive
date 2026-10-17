const handEl = (id) => document.getElementById(id);
let handStreaming = false;
let handPending = false;
let handClickTarget = null;
let handBase = null;
let handEndpoint = null;
let lastStrokeEventKey = null;

async function handApi(path, options = {}) {
  const response = await fetch(path, {
    ...options, headers: {"Content-Type": "application/json", ...(options.headers || {})}
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
  return result;
}

function handMessage(error) { handEl("hand-message").textContent = error.message || String(error); }
function handPoint(event) {
  const bounds = handEl("hand-preview").getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
    y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height))
  };
}

async function handRefresh() {
  const state = await handApi("/api/camera/status");
  const response = await handApi("/api/hand/response/status");
  const selection = await handApi("/api/status");
  const devices = await handApi("/api/devices");
  const simulator = devices.find((device) => device.id === selection.device && device.simulated);
  handEl("hand-response-state").textContent = response.state;
  handEl("hand-response-device").textContent = simulator?.name || "None selected";
  handEl("hand-response-strokes").textContent = response.stroke_count;
  handEl("hand-response-counts").textContent = `${response.pending_response_count} / ${response.completed_response_count}`;
  handEl("hand-response-dropped").textContent = response.dropped_response_count;
  handEl("hand-response-latency").textContent = response.simulator_latency_ms == null ? "—" :
    `${response.simulator_latency_ms.toFixed(1)} ms (${response.simulator_latency_samples} samples)`;
  const armed = ["ARMED", "ACTIVE", "COOLDOWN"].includes(response.state);
  handEl("hand-arm").disabled = !simulator || !handActiveReady(state) || armed || handPending;
  handEl("hand-disarm").disabled = !armed || handPending;
  handEl("hand-create-simulator").disabled = armed || handPending;
  if (simulator) {
    const selector = handEl("hand-response-feature");
    const options = simulator.vibration_features || [];
    const signature = options.join(",");
    if (selector.dataset.features !== signature) {
      selector.replaceChildren(...options.map((index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = `Vibration feature ${index}`;
        return option;
      }));
      selector.dataset.features = signature;
    }
  }
  if (response.error) handEl("hand-message").textContent = response.error;
  const active = ["starting", "running"].includes(state.status);
  const handActive = active && state.mode === "hand";
  handEl("hand-camera-state").textContent = `${state.status} · ${state.mode}`;
  handEl("hand-start").disabled = active || handPending;
  handEl("hand-stop").disabled = !active || handPending;
  for (const id of ["hand-base", "hand-endpoint", "hand-marker", "hand-save"]) {
    handEl(id).disabled = !handActive || handPending;
  }
  handEl("hand-state").textContent = handActive ? state.hand.state : "INACTIVE";
  handEl("hand-count").textContent = handActive ? state.hand.hand_count : "0";
  handEl("hand-position").textContent = state.hand.hand_x == null ? "—" :
    `X ${(state.hand.hand_x * 100).toFixed(0)}%, Y ${(state.hand.hand_y * 100).toFixed(0)}%`;
  handEl("hand-travel").textContent = state.hand.travel_position == null ? "—" :
    `${(state.hand.travel_position * 100).toFixed(0)}% of calibrated axis`;
  handEl("hand-confidence").textContent = state.hand.tracking_confidence.toFixed(2);
  handEl("hand-marker-state").textContent = handEl("hand-marker-anchor").checked ?
    (state.hand.marker_detected ? "Tracked" : "Lost / not calibrated") : "Off";
  handEl("hand-fps").textContent = state.fps.toFixed(1);
  handEl("stroke-direction").textContent = state.stroke?.direction || "UNKNOWN";
  handEl("stroke-id").textContent = state.stroke?.stroke_id ?? "—";
  handEl("stroke-travel").textContent = state.stroke ?
    `${(state.stroke.travel * 100).toFixed(0)}% of axis` : "—";
  if (handActive) {
    const events = await handApi("/api/hand/events");
    const recent = events.filter((event) => event.kind !== "stroke_updated").slice(-30);
    const key = recent.map((event) => `${event.frame_id}:${event.kind}`).join("|");
    if (key !== lastStrokeEventKey) {
      const list = handEl("stroke-events");
      list.replaceChildren();
      for (const event of recent.slice().reverse()) {
        const row = document.createElement("li");
        row.textContent = `${event.kind} · #${event.stroke_id ?? "—"} · position ${event.hand_position == null ? "—" : (event.hand_position * 100).toFixed(0) + "%"}`;
        list.append(row);
      }
      lastStrokeEventKey = key;
    }
  }
  handEl("hand-overlay").checked = state.overlay_enabled;
  if (handActive && !handStreaming) {
    handEl("hand-preview").src = `/api/camera/stream?session=${Date.now()}`;
    handEl("hand-preview").hidden = false;
    handEl("hand-placeholder").hidden = true;
    handStreaming = true;
  } else if (!handActive && handStreaming) {
    handEl("hand-preview").removeAttribute("src");
    handEl("hand-preview").hidden = true;
    handEl("hand-placeholder").hidden = false;
    handStreaming = false;
  }
  if (state.error) handEl("hand-message").textContent = state.error;
}

function handActiveReady(state) {
  return state.status === "running" && state.mode === "hand" && state.hand?.state === "TRACKED";
}

handEl("hand-start").addEventListener("click", async () => {
  handPending = true;
  try {
    await handApi("/api/camera/mode", {method: "POST", body: JSON.stringify({mode: "hand"})});
    await handApi("/api/camera/start", {method: "POST"});
    lastStrokeEventKey = null;
    handEl("stroke-events").replaceChildren();
    handEl("hand-message").textContent = "Local hand camera starting. Simulator responses remain disarmed until explicitly armed.";
  } catch (error) { handMessage(error); }
  finally { handPending = false; await handRefresh(); }
});
handEl("hand-stop").addEventListener("click", async () => {
  handPending = true;
  try { await handApi("/api/camera/stop", {method: "POST"}); }
  catch (error) { handMessage(error); }
  finally { handPending = false; await handRefresh(); }
});
for (const [id, target] of [["hand-base", "base"], ["hand-endpoint", "endpoint"]]) {
  handEl(id).addEventListener("click", () => {
    handClickTarget = target;
    handEl("hand-message").textContent = `Click the ${target === "base" ? "object base" : "far end of the movement axis"} in the preview.`;
  });
}
handEl("hand-preview").addEventListener("click", (event) => {
  if (!handClickTarget) return;
  const point = handPoint(event);
  if (handClickTarget === "base") handBase = point;
  else handEndpoint = point;
  handEl("hand-message").textContent = `${handClickTarget} selected. Save the axis after both points are set.`;
  handClickTarget = null;
});
handEl("hand-marker").addEventListener("click", async () => {
  try {
    if (!handBase) throw new Error("Click the base first.");
    await handApi("/api/calibration/marker", {method: "POST", body: JSON.stringify(handBase)});
    handEl("hand-message").textContent = "Base marker color calibrated locally. Now save the axis with marker anchor checked.";
  } catch (error) { handMessage(error); }
});
handEl("hand-save").addEventListener("click", async () => {
  try {
    if (!handBase || !handEndpoint) throw new Error("Click both base and axis end first.");
    if (handEl("hand-marker-anchor").checked) {
      const marker = await handApi("/api/calibration");
      if (marker.marker_hue == null || marker.mode !== "marker") {
        throw new Error("Calibrate the colored base marker before enabling marker anchor.");
      }
    }
    await handApi("/api/hand/calibration", {method: "POST", body: JSON.stringify({
      base_x: handBase.x, base_y: handBase.y,
      endpoint_x: handEndpoint.x, endpoint_y: handEndpoint.y,
      marker_anchor: handEl("hand-marker-anchor").checked
    })});
    handEl("hand-message").textContent = "Numeric axis saved locally; no frame was saved.";
  } catch (error) { handMessage(error); }
});
handEl("hand-overlay").addEventListener("change", async (event) => {
  try { await handApi("/api/camera/overlay", {method: "POST", body: JSON.stringify({enabled: event.target.checked})}); }
  catch (error) { handMessage(error); }
});
handEl("hand-create-simulator").addEventListener("click", async () => {
  handPending = true;
  try {
    const simulator = await handApi("/api/devices/simulated", {method: "POST"});
    await handApi("/api/devices/select", {method: "POST", body: JSON.stringify({device_id: simulator.id})});
    handEl("hand-message").textContent = "Simulator selected. Track the hand and prop before arming.";
  } catch (error) { handMessage(error); }
  finally { handPending = false; await handRefresh(); }
});
handEl("hand-arm").addEventListener("click", async () => {
  handPending = true;
  try {
    await handApi("/api/hand/response/arm", {method: "POST", body: JSON.stringify({
      feature_index: Number(handEl("hand-response-feature").value),
      intensity: Number(handEl("hand-response-intensity").value),
      duration: Number(handEl("hand-response-duration").value),
      cooldown: Number(handEl("hand-response-cooldown").value),
      mode: handEl("hand-response-mode").value
    })});
    handEl("hand-message").textContent = "Simulator-only stroke responses armed.";
  } catch (error) { handMessage(error); }
  finally { handPending = false; await handRefresh(); }
});
handEl("hand-disarm").addEventListener("click", async () => {
  try { await handApi("/api/hand/response/disarm", {method: "POST"}); await handRefresh(); }
  catch (error) { handMessage(error); }
});
handEl("hand-emergency").addEventListener("click", async () => {
  try { await handApi("/api/emergency-stop", {method: "POST"}); await handRefresh(); }
  catch (error) { handMessage(error); }
});
handApi("/api/hand/calibration").then((config) => {
  handBase = config.base && {x: config.base[0], y: config.base[1]};
  handEndpoint = config.endpoint && {x: config.endpoint[0], y: config.endpoint[1]};
  handEl("hand-marker-anchor").checked = config.marker_anchor;
  return handRefresh();
}).catch(handMessage);
setInterval(() => handRefresh().catch(handMessage), 500);
