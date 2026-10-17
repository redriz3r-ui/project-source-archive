const el = (id) => document.getElementById(id);
let streamAttached = false;
let busy = false;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    cache: "no-store"
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function message(error) { el("message").textContent = error.message || String(error); }
function metric(container, label, value) {
  const row = document.createElement("div");
  row.className = "metric";
  const name = document.createElement("span");
  name.textContent = label;
  const number = document.createElement("strong");
  number.textContent = value === null || value === undefined ? "Not measurable" : String(value);
  row.append(name, number);
  container.append(row);
}
function renderReport(target, report) {
  const container = el(target);
  container.replaceChildren();
  if (!report) { metric(container, "Result", "Stop evaluation to calculate metrics"); return; }
  for (const [label, value] of [
    ["Labeled frames", report.labeled_frames],
    ["Uncertain frames", report.uncertain_frames],
    ["Precision", report.precision],
    ["Recall", report.recall],
    ["False-positive episodes", report.false_positive_episodes],
    ["Negative time (seconds)", report.negative_labeled_seconds],
    ["False-positive episodes / hour", report.false_positive_episodes_per_hour],
    ["Missed intended intervals", report.missed_interactions],
    ["Mean start latency (seconds)", report.mean_start_latency_s],
    ["Mean end latency (seconds)", report.mean_end_latency_s],
    ["Unresolved ends", report.unresolved_ends]
  ]) metric(container, label, value);
  metric(container, "Recommendation", report.recommendation);
}
function renderSamples(samples) {
  const body = el("recent-samples");
  body.replaceChildren();
  for (const sample of [...samples].reverse()) {
    const row = document.createElement("tr");
    const values = [
      `${sample.elapsed_s}s`, sample.label, sample.state,
      sample.confidence ?? "—", sample.distance_mouth_widths ?? "—",
      `${sample.face_detected ? "Face" : "No face"} / ${sample.object_detected ? "Object" : "No object"}`
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = String(value);
      row.append(cell);
    }
    body.append(row);
  }
}

async function refresh() {
  const [evaluation, camera, automation] = await Promise.all([
    api("/api/evaluation/status"), api("/api/camera/status"), api("/api/automation/status")
  ]);
  const cameraOn = ["starting", "running"].includes(camera.status);
  el("camera-state").textContent = camera.status;
  el("evaluation-state").textContent = evaluation.active ? (evaluation.recording ? "Recording numeric data" : "Paused") : "Off";
  el("automation-state").textContent = automation.state;
  el("current-label").textContent = evaluation.label || "—";
  for (const [id, label] of [["label-negative", "NO_INTERACTION"], ["label-positive", "INTENDED"], ["label-uncertain", "UNCERTAIN"]]) {
    el(id).setAttribute("aria-pressed", evaluation.label === label ? "true" : "false");
  }
  el("sample-count").textContent = String(evaluation.sample_count);
  el("draft-json").hidden = !evaluation.draft_id;
  el("camera-start").disabled = cameraOn || busy;
  el("camera-stop").disabled = !cameraOn || busy;
  el("start-evaluation").disabled = busy || !cameraOn || evaluation.active || !!evaluation.draft_id || !["DISARMED", "EMERGENCY_STOP", "ERROR"].includes(automation.state);
  el("stop-evaluation").disabled = busy || !evaluation.active;
  for (const id of ["label-negative", "label-positive", "label-uncertain"]) el(id).disabled = busy || !evaluation.recording;
  el("save-evaluation").disabled = busy || evaluation.active || !evaluation.draft_id;
  el("discard-evaluation").disabled = busy || !evaluation.draft_id;
  if (cameraOn && !streamAttached) {
    el("preview").src = `/api/camera/stream?evaluation=${Date.now()}`;
    el("preview").hidden = false;
    el("preview-placeholder").hidden = true;
    streamAttached = true;
  } else if (!cameraOn && streamAttached) {
    el("preview").removeAttribute("src");
    el("preview").hidden = true;
    el("preview-placeholder").hidden = false;
    streamAttached = false;
  }
  renderReport("report", evaluation.report);
  renderSamples(evaluation.recent_samples);
  if (evaluation.error) el("message").textContent = evaluation.error;
}

async function action(path, body) {
  busy = true;
  try {
    const result = await api(path, {method: "POST", ...(body ? {body: JSON.stringify(body)} : {})});
    await refresh();
    return result;
  } catch (error) { message(error); return null; }
  finally { busy = false; await refresh().catch(message); }
}

el("camera-start").addEventListener("click", async () => {
  busy = true;
  try {
    await api("/api/camera/mode", {method: "POST", body: JSON.stringify({mode: "oral"})});
    await api("/api/camera/start", {method: "POST"});
  } catch (error) { message(error); }
  finally { busy = false; await refresh().catch(message); }
});
el("camera-stop").addEventListener("click", () => action("/api/camera/stop"));
el("emergency").addEventListener("click", () => action("/api/emergency-stop"));
el("start-evaluation").addEventListener("click", async () => {
  if (!el("collect-consent").checked) { message(new Error("Check the numeric collection consent box first.")); return; }
  const result = await action("/api/evaluation/start", {consent: true});
  if (result) el("message").textContent = "Evaluation active. Choose a manual label for each interval; device activation is blocked.";
});
for (const [id, label] of [["label-negative", "NO_INTERACTION"], ["label-positive", "INTENDED"], ["label-uncertain", "UNCERTAIN"]]) {
  el(id).addEventListener("click", async () => {
    const result = await action("/api/evaluation/label", {label});
    if (result) el("message").textContent = `Label changed to ${label}.`;
  });
}
el("stop-evaluation").addEventListener("click", async () => {
  const result = await action("/api/evaluation/stop");
  if (result) el("message").textContent = "Stopped. Review the numeric report, then save with separate consent or discard.";
});
el("save-evaluation").addEventListener("click", async () => {
  if (!el("save-consent").checked) { message(new Error("Check the separate local-save consent box first.")); return; }
  const result = await action("/api/evaluation/save", {consent: true});
  if (result) { el("message").textContent = "Numeric session saved locally."; el("save-consent").checked = false; await refreshSaved(); }
});
el("discard-evaluation").addEventListener("click", async () => {
  if (!window.confirm("Discard this unsaved numeric draft? This cannot be undone.")) return;
  const result = await action("/api/evaluation/discard");
  if (result) el("message").textContent = "Unsaved draft discarded.";
});

async function refreshSaved() {
  const sessions = await api("/api/evaluation/sessions");
  const list = el("saved-sessions");
  list.replaceChildren();
  if (!sessions.length) { const empty = document.createElement("p"); empty.className = "hint"; empty.textContent = "No saved sessions."; list.append(empty); }
  for (const session of sessions) {
    const card = document.createElement("article"); card.className = "rule-card";
    const title = document.createElement("strong"); title.textContent = `${session.started_at} · ${session.sample_count} numeric samples`;
    const actions = document.createElement("div"); actions.className = "inline-actions compact";
    const review = document.createElement("button"); review.type = "button"; review.textContent = "Review";
    review.addEventListener("click", async () => {
      try {
        const data = await api(`/api/evaluation/sessions/${session.id}`);
        renderReport("saved-report", data.report);
        el("saved-summary").textContent = `Labels: ${data.label_changes.length} changes · ${data.samples.length} numeric samples · no frames saved.`;
        el("saved-json").href = `/api/evaluation/sessions/${session.id}`;
        el("saved-review").hidden = false;
      } catch (error) { message(error); }
    });
    const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "Delete"; remove.className = "danger";
    remove.addEventListener("click", async () => {
      if (!window.confirm("Permanently delete this local numeric session?")) return;
      try {
        await api(`/api/evaluation/sessions/${session.id}`, {method: "DELETE"});
        el("saved-review").hidden = true;
        el("message").textContent = "Saved numeric session deleted.";
        await refreshSaved();
      } catch (error) { message(error); }
    });
    actions.append(review, remove); card.append(title, actions); list.append(card);
  }
}

refresh().catch(message);
refreshSaved().catch(message);
setInterval(() => { if (!busy) refresh().catch(message); }, 1000);
