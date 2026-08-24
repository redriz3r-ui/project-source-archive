import { z } from "zod";
import type { Game, RiskProfile } from "@phaseplay/domain";
import seedData from "./data/games.json";

export const PhaseProfileSchema = z.enum(["runway", "balanced", "feature_hunt", "swing", "lock_exit"]);
export const EvidenceClaimSchema = z.object({ id: z.string().min(1), field: z.string().min(1), value: z.union([z.string(), z.number(), z.boolean(), z.array(z.string())]), sourceUrl: z.string().url(), sourceType: z.enum(["manufacturer", "regulator", "casino", "trade", "community", "user"]), retrievedAt: z.string().datetime(), confidence: z.number().min(0).max(1) });
export const GameVersionSchema = z.object({ gameId: z.string().nullable(), jurisdiction: z.string().nullable(), rtpPercent: z.number().min(0).max(100).nullable(), minimumWagerCents: z.number().int().nonnegative().nullable(), maximumWagerCents: z.number().int().nonnegative().nullable(), evidenceClaimIds: z.array(z.string()) });
export const CatalogClassificationSchema = z.object({ riskProfile: z.enum(["low", "medium", "high", "unknown"]), phaseProfiles: z.array(PhaseProfileSchema).min(1), confidence: z.number().min(0).max(1), basis: z.array(z.string()), classifierVersion: z.string().min(1) });
export const GameCatalogRecordSchema = z.object({
  id: z.string().regex(/^[a-z0-9-]+:[a-z0-9-]+$/), canonicalName: z.string().min(1), manufacturer: z.string().min(1), family: z.string().nullable(), aliases: z.array(z.string()), mechanics: z.array(z.string()), versions: z.array(GameVersionSchema), classification: CatalogClassificationSchema, claims: z.array(EvidenceClaimSchema), reviewStatus: z.enum(["draft", "needs_review", "reviewed", "rejected"]), updatedAt: z.string().datetime(),
}).superRefine((record, context) => {
  const claimIds = new Set(record.claims.map((claim) => claim.id));
  for (const version of record.versions) for (const id of version.evidenceClaimIds) if (!claimIds.has(id)) context.addIssue({ code: z.ZodIssueCode.custom, message: `Version references missing claim: ${id}` });
});

export type GameCatalogRecord = z.infer<typeof GameCatalogRecordSchema>;
export type EvidenceClaim = z.infer<typeof EvidenceClaimSchema>;
export type CatalogClassification = z.infer<typeof CatalogClassificationSchema>;

const parsedSeeds = z.array(GameCatalogRecordSchema).parse(seedData);
const records = new Map(parsedSeeds.map((record) => [record.id, record]));
const normalize = (value: string) => value.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, " ").trim();

export function listGames(): GameCatalogRecord[] { return structuredClone([...records.values()]); }
export function getGame(id: string): GameCatalogRecord | null { const record = records.get(id); return record ? structuredClone(record) : null; }
export function getGameEvidence(id: string): EvidenceClaim[] { return getGame(id)?.claims ?? []; }
export function getClassification(id: string): CatalogClassification | null { return getGame(id)?.classification ?? null; }
export function searchGames(query: string, limit = 10): GameCatalogRecord[] {
  const needle = normalize(query); if (!needle) return [];
  return listGames().map((record) => { const names = [record.canonicalName, ...record.aliases].map(normalize); const exact = names.includes(needle); const starts = names.some((name) => name.startsWith(needle)); const contains = names.some((name) => name.includes(needle) || needle.includes(name)); return { record, score: exact ? 3 : starts ? 2 : contains ? 1 : 0 }; }).filter(({ score }) => score > 0).sort((a, b) => b.score - a.score || a.record.canonicalName.localeCompare(b.record.canonicalName)).slice(0, limit).map(({ record }) => record);
}
export function resolveAlias(name: string): GameCatalogRecord | null { return searchGames(name, 1)[0] ?? null; }

const HIGH_VARIANCE_MARKERS = ["hold & spin", "hold and spin", "jackpot", "bonus buy"];
export function classifyFromMetadata(input: Pick<Game, "name" | "manufacturer" | "mechanics">): Pick<Game, "riskProfile" | "classificationConfidence"> {
  const text = [input.name, input.manufacturer, ...input.mechanics].filter(Boolean).join(" ").toLowerCase();
  const riskProfile: RiskProfile = HIGH_VARIANCE_MARKERS.some((marker) => text.includes(marker)) ? "high" : "unknown";
  return { riskProfile, classificationConfidence: riskProfile === "unknown" ? 0 : 0.65 };
}
export const classificationDisclaimer = "Risk profiles describe game mechanics and session fit; they do not predict outcomes.";
