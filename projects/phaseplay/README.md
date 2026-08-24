# PhasePlay AI

PhasePlay is a mobile-first bankroll and risk-management coach for casino sessions. It helps a player plan a fixed entertainment budget, protect cash, record activity, and receive deterministic phase guidance. It does **not** predict wins, identify "hot" machines, or promise an advantage over the house.

## Product principles

- Coaching over prediction: advice is based on the player's preset limits and recorded session state.
- Protected means unavailable: protected cash is excluded from playable bankroll.
- Deterministic core: bankroll arithmetic and phase changes are explainable and testable.
- AI at the edges: language and image classification may improve input, but never override limits or claim future outcomes.
- Responsible play by default: clear stop floors, cool-offs, and exit guidance are part of the product.

## Stack

- **Web/PWA:** React, Vite, TypeScript
- **API:** Hono on Node (portable to edge runtimes)
- **Contracts:** Zod schemas and shared TypeScript types
- **Core logic:** framework-independent TypeScript packages
- **Tests:** Vitest
- **Persistence:** an in-memory adapter to start, with an interface ready for SQLite/Postgres

## Repository map

```text
apps/
  web/                  Mobile-first PWA shell
  api/                  HTTP API and composition root
packages/
  domain/               Shared schemas and data models
  engine/               Deterministic bankroll/phase coaching
  agent/                Safe AI-agent orchestration boundary
  game-classification/  Risk-profile classification
  persistence/          Session repository contracts/adapters
docs/                   Product and architecture notes
assets/                 Shared brand/source assets
```

## Get started

1. Copy `.env.example` to `.env` and adjust values if needed.
2. Run `npm install`.
3. In one terminal run `npm run dev:api`.
4. In another run `npm run dev`.
5. Open the URL Vite prints (normally `http://localhost:5173`).

Use `npm run check` for types, tests, and production builds.

## Initial user journey

1. Enter a session bankroll and an amount to protect.
2. Choose a session posture: make it last, balanced, or higher variance.
3. Receive a plan with a playable amount, stop floor, and opening phase.
4. Log games and bankroll changes.
5. Get deterministic guidance based on remaining budget—not predictions.

See [docs/architecture.md](docs/architecture.md) and [docs/responsible-play.md](docs/responsible-play.md).

The first source-backed game seeds and catalog API are described in [docs/game-catalog.md](docs/game-catalog.md).
