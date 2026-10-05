import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { blogPosts, getPostBySlug, getRelatedPosts } from "@/lib/content/blogPosts";
import EmailCapture from "@/components/marketing/EmailCapture";
import BlogViewTracker from "@/components/analytics/BlogViewTracker";

export const revalidate = 86400;

export function generateStaticParams() {
  return blogPosts.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) return {};
  const canonical = `https://aipokerlab.com/blog/${post.slug}`;
  return {
    title: post.title,
    description: post.description,
    keywords: post.keywords,
    alternates: { canonical },
    openGraph: {
      title: post.title,
      description: post.description,
      url: canonical,
      type: "article",
      publishedTime: post.date,
      modifiedTime: post.updatedAt,
      authors: [post.author],
      images: [{ url: "/og-image.png", width: 1200, height: 630, alt: post.title }],
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.description,
    },
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) notFound();
  const related = getRelatedPosts(slug);
  const canonical = `https://aipokerlab.com/blog/${post.slug}`;

  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.description,
    author: { "@type": "Person", name: post.author },
    publisher: {
      "@type": "Organization",
      name: "AI Poker Lab",
      logo: { "@type": "ImageObject", url: "https://aipokerlab.com/icon-512.png" },
    },
    datePublished: post.date,
    dateModified: post.updatedAt,
    mainEntityOfPage: canonical,
    keywords: post.keywords.join(", "),
    articleSection: post.category,
    wordCount: post.content.split(/\s+/).length,
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: "https://aipokerlab.com/" },
      { "@type": "ListItem", position: 2, name: "Blog", item: "https://aipokerlab.com/blog" },
      { "@type": "ListItem", position: 3, name: post.title, item: canonical },
    ],
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }} />
      <BlogViewTracker slug={post.slug} category={post.category} title={post.title} />

      <div className="mx-auto max-w-4xl px-6 py-8">
        {/* Breadcrumb */}
        <nav className="mb-4 text-xs text-zinc-500">
          <Link href="/" className="underline hover:text-zinc-700">Home</Link> {" / "}
          <Link href="/blog" className="underline hover:text-zinc-700">Blog</Link> {" / "}
          <span className="font-semibold text-zinc-700">{post.category}</span>
        </nav>

        {/* Header */}
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-emerald-100 px-3 py-1 font-bold text-emerald-700">{post.category}</span>
          <span className="text-zinc-500">{post.date} · {post.readTime}</span>
          <span className="text-zinc-400">· Updated {post.updatedAt}</span>
        </div>
        <h1 className="text-3xl font-extrabold leading-tight tracking-tight md:text-4xl">{post.title}</h1>
        <p className="mt-3 text-lg leading-7 text-zinc-600">{post.excerpt}</p>

        {/* Author */}
        <div className="mt-6 flex items-center gap-3 rounded-xl border border-zinc-200 bg-white p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-600 text-sm font-bold text-white">
            {post.author.split(" ").map((w) => w[0]).join("")}
          </div>
          <div>
            <p className="text-sm font-bold">{post.author}</p>
            <p className="text-xs text-zinc-500">{post.authorRole}</p>
          </div>
          <div className="ml-auto hidden gap-2 md:flex">
            <a href={`https://twitter.com/intent/tweet?url=${encodeURIComponent(canonical)}&text=${encodeURIComponent(post.title)}`} target="_blank" rel="noopener noreferrer" className="rounded-full border border-zinc-200 px-3 py-1.5 text-xs font-semibold hover:bg-zinc-50">Share on X</a>
            <a href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(canonical)}`} target="_blank" rel="noopener noreferrer" className="rounded-full border border-zinc-200 px-3 py-1.5 text-xs font-semibold hover:bg-zinc-50">Share on Facebook</a>
          </div>
        </div>

        {/* TOC */}
        <div className="mt-6 rounded-xl border border-zinc-200 bg-zinc-50 p-5">
          <h2 className="text-sm font-bold tracking-wide text-zinc-700">TABLE OF CONTENTS</h2>
          <ol className="mt-3 space-y-1.5">
            {post.toc.map((item, i) => (
              <li key={item.id}>
                <a href={`#${item.id}`} className="text-sm font-medium text-emerald-700 hover:underline">
                  {i + 1}. {item.title}
                </a>
              </li>
            ))}
          </ol>
        </div>

        {/* Article content */}
        <article
          className="prose prose-zinc mt-8 max-w-none prose-headings:font-bold prose-h2:mt-10 prose-h2:text-xl prose-h2:tracking-tight prose-h3:mt-6 prose-h3:text-base prose-p:leading-7 prose-p:text-zinc-700 prose-a:font-semibold prose-a:text-emerald-700 prose-a:underline prose-li:text-zinc-700 prose-table:text-sm prose-th:bg-zinc-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:text-xs prose-th:font-bold prose-td:px-3 prose-td:py-2 prose-td:text-sm prose-blockquote:border-l-emerald-500 prose-blockquote:bg-emerald-50 prose-blockquote:px-4 prose-blockquote:py-2"
          dangerouslySetInnerHTML={{ __html: post.content }}
        />

        {/* Inline email capture */}
        <div className="mt-8">
          <EmailCapture variant="inline" source={`blog_inline_${post.slug}`} />
        </div>

        {/* Author bio */}
        <div className="mt-10 rounded-xl border border-zinc-200 bg-white p-6">
          <div className="flex gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-sm font-bold text-white">
              {post.author.split(" ").map((w) => w[0]).join("")}
            </div>
            <div>
              <h3 className="text-sm font-bold">{post.author}</h3>
              <p className="text-xs font-semibold text-emerald-700">{post.authorRole}</p>
              <p className="mt-2 text-sm leading-6 text-zinc-600">
                {post.author === "Alex Rivera" && "Alex spent 8 years as a mid-stakes 6-max reg before building Lab. He solved 30k+ spots with PioSolver and TexasSolver to build our pre-computed DB. Every coaching prompt is reviewed against his hand database."}
                {post.author === "Dr. Priya Chen" && "Priya built the hybrid solver pipeline and grounded coaching engine. Her research on exploitability-bounded solving keeps Lab AI honest — every explanation is tied to solver JSON, never hallucinated."}
                {post.author === "Marcus Cole" && "Marcus maintains the solver abstraction layer and nightly batch pipeline. He validates every pre-computed spot against PioSolver within 1% frequency delta."}
              </p>
            </div>
          </div>
        </div>

        {/* Related posts */}
        {related.length > 0 && (
          <div className="mt-10">
            <h2 className="text-lg font-bold">Related Articles</h2>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {related.map((r) => (
                <Link key={r.slug} href={`/blog/${r.slug}`} className="rounded-xl border border-zinc-200 bg-white p-5 hover:border-emerald-300 hover:shadow-sm">
                  <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">{r.category}</span>
                  <h3 className="mt-2 text-sm font-bold leading-tight">{r.title}</h3>
                  <p className="mt-1 text-xs leading-5 text-zinc-600">{r.excerpt}</p>
                  <p className="mt-2 text-xs font-bold text-emerald-700">Read →</p>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* CTA */}
        <div className="mt-10 rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
          <h2 className="text-xl font-bold">Practice what you just learned</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-zinc-700">Open the Lab and turn knowledge into skill — preflop charts, replayer, and drills are free to try.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Link href="/lab/preflop" className="rounded-full bg-emerald-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-emerald-700">Browse Preflop Charts</Link>
            <Link href="/dashboard" className="rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-sm font-semibold hover:bg-zinc-50">Open Lab</Link>
          </div>
        </div>

        {/* End-of-post email capture */}
        <div className="mt-8">
          <EmailCapture variant="inline" source={`blog_end_${post.slug}`} title="Enjoyed this article? Get weekly GTO tips" description="Free preflop charts + leak fixes delivered weekly. No spam." />
        </div>

        {/* Social share bottom */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3 border-t border-zinc-200 pt-6">
          <span className="text-xs font-semibold text-zinc-500">Share this article:</span>
          <a href={`https://twitter.com/intent/tweet?url=${encodeURIComponent(canonical)}&text=${encodeURIComponent(post.title)}`} target="_blank" rel="noopener noreferrer" className="rounded-full bg-zinc-900 px-4 py-2 text-xs font-bold text-white hover:bg-zinc-800">Share on X</a>
          <a href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(canonical)}`} target="_blank" rel="noopener noreferrer" className="rounded-full border border-zinc-300 bg-white px-4 py-2 text-xs font-semibold hover:bg-zinc-50">Share on Facebook</a>
          <a href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(canonical)}`} target="_blank" rel="noopener noreferrer" className="rounded-full border border-zinc-300 bg-white px-4 py-2 text-xs font-semibold hover:bg-zinc-50">Share on LinkedIn</a>
        </div>

        <div className="mt-6 text-center">
          <Link href="/blog" className="text-sm font-semibold text-emerald-700 underline">← Back to all articles</Link>
        </div>
      </div>
    </>
  );
}
