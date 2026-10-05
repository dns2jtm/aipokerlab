"use client";

import { useEffect } from "react";
import { trackEvent } from "@/lib/analytics/posthog";

export default function BlogViewTracker({ slug, category, title }: { slug: string; category: string; title: string }) {
  useEffect(() => {
    trackEvent("blog_post_view", { slug, category, title });
  }, [slug, category, title]);
  return null;
}
