const el = (id) => document.getElementById(id);
let editingId = null;
let selectedId = null;
let busy = false;
let rules = [];

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
function clearForm() {
  editingId = null;
  el("rule-form").reset();
  el("save").textContent = "Create rule";
}

function formData() {
  if (el("feature").value === "") throw new Error("Select a device and vibration feature first.");
  return {
    name: el("name").value.trim(), trigger: "INTERACTION_ACTIVE", action: "VIBRATE",
    pattern: el("pattern").value, feature_index: Number(el("feature").value),
    intensity: Number(el("intensity").value) / 100,
    duration: Number(el("duration").value), cooldown: Number(el("cooldown").value),
    minimum_confidence: Number(el("confidence").value)
  };
}

function addRuleCard(rule, locked) {
  const card = document.createElement("article");
  card.className = "rule-card";
  const title = document.createElement("strong");
  title.textContent = `${rule.name} ${rule.enabled ? "· Enabled" : "· Disabled"}`;
  const description = document.createElement("p");
  description.className = "hint";
  description.textContent = `${rule.pattern.replaceAll("_", " ")} · Feature ${rule.feature_index} · ≤ ${Math.round(rule.intensity * 100)}% · ≤ ${rule.duration}s · ${rule.cooldown}s cooldown · score ≥ ${rule.minimum_confidence}`;
  const actions = document.createElement("div");
  actions.className = "inline-actions compact";
  for (const [label, callback] of [
    ["Edit", () => editRule(rule)],
    [rule.enabled ? "Disable" : "Enable", () => changeEnabled(rule)],
    ["Delete", () => deleteRule(rule)]
  ]) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.disabled = locked;
    button.addEventListener("click", callback);
    actions.append(button);
  }
  card.append(title, description, actions);
  el("rule-list").append(card);
}

async function refresh() {
  const [automation, status, devices, listed] = await Promise.all([
    api("/api/automation/status"), api("/api/status"), api("/api/devices"), api("/api/rules")
  ]);
  rules = listed;
  const locked = ["ARMED", "ACTIVE", "COOLDOWN"].includes(automation.state);
  el("automation-state").textContent = automation.state;
  const selected = devices.find((device) => device.id === status.device);
  if (selectedId !== status.device) {
    selectedId = status.device;
    el("feature").replaceChildren();
    for (const index of selected?.vibration_features || []) {
      el("feature").add(new Option(`Vibration feature ${index}`, String(index)));
    }
    if (!el("feature").options.length) el("feature").add(new Option("Select a device first", ""));
  }
  el("rule-list").replaceChildren();
  if (!rules.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "No rules yet. Create one below, then enable it.";
    el("rule-list").append(empty);
  }
  for (const rule of rules) addRuleCard(rule, locked || busy);
  for (const input of el("rule-form").querySelectorAll("input, select, button")) {
    if (input.id !== "simulator") input.disabled = locked || busy;
  }
  el("simulator").disabled = locked || busy;
  if (automation.error) notice(automation.error);
}

function editRule(rule) {
  editingId = rule.id;
  el("name").value = rule.name;
  el("pattern").value = rule.pattern;
  el("feature").value = String(rule.feature_index);
  el("intensity").value = String(Math.round(rule.intensity * 100));
  el("duration").value = String(rule.duration);
  el("cooldown").value = String(rule.cooldown);
  el("confidence").value = String(rule.minimum_confidence);
  el("save").textContent = "Save changes";
  previewPattern().catch(notice);
  el("rule-form").scrollIntoView({behavior: "smooth"});
}

async function changeEnabled(rule) {
  busy = true;
  try {
    await api(`/api/rules/${rule.id}/enabled`, {method: "POST", body: JSON.stringify({enabled: !rule.enabled})});
    el("message").textContent = rule.enabled ? "Rule disabled. Automation remains disarmed." : "Rule enabled. Arm separately on the dashboard.";
  } catch (error) { notice(error); }
  finally { busy = false; await refresh(); }
}

async function deleteRule(rule) {
  if (!window.confirm(`Delete the local rule “${rule.name}”?`)) return;
  busy = true;
  try {
    await api(`/api/rules/${rule.id}`, {method: "DELETE"});
    if (editingId === rule.id) clearForm();
    el("message").textContent = "Rule deleted.";
  } catch (error) { notice(error); }
  finally { busy = false; await refresh(); }
}

el("rule-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  busy = true;
  try {
    const data = formData();
    await api(editingId ? `/api/rules/${editingId}` : "/api/rules", {
      method: editingId ? "PUT" : "POST", body: JSON.stringify(data)
    });
    el("message").textContent = editingId ? "Rule updated." : "Rule created. Enable it before arming.";
    clearForm();
  } catch (error) { notice(error); }
  finally { busy = false; await refresh(); }
});

el("cancel").addEventListener("click", clearForm);
async function previewPattern() {
  const query = new URLSearchParams({
    pattern: el("pattern").value,
    intensity: String(Number(el("intensity").value) / 100),
    duration: el("duration").value
  });
  const data = await api(`/api/patterns/preview?${query}`);
  const chart = el("pattern-preview");
  chart.replaceChildren();
  for (const step of data.steps) {
    const segment = document.createElement("span");
    segment.className = step.intensity > 0 ? "pattern-on" : "pattern-off";
    segment.style.width = `${step.duration / data.duration * 100}%`;
    segment.style.height = `${Math.max(7, step.intensity / data.maximum_intensity * 100)}%`;
    segment.title = `${Math.round(step.intensity * 100)}% for ${step.duration.toFixed(2)}s`;
    chart.append(segment);
  }
  el("pattern-summary").textContent = `${data.pattern.replaceAll("_", " ")} · ${data.steps.length} steps · up to ${Math.round(data.maximum_intensity * 100)}% for at most ${data.duration}s. Visual only; no device command sent.`;
}
el("preview-pattern").addEventListener("click", () => previewPattern().catch(notice));
for (const id of ["pattern", "intensity", "duration"]) {
  el(id).addEventListener("change", () => previewPattern().catch(notice));
}
el("emergency").addEventListener("click", async () => {
  try {
    await api("/api/emergency-stop", {method: "POST"});
    el("message").textContent = "Emergency stop latched. Use the device's physical power control if needed.";
    await refresh();
  } catch (error) { notice(error); }
});
el("simulator").addEventListener("click", async () => {
  busy = true;
  try {
    const simulator = await api("/api/devices/simulated", {method: "POST"});
    await api("/api/devices/select", {method: "POST", body: JSON.stringify({device_id: simulator.id})});
    selectedId = null;
    el("message").textContent = "Simulator selected. It cannot control physical hardware.";
  } catch (error) { notice(error); }
  finally { busy = false; await refresh(); }
});

refresh().catch(notice);
previewPattern().catch(notice);
setInterval(() => { if (!busy) refresh().catch(notice); }, 2000);
