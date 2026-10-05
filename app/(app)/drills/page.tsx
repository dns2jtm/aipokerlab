"use client";

import dynamic from "next/dynamic";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { DrillPack } from "@/lib/drills/engine";
import type { LeakResult } from "@/lib/leaks/detectors";

const DrillPlayer = dynamic(() => import("@/components/drills/DrillPlayer"), {
  loading: () => (
    <div className="animate-pulse space-y-3">
      <div className="h-4 w-32 rounded bg-zinc-200" />
      <div className="h-2 w-full rounded-full bg-zinc-100" />
      <div className="h-40 rounded-xl bg-zinc-100" />
      <div className="flex gap-2">
        <div className="h-8 w-20 rounded-full bg-zinc-200" />
        <div className="h-8 w-20 rounded-full bg-zinc-200" />
        <div className="h-8 w-20 rounded-full bg-zinc-200" />
      </div>
    </div>
  ),
});

function DrillsInner() {
  const searchParams = useSearchParams();
  const leakParam = searchParams.get("leak");

  const [leaks, setLeaks] = useState<LeakResult[]>([]);
  const [drills, setDrills] = useState<DrillPack[]>([]);
  const [activeDrill, setActiveDrill] = useState<DrillPack | null>(null);
  const [loading, setLoading] = useState(false);
  const [filterLeak, setFilterLeak] = useState<string | null>(leakParam);

  useEffect(() => {
    fetch("/api/drills")
      .then((r) => r.json())
      .then((j) => {
        if (j.leaks) setLeaks(j.leaks);
        if (j.drills) setDrills(j.drills);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (leakParam) setFilterLeak(leakParam);
  }, [leakParam]);

  async function generate(leakId: string) {
    setLoading(true);
    try {
      const res = await fetch("/api/drills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leakId, count: 10 }),
      });
      const json = await res.json();
      if (json.drill) {
        setDrills((prev) => [json.drill, ...prev]);
        setActiveDrill(json.drill);
      }
    } finally {
      setLoading(false);
    }
  }

  const filteredDrills = filterLeak ? drills.filter((d) => d.leakId === filterLeak) : drills;

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Drills — Leak-to-Drill</h1>
        <p className="text-sm text-zinc-600">Auto-generated from your worst leak · spaced repetition · vs GTO bot · XP scored.</p>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Generate drill pack by leak</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {leaks.slice(0, 8).map((l) => (
            <button
              key={l.leakId}
              onClick={() => generate(l.leakId)}
              disabled={loading}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${filterLeak === l.leakId ? "border-violet-600 bg-violet-600 text-white" : "border-zinc-300 bg-white hover:bg-zinc-50"} disabled:opacity-50`}
            >
              {l.subcategory} · -{l.evLossBBper100}bb/100
            </button>
          ))}
        </div>
        <div className="mt-2 flex gap-2 text-xs">
          <button onClick={() => setFilterLeak(null)} className={`rounded-full px-3 py-1 ${!filterLeak ? "bg-zinc-900 text-white" : "bg-zinc-100"}`}>All drills</button>
          {filterLeak && <span className="self-center text-zinc-500">Filtered: {filterLeak}</span>}
        </div>
      </div>

      {activeDrill && (
        <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold">Now drilling: {activeDrill.leakLabel} · {activeDrill.hands.length} hands · {activeDrill.category}</h3>
            <button onClick={() => setActiveDrill(null)} className="rounded-full border border-zinc-300 bg-white px-3 py-1 text-xs">Close</button>
          </div>
          <div className="mt-3">
            <DrillPlayer hands={activeDrill.hands} drillId={activeDrill.id} />
          </div>
        </div>
      )}

      {filteredDrills.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center">
          <p className="text-sm font-semibold">No drills yet</p>
          <p className="mt-1 text-xs text-zinc-500">Pick a leak above to generate a 10-hand pack vs GTO bot. Each hand shows GTO frequencies and EV after you act.</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {filteredDrills.map((d) => (
            <div key={d.id} className="rounded-xl border border-zinc-200 bg-white p-5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{d.category} · {d.leakLabel}</p>
                <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-bold text-violet-700">{d.hands.length} hands</span>
              </div>
              <p className="mt-2 text-sm font-semibold">{d.hands[0]?.heroCards} on {d.hands[0]?.board || "preflop"} — {d.hands[0]?.villainAction}</p>
              <p className="mt-1 text-xs text-zinc-600">GTO: {d.hands[0]?.gtoPrimary} · {d.hands[0]?.gtoFreq.raise}/{d.hands[0]?.gtoFreq.call}/{d.hands[0]?.gtoFreq.fold} · +{d.xpReward} XP</p>
              <div className="mt-3 flex gap-2">
                <button onClick={() => setActiveDrill(d)} className="rounded-full bg-violet-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-violet-700">Play →</button>
                <span className="self-center text-xs text-zinc-500">Due now · spaced repetition</span>
              </div>
              <div className="mt-2 h-1 rounded-full bg-zinc-100">
                <div className="h-1 rounded-full bg-violet-500" style={{ width: "0%" }} />
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800">Training only — not for use during play. Spaced repetition: miss → due now, 60%+ → tomorrow, 80%+ → in 3 days.</div>
    </div>
  );
}

export default function DrillsPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-5xl p-8 text-sm text-zinc-500">Loading drills…</div>}>
      <DrillsInner />
    </Suspense>
  );
}
