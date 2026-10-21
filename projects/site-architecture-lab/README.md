# Site Architecture Lab

An offline Python 3.11+ HAR analysis engine with a React + TypeScript dashboard. The initial research target is Chaturbate, but this repository contains **only synthetic example traffic**, with no claims about that site's production systems. No live fetching, crawling, third-party interaction automation, media reconstruction, telemetry or external AI calls are implemented.

## Setup on macOS / Apple Silicon

Install Python 3.11+ and Node.js 20.19+ (Node 22 also works), then from this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
npm --prefix dashboard ci
npm --prefix dashboard run build
./run.sh
```

Open http://127.0.0.1:8765. This single launch command serves the built dashboard and API on loopback. Each restart loads the synthetic example and regenerates its reports. To use another port: `./run.sh --port 8766`.

Use **Import HAR** to analyze a capture in the browser. The file is sent only to the local Python engine; raw bytes are not saved. Import replaces the current in-memory analysis and the five local report files. This is a single-user workspace, not a multi-user server. Keep it bound to loopback.

For CLI analysis:

```sh
.venv/bin/site-architecture-lab analyze examples/synthetic.har --synthetic
.venv/bin/site-architecture-lab analyze captures/homepage.har --output reports/homepage
```

CLI output is independent of the running dashboard; import the same HAR in the interface to view it. Generated reports are excluded from Git. The synthetic fixture intentionally contains a fake query secret to exercise redaction.

## Capture the first public Chaturbate homepage HAR

1. Review the site's terms and use only ordinary browsing you are authorized to perform. Use a fresh signed-out Chrome profile, without extensions or other tabs. Do not log in, open profiles/rooms, enter chat, interact with performers, or access paid content.
2. Open Chrome DevTools → Network **before** navigating. Turn off Preserve log and clear the request list. Keep the usual browser cache settings for an ordinary page load.
3. Navigate manually to `https://chaturbate.com/` once. If an age/consent/access gate appears, stop the capture there; do not bypass it. The analysis will describe only what loaded. Stop Network recording after the initial homepage load. If media starts, stop recording immediately; do not intentionally play streams or collect media payloads.
4. Right-click the request table and choose **Save all as HAR (sanitized)** / the sanitized HAR export option available in your Chrome version. Do not enable the preference to include sensitive data. Chrome's sanitization is incomplete: URLs, bodies and identifiers may still be present. Do not share the raw capture. If your Chrome cannot export without media/body contents, avoid exporting those requests and remove content.text, postData, cookies and credential fields locally before import. This app never fetches media, but cannot undo what a browser already captured.
5. Save under `captures/homepage.har` in this project (create `captures/` if needed). HAR files and that directory are Git-ignored. Store captures only as long as needed, then delete them.
6. Launch `./run.sh`, click **Import HAR**, select that file, and inspect Findings, Network Explorer and Timeline. Or use the CLI command above. Review normalized hosts and all report text before sharing.

Chrome menu labels can vary by version. No browser traffic has been collected for this implementation.

## Views and generated documents

- **Overview:** counts, distinct observed hosts (privacy aliases), timing average, transport signals and request composition.
- **Network Explorer:** search and host/method/type/status filters, size/duration sorting, normalized endpoints, caching flags, security-header presence and initiator category.
- **Architecture Graph:** selectable, keyboard-accessible request role nodes, zoom, scroll pan and supporting request IDs. Browser-to-group edges describe observed requests; groups and browser origin are labeled inferences. No backend-to-backend connections are invented.
- **Timeline:** relative request start and total duration; missing starts remain unknown.
- **Findings:** OBSERVED / INFERRED / UNKNOWN, confidence, evidence IDs and report downloads.

The engine creates `architecture.md`, `architecture.mmd`, `requests-summary.json`, `technology-evidence.md`, and `research-gaps.md` in the chosen report directory. The report JSON includes only an explicit metadata allowlist. No raw capture is copied into the dashboard.

## Privacy and interpretation

All query values, fragments, credentials, request/response bodies, cookie and authorization data, initiator stacks, response header values and unrecognized fields are discarded. Cache values retain only recognized directives and bounded numeric max-age; security headers expose names only. Unknown path segments become `[redacted]`; asset names become `[asset].extension`. Initiator categories and MIME values use allowlists.

Subdomains are masked and remaining domain labels validated; domain names can still identify organizations. Per-capture aliases (H1, H2, …) preserve distinct observed host counts without exposing raw subdomains. The final two labels are retained without a public suffix database and must not be treated as a registrable-domain determination. This conservative policy trades detail for privacy. Do not expose the local API publicly. Input is limited to 25 MiB / 100,000 entries. Raw files can contain sensitive material even after Chrome sanitization; exported reports still require review.

Classification rules: JSON or `/api`/`graphql` paths are API-like; JavaScript/CSS are frontend assets; a 101 response plus WebSocket Upgrade is an observed handshake; event-stream indicates SSE; `/poll` and `/polling` are inferred polling candidates. HLS/DASH extensions and MIME values indicate manifests; `.ts`/`.m4s` and media MIME types indicate segments/media. SDP or explicit WebRTC/STUN/TURN path segments are weak WebRTC hints. No manifest, segment or stream is fetched, decoded or reconstructed. These signals do not prove vendors or backend topology.

HAR often excludes WebSocket frames and WebRTC transports. Script/parser/preload initiators do not prove exact execution dependencies. Frameworks, application initialization internals, CDN vendors, backend languages, databases and internal service boundaries remain UNKNOWN unless independent evidence is supplied. No Python/Django claim is made. Capture duration, missing/cache-served requests and unknown transfer sizes limit conclusions. `bodySize=-1` is displayed as zero/unavailable; duration uses HAR `time`.

## Development and verification

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tests/smoke_local.py # with ./run.sh running on 8765
npm --prefix dashboard run build
# Optional hot-reload UI, with the engine running on 8765:
npm --prefix dashboard run dev
```

The Vite development proxy forwards local API and report requests. Use the built application for HAR imports (same-origin protections can reject development-origin uploads). The engine uses only Python's standard library at runtime. Frontend dependencies are locked in package-lock.json.

Implementation: `analysis.py` orchestrates the pure-function modules `http_analysis.py`, `frontend.py`, `realtime.py`, `streaming.py` and `privacy.py`; `reports.py` creates evidence documents; `cli.py` provides the CLI/local server; `dashboard/` consumes redacted JSON only. The engine can be reused for any HAR, with no dependency on the dashboard or target site.

## Troubleshooting

- Missing dashboard: run `npm --prefix dashboard ci` then `npm --prefix dashboard run build`.
- Port busy: use `./run.sh --port 8766` and open the printed URL.
- Invalid HAR: verify it has `log.entries` with request/response objects, rather than a DevTools trace. Split captures over 25 MiB into smaller homepage-only exports; do not upload them to external services.
- No media/WebSockets/framework findings: absence from HAR is not evidence of absence. Read research-gaps.md.
- Unexpected collapsed URLs/hosts: conservative privacy normalization intentionally removes identifiers and asset names.
- Import error: the previous in-memory analysis remains available; malformed input details and raw URLs are never logged.
- Installation cannot reach a package registry: use an approved network connection or cached packages; the running application needs no internet access.

## Dashboard preview

![Synthetic overview](docs/dashboard.png)
