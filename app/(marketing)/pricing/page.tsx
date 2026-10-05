import type { Metadata } from "next";
import Link from "next/link";
import { PLANS, PLAN_ORDER } from "@/lib/billing/plans";

export const metadata: Metadata = {
  title: "Pricing — Free to Elite, Lab Beats GTO Wizard",
  description:
    "AI Poker Lab pricing: Free, Starter $19, Pro $49, Elite $99. Compare vs GTO Wizard. Unlimited GTO coaching, leak-to-drill loop, ToS-compliant training.",
  alternates: { canonical: "https://aipokerlab.com/pricing" },
  openGraph: {
    title: "Pricing — AI Poker Lab",
    description: "Free to Elite. The GTO coach that closes the loop — leak → drill → improvement.",
    url: "https://aipokerlab.com/pricing",
    type: "website",
  },
};

const pricingJsonLd = {
  "@context": "https://schema.org",
  "@type": "Product",
  name: "AI Poker Lab",
  description: "GTO poker training with AI coach, leak detection, and drills. ToS-compliant.",
  brand: { "@type": "Brand", name: "AI Poker Lab" },
  offers: PLAN_ORDER.map((id) => {
    const p = PLANS[id];
    return {
      "@type": "Offer",
      name: p.name,
      price: String(p.priceMonthly),
      priceCurrency: "USD",
      availability: "https://schema.org/InStock",
      url: "https://aipokerlab.com/pricing",
      priceValidUntil: "2026-12-31",
    };
  }),
};

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "How does AI Poker Lab compare to GTO Wizard pricing?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "GTO Wizard Premium is ~$49/mo for solver viewing. Lab Pro is also $49/mo but adds AI coaching, 12-leak detection with bb/100, and auto drills — the closed loop GTO Wizard doesn't have. Starter at $19/mo is our entry paid tier.",
      },
    },
    {
      "@type": "Question",
      name: "Is there a free plan?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Yes. Free includes 5 hand reviews/day, pre-computed solver (5/day), 3 drills/month, and basic AI Coach. No card required.",
      },
    },
    {
      "@type": "Question",
      name: "Can I cancel anytime?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Yes. Cancel via Stripe Customer Portal from /billing. No dark patterns, no retention tricks. Refunds per our Terms.",
      },
    },
    {
      "@type": "Question",
      name: "What are solver credits?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "On-demand solves for spots not in the pre-computed DB. Free: 5/day, Starter: 50/day, Pro: 100/day, Elite: unlimited + priority queue. Pre-computed hits are instant and don't count against on-demand limits beyond the daily cap.",
      },
    },
  ],
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Home", item: "https://aipokerlab.com/" },
    { "@type": "ListItem", position: 2, name: "Pricing", item: "https://aipokerlab.com/pricing" },
  ],
};

export default function PricingPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(pricingJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />

      <div className="mx-auto max-w-6xl px-6 py-12">
        <nav className="mb-6 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">
            Home
          </Link>{" "}
          / Pricing
        </nav>

        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">Simple pricing. Serious coaching.</h1>
          <p className="mt-3 text-sm leading-6 text-zinc-600">
            Free to start, $19 to grind, $49 for the full Lab. No hidden fees. Cancel anytime via Stripe. ToS-compliant
            training only.
          </p>
          <p className="mt-2 text-xs text-zinc-500">All prices USD / month. Billed monthly. No annual lock-in.</p>
        </div>

        {/* Plan cards */}
        <div className="mt-10 grid gap-6 md:grid-cols-4">
          {PLAN_ORDER.map((id) => {
            const p = PLANS[id];
            return (
              <div
                key={p.id}
                className={`flex flex-col rounded-2xl border p-6 ${p.highlighted ? "border-emerald-300 bg-emerald-50 shadow-sm" : "border-zinc-200 bg-white"}`}
              >
                {p.highlighted && (
                  <span className="mb-3 inline-flex w-fit rounded-full bg-emerald-600 px-2.5 py-1 text-xs font-bold text-white">
                    Most popular
                  </span>
                )}
                <h2 className="text-lg font-bold">{p.name}</h2>
                <p className="mt-1 text-xs text-zinc-600">{p.description}</p>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="text-3xl font-extrabold">${p.priceMonthly}</span>
                  <span className="text-sm text-zinc-500">/month</span>
                </div>
                <ul className="mt-4 flex-1 space-y-2 text-sm leading-6 text-zinc-700">
                  <li>• {String(p.features.analysesPerMonth)} analyses</li>
                  <li>• {String(p.features.solverAccess)}</li>
                  <li>• {String(p.features.drills)}</li>
                  <li>• Sparring: {String(p.features.sparring) || "—"}</li>
                  <li>• Coach: {String(p.features.coach)}</li>
                  <li>• Upload: {String(p.features.handHistoryUpload)}</li>
                </ul>
                <Link
                  href={p.id === "free" ? "/dashboard" : "/billing"}
                  className={`mt-6 inline-flex justify-center rounded-full px-5 py-2.5 text-sm font-bold ${p.highlighted ? "bg-emerald-600 text-white hover:bg-emerald-700" : "border border-zinc-300 bg-white hover:bg-zinc-50"}`}
                >
                  {p.cta}
                </Link>
              </div>
            );
          })}
        </div>

        {/* Feature comparison table */}
        <div className="mt-12 overflow-x-auto rounded-xl border border-zinc-200 bg-white">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b bg-zinc-50 text-left text-xs font-semibold tracking-wide text-zinc-500">
                <th className="px-4 py-3">Feature</th>
                <th className="px-4 py-3">Free</th>
                <th className="px-4 py-3">Starter $19</th>
                <th className="px-4 py-3 text-emerald-700">Pro $49</th>
                <th className="px-4 py-3">Elite $99</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {[
                ["Hand reviews / month", "5/day", "100", "Unlimited", "Unlimited"],
                ["Solver (pre-computed)", "5/day", "50/day", "100/day", "Unlimited + priority"],
                ["On-demand solves", "—", "20/day", "100/day", "Unlimited"],
                ["Drills / month", "3", "50", "Unlimited", "Unlimited + custom"],
                ["Leak detection (12 leaks)", "✓", "✓", "✓", "✓ + trends"],
                ["AI Coach", "Basic", "Full", "Full + history", "Full + voice (soon)"],
                ["Sparring bot", "—", "Flop only", "Preflop + flop", "Full + exploitative"],
                ["Hand history upload", "5/day", "Unlimited", "Unlimited", "Unlimited + API"],
                ["Stripe portal & cancel", "—", "✓", "✓", "✓"],
              ].map(([f, a, b, c, d]) => (
                <tr key={f}>
                  <td className="px-4 py-2.5 font-medium">{f}</td>
                  <td className="px-4 py-2.5 text-zinc-600">{a}</td>
                  <td className="px-4 py-2.5 text-zinc-600">{b}</td>
                  <td className="px-4 py-2.5 font-semibold text-emerald-700">{c}</td>
                  <td className="px-4 py-2.5 text-zinc-600">{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* vs GTO Wizard */}
        <div className="mt-10 rounded-2xl border border-zinc-200 bg-white p-6 md:p-8">
          <h2 className="text-lg font-bold">Lab vs GTO Wizard — Pricing & Value</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-600">
            GTO Wizard Premium is ~$49/mo for solver viewing and basic stats. Lab Pro is also $49/mo — but you get the
            coach, the leak-to-drill loop, and personalized memory. Same price, more improvement.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold tracking-wide text-zinc-500">
                  <th className="py-2">Feature</th>
                  <th className="py-2">GTO Wizard (~$49)</th>
                  <th className="py-2 text-emerald-700">Lab Pro ($49)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {[
                  ["Solver viewer", "✓", "✓"],
                  ["AI explains WHY", "—", "✓ streaming, grounded"],
                  ["Leak detection (bb/100)", "Basic", "12 leaks + EV loss"],
                  ["Auto drills from leaks", "—", "✓ spaced repetition"],
                  ["Personalized memory", "—", "✓"],
                  ["ToS training-only banner", "—", "✓ everywhere"],
                ].map(([a, b, c]) => (
                  <tr key={a}>
                    <td className="py-2 font-medium">{a}</td>
                    <td className="py-2 text-zinc-600">{b}</td>
                    <td className="py-2 font-semibold text-emerald-700">{c}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-zinc-500">
            GTO Wizard pricing as of Oct 2025, for comparison only. GTO Wizard is a trademark of its owner.
          </p>
        </div>

        {/* FAQ */}
        <section className="mx-auto mt-10 max-w-3xl rounded-2xl border border-zinc-200 bg-zinc-50 p-6 md:p-8">
          <h2 className="text-lg font-bold">Pricing FAQ</h2>
          <div className="mt-4 space-y-4">
            {[
              {
                q: "Is there a free plan?",
                a: "Yes. Free includes 5 hand reviews/day, pre-computed solver (5/day), 3 drills/month, and basic AI Coach. No card required. Upgrade anytime from /billing.",
              },
              {
                q: "Can I cancel anytime?",
                a: "Yes. Cancel via Stripe Customer Portal from /billing. No dark patterns. Refunds per our Terms of Service.",
              },
              {
                q: "What are solver credits?",
                a: "On-demand solves for spots not in the pre-computed DB. Free: 5/day, Starter: 50/day, Pro: 100/day, Elite: unlimited + priority queue. Pre-computed hits are instant.",
              },
              {
                q: "Do you offer annual billing?",
                a: "Not yet — monthly only for now. Annual with discount is on the roadmap. Contact us if you need invoicing.",
              },
              {
                q: "Is my hand history private?",
                a: "Yes. Hands never train our models without opt-in. See Privacy Policy. You can delete everything at any time.",
              },
            ].map((f) => (
              <div key={f.q} className="rounded-lg border border-zinc-200 bg-white p-4">
                <h3 className="text-sm font-bold">{f.q}</h3>
                <p className="mt-1 text-sm leading-6 text-zinc-600">{f.a}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-8 text-center">
          <Link
            href="/dashboard"
            className="inline-flex rounded-full bg-emerald-600 px-8 py-3 text-sm font-bold text-white hover:bg-emerald-700"
          >
            Start free — no card required
          </Link>
          <p className="mt-3 text-xs text-zinc-500">
            Questions?{" "}
            <Link href="/contact" className="underline">
              Contact us
            </Link>{" "}
            ·{" "}
            <Link href="/about" className="underline">
              About
            </Link>{" "}
            ·{" "}
            <Link href="/methodology" className="underline">
              Methodology
            </Link>
          </p>
        </div>
      </div>
    </>
  );
}
