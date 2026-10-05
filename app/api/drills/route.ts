import { NextRequest, NextResponse } from "next/server";
import { captureError } from "@/lib/monitoring/sentry";
import { generateDrillPack, computeDueAt, computeXp } from "@/lib/drills/engine";
import { getMockAnalyzerOutput } from "@/lib/leaks/analyzer";
import type { LeakResult } from "@/lib/leaks/detectors";
import { checkRateLimit, getClientIp, rateLimitHeaders, RATE_LIMITS } from "@/lib/security/rateLimit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const packs = new Map<string, ReturnType<typeof generateDrillPack>>();
const attempts: Array<{ drillId: string; handId: string; chosenAction: string; gtoAction: string; correct: boolean; evLoss: number; timeMs: number; createdAt: string }> = [];

export async function GET(req: NextRequest) {
  const ip = getClientIp(req);
  const rl = checkRateLimit(`drills:${ip}`, RATE_LIMITS.drills, "drills");
  if (!rl.allowed) {
    return NextResponse.json({ error: "Rate limit exceeded" }, { status: 429, headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
  }
  const { searchParams } = new URL(req.url);
  const leakId = searchParams.get("leak");
  const list = Array.from(packs.values());

  if (leakId) {
    if (leakId.length > 100) return NextResponse.json({ error: "Invalid leak id" }, { status: 400 });
    const filtered = list.filter((p) => p.leakId === leakId);
    return NextResponse.json({ drills: filtered, attempts: attempts.filter((a) => filtered.some((p) => p.id === a.drillId)) }, { headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
  }

  const analyzer = getMockAnalyzerOutput();
  return NextResponse.json({
    drills: list,
    leaks: analyzer.leaks,
    attempts,
    spaced: list.map((p) => ({
      drillId: p.id,
      leakId: p.leakId,
      dueAt: p.dueAt,
      dueNow: new Date(p.dueAt) <= new Date(),
    })),
  }, { headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
}

export async function POST(req: NextRequest) {
  const ip = getClientIp(req);
  const rl = checkRateLimit(`drills:${ip}`, RATE_LIMITS.drills, "drills");
  if (!rl.allowed) {
    return NextResponse.json({ error: "Rate limit exceeded" }, { status: 429, headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
  }
  try {
    const body = await req.json();

    if (body.leakId && !body.handId) {
      const leakId = String(body.leakId).slice(0, 100);
      const count = typeof body.count === "number" ? Math.max(1, Math.min(20, Math.floor(body.count))) : 10;
      const analyzer = getMockAnalyzerOutput();
      const leak: LeakResult | undefined = analyzer.leaks.find((l) => l.leakId === leakId);
      if (!leak) {
        return NextResponse.json({ error: `Leak ${leakId} not found` }, { status: 404, headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
      }
      const pack = generateDrillPack(leak, count);
      packs.set(pack.id, pack);
      return NextResponse.json({ drill: pack }, { status: 201, headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
    }

    if (body.drillId && body.handId && body.chosenAction) {
      const drillId = String(body.drillId).slice(0, 100);
      const handId = String(body.handId).slice(0, 100);
      const chosenAction = String(body.chosenAction).slice(0, 20).toLowerCase();
      const allowedActions = new Set(["raise", "call", "fold", "bet", "check"]);
      if (!allowedActions.has(chosenAction)) {
        return NextResponse.json({ error: "Invalid chosenAction" }, { status: 400, headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
      }
      const pack = packs.get(drillId);
      if (!pack) return NextResponse.json({ error: "Drill not found" }, { status: 404, headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
      const hand = pack.hands.find((h) => h.id === handId);
      if (!hand) return NextResponse.json({ error: "Hand not found in drill" }, { status: 404, headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });

      const chosen = chosenAction as typeof hand.gtoPrimary;
      const gto = hand.gtoPrimary;
      const normalize = (a: string) => (a === "bet" ? "raise" : a === "check" ? "fold" : a);
      const correct = normalize(chosen) === normalize(gto) || chosen === gto;
      const evLoss = correct ? 0 : -(0.2 + Math.abs(hand.gtoFreq.fold - 50) * 0.01 + Math.random() * 0.3);
      const timeMs = typeof body.timeMs === "number" ? Math.max(0, Math.min(600000, body.timeMs)) : 0;
      const attempt = {
        drillId,
        handId,
        chosenAction: chosen,
        gtoAction: gto,
        correct,
        evLoss: Math.round(evLoss * 100) / 100,
        timeMs,
        createdAt: new Date().toISOString(),
        xp: computeXp(correct, evLoss),
        gtoFreq: hand.gtoFreq,
        explanation: hand.explanation,
        ev: hand.ev,
      };
      attempts.push(attempt);

      const drillAttempts = attempts.filter((a) => a.drillId === drillId);
      const correctCount = drillAttempts.filter((a) => a.correct).length;
      const total = drillAttempts.length;
      const xpTotal = drillAttempts.reduce((acc, a) => acc + (a as unknown as { xp: number }).xp, 0);
      const avgEvLoss = total ? drillAttempts.reduce((acc, a) => acc + a.evLoss, 0) / total : 0;
      const score = total ? Math.round((correctCount / total) * 100) : 0;
      const dueAt = computeDueAt(score, correctCount);

      return NextResponse.json({
        attempt,
        progress: { correct: correctCount, total, xp: xpTotal, avgEvLoss, score, dueAt, completed: total >= pack.hands.length },
      }, { headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
    }

    return NextResponse.json({ error: "Invalid body: need { leakId } to generate or { drillId, handId, chosenAction } to record" }, { status: 400, headers: rateLimitHeaders(rl, RATE_LIMITS.drills) });
  } catch (err) {
    captureError(err, { route: "/api//api/drills" });
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
