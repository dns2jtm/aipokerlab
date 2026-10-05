"use client";

import posthog from "posthog-js";

let initialized = false;

export function initPostHog(): boolean {
  if (initialized) return true;
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  const host = process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com";
  if (!key) {
    if (process.env.NODE_ENV === "development") {
      console.log("[PostHog] NEXT_PUBLIC_POSTHOG_KEY missing — analytics in mock mode (console only)");
    }
    return false;
  }
  try {
    posthog.init(key, {
      api_host: host,
      capture_pageview: false,
      capture_pageleave: true,
      autocapture: false,
      persistence: "localStorage+cookie",
      loaded: () => {
        if (process.env.NODE_ENV === "development") {
          console.log("[PostHog] initialized host=", host);
        }
      },
    });
    initialized = true;
    return true;
  } catch (err) {
    console.warn("[PostHog] init failed", err);
    return false;
  }
}

export function isPostHogReady(): boolean {
  return initialized && typeof posthog !== "undefined" && !!posthog.__loaded;
}

export function trackEvent(event: string, props?: Record<string, unknown>): void {
  if (isPostHogReady()) {
    try {
      posthog.capture(event, props);
    } catch (err) {
      console.warn("[PostHog] capture failed", err);
    }
  } else {
    if (process.env.NODE_ENV === "development") {
      console.log(`[PostHog mock] trackEvent: ${event}`, props || {});
    }
  }
}

export function identifyUser(userId: string, traits?: Record<string, unknown>): void {
  if (isPostHogReady()) {
    try {
      posthog.identify(userId, traits);
    } catch (err) {
      console.warn("[PostHog] identify failed", err);
    }
  } else {
    if (process.env.NODE_ENV === "development") {
      console.log(`[PostHog mock] identifyUser: ${userId}`, traits || {});
    }
  }
}

export function trackPageView(url?: string): void {
  const path = url || (typeof window !== "undefined" ? window.location.pathname + window.location.search : "/");
  if (isPostHogReady()) {
    try {
      posthog.capture("$pageview", { $current_url: typeof window !== "undefined" ? window.location.href : path });
    } catch (err) {
      console.warn("[PostHog] pageview failed", err);
    }
  } else {
    if (process.env.NODE_ENV === "development") {
      console.log(`[PostHog mock] trackPageView: ${path}`);
    }
  }
}

export function resetPostHog(): void {
  if (isPostHogReady()) {
    try {
      posthog.reset();
    } catch {
      // ignore
    }
  }
  initialized = false;
}

export { posthog };
