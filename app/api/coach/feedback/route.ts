import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// In-memory feedback store (mock-friendly, no DB required)
// In production, replace with Prisma / DB persistence
interface FeedbackEntry {
  id: string;
  spotHash: string;
  verdict?: string;
  helpful: boolean;
  comment?: string;
  provider?: string;
  promptVersion?: string;
  timestamp: number;
  ip?: string;
}

const feedbackStore: FeedbackEntry[] = [];
const MAX_STORE = 5000;

function getClientIp(req: NextRequest): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  const realIp = req.headers.get("x-real-ip");
  if (realIp) return realIp.trim();
  const ip = (req as unknown as { ip?: string }).ip;
  if (ip) return ip;
  return "unknown";
}

export async function POST(req: NextRequest) {
  try {
    let body: Record<string, unknown>;
    try {
      body = (await req.json()) as Record<string, unknown>;
    } catch {
      return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }

    const spotHash = body.spotHash as string | undefined;
    const helpful = body.helpful as boolean | undefined;
    const verdict = body.verdict as string | undefined;
    const comment = body.comment as string | undefined;
    const provider = body.provider as string | undefined;
    const promptVersion = body.promptVersion as string | undefined;

    if (!spotHash || typeof spotHash !== "string") {
      return NextResponse.json({ error: "Missing required field: spotHash" }, { status: 400 });
    }
    if (typeof helpful !== "boolean") {
      return NextResponse.json({ error: "Missing required field: helpful (boolean)" }, { status: 400 });
    }

    const entry: FeedbackEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      spotHash,
      verdict,
      helpful,
      comment: comment ? String(comment).slice(0, 1000) : undefined,
      provider,
      promptVersion,
      timestamp: Date.now(),
      ip: getClientIp(req),
    };

    feedbackStore.push(entry);
    if (feedbackStore.length > MAX_STORE) feedbackStore.shift();

    console.log(
      `[coach:feedback] spotHash=${spotHash} helpful=${helpful} provider=${provider || "unknown"} promptVersion=${promptVersion || "unknown"} verdict=${verdict || "—"}`
    );

    return NextResponse.json({ ok: true, id: entry.id }, { status: 201 });
  } catch (err) {
    console.error("[coach:feedback] error", err);
    return NextResponse.json({ error: "Failed to save feedback", details: String(err) }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const spotHash = url.searchParams.get("spotHash");
  const limit = Math.min(parseInt(url.searchParams.get("limit") || "50", 10) || 50, 200);

  let entries = feedbackStore;
  if (spotHash) entries = entries.filter((e) => e.spotHash === spotHash);

  const total = entries.length;
  const helpful = entries.filter((e) => e.helpful).length;
  const notHelpful = total - helpful;

  return NextResponse.json({
    status: "ok",
    endpoint: "/api/coach/feedback",
    total,
    helpful,
    notHelpful,
    helpfulRate: total > 0 ? helpful / total : null,
    entries: entries.slice(-limit).reverse(),
  });
}
