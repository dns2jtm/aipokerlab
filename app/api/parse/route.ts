import { NextRequest, NextResponse } from "next/server";
import { captureError } from "@/lib/monitoring/sentry";
import { parseHands } from "@/lib/parser/handParser";
import { checkRateLimit, getClientIp, rateLimitHeaders, RATE_LIMITS } from "@/lib/security/rateLimit";
import { sanitizeHandHistoryInput } from "@/lib/security/sanitize";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const ip = getClientIp(req);
  const rl = checkRateLimit(`parse:${ip}`, RATE_LIMITS.parse, "parse");
  if (!rl.allowed) {
    return NextResponse.json(
      { error: "Rate limit exceeded: 30 parses per minute", retryAfterMs: rl.retryAfterMs },
      { status: 429, headers: rateLimitHeaders(rl, RATE_LIMITS.parse) }
    );
  }
  try {
    const body = await req.json();
    const rawText = typeof body.rawText === "string" ? body.rawText : typeof body.raw === "string" ? body.raw : "";
    if (!rawText || !rawText.trim()) {
      return NextResponse.json({ error: "rawText is required and must be non-empty" }, { status: 400, headers: rateLimitHeaders(rl, RATE_LIMITS.parse) });
    }
    const sanitized = sanitizeHandHistoryInput(rawText);
    if (sanitized.error && rawText.length > 100 * 1024) {
      return NextResponse.json({ error: sanitized.error }, { status: 413, headers: rateLimitHeaders(rl, RATE_LIMITS.parse) });
    }
    const result = parseHands(sanitized.sanitized);
    return NextResponse.json(
      {
        hands: result.hands,
        errors: result.errors,
        count: result.hands.length,
      },
      { headers: { "Cache-Control": "no-store", ...rateLimitHeaders(rl, RATE_LIMITS.parse) } }
    );
  } catch (err) {
    captureError(err, { route: "/api//api/parse" });
    console.error("[parse] error", err);
    return NextResponse.json({ error: "Failed to parse hand history", details: String(err) }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: "ok",
    endpoint: "/api/parse",
    method: "POST",
    accepts: "{ rawText: string }",
    returns: "{ hands: Hand[], errors: { index, message, snippet }[], count: number }",
    handShape: "{ id, site, stakes, date, hero, heroCards, board, streets: { preflop, flop, turn, river }, streetBoards, pot, winners, ante?, straddle?, sidePots? }",
  });
}
