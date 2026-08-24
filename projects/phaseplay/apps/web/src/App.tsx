import { FormEvent, useMemo, useState } from "react";

type Plan = { startingBankroll: number; protectedCash: number; playableBankroll: number; stopFloor: number };
type View = "setup" | "active";

const phases = [
  { number: "01", name: "RUNWAY", purpose: "Establish the session" },
  { number: "02", name: "EXPLORE", purpose: "Observe without chasing" },
  { number: "03", name: "OPPORTUNITY", purpose: "Use planned flexibility" },
  { number: "04", name: "PROTECT", purpose: "Reduce risk and secure cash" },
  { number: "05", name: "STOP", purpose: "End at your limit" },
] as const;

const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;
const tap = () => navigator.vibrate?.(12);

export function App() {
  const [bankroll, setBankroll] = useState(200);
  const [protectedCash, setProtectedCash] = useState(50);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [view, setView] = useState<View>("setup");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const playable = useMemo(() => Math.max(0, bankroll - protectedCash), [bankroll, protectedCash]);

  async function begin(event: FormEvent) {
    event.preventDefault(); tap(); setError(""); setLoading(true);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? "http://localhost:8787"}/v1/plans`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ startingBankrollCents: Math.round(bankroll * 100), protectedCashCents: Math.round(protectedCash * 100), posture: "balanced" }),
      });
      if (!response.ok) throw new Error("CHECK BANKROLL AND PROTECTED CASH");
      const result = await response.json() as { plan: Plan };
      setPlan(result.plan); setView("active");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "COACHING LINK OFFLINE");
    } finally { setLoading(false); }
  }

  function reset() { tap(); setView("setup"); setPlan(null); setError(""); }

  return <main className="cabinet">
    <header><span className="logo">PP</span><div><strong>PHASEPLAY</strong><small>THE 5 PHASE METHOD</small></div><span className="ready"><i/> READY</span></header>
    <section className="bezel"><div className="screen" aria-live="polite">
      <div className="screen-head"><span>SESSION COACH</span><span>{view === "setup" ? "SETUP" : "LIVE"}</span></div>
      <div className="marquee">{view === "setup" ? "SET YOUR LIMITS" : "PHASE 1 · RUNWAY"}</div>
      <PhaseTable activePhase={view === "active" ? 1 : 0}/>
      {view === "setup" ? <Setup bankroll={bankroll} protectedCash={protectedCash} playable={playable} loading={loading} error={error} setBankroll={setBankroll} setProtectedCash={setProtectedCash} begin={begin}/> : <Active plan={plan!} reset={reset}/>} 
    </div></section>
    <footer><span><i/> BUDGET COACH</span><span>NO PREDICTIONS</span><span>STOP ANY TIME</span></footer>
  </main>;
}

function PhaseTable({ activePhase }: { activePhase: number }) {
  return <div className="phase-table" aria-label="The five phases">
    <div className="phase-heading"><span>PHASE</span><span>PURPOSE</span><span>STATUS</span></div>
    {phases.map((phase, index) => {
      const active = activePhase === index + 1;
      return <div className={active ? "phase-row active" : "phase-row"} key={phase.number}>
        <b>{phase.number}</b><span><strong>{phase.name}</strong><small>{phase.purpose}</small></span><em>{active ? "ACTIVE" : activePhase ? "LOCKED" : "READY"}</em>
      </div>;
    })}
  </div>;
}

type SetupProps = { bankroll: number; protectedCash: number; playable: number; loading: boolean; error: string; setBankroll: (value: number) => void; setProtectedCash: (value: number) => void; begin: (event: FormEvent) => void };
function Setup(props: SetupProps) {
  return <form onSubmit={props.begin}>
    <p className="prompt">&gt; ENTER WHAT YOU BROUGHT. PROTECT WHAT YOU WILL NOT PLAY.</p>
    <div className="money-grid">
      <label><span>BANKROLL</span><span className="money-input">$<input aria-label="Bankroll" type="number" inputMode="decimal" min="1" value={props.bankroll} onChange={(event) => props.setBankroll(Number(event.target.value))}/></span></label>
      <label><span>PROTECTED</span><span className="money-input">$<input aria-label="Protected cash" type="number" inputMode="decimal" min="0" max={Math.max(0, props.bankroll - 1)} value={props.protectedCash} onChange={(event) => props.setProtectedCash(Number(event.target.value))}/></span></label>
    </div>
    <div className="available"><span>AVAILABLE TO PLAY</span><strong>{money(props.playable * 100)}</strong></div>
    {props.error && <p className="error">! {props.error}</p>}
    <div className="controls"><button className="key primary" disabled={props.playable <= 0 || props.loading}>{props.loading ? "LOADING..." : "BEGIN PHASE 1"}</button></div>
  </form>;
}

function Active({ plan, reset }: { plan: Plan; reset: () => void }) {
  return <section className="active-panel">
    <p className="prompt pulse">&gt; ESTABLISH THE SESSION. DO NOT CHASE.</p>
    <div className="readouts"><div><span>STARTED</span><strong>{money(plan.playableBankroll)}</strong></div><div><span>CURRENT</span><strong>{money(plan.playableBankroll)}</strong></div><div><span>CHANGE</span><strong>$0.00</strong></div></div>
    <div className="instruction"><span>PHASE 1 PURPOSE</span><p>Begin inside the plan. Observe the session before making any adjustment.</p></div>
    <div className="controls two"><button className="key secondary" type="button" onClick={reset}>ADJUST PLAN</button><button className="key primary" type="button" onClick={tap}>LOG A GAME</button></div>
  </section>;
}
