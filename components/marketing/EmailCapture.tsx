"use client";

import { useState, useEffect, useCallback } from "react";
import { trackEvent } from "@/lib/analytics/posthog";

type Variant = "inline" | "modal" | "hero";

export default function EmailCapture({
  variant = "inline",
  source = "unknown",
  title,
  description,
  className = "",
  autoShowModal = false,
}: {
  variant?: Variant;
  source?: string;
  title?: string;
  description?: string;
  className?: string;
  autoShowModal?: boolean;
}) {
  const [email, setEmail] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [showModal, setShowModal] = useState(variant !== "modal" ? true : false);
  const [hasTrackedView, setHasTrackedView] = useState(false);

  useEffect(() => {
    if (!hasTrackedView) {
      trackEvent("email_capture_view", { variant, source });
      setHasTrackedView(true);
    }
  }, [variant, source, hasTrackedView]);

  // Exit intent for modal variant
  useEffect(() => {
    if (variant !== "modal" || !autoShowModal) return;
    let triggered = false;
    const handler = (e: MouseEvent) => {
      if (e.clientY <= 0 && !triggered && !showModal) {
        triggered = true;
        setShowModal(true);
        trackEvent("email_capture_exit_intent", { source });
      }
    };
    document.addEventListener("mouseleave", handler);
    // Also show after 30s as fallback
    const timer = setTimeout(() => {
      if (!triggered && !showModal) {
        triggered = true;
        setShowModal(true);
      }
    }, 30000);
    return () => {
      document.removeEventListener("mouseleave", handler);
      clearTimeout(timer);
    };
  }, [variant, autoShowModal, showModal, source]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!email.trim()) {
        setMessage({ type: "error", text: "Please enter your email." });
        return;
      }
      setLoading(true);
      setMessage(null);
      try {
        const res = await fetch("/api/email/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim(), source, website: honeypot }),
        });
        const data = (await res.json()) as { success: boolean; message: string };
        if (data.success) {
          setMessage({ type: "success", text: data.message });
          trackEvent("email_subscribe", { source, variant, success: true });
          setEmail("");
        } else {
          setMessage({ type: "error", text: data.message || "Something went wrong." });
          trackEvent("email_subscribe", { source, variant, success: false });
        }
      } catch {
        setMessage({ type: "error", text: "Network error. Please try again." });
        trackEvent("email_subscribe", { source, variant, success: false });
      } finally {
        setLoading(false);
      }
    },
    [email, honeypot, source, variant]
  );

  const defaults: Record<Variant, { title: string; desc: string }> = {
    inline: {
      title: "Get free preflop charts + weekly leak fixes",
      desc: "Join 2,000+ players improving with AI coaching. No spam, unsubscribe anytime.",
    },
    modal: {
      title: "Wait — grab your free preflop charts",
      desc: "6 positions × 4 stacks, GTO frequencies + EV. Free forever.",
    },
    hero: {
      title: "Free GTO Preflop Charts",
      desc: "Enter your email to get instant access + weekly strategy tips.",
    },
  };

  const t = title || defaults[variant].title;
  const d = description || defaults[variant].desc;

  const form = (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
          disabled={loading}
          className="flex-1 rounded-full border border-zinc-300 bg-white px-4 py-2.5 text-sm outline-none placeholder:text-zinc-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 disabled:opacity-60"
          aria-label="Email address"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-full bg-emerald-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
        >
          {loading ? "Sending…" : variant === "hero" ? "Get Free Charts →" : "Subscribe"}
        </button>
      </div>
      {/* Honeypot */}
      <input
        type="text"
        value={honeypot}
        onChange={(e) => setHoneypot(e.target.value)}
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="hidden"
        placeholder="Leave blank"
      />
      {message && (
        <p className={`text-sm font-medium ${message.type === "success" ? "text-emerald-700" : "text-red-600"}`} role="status">
          {message.text}
        </p>
      )}
      <p className="text-xs text-zinc-500">No spam. Unsubscribe anytime. We respect your inbox.</p>
    </form>
  );

  if (variant === "modal") {
    if (!showModal) return null;
    return (
      <div className={`fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 ${className}`} role="dialog" aria-modal="true">
        <div className="relative w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl">
          <button
            onClick={() => setShowModal(false)}
            className="absolute right-3 top-3 rounded-full p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
            aria-label="Close"
          >
            ✕
          </button>
          <h3 className="text-lg font-bold">{t}</h3>
          <p className="mt-1 text-sm leading-6 text-zinc-600">{d}</p>
          <div className="mt-4">{form}</div>
        </div>
      </div>
    );
  }

  if (variant === "hero") {
    return (
      <div className={`rounded-2xl border border-emerald-200 bg-emerald-50 p-6 ${className}`}>
        <h3 className="text-base font-bold text-emerald-900">{t}</h3>
        <p className="mt-1 text-sm text-emerald-800">{d}</p>
        <div className="mt-4">{form}</div>
      </div>
    );
  }

  // inline
  return (
    <div className={`rounded-xl border border-zinc-200 bg-white p-5 ${className}`}>
      <h3 className="text-sm font-bold">{t}</h3>
      <p className="mt-1 text-sm leading-6 text-zinc-600">{d}</p>
      <div className="mt-4">{form}</div>
    </div>
  );
}
