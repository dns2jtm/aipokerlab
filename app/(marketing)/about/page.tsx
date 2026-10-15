import type { Metadata } from "next";
import Link from "next/link";
import { AuthorBios } from "@/components/marketing/AuthorBio";

export const metadata: Metadata = {
  title: "About — Founder, Solver Engineering & Why We Beat GTO Wizard",
  description:
    "Built by Daniel Sawa: native Rust 6-Max/HU Linear MCCFR + ReBeL subgame solver, PyTorch belief-state value networks, and a ToS-compliant GTO coaching platform.",
  alternates: { canonical: "https://aipokerlab.com/about" },
  openGraph: {
    title: "About AI Poker Lab — Built by Daniel Sawa",
    description:
      "Solo-engineered GTO training lab combining native Rust MCCFR + ReBeL resolving, PyTorch belief-state value networks, and IR drill recommendations.",
    url: "https://aipokerlab.com/about",
    type: "website",
  },
};

const aboutJsonLd = {
  "@context": "https://schema.org",
  "@type": "AboutPage",
  name: "About AI Poker Lab",
  url: "https://aipokerlab.com/about",
  description: "Founder, solver engineering architecture, and ToS-compliant positioning of AI Poker Lab.",
  mainEntity: {
    "@type": "Organization",
    name: "AI Poker Lab",
    url: "https://aipokerlab.com",
    foundingDate: "2025",
    founder: {
      "@type": "Person",
      name: "Daniel Sawa",
      jobTitle: "Founder & Lead Systems / ML Engineer",
      url: "https://github.com/dns2jtm",
    },
    slogan: "Lab, not bot.",
    description:
      "ToS-compliant GTO poker training lab powered by native Rust Linear MCCFR + ReBeL subgame resolving, PyTorch belief-state value networks, 12-leak detection, and spaced-repetition drills.",
  },
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: "https://aipokerlab.com/" },
    { "@type": "ListItem", position: 2, name: "About", item: "https://aipokerlab.com/about" },
  ],
};

export default function AboutPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(aboutJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />

      <div className="mx-auto max-w-4xl px-6 py-12">
        <nav className="mb-6 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">
            Home
          </Link>{" "}
          / About
        </nav>

        <p className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold tracking-wide text-emerald-700">
          LAB, NOT BOT — SOLO-ENGINEERED FROM FIRST PRINCIPLES
        </p>
        <h1 className="mt-4 text-3xl font-extrabold tracking-tight md:text-4xl">About AI Poker Lab</h1>
        <p className="mt-3 max-w-2xl text-lg leading-7 text-zinc-600">
          Built by <strong>Daniel Sawa</strong> to bridge imperfect-information game theory, multi-threaded Rust CFR
          solvers, PyTorch belief-state value networks, and actionable human coaching.
        </p>

        {/* Founder story */}
        <section className="mt-10 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm md:p-8">
          <h2 className="text-xl font-bold">Founder & Engineering Story</h2>
          <div className="mt-4 space-y-4 text-sm leading-6 text-zinc-600">
            <p>
              Most poker study tools give you static lookup tables with zero transparency into how strategies are
              computed—or why a specific hand mixes between raising, calling, and folding. Studying raw solver grids
              without understanding range interaction, blocker leverage, or equity realization leads to rote
              memorization rather than durable skill.
            </p>
            <p>
              <strong>Daniel Sawa</strong> (BSc Computer Science, University of York) got tired of static solver charts
              and black-box tools and built the entire AI Poker Lab stack from first principles: a native multi-threaded{" "}
              <strong>Rust 6-Max & Heads-Up Linear MCCFR engine</strong> (
              <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">engine/noregrets</code>) trained across{" "}
              <strong>15.96M+ infosets</strong> with Variance-Reduced MCCFR (VR-MCCFR) control variates and OCHS
              8-quantile future-equity clustering via L1/Earth Mover's Distance k-medians.
            </p>
            <p>
              To support real-time depth-limited subgame solving and rigorous evaluation, Daniel implemented a{" "}
              <strong>PyTorch ReBeL turn belief-state value network</strong> (
              <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">TurnValueNetTorch</code>,{" "}
              <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">2,664 → 256 → 256 → 2,652</code>) with
              binary <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">VN01</code> Rust inference,{" "}
              <strong>Burch safety-gadget continual resolving</strong> (cutting worst-case corrupted-range combo
              exploitation by 86.5%), and a fast vectorized <strong>Python/NumPy CFR+ restricted subgame solver</strong>{" "}
              reporting exact two-player NashConv.
            </p>
            <p>
              On top of the solver core, AI Poker Lab pairs <strong>{"<50ms"} O(1) spotHash lookups</strong> with a
              12-detector EV-loss leak analyzer, an Information Retrieval (TF-IDF + telemetry severity) spaced-repetition
              drill recommender evaluated via <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">NDCG@k</code>{" "}
              and <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">MRR</code>, and solver-grounded AI
              coaching:
              <strong className="text-zinc-900"> Lab, not bot.</strong>
            </p>
          </div>
        </section>

        {/* Architecture highlights */}
        <section className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            {
              title: "15.96M+ Infoset Rust MCCFR",
              desc: "Parallel Linear MCCFR (Rayon + DashMap + mimalloc) with OCHS L1/EMD clustering, VR-MCCFR baselines, and -42.5% BR exploitability reduction.",
            },
            {
              title: "ReBeL Value Net & Safe Resolving",
              desc: "PyTorch belief-state MLP exported to binary VN01 + Burch safety-gadget continual resolving bounding mean BR margin to 1.7 chips (<0.1% pot).",
            },
            {
              title: "Closed Leak → IR Drill Loop",
              desc: "12 automated leak detectors + hybrid lexical/telemetry drill ranking (NDCG@k, MRR) + SM-2 spaced repetition + grounded coaching.",
            },
          ].map((c) => (
            <div key={c.title} className="rounded-xl border border-zinc-200 bg-zinc-50 p-5">
              <h3 className="text-sm font-bold text-zinc-900">{c.title}</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{c.desc}</p>            </div>
          ))}
        </section>

        {/* Why we beat GTO Wizard */}
        <section className="mt-10">
          <h2 className="text-xl font-bold">Why AI Poker Lab Beats Static Chart Viewers</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            GTO Wizard is an excellent cloud chart viewer. AI Poker Lab is a full-stack solver + coaching laboratory
            engineered for measurable EV improvement:
          </p>
          <div className="mt-6 overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b bg-zinc-50 text-left text-xs font-semibold tracking-wide text-zinc-500">
                  <th className="px-4 py-3">Capability</th>
                  <th className="px-4 py-3">GTO Wizard</th>
                  <th className="px-4 py-3 text-emerald-700">AI Poker Lab</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {[
                  [
                    "Solver engine",
                    "Proprietary cloud lookup",
                    "O(1) spotHash DB + Native Rust Linear MCCFR / ReBeL & Python CFR+",
                  ],
                  [
                    "Continual resolving safety",
                    "—",
                    "✓ Burch safety-gadget (86.5% max exploit reduction)",
                  ],
                  ["Explains WHY (blockers, MDF, equity)", "—", "✓ Solver-grounded coaching cards (temp 0.3)"],
                  ["Leak detection with bb/100", "Basic stats", "✓ 12 detectors + EV loss + severity ranking"],
                  ["Auto drills from leaks", "—", "✓ Hybrid TF-IDF / EV-loss IR recommender + SM-2"],
                  ["Statistical evaluation", "—", "✓ AIVAT control variates, Welch t-test, NDCG@k"],
                  ["Open benchmark transparency", "—", "✓ Full BR/LBR, Cross-Play & Safety Ablation tables"],
                  ["Price (Pro tier)", "$49/mo", "$49/mo — full solver + AI coach + drills"],
                ].map(([a, b, c]) => (
                  <tr key={a}>
                    <td className="px-4 py-2.5 font-medium">{a}</td>
                    <td className="px-4 py-2.5 text-zinc-600">{b}</td>
                    <td className="px-4 py-2.5 font-semibold text-emerald-700">{c}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-zinc-500">
            GTO Wizard and PioSolver are trademarks of their respective owners; comparisons are for technical and
            educational purposes.
          </p>
        </section>

        {/* Founder & Engineering */}
        <section className="mt-10">
          <h2 className="text-xl font-bold">Founder & Engineering</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            Every layer of AI Poker Lab—from the Rust MCCFR & ReBeL solver engine and PyTorch belief-state value
            network to the Next.js 15 coaching interface—is architected and maintained by Daniel Sawa.
          </p>
          <div className="mt-6">
            <AuthorBios />
          </div>
          <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            <strong>Engineering & verification policy:</strong> All solver blueprints, subgame resolvers, and
            pre-computed spots are validated against 18 canonical GTO benchmarks (100% pass rate), exact two-player
            NashConv (<code className="rounded bg-amber-100 px-1 py-0.5 text-xs">solver_gap_chips</code>), and exact
            turn/river best-response (<code className="rounded bg-amber-100 px-1 py-0.5 text-xs">br</code> /
            <code className="rounded bg-amber-100 px-1 py-0.5 text-xs">lbr</code>) probes. Coaching prompts are
            strictly grounded in solver JSON at temperature 0.3 — see{" "}
            <Link href="/methodology" className="font-semibold underline">
              Methodology & Benchmarks
            </Link>
            .
          </div>
        </section>

        {/* ToS positioning */}
        <section className="mt-10 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold">ToS-Compliant Positioning</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            AI Poker Lab is a <strong>training and research platform for post-hand study only</strong>. It must not be
            used during live play. Real-time solver or AI assistance violates the Terms of Service of PokerStars,
            GGPoker, and other platforms. AI Poker Lab is built to make <em>you</em> stronger off the table.
          </p>
          <div className="mt-4 flex flex-wrap gap-4">
            <Link href="/methodology" className="text-sm font-semibold text-emerald-700 underline">
              3-Tier Solver Architecture & Benchmarks →
            </Link>
            <Link href="/methodology/accuracy" className="text-sm font-semibold text-emerald-700 underline">
              Live Accuracy & Ablation Dashboard →
            </Link>
            <a
              href="https://github.com/dns2jtm/aipokerlab"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-semibold text-emerald-700 underline"
            >
              GitHub Repository →
            </a>
          </div>
        </section>

        <p className="mt-8 text-xs text-zinc-500">
          Last updated: October 2026 · Engineered by Daniel Sawa · Questions?{" "}
          <Link href="/contact" className="underline">
            hello@aipokerlab.com
          </Link>
        </p>
      </div>
    </>
  );
}
