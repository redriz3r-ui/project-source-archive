from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from .models import Candidate, ChatWindow


def write_outputs(output_dir: Path, source_url: str, provider: str, windows: list[ChatWindow], candidates: list[Candidate]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "candidates.json").write_text(json.dumps([c.to_dict() for c in candidates], indent=2), encoding="utf-8")
    with (output_dir / "candidates.csv").open("w", newline="", encoding="utf-8") as handle:
        rows = [c.to_dict() for c in candidates]
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["rank", "peak_timestamp"])
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "windows.json").write_text(json.dumps([w.to_dict() for w in windows]), encoding="utf-8")
    (output_dir / "report.html").write_text(_html(source_url, provider, windows, candidates), encoding="utf-8")


def _html(source_url: str, provider: str, windows: list[ChatWindow], candidates: list[Candidate]) -> str:
    width, height = 1000, 220
    max_score = max((w.score for w in windows), default=1) or 1
    points = " ".join(f"{i * width / max(len(windows)-1, 1):.1f},{height - min(w.score/max_score, 1)*height:.1f}" for i, w in enumerate(windows))
    rows = "".join(
        f"<tr><td>{c.rank}</td><td>{fmt(c.peak_timestamp)}</td><td>{c.burst_score:.1f}</td>"
        f"<td>{c.standalone_score:.1f}</td><td>{c.peak_messages}</td><td>{html.escape(c.transcript[:240])}</td>"
        f"<td>{('<a href=\"'+html.escape(c.clip_path)+'\">clip</a>') if c.clip_path else '—'}</td></tr>" for c in candidates)
    return f"""<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\">
<title>StreamClip report</title><style>body{{font:15px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;background:#0d1117;color:#e6edf3}}a{{color:#58a6ff}}.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px;margin:18px 0}}svg{{width:100%;height:220px;background:#090c10}}polyline{{fill:none;stroke:#f778ba;stroke-width:2}}table{{border-collapse:collapse;width:100%}}th,td{{padding:10px;border-bottom:1px solid #30363d;text-align:left}}small{{color:#8b949e}}</style></head>
<body><h1>StreamClip analysis</h1><small>{html.escape(provider)} · <a href=\"{html.escape(source_url)}\">source</a></small>
<div class=card><h2>Normalized chat-burst timeline</h2><svg viewBox=\"0 0 {width} {height}\" preserveAspectRatio=\"none\"><polyline points=\"{points}\"/></svg></div>
<div class=card><h2>Top candidates</h2><table><thead><tr><th>#</th><th>Time</th><th>Burst</th><th>Short score</th><th>Msgs/window</th><th>Transcript</th><th>File</th></tr></thead><tbody>{rows}</tbody></table></div></body></html>"""


def fmt(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"

