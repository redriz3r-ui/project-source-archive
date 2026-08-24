# Architecture

The domain package is the source of truth for data exchanged across clients and services. The engine consumes domain values and returns coaching decisions without network, database, or AI dependencies.

The agent package is deliberately downstream of the engine. It can turn structured decisions into conversational text and can request game classification, but it cannot change financial totals, stop floors, or phase transitions.

Persistence is hidden behind `SessionRepository`. The starter in-memory adapter supports rapid iteration; a durable SQLite/Postgres adapter can replace it without changing the API or engine.

Amounts are stored as integer cents to avoid floating-point errors. Timestamps are ISO 8601 strings. IDs are opaque strings.
