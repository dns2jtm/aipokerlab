import type { Metadata } from "next";
import Link from "next/link";
import { AuthorBios } from "@/components/marketing/AuthorBio";

export const metadata: Metadata = {
  title: "About — Our Mission, Team & Why We Beat GTO Wizard",
  description:
    "Meet the team behind AI Poker Lab: poker pros + AI researchers building the ToS-compliant GTO training lab that actually coaches you. Lab, not bot.",
  alternates: { canonical: "https://aipokerlab.com/about" },
  openGraph: {
    title: "About AI Poker Lab — Lab, Not Bot",
    description: "Poker pros + AI researchers building the GTO coach that closes the loop: leak → drill → improvement.",
    url: "https://aipokerlab.com/about",
    type: "website",
  },
};

const aboutJsonLd = {
  "@context": "https://schema.org",
  "@type": "AboutPage",
  name: "About AI Poker Lab",
  url: "https://aipokerlab.com/about",
  description: "Mission, team, and ToS-compliant positioning of AI Poker Lab.",
  mainEntity: {
    "@type": "Organization",
    name: "AI Poker Lab",
    url: "https://aipokerlab.com",
    foundingDate: "2025",
    slogan: "Lab, not bot.",
    description: "ToS-compliant GTO poker training lab with AI coach, leak detection, and spaced-repetition drills.",
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
          LAB, NOT BOT — ToS-COMPLIANT TRAINING ONLY
        </p>
        <h1 className="mt-4 text-3xl font-extrabold tracking-tight md:text-4xl">About AI Poker Lab</h1>
        <p className="mt-3 max-w-2xl text-lg leading-7 text-zinc-600">
          We&apos;re poker players and AI researchers who got tired of memorizing charts. So we built the coach we
          wished existed.
        </p>

        {/* Founder story */}
        <section className="mt-10 rounded-2xl border border-zinc-200 bg-white p-6 md:p-8">
          <h2 className="text-xl font-bold">Founder Story</h2>
          <div className="mt-4 space-y-4 text-sm leading-6 text-zinc-600">
            <p>
              In 2023, Alex was grinding 6-max $1/$2 and spending $49/month on GTO Wizard. He could see frequencies —
              but not <em>why</em>. He&apos;d review a hand, nod at the chart, and make the same mistake next session.
              There was no loop.
            </p>
            <p>
              Priya, meanwhile, was finishing her PhD on game-theoretic reinforcement learning at Stanford. She&apos;d
              watched DeepMind solve poker-adjacent games and knew the solver math was solid — but the UX was built for
              researchers, not players.
            </p>
            <p>
              They met at a poker study group in San Francisco. One whiteboard later, the thesis was clear:{" "}
              <strong className="text-zinc-900">the solver is not the product — the coach is.</strong> Frequencies
              don&apos;t teach. Explanations, leak detection, and drills do.
            </p>
            <p>
              AI Poker Lab launched in 2025 with a single promise:{" "}
              <strong className="text-zinc-900">Lab, not bot.</strong> Post-hand study only. ToS-compliant with
              PokerStars and GGPoker. Training that makes <em>you</em> unbeatable — not software that plays for you.
            </p>
          </div>
        </section>

        {/* Mission */}
        <section className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            {
              title: "Mission",
              desc: "Make GTO understandable and actionable for every serious student — through coaching, not charts.",
            },
            {
              title: "Positioning",
              desc: "We are a Lab, not a bot. No real-time assistance. No ToS violations. Your account stays safe.",
            },
            {
              title: "Moat",
              desc: "Leak → Drill closed loop + personalized memory. GTO Wizard shows you the map; we walk you there.",
            },
          ].map((c) => (
            <div key={c.title} className="rounded-xl border border-zinc-200 bg-zinc-50 p-5">
              <h3 className="text-sm font-bold">{c.title}</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{c.desc}</p>
            </div>
          ))}
        </section>

        {/* Why we beat GTO Wizard */}
        <section className="mt-10">
          <h2 className="text-xl font-bold">Why We Beat GTO Wizard</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            GTO Wizard is an excellent solver viewer. Lab is a coach. Here&apos;s the difference that matters for
            improvement:
          </p>
          <div className="mt-6 overflow-x-auto rounded-xl border border-zinc-200 bg-white">
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
                  ["Solver viewer", "✓ Full", "✓ Pre-computed 90% + on-demand"],
                  ["Explains WHY (blockers, MDF, equity)", "—", "✓ Grounded coaching cards"],
                  ["Leak detection with bb/100", "Basic stats", "12 leaks + EV loss + severity"],
                  ["Auto drills from leaks", "—", "✓ Spaced repetition, leak-linked"],
                  ["Personalized memory", "—", "✓ References your past mistakes"],
                  ["Tone adaptation", "—", "✓ Concise / detailed / math-heavy"],
                  ["ToS banner everywhere", "—", "✓ Training-only, post-hand"],
                  ["Price (Pro tier)", "$49/mo", "$49/mo — but with coaching"],
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
            Comparison as of Oct 2025. GTO Wizard is a trademark of its owner; comparison for educational purposes.
          </p>
        </section>

        {/* Team */}
        <section className="mt-10">
          <h2 className="text-xl font-bold">Team</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            Poker pros + AI researchers. Every coaching card is reviewed against real solver output and real hand
            histories. No hallucinations.
          </p>
          <div className="mt-6">
            <AuthorBios />
          </div>
          <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            <strong>Editorial policy:</strong> All strategy content is reviewed by Alex (poker) and Priya (AI/solvers)
            before publishing. Solver spots are validated vs PioSolver within 1% frequency delta. Coaching prompts are
            grounded in solver JSON with temperature 0.3 — see{" "}
            <Link href="/methodology" className="underline">
              Methodology
            </Link>
            .
          </div>
        </section>

        {/* ToS positioning */}
        <section className="mt-10 rounded-2xl border border-zinc-200 bg-white p-6">
          <h2 className="text-lg font-bold">ToS-Compliant Positioning</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            AI Poker Lab is a <strong>training tool for post-hand study only</strong>. It must not be used during live
            play. Real-time solver or AI assistance violates the Terms of Service of PokerStars, GGPoker, and other
            major platforms and risks account bans and fund seizure. Lab is designed to make <em>you</em> better — not
            to play for you.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link href="/methodology" className="text-sm font-semibold text-emerald-700 underline">
              How our solver works →
            </Link>
            <Link href="/terms" className="text-sm font-semibold text-emerald-700 underline">
              Terms of Service →
            </Link>
            <Link href="/contact" className="text-sm font-semibold text-emerald-700 underline">
              Contact us →
            </Link>
          </div>
        </section>

        <p className="mt-8 text-xs text-zinc-500">
          Last updated: October 2025 · Questions?{" "}
          <Link href="/contact" className="underline">
            hello@aipokerlab.com
          </Link>
        </p>
      </div>
    </>
  );
}
