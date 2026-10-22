Codex task: Build LiveLock MVP end to end
You are the lead engineer implementing a shippable-to-test Chrome Manifest V3 extension called LiveLock, a privacy-first, adult-only selective NSFW site blocker. Follow the attached LIVELOCK_ARCHITECTURE.md as the source of truth. Work autonomously in the current repository. Do not stop after scaffolding or provide only design; create runnable source, scripts, tests, documentation and a built unpacked extension. Report completed features, tests actually run, and blockers precisely.
Absolute product requirements
Adult users enter or paste one Chaturbate username/room URL. No hardcoded personal broadcaster username.
Chaturbate and a manageable domain blocklist are blocked by default whenever protection is ON. Protection OFF is an explicit user choice in Settings, shows a warning, and must genuinely disable baseline and dynamic deny rules; turning ON restores them.
Verified LIVE status conditionally enables ONLY the chosen broadcaster's canonical top-level room URL, not all of Chaturbate. Keep other listed adult domains blocked.
Remove all room allowances when OFFLINE, UNKNOWN, stale, API failure, config changes, user clicks Lock Now, or selected username is removed.
A Chrome extension is not tamper-proof or OS-wide. Never claim instantaneous relock or guaranteed blocking across browsers/incognito.
No authentication or browsing-history tracking, stream previews, thumbnails, explicit content, adult recommendations, payments, stream fetching/recording, remote scripts, or credentials in the client.
Make Chrome extension installable via chrome://extensions > Load unpacked.
Critical API feasibility gate — FIRST TASK
Chaturbate lists an official Affiliate Users Online API but the detailed v2 documentation requires login. The separate stats API requires each broadcaster's self-issued token, so it does not enable unrestricted status checks. Broadcasters may opt out of affiliate syndication, making absence from feeds inconclusive.
Before coding a production status client, inspect official publicly available documentation and existing repository configuration. Produce docs/provider-feasibility.md that clearly distinguishes what is VERIFIED from assumptions. Do not invent query params, data schema, credentials, availability guarantees or feed coverage. Do not use unauthorized scraping, CAPTCHA evasion, login circumvention, or stream-video endpoints as a shortcut. If affiliate credentials/docs are missing, continue with a complete functional fixture-provider build and mark real-status integration as unconfigured/locked. Do not say live integration works. Make integration swap-in possible without rewrite.
The Chrome Web Store may reject extensions that direct traffic to adult sites. Prioritize a developer-mode unpacked distribution with clear policy caveat; do not promise store availability.
Implementation stack
TypeScript strict, Chrome MV3, minimal Vite build, React UI if feasible.
chrome.declarativeNetRequest packaged baseline blocking + dynamic custom domains + session-scoped narrow exact-room allow rule with explicit priority.
chrome.alarms (~1 min), MV3 service worker event handlers, chrome.storage.local, chrome.webNavigation and/or tab change events, Chaturbate document_start guard for SPA navigations.
Fixture status provider for test/dev ONLY; strongly typed LiveStatusProvider interface; stub/gateway client for future official approved provider.
Unit tests Vitest; MV3 integration/browser smoke tests Playwright as feasible; ESLint, typecheck, build, README.
Required implementation behavior
Install: static default deny rules active independently of background script health; start in locked mode. An explicit protection-OFF setting must call updateEnabledRulesets and remove custom dynamic rules as appropriate; re-enable before other status logic. Surface OFF clearly; don't pretend blocking continues.
First use: show onboarding, honest Chrome-only limitations, username field, save, enabled state, verification connection status. Disabling in Settings requires confirmation and is a user opt-out, not a hidden fail-open.
Input: parse only canonical Chaturbate host chaturbate.com or www.chaturbate.com, normalize lowercase, validate safe ASCII username, prevent domain/lookalike/path/query injection. Handle also plain handle.
Poll: observe fresh time-bounded typed status. Exact platform+username match. Unknown/absent/error/stale results fail closed. Race-proof changing settings mid-request.
Rules: block at priority ~100, narrow session allow at ~200 for only main_frame request to exact chosen canonical username when verified. Do NOT globally allow the platform, do NOT use allowAllRequests as an expedient. Test compatibility with actual Chrome request matching.
Relock: revoke allowance, then redirect/guard open rooms; stop stale requests from unlocking after a user lock. Detect SPA and direct route navigations. Graceful browser-native blocked page if pretty redirect requires too many extra permissions.
State: unconfigured/checking/locked_offline/locked_unknown/unlocked_live. UI shows last check, current status, manual Check now, Lock now, Open approved room ONLY when allowed, and settings.
Storage: only selected username, preferences, last status/expiry, temporary grant metadata; no user account, passwords, streams, or browsing history. A backend username query, if later configured, must be disclosed in privacy copy.
Restart/sleep: reconcile stale grants, remove expired rules, rebuild alarms. Don't claim exact-time expiration; session DNR does not support native expiry. Guard document_start checks stale grants and prohibits unauthorized view as fast as browser allows.
Permissions: minimal; document why each Chrome permission is required. Icons locally packaged, restrictive CSP, no externally loaded JavaScript.
Production cannot enable mock LIVE status with a user-facing switch. In development mode, label simulated status clearly and allow scripted fixture tests.
Working plan: implement in order, don't stop at planning
A. Inspect repository; define package scripts and document provider gate. B. Scaffold manifest/entry points and implement static DNR blocking. Verify extension loads. C. Implement domain/username validators, grant state machine, DNR rule builder, local storage and event handlers. D. Build polished, accessible popup/options/onboarding screens; show no explicit photos. E. Implement fixture provider and deterministic test controls gated behind import.meta.env.DEV/separate dev build. F. Implement remote gateway provider contract/stub with approved-source validation and no fake success responses. G. Implement DOM/content routing guard, tab relock behavior, popup refresh, alarms, and restart reconciliation. H. Write tests for policy, URL matching, invalid response, errors, race, suspension, and simulated live/offline transitions. Run pnpm lint, pnpm typecheck, pnpm test, pnpm build, and report results (or corresponding chosen package manager commands). I. Deliver dist/ unpacked extension, documented manual install flow and limitations, and a concise remaining-work list for real authorized Chaturbate source integration.
Acceptance / manual test matrix
Default platform/other-listed sites blocked; no configured username needed to enable protection. Explicit protection-OFF disables deny rules; turning it back ON restores them.
Mock LIVE for sample_handle permits https://chaturbate.com/sample_handle/ and https://www.chaturbate.com/sample_handle/, but never /other_handle/, /, directory, or sample_handle2.
Invalid username or lookalike domain never matches.
OFFLINE, UNKNOWN, staleness, timeout, HTTP 429/500, invalid payload, or changed handle removes allowance.
Existing room tabs are closed/redirected/guarded on relock; SPA navigations to unapproved rooms do not leak access.
Browser/service-worker restart, tab focus, multiple tabs, incognito scope warning, and race conditions have tests or a manual verification item if automation is not feasible.
Production build never grants live from a fixture.
README does not claim verified Chaturbate API integration without working authorized credentials and validated examples.
Desired final response from Codex
File tree and the exact files/features implemented.
Exact commands to install dependencies, run dev/tests/build, and load dist/ in Chrome.
Test outputs and which manual tests were verified vs merely documented.
Provider status: official integration actually working, or needs authorized affiliate access (with no fake claims).
Known enforcement limitations and remaining blockers for public distribution.
Proceed now. Prefer a complete, working, honest MVP with a fixture over an incomplete or falsely advertised real-time provider.
