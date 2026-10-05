import type { Metadata } from "next";
import Link from "next/link";
import { blogPosts, blogCategories } from "@/lib/content/blogPosts";

export const metadata: Metadata = {
  title: "Poker Strategy Blog — GTO Guides, Leak Fixes & Solver Insights | AI Poker Lab",
  description: "Free poker strategy blog: GTO fundamentals, preflop charts, leak fixing, and solver comparisons. Learn GTO the right way with AI Poker Lab.",
  keywords: ["poker strategy blog", "gto poker blog", "poker training articles", "gto strategy guides"],
  alternates: { canonical: "https://aipokerlab.com/blog" },
  openGraph: {
    title: "Poker Strategy Blog | AI Poker Lab",
    description: "GTO guides, leak fixes, and solver insights — free poker strategy articles from AI Poker Lab.",
    url: "https://aipokerlab.com/blog",
    type: "website",
  },
};

const SITE_URL = "https://aipokerlab.com";

export default function BlogListingPage() {
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE_URL}/blog` },
    ],
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />

      <div className="mx-auto max-w-6xl px-6 py-10">
        <nav className="mb-4 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">Home</Link> {" / "} Blog
        </nav>

        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">Poker Strategy Blog</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">
              GTO fundamentals, preflop mastery, leak fixes, and honest tool comparisons — written by poker pros and AI researchers. Every article is solver-backed and linked to interactive Lab tools.
            </p>
          </div>
          <Link href="/lab/preflop" className="inline-flex shrink-0 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-emerald-700">
            Open Preflop Lab →
          </Link>
        </div>

        {/* Category filter (client-side via anchor links) */}
        <div className="mt-6 flex flex-wrap gap-2">
          <span className="rounded-full bg-zinc-900 px-3 py-1.5 text-xs font-bold text-white">All</span>
          {blogCategories.map((cat) => (
            <a key={cat} href={`#${cat.toLowerCase().replace(/\s+/g, "-")}`} className="rounded-full border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold hover:bg-zinc-50">
              {cat}
            </a>
          ))}
        </div>

        {/* Featured */}
        <div className="mt-8">
          <h2 className="text-sm font-bold tracking-wide text-zinc-500">FEATURED</h2>
          <div className="mt-3 grid gap-6 md:grid-cols-2">
            {blogPosts.filter((p) => p.featured).slice(0, 2).map((post) => (
              <Link key={post.slug} href={`/blog/${post.slug}`} className="group rounded-2xl border border-zinc-200 bg-white p-6 hover:border-emerald-300 hover:shadow-sm">
                <div className="flex items-center gap-2 text-xs">
                  <span className="rounded-full bg-emerald-100 px-2.5 py-1 font-bold text-emerald-700">{post.category}</span>
                  <span className="text-zinc-500">{post.date} · {post.readTime}</span>
                </div>
                <h3 className="mt-3 text-lg font-bold leading-tight group-hover:text-emerald-700">{post.title}</h3>
                <p className="mt-2 text-sm leading-6 text-zinc-600">{post.excerpt}</p>
                <p className="mt-3 text-xs font-semibold text-zinc-500">By {post.author} · {post.authorRole.split("—")[0].trim()}</p>
                <p className="mt-3 text-sm font-bold text-emerald-700">Read article →</p>
              </Link>
            ))}
          </div>
        </div>

        {/* All posts */}
        <div className="mt-10">
          <h2 className="text-sm font-bold tracking-wide text-zinc-500">ALL ARTICLES</h2>
          <div className="mt-4 grid gap-6 md:grid-cols-3">
            {blogPosts.map((post) => (
              <Link key={post.slug} href={`/blog/${post.slug}`} id={post.category.toLowerCase().replace(/\s+/g, "-")} className="group flex flex-col rounded-xl border border-zinc-200 bg-white p-5 hover:border-zinc-300 hover:shadow-sm">
                <div className="flex items-center gap-2 text-xs">
                  <span className="rounded-full bg-zinc-100 px-2 py-1 font-semibold text-zinc-700">{post.category}</span>
                  <span className="text-zinc-500">{post.readTime}</span>
                </div>
                <h3 className="mt-3 text-base font-bold leading-tight group-hover:text-emerald-700">{post.title}</h3>
                <p className="mt-2 flex-1 text-sm leading-6 text-zinc-600">{post.excerpt}</p>
                <div className="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3">
                  <span className="text-xs text-zinc-500">{post.date} · {post.author}</span>
                  <span className="text-xs font-bold text-emerald-700">Read →</span>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="mt-10 rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
          <h2 className="text-xl font-bold">Want to practice what you just read?</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-zinc-700">Every blog post links to interactive Lab tools — preflop charts, replayer, and drills. Open the Lab and turn knowledge into skill.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Link href="/lab/preflop" className="rounded-full bg-emerald-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-emerald-700">Browse Preflop Charts</Link>
            <Link href="/replayer" className="rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-sm font-semibold hover:bg-zinc-50">Try Replayer</Link>
          </div>
        </div>
      </div>
    </>
  );
}
