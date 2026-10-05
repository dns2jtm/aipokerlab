import { PLANS, type PlanId, type FeatureKey } from "./plans";

export interface UserLike {
  subscriptionTier?: string | null;
  role?: string | null;
}

export function getUserPlan(user: UserLike | null | undefined): PlanId {
  const tier = (user?.subscriptionTier || "free").toLowerCase();
  if (tier === "starter" || tier === "pro" || tier === "elite" || tier === "lab_plus") {
    if (tier === "lab_plus") return "pro";
    return tier as PlanId;
  }
  return "free";
}

export function canAccessFeature(user: UserLike | null | undefined, feature: FeatureKey): boolean {
  const plan = getUserPlan(user);
  const planDef = PLANS[plan];
  if (!planDef) return false;
  if (user?.role === "admin") return true;
  const val = planDef.features[feature] as unknown;
  if (typeof val === "boolean") return val;
  return val !== undefined && (val as unknown) !== false;
}

export function getLimit(user: UserLike | null | undefined, key: "analysesPerMonth" | "solverPerDay" | "drillsPerMonth"): number {
  const plan = getUserPlan(user);
  return PLANS[plan].limits[key];
}

export function isUnlimited(limit: number): boolean {
  return limit === -1;
}

export function checkUsageAllowed(user: UserLike | null | undefined, key: "analysesPerMonth" | "solverPerDay" | "drillsPerMonth", used: number): { allowed: boolean; remaining: number | "unlimited"; limit: number } {
  const limit = getLimit(user, key);
  if (isUnlimited(limit)) return { allowed: true, remaining: "unlimited", limit };
  const remaining = Math.max(0, limit - used);
  return { allowed: used < limit, remaining, limit };
}

export function requireFeature(user: UserLike | null | undefined, feature: FeatureKey): { allowed: boolean; plan: PlanId; reason?: string } {
  const allowed = canAccessFeature(user, feature);
  const plan = getUserPlan(user);
  if (allowed) return { allowed: true, plan };
  return { allowed: false, plan, reason: `Feature "${feature}" requires upgrade from ${plan}` };
}
