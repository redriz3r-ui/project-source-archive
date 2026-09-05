# Presidential pipeline

The presidential pipeline is a local orchestration and context-control layer around the existing documentary engine. Emilio Aguinaldo is the regression fixture. Migration indexes existing artifacts; it does not rewrite narration, media, audio, or video.

## Verified architecture

Stages are ordered as `evidence → narrative → visual_search → storyboard`, with `audio` depending on narrative, `preview` depending on storyboard and audio, `render` depending on preview, and `audit` depending on render.

Each indexed stage records a source/output hash, deterministic artifact handle, status, cache disposition, timing, model calls, token count, and update time in:

`public/wiki-tests/<slug>/.pipeline/state.json`

Full artifacts and logs remain on disk. CLI responses use bounded JSON receipts. Structured artifacts can be inspected by handle and JSON path without loading the complete file into model context.

## Commands

```bash
# Canonical generic interface: discover the episode from its title and replay
# only validated cached artifacts. A missing pipeline index is migrated once.
npm run president -- "Emilio Aguinaldo" --replay
npm run president -- "Manuel L. Quezon" --replay

# Index an existing completed project
npm run presidential -- migrate --slug=emilio-aguinaldo

# Compact status receipt
npm run presidential -- status --slug=emilio-aguinaldo

# Prove an unchanged run needs no network, model, narration, or render work
npm run presidential -- replay --slug=emilio-aguinaldo

# Retrieve a bounded part of an artifact
npm run presidential -- inspect-handle --slug=emilio-aguinaldo \
  --handle 'artifact:approved-narrative.json:<hash>' \
  --path '$.openingProof.beats' --limit 2

# Mark a stage and only its dependents stale
npm run presidential -- invalidate-stage --slug=emilio-aguinaldo \
  --stage storyboard

# Recreate and verify compact director context
npm run presidential -- sidecar --slug=emilio-aguinaldo

# Read preview/render/audit gates without producing media
npm run presidential -- preview --slug=emilio-aguinaldo
npm run presidential -- render --slug=emilio-aguinaldo
npm run presidential -- audit --slug=emilio-aguinaldo

# Write the per-episode token projection
npm run presidential -- projection --slug=emilio-aguinaldo
```

Both canonical replay commands are regression-tested. They verify every current
artifact hash before returning `PASS`; changed or missing artifacts fail closed.
The receipt reports zero model calls, tokens, network calls, and render attempts.

## New episode workflow

Initialize an episode once with the editorial metadata that cannot be safely
inferred from an article:

```bash
npm run president -- "President Name" --init \
  --number=3 --term="1944–1946" --title="Segment title"
```

Then run or resume with the same command:

```bash
npm run president -- "President Name"
```

The runner advances deterministically until a creative approval is required:

1. Fetch and compile the Wikipedia article when `article.json` is missing.
2. Write a bounded `narrative-director-request.json` and reserve its maximum
   token cost. The run stops until `approved-narrative.json` exists.
3. Reconcile actual narrative size, write `visual-director-request.json`, and
   reserve the visual call. The run stops until `approved-visual-plan.json`
   exists.
4. Query Wikimedia metadata, enforce rights and coverage, download and decode
   authentic media, run local macOS TTS, and assemble the generic manifest.
5. Render a still at every asset boundary and stop with
   `AWAITING_HUMAN_REVIEW`.
6. Approve the storyboard preview explicitly:

```bash
npm run presidential -- approve-preview --slug=president-name
```

7. Run the canonical command again. It performs at most one full render using
   a 90-second frame timeout and concurrency 1, runs ffprobe and a full FFmpeg
   decode scan, writes validation, and indexes the completed episode.

Individual deterministic stages remain callable for diagnosis:

```bash
npm run presidential -- prepare-narrative --slug=president-name
npm run presidential -- prepare-visual --slug=president-name
npm run presidential -- produce --slug=president-name
npm run presidential -- build-preview --slug=president-name
npm run presidential -- render-final --slug=president-name
npm run presidential -- verify --slug=president-name
```

The director interface is deliberately file-based. No model provider or
credential is silently selected. A human, Codex, a local model, or a future API
adapter may fulfill the two JSON requests, but the runner reserves and
reconciles their bounded context against `usage-ledger.json`. All later stages
use zero language-model tokens.

## Local Ollama director

The optional local director uses Ollama structured outputs and defaults to
`qwen3:4b`. It validates narrative word count and evidence IDs, then validates
visual filenames, beat coverage, and reuse limits before writing either
approved artifact. The model is unloaded after each request so Remotion has the
machine's memory available for rendering.

```bash
# Generate both approval files, but do not continue into rendering.
npm run presidential -- local-direct --slug=president-name

# Local-first canonical workflow. This generates missing director files and
# continues through media, narration, and preview. It still stops for human
# preview approval before the full render.
npm run president -- "President Name" --local

# Override the model when the machine has enough memory.
npm run president -- "President Name" --local --model qwen3:4b
```

Ollama must be running at `http://127.0.0.1:11434`. Override the endpoint with
`OLLAMA_HOST` and the default model with `LOCAL_DIRECTOR_MODEL`.

## Wikimedia acquisition cache

Media acquisition is shared across episodes. Commons metadata is cached by
normalized filename and downloaded image bytes are stored by Wikimedia SHA-1:

```text
public/archive-cache/wikimedia/metadata/
public/archive-cache/wikimedia/objects/
```

An asset already acquired for one president can therefore be copied into a new
episode without another metadata query or image download. On first use after
this upgrade, the adapter can also import matching verified media from an older
episode into the shared object cache. Episode-specific copies remain under
`public/wiki-tests/<slug>/media/`, so existing manifests and renders are not
coupled to the cache layout.

Set a descriptive, contactable Wikimedia user agent before a production run:

```bash
export WIKIMEDIA_USER_AGENT="HistoryDocumentaryEngine/0.7 (your-email-or-project-url)"
```

Requests use the official Commons API and file URLs, run serially, include
`maxlag`, time out, and retry temporary throttling with backoff. No third-party
image proxy is used. Metadata calls are grouped, and only the rights fields the
pipeline validates are requested.

Visual plans may provide preapproved fallbacks. They are attempted in order
only when the primary file is unavailable, invalid, or fails the rights gate:

```json
{
  "id": "asset-03",
  "filename": "Primary historical photograph.jpg",
  "alternates": [
    "Alternate historical photograph.jpg",
    "Second alternate.jpg"
  ]
}
```

The rights ledger records requested and resolved filenames, official URLs,
license, Commons SHA-1, and cache status. If no approved candidate succeeds,
the stage fails closed and writes a compact diagnostic receipt to
`public/wiki-tests/<slug>/.pipeline/acquisition-failure.json`.

Remotion now exposes one data-driven composition named `PresidentSegment`.
Episode manifests are supplied as props and `calculateMetadata` derives duration
from the manifest, so new presidents do not require a new `Root.tsx` registration.

Supplemental evidence uses namespaced paragraph IDs such as `laurel:p-0001`.
The sidecar compiler discovers the matching cached Wikipedia article locally and
requires complete paragraph coverage across every source.

`record`, `resume`, and `run-through-stage` currently expose indexing/replay semantics for completed fixtures. They do not yet regenerate a missing production stage. A stale stage fails closed until its producer updates the artifact and migration/re-indexing records the new hash.

The remaining integration boundary is a configured Narrative/Visual Director
provider. Production no longer depends on president-specific source code, but
the engine intentionally fails closed at the two JSON approval gates rather
than selecting a paid model or spending credentials without configuration.

## Default limits

| Control | Default |
|---|---:|
| Evidence characters | 6,000 |
| Director input | 2,500 estimated tokens |
| Director output | 1,200 estimated tokens |
| Media candidates | 80 |
| Retries | 1 |
| Full renders | 1 |
| Narration | 140–175 words |
| Duration | 60–75 seconds |
| Total model tokens | 15,000 |

The budget validator fails closed and identifies every exceeded field. Existing Aguinaldo media is grandfathered as a regression fixture; these limits apply to subsequent segment production.

## Context and log controls

- Director sidecars preserve originals and include source/sidecar hashes, paragraph-ID verification, and conservative character/4 token estimates.
- The Aguinaldo sidecar reduces estimated context from 31,769 to 3,751 tokens (88.2%).
- `runQuiet()` captures complete stdout/stderr in `.pipeline/logs/` and returns only exit status, duration, log size, and a handle.
- Tests capture 2,509 simulated Remotion progress lines locally while keeping the returned receipt below 900 characters.
- Prompt templates should keep stable instructions and schemas before episode-specific evidence to support provider prefix caching.

## Invalidation

Changing `storyboard` marks only these stages stale:

```text
storyboard, preview, render, audit
```

Evidence changes invalidate the full downstream graph. Render is refused unless preview is `PASS`. Replay is refused whenever any stage is stale.

## Proof artifacts

- `.pipeline/reports/replay-report.json`: eight stages skipped, zero network/model/render calls.
- `.pipeline/reports/sidecar-report.json`: verified paragraph coverage and measured context reduction.
- `.pipeline/reports/token-projection.json`: 15,000-token projected episode allocation versus the prior 160,623-token goal.
- `.pipeline/logs/`: full quiet-execution logs retained outside console/model context.

## Verification

```bash
npm run typecheck
npm test
```

Tests cover deterministic hashing, migration, bounded receipts, handle/path retrieval, network-disabled replay, sidecar verification, budget refusal, dependency-aware invalidation, preview/render ordering, quiet log capture, and the 15,000-token projection.
