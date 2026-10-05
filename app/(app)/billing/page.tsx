import type { Metadata } from "next";
import BillingClient from "./BillingClient";

export const metadata: Metadata = {
  title: "Billing & Plans | AI Poker Lab",
  description: "Choose your plan — Free, Starter $19, Pro $49, Elite $99. Stripe billing, feature comparison, and portal access.",
};

export default function BillingPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Billing & Plans</h1>
        <p className="text-sm text-zinc-600">Free, Starter $19, Pro $49, Elite $99 — mock-friendly when Stripe keys are missing. ToS-compliant training only.</p>
      </div>
      <BillingClient />
    </div>
  );
}
