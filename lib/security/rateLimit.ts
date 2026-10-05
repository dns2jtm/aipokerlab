import { NextRequest } from "next/server";

export interface RateLimitConfig {
  windowMs: number;
  max: number;
}

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: number;
  retryAfterMs?: number;
}

interface Entry {
  timestamps: number[];
}

const stores = new Map<string, Map<string, Entry>>();

function getStore(namespace: string): Map<string, Entry> {
  let s = stores.get(namespace);
  if (!s) {
    s = new Map();
    stores.set(namespace, s);
  }
  return s;
}

export function getClientIp(req: NextRequest): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  const realIp = req.headers.get("x-real-ip");
  if (realIp) return realIp.trim();
  const ip = (req as unknown as { ip?: string }).ip;
  if (ip) return ip;
  return "unknown";
}

/**
 * Sliding window rate limiter (in-memory).
 * Keeps timestamps within windowMs, checks count < max.
 */
export function checkRateLimit(
  key: string,
  config: RateLimitConfig,
  namespace = "default"
): RateLimitResult {
  const now = Date.now();
  const store = getStore(namespace);
  let entry = store.get(key);
  if (!entry) {
    entry = { timestamps: [] };
    store.set(key, entry);
  }
  // Evict outside window
  entry.timestamps = entry.timestamps.filter((t) => now - t < config.windowMs);
  if (entry.timestamps.length >= config.max) {
    const oldest = entry.timestamps[0];
    const resetAt = oldest + config.windowMs;
    return {
      allowed: false,
      remaining: 0,
      resetAt,
      retryAfterMs: Math.max(0, resetAt - now),
    };
  }
  entry.timestamps.push(now);
  const remaining = config.max - entry.timestamps.length;
  const resetAt = entry.timestamps[0] + config.windowMs;
  return { allowed: true, remaining, resetAt };
}

export function rateLimitHeaders(result: RateLimitResult, config: RateLimitConfig): Record<string, string> {
  const headers: Record<string, string> = {
    "X-RateLimit-Limit": String(config.max),
    "X-RateLimit-Remaining": String(result.remaining),
    "X-RateLimit-Reset": String(result.resetAt),
  };
  if (!result.allowed && result.retryAfterMs !== undefined) {
    headers["Retry-After"] = String(Math.ceil(result.retryAfterMs / 1000));
  }
  return headers;
}

export const RATE_LIMITS: Record<string, RateLimitConfig> = {
  parse: { windowMs: 60_000, max: 30 },
  solve: { windowMs: 60_000, max: 10 },
  coach: { windowMs: 60_000, max: 20 },
  drills: { windowMs: 60_000, max: 30 },
  billing: { windowMs: 60_000, max: 10 },
  email: { windowMs: 60_000, max: 5 },
  default: { windowMs: 60_000, max: 60 },
};

// Periodic cleanup to avoid memory leak
if (typeof setInterval !== "undefined") {
  try {
    setInterval(() => {
      const now = Date.now();
      for (const store of stores.values()) {
        for (const [k, v] of store.entries()) {
          v.timestamps = v.timestamps.filter((t) => now - t < 60_000 * 5);
          if (v.timestamps.length === 0) store.delete(k);
        }
      }
    }, 5 * 60 * 1000).unref?.();
  } catch {
    // ignore
  }
}

export function clearRateLimitStore(namespace?: string) {
  if (namespace) stores.delete(namespace);
  else stores.clear();
}
