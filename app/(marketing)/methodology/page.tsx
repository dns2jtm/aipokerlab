import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Methodology — 3-Tier Solver Architecture, ReBeL Value Net & Benchmarks",
  description:
    "Transparent methodology by Daniel Sawa: Native Rust 6-Max/HU Linear MCCFR (15.96M+ infosets, VR-MCCFR, OCHS), PyTorch ReBeL turn belief-state value net (VN01), Burch safety-gadget continual resolving, and Python CFR+.",
  alternates: { canonical: "https://aipokerlab.com/methodology" },
  openGraph: {
    title: "Methodology & Empirical Benchmarks — AI Poker Lab",
    description:
      "15.96M+ infoset Rust Linear MCCFR, PyTorch ReBeL belief-state value networks, Burch safety-gadget continual resolving (-86.5% max exploit), and AIVAT benchmarks.",
    url: "https://aipokerlab.com/methodology",
    type: "article",
  },
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: "https://aipokerlab.com/" },
    { "@type": "ListItem", position: 2, name: "Methodology", item: "https://aipokerlab.com/methodology" },
  ],
};

const techArticleJsonLd = {
  "@context": "https://schema.org",
  "@type": "TechArticle",
  headline: "AI Poker Lab 3-Tier Solver Architecture, PyTorch ReBeL Value Network & Empirical Benchmarks",
  description:
    "Technical architecture and empirical validation of AI Poker Lab's Rust 6-Max/HU Linear MCCFR solver, PyTorch belief-state value network, Burch safety-gadget continual resolving, and IR drill engine.",
  author: [
    {
      "@type": "Person",
      name: "Daniel Sawa",
      jobTitle: "Founder & Lead Systems / ML Engineer",
      url: "https://github.com/dns2jtm",
    },
  ],
  publisher: { "@type": "Organization", name: "AI Poker Lab", url: "https://aipokerlab.com" },
  datePublished: "2025-10-01",
  dateModified: "2026-10-15",
};

export default function MethodologyPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(techArticleJsonLd) }} />

      <div className="mx-auto max-w-5xl px-6 py-12">
        <nav className="mb-6 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">
            Home
          </Link>{" "}
          / Methodology
        </nav>

        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold tracking-wide text-emerald-700">
            3-TIER SOLVER & ML ARCHITECTURE
          </span>
          <span className="inline-flex rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-bold tracking-wide text-violet-700">
            15.96M+ INFOSETS · REBEL VN01 · BURCH SAFETY GADGET
          </span>
        </div>

        <h1 className="mt-4 text-3xl font-extrabold tracking-tight md:text-4xl">
          Solver Architecture, Neural Value Networks & Benchmarks
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">
          No black boxes. Every frequency, counterfactual EV delta, and coaching recommendation is backed by verifiable
          game-theoretic algorithms and reproducible benchmarks. Below is the complete engineering specification of AI
          Poker Lab.
        </p>
        <p className="mt-2 text-xs text-zinc-500">
          Architected & authored by <strong>Daniel Sawa</strong> (Founder & Lead Systems / ML Engineer · BSc
          Computer Science, University of York) · Updated October 2026
        </p>

        {/* Top telemetry summary bar */}
        <div className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { k: "15.96M+", label: "6-Max MCCFR Infosets", sub: "ochs-vr-v1 & distilled-v1" },
            { k: "-42.5%", label: "BR Exploitability Drop", sub: "304.0 vs 528.5 BB/100" },
            { k: "1.7 chips", label: "Safe Resolve BR Margin", sub: "<0.1% pot at ε=1.0 noise" },
            { k: "100% (18/18)", label: "Canonical Validation", sub: "<50ms O(1) spotHash cache" },
          ].map((m) => (
            <div key={m.label} className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
              <div className="text-xl font-extrabold text-emerald-700 md:text-2xl">{m.k}</div>
              <div className="mt-1 text-xs font-bold text-zinc-900">{m.label}</div>
              <div className="mt-0.5 text-[11px] text-zinc-500">{m.sub}</div>
            </div>
          ))}
        </div>

        {/* Section 1: 3-Tier Solver & ML Architecture */}
        <section className="mt-10 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm md:p-8">
          <h2 className="text-xl font-bold">1. Three-Tier Solver & ML Architecture</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            AI Poker Lab combines three complementary solving and inference layers behind a unified{" "}
            <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">SolverService</code> and persistent JSON-stdio
            worker bridge:
          </p>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-5">
              <div className="text-xs font-bold tracking-wide text-emerald-800">TIER 1 · NATIVE RUST ENGINE</div>
              <h3 className="mt-1 text-sm font-bold text-zinc-900">
                6-Max & HU Linear MCCFR + ReBeL Resolver (<code className="text-xs">engine/noregrets</code>)
              </h3>
              <ul className="mt-3 list-disc space-y-1.5 pl-4 text-xs leading-5 text-zinc-700">
                <li>
                  <strong>Parallel Linear MCCFR</strong> (<code className="text-[11px]">Rayon</code>,{" "}
                  <code className="text-[11px]">DashMap</code>, <code className="text-[11px]">mimalloc</code>) with
                  Pluribus negative-regret pruning across <strong>15.96M+ infosets</strong>.
                </li>
                <li>
                  <strong>OCHS Abstraction:</strong> Opponent-Cluster Hand Strength + 8-quantile future-equity
                  distributions clustered via L1 / Earth Mover's Distance k-medians.
                </li>
                <li>
                  <strong>VR-MCCFR:</strong> Schmid et al. (2019) control-variate baselines + 18-snapshot postflop
                  averaging + multiway importance sampling (<code className="text-[11px]">--multiway-focus 0.15</code>).
                </li>
                <li>
                  <strong>Online Subgame Resolving:</strong> Bayesian <code className="text-[11px]">RangeTracker</code>,
                  ReBeL depth-limited flop solving (<code className="text-[11px]">flop.rs</code>), and{" "}
                  <strong>Burch safety-gadget continual resolving</strong> (<code className="text-[11px]">turn.rs</code>
                  , <code className="text-[11px]">river.rs</code>) via a warm <code className="text-[11px]">--stdio</code>{" "}
                  worker.
                </li>
              </ul>
            </div>

            <div className="rounded-xl border border-violet-200 bg-violet-50/60 p-5">
              <div className="text-xs font-bold tracking-wide text-violet-800">TIER 2 · PYTORCH NEURAL & IR</div>
              <h3 className="mt-1 text-sm font-bold text-zinc-900">
                ReBeL Belief-State Value Net & IR Engine (<code className="text-xs">value_net_torch.py</code>)
              </h3>
              <ul className="mt-3 list-disc space-y-1.5 pl-4 text-xs leading-5 text-zinc-700">
                <li>
                  <strong>TurnValueNetTorch:</strong> PyTorch MLP (<code className="text-[11px]">2,664 → 256 → 256 → 2,652</code>)
                  mapping board multi-hot, pot/stack scalars, and <code className="text-[11px]">2 × 1,326</code>{" "}
                  Bayesian belief states to 2,652 counterfactual values.
                </li>
                <li>
                  <strong>Training & Binary Export:</strong> <code className="text-[11px]">AdamW</code>, cosine
                  annealing, range-weighted Huber/MSE loss, exported directly to Rust binary{" "}
                  <code className="text-[11px]">VN01</code> (<code className="text-[11px]">value_net.bin</code>).
                </li>
                <li>
                  <strong>Offline IR Evaluation:</strong> <code className="text-[11px]">NDCG@5/10/20</code>,{" "}
                  <code className="text-[11px]">MRR</code>, Spearman <code className="text-[11px]">ρ</code>, Brier
                  calibration, and top-decile EV hit rate.
                </li>
                <li>
                  <strong>DrillRecommender & A/B Testing:</strong> Hybrid token + 3-gram TF-IDF + EV-loss severity
                  recommender + <code className="text-[11px]">ab_policy_test</code> with AIVAT control variates.
                </li>
              </ul>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-5">
              <div className="text-xs font-bold tracking-wide text-zinc-700">TIER 3 · SUBGAME CFR+ & CACHE</div>
              <h3 className="mt-1 text-sm font-bold text-zinc-900">
                Vectorized NumPy CFR+ & O(1) <code className="text-xs">spotHash</code> DB
              </h3>
              <ul className="mt-3 list-disc space-y-1.5 pl-4 text-xs leading-5 text-zinc-700">
                <li>
                  <strong>O(1) Pre-Computed Cache:</strong> Deterministic <code className="text-[11px]">spotHash</code>{" "}
                  over <code className="text-[11px]">board + ranges + stack + pot + betSizings + rake</code> serving
                  pre-solved spots in <strong>{"<50ms"} p95</strong>.
                </li>
                <li>
                  <strong>Fast Vectorized CFR+ (<code className="text-[11px]">showdown_solver.py</code>):</strong>{" "}
                  Multi-sizing (<code className="text-[11px]">33%</code>, <code className="text-[11px]">66%</code>,{" "}
                  <code className="text-[11px]">100%</code> pot) with opponent reraise branches and IP/OOP equity
                  realization matrices.
                </li>
                <li>
                  <strong>Exact NashConv Telemetry:</strong> Reports exact two-player{" "}
                  <code className="text-[11px]">solver_gap_chips</code> (sum of both players' best-response
                  improvements) on every restricted solve.
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-6 rounded-xl bg-zinc-900 p-4 text-xs leading-5 text-zinc-100">
            <div className="font-mono text-[11px] tracking-wide text-emerald-400">SOLVE & RESOLVE PIPELINE</div>
            <div className="mt-1 font-mono">
              Client → /api/solve (spotHash) → Redis / PrecomputedDB O(1) Hit ({"<50ms"}) → Miss / Deep Review:
              RangeTracker Bayesian Update → Rust ReBeL + Burch Gadget Safe-Resolve (blueprint.bin + value_net.bin) /
              Vectorized CFR+ (solver_gap_chips)
            </div>
          </div>
        </section>

        {/* Section 2: Trained Blueprint Models & Exploitability Probes */}
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm md:p-8">
          <h2 className="text-xl font-bold">2. Trained Blueprint Models & Exploitability Lower-Bound Probes</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            We train multiple 6-Max and Heads-Up blueprint profiles in{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">engine/noregrets</code> and evaluate them using
            exact turn/river expectimax best-response probes (<code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">br</code>)
            and Local Best Response (<code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">lbr</code>).
          </p>

          <h3 className="mt-6 text-sm font-bold text-zinc-900">Trained Blueprint Models Summary</h3>
          <div className="mt-3 overflow-x-auto rounded-xl border border-zinc-200">
            <table className="w-full min-w-[680px] text-sm">
              <thead>
                <tr className="border-b bg-zinc-50 text-left text-xs font-semibold tracking-wide text-zinc-500">
                  <th className="px-4 py-3">Model</th>
                  <th className="px-4 py-3">Table</th>
                  <th className="px-4 py-3">Profile & Algorithms</th>
                  <th className="px-4 py-3">Iterations</th>
                  <th className="px-4 py-3">Buckets</th>
                  <th className="px-4 py-3">Infosets</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 text-xs">
                <tr>
                  <td className="px-4 py-2.5 font-mono font-bold text-emerald-700">distilled-v1</td>
                  <td className="px-4 py-2.5">6-Max</td>
                  <td className="px-4 py-2.5 text-zinc-600">
                    Expert-iteration distillation from <code>ochs-vr-v1</code> + <code>value_net.bin</code> +{" "}
                    <code>--safe-resolve</code>
                  </td>
                  <td className="px-4 py-2.5 font-mono">2,000,000 + search</td>
                  <td className="px-4 py-2.5 font-mono">16</td>
                  <td className="px-4 py-2.5 font-mono font-semibold">15,956,290+</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-mono font-bold text-emerald-700">ochs-vr-v1</td>
                  <td className="px-4 py-2.5">6-Max</td>
                  <td className="px-4 py-2.5 text-zinc-600">
                    OCHS L1/EMD + VR-MCCFR + 18-Snapshot Avg + Multiway 0.15 + ReBeL <code>value_net.bin</code>
                  </td>
                  <td className="px-4 py-2.5 font-mono">2,000,000</td>
                  <td className="px-4 py-2.5 font-mono">16</td>
                  <td className="px-4 py-2.5 font-mono font-semibold">15,956,290</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-mono font-bold">rnr-caller-v1</td>
                  <td className="px-4 py-2.5">6-Max</td>
                  <td className="px-4 py-2.5 text-zinc-600">
                    Restricted Nash Response (<code>--rnr-model caller --rnr-p 0.5</code>) + OCHS + VR-MCCFR
                  </td>
                  <td className="px-4 py-2.5 font-mono">500,000</td>
                  <td className="px-4 py-2.5 font-mono">12</td>
                  <td className="px-4 py-2.5 font-mono">~4,400,000</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-mono font-bold">hu-v1</td>
                  <td className="px-4 py-2.5">2-Max (HU)</td>
                  <td className="px-4 py-2.5 text-zinc-600">
                    Dedicated Heads-Up blueprint (<code>--players 2</code> + OCHS + VR-MCCFR + Snapshot-Avg)
                  </td>
                  <td className="px-4 py-2.5 font-mono">500,000</td>
                  <td className="px-4 py-2.5 font-mono">12</td>
                  <td className="px-4 py-2.5 font-mono">~300,000</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-mono font-bold text-zinc-600">local-v1</td>
                  <td className="px-4 py-2.5">6-Max</td>
                  <td className="px-4 py-2.5 text-zinc-600">Baseline 6-Max EMD k-means blueprint</td>
                  <td className="px-4 py-2.5 font-mono">1,000,000</td>
                  <td className="px-4 py-2.5 font-mono">12</td>
                  <td className="px-4 py-2.5 font-mono">9,627,290</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h3 className="mt-6 text-sm font-bold text-zinc-900">
            Exploitability Lower-Bound Probes (<code>br</code> Exact Turn/River Expectimax & <code>lbr</code>)
          </h3>
          <div className="mt-3 overflow-x-auto rounded-xl border border-zinc-200">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b bg-zinc-50 text-left text-xs font-semibold tracking-wide text-zinc-500">
                  <th className="px-4 py-3">Model</th>
                  <th className="px-4 py-3">Table Size</th>
                  <th className="px-4 py-3">br Probe (1,000 hands, 60 runouts)</th>
                  <th className="px-4 py-3">lbr Probe (4,000 hands, 60 runouts)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 text-xs">
                <tr>
                  <td className="px-4 py-2.5 font-mono font-semibold">local-v1</td>
                  <td className="px-4 py-2.5">6-Max</td>
                  <td className="px-4 py-2.5 font-mono">528.5 BB/100 (±357.1)</td>
                  <td className="px-4 py-2.5 font-mono">427.0 BB/100 (±170.0)</td>
                </tr>
                <tr className="bg-emerald-50/50">
                  <td className="px-4 py-2.5 font-mono font-bold text-emerald-800">ochs-vr-v1</td>
                  <td className="px-4 py-2.5">6-Max</td>
                  <td className="px-4 py-2.5 font-mono font-bold text-emerald-700">
                    304.0 BB/100 (±306.6) · -42.5%
                  </td>
                  <td className="px-4 py-2.5 font-mono font-bold text-emerald-700">
                    376.3 BB/100 (±158.7) · -11.9%
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-mono font-semibold">rnr-caller-v1</td>
                  <td className="px-4 py-2.5">6-Max</td>
                  <td className="px-4 py-2.5 font-mono">852.4 BB/100 (±446.5)</td>
                  <td className="px-4 py-2.5 font-mono">1034.2 BB/100 (±220.4)</td>
                </tr>
                <tr className="bg-emerald-50/50">
                  <td className="px-4 py-2.5 font-mono font-bold text-emerald-800">hu-v1</td>
                  <td className="px-4 py-2.5">2-Max (HU)</td>
                  <td className="px-4 py-2.5 font-mono font-bold text-emerald-700">114.3 BB/100 (±235.4)</td>
                  <td className="px-4 py-2.5 font-mono font-bold text-emerald-700">148.4 BB/100 (±120.6)</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Section 3: Duplicate, AIVAT, Cross-Play & Burch Safety Ablation */}
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm md:p-8">
          <h2 className="text-xl font-bold">
            3. Duplicate & AIVAT Winrates, 6-Max Cross-Play & Burch Safety-Gadget Ablation
          </h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            To eliminate deck-luck variance, we evaluate blueprints using both <strong>Duplicate matching</strong> (3
            seeds × 24,000 hands) and <strong>AIVAT</strong> (Action-Informed Variance-Reduced Advantage Testing,
            6,000 hands).
          </p>

          <div className="mt-4 grid gap-6 lg:grid-cols-2">
            <div>
              <h3 className="text-sm font-bold text-zinc-900">Duplicate & AIVAT Winrate Benchmarks</h3>
              <div className="mt-2 overflow-x-auto rounded-xl border border-zinc-200">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-zinc-50 text-left font-semibold text-zinc-500">
                      <th className="px-3 py-2.5">Model</th>
                      <th className="px-3 py-2.5">Estimator</th>
                      <th className="px-3 py-2.5">vs Random</th>
                      <th className="px-3 py-2.5">vs Caller</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 font-mono">
                    <tr>
                      <td className="px-3 py-2 font-bold">local-v1</td>
                      <td className="px-3 py-2 font-sans text-zinc-600">Duplicate</td>
                      <td className="px-3 py-2">+696.5 ± 121.0</td>
                      <td className="px-3 py-2">+284.6 ± 101.4</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2 font-bold">ochs-vr-v1</td>
                      <td className="px-3 py-2 font-sans text-zinc-600">Duplicate</td>
                      <td className="px-3 py-2">+635.8 ± 116.3</td>
                      <td className="px-3 py-2">+185.6 ± 100.8</td>
                    </tr>
                    <tr className="bg-emerald-50/50">
                      <td className="px-3 py-2 font-bold text-emerald-800">rnr-caller-v1</td>
                      <td className="px-3 py-2 font-sans text-zinc-600">Duplicate</td>
                      <td className="px-3 py-2">+572.1 ± 128.4</td>
                      <td className="px-3 py-2 font-bold text-emerald-700">+5501.1 ± 82.9</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2 font-bold">hu-v1 (2-Max)</td>
                      <td className="px-3 py-2 font-sans text-zinc-600">Duplicate</td>
                      <td className="px-3 py-2">+359.5 ± 49.5</td>
                      <td className="px-3 py-2 font-bold text-emerald-700">+690.1 ± 52.3</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2 font-bold">ochs-vr-v1</td>
                      <td className="px-3 py-2 font-sans text-zinc-600">AIVAT</td>
                      <td className="px-3 py-2">+486.7 ± 147.6</td>
                      <td className="px-3 py-2">+209.7 ± 105.0</td>
                    </tr>
                    <tr className="bg-emerald-50/50">
                      <td className="px-3 py-2 font-bold text-emerald-800">rnr-caller-v1</td>
                      <td className="px-3 py-2 font-sans text-zinc-600">AIVAT</td>
                      <td className="px-3 py-2">+578.7 ± 162.4</td>
                      <td className="px-3 py-2 font-bold text-emerald-700">+5346.5 ± 387.4</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2 font-bold">hu-v1 (2-Max)</td>
                      <td className="px-3 py-2 font-sans text-zinc-600">AIVAT</td>
                      <td className="px-3 py-2">+348.1 ± 99.7</td>
                      <td className="px-3 py-2 font-bold text-emerald-700">+546.6 ± 86.1</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-bold text-zinc-900">6-Max Head-to-Head Cross-Play (24,000 Hands)</h3>
              <div className="mt-2 overflow-x-auto rounded-xl border border-zinc-200">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-zinc-50 text-left font-semibold text-zinc-500">
                      <th className="px-3 py-2.5">Focal (1 Rotating Seat)</th>
                      <th className="px-3 py-2.5">Field (5 Seats)</th>
                      <th className="px-3 py-2.5">Hands</th>
                      <th className="px-3 py-2.5">Winrate (BB/100)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 font-mono">
                    <tr className="bg-emerald-50/40">
                      <td className="px-3 py-2.5 font-bold text-emerald-800">distilled-v1</td>
                      <td className="px-3 py-2.5">ochs-vr-v1</td>
                      <td className="px-3 py-2.5">24,000</td>
                      <td className="px-3 py-2.5 font-bold text-emerald-700">+26.75 ± 111.62</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2.5 font-bold text-emerald-800">ochs-vr-v1</td>
                      <td className="px-3 py-2.5">local-v1</td>
                      <td className="px-3 py-2.5">24,000</td>
                      <td className="px-3 py-2.5 font-bold text-emerald-700">+40.57 ± 116.78</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2.5 font-bold text-emerald-800">distilled-v1</td>
                      <td className="px-3 py-2.5">local-v1</td>
                      <td className="px-3 py-2.5">24,000</td>
                      <td className="px-3 py-2.5 font-bold text-emerald-700">+40.57 ± 116.78</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h3 className="mt-5 text-sm font-bold text-zinc-900">
                Burch Safety-Gadget Continual Resolving Ablation (<code>ablate-safety</code>)
              </h3>
              <div className="mt-2 overflow-x-auto rounded-xl border border-zinc-200">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b bg-zinc-50 text-left font-semibold text-zinc-500">
                      <th className="px-3 py-2">Noise ε</th>
                      <th className="px-3 py-2">Unsafe Mean / Max</th>
                      <th className="px-3 py-2 text-emerald-700">Safe Gadget Mean / Max</th>
                      <th className="px-3 py-2">Mean Pot</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 font-mono">
                    <tr>
                      <td className="px-3 py-2">0.25</td>
                      <td className="px-3 py-2 text-zinc-600">3.0 / 85.6 chips</td>
                      <td className="px-3 py-2 font-bold text-emerald-700">1.5 / 21.0 chips</td>
                      <td className="px-3 py-2">2,083</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2">0.50</td>
                      <td className="px-3 py-2 text-zinc-600">4.8 / 117.9 chips</td>
                      <td className="px-3 py-2 font-bold text-emerald-700">1.6 / 15.0 chips</td>
                      <td className="px-3 py-2">2,083</td>
                    </tr>
                    <tr className="bg-emerald-50/50">
                      <td className="px-3 py-2 font-bold">1.00</td>
                      <td className="px-3 py-2 text-red-700">9.8 / 317.4 chips</td>
                      <td className="px-3 py-2 font-bold text-emerald-700">1.7 / 42.7 chips (-86.5%)</td>
                      <td className="px-3 py-2">2,083</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs leading-5 text-emerald-900">
            <strong>Key Ablation Finding:</strong> Under maximally corrupted opponent range beliefs (<code>ε = 1.0</code>
            ), naive unsafe subgame resolving exposes up to <strong>317.4 chips</strong> (9.8 chips mean) of
            best-response exploitation above the blueprint safety threshold. Burch gadget continual resolving bounds the
            mean best-response margin to <strong>1.7 chips ({"<0.1%"} of the 2,083-chip pot)</strong> and reduces
            worst-case combo exploitation by <strong>86.5%</strong> (<code>42.7</code> vs <code>317.4</code> chips).
          </div>
        </section>

        {/* Section 4: AI Coach & IR Drill Recommendation Engine */}
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm md:p-8">
          <h2 className="text-xl font-bold">4. Grounded AI Coach & Information-Retrieval Drill Engine</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            The AI Coach never invents frequencies. Every explanation is conditioned on structured solver JSON, exact
            EV loss deltas, and your 12-detector leak telemetry.
          </p>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-5">
              <h3 className="text-sm font-bold text-zinc-900">Solver-Grounded Coaching Pipeline</h3>
              <ul className="mt-2 list-disc space-y-1.5 pl-4 text-xs leading-5 text-zinc-600">
                <li>
                  <strong>Context Assembly:</strong> <code className="text-[11px]">strategyMap</code>,{" "}
                  <code className="text-[11px]">evMap</code>, <code className="text-[11px]">nashDistance</code> /
                  <code className="text-[11px]">solver_gap_chips</code>, and active user leak profile.
                </li>
                <li>
                  <strong>Deterministic Guardrails:</strong> Temperature <code className="text-[11px]">0.3</code>, 800
                  token ceiling, structured output schema{" "}
                  <code className="text-[11px]">{"{"} summary, why, heuristic, evLoss, drillSuggestion {"}"}</code>.
                </li>
                <li>
                  <strong>Caching & Tone:</strong> 7-day cache keyed by{" "}
                  <code className="text-[11px]">hash(solverContext + leakId)</code>; supports concise, detailed, and
                  math-heavy coaching modes.
                </li>
              </ul>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-5">
              <h3 className="text-sm font-bold text-zinc-900">Personalized Leak-to-Drill IR Recommender</h3>
              <ul className="mt-2 list-disc space-y-1.5 pl-4 text-xs leading-5 text-zinc-600">
                <li>
                  <strong>12 Automated Leak Detectors:</strong> Quantifies BB over-folding, c-bet frequency errors,
                  turn/river aggression, and positional VPIP drift in <code className="text-[11px]">bb/100</code>.
                </li>
                <li>
                  <strong>Hybrid IR Ranking:</strong> Combines lexical TF-IDF (word + character 3-gram cosine
                  similarity) with telemetry EV-loss severity and novelty discounting.
                </li>
                <li>
                  <strong>Offline IR Metrics & Spaced Repetition:</strong> Validated with{" "}
                  <code className="text-[11px]">NDCG@k</code>, <code className="text-[11px]">MRR</code>,{" "}
                  <code className="text-[11px]">Precision@k</code>, <code className="text-[11px]">Recall@k</code>, and
                  scheduled via SM-2 spaced repetition.
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* Section 5: Live Benchmark Verification */}
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm md:p-8">
          <h2 className="text-xl font-bold">5. Live Validation Suite & Honest Scope Disclosure</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            In addition to our 15.96M+ infoset Rust MCCFR benchmarks, our web{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">SolverService</code> is continuously verified
            against 18 canonical preflop and postflop GTO benchmarks via{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">/api/solver/validate</code>.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link
              href="/methodology/accuracy"
              className="rounded-full bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-emerald-700"
            >
              Open Live Accuracy & Benchmark Dashboard →
            </Link>
            <Link
              href="/api/solver/validate"
              className="rounded-full border border-zinc-300 bg-white px-5 py-2.5 text-xs font-semibold hover:bg-zinc-50"
            >
              Raw Validation JSON (/api/solver/validate)
            </Link>
            <a
              href="https://github.com/dns2jtm/aipokerlab"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full border border-zinc-300 bg-white px-5 py-2.5 text-xs font-semibold hover:bg-zinc-50"
            >
              View Source on GitHub →
            </a>
          </div>
        </section>

        <p className="mt-8 text-xs text-zinc-500">
          Last updated: October 2026 · Engineered & verified by Daniel Sawa (
          <a href="https://github.com/dns2jtm/aipokerlab" className="underline">
            github.com/dns2jtm/aipokerlab
          </a>
          )
        </p>
      </div>
    </>
  );
}
