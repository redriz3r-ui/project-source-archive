import { z } from "zod";

export const MoneySchema = z.number().int().nonnegative().brand("Cents");
export type Money = z.infer<typeof MoneySchema>;
export const cents = (value: number): Money => MoneySchema.parse(value);

export const SessionPostureSchema = z.enum(["make_it_last", "balanced", "higher_variance"]);
export type SessionPosture = z.infer<typeof SessionPostureSchema>;

export const PhaseSchema = z.enum(["runway", "explore", "opportunity", "protect", "stop"]);
export type Phase = z.infer<typeof PhaseSchema>;

export const RiskProfileSchema = z.enum(["low", "medium", "high", "unknown"]);
export type RiskProfile = z.infer<typeof RiskProfileSchema>;

export const GameSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  manufacturer: z.string().optional(),
  riskProfile: RiskProfileSchema,
  mechanics: z.array(z.string()).default([]),
  classificationConfidence: z.number().min(0).max(1),
  source: z.enum(["catalog", "user", "vision"]),
});
export type Game = z.infer<typeof GameSchema>;

export const BankrollPlanSchema = z.object({
  startingBankroll: MoneySchema,
  protectedCash: MoneySchema,
  playableBankroll: MoneySchema,
  stopFloor: MoneySchema,
  profitTarget: MoneySchema.optional(),
  posture: SessionPostureSchema,
});
export type BankrollPlan = z.infer<typeof BankrollPlanSchema>;

export const SessionLogSchema = z.object({
  id: z.string().min(1),
  sessionId: z.string().min(1),
  gameId: z.string().optional(),
  gameName: z.string().min(1),
  phase: PhaseSchema,
  startedAt: z.string().datetime(),
  endedAt: z.string().datetime().optional(),
  spins: z.number().int().positive().optional(),
  openingBalance: MoneySchema,
  closingBalance: MoneySchema,
  wagerCents: MoneySchema.optional(),
  notes: z.string().max(500).optional(),
});
export type SessionLog = z.infer<typeof SessionLogSchema>;

export const SessionSchema = z.object({
  id: z.string().min(1),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  status: z.enum(["planning", "active", "ended"]),
  plan: BankrollPlanSchema,
  currentBalance: MoneySchema,
  currentPhase: PhaseSchema,
  logs: z.array(SessionLogSchema),
});
export type Session = z.infer<typeof SessionSchema>;
