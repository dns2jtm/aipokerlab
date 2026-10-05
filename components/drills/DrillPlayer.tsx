"use client";

import { useState } from "react";
import type { DrillHand } from "@/lib/drills/engine";

interface DrillPlayerProps {
  hands: DrillHand[];
  drillId: string;
  onComplete?: (xp: number) => void;
}

type Feedback = {
  correct: boolean;
  chosen: string;
  gto: string;
  gtoFreq: { raise: number; call: number; fold: number };
  evLoss: number;
  explanation: string;
  xp: number;
};

export default function DrillPlayer({ hands, drillId, onComplete }: DrillPlayerProps) {
  const [idx, setIdx] = useState(0);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [loading, setLoading] = useState(false);
  const [xpTotal, setXpTotal] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [done, setDone] = useState(false);
  const [startTime] = useState(() => Date.now());
  const [handStart, setHandStart] = useState(() => Date.now());

  const hand = hands[idx];
  const progress = ((idx + (feedback ? 1 : 0)) / hands.length) * 100;

  if (!hand) return <div className="text-sm text-zinc-500">No hands in this drill.</div>;

  async function choose(action: string) {
    if (feedback || loading) return;
    setLoading(true);
    const timeMs = Date.now() - handStart;
    try {
      const res = await fetch("/api/drills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ drillId, handId: hand.id, chosenAction: action, timeMs }),
      });
      const json = await res.json();
      if (json.attempt) {
        const fb: Feedback = {
          correct: json.attempt.correct,
          chosen: json.attempt.chosenAction,
          gto: json.attempt.gtoAction,
          gtoFreq: json.attempt.gtoFreq || hand.gtoFreq,
          evLoss: json.attempt.evLoss,
          explanation: json.attempt.explanation || hand.explanation,
          xp: json.attempt.xp || 0,
        };
        setFeedback(fb);
        setXpTotal((prev) => prev + fb.xp);
        if (fb.correct) setCorrectCount((c) => c + 1);
        if (json.progress?.completed) {
          setDone(true);
          onComplete?.(json.progress.xp);
        }
      } else {
        // Fallback local eval if API not seeded
        const correct = action.toLowerCase() === hand.gtoPrimary.toLowerCase();
        setFeedback({
          correct,
          chosen: action,
          gto: hand.gtoPrimary,
          gtoFreq: hand.gtoFreq,
          evLoss: correct ? 0 : -0.5,
          explanation: hand.explanation,
          xp: correct ? 10 : 2,
        });
        setXpTotal((prev) => prev + (correct ? 10 : 2));
        if (correct) setCorrectCount((c) => c + 1);
      }
    } catch {
      const correct = action.toLowerCase() === hand.gtoPrimary.toLowerCase();
      setFeedback({
        correct,
        chosen: action,
        gto: hand.gtoPrimary,
        gtoFreq: hand.gtoFreq,
        evLoss: correct ? 0 : -0.5,
        explanation: hand.explanation,
        xp: correct ? 10 : 2,
      });
    } finally {
      setLoading(false);
    }
  }

  function next() {
    if (idx + 1 >= hands.length) {
      setDone(true);
      return;
    }
    setIdx((i) => i + 1);
    setFeedback(null);
    setHandStart(Date.now());
  }

  if (done) {
    const score = Math.round((correctCount / hands.length) * 100);
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center">
        <p className="text-lg font-bold text-emerald-800">Drill complete!</p>
        <p className="mt-2 text-sm text-emerald-900">
          {correctCount}/{hands.length} correct · {score}% · +{xpTotal} XP
        </p>
        <div className="mt-3 h-2 rounded-full bg-emerald-200">
          <div className="h-2 rounded-full bg-emerald-600" style={{ width: `${score}%` }} />
        </div>
        <p className="mt-2 text-xs text-emerald-700">Next review: {score >= 80 ? "in 3 days" : score >= 60 ? "tomorrow" : "now — drill again"}</p>
        <button onClick={() => { setIdx(0); setFeedback(null); setDone(false); setXpTotal(0); setCorrectCount(0); }} className="mt-4 rounded-full bg-emerald-600 px-5 py-2 text-sm font-bold text-white hover:bg-emerald-700">
          Drill again
        </button>
      </div>
    );
  }

  const isPreflop = hand.street === "preflop";
  const actions = isPreflop
    ? ["raise", "call", "fold"]
    : hand.villainAction?.includes("checks to you")
      ? ["bet", "check"]
      : ["raise", "call", "fold"];

  return (
    <div className="space-y-3">
      {/* Progress */}
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-zinc-600">Hand {idx + 1} / {hands.length}</span>
        <span className="font-bold text-violet-600">+{xpTotal} XP · {correctCount} correct</span>
      </div>
      <div className="h-1.5 rounded-full bg-zinc-200">
        <div className="h-1.5 rounded-full bg-violet-600 transition-all" style={{ width: `${progress}%` }} />
      </div>

      {/* Hand card */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-zinc-900 px-2.5 py-1 font-bold text-white">{hand.heroPosition} · {hand.heroCards}</span>
          {hand.board && <span className="rounded bg-zinc-100 px-2 py-1 font-mono">{hand.board}</span>}
          <span className="rounded-full bg-zinc-100 px-2 py-1 capitalize">{hand.street}</span>
          <span className="text-zinc-500">Pot {hand.pot.toFixed(1)}bb · 100bb deep</span>
        </div>
        <p className="mt-3 text-sm font-semibold">{hand.villainAction} {hand.betSizePct ? `· ${hand.betSizePct}% pot` : ""}</p>
        <p className="mt-1 text-sm text-zinc-600">What does GTO do? <span className="font-mono text-xs text-zinc-400">vs GTO bot</span></p>

        <div className="mt-4 flex flex-wrap gap-2">
          {actions.map((a) => (
            <button
              key={a}
              onClick={() => choose(a)}
              disabled={!!feedback || loading}
              className={`rounded-full px-5 py-2 text-sm font-bold capitalize transition ${
                feedback
                  ? a === feedback.gto
                    ? "bg-emerald-600 text-white"
                    : a === feedback.chosen && !feedback.correct
                      ? "bg-red-500 text-white"
                      : "bg-zinc-100 text-zinc-400"
                  : a === "raise" || a === "bet"
                    ? "bg-emerald-600 text-white hover:bg-emerald-700"
                    : a === "call" || a === "check"
                      ? "bg-amber-400 text-zinc-900 hover:bg-amber-500"
                      : "bg-red-500 text-white hover:bg-red-600"
              } disabled:opacity-60`}
            >
              {a}
            </button>
          ))}
        </div>
        {loading && <p className="mt-2 text-xs text-zinc-500">Scoring vs GTO…</p>}
      </div>

      {/* Feedback */}
      {feedback && (
        <div className={`rounded-xl border p-4 ${feedback.correct ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
          <div className="flex items-center gap-2">
            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${feedback.correct ? "bg-emerald-600 text-white" : "bg-amber-500 text-white"}`}>
              {feedback.correct ? "✓ Correct" : "✕ Miss"} · GTO: {feedback.gto}
            </span>
            <span className="text-xs font-mono">Raise {feedback.gtoFreq.raise}% / Call {feedback.gtoFreq.call}% / Fold {feedback.gtoFreq.fold}%</span>
            <span className={`ml-auto text-xs font-bold ${feedback.evLoss < -0.3 ? "text-red-600" : "text-zinc-600"}`}>EV {feedback.evLoss.toFixed(2)}bb · +{feedback.xp} XP</span>
          </div>
          <p className="mt-2 text-sm leading-5 text-zinc-700">{feedback.explanation}</p>
          <div className="mt-3 flex gap-2">
            <button onClick={next} className="rounded-full bg-zinc-900 px-5 py-1.5 text-sm font-bold text-white hover:bg-zinc-800">
              {idx + 1 >= hands.length ? "Finish" : "Next →"}
            </button>
            <span className="self-center text-xs text-zinc-500">Spaced repetition: next due {feedback.correct ? "in 1-3 days" : "now"}</span>
          </div>
        </div>
      )}
    </div>
  );
}
