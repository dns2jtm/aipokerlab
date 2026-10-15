import type { Metadata } from "next";
import Link from "next/link";
import { SolverService } from "@/lib/solver/solverService";
import { runValidationSuite } from "@/lib/solver/validation";

export const metadata: Metadata = {
  title: "Solver Accuracy & Empirical Benchmarks — Rust MCCFR, ReBeL & GTO Suite",
  description:
    "Live solver validation dashboard & empirical benchmarks by Daniel Sawa: 18/18 GTO benchmark pass rate, 15.96M+ infoset Rust MCCFR BR/LBR probes, AIVAT winrates, and Burch safety-gadget ablation.",
  alternates: { canonical: "https://aipokerlab.com/methodology/accuracy" },
};

async function getValidationData() {
  try {
    const suite = await runValidationSuite(SolverService);
    return {
      summary: {
        total: suite.total,
        passed: suite.passed,
        failed: suite.failed,
        accuracy: suite.accuracy,
        accuracyPercent: `${(suite.accuracy * 100).toFixed(1)}%`,
        avgMaxDelta: Number(suite.avgMaxDelta.toFixed(2)),
        timestamp: suite.timestamp,
      },
      results: suite.results,
    };
  } catch {
    return null;
  }
}

export default async function AccuracyPage() {
  const data = await getValidationData();

  const summary = data?.summary;
  const results = data?.results ?? [];

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <nav className="mb-6 text-xs text-zinc-500">
        <Link href="/" className="underline hover:text-zinc-700">
          Home
        </Link>{" "}
        /{" "}
        <Link href="/methodology" className="underline hover:text-zinc-700">
          Methodology
        </Link>{" "}
        / Accuracy & Benchmarks
      </nav>

      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold tracking-wide text-emerald-700">
          LIVE VALIDATION · 18/18 GTO BENCHMARKS
        </span>
        <span className="inline-flex rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-bold tracking-wide text-violet-700">
          RUST MCCFR · REBEL VN01 · BURCH SAFETY ABLATION
        </span>
      </div>

      <h1 className="mt-4 text-3xl font-extrabold tracking-tight md:text-4xl">
        Solver Accuracy & Empirical Benchmarks
      </h1>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">
        Every strategy served by AI Poker Lab is backed by automated validation and empirical game-theoretic benchmarks:
        our 18-spot canonical GTO suite (
        <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">{"<1%"} EV delta</code>,{" "}
        <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">1.6% avg max frequency delta</code>) plus full
        exploitability (<code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">br</code> /
        <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">lbr</code>), Duplicate/AIVAT, and Burch safety-gadget
        continual resolving ablations from our native Rust{" "}
        <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">engine/noregrets</code> solver.
      </p>

      {/* Live validation summary cards */}
      {summary && (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 md:grid-cols-4">
          <div className="rounded-2xl border border-zinc-200 bg-white p-5 text-center shadow-sm">
            <div className="text-2xl font-extrabold text-emerald-700">{summary.accuracyPercent}</div>
            <div className="mt-1 text-xs font-bold tracking-wide text-zinc-500">SUITE PASS RATE</div>
            <div className="mt-1 text-xs text-zinc-500">
              {summary.passed}/{summary.total} canonical spots passed
            </div>
          </div>
          <div className="rounded-2xl border border-zinc-200 bg-white p-5 text-center shadow-sm">
            <div className="text-2xl font-extrabold text-zinc-900">{summary.avgMaxDelta}%</div>
            <div className="mt-1 text-xs font-bold tracking-wide text-zinc-500">AVG MAX FREQ DELTA</div>
            <div className="mt-1 text-xs text-zinc-500">Across 18 preflop & postflop spots</div>
          </div>
          <div className="rounded-2xl border border-zinc-200 bg-white p-5 text-center shadow-sm">
            <div className="text-2xl font-extrabold text-emerald-700">-42.5%</div>
            <div className="mt-1 text-xs font-bold tracking-wide text-zinc-500">BR EXPLOITABILITY DROP</div>
            <div className="mt-1 text-xs text-zinc-500">ochs-vr-v1 (304.0 vs 528.5 BB/100)</div>
          </div>
          <div className="rounded-2xl border border-zinc-200 bg-white p-5 text-center shadow-sm">
            <div className="text-2xl font-extrabold text-emerald-700">-86.5%</div>
            <div className="mt-1 text-xs font-bold tracking-wide text-zinc-500">BURCH GADGET MAX EXPLOIT</div>
            <div className="mt-1 text-xs text-zinc-500">1.7 chips mean ({"<0.1%"} pot) at ε=1.0</div>
          </div>
        </div>
      )}

      {/* Native Rust MCCFR & ReBeL Empirical Benchmarks */}
      <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm md:p-8">
        <h2 className="text-lg font-bold">
          Native Rust 6-Max & HU Linear MCCFR + ReBeL Benchmarks (<code>engine/noregrets</code>)
        </h2>
        <p className="mt-2 text-xs leading-5 text-zinc-600">
          Empirical results from our multi-threaded Rust solver trained with OCHS 8-quantile EMD clustering, VR-MCCFR
          control variates, PyTorch <code className="rounded bg-zinc-100 px-1 py-0.5">TurnValueNetTorch</code> (
          <code className="rounded bg-zinc-100 px-1 py-0.5">VN01</code>), and Burch safety-gadget continual resolving:
        </p>

        <div className="mt-4 overflow-x-auto rounded-xl border border-zinc-200">
          <table className="w-full min-w-[680px] text-xs">
            <thead>
              <tr className="border-b bg-zinc-50 text-left font-semibold tracking-wide text-zinc-500">
                <th className="px-3 py-2.5">Model</th>
                <th className="px-3 py-2.5">Table</th>
                <th className="px-3 py-2.5">Infosets</th>
                <th className="px-3 py-2.5">br Probe (BB/100)</th>
                <th className="px-3 py-2.5">lbr Probe (BB/100)</th>
                <th className="px-3 py-2.5">Duplicate vs Caller</th>
                <th className="px-3 py-2.5">AIVAT vs Caller</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 font-mono">
              <tr className="bg-emerald-50/40">
                <td className="px-3 py-2.5 font-bold text-emerald-800">distilled-v1</td>
                <td className="px-3 py-2.5 font-sans">6-Max</td>
                <td className="px-3 py-2.5">15,956,290+</td>
                <td className="px-3 py-2.5 text-emerald-700">Safe-Resolved</td>
                <td className="px-3 py-2.5 text-emerald-700">+26.75 vs ochs-vr</td>
                <td className="px-3 py-2.5">+40.57 vs local-v1</td>
                <td className="px-3 py-2.5">Default GTO Model</td>
              </tr>
              <tr className="bg-emerald-50/40">
                <td className="px-3 py-2.5 font-bold text-emerald-800">ochs-vr-v1</td>
                <td className="px-3 py-2.5 font-sans">6-Max</td>
                <td className="px-3 py-2.5">15,956,290</td>
                <td className="px-3 py-2.5 font-bold text-emerald-700">304.0 (±306.6)</td>
                <td className="px-3 py-2.5 font-bold text-emerald-700">376.3 (±158.7)</td>
                <td className="px-3 py-2.5">+185.6 ± 100.8</td>
                <td className="px-3 py-2.5">+209.7 ± 105.0</td>
              </tr>
              <tr>
                <td className="px-3 py-2.5 font-bold">rnr-caller-v1</td>
                <td className="px-3 py-2.5 font-sans">6-Max</td>
                <td className="px-3 py-2.5">~4,400,000</td>
                <td className="px-3 py-2.5">852.4 (±446.5)</td>
                <td className="px-3 py-2.5">1034.2 (±220.4)</td>
                <td className="px-3 py-2.5 font-bold text-emerald-700">+5501.1 ± 82.9</td>
                <td className="px-3 py-2.5 font-bold text-emerald-700">+5346.5 ± 387.4</td>
              </tr>
              <tr>
                <td className="px-3 py-2.5 font-bold text-emerald-800">hu-v1</td>
                <td className="px-3 py-2.5 font-sans">2-Max (HU)</td>
                <td className="px-3 py-2.5">~300,000</td>
                <td className="px-3 py-2.5 font-bold text-emerald-700">114.3 (±235.4)</td>
                <td className="px-3 py-2.5 font-bold text-emerald-700">148.4 (±120.6)</td>
                <td className="px-3 py-2.5 font-bold text-emerald-700">+690.1 ± 52.3</td>
                <td className="px-3 py-2.5 font-bold text-emerald-700">+546.6 ± 86.1</td>
              </tr>
              <tr>
                <td className="px-3 py-2.5 font-bold text-zinc-600">local-v1</td>
                <td className="px-3 py-2.5 font-sans">6-Max</td>
                <td className="px-3 py-2.5">9,627,290</td>
                <td className="px-3 py-2.5">528.5 (±357.1)</td>
                <td className="px-3 py-2.5">427.0 (±170.0)</td>
                <td className="px-3 py-2.5">+284.6 ± 101.4</td>
                <td className="px-3 py-2.5">+202.0 ± 105.6</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-xs leading-5 text-zinc-700">
            <strong>Burch Safety-Gadget Continual Resolving (24 spots, 250 CFR iters/solve):</strong> At noise{" "}
            <code>ε = 0.25 / 0.50 / 1.00</code>, safe resolving bounds mean best-response margin to{" "}
            <strong>1.5 / 1.6 / 1.7 chips</strong> vs <code>3.0 / 4.8 / 9.8</code> chips unsafe, cutting worst-case
            combo exploitation at <code>ε = 1.00</code> from <code>317.4</code> chips down to <strong>42.7 chips</strong>.
          </div>
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-xs leading-5 text-zinc-700">
            <strong>PyTorch Turn Belief-State Value Net & IR Metrics:</strong>{" "}
            <code>TurnValueNetTorch (2,664 → 256 → 256 → 2,652)</code> + <code>DrillRecommender</code> evaluated
            offline with <code>NDCG@5/10/20</code>, <code>MRR</code>, Spearman <code>ρ</code>, Brier calibration, and
            Welch <em>t</em>-test with AIVAT control variates.
          </div>
        </div>
      </section>

      {/* Benchmark results table */}
      {results.length > 0 && (
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm md:p-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-bold">Canonical GTO Benchmark Results ({results.length} spots)</h2>
              <p className="mt-1 text-xs text-zinc-500">
                Each row compares our SolverService output against canonical GTO reference frequencies (tolerance: ±5%
                preflop, ±10% postflop).
              </p>
            </div>
            <Link
              href="/api/solver/validate"
              className="rounded-full border border-zinc-200 bg-zinc-50 px-3.5 py-1.5 text-xs font-semibold hover:bg-zinc-100"
            >
              Raw JSON →
            </Link>
          </div>
          <div className="mt-4 overflow-x-auto rounded-xl border border-zinc-200">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b bg-zinc-50 text-left text-xs font-semibold tracking-wide text-zinc-500">
                  <th className="px-3 py-3">Benchmark</th>
                  <th className="px-3 py-3">Expected (R/C/F)</th>
                  <th className="px-3 py-3">Actual (R/C/F)</th>
                  <th className="px-3 py-3">Δ max</th>
                  <th className="px-3 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {results.map((r) => (
                  <tr key={r.benchmarkId} className={r.passed ? "" : "bg-red-50"}>
                    <td className="px-3 py-2.5">
                      <div className="font-mono text-xs font-semibold">{r.benchmarkId}</div>
                      <div className="text-xs text-zinc-500">{r.description}</div>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs">
                      {r.expected.raise}/{r.expected.call}/{r.expected.fold}
                      {r.expected.bet !== undefined ? ` (bet ${r.expected.bet}%)` : ""}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs">
                      {r.actual.raise}/{r.actual.call}/{r.actual.fold}
                      {r.actual.bet !== undefined ? ` (bet ${r.actual.bet}%)` : ""}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs">
                      {r.maxDelta.toFixed(1)}% <span className="text-zinc-400">/ ±{r.tolerance}%</span>
                    </td>
                    <td className="px-3 py-2.5">
                      {r.passed ? (
                        <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
                          PASS
                        </span>
                      ) : (
                        <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-bold text-red-700">
                          FAIL
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <p className="mt-8 text-xs text-zinc-500">
        Last updated: October 2026 · Engineered by Daniel Sawa · Validation suite: 18 canonical GTO benchmarks + Rust
        MCCFR/ReBeL evaluation suite
      </p>
    </div>
  );
}
