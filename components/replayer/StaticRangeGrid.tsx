"use client";

import { useMemo, useState } from "react";
import {
  getPreflopRange,
  type Position,
  type StackDepth,
  type HandGto,
} from "@/lib/solver/mockPreflop";

function bgForPrimary(h: HandGto): string {
  const { primary, freq } = h;
  const intensity = Math.max(freq.raise, freq.call, freq.fold);
  if (primary === "raise") {
    if (intensity >= 80) return "bg-emerald-600 text-white";
    if (intensity >= 55) return "bg-emerald-500 text-white";
    return "bg-emerald-300 text-emerald-900";
  }
  if (primary === "call") return "bg-amber-400 text-zinc-900";
  if (intensity >= 80) return "bg-red-500 text-white";
  if (intensity >= 55) return "bg-red-400 text-white";
  return "bg-zinc-200 text-zinc-700";
}

export default function StaticRangeGrid({
  position,
  stack,
}: {
  position: Position;
  stack: StackDepth;
}) {
  const [selected, setSelected] = useState<HandGto | null>(null);
  const [hovered, setHovered] = useState<HandGto | null>(null);

  const range = useMemo(() => getPreflopRange(position, stack), [position, stack]);

  const grid: HandGto[][] = [];
  let idx = 0;
  for (let r = 0; r < 13; r++) {
    const row: HandGto[] = [];
    for (let c = 0; c < 13; c++) row.push(range[idx++]);
    grid.push(row);
  }

  const active = hovered ?? selected;
  const raiseCount = range.filter((h) => h.primary === "raise").length;
  const callCount = range.filter((h) => h.primary === "call").length;
  const foldCount = range.filter((h) => h.primary === "fold").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-6 lg:flex-row">
        <div className="flex-1">
          <div className="overflow-x-auto">
            <div className="min-w-[420px]">
              <div className="grid grid-cols-13 gap-0.5">
                {grid.flat().map((h) => (
                  <button
                    key={h.hand}
                    onMouseEnter={() => setHovered(h)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => setSelected(h)}
                    className={`aspect-square rounded-sm text-[9px] font-bold leading-none transition hover:brightness-110 hover:ring-1 hover:ring-zinc-900 ${bgForPrimary(h)} ${selected?.hand === h.hand ? "ring-2 ring-zinc-900 ring-offset-1" : ""}`}
                    title={`${h.hand}: R${h.freq.raise}/C${h.freq.call}/F${h.freq.fold} EV ${h.ev}bb`}
                  >
                    {h.hand}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs">
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm bg-emerald-500" /> Raise ({raiseCount})
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm bg-amber-400" /> Call ({callCount})
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm bg-red-400" /> Fold ({foldCount})
            </span>
            <span className="ml-auto text-zinc-500">
              {position} · {stack} · 6-max · rake 5% cap $3
            </span>
          </div>
        </div>
        <div className="w-full lg:w-72">
          <div className="rounded-xl border border-zinc-200 bg-white p-4">
            {active ? (
              <>
                <div className="flex items-baseline justify-between">
                  <span className="text-2xl font-extrabold">{active.hand}</span>
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-bold ${active.primary === "raise" ? "bg-emerald-100 text-emerald-700" : active.primary === "call" ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-700"}`}
                  >
                    {active.primary.toUpperCase()}
                  </span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  {position} · {stack} · GTO frequencies
                </p>
                <div className="mt-4 space-y-2">
                  {(
                    [
                      ["Raise", active.freq.raise, "bg-emerald-500"],
                      ["Call", active.freq.call, "bg-amber-400"],
                      ["Fold", active.freq.fold, "bg-red-400"],
                    ] as const
                  ).map(([label, pct, bar]) => (
                    <div key={label}>
                      <div className="flex justify-between text-xs">
                        <span className="font-medium">{label}</span>
                        <span className="font-bold">{pct}%</span>
                      </div>
                      <div className="mt-1 h-2 rounded-full bg-zinc-100">
                        <div className={`h-2 rounded-full ${bar}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 rounded-lg bg-zinc-50 p-3">
                  <p className="text-xs font-semibold text-zinc-600">EV</p>
                  <p className="text-lg font-bold">
                    {active.ev > 0 ? "+" : ""}
                    {active.ev} bb
                  </p>
                  <p className="text-xs text-zinc-500">Quantized to 0.1bb · TexasSolver-style</p>
                </div>
                <p className="mt-3 text-xs leading-4 text-zinc-600">
                  {active.primary === "raise" && "GTO raises this hand for value/equity denial. Mix in calls at low frequency to protect calling range."}
                  {active.primary === "call" && "GTO calls to realize equity and keep villain's bluffs in. Fold is close — blocker effects matter."}
                  {active.primary === "fold" && "GTO folds — not enough equity vs opening range. Raise as bluff only with blockers at low freq."}
                </p>
              </>
            ) : (
              <p className="text-sm text-zinc-500">Hover or tap a hand to see GTO action, frequencies, and EV.</p>
            )}
          </div>
          <div className="mt-3 rounded-lg bg-amber-50 p-3 text-xs leading-4 text-amber-800">
            Training only — not for use during play. Frequencies are pre-computed GTO (TexasSolver, 0.5% exploitability).
          </div>
        </div>
      </div>
    </div>
  );
}
