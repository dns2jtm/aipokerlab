"use client";

import { useState } from "react";

export interface CoachingCardProps {
  summary?: string;
  why?: string;
  heuristic?: string;
  evLoss?: number;
  // V2 fields
  verdict?: "good" | "mistake" | "big_mistake";
  rule?: string;
  example?: string;
  drill?: string;
  nextStep?: string;
  spotHash?: string;
  gtoFreq?: { raise: number; call: number; fold: number };
  solverGrounded?: boolean;
  drillSuggestion?: { type: string; spotHash: string };
  streaming?: boolean;
  onDrillClick?: () => void;
  // LLM provider transparency
  provider?: "openai" | "anthropic" | "mock" | string;
  promptVersion?: string;
  cacheHit?: boolean;
}

function VerdictBadge({ verdict }: { verdict?: string }) {
  if (!verdict) return null;
  const map: Record<string, { label: string; cls: string }> = {
    good: { label: "Good", cls: "bg-emerald-100 text-emerald-700 border-emerald-200" },
    mistake: { label: "Mistake", cls: "bg-amber-100 text-amber-800 border-amber-200" },
    big_mistake: { label: "Big Mistake", cls: "bg-red-100 text-red-700 border-red-200" },
  };
  const v = map[verdict] || map.mistake;
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold ${v.cls}`}>
      {verdict === "good" ? "✓ " : verdict === "big_mistake" ? "✕ " : "⚠ "}
      {v.label}
    </span>
  );
}

function ProviderBadge({ provider, cacheHit }: { provider?: string; cacheHit?: boolean }) {
  if (!provider) return null;
  const isMock = provider === "mock";
  const label = isMock ? "Mock" : provider === "anthropic" ? "Claude 3.5 Sonnet" : provider === "openai" ? "GPT-4o" : provider;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${
        isMock ? "border-zinc-200 bg-zinc-100 text-zinc-600" : "border-emerald-200 bg-emerald-50 text-emerald-700"
      }`}
      title={cacheHit ? "Served from cache" : isMock ? "Mock fallback — no API key" : "Real LLM"}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${isMock ? "bg-zinc-400" : "bg-emerald-500"}`} />
      {label}
      {cacheHit && <span className="ml-1 rounded bg-white px-1 py-0 text-[10px] font-bold border border-zinc-200">cached</span>}
    </span>
  );
}

export default function CoachingCard({
  summary,
  why,
  heuristic,
  evLoss,
  verdict,
  rule,
  example,
  drill,
  nextStep,
  spotHash,
  gtoFreq,
  solverGrounded,
  drillSuggestion,
  streaming,
  onDrillClick,
  provider,
  promptVersion,
  cacheHit,
}: CoachingCardProps) {
  const displayRule = rule || heuristic || "";
  const displaySummary = summary || (verdict ? `${verdict} — ${displayRule.slice(0, 60)}` : "Coaching");
  const displayWhy = why || "";
  const loss = evLoss ?? 0;
  const isMistake = verdict === "mistake" || verdict === "big_mistake" || loss < -0.3;

  const [feedback, setFeedback] = useState<"helpful" | "not_helpful" | null>(null);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shareStatus, setShareStatus] = useState<string | null>(null);

  async function handleFeedback(helpful: boolean) {
    if (feedback || feedbackSubmitting) return;
    setFeedbackSubmitting(true);
    try {
      const res = await fetch("/api/coach/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spotHash: spotHash || "unknown",
          helpful,
          verdict,
          provider: provider || "mock",
          promptVersion: promptVersion || "v2.1",
        }),
      });
      if (res.ok) {
        setFeedback(helpful ? "helpful" : "not_helpful");
      } else {
        setShareStatus("Feedback failed");
        setTimeout(() => setShareStatus(null), 2000);
      }
    } catch {
      setShareStatus("Feedback failed");
      setTimeout(() => setShareStatus(null), 2000);
    } finally {
      setFeedbackSubmitting(false);
    }
  }

  function buildShareText(): string {
    const parts = [
      `Lab Coach — ${verdict || "coaching"} (${provider || "mock"}${promptVersion ? ` · ${promptVersion}` : ""})`,
      `Summary: ${displaySummary}`,
      displayRule ? `Rule: ${displayRule}` : "",
      example ? `Example: ${example}` : "",
      drill ? `Drill: ${drill}` : "",
      displayWhy ? `Why: ${displayWhy}` : "",
      `EV: ${loss.toFixed(2)}bb · GTO: ${gtoFreq ? `R${gtoFreq.raise}/C${gtoFreq.call}/F${gtoFreq.fold}` : "—"} · spot ${spotHash || "—"}`,
      "Training only — not for use during play.",
    ].filter(Boolean);
    return parts.join("\n");
  }

  async function handleCopy() {
    const text = buildShareText();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: create textarea
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  async function handleShare() {
    const text = buildShareText();
    const shareData = {
      title: "Lab Coach — Coaching Card",
      text,
    };
    try {
      if (navigator.share && navigator.canShare?.(shareData)) {
        await navigator.share(shareData);
        setShareStatus("Shared!");
        setTimeout(() => setShareStatus(null), 2000);
      } else {
        await handleCopy();
        setShareStatus("Copied — share not supported");
        setTimeout(() => setShareStatus(null), 2000);
      }
    } catch (err) {
      // user cancelled or error — fallback to copy
      if ((err as Error)?.name !== "AbortError") {
        await handleCopy();
      }
    }
  }

  return (
    <div
      className={`rounded-xl border p-4 md:p-5 ${isMistake ? "border-amber-200 bg-amber-50/60" : verdict === "good" ? "border-emerald-200 bg-emerald-50" : "border-zinc-200 bg-white"}`}
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-600 text-xs font-bold text-white">AI</span>
          <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Lab Coach</span>
          <VerdictBadge verdict={verdict} />
          {streaming && <span className="animate-pulse text-xs text-zinc-400">streaming…</span>}
        </div>
        <div className="flex items-center gap-2">
          <ProviderBadge provider={provider} cacheHit={cacheHit} />
          {typeof loss === "number" && (
            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${loss < -1 ? "bg-red-100 text-red-700" : loss < -0.3 ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-700"}`}>
              EV {loss > 0 ? "+" : ""}{loss.toFixed(2)} bb
            </span>
          )}
          {solverGrounded !== undefined && (
            <span className={`rounded-full px-2 py-0.5 text-xs ${solverGrounded ? "bg-emerald-100 text-emerald-700" : "bg-zinc-100 text-zinc-500"}`}>
              {solverGrounded ? "Grounded" : "Ungrounded"}
            </span>
          )}
        </div>
      </div>

      {/* Summary */}
      <p className="mt-3 text-sm font-bold leading-6 text-zinc-900">{displaySummary}</p>

      {/* Why */}
      {displayWhy && <p className="mt-2 text-sm leading-6 text-zinc-700">{displayWhy}</p>}

      {/* GTO frequencies */}
      {gtoFreq && (
        <div className="mt-3 flex gap-2 text-xs">
          <span className="rounded-full bg-white px-2.5 py-1 font-mono font-semibold border border-zinc-200">Raise {gtoFreq.raise}%</span>
          <span className="rounded-full bg-white px-2.5 py-1 font-mono font-semibold border border-zinc-200">Call {gtoFreq.call}%</span>
          <span className="rounded-full bg-white px-2.5 py-1 font-mono font-semibold border border-zinc-200">Fold {gtoFreq.fold}%</span>
        </div>
      )}

      {/* Rule */}
      {displayRule && (
        <div className="mt-3 rounded-lg border border-emerald-200 bg-white p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-emerald-700">Rule</p>
          <p className="mt-1 text-sm font-semibold leading-5 text-emerald-900">{displayRule}</p>
        </div>
      )}

      {/* Example */}
      {example && (
        <div className="mt-3 rounded-lg bg-white p-3 border border-zinc-200">
          <p className="text-xs font-bold uppercase tracking-wide text-zinc-500">Example</p>
          <p className="mt-1 text-sm leading-5 text-zinc-700">{example}</p>
        </div>
      )}

      {/* Drill */}
      {drill && (
        <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50 p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-violet-700">Drill</p>
          <p className="mt-1 text-sm leading-5 text-violet-900">{drill}</p>
          <button
            onClick={onDrillClick}
            className="mt-2 rounded-full bg-violet-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-violet-700"
          >
            Start drill →
          </button>
        </div>
      )}

      {/* Next step */}
      {nextStep && !drill && (
        <p className="mt-3 text-xs font-medium text-zinc-600">{nextStep}</p>
      )}

      {/* Actions: feedback + copy/share */}
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-zinc-200 pt-3">
        <span className="text-xs font-semibold text-zinc-500">Was this helpful?</span>
        <button
          onClick={() => handleFeedback(true)}
          disabled={!!feedback || feedbackSubmitting}
          className={`rounded-full border px-3 py-1 text-xs font-bold transition ${
            feedback === "helpful"
              ? "border-emerald-300 bg-emerald-100 text-emerald-700"
              : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          }`}
        >
          {feedback === "helpful" ? "✓ Helpful" : "👍 Helpful"}
        </button>
        <button
          onClick={() => handleFeedback(false)}
          disabled={!!feedback || feedbackSubmitting}
          className={`rounded-full border px-3 py-1 text-xs font-bold transition ${
            feedback === "not_helpful"
              ? "border-amber-300 bg-amber-100 text-amber-700"
              : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          }`}
        >
          {feedback === "not_helpful" ? "✓ Not helpful" : "👎 Not helpful"}
        </button>
        {feedback && <span className="text-xs text-zinc-500">Thanks for your feedback!</span>}
        {feedbackSubmitting && <span className="text-xs text-zinc-400">sending…</span>}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            {copied ? "✓ Copied" : "⎘ Copy"}
          </button>
          <button
            onClick={handleShare}
            className="rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            ↗ Share
          </button>
        </div>
        {shareStatus && <span className="text-xs text-zinc-500">{shareStatus}</span>}
      </div>

      {/* Footer meta */}
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
        {spotHash && <span className="font-mono">spot {spotHash.slice(0, 12)}</span>}
        {drillSuggestion && <span>· drill: {drillSuggestion.type}</span>}
        {promptVersion && <span>· {promptVersion}</span>}
        {provider && <span>· {provider}</span>}
        {cacheHit !== undefined && <span>· {cacheHit ? "cached" : "fresh"}</span>}
        <span>· temp 0.3 · ToS post-hand only</span>
      </div>
    </div>
  );
}
