"use client";

import { useState } from "react";

export default function ContactForm() {
  const [sent, setSent] = useState(false);
  const [honeypot, setHoneypot] = useState("");
  const [form, setForm] = useState({ name: "", email: "", topic: "General", message: "" });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (honeypot.trim() !== "") return; // bot
    if (!form.name || !form.email || !form.message) return;
    setSent(true);
    setTimeout(() => setSent(false), 4000);
  }

  if (sent) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center">
        <div className="text-lg">✓</div>
        <h3 className="mt-1 text-sm font-bold text-emerald-900">Message sent (mock)</h3>
        <p className="mt-1 text-xs leading-5 text-emerald-700">
          Thanks, {form.name}! In production this would email hello@aipokerlab.com. We&apos;d reply within 24 hours.
        </p>
        <button
          onClick={() => {
            setSent(false);
            setForm({ name: "", email: "", topic: "General", message: "" });
          }}
          className="mt-3 text-xs font-semibold text-emerald-700 underline"
        >
          Send another
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="block">
          <span className="text-xs font-semibold text-zinc-700">Name</span>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Jane Doe"
            required
            maxLength={100}
            className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-zinc-700">Email</span>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="jane@example.com"
            required
            maxLength={254}
            className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
          />
        </label>
      </div>
      <label className="block">
        <span className="text-xs font-semibold text-zinc-700">Topic</span>
        <select
          value={form.topic}
          onChange={(e) => setForm({ ...form, topic: e.target.value })}
          className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
        >
          <option>General</option>
          <option>Support</option>
          <option>Billing</option>
          <option>Methodology / Solver</option>
          <option>Partnership / Press</option>
        </select>
      </label>
      <label className="block">
        <span className="text-xs font-semibold text-zinc-700">Message</span>
        <textarea
          value={form.message}
          onChange={(e) => setForm({ ...form, message: e.target.value })}
          placeholder="How can we help?"
          required
          rows={4}
          maxLength={5000}
          className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
        />
      </label>
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
      <button
        type="submit"
        className="w-full rounded-full bg-zinc-900 px-6 py-2.5 text-sm font-bold text-white hover:bg-zinc-800"
      >
        Send message
      </button>
      <p className="text-center text-xs text-zinc-500">
        Or email directly:{" "}
        <a href="mailto:hello@aipokerlab.com" className="underline">
          hello@aipokerlab.com
        </a>
      </p>
    </form>
  );
}
