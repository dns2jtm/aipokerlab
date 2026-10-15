import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import StaticRangeGrid from "@/components/replayer/StaticRangeGrid";
import EmailCapture from "@/components/marketing/EmailCapture";
import PreflopTracker from "@/components/analytics/PreflopTracker";
import { getPreflopRange, type Position, type StackDepth } from "@/lib/solver/mockPreflop";
import {
  getPreflopSeoContent,
  ALL_POSITIONS,
  ALL_STACKS,
  POSITION_LABELS,
  STACK_LABELS,
  SITE_URL,
  type PositionKey,
  type StackKey,
} from "@/lib/seo/preflopContent";

export const revalidate = 86400;

const VALID_POSITIONS = new Set(ALL_POSITIONS);
const VALID_STACKS = new Set(ALL_STACKS);

export function generateStaticParams() {
  const params: { position: string; stack: string }[] = [];
  for (const pos of ALL_POSITIONS) {
    for (const stack of ALL_STACKS) {
      params.push({ position: pos, stack });
    }
  }
  return params;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ position: string; stack: string }>;
}): Promise<Metadata> {
  const { position, stack } = await params;
  if (!VALID_POSITIONS.has(position as PositionKey) || !VALID_STACKS.has(stack as StackKey)) {
    return {};
  }
  const seo = getPreflopSeoContent(position as PositionKey, stack as StackKey);
  const canonical = `${SITE_URL}/lab/preflop/${position}/${stack}`;
  return {
    title: seo.title,
    description: seo.description,
    keywords: seo.keywords,
    alternates: { canonical },
    openGraph: {
      title: seo.title,
      description: seo.description,
      url: canonical,
      type: "website",
      images: [{ url: "/og-image.png", width: 1200, height: 630, alt: seo.h1 }],
    },
    twitter: {
      card: "summary_large_image",
      title: seo.title,
      description: seo.description,
    },
  };
}

function toSolverPosition(pos: PositionKey): Position {
  return POSITION_LABELS[pos] as Position;
}

function toSolverStack(stack: StackKey): StackDepth {
  return STACK_LABELS[stack] as StackDepth;
}

export default async function PreflopChartPage({
  params,
}: {
  params: Promise<{ position: string; stack: string }>;
}) {
  const { position: posParam, stack: stackParam } = await params;
  if (!VALID_POSITIONS.has(posParam as PositionKey) || !VALID_STACKS.has(stackParam as StackKey)) {
    notFound();
  }
  const pos = posParam as PositionKey;
  const stack = stackParam as StackKey;
  const seo = getPreflopSeoContent(pos, stack);
  const solverPos = toSolverPosition(pos);
  const solverStack = toSolverStack(stack);
  const range = getPreflopRange(solverPos, solverStack);

  const raiseCount = range.filter((h) => h.primary === "raise").length;
  const callCount = range.filter((h) => h.primary === "call").length;
  const foldCount = range.filter((h) => h.primary === "fold").length;
  const total = range.length;
  const raisePct = ((raiseCount / total) * 100).toFixed(1);
  const callPct = ((callCount / total) * 100).toFixed(1);
  const foldPct = ((foldCount / total) * 100).toFixed(1);

  // Top 5 raises by EV
  const topRaises = [...range]
    .filter((h) => h.primary === "raise")
    .sort((a, b) => b.ev - a.ev)
    .slice(0, 5);

  const canonical = `${SITE_URL}/lab/preflop/${pos}/${stack}`;

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Preflop Lab", item: `${SITE_URL}/lab/preflop` },
      { "@type": "ListItem", position: 3, name: POSITION_LABELS[pos], item: `${SITE_URL}/lab/preflop/${pos}` },
      { "@type": "ListItem", position: 4, name: `${POSITION_LABELS[pos]} ${STACK_LABELS[stack]}`, item: canonical },
    ],
  };

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: seo.faq.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />
      <PreflopTracker position={pos} stack={stack} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />

      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* Breadcrumb */}
        <nav className="mb-4 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">Home</Link>
          {" / "}
          <Link href="/lab/preflop" className="underline hover:text-zinc-700">Preflop Lab</Link>
          {" / "}
          <Link href={`/lab/preflop/${pos}`} className="underline hover:text-zinc-700">{POSITION_LABELS[pos]}</Link>
          {" / "}
          <span className="font-semibold text-zinc-700">{STACK_LABELS[stack]}</span>
        </nav>

        {/* H1 */}
        <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">{seo.h1}</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">{seo.intro}</p>

        {/* Quick stats */}
        <div className="mt-6 grid grid-cols-3 gap-3 md:max-w-xl">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
            <p className="text-2xl font-extrabold text-emerald-700">{raisePct}%</p>
            <p className="text-xs font-semibold text-emerald-700">Raise ({raiseCount})</p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-center">
            <p className="text-2xl font-extrabold text-amber-700">{callPct}%</p>
            <p className="text-xs font-semibold text-amber-700">Call ({callCount})</p>
          </div>
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-center">
            <p className="text-2xl font-extrabold text-red-700">{foldPct}%</p>
            <p className="text-xs font-semibold text-red-700">Fold ({foldCount})</p>
          </div>
        </div>

        {/* Range Grid */}
        <div className="mt-8 rounded-xl border border-zinc-200 bg-white p-4 md:p-6">
          <h2 className="mb-4 text-sm font-bold tracking-wide text-zinc-700">
            Interactive Range Grid — {POSITION_LABELS[pos]} {STACK_LABELS[stack]} · 6-max · Hover for frequencies
          </h2>
          <StaticRangeGrid position={solverPos} stack={solverStack} />
        </div>

        {/* GTO Stats Table */}
        <div className="mt-8 rounded-xl border border-zinc-200 bg-white p-6">
          <h2 className="text-lg font-bold">GTO Stats — {POSITION_LABELS[pos]} {STACK_LABELS[stack]}</h2>
          <p className="mt-1 text-xs text-zinc-500">Hybrid O(1) spotHash DB + Rust Linear MCCFR · Rake 5% cap $3 · 6-max</p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold tracking-wide text-zinc-500">
                  <th className="py-2">Action</th>
                  <th className="py-2">Hands</th>
                  <th className="py-2">Frequency</th>
                  <th className="py-2">Avg EV (bb)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                <tr>
                  <td className="py-2.5"><span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">Raise</span></td>
                  <td className="py-2.5 font-medium">{raiseCount} / {total}</td>
                  <td className="py-2.5 font-bold text-emerald-700">{raisePct}%</td>
                  <td className="py-2.5 text-zinc-600">{(range.filter((h) => h.primary === "raise").reduce((s, h) => s + h.ev, 0) / Math.max(1, raiseCount)).toFixed(2)} bb</td>
                </tr>
                <tr>
                  <td className="py-2.5"><span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">Call</span></td>
                  <td className="py-2.5 font-medium">{callCount} / {total}</td>
                  <td className="py-2.5 font-bold text-amber-700">{callPct}%</td>
                  <td className="py-2.5 text-zinc-600">{(range.filter((h) => h.primary === "call").reduce((s, h) => s + h.ev, 0) / Math.max(1, callCount)).toFixed(2)} bb</td>
                </tr>
                <tr>
                  <td className="py-2.5"><span className="rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">Fold</span></td>
                  <td className="py-2.5 font-medium">{foldCount} / {total}</td>
                  <td className="py-2.5 font-bold text-red-700">{foldPct}%</td>
                  <td className="py-2.5 text-zinc-600">{(range.filter((h) => h.primary === "fold").reduce((s, h) => s + h.ev, 0) / Math.max(1, foldCount)).toFixed(2)} bb</td>
                </tr>
              </tbody>
            </table>
          </div>
          {topRaises.length > 0 && (
            <div className="mt-4">
              <h3 className="text-xs font-bold tracking-wide text-zinc-500">TOP 5 RAISES BY EV</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {topRaises.map((h) => (
                  <span key={h.hand} className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
                    {h.hand} <span className="font-normal text-emerald-600">+{h.ev}bb</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Strategy */}
        <div className="mt-8 rounded-xl border border-zinc-200 bg-white p-6">
          <h2 className="text-lg font-bold">How to Play {POSITION_LABELS[pos]} at {STACK_LABELS[stack]}</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-600">{seo.strategy}</p>
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm leading-6 text-emerald-900">{seo.tip}</p>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link href="/dashboard" className="rounded-full bg-emerald-600 px-5 py-2 text-sm font-bold text-white hover:bg-emerald-700">Drill This Range →</Link>
            <Link href="/replayer" className="rounded-full border border-zinc-300 bg-white px-5 py-2 text-sm font-semibold hover:bg-zinc-50">Analyze Your Hands</Link>
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-8 rounded-xl border border-zinc-200 bg-white p-6">
          <h2 className="text-lg font-bold">FAQ — {POSITION_LABELS[pos]} {STACK_LABELS[stack]} GTO Chart</h2>
          <div className="mt-4 space-y-5">
            {seo.faq.map((f) => (
              <div key={f.q}>
                <h3 className="text-sm font-bold text-zinc-900">{f.q}</h3>
                <p className="mt-1 text-sm leading-6 text-zinc-600">{f.a}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Internal links — other stacks for same position */}
        <div className="mt-8 rounded-xl border border-zinc-200 bg-zinc-50 p-6">
          <h2 className="text-sm font-bold tracking-wide text-zinc-700">Other Stack Depths for {POSITION_LABELS[pos]}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {ALL_STACKS.filter((s) => s !== stack).map((s) => (
              <Link key={s} href={`/lab/preflop/${pos}/${s}`} className="rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold hover:bg-zinc-50">
                {POSITION_LABELS[pos]} {STACK_LABELS[s]} →
              </Link>
            ))}
          </div>
          <h3 className="mt-6 text-sm font-bold tracking-wide text-zinc-700">Other Positions at {STACK_LABELS[stack]}</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {ALL_POSITIONS.filter((p) => p !== pos).map((p) => (
              <Link key={p} href={`/lab/preflop/${p}/${stack}`} className="rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold hover:bg-zinc-50">
                {POSITION_LABELS[p]} {STACK_LABELS[stack]} →
              </Link>
            ))}
          </div>
          <div className="mt-6 flex flex-wrap gap-3 text-sm">
            <Link href="/lab/preflop" className="font-semibold text-emerald-700 underline">All Preflop Charts →</Link>
            <span className="text-zinc-300">·</span>
            <Link href="/blog" className="font-semibold text-emerald-700 underline">Poker Strategy Blog →</Link>
            <span className="text-zinc-300">·</span>
            <Link href="/methodology" className="font-semibold text-emerald-700 underline">How Our Solver Works →</Link>
          </div>
        </div>

        <div className="mt-8">
          <EmailCapture variant="inline" source={`preflop_${pos}_${stack}`} title="Get all 24 GTO charts + weekly tips" description="Free preflop charts and leak fixes — no spam." />
        </div>

        {/* ToS banner */}
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-center text-xs leading-5 text-amber-800">
          <strong>Training only</strong> — not for use during play. Compliant with PokerStars / GGPoker ToS. Post-hand study only. Using solvers during live play risks account bans.
        </div>
      </div>
    </>
  );
}
