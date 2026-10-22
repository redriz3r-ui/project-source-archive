# Permission model — v0.2.0

- `declarativeNetRequest`: packaged baseline/custom navigation denial and exact session allowance. Block/allow actions use this permission's implicit host access; no blanket host permission is needed.
- `storage`: local preferences/selected status; transient `storage.session` request budget, page hint and still-valid selected observation. Local access restricted to TRUSTED_CONTEXTS; content scripts ask background for decisions instead of reading selections.
- `alarms`: approximate minute polling and 30-second lease reconciliation. DNR has no native timestamp expiry.
- `webNavigation`: committed/history state events for route and SPA reconciliation. No navigation history is persisted.
- `tabs`: inspect and relock open unauthorized tabs, including custom blocked domains. No browsing history collection or logging.
- `https://chaturbate.com/*`, `https://*.chaturbate.com/*`: document-start content guard. The existing canonical host permission ALSO permits direct cross-origin extension fetch of the documented official HTTPS affiliate API. No new origin, gateway permission or authentication cookie access was added.
- Web-accessible resource: only `blocked.html`, on platform hosts, for guarded navigation. Version 0.4.1 displays the chosen handle and status only when opened as a top-level extension page. Its dedicated read-only status message returns no selection to embedded frames; embedded rendering is generic. The full config and UI control actions are not available to the restricted page. Settings is not web-accessible.

Connected production requests documented paginated JSON metadata from Chaturbate with a public campaign slug, `client_ip=request_ip`, credentials omitted, no referrer, redirects rejected. The selected handle is matched locally rather than sent as a query. Response room lists are transient; only selected-room minimal observation and a page-offset hint are retained. No API secret, login cookie or password is bundled. The public campaign is designed by the official API for client-side requests and is intentionally visible in the compiled connected build.

Simulator and explicit unconfigured builds make no provider network requests. No cookies/history/clipboard/broad webRequest/remote-script permission is requested. The optional gateway client remains unused.

Version 0.3.0 bundles broad adult-domain denial and a 4chan /gif navigation rule using existing declarativeNetRequest/tabs permissions. No added host permissions or external list fetch at runtime. See blocklist.md.

Version 0.4.0 adds a strict ThePornDude domain overlay under the user’s explicit request. Listed domains override the earlier mixed-content exclusions and are blocked in full. Source collection is a data-preparation step only; no runtime crawler, added host permissions, copied review/media content or automatic source updates. See directory-blocklist.md.

Version 0.4.2 allows the top-level restricted page to read its existing local config/manual-lock preference for a resilient name reminder. This is not a grant source: it always marks live verification unavailable until the background positively responds. Embedded rendering performs neither the storage read nor a status request and exposes no selection. No new Chrome permissions, remote requests or access-policy changes.
