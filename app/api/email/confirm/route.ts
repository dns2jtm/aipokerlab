import { NextRequest, NextResponse } from "next/server";
import { emailStore } from "@/lib/email/store";
import { captureError } from "@/lib/monitoring/sentry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const token = req.nextUrl.searchParams.get("token");
    if (!token || token.trim() === "") {
      return NextResponse.json({ success: false, message: "Missing confirmation token." }, { status: 400 });
    }

    const sub = await emailStore.findByToken(token);
    if (!sub) {
      return NextResponse.json({ success: false, message: "Invalid or expired confirmation link." }, { status: 404 });
    }

    if (sub.confirmed) {
      return NextResponse.json({ success: true, message: "Your email is already confirmed. You're all set!" });
    }

    await emailStore.confirm(token);
    return NextResponse.json({ success: true, message: "Email confirmed! You're now subscribed to AI Poker Lab." });
  } catch (err) {
    captureError(err, { route: "/api/email/confirm" });
    console.error("[email/confirm] error", err);
    return NextResponse.json({ success: false, message: "Something went wrong. Please try again." }, { status: 500 });
  }
}
