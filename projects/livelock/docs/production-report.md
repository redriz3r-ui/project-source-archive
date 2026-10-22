# LiveLock 0.4.5 — requested three-line format

Changed only restricted-page copy/layout: selected-name status, “All NSFW is locked,” and “Please check again,” on separate lines. Confirmed OFFLINE, unconfirmed LIVE, unavailable/checking/locked and protection-OFF remain distinct. This does not claim all internet sites are blocked or falsely infer OFFLINE from feed absence. No access/provider/list changes. Current package: livelock-0.4.5-connected.zip and dist/.

Lint, strict types and three builds passed; targeted page/privacy/fallback browser checks are recorded in test-matrix.md. No new copy-mirroring unit tests or unrelated-suite reruns.

---

## Historical v0.4.3 copy

# LiveLock 0.4.3 — simple app-style status

The restricted page now contains only a small mark/brand, selected-name status and one short friendly sentence. Removed the settings/review link, footer, deal/rules language and teasing coaching. Offline is only shown for confirmed OFFLINE; UNKNOWN/unavailable use waiting/status-unavailable copy. Live/checking/manual lock/OFF remain truthful. Existing local-name fallback and iframe privacy are unchanged. No access-policy/provider/blocklist changes.

Current dist/ and ZIPs use v0.4.3. Lint, strict types and all three builds passed. Targeted Chromium page/privacy/fallback checks are recorded in test-matrix.md. Prior policy/provider/full-suite evidence below remains historical rather than being rerun for a copy/layout-only edit.

---

## Historical v0.4.2 delivery

# LiveLock 0.4.2 — playful copy and resilient selection reminder

The user’s screenshot showed the generic status-error fallback, not the intended selected-name page. This release preserves the locally saved selection at top level when the background status message fails (including a simulated legacy/unavailable worker), while explicitly showing status as unavailable and never inferring LIVE from saved preferences/grants. The exact cause in the user’s running browser was not observed; an old/unavailable worker is covered by the new browser regression test.

New copy: “Nice try. You picked @handle.” The one-room agreement, “quick look” detour, live green light, offline “no side quests” and manual-lock “velvet rope” messages replace the clinical copy. No access or provider rules change. No username is hardcoded. Embedded pages remain generic and do not read preferences or request status. Selection rendering is text-only.

Current source and dist/ packaged as `artifacts/livelock-0.4.2-connected.zip`; separate simulator/regression builds remain. Tests include normal selection edits/lock/OFF/privacy and the previously broken status-request fallback. See test-matrix.md for final validation.

---

## Historical v0.4.1 personalization

# LiveLock 0.4.1 — personalized restricted page

The local restricted page now names the current selected broadcaster (“Only @handle. Only when live.”), explains the single-room boundary and displays the actual live/unconfirmed/checking/manual lock/unconfigured/protection-OFF state. Selection changes update the open page. No personal handle is hardcoded or added to its URL; copy no longer lists technical possibilities such as lease expiry or Chrome error codes.

Privacy: the web-accessible page is personalized only at top level. A dedicated read-only message validates own extension ID, exact page URL and top-level frame; embedded pages stay generic and cannot get the selected handle from it. The page does not receive config or gain popup/options control actions. Browser coverage verifies selection updates, lock/OFF states and embedding isolation. Source: `src/blocked/main.ts`, `blocked.html`, background message branch.

Current package: `artifacts/livelock-0.4.1-connected.zip` and updated `dist/`; simulator and unconfigured regression builds included. Status-provider logic and domain coverage remain unchanged from v0.4.0. Reload the extension and refresh any open restricted page to see the change. Validation results are in test-matrix.md.

---

## Historical v0.4.0 directory overlay

# LiveLock 0.4.0 — requested directory blocking

Adds 3,035 website/redirector domains verified from 9,036 distinct public directory listings across 156 category pages, with zero unresolved records in that collected snapshot. Extraction uses visible category-link data, domain mentions, bounded HEAD-only referral checks and nine final review-page displayed domain links. No review text/media is shipped. See [directory-blocklist.md](directory-blocklist.md) for provenance and collection limits.

The directory overlay unions with the larger community category list, preserving existing coverage, local preferences and the exact verified-live room exception. Listed mixed-use sites now block in full, including 4chan, Reddit, YouTube and Instagram. This deliberately supersedes prior mixed-content exclusions for domains explicitly in the overlay. No new runtime host permissions or runtime list-fetching is introduced. Future directory additions need a new snapshot/build.

Current deliverable: `dist/`, `artifacts/livelock-0.4.0-connected.zip`, simulator/regression builds and source/tests. **Validation: 119 unit tests and 5 Chromium tests passed; 1 optional live-network test skipped.** Lint, strict types, builds, archive integrity and zero known dependency vulnerabilities verified. Combined list: 764,877 unique entries in 7,650 native rules. Details in test-matrix.md. API provider logic is unchanged. Publication, browser sleep/incognito/accessibility/real-page-rendering limits and directory fact-list distribution review remain as documented below. The collected category snapshot is not proof of every search-only, translated, historical or future entry advertised by the directory.

---

## Historical v0.3.0 blocklist delivery

# LiveLock 0.3.0 — expanded adult-site blocking

The user's reported erome.com and 4chan /gif gaps came from the original five-domain default. Version 0.3.0 replaces it with a local 764,348-domain category snapshot plus an anchored /gif board rule. It preserves the exact real Chaturbate public-room exception and preferences. Other 4chan boards and protected mixed-content services are not blanket-blocked.

Data source, filtering, license, provenance, limits and update instructions: [blocklist.md](blocklist.md). All denial is still packaged browser-native enforcement, default ON and disabled by the explicit OFF setting. No permissions were added. Expanded lookup also relocks existing matching tabs.

Current deliverables: `dist/` and `artifacts/livelock-0.3.0-connected.zip`, separate simulator, explicit unconfigured regression build, hashes and updated source/tests. Unit suite: **114 passed**. Chromium: **5 passed, 1 optional real-network test intentionally skipped**; see test-matrix.md. Real API integration remains in place; no provider logic changed in this release. Its actual real-network proof below is from v0.2.0. This version rechecks the exact-room rule against the much larger baseline in Chromium.

Not a guarantee of every adult site/page; list errors/new sites/mixed-content content remain possible. Static lists require a reviewed rebuild/reload to update. Larger list costs about 30 MB of unpacked data/lookup code, approximately 7.4 MB ZIP. Existing public-distribution, private-status semantics, browser sleep/incognito/accessibility and real-room rendering caveats still apply. The user separately confirmed a real broadcaster test worked with v0.2.0; that is user feedback, not a claim that automation rendered streams.

---

## Historical v0.2.0 delivery and real-API evidence

# LiveLock 0.2.0 delivery report — real API connected

2026-10-22. The local production build in `dist/` is now integrated with the official Chaturbate Users Online v2 API. This supersedes the v0.1.0 unconfigured-provider report.

## What is working and actually verified

- The user signed in to official API documentation; documented direct browser requests use a public campaign slug, not a secret credential. Existing host permission suffices. No server/gateway, cookies, login credentials or broadcaster token are used.
- The real official endpoint returned HTTP 200 JSON. An actual selected-handle probe scanned 18 pages and returned UNKNOWN/not-listed. This is not an OFFLINE claim: opt-outs, regional filtering and feed coverage prevent that inference.
- A real-network Chromium test fetched a real public room from the official feed, selected it in the production extension, and verified LIVE plus an exact session allowance and enabled Open button. No room was opened, no stream was fetched and no synthetic API response was used in that test. Redacted local evidence: `artifacts/live-browser-verification.json`.
- Production remains fixture-free. Real status is exact username + current_show public; private/group/away, missing/malformed/stale/error/limited responses stay locked. Cached selected observations never extend their original lease; failed refresh discards the previous LIVE. Session storage preserves scan budget/page hint/cache across worker lifetimes.
- Existing baseline/custom blocking, exact canonical/www room allowance, SPA/document guard, multi-tab expiry, OFF/ON, pending-request race protection and restart behavior remain implemented/tested.

## Delivered files

`dist/` is the connected unpacked production extension. `dist-dev/` is the separate simulator. `dist-unconfigured/` is the explicit locked regression build. Current packages: `artifacts/livelock-0.2.0-connected.zip` and `artifacts/livelock-0.2.0-simulator.zip`, with SHA-256 sidecars. Older v0.1.0 ZIPs are historical unconfigured builds; use v0.2.0.

New adapter: `src/providers/affiliate-provider.ts`. Build configuration: ignored `config/affiliate.local.json` holds only the public campaign slug. It is intentionally present in the connected bundle and API query, as the official API supports client-side use. A clone without that file builds locked/unconfigured. No broadcaster username is baked into source or build.

## Final validation actually executed

- Strict TypeScript and ESLint passed.
- Vitest: **89 tests passed** (policy, controller, gateway fallback, official affiliate pagination/public identity/HTTP freshness/malformed payloads/timeouts/429/backoff/cache/failure tests).
- Chromium/Playwright: **5 tests passed**, including the real-network official API positive-control test. Normal tests also cover connected adapter errors/private status, fixture exclusion, exact DNR matching, native denial, synthetic allowed room/SPA, two-room expiry, OFF persistence and fresh-grant revocation after actual isolated browser restarts.
- `npm run package`, `npm run build:unconfigured` passed; current ZIPs generated. Build-time assertion confirms no fixture provider in production.
- Dependency lockfile updated for v0.2.0; offline lockfile audit reported zero vulnerabilities. No dependency versions were added/changed from the previously audited set.
- Node 24.19.0, Vitest 4.1.12, Playwright 1.64.1, Chrome for Testing 156.0.8078.4 on macOS ARM64. Browser tests used an isolated profile, not the user's ordinary Chrome profile. CI is configured, not hosted/executed here.

Exact commands: `npm run lint`, `npm run typecheck`, `npm test`, `npm run package`, `npm run build:unconfigured`, `LIVELOCK_REAL_API=1 npm run test:e2e`, and `npm run check:live -- <selected-handle>`. See e2e-results.json and local live verification evidence in artifacts/.

## Remaining work and practical limits

1. Install/reload `dist/` in the user's actual Chrome profile and enter the selected handle. No personal selection is hardcoded. The isolated test proves API/Chrome grant integration; it does not install into the user's normal profile.
2. Real-room rendering, normal login/age gates, private-show transitions, actual sleep/delayed alarms, forced worker suspension, incognito, multiple windows/competing extensions and manual accessibility need dedicated user-profile checks. No live video was tested.
3. Confirm periodic polling, usage/license/caching/rate terms before broad public redistribution. Documentation recommends one request per visitor and publishes no numerical polling quota on the inspected page. Bounded local scans are not evidence of permission for a large-scale service. If a shared service is later needed, preserve each user's regional restrictions and minimize logs.
4. Validate long-term source freshness/roster behavior. HTTP Date establishes response freshness only; the API gives no independent event timestamp. Missing means UNKNOWN forever, not confirmed OFFLINE. Up to 40 pages / 25 seconds bounds scan work; failures/limits lock.
5. Review Chrome Web Store policy and release/privacy/security/provenance before publication. The adult-site integration can be ineligible for store distribution. No store submission, deployment or public release was made.

LiveLock is not tamper-proof/system-wide/comprehensive or instantaneous. DNR session allowances do not self-expire; logical lease removal depends on alarms/focus/navigation/UI/document guard. Allowed pages may contain recommendations/chat/thumbnails. No sanitization, age/login bypass, browsing-history logging, stream fetching or recording. Current direct requests disclose requesting IP/public campaign to Chaturbate but do not transmit the selected handle as a query or use an intermediary gateway.
