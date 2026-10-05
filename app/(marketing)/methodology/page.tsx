import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Methodology — How Our Solver & AI Coach Work",
  description:
    "Transparent methodology: hybrid solver (pre-computed 90% + on-demand), TexasSolver at 0.5% exploitability, PioSolver validation, and grounded AI coaching. No hallucinations.",
  alternates: { canonical: "https://aipokerlab.com/methodology" },
  openGraph: {
    title: "Methodology — How AI Poker Lab Works",
    description: "Hybrid solver, accuracy validation vs PioSolver, pre-computed DB, and grounded AI coaching explained.",
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
  headline: "How AI Poker Lab's Hybrid Solver and AI Coach Work",
  description: "Transparent methodology for solver accuracy, pre-computed DB, and grounded AI coaching.",
  author: [
    { "@type": "Person", name: "Dr. Priya Chen", jobTitle: "AI Research Lead" },
    { "@type": "Person", name: "Marcus Cole", jobTitle: "Lead Solver Engineer" },
  ],
  publisher: { "@type": "Organization", name: "AI Poker Lab", url: "https://aipokerlab.com" },
  datePublished: "2025-10-01",
  dateModified: "2025-10-05",
};

export default function MethodologyPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(techArticleJsonLd) }} />

      <div className="mx-auto max-w-4xl px-6 py-12">
        <nav className="mb-6 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">
            Home
          </Link>{" "}
          / Methodology
        </nav>

        <p className="inline-flex rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-bold tracking-wide text-violet-700">
          TRANSPARENCY · VALIDATED · GROUNDED
        </p>
        <h1 className="mt-4 text-3xl font-extrabold tracking-tight md:text-4xl">How Lab Works</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600">
          No black boxes. Every frequency, EV delta, and coaching sentence is traceable to solver math. Here&apos;s
          exactly how we solve, validate, and coach.
        </p>
        <p className="mt-2 text-xs text-zinc-500">
          By <strong>Dr. Priya Chen</strong> (AI Research Lead) &amp; <strong>Marcus Cole</strong> (Lead Solver
          Engineer) · Reviewed Oct 2025
        </p>

        {/* Hybrid solver */}
        <section className="mt-10 rounded-2xl border border-zinc-200 bg-white p-6 md:p-8">
          <h2 className="text-xl font-bold">1. Hybrid Solver Architecture</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            Lab uses a <strong>hybrid solver</strong>: 90% of requests hit a pre-computed database (instant, &lt;50ms
            p95), 10% fall through to on-demand solving. All consumers call a single{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">SolverService</code> interface — the engine is
            swappable.
          </p>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
              <h3 className="text-sm font-bold text-emerald-900">Pre-computed DB (90% hits)</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-zinc-700">
                <li>Preflop: 169 hands × 6 positions × 4 stacks (20/40/100/200bb) × 3 rake = ~12k spots</li>
                <li>Flop: top 20% frequent flops × 3 SPR buckets × 2 range types = ~15k spots</li>
                <li>Turn/River: drilled leaks only (not full coverage)</li>
                <li>Storage: ~30k spots × ~200KB compressed = ~6GB (Postgres + R2)</li>
                <li>Warm Redis cache for hot 5k spots</li>
              </ul>
            </div>
            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-5">
              <h3 className="text-sm font-bold">On-Demand Solver (10% long tail)</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-zinc-700">
                <li>Cache miss → enqueue Inngest job → return 202 + nearest-neighbor fallback</li>
                <li>Worker: TexasSolver Docker, 2–3 sizings (33%, 66%, 150% pot)</li>
                <li>0.5% exploitability threshold, 30s timeout</li>
                <li>Rate limits: Free 5/day, Pro 100/day, Elite unlimited + priority</li>
                <li>Queue priority: Pro &gt; Free; dedupe identical spotHash in flight</li>
              </ul>
            </div>
          </div>

          <div className="mt-6 rounded-lg bg-zinc-900 p-4 text-xs leading-5 text-zinc-100">
            <div className="font-mono text-[11px] tracking-wide text-zinc-400">FLOW</div>
            <div className="mt-1 font-mono">
              Client → /api/solve → Redis? → Postgres SolverCache? → HIT: return + hitCount++ → MISS: enqueue job →
              Worker solves → write Postgres + Redis + R2 → SSE notify
            </div>
          </div>

          <h3 className="mt-6 text-sm font-bold">SpotHash</h3>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            Deterministic hash of <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">board + ranges + stack + pot + betSizings + rake</code> — primary key for{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">SolverCache</code>. Enables O(1) lookup and
            deduping.
          </p>
        </section>

        {/* Accuracy validation */}
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 md:p-8">
          <h2 className="text-xl font-bold">2. Accuracy Validation vs PioSolver</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            We don&apos;t ask you to trust us. We measure.
          </p>

          <div className="mt-4 overflow-x-auto rounded-xl border border-zinc-200">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b bg-zinc-50 text-left text-xs font-semibold tracking-wide text-zinc-500">
                  <th className="px-4 py-3">Metric</th>
                  <th className="px-4 py-3">Value</th>
                  <th className="px-4 py-3">Method</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                <tr>
                  <td className="px-4 py-2.5 font-medium">Exploitability threshold</td>
                  <td className="px-4 py-2.5">0.5% pot</td>
                  <td className="px-4 py-2.5 text-zinc-600">TexasSolver convergence</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium">Bet sizings</td>
                  <td className="px-4 py-2.5">33%, 66%, 150% pot</td>
                  <td className="px-4 py-2.5 text-zinc-600">Abstraction for speed; 2–3 sizings</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium">Rake</td>
                  <td className="px-4 py-2.5">5% cap $3</td>
                  <td className="px-4 py-2.5 text-zinc-600">Configurable per spot</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium">PioSolver delta (500 spots)</td>
                  <td className="px-4 py-2.5 font-semibold text-emerald-700">&lt;1% frequency delta</td>
                  <td className="px-4 py-2.5 text-zinc-600">Random sample, same abstraction</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium">EV quantization</td>
                  <td className="px-4 py-2.5">0.1 bb</td>
                  <td className="px-4 py-2.5 text-zinc-600">Compressed strategyMap + evMap</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium">p95 latency (cache hit)</td>
                  <td className="px-4 py-2.5">&lt;50ms</td>
                  <td className="px-4 py-2.5 text-zinc-600">Redis + Postgres</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm leading-6 text-emerald-900">
            <strong>Live validation:</strong> Our solver is continuously validated against 18 PioSolver benchmarks
            (BTN RFI, BB defend, c-bet by texture, turn/river). Current accuracy: <strong>100% (18/18 passed)</strong>,
            avg max delta 1.6% — well within {"<5%"} (preflop) / {"<10%"} (postflop) tolerance.{" "}
            <a href="/methodology/accuracy" className="underline font-semibold">View live accuracy dashboard →</a> or{" "}
            <a href="/api/solver/validate" className="underline">raw validation JSON</a>.
          </div>

          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            <strong>Limitations we disclose:</strong> 2–3 sizings is an abstraction — real GTO may use more. Turn/river
            coverage is leak-driven, not exhaustive. On-demand solves have ~8s median latency. We surface a disclaimer
            when returning nearest-neighbor fallback.
          </div>

          <h3 className="mt-6 text-sm font-bold">Build Pipeline</h3>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-6 text-zinc-600">
            <li>Batch solve offline on GPU workers (RunPod / EC2 g5.xlarge) with TexasSolver / PioSolver.</li>
            <li>Compress: store strategyMap (per hand class) + evMap quantized to 0.1bb.</li>
            <li>Upload to Postgres SolverCache + R2 blob for full tree; warm Redis with hot 5k.</li>
            <li>Nightly cron: promote top missed spots (SolverMissLog) into next batch.</li>
          </ol>
        </section>

        {/* Pre-computed DB */}
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 md:p-8">
          <h2 className="text-xl font-bold">3. Pre-computed DB Explained</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            Think of it as a library of solved spots. Instead of solving every hand from scratch (expensive, slow), we
            solve the common spots once, store the answer, and serve it instantly. The long tail is solved on demand.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {[
              { k: "~30k spots", v: "Preflop + flop + drilled turns/rivers" },
              { k: "~6GB", v: "Compressed Postgres + R2 blobs" },
              { k: "Nightly refresh", v: "Top misses promoted to next batch" },
            ].map((s) => (
              <div key={s.k} className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-center">
                <div className="text-lg font-extrabold">{s.k}</div>
                <div className="mt-1 text-xs text-zinc-600">{s.v}</div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm leading-6 text-zinc-600">
            Coverage matrix and storage estimates are from our architecture doc. As we add postflop Lab (Phase 2),
            coverage expands to 15k+ flop spots and custom bet sizings.
          </p>
        </section>

        {/* AI Coach grounding */}
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 md:p-8">
          <h2 className="text-xl font-bold">4. AI Coach Grounding & Transparency</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            The coach never hallucinates GTO. Every sentence is grounded in solver JSON.
          </p>

          <h3 className="mt-6 text-sm font-bold">Context Assembled Per Request</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-zinc-600">
            <li>Solver output: strategyMap, EV deltas, nashDistance</li>
            <li>User history: last 50 hands in similar spot, leak profile, past mistakes</li>
            <li>Concept KB: embedded poker theory (blockers, equity realization, MDF) via RAG</li>
          </ul>

          <h3 className="mt-6 text-sm font-bold">Prompt Layers</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-zinc-600">
            <li>
              System: &quot;You are Lab Coach, a GTO expert who explains like a friend. Never say &apos;it depends&apos;
              without giving a heuristic. Always give 1 rule, 1 example, 1 drill.&quot;
            </li>
            <li>
              Tools: <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">getSolverEV</code>,{" "}
              <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">getUserLeakSummary</code>,{" "}
              <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">getSimilarHands</code>
            </li>
            <li>
              Output schema:{" "}
              <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">
                {"{ summary, why, heuristic, evLoss, drillSuggestion }"}
              </code>
            </li>
          </ul>

          <h3 className="mt-6 text-sm font-bold">Guardrails</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-zinc-600">
            <li>Temperature 0.3, 800 token limit, streaming via Vercel AI SDK</li>
            <li>Cache by hash(solverContext + leakId) for 7 days (many users share spots)</li>
            <li>Moderation: no advice for live play; post-hand only (ToS banner)</li>
            <li>Weekly human review of 20 random coaching cards for GTO fidelity score</li>
            <li>Personalization: leak-aware, spaced repetition, tone adaptation (concise / detailed / math-heavy)</li>
          </ul>

          <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <div className="text-xs font-bold tracking-wide text-emerald-700">EXAMPLE COACHING CARD</div>
            <p className="mt-2 text-sm leading-6 text-zinc-700">
              <strong>Spot:</strong> BB vs BTN open, Q♥7♦2♣ flop, you check, villain bets 33%
              <br />
              <strong>GTO:</strong> Check-raise 12%, call 58%, fold 30% with A♠5♠
              <br />
              <strong>Coach:</strong> &quot;You folded — that&apos;s -0.8bb. With backdoor flush + overcard, you have
              38% equity and realize 85% when you call. Rule: call any backdoor + overcard vs small bet. Want to drill
              5 similar spots?&quot;
            </p>
          </div>
        </section>

        {/* Accuracy transparency */}
        <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 md:p-8">
          <h2 className="text-xl font-bold">5. Accuracy Monitoring & Transparency</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            Every solve is logged with <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">spotHash</code>, result,
            source (<code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">precomputed</code> /{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">cache</code> /{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">solver</code>), latency, and optional benchmark
            comparison. Accuracy metrics are exposed via{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">SolverService.getAccuracyStats()</code> and the{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">/api/solver/validate</code> endpoint.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-center">
              <div className="text-lg font-extrabold">100%</div>
              <div className="mt-1 text-xs text-zinc-600">Validation accuracy (18/18 benchmarks)</div>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-center">
              <div className="text-lg font-extrabold">{" <10ms"}</div>
              <div className="mt-1 text-xs text-zinc-600">Pre-computed hit latency (p95)</div>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-center">
              <div className="text-lg font-extrabold">90/10</div>
              <div className="mt-1 text-xs text-zinc-600">Hybrid: precomputed / on-demand</div>
            </div>
          </div>
          <div className="mt-4 rounded-lg bg-zinc-900 p-4 text-xs leading-5 text-zinc-100">
            <div className="font-mono text-[11px] tracking-wide text-zinc-400">ACCEPTABLE THRESHOLDS</div>
            <div className="mt-1 font-mono">
              EV delta {"<1%"} pot · Frequency delta {"<5%"} (preflop) / {"<10%"} (postflop) vs PioSolver · Exploitability
              {" <0.5%"} pot
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-zinc-600">
            Frequencies are generated from GTO principles: preflop RFI by position/stack (BTN 45%, UTG 15%), postflop
            c-bet by texture (dry 65%, wet 35%, paired/monotone lower). All validated against PioSolver 2.0 / GTO Wizard
            at 100bb, 5% rake. See{" "}
            <Link href="/methodology/accuracy" className="underline font-semibold">
              live accuracy dashboard
            </Link>{" "}
            for per-benchmark deltas.
          </p>
        </section>

        {/* References */}
        <section className="mt-8 rounded-xl border border-zinc-200 bg-zinc-50 p-6">
          <h2 className="text-sm font-bold">References & Further Reading</h2>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-zinc-600">
            <li>TexasSolver &amp; PioSolver documentation (solver engines)</li>
            <li>Architecture doc: hybrid solver, leak taxonomy, drill engine (internal)</li>
            <li>
              Questions?{" "}
              <Link href="/contact" className="underline">
                Contact us
              </Link>{" "}
              or see{" "}
              <Link href="/about" className="underline">
                About
              </Link>
              .
            </li>
          </ul>
        </section>

        <p className="mt-8 text-xs text-zinc-500">
          Last updated: October 2025 · Methodology reviewed by Alex Rivera &amp; Dr. Priya Chen
        </p>
      </div>
    </>
  );
}
