import { NextRequest, NextResponse } from "next/server";
import { captureError } from "@/lib/monitoring/sentry";
import { createPortalSession, isStripeConfigured } from "@/lib/billing/stripe";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const customerId = typeof body.customerId === "string" ? body.customerId : typeof body.stripeCustomerId === "string" ? body.stripeCustomerId : undefined;
    const returnUrl = typeof body.returnUrl === "string" ? body.returnUrl : undefined;
    const session = await createPortalSession({ customerId, returnUrl });
    return NextResponse.json(
      { url: session.url, mock: session.mock, stripeConfigured: isStripeConfigured() },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (err) {
    captureError(err, { route: "/api//api/billing/portal" });
    console.error("[billing/portal] error", err);
    return NextResponse.json({ error: "Failed to create portal session", details: String(err) }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: "ok",
    endpoint: "/api/billing/portal",
    method: "POST",
    accepts: "{ customerId?, returnUrl? }",
    returns: "{ url, mock, stripeConfigured }",
    stripeConfigured: isStripeConfigured(),
  });
}
