# v0.4.4 three-line copy verification

Uses the existing targeted Chromium page tests to verify selection changes, manual lock/OFF, unavailable-worker fallback without false LIVE, and generic embedded rendering with no controls or selected handle. Lint, strict typecheck and all three builds passed. **Both targeted tests passed.** Packaged contents, archive integrity and checksums verified. Latest results: artifacts/e2e-results.json. No new unit tests for this reversible wording edit.

---

## Historical v0.4.3 verification

# v0.4.3 concise status-page verification

Targeted Chromium cases: selected-name updates, manual lock/OFF, generic embedded rendering without links/controls, and selected-name recovery on a failed status message without a LIVE claim. Lint, typecheck and all three builds passed. No new unit tests were added for a reversible copy/layout change, and the unrelated policy/provider suite was not repeated. **Both targeted Chromium tests passed.** ZIP contents, archive integrity and checksums verified. Details: artifacts/e2e-results.json.

---

## Historical v0.4.2 full-suite validation

# v0.4.2 playful-page and fallback regression

Added an actual extension-page browser regression that forces the status message to fail, then verifies that the locally selected handle still appears, status is explicitly reconnecting, and no LIVE claim appears. Existing browser coverage still checks selection changes, manual lock/OFF and iframe privacy. **Final: 119 unit tests passed, 7 Chromium tests passed, 1 optional real-network test skipped.** Lint, strict types, three builds and package/checksum consistency passed. The generated blocked-personalized-fallback.png is the regression preview.

---

## Historical v0.4.1 page validation

# v0.4.1 personalized-page regression

Added real Chromium coverage for the configured handle in the heading/status, selection edits updating an open restricted page, manual Lock now copy, truthful protection-OFF copy, and absence of the selected handle/settings link in an externally embedded restricted page. No extra copy-mirroring unit tests were added; the meaningful new boundary is verified in the actual extension. **119 unit tests passed; 6 browser tests passed; 1 optional real-network test skipped.** Lint, strict types, all three builds and packaged-file/checksum consistency also passed. Details: artifacts/e2e-results.json.

---

## Historical v0.4.0 directory-overlay validation

# v0.4.0 directory-overlay regression

New coverage checks every extracted directory domain and its subdomains against the shared background lookup, plus the directory/referral host and whole mixed-use domains. Chromium checks native baseline denial for these roots and ensures a LIVE session allowance still matches only the selected Chaturbate room. Expected other-board behavior is intentionally changed: all 4chan is now blocked because it appears in the directory overlay. **119 unit tests passed; 5 Chromium tests passed; 1 optional real-network API test was intentionally skipped.** Lint, strict typechecking, three builds, ZIP/hash consistency and a zero-vulnerability dependency audit passed. Details: artifacts/e2e-results.json.

All 156 discovered English category pages were collected successfully; 9,036 deduplicated listings yielded 3,035 verified domains with zero final unresolved records. This is snapshot evidence, not an assertion about search-only/historical/future listings. No explicit media was downloaded by the header resolver and no review prose/media is bundled.

---

## Historical v0.3.0 validation

# v0.3.0 blocklist regression update

Vitest: **114 tests passed**. Added broad bundled category lookup, erome/subdomain/HTTP and 4chan /gif/path/encoded-boundary cases, safe mixed-board/lookalike cases, plus redirecting existing matching tabs. Browser suite now additionally tests actual Chrome denial of the two reported targets, rule variants, other-board preservation and OFF/ON. **Chromium: 5 passed, 1 intentionally skipped (optional real-network API test).** The existing exact-room allowance still passed against the expanded baseline. Details: `artifacts/e2e-results.json`. The live-network API test is intentionally optional and was previously passed in v0.2.0; no provider code changed for this blocklist fix.

---

## Historical v0.2.0 provider validation

# Test matrix — v0.2.0, 2026-10-22

**89 Vitest tests passed; 5 Chromium tests passed, including a real official-API positive control.** Node 24.19.0, Vitest 4.1.12, Playwright 1.64.1, Chrome for Testing 156.0.8078.4, macOS ARM64. Isolated browser execution required sandbox escalation and did not alter the normal Chrome profile.

| Requirement | Executed evidence | Remaining scope |
| --- | --- | --- |
| Default blocking, no handle | Controller + native ERR_BLOCKED_BY_CLIENT in Chromium | Normal user-profile installation |
| Protection OFF/ON | Actual rules/UI checks; OFF persistence across Chromium restart | Extension update manual |
| Handle/domain parsing | Malicious/lookalike/path/query/Unicode/domain rejection | Full platform naming grammar; accepted 3–30 ASCII subset |
| Exact room allowance | Actual Chrome testMatchOutcome chooses session only for canonical/www exact room; wrong room/directory/subdomain/embedded frame stays baseline/dynamic | Real page rendering and age/login gates |
| Real official API connectivity | Actual HTTP 200 paginated feed, selected-handle absence UNKNOWN; actual extension fetch public control creates exact LIVE allowance | Continuous source reliability and polling terms |
| Official metadata validation | Pagination, identity/public-only, private/group/away lock, HTTP 401/403/429/500, malformed content, stale/future Date/Age, timeout tests | Feed has no source-event timestamp |
| Cache/budgets/backoff | Persisted session budget across reconstructed providers, exact-selected original lease cache, no stale LIVE fallback, Retry-After, page cap | Broad user scale/rate contract |
| Relock on errors/non-public | Connected production Chromium test removes grant for HTTP failure and private room; seeded fixture LIVE ignored | Actual offline/private transition timing |
| Pending-request/config/lock races | Deferred provider/Chrome-regex validation tests and repeated-click budget test | Long-running real-world provider faults |
| SPA and multiple rooms | Actual history.pushState redirects; clock expiry redirects two loaded synthetic rooms | Platform-specific DOM transitions can show brief content |
| Restart/expiry | Real isolated Chromium close/relaunch preserves OFF, discards fresh LIVE; controller reconstruction and clock-advanced expiry | Actual sleep/forced worker suspension/manual end-user browser |
| Simulator isolation | Separate labeled build; production code-exclusion assertion; production ignores fixtureState | Re-audit on future integrations |
| Privacy | No secrets/cookies/provider login; selected handle matched locally; no streams/images fetched; no roster persistence | Future gateway/distribution review |
| Accessibility/layout | Local labels/focus/status design and screenshots | Screen-reader/keyboard-only manual checks |

Normal browser tests use synthetic HTML/metadata as marked in source. `LIVELOCK_REAL_API=1` additionally enables one real-network browser check that fetches only metadata, chooses a public feed entry internally, verifies the real production grant path, and never opens the room/stream. The selected real user handle is passed to a separate CLI probe, never hardcoded. Its missing feed entry remains UNKNOWN, not asserted OFFLINE.

Artifacts: e2e-results.json, popup-connected.png, popup-production.png, settings-simulator.png, ZIPs/hash sidecars, previous dependency audit, ignored live-verification.json and live-browser-verification.json (the latter redacts the public control's identity).

Not executed: real explicit content/video rendering, actual broadcaster private/offline transitions, headed normal-profile manual installation checks, OS sleep, incognito or screen-reader sessions. CI is provided but not run on GitHub. With no local campaign file, CI builds unconfigured and skips connected-only/live-network cases; local connected suite here executed all 5.
