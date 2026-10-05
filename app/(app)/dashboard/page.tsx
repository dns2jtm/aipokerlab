import Link from "next/link";

export const metadata = { title: "Dashboard | AI Poker Lab" };

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-zinc-600">
          Your Lab overview — leaks, drills, and recent hands.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-200 bg-white p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Worst Leak
          </p>
          <p className="mt-2 text-lg font-bold">BB vs BTN — over-fold</p>
          <p className="text-sm text-red-600">-4.2 bb/100 · 68% fold (GTO 42%)</p>
          <Link
            href="/leaks"
            className="mt-3 inline-block text-xs font-semibold text-emerald-600 hover:underline"
          >
            View leaks →
          </Link>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Drills Due
          </p>
          <p className="mt-2 text-3xl font-bold">5</p>
          <p className="text-sm text-zinc-600">Spaced repetition queue</p>
          <Link
            href="/drills"
            className="mt-3 inline-block text-xs font-semibold text-emerald-600 hover:underline"
          >
            Start drills →
          </Link>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Hands Reviewed
          </p>
          <p className="mt-2 text-3xl font-bold">127</p>
          <p className="text-sm text-zinc-600">Last 30 days</p>
          <Link
            href="/replayer"
            className="mt-3 inline-block text-xs font-semibold text-emerald-600 hover:underline"
          >
            Open Replayer →
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Link
          href="/lab/preflop"
          className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 hover:bg-emerald-100"
        >
          <h3 className="font-semibold">Preflop Lab</h3>
          <p className="mt-1 text-sm text-zinc-700">
            Browse 169 hands × 6 positions × 4 stack depths. Quiz yourself.
          </p>
          <span className="mt-3 inline-block text-sm font-bold text-emerald-700">
            Open →
          </span>
        </Link>
        <Link
          href="/replayer"
          className="rounded-xl border border-zinc-200 bg-white p-6 hover:bg-zinc-50"
        >
          <h3 className="font-semibold">Hand Replayer + GTO Check</h3>
          <p className="mt-1 text-sm text-zinc-600">
            Paste a hand history, see EV loss per street, get AI coaching.
          </p>
          <span className="mt-3 inline-block text-sm font-bold text-zinc-900">
            Paste hand →
          </span>
        </Link>
      </div>

      <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
        Training tool only — not for use during play. Compliant with PokerStars /
        GGPoker ToS.
      </div>
    </div>
  );
}
