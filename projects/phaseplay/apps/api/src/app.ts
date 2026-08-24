import { Hono } from "hono";
import { cors } from "hono/cors";
import { cents, SessionPostureSchema } from "@phaseplay/domain";
import { createBankrollPlan } from "@phaseplay/engine";
import { getGame, getGameEvidence, resolveAlias, searchGames } from "@phaseplay/game-classification";

export const app = new Hono();
app.use("*", cors());
app.get("/health", (context) => context.json({ ok: true, service: "phaseplay-api" }));
app.get("/v1/games", (context) => {
  const query = context.req.query("q")?.trim();
  if (!query) return context.json({ error: "A non-empty q parameter is required." }, 400);
  return context.json({ games: searchGames(query), disclaimer: "Risk profiles describe mechanics and session fit; they do not predict outcomes." });
});
app.get("/v1/games/resolve", (context) => {
  const name = context.req.query("name")?.trim();
  if (!name) return context.json({ error: "A non-empty name parameter is required." }, 400);
  const game = resolveAlias(name);
  return game ? context.json({ game }) : context.json({ error: "Game not found." }, 404);
});
app.get("/v1/games/:manufacturer/:slug/evidence", (context) => {
  const id = `${context.req.param("manufacturer")}:${context.req.param("slug")}`;
  const game = getGame(id);
  return game ? context.json({ gameId: id, claims: getGameEvidence(id) }) : context.json({ error: "Game not found." }, 404);
});
app.get("/v1/games/:manufacturer/:slug", (context) => {
  const id = `${context.req.param("manufacturer")}:${context.req.param("slug")}`;
  const game = getGame(id);
  return game ? context.json({ game }) : context.json({ error: "Game not found." }, 404);
});
app.post("/v1/plans", async (context) => {
  const body = await context.req.json<{ startingBankrollCents: number; protectedCashCents?: number; posture: string }>();
  const posture = SessionPostureSchema.parse(body.posture);
  const plan = createBankrollPlan(cents(body.startingBankrollCents), posture, body.protectedCashCents === undefined ? undefined : cents(body.protectedCashCents));
  return context.json({ plan, disclaimer: "Budget coaching only. PhasePlay does not predict gambling outcomes." }, 201);
});
