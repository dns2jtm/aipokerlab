import crypto from "crypto";

// ── In-memory store with Prisma-ready interface ─────────────────────────

export type Subscriber = {
  email: string;
  source: string;
  confirmed: boolean;
  token: string;
  createdAt: string;
  confirmedAt?: string;
  ip?: string;
};

const subscribersByEmail = new Map<string, Subscriber>();
const subscribersByToken = new Map<string, Subscriber>();

export function generateToken(): string {
  return crypto.randomBytes(32).toString("hex");
}

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 254;
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

// Prisma-ready interface: swap to Prisma when DB ready
export const emailStore = {
  async findByEmail(email: string): Promise<Subscriber | null> {
    return subscribersByEmail.get(normalizeEmail(email)) || null;
  },
  async findByToken(token: string): Promise<Subscriber | null> {
    return subscribersByToken.get(token) || null;
  },
  async create(data: { email: string; source: string; token: string; ip?: string }): Promise<Subscriber> {
    const email = normalizeEmail(data.email);
    const sub: Subscriber = {
      email,
      source: data.source,
      confirmed: false,
      token: data.token,
      createdAt: new Date().toISOString(),
      ip: data.ip,
    };
    subscribersByEmail.set(email, sub);
    subscribersByToken.set(data.token, sub);
    return sub;
  },
  async confirm(token: string): Promise<Subscriber | null> {
    const sub = subscribersByToken.get(token);
    if (!sub) return null;
    sub.confirmed = true;
    sub.confirmedAt = new Date().toISOString();
    return sub;
  },
  async list(): Promise<Subscriber[]> {
    return Array.from(subscribersByEmail.values());
  },
  // For testing
  _clear() {
    subscribersByEmail.clear();
    subscribersByToken.clear();
  },
};

// ── Rate limiting: 5/min per IP ─────────────────────────────────────────

const rateMap = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT = 5;
const WINDOW_MS = 60_000;

export function checkRateLimit(ip: string): { allowed: boolean; remaining: number; resetAt: number } {
  const now = Date.now();
  const entry = rateMap.get(ip);
  if (!entry || now > entry.resetAt) {
    const resetAt = now + WINDOW_MS;
    rateMap.set(ip, { count: 1, resetAt });
    return { allowed: true, remaining: RATE_LIMIT - 1, resetAt };
  }
  if (entry.count >= RATE_LIMIT) {
    return { allowed: false, remaining: 0, resetAt: entry.resetAt };
  }
  entry.count++;
  return { allowed: true, remaining: RATE_LIMIT - entry.count, resetAt: entry.resetAt };
}

export function getClientIp(req: Request): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  const realIp = req.headers.get("x-real-ip");
  if (realIp) return realIp.trim();
  return "unknown";
}
