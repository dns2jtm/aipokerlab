import { PLANS, type PlanId } from "./plans";

export const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || "";
export const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || "";
export const APP_URL = process.env.NEXT_PUBLIC_APP_URL || process.env.APP_URL || "http://localhost:3000";

export function isStripeConfigured(): boolean {
  return Boolean(STRIPE_SECRET_KEY && STRIPE_SECRET_KEY.startsWith("sk_"));
}

export function getPriceId(plan: PlanId): string | undefined {
  return PLANS[plan]?.priceId;
}

export interface MockCheckoutSession {
  id: string;
  url: string;
  plan: PlanId;
  mock: boolean;
}

export async function createCheckoutSessionMock(plan: PlanId): Promise<MockCheckoutSession> {
  const id = `cs_mock_${plan}_${Date.now()}`;
  const url = `${APP_URL}/billing?checkout=mock&plan=${plan}&session_id=${id}`;
  return { id, url, plan, mock: true };
}

export async function createCheckoutSession(plan: PlanId, opts?: { userId?: string; email?: string; successUrl?: string; cancelUrl?: string }): Promise<MockCheckoutSession> {
  if (!isStripeConfigured()) {
    return createCheckoutSessionMock(plan);
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const StripeMod: any = await import("stripe");
    const Stripe = StripeMod.default || StripeMod;
    const stripe = new Stripe(STRIPE_SECRET_KEY);
    const priceId = getPriceId(plan);
    if (!priceId || priceId.includes("_mock")) {
      return createCheckoutSessionMock(plan);
    }
    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      line_items: [{ price: priceId, quantity: 1 }],
      success_url: opts?.successUrl || `${APP_URL}/billing?success=1&plan=${plan}`,
      cancel_url: opts?.cancelUrl || `${APP_URL}/billing?canceled=1`,
      customer_email: opts?.email || undefined,
      metadata: { plan, userId: opts?.userId || "" },
      allow_promotion_codes: true,
    });
    return { id: session.id, url: session.url || `${APP_URL}/billing?success=1`, plan, mock: false };
  } catch (e) {
    console.warn("[stripe] checkout fallback to mock", e);
    return createCheckoutSessionMock(plan);
  }
}

export async function createPortalSessionMock(customerId?: string): Promise<{ url: string; mock: boolean }> {
  return { url: `${APP_URL}/billing?portal=mock&customer=${customerId || "mock"}`, mock: true };
}

export async function createPortalSession(opts?: { customerId?: string; returnUrl?: string }): Promise<{ url: string; mock: boolean }> {
  if (!isStripeConfigured() || !opts?.customerId) {
    return createPortalSessionMock(opts?.customerId);
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const StripeMod: any = await import("stripe");
    const Stripe = StripeMod.default || StripeMod;
    const stripe = new Stripe(STRIPE_SECRET_KEY);
    const session = await stripe.billingPortal.sessions.create({
      customer: opts.customerId,
      return_url: opts.returnUrl || `${APP_URL}/billing`,
    });
    return { url: session.url, mock: false };
  } catch (e) {
    console.warn("[stripe] portal fallback to mock", e);
    return createPortalSessionMock(opts?.customerId);
  }
}

export function getStripePublishableKey(): string {
  return process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || process.env.STRIPE_PUBLISHABLE_KEY || "";
}
