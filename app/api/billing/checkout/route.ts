import { NextRequest, NextResponse } from "next/server";
import { captureError } from "@/lib/monitoring/sentry";
import { createCheckoutSession, isStripeConfigured } from "@/lib/billing/stripe";
import { getPlan, type PlanId } from "@/lib/billing/plans";
import { checkRateLimit, getClientIp, rateLimitHeaders, RATE_LIMITS } from "@/lib/security/rateLimit";
import { sanitizeEmail } from "@/lib/security/sanitize";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const ip = getClientIp(req);
  const rl = checkRateLimit(`billing:${ip}`, RATE_LIMITS.billing, "billing");
  if (!rl.allowed) {
    return NextResponse.json({ error: "Rate limit exceeded" }, { status: 429, headers: rateLimitHeaders(rl, RATE_LIMITS.billing) });
  }
  try {
    const body = await req.json();
    const plan = (body.plan || "").toLowerCase() as PlanId;
    if (!plan || !getPlan(plan)) {
      return NextResponse.json({ error: `Invalid plan. Must be one of: free, starter, pro, elite` }, { status: 400, headers: rateLimitHeaders(rl, RATE_LIMITS.billing) });
    }
    if (plan === "free") {
      return NextResponse.json({ error: "Free plan does not require checkout", plan }, { status: 400, headers: rateLimitHeaders(rl, RATE_LIMITS.billing) });
    }
    let email: string | undefined;
    if (typeof body.email === "string" && body.email.trim()) {
      const sanitized = sanitizeEmail(body.email);
      if (!sanitized.valid) {
        return NextResponse.json({ error: sanitized.error || "Invalid email" }, { status: 400, headers: rateLimitHeaders(rl, RATE_LIMITS.billing) });
      }
      email = sanitized.sanitized;
    }
    const userId = typeof body.userId === "string" ? body.userId.slice(0, 100) : undefined;
    const session = await createCheckoutSession(plan, { userId, email });
    return NextResponse.json(
      {
        url: session.url,
        sessionId: session.id,
        plan: session.plan,
        mock: session.mock,
        stripeConfigured: isStripeConfigured(),
      },
      { headers: { "Cache-Control": "no-store", ...rateLimitHeaders(rl, RATE_LIMITS.billing) } }
    );
  } catch (err) {
    captureError(err, { route: "/api//api/billing/checkout" });
    console.error("[billing/checkout] error", err);
    return NextResponse.json({ error: "Failed to create checkout session", details: String(err) }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: "ok",
    endpoint: "/api/billing/checkout",
    method: "POST",
    accepts: "{ plan: 'starter'|'pro'|'elite', email?, userId? }",
    returns: "{ url, sessionId, plan, mock, stripeConfigured }",
    stripeConfigured: isStripeConfigured(),
  });
}
