import type { Metadata } from "next";
import RangeGrid from "@/components/replayer/RangeGrid";
import EmailCapture from "@/components/marketing/EmailCapture";

export const metadata: Metadata = {
  title: "Preflop Lab | AI Poker Lab",
  description:
    "Interactive 13x13 GTO preflop range grid — 169 hands, 6 positions, 4 stack depths. See raise/call/fold frequencies and EV. ToS-compliant training.",
};

export default function PreflopLabPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Preflop Lab</h1>
        <p className="text-sm text-zinc-600">
          169 hands · 6 positions · 4 stack depths · Pre-computed GTO (mock for MVP).
          Tap any hand for frequencies and EV.
        </p>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-4 md:p-6">
        <RangeGrid />
      </div>

      <EmailCapture variant="inline" source="app_preflop_lab" title="Get weekly GTO tips + leak fixes" description="Free preflop charts and strategy — no spam." />

      <div className="rounded-lg border border-zinc-200 bg-white p-4">
        <h3 className="text-sm font-semibold">How to use</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-600">
          <li>Pick a position and stack depth — grid updates instantly (pre-computed).</li>
          <li>Hover/tap a hand to see GTO raise/call/fold frequencies and EV in bb.</li>
          <li>Quiz yourself: &quot;What does GTO do with AJo UTG 100bb?&quot; — then check.</li>
          <li>Production: 12k preflop spots solved with TexasSolver, 0.5% exploitability.</li>
        </ul>
      </div>
    </div>
  );
}
