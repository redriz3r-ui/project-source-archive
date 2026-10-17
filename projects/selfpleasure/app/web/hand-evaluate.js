const strokeEl = (id) => document.getElementById(id);
let strokeBusy = false;
let strokeStream = false;

async function strokeApi(path, options = {}) {
  const response = await fetch(path, {
    ...options, headers: {"Content-Type": "application/json", ...(options.headers || {})},
    cache: "no-store"
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function strokeMessage(error) { strokeEl("stroke-message").textContent = error.message || String(error); }
function strokeMetric(label, value) {
  const row = document.createElement("div");
  row.className = "metric";
  const left = document.createElement("span");
  const right = document.createElement("strong");
  left.textContent = label;
  right.textContent = value == null ? "Not measurable" : String(value);
  row.append(left, right);
  strokeEl("stroke-report").append(row);
}
function renderStrokeReport(report) {
  strokeEl("stroke-report").replaceChildren();
  if (!report) { strokeMetric("Result", "Stop evaluation to calculate metrics"); return; }
  for (const [label, value] of [
    ["Manual strokes", report.manual_strokes], ["Detected strokes", report.detected_strokes],
    ["Matched strokes", report.matched_strokes], ["Missed strokes", report.missed_strokes],
    ["False detections", report.false_detections], ["Stroke-count accuracy", report.stroke_count_accuracy],
    ["Precision", report.precision], ["Recall", report.recall],
    ["False detections / negative hour", report.false_detections_per_hour],
    ["Mean detection latency (s)", report.mean_detection_latency_s],
    ["Detection latencies (s)", report.detection_latencies_s.join(", ") || "—"],
    ["Matching window (s)", report.matching_window_s]
  ]) strokeMetric(label, value);
  strokeMetric("Limit", report.warning);
}

async function refreshStrokeSessions() {
  const sessions = await strokeApi("/api/stroke-evaluation/sessions");
  const list = strokeEl("stroke-sessions");
  list.replaceChildren();
  if (!sessions.length) { list.textContent = "No saved sessions."; return; }
  for (const session of sessions) {
    const card = document.createElement("div");
    card.className = "rule-card";
    const title = document.createElement("strong");
    title.textContent = `${session.started_at} · ${session.id.slice(0, 8)}`;
    const summary = document.createElement("p");
    summary.textContent = `Manual ${session.report.manual_strokes} · detected ${session.report.detected_strokes} · precision ${session.report.precision ?? "—"}`;
    const review = document.createElement("a");
    review.href = `/api/stroke-evaluation/sessions/${session.id}`;
    review.target = "_blank";
    review.rel = "noopener";
    review.textContent = "Review numeric JSON";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "danger";
    remove.textContent = "Delete";
    remove.addEventListener("click", async () => {
      if (!confirm("Delete this saved numeric stroke session?")) return;
      try {
        await strokeApi(`/api/stroke-evaluation/sessions/${session.id}`, {method: "DELETE"});
        await refreshStrokeSessions();
      } catch (error) { strokeMessage(error); }
    });
    card.append(title, summary, review, remove);
    list.append(card);
  }
}

async function refreshStroke() {
  const [camera, evaluation] = await Promise.all([
    strokeApi("/api/camera/status"), strokeApi("/api/stroke-evaluation/status")
  ]);
  const active = ["starting", "running"].includes(camera.status);
  const handActive = active && camera.mode === "hand";
  strokeEl("stroke-camera-state").textContent = `${camera.status} · ${camera.mode} · ${camera.hand.state}`;
  strokeEl("stroke-position").textContent = camera.hand.travel_position == null ?
    `— / ${camera.fps.toFixed(1)} FPS` :
    `${(camera.hand.travel_position * 100).toFixed(0)}% / ${camera.fps.toFixed(1)} FPS`;
  strokeEl("stroke-camera-start").disabled = active || strokeBusy;
  strokeEl("stroke-camera-stop").disabled = !active || strokeBusy;
  strokeEl("stroke-session-state").textContent = evaluation.active ?
    (evaluation.recording ? "Recording" : "Paused") : evaluation.draft_id ? "Draft ready" : "Off";
  strokeEl("stroke-current-label").textContent = evaluation.current_label || "UNCERTAIN";
  strokeEl("stroke-counts").textContent = `${evaluation.manual_stroke_count} / ${evaluation.detected_stroke_count}`;
  strokeEl("stroke-eval-start").disabled = strokeBusy || !handActive || evaluation.active || !!evaluation.draft_id;
  strokeEl("stroke-eval-stop").disabled = strokeBusy || !evaluation.active;
  for (const id of ["stroke-label-positive", "stroke-label-negative", "stroke-label-uncertain"]) {
    strokeEl(id).disabled = strokeBusy || !evaluation.active || !evaluation.recording;
  }
  strokeEl("stroke-mark").disabled = strokeBusy || !evaluation.recording || evaluation.current_label !== "STROKES";
  strokeEl("stroke-save").disabled = strokeBusy || evaluation.active || !evaluation.draft_id;
  strokeEl("stroke-discard").disabled = strokeBusy || !evaluation.draft_id;
  strokeEl("stroke-draft-link").hidden = !evaluation.draft_id;
  renderStrokeReport(evaluation.report);
  if (handActive && !strokeStream) {
    strokeEl("stroke-preview").src = `/api/camera/stream?session=${Date.now()}`;
    strokeEl("stroke-preview").hidden = false;
    strokeEl("stroke-placeholder").hidden = true;
    strokeStream = true;
  } else if (!handActive && strokeStream) {
    strokeEl("stroke-preview").removeAttribute("src");
    strokeEl("stroke-preview").hidden = true;
    strokeEl("stroke-placeholder").hidden = false;
    strokeStream = false;
  }
  if (evaluation.error || camera.error) strokeEl("stroke-message").textContent = evaluation.error || camera.error;
}

async function strokeAction(path, body) {
  strokeBusy = true;
  try {
    const result = await strokeApi(path, {method: "POST", ...(body ? {body: JSON.stringify(body)} : {})});
    await refreshStroke();
    return result;
  } catch (error) { strokeMessage(error); return null; }
  finally { strokeBusy = false; await refreshStroke().catch(strokeMessage); }
}

strokeEl("stroke-camera-start").addEventListener("click", async () => {
  strokeBusy = true;
  try {
    await strokeApi("/api/camera/mode", {method: "POST", body: JSON.stringify({mode: "hand"})});
    await strokeApi("/api/camera/start", {method: "POST"});
  } catch (error) { strokeMessage(error); }
  finally { strokeBusy = false; await refreshStroke().catch(strokeMessage); }
});
strokeEl("stroke-camera-stop").addEventListener("click", () => strokeAction("/api/camera/stop"));
strokeEl("stroke-emergency").addEventListener("click", () => strokeAction("/api/emergency-stop"));
strokeEl("stroke-eval-start").addEventListener("click", async () => {
  if (!strokeEl("stroke-collect-consent").checked) {
    strokeMessage(new Error("Check numeric collection consent first.")); return;
  }
  await strokeAction("/api/stroke-evaluation/start", {consent: true});
});
strokeEl("stroke-eval-stop").addEventListener("click", () => strokeAction("/api/stroke-evaluation/stop"));
for (const [id, label] of [["stroke-label-positive", "STROKES"],
                            ["stroke-label-negative", "NO_STROKES"],
                            ["stroke-label-uncertain", "UNCERTAIN"]]) {
  strokeEl(id).addEventListener("click", () => strokeAction("/api/stroke-evaluation/label", {label}));
}
strokeEl("stroke-mark").addEventListener("click", () => strokeAction("/api/stroke-evaluation/mark"));
strokeEl("stroke-save").addEventListener("click", async () => {
  if (!strokeEl("stroke-save-consent").checked) {
    strokeMessage(new Error("Check local save consent first.")); return;
  }
  const result = await strokeAction("/api/stroke-evaluation/save", {consent: true});
  if (result) await refreshStrokeSessions();
});
strokeEl("stroke-discard").addEventListener("click", () => strokeAction("/api/stroke-evaluation/discard"));
Promise.all([refreshStroke(), refreshStrokeSessions()]).catch(strokeMessage);
setInterval(() => { if (!strokeBusy) refreshStroke().catch(strokeMessage); }, 500);
