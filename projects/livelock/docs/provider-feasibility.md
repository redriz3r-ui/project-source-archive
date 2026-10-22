# Official provider integration — 2026-10-22, v0.2.0

## Verified change since v0.1

The user signed in to the official affiliate documentation and authorized connecting the real API. The authenticated Users Online v2 page explicitly supports client-side JavaScript and server-side requests. It supplies a public campaign slug (`wm`), not a secret API key. We do not copy login cookies, passwords, account balances, tokens or account identifiers into the extension.

Official documentation: https://chaturbate.com/affiliates/promotools/api_usersonline/

Verified documented endpoint: `https://chaturbate.com/api/public/affiliates/onlinerooms/`.
Documented request parameters used: `wm=<public campaign slug>`, `client_ip=request_ip` for direct client requests, `format=json`, `limit=500` (supported 1–500), `offset=<nonnegative integer>`.
Documented response: `{count, results}`; room `username` and `current_show`, where show is `public`, `private`, `group` or `away`. No exact-username query parameter is documented. Do not invent one. Usernames are matched locally. The documented field maximum is 111 characters; our accepted handle syntax remains a conservative 3–30 character subset until full naming rules are verified.

The v1 documentation was also inspected. It has legacy recorded/region fields and recommends v2; the implementation uses v2 and its required regional IP filtering.

## Implemented integration

`AffiliateProvider` requests the official API directly from the extension with existing Chaturbate host permission. Credentials omitted, redirects rejected, no referrer, no-store, 25-second overall timeout, 500 rooms/page, at most 40 pages and 150 ms between pages. Exact matches marked `public` produce authorized-affiliate LIVE. Private/group/away, malformed responses, errors, missing identity, stale transport dates, timeouts, limits or unlisted handles produce UNKNOWN and keep/revoke blocking. No affiliate links, embedding, images or streams are opened or fetched by this provider.

The public campaign slug lives in ignored `config/affiliate.local.json` for the local connected build, and is intentionally present in that build's API requests as the documented public identifier. It is not an API credential. The selected handle is NOT put in a network query. No server/gateway or server credentials are required for this direct documented route. Region filtering uses the extension user's actual requesting IP, avoiding a server-IP mismatch.

Request budgets persist in `chrome.storage.session` across service-worker lifetimes: at least 60 seconds between scans, still-valid same-identity cache without lease extension, Retry-After handling on 429, and no previous LIVE reuse after a failed attempted refresh. Only a page-offset hint and the selected minimal observation are retained; full rosters/room metadata are discarded. The API provides no stream observation timestamp; `observedAt` uses the HTTP Date header, checked against local time and Age, with a maximum 90-second lease. This establishes response freshness, not guaranteed source-event freshness.

## Actual evidence

A read-only metadata probe returned HTTP 200 application/json with fresh Date. At the selected-handle check the API reported 8,910 rooms; 18 pages were scanned and the user's selected handle was not listed. Result: real UNKNOWN/not-listed, not an invented OFFLINE. Sanitized local evidence is in ignored `artifacts/live-verification.json`. A separate explicitly enabled real-network browser check validates the positive grant path using a public room returned by the real feed, without opening a room or fetching streams; its redacted result is in `artifacts/live-browser-verification.json` when run. Normal automated tests use synthetic metadata and do not claim real availability.

## Limits / publication gate still open

The API documentation recommends one request per page visitor; no numerical polling quota or contractual authorization for broad redistribution of a periodically polling blocker was stated on that page. Local connectivity is verified; scalable public release still requires confirming polling/license/rate/caching terms and possible shared infrastructure. Pagination is not a consistent snapshot, broadcasters can opt out, and IP restrictions can omit a room. A complete absence is therefore ALWAYS UNKNOWN. There is no truthful explicit OFFLINE sample from this feed, and no real stream-end timing guarantee.

Official opt-out explanation: https://support.chaturbate.com/hc/en-us/articles/22668646607252-DMCA-on-Chaturbate
The statistics API still requires broadcaster-issued tokens and is not used: https://chaturbate.com/statsapi/documentation/
Store publication remains unresolved: https://developer.chrome.com/docs/webstore/troubleshooting
