import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ALL_POSITIONS,
  ALL_STACKS,
  POSITION_LABELS,
  POSITION_FULL,
  STACK_LABELS,
  SITE_URL,
  type PositionKey,
} from "@/lib/seo/preflopContent";

export const revalidate = 86400;

const VALID = new Set(ALL_POSITIONS);

export function generateStaticParams() {
  return ALL_POSITIONS.map((position) => ({ position }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ position: string }>;
}): Promise<Metadata> {
  const { position } = await params;
  if (!VALID.has(position as PositionKey)) return {};
  const label = POSITION_LABELS[position as PositionKey];
  const full = POSITION_FULL[position as PositionKey];
  const canonical = `${SITE_URL}/lab/preflop/${position}`;
  return {
    title: `GTO Preflop Charts ${label} (${full}) — All Stack Depths | AI Poker Lab`,
    description: `Free GTO preflop charts for ${label} (${full}) — all stack depths (20bb, 40bb, 100bb, 200bb). 6-max, rake 5% cap $3. Interactive range grids, frequencies, and EV.`,
    keywords: [`gto preflop chart ${label.toLowerCase()}`, `${label.toLowerCase()} preflop range`, `gto ${label.toLowerCase()} range`, "preflop charts gto"],
    alternates: { canonical },
    openGraph: {
      title: `GTO Preflop Charts ${label} — All Stacks | AI Poker Lab`,
      description: `Browse all GTO preflop charts for ${label} (${full}) at every stack depth.`,
      url: canonical,
      type: "website",
    },
  };
}

export default async function PositionPage({
  params,
}: {
  params: Promise<{ position: string }>;
}) {
  const { position: posParam } = await params;
  if (!VALID.has(posParam as PositionKey)) notFound();
  const pos = posParam as PositionKey;
  const label = POSITION_LABELS[pos];
  const full = POSITION_FULL[pos];
  const canonical = `${SITE_URL}/lab/preflop/${pos}`;

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Preflop Lab", item: `${SITE_URL}/lab/preflop` },
      { "@type": "ListItem", position: 3, name: label, item: canonical },
    ],
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />

      <div className="mx-auto max-w-6xl px-6 py-8">
        <nav className="mb-4 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">Home</Link> {" / "}
          <Link href="/lab/preflop" className="underline hover:text-zinc-700">Preflop Lab</Link> {" / "}
          <span className="font-semibold text-zinc-700">{label}</span>
        </nav>

        <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">
          GTO Preflop Charts: {label} ({full}) — All Stack Depths
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">
          Browse every GTO preflop chart for <strong>{label} ({full})</strong> at 6-max — from short-stack 20bb to deep 200bb.
          Each chart shows raise/call/fold frequencies for all 169 hands, EV, and study tips. Pick your stack depth below.
          All charts are pre-computed with TexasSolver (0.5% exploitability, rake 5% cap $3) and free to study.
        </p>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {ALL_STACKS.map((stack) => (
            <Link
              key={stack}
              href={`/lab/preflop/${pos}/${stack}`}
              className="group rounded-xl border border-zinc-200 bg-white p-6 hover:border-emerald-300 hover:shadow-sm"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold group-hover:text-emerald-700">
                  {label} {STACK_LABELS[stack]}
                </h2>
                <span className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-bold text-white group-hover:bg-emerald-600">View Chart →</span>
              </div>
              <p className="mt-2 text-sm leading-6 text-zinc-600">
                {stack === "20" && "Short-stack push/fold territory — maximize fold equity, avoid dominated calls."}
                {stack === "40" && "Mid-stack zone — postflop play with reduced implied odds. Tighten speculative hands."}
                {stack === "100" && "Standard cash depth — the baseline every serious student should master first."}
                {stack === "200" && "Deep-stacked — huge implied odds but reverse implied odds punish dominated hands."}
              </p>
              <p className="mt-3 text-xs font-medium text-emerald-700">Interactive grid + GTO stats + FAQ →</p>
            </Link>
          ))}
        </div>

        <div className="mt-8 rounded-xl border border-zinc-200 bg-zinc-50 p-6">
          <h2 className="text-sm font-bold tracking-wide text-zinc-700">Other Positions</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {ALL_POSITIONS.filter((p) => p !== pos).map((p) => (
              <Link key={p} href={`/lab/preflop/${p}`} className="rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold hover:bg-zinc-50">
                {POSITION_LABELS[p]} ({POSITION_FULL[p]}) →
              </Link>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            <Link href="/lab/preflop" className="font-semibold text-emerald-700 underline">All Preflop Charts →</Link>
            <span className="text-zinc-300">·</span>
            <Link href="/blog" className="font-semibold text-emerald-700 underline">Strategy Blog →</Link>
          </div>
        </div>
      </div>
    </>
  );
}
