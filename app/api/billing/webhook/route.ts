import { NextRequest, NextResponse } from "next/server";
import { captureError } from "@/lib/monitoring/sentry";
import { isStripeConfigured, STRIPE_WEBHOOK_SECRET, STRIPE_SECRET_KEY } from "@/lib/billing/stripe";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// In-memory mock store for webhook events (for testing without DB)
const webhookEvents: Array<{ type: string; id: string; receivedAt: string; data: unknown }> = [];

export async function POST(req: NextRequest) {
  const rawBody = await req.text();
  let event: { type: string; id: string; data: { object: Record<string, unknown> } };

  if (isStripeConfigured() && STRIPE_WEBHOOK_SECRET) {
    try {
      const StripeMod = await import("stripe");
      const Stripe = (StripeMod.default || StripeMod) as unknown as new (key: string) => {
        webhooks: { constructEvent: (body: string, sig: string, secret: string) => { type: string; id: string; data: { object: Record<string, unknown> } } };
      };
      const stripe = new Stripe(STRIPE_SECRET_KEY);
      const sig = req.headers.get("stripe-signature") || "";
      if (!sig) {
        return NextResponse.json({ error: "Missing stripe-signature header" }, { status: 400 });
      }
      event = stripe.webhooks.constructEvent(rawBody, sig, STRIPE_WEBHOOK_SECRET);
    } catch (err) {
    captureError(err, { route: "/api//api/billing/webhook" });
    console.error("[webhook] signature verification failed", err);
      return NextResponse.json({ error: "Webhook signature verification failed", details: String(err) }, { status: 400 });
    }
  } else {
    // Mock-friendly: parse JSON directly
    try {
      const parsed = JSON.parse(rawBody) as { type?: string; id?: string; data?: { object: Record<string, unknown> } };
      event = {
        type: parsed.type || "checkout.session.completed",
        id: parsed.id || `evt_mock_${Date.now()}`,
        data: parsed.data || { object: {} },
      };
      // If body is empty or not JSON, treat as mock ping
      if (!parsed.type && !rawBody.trim()) {
        event = { type: "ping", id: `evt_mock_${Date.now()}`, data: { object: {} } };
      }
    } catch {
      // Raw body not JSON — treat as ping
      event = { type: "ping", id: `evt_mock_${Date.now()}`, data: { object: {} } };
    }
  }

  // Handle events
  const obj = event.data.object as Record<string, unknown>;
  let action = "ignored";

  switch (event.type) {
    case "checkout.session.completed": {
      const plan = (obj.metadata as Record<string, string> | undefined)?.plan || (obj.plan as string) || "unknown";
      const customer = (obj.customer as string) || (obj.customer_email as string) || "mock_customer";
      console.log(`[webhook] checkout.session.completed plan=${plan} customer=${customer} id=${event.id}`);
      // In prod: upsert Subscription, set user.subscriptionTier = plan, stripeCustomerId = customer
      action = `subscription activated: plan=${plan}`;
      break;
    }
    case "customer.subscription.updated":
    case "customer.subscription.created": {
      const status = (obj.status as string) || "active";
      const plan = (obj.metadata as Record<string, string> | undefined)?.plan || "pro";
      console.log(`[webhook] subscription updated status=${status} plan=${plan}`);
      action = `subscription ${status}: plan=${plan}`;
      break;
    }
    case "customer.subscription.deleted": {
      console.log(`[webhook] subscription deleted id=${event.id}`);
      action = "subscription canceled -> downgrade to free";
      break;
    }
    case "invoice.payment_failed": {
      console.log(`[webhook] payment failed id=${event.id}`);
      action = "payment failed -> past_due";
      break;
    }
    case "ping": {
      action = "ping ok (mock)";
      break;
    }
    default: {
      console.log(`[webhook] unhandled event type=${event.type}`);
      action = `unhandled: ${event.type}`;
    }
  }

  webhookEvents.push({ type: event.type, id: event.id, receivedAt: new Date().toISOString(), data: obj });
  // Keep last 100
  if (webhookEvents.length > 100) webhookEvents.shift();

  return NextResponse.json({ received: true, type: event.type, id: event.id, action, mock: !isStripeConfigured() });
}

export async function GET() {
  return NextResponse.json({
    status: "ok",
    endpoint: "/api/billing/webhook",
    method: "POST",
    events: webhookEvents.slice(-10),
    stripeConfigured: isStripeConfigured(),
    handled: ["checkout.session.completed", "customer.subscription.updated", "customer.subscription.created", "customer.subscription.deleted", "invoice.payment_failed"],
    mockFriendly: true,
  });
}
