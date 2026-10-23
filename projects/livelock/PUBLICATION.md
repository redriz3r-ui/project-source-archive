# Publication notes

LiveLock is being preserved as a public-source candidate.

Current scope: TypeScript extension with setup, test files and an existing license.

Preparation still required: Inspect config/, bundled dist variants and test artifacts for personalized room/setup data; publish source plus sanitized setup examples, with the actual behavior and maturity clearly documented.

This source export deliberately omits local credentials, personal configurations, caches, installed dependencies, local datasets and selected media/models. Some demos need replacement assets before they run. Existing validation documents describe earlier checks and have not been rerun for this export. No new open-source license is granted by this export; see any existing project license.

The downloaded src/rules/adult-domains.json data file is omitted from the public source export. Review scripts/import-blocklist.mjs and the blocklist documentation to obtain an appropriate local list before building.
