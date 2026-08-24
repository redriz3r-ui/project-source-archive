# Game catalog

The starter catalog is stored in `packages/game-classification/src/data/games.json`. These version-controlled seeds are the reviewed layer, not raw scraper output.

Each record separates:

- canonical identity and aliases;
- mechanics asserted by a source;
- version-specific wager and RTP facts;
- evidence claims with URL, source tier, retrieval time, and confidence;
- PhasePlay classification, confidence, basis, and classifier version;
- review status.

`reviewed` means the included factual claims were checked against the cited source. It does not imply that every property of the game is known. `needs_review` records can be searched during development but should be clearly labeled in user-facing responses.

## Catalog API

```text
GET /v1/games?q=buffalo
GET /v1/games/resolve?name=Huff%20N%20Xtra%20Puff
GET /v1/games/aristocrat/buffalo-cash
GET /v1/games/aristocrat/buffalo-cash/evidence
```

## Storage path

For the next stage, raw HTML/PDF extraction results should be stored as immutable JSON or object-storage artifacts. After review, normalized records will move to PostgreSQL while these seeds remain fixtures for tests and local development.

Never flatten version-specific RTP into a title-level value. Unknown values remain `null`, and classifications never represent outcome predictions.
