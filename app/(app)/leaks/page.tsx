"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { getMockAnalyzerOutput } from "@/lib/leaks/analyzer";
import type { LeakResult } from "@/lib/leaks/detectors";

function SeverityBadge({ severity }: { severity: string }) {
  const cls =
    severity === "high"
      ? "bg-red-100 text-red-700 border-red-200"
      : severity === "medium"
        ? "bg-amber-100 text-amber-800 border-amber-200"
        : "bg-zinc-100 text-zinc-600 border-zinc-200";
  return <span className={`rounded-full border px-2.5 py-0.5 text-xs font-bold ${cls}`}>{severity}</span>;
}

function FrequencyBar({ frequency, severity }: { frequency: string; severity: string }) {
  // Extract % from frequency string for bar width
  const match = frequency.match(/(\d+)%/);
  const pct = match ? parseInt(match[1], 10) : 50;
  const color = severity === "high" ? "bg-red-500" : severity === "medium" ? "bg-amber-500" : "bg-zinc-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full bg-zinc-200">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="font-mono text-xs">{frequency}</span>
    </div>
  );
}

export default function LeaksPage() {
  const [showAll, setShowAll] = useState(false);
  const data = useMemo(() => getMockAnalyzerOutput(), []);
  const leaks: LeakResult[] = data.leaks;
  const visible = showAll ? leaks : leaks.slice(0, 6);

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Leak Detector</h1>
          <p className="text-sm text-zinc-600">
            12 core leaks · ranked by EV loss · {data.handCount} hands analyzed · total {data.totalEvLossBBper100} bb/100 leak
          </p>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs">
          <span className="font-semibold">Worst leak:</span> {data.worstLeak ? `${data.worstLeak.subcategory} · -${data.worstLeak.evLossBBper100} bb/100` : "—"}
        </div>
      </div>

      {leaks.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-500">
          No leaks detected — nice! Play more hands to get a larger sample.
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Leak</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Frequency</th>
                  <th className="px-4 py-3">EV Loss</th>
                  <th className="px-4 py-3">Sample</th>
                  <th className="px-4 py-3">Drill</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {visible.map((l) => (
                  <tr key={l.leakId} className="hover:bg-zinc-50">
                    <td className="px-4 py-3 font-medium">{l.category}</td>
                    <td className="px-4 py-3">
                      <p className="font-semibold">{l.subcategory}</p>
                      <p className="text-xs text-zinc-500">{l.description}</p>
                      <p className="font-mono text-xs text-zinc-400">{l.gtoBenchmark}</p>
                    </td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={l.severity} />
                    </td>
                    <td className="px-4 py-3">
                      <FrequencyBar frequency={l.frequency} severity={l.severity} />
                    </td>
                    <td className="px-4 py-3 font-bold text-red-600">-{l.evLossBBper100.toFixed(1)} bb/100</td>
                    <td className="px-4 py-3 text-xs">{l.sampleSize}</td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/drills?leak=${l.leakId}`}
                        className="rounded-full bg-violet-600 px-3 py-1 text-xs font-bold text-white hover:bg-violet-700"
                      >
                        Drill →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {leaks.length > 6 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="rounded-full border border-zinc-300 bg-white px-4 py-1.5 text-xs font-semibold hover:bg-zinc-50"
            >
              {showAll ? "Show less" : `Show all ${leaks.length} leaks`}
            </button>
          )}

          <div className="grid gap-3 md:grid-cols-2">
            {visible.slice(0, 2).map((l) => (
              <div key={`card-${l.leakId}`} className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{l.category} · {l.subcategory}</p>
                  <SeverityBadge severity={l.severity} />
                </div>
                <p className="mt-2 text-sm font-bold">-{l.evLossBBper100} bb/100 · {l.frequency}</p>
                <p className="mt-1 text-xs text-zinc-600">{l.description} — {l.gtoBenchmark}</p>
                <div className="mt-2 flex gap-2">
                  <Link href={`/drills?leak=${l.leakId}`} className="rounded-full bg-emerald-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-emerald-700">
                    Drill this leak
                  </Link>
                  <Link href={`/coach`} className="rounded-full border border-zinc-300 bg-white px-4 py-1.5 text-xs font-semibold hover:bg-zinc-50">
                    Ask Coach
                  </Link>
                </div>
                {l.affectedHands.length > 0 && (
                  <p className="mt-2 font-mono text-xs text-zinc-400">Hands: {l.affectedHands.slice(0, 3).join(", ")}</p>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      <div className="rounded-lg bg-zinc-900 p-4 text-xs leading-5 text-zinc-300">
        <strong className="text-white">How it works:</strong> 12 detectors run on your last {data.handCount} hands. Each leak shows your frequency vs GTO, severity (low/medium/high by bb/100), and EV loss. Sorted by EV loss so you fix the biggest leak first. Click Drill to generate a 10-hand pack vs GTO bot.
      </div>
    </div>
  );
}
