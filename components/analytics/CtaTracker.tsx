"use client";

import { trackEvent } from "@/lib/analytics/posthog";

export default function CtaTracker({
  location,
  label,
  href,
  children,
}: {
  location: string;
  label: string;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <span
      onClick={() => trackEvent("cta_click", { location, label, href })}
      className="inline-flex"
    >
      {children}
    </span>
  );
}
