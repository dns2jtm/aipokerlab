export type PlanId = "free" | "starter" | "pro" | "elite";
export type FeatureKey = "analysesPerMonth" | "solverAccess" | "drills" | "sparring" | "coach" | "handHistoryUpload";

export interface Plan {
  id: PlanId;
  name: string;
  priceMonthly: number; // USD
  priceId?: string; // Stripe price ID (env)
  interval: "month";
  features: Record<FeatureKey, string | number | boolean>;
  limits: {
    analysesPerMonth: number; // -1 = unlimited
    solverPerDay: number;
    drillsPerMonth: number;
  };
  cta: string;
  highlighted?: boolean;
  description: string;
}

export const PLANS: Record<PlanId, Plan> = {
  free: {
    id: "free",
    name: "Free",
    priceMonthly: 0,
    interval: "month",
    description: "Try the Lab — 5 hand reviews per day",
    cta: "Start free",
    limits: { analysesPerMonth: 5, solverPerDay: 5, drillsPerMonth: 3 },
    features: {
      analysesPerMonth: 5,
      solverAccess: "Pre-computed only (5/day)",
      drills: "3 drills / month",
      sparring: false,
      coach: "Basic (mock)",
      handHistoryUpload: "5 hands / day",
    },
  },
  starter: {
    id: "starter",
    name: "Starter",
    priceMonthly: 19,
    priceId: process.env.STRIPE_PRICE_STARTER || "price_starter_mock",
    interval: "month",
    description: "For regular grinders — unlimited reviews",
    cta: "Go Starter",
    limits: { analysesPerMonth: 100, solverPerDay: 50, drillsPerMonth: 50 },
    features: {
      analysesPerMonth: 100,
      solverAccess: "Pre-computed + 20 on-demand / day",
      drills: "50 drills / month",
      sparring: "Flop only",
      coach: "Full AI Coach",
      handHistoryUpload: "Unlimited",
    },
  },
  pro: {
    id: "pro",
    name: "Pro",
    priceMonthly: 49,
    priceId: process.env.STRIPE_PRICE_PRO || "price_pro_mock",
    interval: "month",
    description: "Most popular — full Lab + sparring",
    cta: "Go Pro",
    highlighted: true,
    limits: { analysesPerMonth: -1, solverPerDay: 100, drillsPerMonth: -1 },
    features: {
      analysesPerMonth: "Unlimited",
      solverAccess: "Unlimited pre-computed + 100 on-demand / day",
      drills: "Unlimited",
      sparring: "Full (preflop + flop)",
      coach: "Full AI Coach + history",
      handHistoryUpload: "Unlimited",
    },
  },
  elite: {
    id: "elite",
    name: "Elite",
    priceMonthly: 99,
    priceId: process.env.STRIPE_PRICE_ELITE || "price_elite_mock",
    interval: "month",
    description: "For pros — everything + priority solver",
    cta: "Go Elite",
    limits: { analysesPerMonth: -1, solverPerDay: -1, drillsPerMonth: -1 },
    features: {
      analysesPerMonth: "Unlimited",
      solverAccess: "Unlimited + priority queue",
      drills: "Unlimited + custom",
      sparring: "Full + exploitative modes",
      coach: "Full + voice (soon)",
      handHistoryUpload: "Unlimited + API",
    },
  },
};

export const PLAN_ORDER: PlanId[] = ["free", "starter", "pro", "elite"];

export function getPlan(id: string): Plan | undefined {
  return PLANS[id as PlanId];
}

export function isPaidPlan(id: string): boolean {
  return id === "starter" || id === "pro" || id === "elite";
}

export const FEATURE_GATES: Record<FeatureKey, { free: boolean; starter: boolean; pro: boolean; elite: boolean }> = {
  analysesPerMonth: { free: true, starter: true, pro: true, elite: true },
  solverAccess: { free: true, starter: true, pro: true, elite: true },
  drills: { free: true, starter: true, pro: true, elite: true },
  sparring: { free: false, starter: true, pro: true, elite: true },
  coach: { free: true, starter: true, pro: true, elite: true },
  handHistoryUpload: { free: true, starter: true, pro: true, elite: true },
};
