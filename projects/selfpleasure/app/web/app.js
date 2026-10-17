const el = (id) => document.getElementById(id);
let streamAttached = false;
let busy = false;
let enabledRule = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {"Content-Type": "application/json", ...(options.headers || {})}
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function notice(error) { el("message").textContent = error.message || String(error); }

async function refresh() {
  const {status, camera, automation, devices, rules} = await api("/api/dashboard");
  const selected = devices.find((device) => device.id === status.device);
  el("quit-app").hidden = !status.desktop_app;
  enabledRule = rules.find((rule) => rule.enabled) || null;
  const activeCamera = camera.status === "running" || camera.status === "starting";
  el("camera-badge").textContent = `${camera.status} · ${camera.mode}`;
  el("intiface-badge").textContent = status.intiface === "connected" ? "Connected" : "Offline";
  el("intiface").textContent = status.intiface === "connected" ? "Connected" : "Not connected";
  el("device").textContent = selected ? `${selected.name}${selected.simulated ? " · Simulator" : ""}` : "None selected";
  el("feature").textContent = enabledRule ? `Vibration ${enabledRule.feature_index}` : "—";
  el("intensity").textContent = enabledRule ? `${Math.round(enabledRule.intensity * 100)}%` : "—";
  el("duration").textContent = enabledRule ? `${enabledRule.duration}s` : "—";
  el("face").textContent = camera.face_detected ? "Detected" : "Not detected";
  el("object").textContent = camera.object_detected ? `Tracked · ${camera.object_mode}` : "Not tracked";
  el("interaction").textContent = camera.interaction_state;
  el("interaction-badge").textContent = camera.interaction_state;
  el("confidence").textContent = camera.interaction_confidence.toFixed(2);
  el("fps").textContent = camera.fps.toFixed(1);
  el("automation-badge").textContent = automation.state;
  el("rule-name").textContent = enabledRule?.name || "None enabled";
  el("pattern").textContent = enabledRule ? enabledRule.pattern.replaceAll("_", " ") : "—";
  el("cooldown").textContent = enabledRule ? `${enabledRule.cooldown}s` : "—";
  const session = automation.session || {};
  if (session.enabled && session.next_pattern) {
    el("pattern").textContent = `${session.next_pattern.replaceAll("_", " ")} · next`;
  }
  el("session-phase").textContent = session.phase || "Off";
  el("session-progress").textContent = session.enabled ?
    `${session.completed_pulses} / ${session.total_pulses} bounded pulses` : "—";
  el("camera-start").disabled = activeCamera || busy;
  el("camera-stop").disabled = !activeCamera || busy;
  const armed = ["ARMED", "ACTIVE", "COOLDOWN"].includes(automation.state);
  el("guided-session").disabled = armed || busy;
  el("include-buildup").disabled = armed || busy || !el("guided-session").checked;
  for (const id of ["opening-pulses", "middle-pulses"]) {
    el(id).disabled = armed || busy || !el("guided-session").checked;
  }
  el("buildup-pulses").disabled = armed || busy || !el("guided-session").checked || !el("include-buildup").checked;
  el("arm").disabled = busy || armed || !activeCamera || camera.mode !== "oral" || !selected || !enabledRule ||
    status.evaluation_active || !selected.vibration_features.includes(enabledRule.feature_index);
  el("disarm").disabled = busy || !armed;
  if (activeCamera && !streamAttached) {
    el("preview").src = `/api/camera/stream?session=${Date.now()}`;
    el("preview").hidden = false;
    el("preview-placeholder").hidden = true;
    streamAttached = true;
  } else if (!activeCamera && streamAttached) {
    el("preview").removeAttribute("src");
    el("preview").hidden = true;
    el("preview-placeholder").hidden = false;
    streamAttached = false;
  }
  if (automation.error) el("message").textContent = automation.error;
  else if (status.control_error) el("message").textContent = status.control_error;
  else if (camera.error) el("message").textContent = camera.error;
  else if (status.rules_error) el("message").textContent = status.rules_error;
}

async function act(path, body) {
  busy = true;
  try {
    await api(path, {method: "POST", ...(body ? {body: JSON.stringify(body)} : {})});
    await refresh();
  } catch (error) { notice(error); }
  finally { busy = false; await refresh().catch(notice); }
}

el("camera-start").addEventListener("click", async () => {
  busy = true;
  try {
    await api("/api/camera/mode", {method: "POST", body: JSON.stringify({mode: "oral"})});
    await api("/api/camera/start", {method: "POST"});
  } catch (error) { notice(error); }
  finally { busy = false; await refresh().catch(notice); }
});
el("camera-stop").addEventListener("click", () => act("/api/camera/stop"));
el("arm").addEventListener("click", () => {
  if (!enabledRule) return;
  const body = {rule_id: enabledRule.id};
  if (el("guided-session").checked) {
    body.session = {
      opening_pulses: Number(el("opening-pulses").value),
      middle_pulses: Number(el("middle-pulses").value),
      buildup_pulses: Number(el("buildup-pulses").value),
      include_buildup: el("include-buildup").checked
    };
  }
  act("/api/automation/arm", body);
});
el("disarm").addEventListener("click", () => act("/api/automation/disarm"));
el("emergency").addEventListener("click", () => act("/api/emergency-stop"));
el("quit-app").addEventListener("click", async () => {
  if (!window.confirm("Quit SelfPleasure? The app will attempt to stop output and close the camera. Verify physical stop.")) return;
  try {
    await api("/api/application/quit", {method: "POST"});
    el("message").textContent = "SelfPleasure is closing. Stop attempted and camera closed; verify physical stop.";
  } catch (error) { notice(error); }
});
refresh().catch(notice);
setInterval(() => { if (!busy) refresh().catch(notice); }, 1000);
