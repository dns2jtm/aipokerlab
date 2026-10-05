"use client";

import { useEffect } from "react";
import { trackEvent } from "@/lib/analytics/posthog";

export default function PreflopTracker({ position, stack }: { position: string; stack: string }) {
  useEffect(() => {
    trackEvent("preflop_chart_view", { position, stack, source: "marketing_chart" });
  }, [position, stack]);
  return null;
}
