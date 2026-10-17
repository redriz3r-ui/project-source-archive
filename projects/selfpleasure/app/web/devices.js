const byId = (id) => document.getElementById(id);
let inventory = [];
let busy = false;
let lastSelectedId = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function notice(text) { byId("message").textContent = text; }

async function refresh() {
  const [status, devices, automation] = await Promise.all([
    api("/api/status"), api("/api/devices"), api("/api/automation/status")
  ]);
  inventory = devices;
  byId("connection").textContent = status.intiface === "connected" ? "Connected" : "Not connected";
  byId("connect").disabled = status.evaluation_active || busy;
  byId("scan").disabled = status.evaluation_active || status.intiface !== "connected" || status.test_running || busy;
  byId("disconnect").disabled = status.evaluation_active || status.intiface !== "connected" || busy;
  const selector = byId("devices");
  selector.replaceChildren(new Option("None selected", ""));
  for (const device of devices) {
    selector.add(new Option(`${device.name}${device.simulated ? " (simulated)" : ""}`, device.id));
  }
  selector.value = status.device || "";
  selector.disabled = status.evaluation_active || busy;
  const selected = devices.find((device) => device.id === status.device);
  if (lastSelectedId !== status.device) {
    lastSelectedId = status.device;
    byId("bench-confirmation").checked = false;
    const feature = byId("feature");
    feature.replaceChildren();
    for (const index of selected?.vibration_features || []) {
      feature.add(new Option(`Vibration feature ${index}`, String(index)));
    }
    if (!feature.options.length) feature.add(new Option("No vibration output", ""));
  }
  byId("capabilities").textContent = selected
    ? `Outputs: ${selected.capabilities.join(", ") || "none"}. ${selected.can_vibrate ? "Vibration supported." : "No vibration output."}`
    : "No device selected.";
  const automationArmed = ["ARMED", "ACTIVE", "COOLDOWN"].includes(automation.state);
  const benchSelected = Boolean(selected && !selected.simulated && status.real_device_manual_bench_enabled && !status.real_device_output_enabled);
  const realLocked = Boolean(selected && !selected.simulated && !status.real_device_output_enabled && !benchSelected);
  byId("bench-warning").hidden = !benchSelected;
  byId("bench-confirmation-row").hidden = !benchSelected;
  const ready = Boolean(selected?.can_vibrate && byId("feature").value !== "") && !realLocked &&
    (!benchSelected || byId("bench-confirmation").checked) && !status.test_running && !automationArmed && !status.evaluation_active && !busy;
  byId("enable").disabled = !ready;
  byId("test").disabled = !ready || !status.activation_enabled;
  byId("intensity").disabled = !ready;
  byId("duration").disabled = !ready;
  byId("feature").disabled = status.test_running || status.evaluation_active || busy;
  byId("intensity").max = String(Math.round(status.max_intensity * 100));
  byId("duration").max = String(status.max_duration);
  if (Number(byId("intensity").value) > Math.round(status.max_intensity * 100))
    byId("intensity").value = String(Math.round(status.max_intensity * 100));
  if (Number(byId("duration").value) > status.max_duration)
    byId("duration").value = String(status.max_duration);
  byId("intensity-value").textContent = `${byId("intensity").value}%`;
  byId("limits").textContent = `Maximum intensity ${Math.round(status.max_intensity * 100)}%; maximum duration ${status.max_duration} seconds. Enable one test before each run.`;
  if (benchSelected) byId("limits").textContent += " Off-body manual tests only; automation stays locked. Verify physical stop after each test.";
  if (automationArmed) byId("limits").textContent += " Disarm automation before manual testing.";
  if (realLocked) byId("limits").textContent = "Real-device output is locked after a failed physical stop. Do not retry this device; use the simulator.";
  if (status.evaluation_active) byId("limits").textContent += " Evaluation mode blocks device control.";
  if (status.control_error) notice(status.control_error);
  else if (status.intiface_error) notice(status.intiface_error);
}

async function action(path, options = {}) {
  busy = true;
  try {
    const result = await api(path, { method: "POST", ...options });
    await refresh();
    return result;
  } catch (error) {
    notice(error.message);
  } finally {
    busy = false;
    await refresh();
  }
}

byId("connect").addEventListener("click", async () => { await action("/api/intiface/connect"); });
byId("scan").addEventListener("click", async () => { await action("/api/intiface/scan"); });
byId("disconnect").addEventListener("click", async () => { await action("/api/intiface/disconnect"); });
byId("devices").addEventListener("change", async (event) => {
  if (event.target.value) {
    await action("/api/devices/select", { body: JSON.stringify({ device_id: event.target.value }) });
  }
});
byId("intensity").addEventListener("input", () => {
  byId("intensity-value").textContent = `${byId("intensity").value}%`;
});
byId("bench-confirmation").addEventListener("change", () => refresh().catch((error) => notice(error.message)));
byId("enable").addEventListener("click", async () => {
  const result = await action("/api/control/enable", {body: JSON.stringify({off_body_confirmed: byId("bench-confirmation").checked})});
  if (result?.enabled) notice("One manual test is enabled. Press Test Vibration when ready.");
});
byId("test").addEventListener("click", async () => {
  const intensity = Number(byId("intensity").value) / 100;
  const duration = Number(byId("duration").value);
  const feature_index = Number(byId("feature").value);
  const result = await action("/api/control/test", { body: JSON.stringify({ intensity, duration, feature_index,
    off_body_confirmed: byId("bench-confirmation").checked }) });
  if (result?.started) {
    byId("bench-confirmation").checked = false;
    notice(`Test started for ${duration} second(s); automatic stop will be attempted. Verify physical stop.`);
    await refresh();
  }
});
byId("stop").addEventListener("click", async () => {
  await action("/api/control/stop");
  notice("Stop attempted. Test disarmed; verify the device physically stopped.");
});
byId("emergency").addEventListener("click", async () => {
  await action("/api/emergency-stop");
  notice("Emergency Stop attempted. Verify physical stop; use the device's power control if needed.");
});

refresh().catch((error) => notice(error.message));
setInterval(() => { if (!busy) refresh().catch((error) => notice(error.message)); }, 1000);
