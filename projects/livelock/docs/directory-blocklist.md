# ThePornDude directory overlay — v0.4.0

User request: block sites mentioned by theporndude.com. This is a stricter overlay on the existing adult-category snapshot, not a replacement for it. The exact selected canonical Chaturbate room can still be allowed only on confirmed public LIVE status.

## Actual collection

On 2026-10-22 the public English directory homepage exposed 156 category links. All 156 category pages were inspected through ordinary browser navigation. One transient navigation timeout succeeded on retry. Their rendered category cards exposed site IDs and public external-link attributes. After deduplication: **9,036 distinct listings**.

Domain evidence came from those rendered external links, domain mentions in listing descriptions, 2,220 unique referral links checked with bounded credential-free HEAD requests, and displayed domain-link text on nine final public review pages. The HEAD collector used four workers, a delay between requests, a per-request timeout, and stopped on HTTP 429. It did not download destination bodies. No destination site pages, stream/video files or uncensored media were requested by that collector. The directory's browser pages may load their own ordinary identification assets; no images, reviews or other media are copied into the extension.

All 9,036 collected listings have a verified domain or are themselves links back to the directory. **3,035 unique website/redirector domains** are bundled in `src/rules/directory-domains.json`, including the directory and its public referral domain. Final unresolved listing count: zero. Metadata and an extraction hash are in `src/rules/directory-metadata.json`. No review prose, creator listing details or screenshots are bundled. The temporary source extraction is local data in /private/tmp, not part of the extension.

The directory advertises a larger total search index than the category snapshot. This collection does not claim every historical/search-only/unlisted entry, every translation/mirror, unknown JavaScript redirect destination or future addition. It verifies the public category snapshot actually collected. The large existing adult-category list continues to cover additional domains beyond it.

## Domain policy

Public-suffix-aware parsing (`tldts`, build/data preparation only) reduces affiliate URLs to website domains, preserves private hosting boundaries such as named Blogspot sites, and avoids guessing country suffixes. Valid nested destination query URLs and verified displayed domain aliases are included. Referral hosts are blocked too. No runtime resolver or new host permissions are added.

Under the user's new strict directory instruction, an explicitly included mixed-use domain is blocked in full: this includes 4chan.org, reddit.com, youtube.com, instagram.com, X/Twitter, Patreon and DeviantArt where present in the collected data. The earlier v0.3.0 exclusion of mixed-use roots no longer applies to directory-overlay domains. In particular, other 4chan boards are now blocked, not only /gif. Websites merely linked in unrelated directory navigation/legal boilerplate are not automatically added as listings.

All domains and their subdomains are denied for top-level/embedded navigation when protection is ON. The entire baseline is disabled by explicit protection OFF. The selected exact Chaturbate public room remains the sole live exception; granting it cannot allow Reddit, OnlyFans, the directory or other domains.

## Rebuild/update

`src/rules/directory-domains.json` and summary metadata are vendored facts, not remotely executed code. The reviewed baseline builder unions this file with the original community category list. Background tab lookup uses the same union. Updates require a deliberate new source extraction/import and rebuild/reload. There is no promise of automatic synchronization when the directory changes.

Reproduction tools: `scripts/import-directory.mjs` takes the browser-extracted category snapshot, normalizes domains and records provenance. `scripts/resolve-directory-links.mjs` processes its temporary unresolved queue with HEAD-only public requests. Final review-page domain labels can be included as DOM evidence in the input. These tools are preparation tools, not shipped network crawlers. No provider credentials or browsing-history log are involved.

Directory attribution: https://theporndude.com/ . Only domain facts are bundled; no claim is made that the directory's text/artwork is open licensed. Broad distribution/legal review remains outstanding as documented in production-report.md.
