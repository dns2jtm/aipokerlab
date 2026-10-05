import type { Metadata } from "next";
import Link from "next/link";
import EmailCapture from "@/components/marketing/EmailCapture";
import CtaTracker from "@/components/analytics/CtaTracker";

export const metadata: Metadata = {
  title: "AI Poker Lab — The AI Poker Lab That Makes You Unbeatable",
  description:
    "GTO poker training that beats GTO Wizard by being a better COACH. Personalized AI explanations, leak-to-drill loop, adaptive learning. Rank for ai poker bot the right way — ToS-compliant training.",
  keywords: [
    "ai poker bot",
    "ai poker lab",
    "gto poker trainer",
    "gto wizard alternative",
    "poker ai coach",
    "gto poker training",
    "poker leak detector",
  ],
  alternates: { canonical: "https://aipokerlab.com/" },
  openGraph: {
    title: "The AI Poker Lab That Makes You Unbeatable",
    description:
      "Stop memorizing charts. Start understanding GTO with an AI coach that finds your leaks and drills you until they're gone.",
    url: "https://aipokerlab.com/",
    type: "website",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "AI Poker Lab — GTO Training with AI Coach" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "The AI Poker Lab That Makes You Unbeatable",
    description: "GTO training with a real AI coach. Leak detection → personalized drills → measurable improvement.",
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
  aggregateRating: { "@type": "AggregateRating", ratingValue: "4.8", ratingCount: "127", bestRating: "5" },
  author: { "@type": "Organization", name: "AI Poker Lab", url: SITE_URL },
  description:
    "GTO poker training SaaS with AI coach, leak detection, and spaced-repetition drills. ToS-compliant post-hand study — not a bot.",
  featureList: [
    "Preflop Lab with 24 GTO charts (6 positions × 4 stack depths)",
    "Hand Replayer with GTO overlay and EV loss per street",
    "12-leak detector with bb/100 quantification",
    "Leak-to-drill closed loop with spaced repetition",
    "AI Coach streaming explanations grounded in solver math",
  ],
  screenshot: `${SITE_URL}/og-image.png`,
};

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "Is AI Poker Lab an ai poker bot for cheating?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "No. AI Poker Lab is a training lab for post-hand study only. It is ToS-compliant with PokerStars and GGPoker and must not be used during live play. Real-time bots get your account banned — Lab keeps you safe by training you to play GTO yourself.",
      },
    },
    {
      "@type": "Question",
      name: "How is this better than GTO Wizard?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "GTO Wizard shows frequencies. Lab explains WHY in plain English, links every mistake to your personal leaks, and auto-generates drills until the leak is fixed — the closed loop GTO Wizard doesn't have. Plus personalized memory and adaptive tone.",
      },
    },
    {
      "@type": "Question",
      name: "What does the AI Coach actually do?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "The AI Coach is grounded in solver output (strategyMap + EV deltas) and your leak profile. It streams a coaching card per mistake: summary, why (blockers, equity realization, MDF), a heuristic, EV loss, and a drill suggestion. Temperature 0.3, 800 token limit, cached 7 days.",
      },
    },
    {
      "@type": "Question",
      name: "Is my hand history private?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Yes. Your hands never train our models without explicit opt-in. Raw histories are stored encrypted, parsed hands are isolated per user, and you can delete everything at any time. See our Privacy Policy.",
      },
    },
    {
      "@type": "Question",
      name: "How accurate is the solver?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Pre-computed spots are solved with TexasSolver at 0.5% exploitability, 2–3 bet sizings, rake 5% cap $3. Validated vs PioSolver within 1% frequency delta on 500 sampled spots. See Methodology for full validation.",
      },
    },
    {
      "@type": "Question",
      name: "Can I use this during live play?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "No. AI Poker Lab is for post-hand study only. Using any solver or AI assistance during live play violates PokerStars and GGPoker Terms of Service and risks account bans and fund seizure.",
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
  description: "ToS-compliant GTO poker training lab — AI coach, leak detection, and drills. Not a cheating bot.",
  foundingDate: "2025",
  sameAs: [
    "https://twitter.com/aipokerlab",
    "https://github.com/aipokerlab",
    "https://www.youtube.com/@aipokerlab",
  ],
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
    { "@type": "ListItem", position: 3, name: "Replayer", item: `${SITE_URL}/replayer` },
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
      <section className="mx-auto max-w-6xl px-6 py-16 md:py-24">
        <div className="grid gap-10 md:grid-cols-2 md:items-center">
          <div>
            <p className="mb-3 inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold tracking-wide text-emerald-700">
              ToS-COMPLIANT · POST-HAND TRAINING ONLY
            </p>
            <h1 className="text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">
              The AI Poker Lab
              <br />
              <span className="text-emerald-600">That Makes You Unbeatable</span>
            </h1>
            <p className="mt-4 max-w-xl text-lg leading-7 text-zinc-600">
              GTO Wizard shows you frequencies. <strong>Lab coaches you</strong> — explains every mistake in plain
              English, finds your leaks, and drills you until they&apos;re gone. The closed loop that actually makes
              you better.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <CtaTracker location="hero" label="Open Lab — Free" href="/dashboard">
                <Link
                  href="/dashboard"
                  className="rounded-full bg-emerald-600 px-7 py-3 text-sm font-bold text-white shadow hover:bg-emerald-700"
                >
                  Open Lab — Free
                </Link>
              </CtaTracker>
              <CtaTracker location="hero" label="Try Preflop Lab" href="/lab/preflop">
                <Link
                  href="/lab/preflop"
                  className="rounded-full border border-zinc-300 bg-white px-7 py-3 text-sm font-semibold hover:bg-zinc-50"
                >
                  Try Preflop Lab
                </Link>
              </CtaTracker>
            </div>
            <p className="mt-3 text-xs text-zinc-500">Free preflop charts · 5 hand reviews/day · No card required</p>
            <div className="mt-6">
              <EmailCapture variant="hero" source="landing_hero" />
            </div>
          </div>

          {/* Hero visual — mock range grid teaser */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">Preflop Lab — BTN 100bb</span>
              <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">GTO</span>
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
            <div className="mt-3 flex gap-2 text-[10px] font-medium">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-sm bg-emerald-500" /> Raise
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-sm bg-amber-300" /> Call
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-sm bg-red-300" /> Fold
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-sm bg-zinc-200" /> Mixed
              </span>
            </div>
            <p className="mt-2 text-xs text-zinc-500">169 hands · 6 positions · 4 stack depths — pre-computed, instant.</p>
          </div>
        </div>
      </section>

      {/* Value props vs GTO Wizard */}
      <section className="border-y border-zinc-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <h2 className="text-center text-2xl font-bold">Why Lab beats GTO Wizard</h2>
          <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-zinc-600">
            GTO Wizard is a solver viewer. Lab is a coach that closes the loop.
          </p>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {[
              {
                title: "Explains WHY, not just what",
                desc: "Every spot comes with a plain-English coaching card: blockers, equity realization, MDF — grounded in solver math, not hallucinated.",
                icon: "🧠",
              },
              {
                title: "Leak → Drill closed loop",
                desc: "Lab detects your 12 core leaks (BB defend, c-bet, fold vs c-bet…) and auto-generates spaced-repetition drills from your worst leak.",
                icon: "🎯",
              },
              {
                title: "Adaptive & personal",
                desc: "Remembers your mistakes, references last week's errors, adapts tone (concise / math-heavy). Your history, not generic charts.",
                icon: "🔁",
              },
            ].map((c) => (
              <div key={c.title} className="rounded-xl border border-zinc-200 bg-zinc-50 p-6">
                <div className="text-2xl">{c.icon}</div>
                <h3 className="mt-3 font-semibold">{c.title}</h3>
                <p className="mt-2 text-sm leading-6 text-zinc-600">{c.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-10 overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b text-left text-zinc-500">
                  <th className="py-2 font-medium">Feature</th>
                  <th className="py-2 font-medium">GTO Wizard</th>
                  <th className="py-2 font-semibold text-emerald-700">AI Poker Lab</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {[
                  ["Solver viewer", "✓", "✓"],
                  ["AI explains WHY", "—", "✓ streaming coach"],
                  ["Leak detection (bb/100)", "basic", "12 leaks + EV loss"],
                  ["Auto drills from leaks", "—", "✓ spaced repetition"],
                  ["Personalized memory", "—", "✓"],
                  ["ToS banner everywhere", "—", "✓"],
                ].map(([f, g, l]) => (
                  <tr key={f}>
                    <td className="py-2 font-medium">{f}</td>
                    <td className="py-2 text-zinc-600">{g}</td>
                    <td className="py-2 font-semibold text-emerald-700">{l}</td>
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
            <h2 className="text-xl font-bold">Free Preflop Charts — Start Now</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-700">
              6-max, 100bb, all positions. See GTO open, 3-bet, and defend frequencies for every hand. No signup to
              browse — sign up to drill.
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

      {/* SEO: ai poker bot conquest */}
      <section className="border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-3xl px-6 py-12">
          <h2 className="text-lg font-bold">AI Poker Bot vs AI Poker Lab: Why Training Beats Cheating</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            Searching for an &quot;ai poker bot&quot;? Real-time bots get your account banned and your funds seized.{" "}
            <strong>AI Poker Lab</strong> is the ToS-compliant alternative: study GTO after your session, fix leaks
            with AI coaching, and bring unbeatable play to the table yourself — safely. Training beats cheating, and it
            keeps your account safe.
          </p>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            Lab is built for serious students: hybrid solver (pre-computed 90% + on-demand), Vercel AI SDK streaming
            coach, and a leak-to-drill loop that GTO Wizard doesn&apos;t offer.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href="/methodology" className="text-sm font-semibold text-emerald-700 underline">
              How our solver works →
            </Link>
            <span className="text-zinc-300">·</span>
            <Link href="/about" className="text-sm font-semibold text-emerald-700 underline">
              Meet the team →
            </Link>
            <span className="text-zinc-300">·</span>
            <Link href="/pricing" className="text-sm font-semibold text-emerald-700 underline">
              See pricing →
            </Link>
          </div>
        </div>
      </section>

      {/* Blog teaser */}
      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-bold">Learn GTO — Free Strategy Blog</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">Solver-backed guides: GTO fundamentals, preflop mastery, leak fixes, and honest tool comparisons. Every article links to interactive Lab tools.</p>
          </div>
          <Link href="/blog" className="hidden rounded-full border border-zinc-300 bg-white px-5 py-2 text-sm font-semibold hover:bg-zinc-50 md:inline-flex">View All Articles →</Link>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <Link href="/blog/what-is-gto-poker-complete-guide" className="rounded-xl border border-zinc-200 bg-white p-5 hover:border-emerald-300 hover:shadow-sm">
            <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-700">GTO Fundamentals</span>
            <h3 className="mt-2 text-sm font-bold leading-tight">What is GTO Poker? Complete Beginner's Guide</h3>
            <p className="mt-1 text-xs leading-5 text-zinc-600">Nash equilibrium, why solvers fold 30% on Q72r, and how to study GTO without memorizing 10k charts.</p>
          </Link>
          <Link href="/blog/ai-poker-bot-vs-gto-solver-difference" className="rounded-xl border border-zinc-200 bg-white p-5 hover:border-emerald-300 hover:shadow-sm">
            <span className="rounded-full bg-violet-100 px-2 py-1 text-xs font-bold text-violet-700">AI Poker</span>
            <h3 className="mt-2 text-sm font-bold leading-tight">AI Poker Bot vs GTO Solver: What's the Difference?</h3>
            <p className="mt-1 text-xs leading-5 text-zinc-600">Why training with a solver beats cheating — and how Lab gives you the edge without risking your account.</p>
          </Link>
          <Link href="/blog/gto-preflop-charts-how-to-study" className="rounded-xl border border-zinc-200 bg-white p-5 hover:border-emerald-300 hover:shadow-sm">
            <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-bold text-amber-800">Preflop Strategy</span>
            <h3 className="mt-2 text-sm font-bold leading-tight">GTO Preflop Charts: How to Study Like a Pro</h3>
            <p className="mt-1 text-xs leading-5 text-zinc-600">How to read range grids, why BTN opens 48% and UTG only 15%, and how to drill ranges until automatic.</p>
          </Link>
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <Link href="/blog/5-biggest-leaks-microstakes-players" className="rounded-full border border-zinc-200 bg-white px-3 py-1.5 font-medium hover:bg-zinc-50">5 Biggest Microstakes Leaks →</Link>
          <Link href="/blog/how-to-defend-vs-cbets-gto-frequencies" className="rounded-full border border-zinc-200 bg-white px-3 py-1.5 font-medium hover:bg-zinc-50">Defend vs C-Bets →</Link>
          <Link href="/blog/best-poker-study-tools-2026-comparison" className="rounded-full border border-zinc-200 bg-white px-3 py-1.5 font-medium hover:bg-zinc-50">Best Study Tools 2026 →</Link>
        </div>
        <div className="mt-4 md:hidden">
          <Link href="/blog" className="text-sm font-semibold text-emerald-700 underline">View all articles →</Link>
        </div>
      </section>

      {/* Preflop chart quick links */}
      <section className="border-y border-zinc-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <h2 className="text-lg font-bold">Free GTO Preflop Charts — Every Position & Stack</h2>
          <p className="mt-1 text-sm text-zinc-600">24 interactive charts (6 positions × 4 stacks) — hover for frequencies and EV. Pre-computed with TexasSolver.</p>
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
              <Link key={label} href={href} className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 hover:border-emerald-300 hover:bg-white">
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
        <h2 className="text-2xl font-bold">Ready to be unbeatable?</h2>
        <p className="mt-2 text-sm text-zinc-600">Open the Lab, paste a hand, see your leaks in seconds.</p>
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
