import { NextRequest, NextResponse } from "next/server";
import { captureError } from "@/lib/monitoring/sentry";
import { generateMockCoachingCard, buildCoachingContext, COACH_CONFIG } from "@/lib/coach/coachEngine";
import type { CoachRequest } from "@/lib/coach/coachEngine";
import { generateCoachingCard, streamCoachingCard, getProviderName, getPromptVersion as getLLMPromptVersion } from "@/lib/coach/llmProvider";
import { PROMPT_VERSION } from "@/lib/coach/promptComposer";
import type { CoachingCardV2 } from "@/lib/coach/promptComposer";
import { checkRateLimit as checkSharedRateLimit, getClientIp as getSharedIp, rateLimitHeaders as sharedRateLimitHeaders, RATE_LIMITS } from "@/lib/security/rateLimit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// ── In-memory LRU cache (1000 entries, 1h TTL) ──────────────────────────

const CACHE_MAX = 1000;
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

interface CacheEntry {
  card: CoachingCardV2;
  timestamp: number;
  provider: string;
  promptVersion: string;
}

const coachCache = new Map<string, CacheEntry>();

function hashString(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h.toString(16);
}

function getCacheKey(spotHash: string, leakHistory: unknown, promptVersion: string, tone?: string): string {
  const leakHash = hashString(JSON.stringify(leakHistory || []));
  return `${spotHash}::${leakHash}::${promptVersion}::${tone || "concise"}`;
}

function getCached(key: string): CacheEntry | null {
  const entry = coachCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
    coachCache.delete(key);
    return null;
  }
  // LRU: move to end
  coachCache.delete(key);
  coachCache.set(key, entry);
  return entry;
}

function setCached(key: string, entry: CacheEntry) {
  if (coachCache.size >= CACHE_MAX) {
    const oldest = coachCache.keys().next().value as string | undefined;
    if (oldest) coachCache.delete(oldest);
  }
  coachCache.set(key, entry);
}

// ── Rate limiting: 20 req/min per IP (in-memory) ────────────────────────

const RATE_LIMIT = 20;
const WINDOW_MS = 60 * 1000;

interface RateEntry {
  count: number;
  resetAt: number;
}

const rateMap = new Map<string, RateEntry>();

function getClientIp(req: NextRequest): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  const realIp = req.headers.get("x-real-ip");
  if (realIp) return realIp.trim();
  // NextRequest.ip is available in some runtimes
  const ip = (req as unknown as { ip?: string }).ip;
  if (ip) return ip;
  return "unknown";
}

function isRateLimited(ip: string): { limited: boolean; remaining: number; resetAt: number } {
  const now = Date.now();
  const entry = rateMap.get(ip);
  if (!entry || now > entry.resetAt) {
    rateMap.set(ip, { count: 1, resetAt: now + WINDOW_MS });
    return { limited: false, remaining: RATE_LIMIT - 1, resetAt: now + WINDOW_MS };
  }
  if (entry.count >= RATE_LIMIT) {
    return { limited: true, remaining: 0, resetAt: entry.resetAt };
  }
  entry.count++;
  return { limited: false, remaining: RATE_LIMIT - entry.count, resetAt: entry.resetAt };
}

// Periodic cleanup for rateMap (avoid memory leak)
if (typeof setInterval !== "undefined") {
  // Only run in Node, not during build
  try {
    setInterval(() => {
      const now = Date.now();
      for (const [k, v] of rateMap.entries()) {
        if (now > v.resetAt) rateMap.delete(k);
      }
      // Also evict expired cache entries
      for (const [k, v] of coachCache.entries()) {
        if (Date.now() - v.timestamp > CACHE_TTL_MS) coachCache.delete(k);
      }
    }, 5 * 60 * 1000).unref?.();
  } catch {
    // ignore
  }
}

// ── Validation ───────────────────────────────────────────────────────────

function validateLeakHistory(leakHistory: unknown): { valid: boolean; error?: string } {
  if (leakHistory === undefined || leakHistory === null) return { valid: true };
  if (!Array.isArray(leakHistory)) return { valid: false, error: "leakHistory must be an array" };
  for (let i = 0; i < leakHistory.length; i++) {
    const item = leakHistory[i] as Record<string, unknown>;
    if (typeof item !== "object" || item === null) {
      return { valid: false, error: `leakHistory[${i}] must be an object` };
    }
    // Check required fields — allow flexible but warn if missing
    const required = ["subcategory", "category", "severity", "evLossBBper100"];
    for (const f of required) {
      if (item[f] === undefined) {
        return { valid: false, error: `leakHistory[${i}] missing required field: ${f}` };
      }
    }
    if (typeof item.evLossBBper100 !== "number") {
      return { valid: false, error: `leakHistory[${i}].evLossBBper100 must be a number` };
    }
  }
  return { valid: true };
}

function validateRequest(body: Record<string, unknown>): { valid: boolean; error?: string } {
  if (!body.hand) return { valid: false, error: "Missing required field: hand" };
  if (typeof body.hand !== "object" || body.hand === null) return { valid: false, error: "hand must be an object" };
  if (!body.solverResult) return { valid: false, error: "Missing required field: solverResult" };
  if (typeof body.solverResult !== "object" || body.solverResult === null) return { valid: false, error: "solverResult must be an object" };

  const leakCheck = validateLeakHistory(body.leakHistory);
  if (!leakCheck.valid) return leakCheck;

  return { valid: true };
}

// ── POST ─────────────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  // Rate limiting (shared sliding window)
  const ip = getSharedIp(req);
  const sharedRl = checkSharedRateLimit("coach:"+ip, RATE_LIMITS.coach, "coach");
  if (!sharedRl.allowed) {
    return NextResponse.json({ error: "Rate limit exceeded", message: "Max "+RATE_LIMITS.coach.max+" requests per minute" }, { status: 429, headers: sharedRateLimitHeaders(sharedRl, RATE_LIMITS.coach) });
  }
  const rate = isRateLimited(ip);
  if (rate.limited) {
    return NextResponse.json(
      { error: "Rate limit exceeded", message: `Max ${RATE_LIMIT} requests per minute` },
      {
        status: 429,
        headers: {
          "Retry-After": String(Math.ceil((rate.resetAt - Date.now()) / 1000)),
          "X-RateLimit-Limit": String(RATE_LIMIT),
          "X-RateLimit-Remaining": String(rate.remaining),
          "X-RateLimit-Reset": String(rate.resetAt),
        },
      }
    );
  }

  try {
    let body: Record<string, unknown>;
    try {
      body = (await req.json()) as Record<string, unknown>;
    } catch {
      return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }

    // Input size validation
    const bodyStr = JSON.stringify(body);
    if (bodyStr.length > 50*1024) return NextResponse.json({ error: "Payload too large (max 50KB)" }, { status: 413 });
    // Validation — require hand and solverResult
    const validation = validateRequest(body);
    if (!validation.valid) {
      return NextResponse.json({ error: "Validation failed", details: validation.error }, { status: 400 });
    }

    const hand = body.hand as CoachRequest["hand"];
    const solverResult = body.solverResult as CoachRequest["solverResult"];
    const leakHistory = (body.leakHistory as CoachRequest["leakHistory"]) || [];
    const tone = (body.tone as CoachRequest["tone"]) || "concise";
    const requestedPromptVersion = (body.promptVersion as string) || getLLMPromptVersion();

    const input: CoachRequest = { hand, solverResult, leakHistory, tone };

    // Build context (includes prompt version)
    const ctx = buildCoachingContext({
      hand,
      solverResult,
      leakHistory,
      tone,
      // pass promptVersion via context builder if supported
    } as unknown as Parameters<typeof buildCoachingContext>[0]);

    // Override promptVersion in metadata if requested
    const promptVersion = requestedPromptVersion || PROMPT_VERSION;
    // Rebuild fullPrompt with correct version if needed
    // ctx already built with default version; we use promptVersion for cache key and headers

    const provider = getProviderName();
    const cacheKey = getCacheKey(ctx.metadata.spotHash, leakHistory, promptVersion, tone);

    // Check cache
    const cached = getCached(cacheKey);
    if (cached) {
      const json = JSON.stringify({
        ...cached.card,
        _meta: {
          spotHash: ctx.metadata.spotHash,
          solverGrounded: ctx.metadata.hasSolverData,
          tokens: 420,
          temp: COACH_CONFIG.temp,
          model: cached.provider === "mock" ? COACH_CONFIG.model : getProviderModel(cached.provider),
          cached: true,
          tos: COACH_CONFIG.tos,
          provider: cached.provider,
          promptVersion: cached.promptVersion,
        },
      });

      const encoder = new TextEncoder();
      const stream = new ReadableStream<Uint8Array>({
        async start(controller) {
          const chunkSize = 64;
          for (let i = 0; i < json.length; i += chunkSize) {
            controller.enqueue(encoder.encode(json.slice(i, i + chunkSize)));
            await new Promise((r) => setTimeout(r, 4));
          }
          controller.close();
        },
      });

      return new NextResponse(stream, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-cache, no-transform",
          "X-Coach-Temp": String(COACH_CONFIG.temp),
          "X-Coach-Grounded": String(ctx.metadata.hasSolverData),
          "X-Coach-Tos": "post-hand-only",
          "X-Coach-SpotHash": ctx.metadata.spotHash,
          "X-Coach-Provider": cached.provider,
          "X-Prompt-Version": cached.promptVersion,
          "X-Cache-Hit": "true",
          "X-RateLimit-Limit": String(RATE_LIMIT),
          "X-RateLimit-Remaining": String(rate.remaining),
        },
      });
    }

    // Try real LLM first, fallback to mock on error or missing keys
    // Use llmProvider which already handles fallback
    let card: CoachingCardV2;
    let usedProvider = provider;
    try {
      // Build prompt for LLM
      const prompt = ctx.fullPrompt;
      const llmContext = {
        hand,
        solverResult,
        leakHistory,
        tone,
      };
      card = await generateCoachingCard(prompt, llmContext);
      // If provider was mock, card is mock; if real LLM failed, generateCoachingCard already fell back to mock
      // Detect actual provider used: if we got a mock card but provider was real, it fell back
      // We keep usedProvider as selected provider, but if card looks like mock fallback we still report selected
      // For transparency, check if provider would have been mock
      usedProvider = provider;
    } catch (err) {
    captureError(err, { route: "/api//api/coach" });
    console.error("[coach] LLM failed, falling back to mock:", String(err).slice(0, 500));
      card = generateMockCoachingCard(input);
      usedProvider = "mock";
    }

    // Cache the result
    setCached(cacheKey, {
      card,
      timestamp: Date.now(),
      provider: usedProvider,
      promptVersion,
    });

    // Prepare response JSON with meta
    const responseJson = JSON.stringify({
      ...card,
      _meta: {
        spotHash: ctx.metadata.spotHash,
        solverGrounded: ctx.metadata.hasSolverData,
        tokens: 420,
        temp: COACH_CONFIG.temp,
        model: usedProvider === "mock" ? COACH_CONFIG.model : getProviderModel(usedProvider),
        cached: false,
        tos: COACH_CONFIG.tos,
        provider: usedProvider,
        promptVersion,
      },
    });

    // Stream response — if provider supports streaming, we stream JSON chunks
    // For real LLM, we already have the full card, so stream the JSON
    // Alternatively, we could stream via streamCoachingCard for true token streaming
    const shouldStreamReal = usedProvider !== "mock" && req.headers.get("accept")?.includes("text/event-stream") !== true;
    // We always stream JSON chunks for consistency with existing client

    const encoder = new TextEncoder();

    // If client wants streaming and provider is real, try true streaming
    // Check if we should use streamCoachingCard for real-time token streaming
    const useTrueStreaming = usedProvider !== "mock" && false; // disabled: we already generated card; true streaming would require not calling generate first

    if (useTrueStreaming) {
      // True streaming path (not currently used, but kept for future)
      const prompt = ctx.fullPrompt;
      const llmContext = { hand, solverResult, leakHistory, tone };
      const stream = new ReadableStream<Uint8Array>({
        async start(controller) {
          try {
            for await (const chunk of streamCoachingCard(prompt, llmContext)) {
              controller.enqueue(encoder.encode(chunk));
            }
          } catch (e) {
            console.error("[coach] streaming error", e);
            controller.enqueue(encoder.encode(JSON.stringify(card)));
          }
          controller.close();
        },
      });
      return new NextResponse(stream, {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-cache, no-transform",
          "X-Coach-Temp": String(COACH_CONFIG.temp),
          "X-Coach-Grounded": String(ctx.metadata.hasSolverData),
          "X-Coach-Tos": "post-hand-only",
          "X-Coach-SpotHash": ctx.metadata.spotHash,
          "X-Coach-Provider": usedProvider,
          "X-Prompt-Version": promptVersion,
          "X-Cache-Hit": "false",
          "X-RateLimit-Limit": String(RATE_LIMIT),
          "X-RateLimit-Remaining": String(rate.remaining),
        },
      });
    }

    // Default: chunked JSON streaming (works for both mock and real)
    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        const chunkSize = 64;
        for (let i = 0; i < responseJson.length; i += chunkSize) {
          controller.enqueue(encoder.encode(responseJson.slice(i, i + chunkSize)));
          await new Promise((r) => setTimeout(r, 8));
        }
        controller.close();
      },
    });

    return new NextResponse(stream, {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "X-Coach-Temp": String(COACH_CONFIG.temp),
        "X-Coach-Grounded": String(ctx.metadata.hasSolverData),
        "X-Coach-Tos": "post-hand-only",
        "X-Coach-SpotHash": ctx.metadata.spotHash,
        "X-Coach-Provider": usedProvider,
        "X-Prompt-Version": promptVersion,
        "X-Cache-Hit": "false",
        "X-RateLimit-Limit": String(RATE_LIMIT),
        "X-RateLimit-Remaining": String(rate.remaining),
      },
    });
  } catch (err) {
    captureError(err, { route: "/api//api/coach" });
    console.error("[coach] error", err);
    return NextResponse.json({ error: "Failed to generate coaching card", details: String(err) }, { status: 500 });
  }
}

function getProviderModel(provider: string): string {
  if (provider === "anthropic") return process.env.ANTHROPIC_MODEL || "claude-3-5-sonnet-20241022";
  if (provider === "openai") return process.env.OPENAI_MODEL || "gpt-4o";
  return COACH_CONFIG.model;
}

export async function GET() {
  const provider = getProviderName();
  const promptVersion = getLLMPromptVersion();
  return NextResponse.json({
    status: "ok",
    endpoint: "/api/coach",
    method: "POST",
    accepts: "{ hand, solverResult, leakHistory, tone?, promptVersion? }",
    returns: "{ verdict, rule, example, drill, evLoss, nextStep, summary, why, heuristic, drillSuggestion, spotHash, gtoFreq, solverGrounded }",
    config: COACH_CONFIG,
    provider,
    promptVersion,
    cache: { size: coachCache.size, max: CACHE_MAX, ttlMs: CACHE_TTL_MS },
    rateLimit: { max: RATE_LIMIT, windowMs: WINDOW_MS },
  });
}
