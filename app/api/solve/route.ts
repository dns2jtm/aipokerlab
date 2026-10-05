import { NextRequest, NextResponse } from "next/server";
import { captureError } from "@/lib/monitoring/sentry";
import { SolverService, generateSpotHash, inflightSolves } from "@/lib/solver/solverService";
import type { SpotInput } from "@/lib/solver/solverService";
import { checkRateLimit, getClientIp, rateLimitHeaders, RATE_LIMITS } from "@/lib/security/rateLimit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function validateSpot(body: unknown): { valid: boolean; spot?: SpotInput; error?: string } {
  if (!body || typeof body !== "object") return { valid: false, error: "Body must be JSON object with { spot }" };
  const obj = body as Record<string, unknown>;
  const spot = (obj.spot || obj) as Record<string, unknown>;
  if (typeof spot.street !== "string" && typeof spot.board !== "string") {
    return { valid: false, error: "spot.street or spot.board is required" };
  }
  // Validate field lengths to prevent abuse
  if (typeof spot.board === "string" && spot.board.length > 100) return { valid: false, error: "board too long (max 100)" };
  if (typeof spot.heroRange === "string" && spot.heroRange.length > 200) return { valid: false, error: "heroRange too long" };
  if (typeof spot.villainRange === "string" && spot.villainRange.length > 200) return { valid: false, error: "villainRange too long" };
  if (Array.isArray(spot.betSizings) && spot.betSizings.length > 10) return { valid: false, error: "betSizings too many (max 10)" };
  const normalized: SpotInput = {
    board: typeof spot.board === "string" ? spot.board.slice(0, 100) : "",
    heroRange: typeof spot.heroRange === "string" ? spot.heroRange.slice(0, 200) : typeof spot.heroCards === "string" ? spot.heroCards.slice(0, 20) : "random",
    villainRange: typeof spot.villainRange === "string" ? spot.villainRange.slice(0, 200) : "random",
    pot: typeof spot.pot === "number" ? spot.pot : typeof spot.pot === "string" ? parseFloat(spot.pot) : 7.5,
    stacks: typeof spot.stacks === "number" ? spot.stacks : typeof spot.stack === "number" ? spot.stack : 100,
    betSizings: Array.isArray(spot.betSizings) ? (spot.betSizings as number[]).slice(0, 10) : [0.33, 0.66, 1.5],
    rake: typeof spot.rake === "number" ? spot.rake : 0.05,
    street: typeof spot.street === "string" ? spot.street.slice(0, 20) : "flop",
    position: typeof spot.position === "string" ? spot.position.slice(0, 20) : undefined,
    heroCards: typeof spot.heroCards === "string" ? spot.heroCards.slice(0, 20) : undefined,
  };
  if (isNaN(normalized.pot)) normalized.pot = 7.5;
  if (isNaN(normalized.stacks)) normalized.stacks = 100;
  if (isNaN(normalized.rake)) normalized.rake = 0.05;
  // Clamp numeric ranges
  normalized.pot = Math.max(0, Math.min(10000, normalized.pot));
  normalized.stacks = Math.max(1, Math.min(10000, normalized.stacks));
  normalized.rake = Math.max(0, Math.min(0.2, normalized.rake));
  return { valid: true, spot: normalized };
}

export async function POST(req: NextRequest) {
  const ip = getClientIp(req);
  const rl = checkRateLimit(`solve:${ip}`, RATE_LIMITS.solve, "solve");
  if (!rl.allowed) {
    return NextResponse.json(
      { error: "Rate limit exceeded: 10 solves per minute", retryAfterMs: rl.retryAfterMs },
      { status: 429, headers: rateLimitHeaders(rl, RATE_LIMITS.solve) }
    );
  }

  try {
    const body = await req.json();
    const validation = validateSpot(body);
    if (!validation.valid || !validation.spot) {
      return NextResponse.json({ error: validation.error }, { status: 400, headers: rateLimitHeaders(rl, RATE_LIMITS.solve) });
    }
    const spot = validation.spot;
    const spotHash = generateSpotHash(spot);

    const existing = inflightSolves.get(spotHash);
    if (existing) {
      const result = await existing;
      return NextResponse.json(result, {
        headers: {
          "X-Solver-Source": result.source,
          "X-Spot-Hash": spotHash,
          ...rateLimitHeaders(rl, RATE_LIMITS.solve),
          "Cache-Control": "no-store",
        },
      });
    }

    const promise = SolverService.solve(spot);
    inflightSolves.set(spotHash, promise);
    try {
      const result = await promise;
      return NextResponse.json(result, {
        headers: {
          "X-Solver-Source": result.source,
          "X-Spot-Hash": spotHash,
          ...rateLimitHeaders(rl, RATE_LIMITS.solve),
          "Cache-Control": "no-store",
        },
      });
    } finally {
      inflightSolves.delete(spotHash);
    }
  } catch (err) {
    captureError(err, { route: "/api//api/solve" });
    console.error("[solve] error", err);
    return NextResponse.json({ error: "Failed to solve spot", details: String(err) }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    status: "ok",
    endpoint: "/api/solve",
    method: "POST",
    accepts: "{ spot: { board, heroRange, villainRange, pot, stacks, betSizings, rake, street, position?, heroCards? } }",
    returns: "{ spotHash, gtoFreq: { raise, call, fold, bet?, check? }, ev, exploitability, source, solveTimeMs, board, street }",
    rateLimit: "10/min per IP",
    cache: "in-memory Map (Prisma-ready)",
  });
}
