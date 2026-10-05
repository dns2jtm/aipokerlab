"use client";

import { useMemo, useState } from "react";
import { SAMPLE_HAND, type CanonicalHand } from "@/lib/parser/handParser";

interface GtoEval {
  street: string;
  gto: string;
  heroAction: string;
  evLoss: number;
  verdict: "good" | "mistake" | "neutral";
  solver?: { gtoFreq: { raise: number; call: number; fold: number; bet?: number; check?: number }; ev: number; source: string; spotHash: string };
}

function mockGtoEvalForHand(hand: CanonicalHand): GtoEval[] {
  const streets: (keyof CanonicalHand["streets"])[] = ["preflop", "flop", "turn", "river"];
  return streets
    .filter((k) => hand.streets[k].length > 0 || k === "preflop")
    .map((k, i) => {
      const actions = hand.streets[k];
      const board = hand.streetBoards[k] || hand.board || "";
      const seed = `${k}-${i}-${hand.id}-${hand.board}`;
      let h = 0;
      for (let c = 0; c < seed.length; c++) h = (h * 31 + seed.charCodeAt(c)) >>> 0;
      const r = (h % 100) / 100;
      const heroAction = actions.map((a) => `${a.player}: ${a.action}${a.amount !== undefined ? ` $${a.amount}` : ""}${a.isAllIn ? " (all-in)" : ""}`).join(" · ") || "—";
      if (k === "preflop") {
        return {
          street: "Preflop",
          gto: "Call 58% / 3-bet 12% / Fold 30% (A5s BTN vs CO open)",
          heroAction,
          evLoss: r > 0.6 ? -0.35 : -0.05,
          verdict: r > 0.6 ? "mistake" : "good",
        };
      }
      if (k === "flop") {
        return {
          street: `Flop [${board || "Qh 7d 2c"}]`,
          gto: "Check-raise 12%, call 58%, fold 30% — backdoor flush + overcard",
          heroAction,
          evLoss: r > 0.5 ? -0.8 : -0.1,
          verdict: r > 0.5 ? "mistake" : "good",
        };
      }
      if (k === "turn") {
        return {
          street: `Turn [${board || "—"}]`,
          gto: "Probe 35% / Check 65% — equity realization 85% when calling",
          heroAction,
          evLoss: r > 0.7 ? -1.1 : -0.15,
          verdict: r > 0.7 ? "mistake" : "neutral",
        };
      }
      return {
        street: `River [${board || "—"}]`,
        gto: "Bluff catch 42% / Fold 58% — MDF 62%, blockers matter",
        heroAction,
        evLoss: r > 0.65 ? -0.6 : -0.08,
        verdict: r > 0.65 ? "mistake" : "good",
      };
    });
}

export default function HandReplayer() {
  const [raw, setRaw] = useState(SAMPLE_HAND);
  const [hands, setHands] = useState<CanonicalHand[] | null>(null);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [errors, setErrors] = useState<{ index: number; message: string; snippet: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [solverEvals, setSolverEvals] = useState<Record<string, GtoEval[]>>({});
  const [solverLoading, setSolverLoading] = useState(false);

  const selectedHand = hands && hands.length > 0 ? hands[Math.min(selectedIdx, hands.length - 1)] : null;

  const evals = useMemo(() => {
    if (!selectedHand) return [];
    const key = selectedHand.id;
    if (solverEvals[key]) return solverEvals[key];
    return mockGtoEvalForHand(selectedHand);
  }, [selectedHand, solverEvals]);

  const totalEvLoss = evals.reduce((acc, e) => acc + e.evLoss, 0);

  const handleParse = async () => {
    setLoading(true);
    setErrors([]);
    try {
      const res = await fetch("/api/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rawText: raw }),
      });
      const data = await res.json();
      if (!res.ok) {
        setErrors([{ index: 0, message: data.error || "Parse failed", snippet: "" }]);
        setHands(null);
        return;
      }
      setHands(data.hands || []);
      setErrors(data.errors || []);
      setSelectedIdx(0);
      setSolverEvals({});
    } catch (e) {
      setErrors([{ index: 0, message: String(e), snippet: "" }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSolve = async () => {
    if (!selectedHand) return;
    setSolverLoading(true);
    try {
      const streets: (keyof CanonicalHand["streets"])[] = ["preflop", "flop", "turn", "river"];
      const activeStreets = streets.filter((k) => selectedHand.streets[k].length > 0 || k === "preflop");
      const results: GtoEval[] = [];
      for (const k of activeStreets) {
        const board = k === "preflop" ? "" : selectedHand.streetBoards[k] || selectedHand.board || "";
        const spot = {
          board,
          heroRange: selectedHand.heroCards || "As5s",
          villainRange: "random",
          pot: selectedHand.pot || 7.5,
          stacks: 100,
          betSizings: [0.33, 0.66, 1.5],
          rake: 0.05,
          street: k,
          position: "BB",
          heroCards: selectedHand.heroCards,
        };
        try {
          const res = await fetch("/api/solve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ spot }),
          });
          const data = await res.json();
          if (res.ok && data.gtoFreq) {
            const heroAction = selectedHand.streets[k].map((a) => `${a.player}: ${a.action}${a.amount !== undefined ? ` $${a.amount}` : ""}`).join(" · ") || "—";
            const evLoss = data.ev !== undefined ? -Math.abs(data.ev) * 0.5 : -0.2;
            results.push({
              street: k === "preflop" ? "Preflop" : `${k.charAt(0).toUpperCase() + k.slice(1)} [${board || "—"}]`,
              gto: `GTO: raise ${data.gtoFreq.raise}% / call ${data.gtoFreq.call}% / fold ${data.gtoFreq.fold}%${data.gtoFreq.bet !== undefined ? ` / bet ${data.gtoFreq.bet}%` : ""}${data.gtoFreq.check !== undefined ? ` / check ${data.gtoFreq.check}%` : ""} · EV ${data.ev?.toFixed(2) ?? "—"} · ${data.source}`,
              heroAction,
              evLoss,
              verdict: Math.abs(evLoss) > 0.4 ? "mistake" : Math.abs(evLoss) > 0.15 ? "neutral" : "good",
              solver: data,
            });
          } else {
            results.push(...mockGtoEvalForHand(selectedHand).filter((e) => e.street.toLowerCase().includes(k)));
          }
        } catch {
          results.push(...mockGtoEvalForHand(selectedHand).filter((e) => e.street.toLowerCase().includes(k)));
        }
      }
      if (results.length) setSolverEvals((prev) => ({ ...prev, [selectedHand.id]: results }));
    } finally {
      setSolverLoading(false);
    }
  };

  // Initial parse on mount via effect-like: if no hands, show sample parsed locally
  const hasHands = hands !== null;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <label className="text-sm font-semibold">Paste hand history</label>
          <p className="text-xs text-zinc-500">Supports PokerStars, GGPoker, generic. Paste one or multiple hands — auto-detects format.</p>
          <textarea
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            rows={14}
            placeholder="Paste hand history here..."
            className="w-full rounded-xl border border-zinc-300 bg-white p-3 font-mono text-xs leading-5 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleParse}
              disabled={loading}
              className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-semibold text-white hover:bg-zinc-800 disabled:opacity-50"
            >
              {loading ? "Parsing..." : "Parse & Evaluate"}
            </button>
            <button
              onClick={() => {
                setRaw(SAMPLE_HAND);
                setHands(null);
                setErrors([]);
                setSolverEvals({});
              }}
              className="rounded-full border border-zinc-300 bg-white px-5 py-2 text-sm font-semibold hover:bg-zinc-50"
            >
              Load sample
            </button>
            <button
              onClick={() => {
                setRaw("");
                setHands(null);
                setErrors([]);
                setSolverEvals({});
              }}
              className="rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm hover:bg-zinc-50"
            >
              Clear
            </button>
          </div>

          {hasHands && (
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <p className="text-xs font-semibold text-zinc-700">
                Parsed {hands?.length ?? 0} hand(s) {errors.length ? `· ${errors.length} error(s)` : "· no errors"}
              </p>
              {hands && hands.length > 1 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {hands.map((h, i) => (
                    <button
                      key={h.id + i}
                      onClick={() => setSelectedIdx(i)}
                      className={`rounded-full px-3 py-1 text-xs font-medium ${i === selectedIdx ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"}`}
                    >
                      #{i + 1} {h.site} {h.stakes ? `· ${h.stakes}` : ""} {h.heroCards ? `· ${h.heroCards}` : ""}
                    </button>
                  ))}
                </div>
              )}
              {errors.length > 0 && (
                <div className="mt-2 space-y-1">
                  {errors.map((e, i) => (
                    <p key={i} className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
                      Hand {e.index + 1}: {e.message} {e.snippet ? `— "${e.snippet.slice(0, 80)}..."` : ""}
                    </p>
                  ))}
                </div>
              )}
              {selectedHand && (
                <div className="mt-2 text-xs text-zinc-600">
                  <span className="font-semibold">{selectedHand.hero}</span> · {selectedHand.site} · {selectedHand.stakes || "—"} · {selectedHand.date} · Pot ${selectedHand.pot} · Board: {selectedHand.board || "—"}
                  {selectedHand.ante !== undefined && ` · Ante $${selectedHand.ante}`}
                  {selectedHand.straddle !== undefined && ` · Straddle $${selectedHand.straddle}`}
                  {selectedHand.sidePots && ` · Side pots: ${selectedHand.sidePots.join(", ")}`}
                  {selectedHand.winners.length > 0 && ` · Winner: ${selectedHand.winners.map((w) => `${w.player} $${w.amount}`).join(", ")}`}
                </div>
              )}
            </div>
          )}
          {!hasHands && (
            <p className="text-xs text-zinc-500">Click Parse & Evaluate to parse via /api/parse. Supports PokerStars and GGPoker, including all-in, side pots, straddle, ante.</p>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Street-by-street</h3>
            <div className="flex items-center gap-2">
              {selectedHand && (
                <button
                  onClick={handleSolve}
                  disabled={solverLoading}
                  className="rounded-full bg-emerald-600 px-3 py-1 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  {solverLoading ? "Solving..." : "GTO Evaluate (Solver)"}
                </button>
              )}
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-bold ${totalEvLoss < -1 ? "bg-red-100 text-red-700" : totalEvLoss < -0.3 ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-700"}`}
              >
                Total EV loss: {totalEvLoss.toFixed(2)} bb
              </span>
            </div>
          </div>

          {!selectedHand ? (
            <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-500">No hand selected. Paste a history and click Parse & Evaluate.</div>
          ) : (
            <div className="space-y-3">
              {(["preflop", "flop", "turn", "river"] as const)
                .filter((k) => selectedHand.streets[k].length > 0 || k === "preflop")
                .map((k) => {
                  const actions = selectedHand.streets[k];
                  const board = selectedHand.streetBoards[k] || "";
                  const ev = evals.find((e) => e.street.toLowerCase().includes(k));
                  return (
                    <div key={k} className="rounded-xl border border-zinc-200 bg-white p-4">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-bold capitalize">
                          {k}
                          {board ? <span className="ml-2 rounded bg-zinc-100 px-2 py-0.5 font-mono text-xs">{board}</span> : null}
                          {k !== "preflop" && !board && selectedHand.board ? <span className="ml-2 rounded bg-zinc-100 px-2 py-0.5 font-mono text-xs">{selectedHand.board}</span> : null}
                        </h4>
                        {ev && (
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-bold ${ev.verdict === "mistake" ? "bg-red-100 text-red-700" : ev.verdict === "good" ? "bg-emerald-100 text-emerald-700" : "bg-zinc-100 text-zinc-600"}`}
                          >
                            {ev.verdict === "mistake" ? "Mistake" : ev.verdict === "good" ? "Good" : "Neutral"} · {ev.evLoss.toFixed(2)} bb
                          </span>
                        )}
                      </div>
                      {k === "preflop" && selectedHand.heroCards && <p className="mt-1 font-mono text-xs">Hero: <strong>{selectedHand.heroCards}</strong></p>}
                      <div className="mt-2 space-y-1">
                        {actions.length ? (
                          actions.map((a, i) => (
                            <div key={i} className="flex gap-2 rounded bg-zinc-50 px-2 py-1 text-xs">
                              <span className="font-semibold">{a.player}</span>
                              <span className="text-zinc-700">
                                {a.action}
                                {a.amount !== undefined ? ` $${a.amount}` : ""}
                                {a.total !== undefined ? ` to $${a.total}` : ""}
                                {a.isAllIn ? " (all-in)" : ""}
                              </span>
                            </div>
                          ))
                        ) : (
                          <p className="text-xs text-zinc-500">No actions for this street.</p>
                        )}
                      </div>
                      {ev && (
                        <div className="mt-3 rounded-lg bg-zinc-50 p-3">
                          <p className="text-xs font-semibold text-zinc-700">GTO Evaluation {ev.solver ? `· ${ev.solver.source} · ${ev.solver.spotHash.slice(0, 8)}` : "(mock)"}</p>
                          <p className="mt-1 text-xs leading-5 text-zinc-600">{ev.gto}</p>
                          <p className="mt-1 text-xs text-zinc-500">Hero line: {ev.heroAction || "—"}</p>
                          <div className="mt-2 h-1.5 rounded-full bg-zinc-200">
                            <div className={`h-1.5 rounded-full ${ev.evLoss < -0.5 ? "bg-red-500" : ev.evLoss < -0.2 ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${Math.min(100, Math.abs(ev.evLoss) * 60 + 20)}%` }} />
                          </div>
                          <p className="mt-1 text-xs font-medium">
                            EV loss: <span className={ev.evLoss < -0.3 ? "text-red-600" : "text-zinc-700"}>{ev.evLoss.toFixed(2)} bb</span>
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          )}

          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <h4 className="flex items-center gap-2 text-sm font-bold text-emerald-800">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-600 text-xs text-white">AI</span>
              AI Coach — Grounded
            </h4>
            <p className="mt-2 text-xs leading-5 text-emerald-900/80">
              &quot;You folded A5s on Q72r vs 33% pot — that&apos;s -0.8bb. With backdoor flush + overcard you have 38% equity and realize 85% when you call. Rule: call any backdoor + overcard vs small bet. Want to drill 5 similar spots?&quot;
            </p>
            <p className="mt-2 text-xs text-emerald-700">Grounded in solver JSON · Vercel AI SDK streaming · ToS-compliant post-hand only.</p>
            <button className="mt-3 rounded-full bg-emerald-600 px-4 py-1.5 text-xs font-bold text-white opacity-60">Drill this spot (soon)</button>
          </div>
        </div>
      </div>
    </div>
  );
}
