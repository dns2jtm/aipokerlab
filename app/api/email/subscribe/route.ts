import { NextRequest, NextResponse } from "next/server";
import { emailStore, generateToken, isValidEmail, normalizeEmail, checkRateLimit, getClientIp } from "@/lib/email/store";
import { sendWelcomeEmail } from "@/lib/email/resend";
import { captureError } from "@/lib/monitoring/sentry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const ip = getClientIp(req);
    const rate = checkRateLimit(ip);
    if (!rate.allowed) {
      return NextResponse.json(
        { success: false, message: "Too many requests. Please try again in a minute." },
        {
          status: 429,
          headers: {
            "Retry-After": String(Math.ceil((rate.resetAt - Date.now()) / 1000)),
            "X-RateLimit-Remaining": "0",
          },
        }
      );
    }

    let body: Record<string, unknown>;
    try {
      body = (await req.json()) as Record<string, unknown>;
    } catch {
      return NextResponse.json({ success: false, message: "Invalid JSON body" }, { status: 400 });
    }

    // Honeypot: if filled, silently succeed (bot)
    const honeypot = typeof body.website === "string" ? body.website : typeof body.honeypot === "string" ? body.honeypot : "";
    if (honeypot && honeypot.trim() !== "") {
      return NextResponse.json({ success: true, message: "Thanks for subscribing! Check your email to confirm." });
    }

    const email = typeof body.email === "string" ? body.email.trim() : "";
    const source = typeof body.source === "string" ? body.source : "unknown";

    if (!email || !isValidEmail(email)) {
      return NextResponse.json({ success: false, message: "Please enter a valid email address." }, { status: 400 });
    }

    const normalized = normalizeEmail(email);
    const existing = await emailStore.findByEmail(normalized);
    if (existing) {
      if (existing.confirmed) {
        return NextResponse.json({ success: true, message: "You're already subscribed! Check your inbox for updates." });
      }
      // Resend confirmation
      const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://aipokerlab.com";
      const confirmUrl = `${appUrl}/api/email/confirm?token=${existing.token}`;
      await sendWelcomeEmail(normalized, confirmUrl);
      return NextResponse.json({ success: true, message: "Check your email to confirm your subscription." });
    }

    const token = generateToken();
    await emailStore.create({ email: normalized, source, token, ip });

    const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://aipokerlab.com";
    const confirmUrl = `${appUrl}/api/email/confirm?token=${token}`;

    // Send welcome email (mock-friendly)
    try {
      await sendWelcomeEmail(normalized, confirmUrl);
    } catch (err) {
      captureError(err, { route: "/api/email/subscribe", email: normalized });
      // Don't fail the request if email fails — still store subscription
    }

    return NextResponse.json(
      { success: true, message: "Thanks for subscribing! Check your email to confirm." },
      { headers: { "X-RateLimit-Remaining": String(rate.remaining) } }
    );
  } catch (err) {
    captureError(err, { route: "/api/email/subscribe" });
    console.error("[email/subscribe] error", err);
    return NextResponse.json({ success: false, message: "Something went wrong. Please try again." }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: "ok",
    endpoint: "/api/email/subscribe",
    method: "POST",
    accepts: "{ email: string, source?: string, website?: string (honeypot) }",
    returns: "{ success: boolean, message: string }",
    rateLimit: "5/min per IP",
    doubleOptIn: true,
  });
}
