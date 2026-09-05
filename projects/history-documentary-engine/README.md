# History Documentary Engine

See [docs/presidential-pipeline.md](docs/presidential-pipeline.md) for the token-efficient presidential segment workflow, commands, budgets, replay proof, and current limitations.

A manifest-driven Remotion engine that turns researched production briefs into paced, narrated, captioned history videos with archive media, original visual fallbacks, maps, motion graphics, music, sound cues, provenance, and automated quality gates.

The design borrows two architectural ideas—not source code—from Remotion's prompt-to-video template and MapLibre example: keep generation separate from rendering through a timeline data contract, and make maps deterministic and frame-driven. The MVP uses an offline SVG map plate so the sample renders without API keys, live tiles, or provider terms.

## What works

- JSON manifest validated with Zod
- Sentence-level visual director targeting a meaningful change every 3–6 seconds
- Narrative and fast chapter-based `EXPLAINED` story modes
- Scene registry with `TITLE_CARD`, `CHAPTER_CARD`, `ARCHIVE_PHOTO`, `KEN_BURNS`, `MAP`, `DOCUMENT_EXCERPT`, `QUOTE_CARD`, `STATISTIC`, `DATE_CARD`, `LABELED_CUTOUT`, `DIAGRAM`, and `ILLUSTRATION`
- Deterministic 1280×720 composition whose metadata follows the selected manifest
- Rights-aware Library of Congress acquisition with local asset promotion and provenance
- Local narration, audio-driven scene timing, and automated phrase captions
- Resumable production CLI with validation and verified MP4 rendering
- Provider contracts for archives, narration, illustrations, music, and sound effects
- Credential-free procedural illustration, ambient-score, and sound-effect adapters with original-asset licensing metadata
- Reusable motion and transition direction attached to every shot
- Quality gates for cadence, asset repetition, visual variety, citations, claim lineage, rights, credits, audio ducking, captions, timeline continuity, and verified media
- Explicit isolation area for DepthFlow or other license-sensitive add-ons

## Setup

Requires Node.js 20 or newer.

```bash
npm install
npm run dev
```

Remotion Studio opens with the `HistoryDocumentary` composition.

Render the included 17.5-second demo:

```bash
npm run render
```

The video is written to `out/demo.mp4`. Render a quick inspection frame with `npm run render:still`.

## CLI

### One-command documentary creation

Create a documentary from only a title and topic:

```bash
npm run documentary -- create \
  --title "Apollo 11" \
  --topic "The first crewed Moon landing in 1969" \
  --render
```

This performs authoritative-source discovery, evidence extraction, conflict screening, claim-cited brief generation, scene planning, multi-provider archive acquisition, local narration, captions, validation, rendering, and media verification. Use `--refresh` to regenerate research and planning while preserving timestamped copies of previous manifests and reports. Without `--refresh`, completed artifacts are resumed.

For a new arbitrary topic with local Qwen script direction, add `--local`:

```bash
npm run documentary -- create \
  --title "The Ozone Disco Fire" \
  --topic "The 1996 Ozone Disco nightclub fire in Quezon City" \
  --local
```

The local workflow uses Ollama's `qwen3:4b` model by default. It supplies only
supported research claims and authoritative source IDs, validates the returned
claim/source relationships and word limits, unloads the model after inference,
and retries validation corrections up to two times before failing closed. It
stops at `READY_TO_RENDER`. Inspect the generated manifest before rendering:

For an 8 GB Mac, `--agentic` enables the bounded Qwen workflow. Qwen first calls
the structured `SUBMIT_SCRIPT` tool as director, then starts a fresh 4096-token
context and calls `REVIEW_SCRIPT` as an independent critic. The critic may
approve or replace the script. Calls run sequentially, output is capped, the
model is unloaded between calls, and every decision is recorded in
`qwen-agent-log.json`:

```bash
npm run documentary -- create \
  --title "The Ozone Disco Fire" \
  --topic "The 1996 Ozone Disco nightclub fire in Quezon City" \
  --research automation/generated/the-ozone-disco-fire/research-report.curated.json \
  --local --agentic --refresh
```

```bash
npm run documentary -- render-project public/projects/the-ozone-disco-fire/manifest.json
```

`--model <ollama-model>` overrides the default. If `--render` is also supplied
with `--local`, the safety stop still wins and the full render is not started.

The planner expands each sourced script passage into sentence-level shots. Set `"storyMode": "NARRATIVE"` for a continuous documentary or `"storyMode": "EXPLAINED"` and add a `chapter` to each script passage for numbered chapter cards.

The default research workflow uses Wikipedia only to discover citations; Wikipedia is recorded as `DISCOVERY_ONLY` and cannot satisfy the evidence gate. A passing project requires at least two successfully acquired primary or authoritative-secondary sources and at least six supported, non-conflicting claims.

Generate a starter manifest:

```bash
npm run documentary -- generate \
  --title "The Railway That Remade the Valley" \
  --topic "Industrial transport in the early twentieth century"
```

This creates `public/projects/the-railway-that-remade-the-valley/manifest.json`. Validate or inspect any manifest:

```bash
npm run documentary -- validate public/projects/sample/manifest.json
npm run documentary -- load public/projects/sample/manifest.json
```

The Studio defaults to the Greenwood sample. Automated renders pass the selected manifest as input, so no source-code edit is required to render another project.

### Rights-aware archive automation

Search the public LOC photo API:

```bash
npm run documentary -- archive-search "Tulsa Race Massacre relief 1921" --limit 5
```

Collect ranked candidates for every image scene that has an `archiveQuery`:

```bash
npm run documentary -- archive-collect public/projects/greenwood-1921/manifest.json --download
```

The command writes an auditable `archive-candidates.json` report beside the manifest. The default resolver searches Library of Congress, Wikimedia Commons, Internet Archive, and NASA Images behind a common adapter contract. It promotes only public-domain/no-known-restrictions or explicitly supported Creative Commons candidates, records provider failures, rejects oversized files, prevents duplicate reuse, and leaves unclear-rights items for review.

Promote the best unique rights-cleared candidate into each eligible scene:

```bash
npm run documentary -- archive-promote public/projects/greenwood-1921/manifest.json
```

Promotion creates a timestamped manifest backup, downloads production assets under `archive-assets/`, adds item-level provenance to the source ledger, prevents the same LOC item from being reused, and writes `archive-promotions.json`. Scenes without a unique rights-cleared candidate remain unchanged.

### Automated narration and exact timing

Generate local narration without API keys and retime every scene from the actual audio duration:

```bash
npm run documentary -- narrate public/projects/greenwood-1921/manifest.json --voice Samantha --rate 175
```

The local adapter uses macOS speech generation, converts each clip to render-safe WAV audio, measures it, adds it to the scene, rebuilds the continuous timeline, creates a manifest backup, and writes `narration-report.json`.

For a new production brief, planning and narration can run as one automated step:

```bash
npm run documentary -- produce automation/example-brief.json --voice Samantha --rate 175
```

This local voice is an automation baseline rather than the intended final editorial voice. A future ElevenLabs or OpenAI adapter can implement the same narration contract without changing the renderer or manifest workflow.

### Resumable production orchestrator

Run planning, archive acquisition, narration, captions, and validation while resuming completed work:

```bash
npm run documentary -- run automation/tulsa-1921-brief.json --voice Samantha --rate 175
```

Add `--render` to finish with a verified MP4:

```bash
npm run documentary -- run automation/tulsa-1921-brief.json --render
```

The orchestrator creates `production-state.json`, detects existing archive and narration reports, skips finished work, and records each completed stage. Rendering writes `renders/<project-id>.mp4` and `render-report.json`; verification requires a valid video stream, matching dimensions, a positive duration, and an audio stream when narration exists. Use `--no-archives` for an offline run or `--force-narration` to regenerate the voice track.

Render an already prepared manifest directly:

```bash
npm run documentary -- render-project public/projects/greenwood-1921/manifest.json
```

After narration, the orchestrator automatically creates phrase-level captions, distributes their timing across each measured audio clip, records them in the manifest, and writes `caption-report.json`. Regenerate captions directly with:

```bash
npm run documentary -- caption public/projects/greenwood-1921/manifest.json
```

The caption report records whether a permissively licensed local `whisper-cli` installation was detected. Phrase-level timing remains the credential-free fallback when a compatible aligner and model are unavailable.

Inspect a project without changing it:

```bash
npm run documentary -- status public/projects/greenwood-1921/manifest.json
```

### Token-efficient intelligence proof

Run the bounded-context research and narration proof:

```bash
npm run intelligence-proof
```

The proof stores sources, evidence, claims, decisions, a size-bounded context brief, an exact retrieval receipt, dependency state, cache state, path-restricted narration patches, and replayable run receipts under `public/projects/episode-2/intelligence-proof/`. An identical rerun prints `SKIPPED` and performs no model work. This layer is upstream of PHONE_FAST and does not modify the existing episode manifests or renderer.

### Automated scene planning

The first automation stage converts a sourced production brief into a timed manifest:

```bash
npm run documentary -- plan automation/example-brief.json
```

Each script passage must cite at least one source and may cite evidence-ledger claim IDs. The visual director splits passages into readable narration shots, assigns purpose/motion/transition metadata, and selects a visual form from semantic cues. Archive searches run first; unresolved archive shots are explicitly converted to original procedural illustrations instead of masquerading as historical evidence.

Generate credential-free original visual and audio fallbacks for a prepared manifest:

```bash
npm run documentary -- creative-assets public/projects/apollo-11/manifest.json
```

The command records its provider, rights, credits, soundtrack ducking levels, and timed emphasis cues in the manifest and `creative-assets-report.json`. Replace the procedural adapters with a credentialed implementation of the same interfaces when richer artwork or music is required.

## Manifest contract

Every scene has an `id`, `type`, `startFrame`, `durationFrames`, optional narration/caption, source IDs, evidence-ledger claim IDs, review status, shot direction, and type-specific `payload`. Direction preserves the parent passage, shot index, editorial purpose, motion preset, and transition. Assets under `public/` use public-relative paths.

`MAP` supports both the credential-free offline SVG renderer and a real MapLibre renderer driven by local GeoJSON, deterministic frame-based camera coordinates, routes, region layers, points, and explicit attribution. The MapLibre proof project contains no remote tiles and renders with Remotion's ANGLE WebGL backend.

Scene components are registered in `src/scenes/registry.tsx`; adding a scene means extending the discriminated schema and registering one renderer. Provider integrations belong behind adapters in `cli/adapters.ts`, keeping API credentials, licensing rules, and source attribution out of scene components.

## Source and licensing notes

Procedural SVGs are clearly credited as original visual reconstructions and are never labeled as archive evidence. Real archive media retains item URL, institution, rights status, title, and access date. The production validator refuses uncleared archive media and missing credits.

Remotion uses its own license and may require a company license in some situations; review its current terms for your use. No code was copied from the reference repositories. DepthFlow and any AGPL/non-commercial dependency remain absent and optional; see `optional/README.md`.

## Next milestones

1. Add a configured local forced-alignment model for word-level timestamps.
2. Add optional credentialed illustration, music, and narration adapters behind the existing interfaces.
3. Add optional cached historical basemap tiles and style packages for MapLibre.
4. Add perceptual similarity scoring for images in addition to exact asset-reuse checks.
5. Add a human editorial approval gate before publication.
