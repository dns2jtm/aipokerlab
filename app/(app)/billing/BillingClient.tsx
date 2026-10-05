"use client";

import { useState } from "react";
import { PLANS, PLAN_ORDER, type PlanId } from "@/lib/billing/plans";

export default function BillingClient() {
  const [currentPlan, setCurrentPlan] = useState<PlanId>("free");
  const [loadingPlan, setLoadingPlan] = useState<PlanId | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);

  const handleCheckout = async (plan: PlanId) => {
    if (plan === "free") {
      setCurrentPlan("free");
      setMessage("Switched to Free plan (mock).");
      return;
    }
    setLoadingPlan(plan);
    setMessage(null);
    try {
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage(data.error || "Checkout failed");
        return;
      }
      if (data.mock) {
        setCurrentPlan(plan);
        setMessage(`Mock checkout for ${plan} — would redirect to ${data.url}. Plan set to ${plan} (mock).`);
      } else {
        window.location.href = data.url;
      }
    } catch (e) {
      setMessage(String(e));
    } finally {
      setLoadingPlan(null);
    }
  };

  const handlePortal = async () => {
    setPortalLoading(true);
    setMessage(null);
    try {
      const res = await fetch("/api/billing/portal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage(data.error || "Portal failed");
        return;
      }
      if (data.mock) {
        setMessage(`Mock portal — would redirect to ${data.url}`);
      } else {
        window.location.href = data.url;
      }
    } catch (e) {
      setMessage(String(e));
    } finally {
      setPortalLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-zinc-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">Current plan</p>
            <p className="text-xs text-zinc-600">
              You are on <span className="font-bold capitalize">{currentPlan}</span> · {PLANS[currentPlan].description}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handlePortal}
              disabled={portalLoading}
              className="rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold hover:bg-zinc-50 disabled:opacity-50"
            >
              {portalLoading ? "Opening..." : "Manage billing (Portal)"}
            </button>
            <span className="rounded-full bg-zinc-900 px-3 py-2 text-xs font-bold text-white">Mock-friendly</span>
          </div>
        </div>
        {message && <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">{message}</p>}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {PLAN_ORDER.map((id) => {
          const plan = PLANS[id];
          const isCurrent = currentPlan === id;
          return (
            <div
              key={id}
              className={`flex flex-col rounded-2xl border bg-white p-5 ${plan.highlighted ? "border-emerald-500 shadow-lg" : "border-zinc-200"} ${isCurrent ? "ring-2 ring-zinc-900" : ""}`}
            >
              {plan.highlighted && <span className="mb-2 w-fit rounded-full bg-emerald-600 px-2.5 py-1 text-xs font-bold text-white">Most popular</span>}
              <h3 className="text-lg font-bold">{plan.name}</h3>
              <p className="text-xs text-zinc-500">{plan.description}</p>
              <div className="mt-3 flex items-baseline gap-1">
                <span className="text-2xl font-bold">${plan.priceMonthly}</span>
                <span className="text-xs text-zinc-500">/month</span>
              </div>
              <ul className="mt-4 space-y-1.5 text-xs text-zinc-700">
                <li>Analyses: {String(plan.features.analysesPerMonth)}</li>
                <li>Solver: {String(plan.features.solverAccess)}</li>
                <li>Drills: {String(plan.features.drills)}</li>
                <li>Sparring: {String(plan.features.sparring)}</li>
                <li>Coach: {String(plan.features.coach)}</li>
                <li>Upload: {String(plan.features.handHistoryUpload)}</li>
              </ul>
              <button
                onClick={() => handleCheckout(id)}
                disabled={loadingPlan === id || isCurrent}
                className={`mt-5 rounded-full px-4 py-2 text-sm font-bold ${isCurrent ? "bg-zinc-100 text-zinc-500" : plan.highlighted ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-zinc-900 text-white hover:bg-zinc-800"} disabled:opacity-50`}
              >
                {isCurrent ? "Current plan" : loadingPlan === id ? "Loading..." : plan.cta}
              </button>
              {isCurrent && <p className="mt-2 text-center text-xs text-zinc-500">You are on this plan</p>}
            </div>
          );
        })}
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-4">
        <h3 className="text-sm font-bold">Feature comparison</h3>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-zinc-500">
                <th className="py-2 pr-3">Feature</th>
                {PLAN_ORDER.map((id) => (
                  <th key={id} className="px-3 py-2 capitalize">
                    {PLANS[id].name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { label: "Price", get: (p: (typeof PLANS)[PlanId]) => `$${p.priceMonthly}/mo` },
                { label: "Analyses / month", get: (p: (typeof PLANS)[PlanId]) => String(p.features.analysesPerMonth) },
                { label: "Solver access", get: (p: (typeof PLANS)[PlanId]) => String(p.features.solverAccess) },
                { label: "Drills", get: (p: (typeof PLANS)[PlanId]) => String(p.features.drills) },
                { label: "Sparring", get: (p: (typeof PLANS)[PlanId]) => String(p.features.sparring) },
                { label: "AI Coach", get: (p: (typeof PLANS)[PlanId]) => String(p.features.coach) },
                { label: "Hand upload", get: (p: (typeof PLANS)[PlanId]) => String(p.features.handHistoryUpload) },
              ].map((row) => (
                <tr key={row.label} className="border-b border-zinc-100">
                  <td className="py-2 pr-3 font-medium text-zinc-700">{row.label}</td>
                  {PLAN_ORDER.map((id) => (
                    <td key={id} className="px-3 py-2 text-zinc-600">
                      {row.get(PLANS[id])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-zinc-500">Stripe checkout is mock-friendly: without STRIPE_SECRET_KEY it returns a mock URL and sets plan locally. Webhook at /api/billing/webhook handles checkout.session.completed and subscription updates.</p>
      </div>
    </div>
  );
}
