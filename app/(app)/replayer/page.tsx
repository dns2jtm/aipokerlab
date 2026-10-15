import type { Metadata } from "next";
import dynamic from "next/dynamic";

const HandReplayer = dynamic(() => import("@/components/replayer/HandReplayer"), {
  loading: () => (
    <div className="animate-pulse space-y-4">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="h-4 w-32 rounded bg-zinc-200" />
          <div className="h-48 rounded-xl bg-zinc-100" />
          <div className="h-10 w-40 rounded-full bg-zinc-200" />
        </div>
        <div className="space-y-3">
          <div className="h-4 w-32 rounded bg-zinc-200" />
          <div className="h-32 rounded-xl bg-zinc-100" />
          <div className="h-32 rounded-xl bg-zinc-100" />
        </div>
      </div>
    </div>
  ),
});

export const metadata: Metadata = {
  title: "Hand Replayer | AI Poker Lab",
  description:
    "Paste hand history, see street-by-street GTO evaluation with EV loss, and get AI coaching. ToS-compliant post-hand study.",
};

export default function ReplayerPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Hand Replayer + Subgame GTO Check</h1>
        <p className="text-sm text-zinc-600">
          Paste a PokerStars or GGPoker hand history — inspect parsed streets, hybrid GTO equilibrium frequencies, EV loss per street, and solver-grounded AI coaching.
        </p>
      </div>
      <div className="rounded-xl border border-zinc-200 bg-white p-4 md:p-6">
        <HandReplayer />
      </div>
    </div>
  );
}
