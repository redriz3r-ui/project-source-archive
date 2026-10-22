# LiveLock 0.4.5 — connected to the real Chaturbate API

`dist/` now uses Chaturbate's documented official affiliate online-room API. It unlocks only the exact selected room when that API lists the room as **public**. If the room is absent, private/away, unverified or the API fails, it stays blocked. Missing from the feed does not prove offline.

## Use it

1. In desktop Chrome, open `chrome://extensions` and enable **Developer mode**.
2. Click **Load unpacked** and select **dist/** (the folder with manifest.json). If you already loaded that folder, click its **Reload** button. Disable/remove the older simulator or other LiveLock variant so it cannot override the allowance.
3. Pin LiveLock, open **Settings & setup**, enter your broadcaster's username or room URL and **Save and lock**.
4. Open the toolbar popup and click **Check again**. **LIVE** enables **Open approved room**. UNKNOWN means the API has not confirmed a public room, so it stays locked.
5. **Lock now** immediately revokes access and pauses automatic unlocking until Check again. Protection OFF requires an explicit acknowledgment in Settings and actually disables LiveLock's rules.

For adults 18+ only. Named-domain blocking works by default even without a selected handle. Incognito requires separate Chrome permission; other browsers/devices and disabled/uninstalled extensions are outside scope. Polling and relocking can lag, especially after sleep. An allowed page may still contain recommendations/chat/thumbnails; LiveLock limits navigation rather than sanitizing the page. It never bypasses login or age checks.

## Three-line personalized status in v0.4.5

The restricted page is just a small LiveLock mark and three short lines: the selected broadcaster’s status, “All NSFW is locked,” and “Please check again.” No settings/review link, footer, deal language or coaching. Examples: “@handle is offline.” or, when the API has not confirmed a public room, “@handle isn’t confirmed live.” Live, checking, manually locked and protection-OFF states have their own concise messages. Name recovery during an unavailable/older worker and iframe privacy are preserved. No username is hardcoded.

## ThePornDude directory blocking in v0.4.0

The extension now adds **3,035 verified domains from 9,036 listings across all 156 collected English category pages** of ThePornDude. It blocks the directory itself, referral links and listed website domains/subdomains. This stricter policy blocks mixed-use listed domains in full, including Reddit, YouTube, Instagram and 4chan (all boards). The chosen verified-live Chaturbate room remains the narrow exception. Reload LiveLock in Chrome to activate version 0.4.0.

This is the collected directory snapshot, not automatic synchronization of future additions or a claim to every hidden/search-only/historical entry. See [directory collection and scope](docs/directory-blocklist.md).

## Existing category coverage from v0.3.0

The previous five-domain default has been replaced by a bundled **764,348-domain adult-site snapshot**, including erome.com and subdomains, plus an exact 4chan `/gif` board rule. Version 0.3.0 spared other 4chan boards; v0.4.0 now blocks the whole listed 4chan domain under the stricter directory instruction. The data is bundled locally, with no new permissions or runtime list requests. Reload the extension in Chrome to activate it. New sites and explicit pages on mixed-content services can still be missed; this is not a guarantee of all NSFW content. See [blocklist provenance and scope](docs/blocklist.md).

## Real API connection

The authenticated official API documentation was inspected after user sign-in. It permits direct browser requests with a **public affiliate campaign identifier**; no password, API secret, login cookie or backend is needed. The local connected build has that public campaign configured. Chaturbate's required `client_ip=request_ip` preserves regional filtering. Only exact identity plus `current_show=public` can grant access. The selected handle is matched locally against paginated metadata and is not sent as a search query. No thumbnails, stream/video URLs or embed URLs are requested or opened by the status provider.

The real selected-handle check completed against all 18 pages and returned UNKNOWN/not-listed. That means the connection works but that check did not confirm the selected broadcaster live. See [provider evidence and limitations](docs/provider-feasibility.md) and [delivery report](docs/production-report.md).

## Build and verify

Node 22.13+ or Node 24 LTS:

```sh
npm ci
npx playwright install chromium
npm run lint
npm run typecheck
npm test
npm run build
npm run build:dev
npm run build:unconfigured
npm run test:e2e
npm run package
```

The **local** `config/affiliate.local.json` (ignored by Git) contains `{ "campaign": "your_public_affiliate_campaign_slug" }`. Obtain your own slug from the official documentation in your account. The delivered `dist/` and connected ZIP already contain the configured public campaign. Clones without that local file build an unconfigured, locked production variant. This is intentional: no unrelated account is silently configured for a new developer.

- `dist/`: real connected build when local campaign configured; otherwise locked/unconfigured.
- `dist-dev/`: separate DEVELOPMENT SIMULATOR, no real provider requests; LIVE clearly simulated. Install one build at a time.
- `dist-unconfigured/`: explicit locked build for regression tests.
- `artifacts/livelock-0.4.5-connected.zip`: current connected extension with SHA-256 sidecar; extract and Load unpacked its `dist/` folder.
- `npm run dev`: rebuild simulator; reload it in Chrome after changes.
- `npm run check`: normal complete automated verification. Real-network checks are opt-in.
- `npm run check:live -- <your-handle>`: real metadata-only check using the local public campaign; writes ignored local evidence.
- `LIVELOCK_REAL_API=1 npm run test:e2e`: also runs the real-network browser positive control, selecting a public feed entry internally without opening its room. It fetches no streams.

## Source tree

```text
src/core/blocklist.ts               Shared bundled-domain and board-path lookup
src/rules/                         Adult-category + directory domains, board rules and provenance
src/core/policy.ts                  Parsers, policy, freshness, exact allow/deny rules
src/background/controller.ts       Serialized grants/rules, revisions, locking, tab cleanup
src/background/index.ts            MV3 listeners, polling, trusted UI control messages
src/providers/affiliate-provider.ts Official v2 pagination, exact public match, cache/backoff
src/providers/interface.ts         Shared contract and unconfigured fallback
src/providers/fixture-provider.dev.ts  Simulator only; excluded from production bundle
src/providers/gateway-provider.ts  Optional future gateway; currently unused
src/content/room-guard.ts           Document-start, focus, expiry and SPA guard
src/ui/main.ts, style.css           Popup/settings UI and real provider diagnostics
src/blocked/main.ts                Personalized top-level restricted-page status
popup.html, options.html, blocked.html  Local UI, onboarding and restricted page
scripts/build.mjs, package.mjs, check-live.mjs  Build/package/real metadata verification
config/affiliate.local.json         Ignored local PUBLIC campaign slug; never passwords
public/icons/                      Local packaged PNG icons
tests/                             Unit/controller/provider + Chromium MV3 tests
docs/                              Provider evidence, permissions, threat model, test matrix
dist/, dist-dev/, dist-unconfigured/  Built unpacked variants
artifacts/                         Packages, hashes, reports and screenshots
```

## Privacy and enforcement

Preferences and selected status stay local (`chrome.storage.local`); transient request budget/page hint/cache use `chrome.storage.session`. No sync, accounts, tracking, analytics or history log. Direct official API requests reveal the requesting IP and public campaign to Chaturbate. No login cookies or passwords are used. The full feed is processed temporarily and discarded; only selected-room minimal metadata is retained. No intermediary gateway receives the selection.

Baseline blocks the union of the 764,348-entry adult-category list and 3,035 directory-overlay domains (with overlaps deduplicated), their subdomains, the existing board rule, plus up to 100 custom domains/subdomains. Directory-overlay domains override earlier mixed-content exclusions. Priority-200 session allowance matches only canonical/www HTTPS `/handle/` main-frame URL; other rooms/directories and embedded frames remain denied. Provider polling approximately once per minute, bounded scans, HTTP-response freshness checks and a maximum 90-second logical lease. DNR rules do not expire themselves; delayed alarms/sleep can delay removal. SPA checks nominally run every 250 ms plus browser scheduling. The extension is not tamper-proof, system-wide or an exhaustive adult-site classifier.

Public distribution still needs confirmation of polling/license/rate terms, broader manual browser/site testing and review of [Chrome's adult-site extension policy](https://developer.chrome.com/docs/webstore/troubleshooting). A functioning local API connection is not proof of Web Store eligibility or an approval for broad redistribution. See [production work remaining](docs/production-report.md).
