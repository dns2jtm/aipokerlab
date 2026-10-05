"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import type { CoachingCardV2 } from "@/lib/coach/promptComposer";

const CoachingCard = dynamic(() => import("@/components/coach/CoachingCard"), {
  loading: () => (
    <div className="animate-pulse rounded-xl border border-zinc-200 bg-white p-5">
      <div className="h-4 w-24 rounded bg-zinc-200" />
      <div className="mt-3 h-4 w-full rounded bg-zinc-100" />
      <div className="mt-2 h-4 w-3/4 rounded bg-zinc-100" />
      <div className="mt-4 h-20 rounded-lg bg-zinc-100" />
    </div>
  ),
});

type HandOption = {
  id: string;
  label: string;
  heroCards: string;
  board: string;
  street: string;
  heroPosition: string;
  villainPosition: string;
  actions: Array<{ player: string; action: string }>;
  solver: { spotHash: string; gtoFreq: { raise: number; call: number; fold: number }; evLoss: number; pot: number };
};

const HANDS: HandOption[] = [
  {
    id: "h1",
    label: "A♠5♠ on Q♥7♦2♣ — folded vs 33% c-bet (BB vs BTN)",
    heroCards: "As 5s",
    board: "Qh 7d 2c",
    street: "flop",
    heroPosition: "BB",
    villainPosition: "BTN",
    actions: [{ player: "Hero", action: "checks" }, { player: "Villain", action: "bets $4 (33% pot)" }, { player: "Hero", action: "folds" }],
    solver: { spotHash: "Qh7d2c-BBvsBTN-33pct", gtoFreq: { raise: 12, call: 58, fold: 30 }, evLoss: -0.8, pot: 7.5 },
  },
  {
    id: "h2",
    label: "K♥9♥ on Q♥7♦2♣ — folded BB vs BTN open (preflop)",
    heroCards: "Kh 9h",
    board: "",
    street: "preflop",
    heroPosition: "BB",
    villainPosition: "BTN",
    actions: [{ player: "Villain", action: "raises 2.5x" }, { player: "Hero", action: "folds" }],
    solver: { spotHash: "pre-BBvsBTN-K9s", gtoFreq: { raise: 8, call: 74, fold: 18 }, evLoss: -0.42, pot: 3.5 },
  },
  {
    id: "h3",
    label: "Q♦J♦ on Q♥7♦2♣5♥ — folded vs turn barrel 66% (top pair)",
    heroCards: "Qd Jd",
    board: "Qh 7d 2c 5h",
    street: "turn",
    heroPosition: "BB",
    villainPosition: "BTN",
    actions: [{ player: "Hero", action: "checks" }, { player: "Villain", action: "bets 66% pot" }, { player: "Hero", action: "folds" }],
    solver: { spotHash: "Qh7d2c5h-turn-66pct", gtoFreq: { raise: 5, call: 95, fold: 0 }, evLoss: -2.1, pot: 15 },
  },
  {
    id: "h4",
    label: "A♦4♠ on — called vs BTN open (missed 3-bet)",
    heroCards: "Ad 4s",
    board: "",
    street: "preflop",
    heroPosition: "BB",
    villainPosition: "BTN",
    actions: [{ player: "Villain", action: "raises 2.5x" }, { player: "Hero", action: "calls" }],
    solver: { spotHash: "pre-BBvsBTN-A4s", gtoFreq: { raise: 35, call: 55, fold: 10 }, evLoss: -0.4, pot: 5.5 },
  },
  {
    id: "h5",
    label: "9♣2♦ on Q♥7♦2♣ — folded vs 33% c-bet (correct fold)",
    heroCards: "9c 2d",
    board: "Qh 7d 2c",
    street: "flop",
    heroPosition: "BB",
    villainPosition: "BTN",
    actions: [{ player: "Hero", action: "checks" }, { player: "Villain", action: "bets 33% pot" }, { player: "Hero", action: "folds" }],
    solver: { spotHash: "Qh7d2c-92o-33pct", gtoFreq: { raise: 2, call: 10, fold: 88 }, evLoss: -0.08, pot: 7.5 },
  },
];

const MOCK_LEAKS = [
  { category: "Preflop", subcategory: "BB vs BTN over-fold", severity: "high", evLossBBper100: 4.2, frequency: "68% fold (GTO 42%)", sampleSize: 214 },
  { category: "Postflop", subcategory: "fold vs c-bet", severity: "medium", evLossBBper100: 1.8, frequency: "58% fold (GTO 45%)", sampleSize: 76 },
];

export default function CoachPage() {
  const [selectedId, setSelectedId] = useState<string>(HANDS[0].id);
  const [card, setCard] = useState<CoachingCardV2 | null>(null);
  const [meta, setMeta] = useState<{ provider?: string; promptVersion?: string; cacheHit?: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const selected = HANDS.find((h) => h.id === selectedId) || HANDS[0];

  async function handleCoach() {
    setLoading(true);
    setError(null);
    setCard(null);
    setMeta(null);
    setStreamingText("");
    try {
      const res = await fetch("/api/coach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hand: {
            id: selected.id,
            heroCards: selected.heroCards,
            board: selected.board,
            street: selected.street,
            heroPosition: selected.heroPosition,
            villainPosition: selected.villainPosition,
            actions: selected.actions,
          },
          solverResult: {
            spotHash: selected.solver.spotHash,
            board: selected.board,
            heroCards: selected.heroCards,
            heroPosition: selected.heroPosition,
            villainPosition: selected.villainPosition,
            pot: selected.solver.pot,
            gtoFreq: selected.solver.gtoFreq,
            evLoss: selected.solver.evLoss,
            source: "cache",
          },
          leakHistory: MOCK_LEAKS,
          tone: "concise",
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.error ? `${errJson.error}: ${errJson.details || ""}` : `Coach API ${res.status}`);
      }

      const provider = res.headers.get("X-Coach-Provider") || res.headers.get("x-coach-provider") || "mock";
      const promptVersion = res.headers.get("X-Prompt-Version") || res.headers.get("x-prompt-version") || "v2.1";
      const cacheHit = (res.headers.get("X-Cache-Hit") || res.headers.get("x-cache-hit")) === "true";

      if (!res.body) {
        const json = await res.json();
        const { _meta, ...rest } = json as CoachingCardV2 & { _meta?: { provider?: string; promptVersion?: string; cached?: boolean } };
        setCard(rest as CoachingCardV2);
        setMeta({
          provider: _meta?.provider || provider,
          promptVersion: _meta?.promptVersion || promptVersion,
          cacheHit: _meta?.cached ?? cacheHit,
        });
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        acc += chunk;
        setStreamingText(acc);
      }
      try {
        const parsed = JSON.parse(acc);
        const { _meta, ...rest } = parsed as CoachingCardV2 & { _meta?: { provider?: string; promptVersion?: string; cached?: boolean } };
        setCard(rest as CoachingCardV2);
        setMeta({
          provider: _meta?.provider || provider,
          promptVersion: _meta?.promptVersion || promptVersion,
          cacheHit: _meta?.cached ?? cacheHit,
        });
      } catch {
        setError("Failed to parse coaching response");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold">AI Coach</h1>
        <p className="text-sm text-zinc-600">Streaming coach grounded in solver JSON · temp 0.3 · ToS post-hand only.</p>
        {meta && (
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <span className={`rounded-full border px-2 py-0.5 font-semibold ${meta.provider === "mock" ? "border-zinc-200 bg-zinc-100 text-zinc-600" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
              {meta.provider === "mock" ? "Mock" : meta.provider === "anthropic" ? "Claude 3.5 Sonnet" : meta.provider === "openai" ? "GPT-4o" : meta.provider}
              {meta.cacheHit ? " · cached" : " · fresh"}
            </span>
            {meta.promptVersion && <span className="rounded-full border border-zinc-200 bg-white px-2 py-0.5 font-mono text-zinc-600">{meta.promptVersion}</span>}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-4">
        <label className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Select a hand</label>
        <div className="mt-2 grid gap-2">
          {HANDS.map((h) => (
            <button
              key={h.id}
              onClick={() => setSelectedId(h.id)}
              className={`rounded-lg border px-3 py-2.5 text-left text-sm ${selectedId === h.id ? "border-emerald-500 bg-emerald-50 font-semibold" : "border-zinc-200 bg-white hover:bg-zinc-50"}`}
            >
              <span className="font-mono text-xs text-zinc-500">{h.heroCards}</span> · {h.label}
              <span className="ml-2 font-mono text-xs text-zinc-400">EV {h.solver.evLoss}bb · {h.solver.gtoFreq.call}% call</span>
            </button>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleCoach}
            disabled={loading}
            className="rounded-full bg-emerald-600 px-5 py-2 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {loading ? "Coaching…" : "Get coaching →"}
          </button>
          <span className="self-center text-xs text-zinc-500">Grounded: {selected.solver.spotHash} · temp 0.3 · 800 tokens</span>
        </div>
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      </div>

      {loading && streamingText && (
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <p className="text-xs font-semibold text-zinc-500">Streaming…</p>
          <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-zinc-600">{streamingText.slice(0, 600)}…</pre>
        </div>
      )}

      {card ? (
        <CoachingCard
          summary={card.summary}
          why={card.why}
          heuristic={card.heuristic}
          evLoss={card.evLoss}
          verdict={card.verdict}
          rule={card.rule}
          example={card.example}
          drill={card.drill}
          nextStep={card.nextStep}
          spotHash={card.spotHash}
          gtoFreq={card.gtoFreq}
          solverGrounded={card.solverGrounded}
          drillSuggestion={card.drillSuggestion}
          provider={meta?.provider}
          promptVersion={meta?.promptVersion}
          cacheHit={meta?.cacheHit}
          onDrillClick={() => (window.location.href = "/drills")}
        />
      ) : !loading ? (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-6 text-center text-sm text-zinc-500">
          Select a hand and click Get coaching to see the 1 rule / 1 example / 1 drill card.
        </div>
      ) : null}

      <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800">Training only — not for use during play. Compliant with PokerStars / GGPoker ToS.</div>
    </div>
  );
}
