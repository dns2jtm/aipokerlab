import type { Metadata } from "next";
import Link from "next/link";
import EmailCapture from "@/components/marketing/EmailCapture";
import CtaTracker from "@/components/analytics/CtaTracker";

export const metadata: Metadata = {
  title: "AI Poker Lab — Rust MCCFR + ReBeL GTO Solver, Leak Detector & AI Coach",
  description:
    "Built by Daniel Sawa: 15.96M+ infoset Rust 6-Max/HU Linear MCCFR solver, PyTorch ReBeL belief-state value network, Burch safety-gadget continual resolving, 12-leak detector, and IR spaced-repetition drills.",
  keywords: [
    "ai poker lab",
    "gto poker solver",
    "rebel poker value network",
    "mccfr poker solver",
    "gto wizard alternative",
    "poker ai coach",
    "poker leak detector",
  ],
  alternates: { canonical: "https://aipokerlab.com/" },
  openGraph: {
    title: "AI Poker Lab — GTO Solver, ReBeL Value Net & AI Coach",
    description:
      "15.96M+ infoset Rust Linear MCCFR + ReBeL subgame resolving, PyTorch belief-state value networks, 12-leak detection, and personalized IR drills.",
    url: "https://aipokerlab.com/",
    type: "website",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "AI Poker Lab — GTO Training with AI Coach" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Poker Lab — Rust MCCFR + ReBeL GTO Training Lab",
    description:
      "15.96M+ infoset Rust Linear MCCFR, PyTorch ReBeL value networks, 12-leak detection, and spaced-repetition drills.",
  },
};

const SITE_URL = "https://aipokerlab.com";

const softwareJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "AI Poker Lab",
  url: SITE_URL,
  applicationCategory: "GameApplication",
  operatingSystem: "Web",
  offers: {
    "@type": "AggregateOffer",
    priceCurrency: "USD",
    lowPrice: "0",
    highPrice: "99",
    offerCount: 4,
    offers: [
      { "@type": "Offer", name: "Free", price: "0", priceCurrency: "USD" },
      { "@type": "Offer", name: "Starter", price: "19", priceCurrency: "USD" },
      { "@type": "Offer", name: "Pro", price: "49", priceCurrency: "USD" },
      { "@type": "Offer", name: "Elite", price: "99", priceCurrency: "USD" },
    ],
  },
  author: {
    "@type": "Person",
    name: "Daniel Sawa",
    jobTitle: "Founder & Lead Systems / ML Engineer",
    url: "https://github.com/dns2jtm",
  },
  description:
    "ToS-compliant GTO poker training platform powered by a native Rust 6-Max/HU Linear MCCFR blueprint (15.96M+ infosets), PyTorch ReBeL belief-state value network, Burch safety-gadget continual resolving, and IR drill recommendations.",
  featureList: [
    "Native Rust 6-Max & Heads-Up Linear MCCFR Blueprint (15.96M+ infosets, OCHS L1/EMD, VR-MCCFR)",
    "PyTorch ReBeL Turn Belief-State Value Network (VN01) & Burch Safety-Gadget Continual Resolving",
    "Vectorized Python/NumPy CFR+ Restricted Subgame Solver with Exact Two-Player NashConv",
    "Preflop Lab with 24 GTO charts (6 positions × 4 stack depths) & <50ms O(1) spotHash lookup",
    "12-leak detector with bb/100 quantification & hybrid TF-IDF / EV-loss IR drill recommender",
  ],
  screenshot: `${SITE_URL}/og-image.png`,
};

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "Is AI Poker Lab a real-time poker bot?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "No. AI Poker Lab is a post-hand study and research laboratory. It is ToS-compliant with PokerStars and GGPoker and must not be used during live play.",
      },
    },
    {
      "@type": "Question",
      name: "How does the 3-tier solver architecture work?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Tier 1 serves pre-computed O(1) spotHash strategies in <50ms. Tier 2 runs a native multi-threaded Rust 6-Max/HU Linear MCCFR blueprint (15.96M+ infosets, VR-MCCFR, OCHS clustering) with ReBeL depth-limited flop solving (PyTorch TurnValueNetTorch VN01) and Burch safety-gadget continual resolving. Tier 3 runs a vectorized Python/NumPy CFR+ subgame solver reporting exact two-player NashConv.",
      },
    },
    {
      "@type": "Question",
      name: "How is solver accuracy validated?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "We validate across 18 canonical GTO benchmarks (100% pass rate, 1.6% avg max delta), exact turn/river expectimax best-response (br) and Local Best Response (lbr) probes (-42.5% BR exploitability reduction in ochs-vr-v1), 24,000-hand 6-max cross-play, Duplicate & AIVAT variance-reduced trials, and Burch safety-gadget continual resolving ablations (-86.5% worst-case combo exploitation).",
      },
    },
    {
      "@type": "Question",
      name: "Who built AI Poker Lab?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "AI Poker Lab is architected and engineered by Daniel Sawa (Founder & Lead Systems / ML Engineer, BSc Computer Science, University of York).",
      },
    },
  ],
};

const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "AI Poker Lab",
  url: SITE_URL,
  logo: `${SITE_URL}/icon-512.png`,
  description:
    "ToS-compliant GTO poker training lab & imperfect-information game theory engine built by Daniel Sawa.",
  foundingDate: "2025",
  founder: {
    "@type": "Person",
    name: "Daniel Sawa",
    url: "https://github.com/dns2jtm",
  },
  sameAs: ["https://github.com/dns2jtm/aipokerlab", "https://github.com/dns2jtm"],
  contactPoint: {
    "@type": "ContactPoint",
    email: "hello@aipokerlab.com",
    contactType: "customer support",
    availableLanguage: ["English"],
  },
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
    { "@type": "ListItem", position: 2, name: "Preflop Lab", item: `${SITE_URL}/lab/preflop` },
    { "@type": "ListItem", position: 3, name: "Methodology", item: `${SITE_URL}/methodology` },
    { "@type": "ListItem", position: 4, name: "Pricing", item: `${SITE_URL}/pricing` },
  ],
};

export default function MarketingPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 py-14 md:py-20">
        <div className="grid gap-10 lg:grid-cols-12 lg:items-center">
          <div className="lg:col-span-7">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold tracking-wide text-emerald-700">
                RUST LINEAR MCCFR · PYTORCH REBEL VN01 · CFR+
              </span>
              <span className="inline-flex rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-semibold text-zinc-600">
                15.96M+ Infosets · Built by Daniel Sawa
              </span>
            </div>
            <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-zinc-900 md:text-5xl">
              The GTO Solver & AI Lab
              <br />
              <span className="text-emerald-600">Engineered From First Principles</span>
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-600 md:text-lg">
              Static chart viewers show you frequencies without context. <strong>AI Poker Lab</strong> combines an{" "}
              <strong>O(1) pre-computed spotHash database</strong> with a native multi-threaded{" "}
              <strong>Rust 6-Max & Heads-Up Linear MCCFR blueprint</strong>, a{" "}
              <strong>PyTorch ReBeL belief-state value network</strong>,{" "}
              <strong>Burch safety-gadget continual resolving</strong>, and an{" "}
              <strong>IR spaced-repetition drill engine</strong> that closes your EV leaks.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <CtaTracker location="hero" label="Open Lab — Free" href="/dashboard">
                <Link
                  href="/dashboard"
                  className="rounded-full bg-emerald-600 px-7 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-emerald-700"
                >
                  Open Lab — Free
                </Link>
              </CtaTracker>
              <CtaTracker location="hero" label="Try Preflop Lab" href="/lab/preflop">
                <Link
                  href="/lab/preflop"
                  className="rounded-full border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-50"
                >
                  Interactive Preflop Lab
                </Link>
              </CtaTracker>
              <Link
                href="/methodology"
                className="rounded-full border border-zinc-200 bg-zinc-50 px-5 py-3 text-sm font-semibold text-zinc-700 transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-800"
              >
                Solver Benchmarks →
              </Link>
            </div>
            <p className="mt-3 text-xs text-zinc-500">
              24 free 6-max preflop charts · 18/18 validated GTO benchmarks · Post-hand study only
            </p>
            <div className="mt-6">
              <EmailCapture variant="hero" source="landing_hero" />
            </div>
          </div>

          {/* Hero visual — range grid + solver telemetry card */}
          <div className="space-y-4 lg:col-span-5">
            <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <span className="text-sm font-bold text-zinc-900">Preflop Lab — BTN 100bb RFI</span>
                  <p className="text-[11px] text-zinc-500">O(1) spotHash · 15.96M+ Infoset Blueprint</p>
                </div>
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
                  distilled-v1
                </span>
              </div>
              <div className="grid grid-cols-13 gap-0.5">
                {Array.from({ length: 169 }).map((_, i) => {
                  const v = (i * 37) % 100;
                  let bg = "bg-zinc-100";
                  if (v > 78) bg = "bg-emerald-500";
                  else if (v > 55) bg = "bg-emerald-300";
                  else if (v > 35) bg = "bg-amber-300";
                  else if (v > 18) bg = "bg-red-300";
                  return (
                    <div
                      key={i}
                      className={`aspect-square rounded-sm ${bg} flex items-center justify-center text-[6px] font-bold text-zinc-700`}
                      title={`Hand ${i}`}
                    />
                  );
                })}
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] font-medium text-zinc-600">
                <div className="flex gap-3">
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500" /> Raise 48%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm bg-amber-300" /> Call
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm bg-red-300" /> Fold 52%
                  </span>
                </div>
                <span className="font-mono text-[10px] text-zinc-500">p95 {"<50ms"}</span>
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4 text-xs text-zinc-200 shadow-sm">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                <span className="font-mono text-[11px] font-bold text-emerald-400">
                  ENGINE TELEMETRY · engine/noregrets
                </span>
                <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300">VN01 + CFR+</span>
              </div>
              <div className="mt-2.5 grid grid-cols-2 gap-2 font-mono text-[11px]">
                <div className="rounded-lg bg-zinc-800/80 p-2.5">
                  <div className="text-zinc-400">BR Exploitability</div>
                  <div className="mt-0.5 text-sm font-bold text-emerald-400">-42.5% (304 BB/100)</div>
                </div>
                <div className="rounded-lg bg-zinc-800/80 p-2.5">
                  <div className="text-zinc-400">Burch Safe-Resolve</div>
                  <div className="mt-0.5 text-sm font-bold text-emerald-400">1.7 chips ({"<0.1%"} pot)</div>
                </div>
                <div className="rounded-lg bg-zinc-800/80 p-2.5">
                  <div className="text-zinc-400">RnR vs Calling Station</div>
                  <div className="mt-0.5 text-sm font-bold text-white">+5,346.5 BB/100 AIVAT</div>
                </div>
                <div className="rounded-lg bg-zinc-800/80 p-2.5">
                  <div className="text-zinc-400">6-Max Cross-Play</div>
                  <div className="mt-0.5 text-sm font-bold text-white">+40.57 BB/100 (24k)</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Empirical Benchmarks Banner */}
      <section className="border-y border-zinc-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <span className="text-xs font-bold tracking-wider text-emerald-700 uppercase">
                VERIFIABLE GAME-THEORETIC SYSTEMS
              </span>
              <h2 className="mt-1 text-2xl font-extrabold tracking-tight">
                3-Tier Solver Architecture & Empirical Benchmarks
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">
                Built from scratch in Rust, PyTorch, NumPy, and TypeScript—every component is benchmarked with
                exact turn/river best-response probes, AIVAT control variates, and offline Information Retrieval metrics.
              </p>
            </div>
            <Link
              href="/methodology"
              className="inline-flex shrink-0 rounded-full bg-zinc-900 px-5 py-2.5 text-xs font-bold text-white hover:bg-zinc-800"
            >
              Read Full Methodology →
            </Link>
          </div>

          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {[
              {
                badge: "RUST · RAYON · DASHMAP",
                title: "15.96M+ Infoset Linear MCCFR & ReBeL",
                desc: "Parallel 6-Max & Heads-Up Linear MCCFR with Pluribus negative-regret pruning, VR-MCCFR control-variate baselines, and OCHS 8-quantile L1/EMD hand clustering. Cuts exact turn/river BR exploitability by 42.5%.",
              },
              {
                badge: "PYTORCH · VN01 · SAFETY GADGET",
                title: "Belief-State Value Net & Safe Resolving",
                desc: "TurnValueNetTorch (2,664 → 256 → 256 → 2,652) exported to binary VN01 + Burch safety-gadget continual resolving bounding mean BR margin to 1.7 chips (<0.1% pot) and cutting max combo exploit by 86.5%.",
              },
              {
                badge: "IR RANKING · SM-2 · GROUNDED LLM",
                title: "12-Leak Detector & IR Drill Recommender",
                desc: "Quantifies 12 core leaks in bb/100 and ranks corrective drills via hybrid token/3-gram TF-IDF + EV-loss severity (evaluated with NDCG@k, MRR, and Brier score), paired with solver-grounded AI coaching.",
              },
            ].map((c) => (
              <div key={c.title} className="rounded-2xl border border-zinc-200 bg-zinc-50/70 p-6 shadow-sm">
                <span className="inline-block rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800">
                  {c.badge}
                </span>
                <h3 className="mt-3 text-base font-bold text-zinc-900">{c.title}</h3>
                <p className="mt-2 text-sm leading-6 text-zinc-600">{c.desc}</p>
              </div>
            ))}
          </div>

          {/* Comparison table */}
          <div className="mt-10 overflow-x-auto rounded-2xl border border-zinc-200 bg-white shadow-sm">
            <table className="w-full min-w-[600px] text-sm">
              <thead>
                <tr className="border-b bg-zinc-50 text-left text-xs font-semibold tracking-wide text-zinc-500">
                  <th className="px-4 py-3">Capability</th>
                  <th className="px-4 py-3">Static Cloud Viewers</th>
                  <th className="px-4 py-3 text-emerald-700">AI Poker Lab</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {[
                  [
                    "Solver Architecture",
                    "Pre-solved cloud lookup",
                    "O(1) spotHash DB + Native Rust 6-Max/HU Linear MCCFR + Python CFR+",
                  ],
                  [
                    "Depth-Limited & Safe Resolving",
                    "—",
                    "✓ PyTorch ReBeL Value Net (VN01) + Burch Safety-Gadget (-86.5% max exploit)",
                  ],
                  [
                    "Explains WHY (blockers, MDF, equity)",
                    "—",
                    "✓ Streaming AI Coach grounded in solver JSON (temp 0.3)",
                  ],
                  [
                    "Leak Detection & Drill Ranking",
                    "Basic stats",
                    "✓ 12 EV-loss detectors + TF-IDF / severity IR drill recommender (NDCG@k)",
                  ],
                  [
                    "Benchmark & Statistical Rigor",
                    "Closed",
                    "✓ Published BR/LBR, 24k Cross-Play, AIVAT & Welch t-test benchmarks",
                  ],
                ].map(([f, g, l]) => (
                  <tr key={f}>
                    <td className="px-4 py-2.5 font-medium text-zinc-900">{f}</td>
                    <td className="px-4 py-2.5 text-zinc-600">{g}</td>
                    <td className="px-4 py-2.5 font-semibold text-emerald-700">{l}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Free preflop chart teaser */}
      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-8 md:flex md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-bold">Free Interactive Preflop Lab — 24 GTO Charts</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-700">
              6 positions × 4 stack depths (20bb, 40bb, 100bb, 200bb). Inspect raise, call, and fold frequencies plus
              hand EV in real time.
            </p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              {["UTG", "HJ", "CO", "BTN", "SB", "BB"].map((p) => (
                <span key={p} className="rounded-full bg-white px-3 py-1 font-semibold shadow-sm">
                  {p}
                </span>
              ))}
            </div>
          </div>
          <CtaTracker location="preflop_teaser" label="Open Preflop Lab" href="/lab/preflop">
            <Link
              href="/lab/preflop"
              className="mt-6 inline-flex rounded-full bg-zinc-900 px-6 py-3 text-sm font-bold text-white hover:bg-zinc-800 md:mt-0"
            >
              Open Preflop Lab →
            </Link>
          </CtaTracker>
        </div>
      </section>

      {/* Founder & Engineering Callout */}
      <section className="border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-4xl px-6 py-12">
          <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-6 md:p-8">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <span className="text-xs font-bold tracking-wider text-emerald-700 uppercase">
                  SOLO-ENGINEERED BY DANIEL SAWA
                </span>
                <h2 className="mt-1 text-xl font-bold text-zinc-900">
                  Imperfect-Information Game Theory Meets Actionable Coaching
                </h2>
              </div>
              <a
                href="https://github.com/dns2jtm/aipokerlab"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex shrink-0 items-center gap-1 rounded-full border border-zinc-300 bg-white px-4 py-2 text-xs font-bold text-zinc-800 hover:bg-zinc-100"
              >
                github.com/dns2jtm/aipokerlab ↗
              </a>
            </div>
            <p className="mt-3 text-sm leading-6 text-zinc-600">
              AI Poker Lab is architected by <strong>Daniel Sawa</strong> (BSc Computer Science, University of York).
              Every component—from the multi-threaded Rust 6-Max/HU Linear MCCFR solver (<code className="text-xs">engine/noregrets</code>),
              PyTorch belief-state value network (<code className="text-xs">value_net_torch.py</code>), and vectorized
              NumPy CFR+ subgame solver (<code className="text-xs">showdown_solver.py</code>) to the Next.js 15
              coaching & IR drill engine—is built for mathematical transparency and ToS-compliant post-hand study.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link href="/methodology" className="text-sm font-semibold text-emerald-700 underline">
                Solver Architecture & Benchmarks →
              </Link>
              <span className="text-zinc-300">·</span>
              <Link href="/methodology/accuracy" className="text-sm font-semibold text-emerald-700 underline">
                Live Accuracy Suite →
              </Link>
              <span className="text-zinc-300">·</span>
              <Link href="/about" className="text-sm font-semibold text-emerald-700 underline">
                About Daniel Sawa →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Blog teaser */}
      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-bold">Learn GTO — Strategy & Solver Engineering Blog</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">
              Solver-backed guides by Daniel Sawa: GTO fundamentals, preflop mastery, MDF & equity realization,
              and tool comparisons.
            </p>
          </div>
          <Link
            href="/blog"
            className="hidden rounded-full border border-zinc-300 bg-white px-5 py-2 text-sm font-semibold hover:bg-zinc-50 md:inline-flex"
          >
            View All Articles →
          </Link>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <Link
            href="/blog/what-is-gto-poker-complete-guide"
            className="rounded-xl border border-zinc-200 bg-white p-5 hover:border-emerald-300 hover:shadow-sm"
          >
            <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-700">
              GTO Fundamentals
            </span>
            <h3 className="mt-2 text-sm font-bold leading-tight">What is GTO Poker? Complete Beginner's Guide</h3>
            <p className="mt-1 text-xs leading-5 text-zinc-600">
              Nash equilibrium, why solvers fold 30% on Q72r, and how to study GTO without memorizing 10k charts.
            </p>
          </Link>
          <Link
            href="/blog/ai-poker-bot-vs-gto-solver-difference"
            className="rounded-xl border border-zinc-200 bg-white p-5 hover:border-emerald-300 hover:shadow-sm"
          >
            <span className="rounded-full bg-violet-100 px-2 py-1 text-xs font-bold text-violet-700">AI Poker</span>
            <h3 className="mt-2 text-sm font-bold leading-tight">
              AI Poker Bot vs GTO Solver: What's the Difference?
            </h3>
            <p className="mt-1 text-xs leading-5 text-zinc-600">
              Why post-hand training with a CFR solver beats real-time bots — and keeps your bankroll safe.
            </p>
          </Link>
          <Link
            href="/blog/gto-preflop-charts-how-to-study"
            className="rounded-xl border border-zinc-200 bg-white p-5 hover:border-emerald-300 hover:shadow-sm"
          >
            <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-bold text-amber-800">
              Preflop Strategy
            </span>
            <h3 className="mt-2 text-sm font-bold leading-tight">GTO Preflop Charts: How to Study Like a Pro</h3>
            <p className="mt-1 text-xs leading-5 text-zinc-600">
              How to read range grids, why BTN opens 48% and UTG only 15%, and how to drill ranges until automatic.
            </p>
          </Link>
        </div>
      </section>

      {/* Preflop chart quick links */}
      <section className="border-y border-zinc-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <h2 className="text-lg font-bold">Free GTO Preflop Charts — Every Position & Stack</h2>
          <p className="mt-1 text-sm text-zinc-600">
            24 interactive charts (6 positions × 4 stacks) — hover for frequencies and EV. Validated O(1) pre-computed
            GTO ranges.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
            {[
              ["BTN 100bb", "/lab/preflop/btn/100", "Most profitable — start here"],
              ["UTG 100bb", "/lab/preflop/utg/100", "Tightest — discipline test"],
              ["BB 100bb", "/lab/preflop/bb/100", "Biggest leak — defend wider"],
              ["CO 100bb", "/lab/preflop/co/100", "Where ranges open up"],
              ["BTN 20bb", "/lab/preflop/btn/20", "Short-stack push/fold"],
              ["BTN 200bb", "/lab/preflop/btn/200", "Deep — implied odds matter"],
              ["SB 100bb", "/lab/preflop/sb/100", "Trickiest spot — OOP"],
              ["All Charts", "/lab/preflop", "Browse all 24 →"],
            ].map(([label, href, desc]) => (
              <Link
                key={label}
                href={href}
                className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 hover:border-emerald-300 hover:bg-white"
              >
                <p className="text-sm font-bold">{label}</p>
                <p className="text-xs text-zinc-500">{desc}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Email capture footer */}
      <section className="mx-auto max-w-6xl px-6 py-10">
        <EmailCapture variant="inline" source="landing_footer" />
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-6 py-12 text-center">
        <h2 className="text-2xl font-bold">Ready to train with real solver telemetry?</h2>
        <p className="mt-2 text-sm text-zinc-600">Open the Lab, paste a hand, and inspect your leaks in seconds.</p>
        <CtaTracker location="footer_cta" label="Go to Dashboard" href="/dashboard">
          <Link
            href="/dashboard"
            className="mt-6 inline-flex rounded-full bg-emerald-600 px-8 py-3 text-sm font-bold text-white hover:bg-emerald-700"
          >
            Go to Dashboard
          </Link>
        </CtaTracker>
      </section>
    </>
  );
}
