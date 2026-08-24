import { describe, expect, it } from "vitest";
import { cents } from "@phaseplay/domain";
import { createBankrollPlan, evaluateSession } from ".";

describe("bankroll engine", () => {
  it("keeps protected cash outside the playable bankroll", () => {
    const plan = createBankrollPlan(cents(20_000), "balanced", cents(5_000));
    expect(plan.playableBankroll).toBe(15_000);
  });

  it("ends coaching at the preset stop floor", () => {
    const plan = createBankrollPlan(cents(20_000), "balanced");
    expect(evaluateSession(plan, plan.stopFloor).action).toBe("end_session");
  });
});
