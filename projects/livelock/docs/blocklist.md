# Broader adult-site blocking — v0.3.0

The previous default covered only five domains. The user reported erome.com and the /gif board on 4chan; neither was covered. This version bundles a much larger category snapshot and a separate board-path rule.

## Data and provenance

Source: [Block List Project adult-domain list](https://blocklistproject.github.io/Lists/alt-version/porn-nl.txt), retrieved 2026-10-22. Source header reports 953,393 entries and a 2026-07-18 modification date. Snapshot metadata and SHA-256 are retained in `src/rules/blocklist-metadata.json`. The upstream repository's [license](https://github.com/blocklistproject/Lists/blob/master/LICENSE) is Unlicense and is shipped in `third-party/blocklistproject-UNLICENSE.txt` in source and extension. The snapshot header itself labels the data MIT; that original header is preserved in metadata rather than silently rewritten.

After DNS-shape validation, excluding mixed-content/shared sites, adding required baseline domains including erome.com, and pruning redundant children covered by parent domains: **764,348 domain entries**, each covering its subdomains. This is a bundled list snapshot, not a guarantee of every adult domain or classification of every page. Lists may be incomplete or contain false positives.

The domains are grouped 100 per packaged DNR rule. This yields 7,644 domain rules plus one board regex (7,645 static rules total), within Chrome's guaranteed 30,000 static-rule allowance. All deny rules are priority 100, main_frame/sub_frame only. The exact selected-room priority-200 session allowance remains narrow and does not unlock any other listed domain. No new host permissions or runtime list downloads were added. The larger bundle costs approximately 30 MB unpacked for enforcement data/background lookup; the connected ZIP is about 7.4 MB.

Mixed-content roots such as 4chan, Reddit, Wikipedia, social networks and shared image hosts are excluded from blanket category blocking. These exclusions do not mean their content is all safe. Only explicitly added path restrictions apply on those hosts. This is a domain/path blocker, not an image classifier.

## 4chan /gif

A separate anchored regex blocks `/gif`, `/gif/`, threads and query/fragment variants on 4chan.org, 4channel.org and their subdomains, HTTP/HTTPS, including basic percent-encoded path variants. `/g/`, `/gifx/` and the rest of 4chan are not blanket-blocked. No thumbnails/content were inspected to implement the rule.

The background uses the same snapshot and path regex as Chrome's packaged rules to redirect already-open matching tabs. Suffix-set lookup avoids scanning 764,348 entries on every tab event. Protection OFF disables the entire ruleset and these tab guards; ON restores it. Existing preferences and broadcaster selection survive reload.

## Updates

Runtime is offline for list data. To intentionally review/update a snapshot, download the official text to a temporary file, run `node scripts/import-blocklist.mjs /path/to/porn-nl.txt`, inspect metadata/data changes and run the normal checks/build/package. Rebuild and reload Chrome to activate new static rules. The import script validates input size/shape, protects mixed sites, prunes redundant subdomains and records provenance; it does not execute downloaded data.

## Verification

Unit checks cover erome, subdomains, both reported examples, encoded/case variants, exact path boundaries, lookalike hosts and preserving other boards. Controller integration checks redirect existing matching tabs. Chromium tests verify actual native ERR_BLOCKED_BY_CLIENT for erome.com and boards.4chan.org/gif without downloading their content, Chrome testMatchOutcome for variants, and OFF/ON removal/restoration. Existing live-room, restart, race and provider tests remain included. Final result is recorded in test-matrix.md.
