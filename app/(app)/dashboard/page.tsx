import Link from "next/link";

export const metadata = { title: "Dashboard | AI Poker Lab" };

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight">Training & Solver Dashboard</h1>
            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
              distilled-v1 Active
            </span>
          </div>
          <p className="mt-1 text-sm text-zinc-600">
            Your personal GTO telemetry — 12-detector EV leak profile, IR-ranked drills, and hybrid solver status.
          </p>
        </div>
        <Link
          href="/methodology/accuracy"
          className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50"
        >
          18/18 Benchmarks Passed →
        </Link>
      </div>

      {/* Primary telemetry cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wide text-zinc-500">Priority Leak (12-Detector Scan)</p>
          <p className="mt-2 text-lg font-extrabold text-zinc-900">BB vs BTN — Over-Fold</p>
          <p className="mt-0.5 text-sm font-semibold text-red-600">-4.2 bb/100 · 68% fold (GTO 42%)</p>
          <Link
            href="/leaks"
            className="mt-3 inline-block text-xs font-bold text-emerald-700 hover:underline"
          >
            Inspect all 12 leaks →
          </Link>
        </div>
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wide text-zinc-500">IR Drill Queue (SM-2)</p>
          <p className="mt-2 text-3xl font-extrabold text-zinc-900">5</p>
          <p className="mt-0.5 text-sm text-zinc-600">Ranked by TF-IDF + EV-loss severity</p>
          <Link
            href="/drills"
            className="mt-3 inline-block text-xs font-bold text-emerald-700 hover:underline"
          >
            Launch drill pack →
          </Link>
        </div>
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wide text-zinc-500">Hands Analyzed</p>
          <p className="mt-2 text-3xl font-extrabold text-zinc-900">127</p>
          <p className="mt-0.5 text-sm text-zinc-600">Street-by-street EV & NashConv</p>
          <Link
            href="/replayer"
            className="mt-3 inline-block text-xs font-bold text-emerald-700 hover:underline"
          >
            Open Hand Replayer →
          </Link>
        </div>
      </div>

      {/* Solver & Neural Value Net Telemetry Panel */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5 text-zinc-100 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-3">
          <div>
            <span className="font-mono text-xs font-bold text-emerald-400">
              3-TIER SOLVER ENGINE · engine/noregrets + value_net_torch.py + showdown_solver.py
            </span>
            <p className="mt-0.5 text-xs text-zinc-400">
              Architected by Daniel Sawa · Native Rust 6-Max/HU Linear MCCFR, PyTorch ReBeL Value Net (VN01) &
              Vectorized CFR+
            </p>
          </div>
          <Link
            href="/methodology"
            className="rounded-full bg-zinc-800 px-3 py-1 text-xs font-semibold text-emerald-400 hover:bg-zinc-700"
          >
            Architecture & Benchmarks →
          </Link>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 font-mono text-xs md:grid-cols-4">
          <div className="rounded-xl bg-zinc-800/80 p-3">
            <div className="text-zinc-400">Blueprint Infosets</div>
            <div className="mt-1 text-base font-bold text-white">15,956,290+</div>
            <div className="mt-0.5 text-[11px] text-emerald-400">OCHS L1/EMD + VR-MCCFR</div>
          </div>
          <div className="rounded-xl bg-zinc-800/80 p-3">
            <div className="text-zinc-400">Turn/River BR Probe</div>
            <div className="mt-1 text-base font-bold text-white">304.0 BB/100</div>
            <div className="mt-0.5 text-[11px] text-emerald-400">-42.5% vs baseline</div>
          </div>
          <div className="rounded-xl bg-zinc-800/80 p-3">
            <div className="text-zinc-400">Burch Safe-Resolve</div>
            <div className="mt-1 text-base font-bold text-white">1.7 chips mean</div>
            <div className="mt-0.5 text-[11px] text-emerald-400">-86.5% max combo exploit</div>
          </div>
          <div className="rounded-xl bg-zinc-800/80 p-3">
            <div className="text-zinc-400">O(1) spotHash Cache</div>
            <div className="mt-1 text-base font-bold text-white">{"<50ms"} p95</div>
            <div className="mt-0.5 text-[11px] text-emerald-400">100% (18/18) validated</div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2">
        <Link
          href="/lab/preflop"
          className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 transition hover:border-emerald-300 hover:bg-emerald-100/70"
        >
          <h3 className="text-base font-bold text-zinc-900">Interactive Preflop Lab</h3>
          <p className="mt-1 text-sm text-zinc-700">
            Browse 169 hands × 6 positions × 4 stack depths with equilibrium frequencies and EV in bb.
          </p>
          <span className="mt-3 inline-block text-sm font-bold text-emerald-700">Open Preflop Grid →</span>
        </Link>
        <Link
          href="/replayer"
          className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition hover:border-zinc-300 hover:bg-zinc-50"
        >
          <h3 className="text-base font-bold text-zinc-900">Hand Replayer + Subgame Check</h3>
          <p className="mt-1 text-sm text-zinc-600">
            Paste a PokerStars or GGPoker hand history to inspect street-by-street EV loss and AI Coach analysis.
          </p>
          <span className="mt-3 inline-block text-sm font-bold text-zinc-900">Analyze Hand →</span>
        </Link>
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-800">
        <strong>ToS Compliance:</strong> Training and post-hand research tool only — never use during live play.
      </div>
    </div>
  );
}
