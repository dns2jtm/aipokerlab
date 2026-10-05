import type { MetadataRoute } from "next";
import { blogPosts } from "@/lib/content/blogPosts";

const SITE_URL = "https://aipokerlab.com";

const POSITIONS = ["utg", "hj", "co", "btn", "sb", "bb"] as const;
const STACKS = ["20", "40", "100", "200"] as const;

const MARKETING_PAGES = [
  { path: "", priority: 1.0, changeFrequency: "weekly" as const },
  { path: "/about", priority: 0.8, changeFrequency: "monthly" as const },
  { path: "/methodology", priority: 0.8, changeFrequency: "monthly" as const },
  { path: "/pricing", priority: 0.9, changeFrequency: "weekly" as const },
  { path: "/contact", priority: 0.5, changeFrequency: "monthly" as const },
  { path: "/privacy", priority: 0.3, changeFrequency: "yearly" as const },
  { path: "/terms", priority: 0.3, changeFrequency: "yearly" as const },
  { path: "/lab/preflop", priority: 0.9, changeFrequency: "weekly" as const },
  { path: "/replayer", priority: 0.7, changeFrequency: "weekly" as const },
  { path: "/blog", priority: 0.8, changeFrequency: "weekly" as const },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const marketing: MetadataRoute.Sitemap = MARKETING_PAGES.map((p) => ({
    url: `${SITE_URL}${p.path}`,
    lastModified: now,
    changeFrequency: p.changeFrequency,
    priority: p.priority,
  }));

  // Position overview pages
  const positionPages: MetadataRoute.Sitemap = POSITIONS.map((pos) => ({
    url: `${SITE_URL}/lab/preflop/${pos}`,
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  // 6 positions x 4 stacks = 24 preflop chart pages (SEO long-tail)
  const preflopCharts: MetadataRoute.Sitemap = POSITIONS.flatMap((pos) =>
    STACKS.map((stack) => ({
      url: `${SITE_URL}/lab/preflop/${pos}/${stack}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: 0.7,
    }))
  );

  // Legacy query-param URLs (keep for backwards compat, lower priority)
  const legacyPreflop: MetadataRoute.Sitemap = (["UTG", "HJ", "CO", "BTN", "SB", "BB"] as const).flatMap((pos) =>
    (["20bb", "40bb", "100bb", "200bb"] as const).map((stack) => ({
      url: `${SITE_URL}/lab/preflop?pos=${pos}&stack=${stack}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: 0.3,
    }))
  );

  const blog: MetadataRoute.Sitemap = blogPosts.map((post) => ({
    url: `${SITE_URL}/blog/${post.slug}`,
    lastModified: new Date(post.updatedAt),
    changeFrequency: "monthly" as const,
    priority: 0.6,
  }));

  return [...marketing, ...positionPages, ...preflopCharts, ...legacyPreflop, ...blog];
}
