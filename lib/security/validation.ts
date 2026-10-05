import { z } from "zod";

// We use zod if available, otherwise fallback to manual validation.
// To avoid hard dep, we try to use zod but also export manual validators.

export const emailSchema = z.string().trim().toLowerCase().max(254).email();

export const parseSchema = z.object({
  rawText: z.string().min(1, "rawText is required").max(100 * 1024, "rawText too large (max 100KB)"),
  raw: z.string().optional(),
}).passthrough().transform((v) => ({
  rawText: (v.rawText || (v as unknown as { raw?: string }).raw || "") as string,
})).refine((v) => v.rawText.trim().length > 0, { message: "rawText is required and must be non-empty" });

export const solveSchema = z.object({
  spot: z.object({
    board: z.string().max(100).optional().default(""),
    heroRange: z.string().max(200).optional(),
    villainRange: z.string().max(200).optional(),
    pot: z.union([z.number(), z.string()]).optional(),
    stacks: z.union([z.number(), z.string()]).optional(),
    betSizings: z.array(z.number()).max(10).optional(),
    rake: z.number().min(0).max(0.2).optional(),
    street: z.string().max(20).optional(),
    position: z.string().max(20).optional(),
    heroCards: z.string().max(20).optional(),
  }).passthrough().optional(),
  board: z.string().max(100).optional(),
  street: z.string().max(20).optional(),
}).passthrough();

export const coachSchema = z.object({
  hand: z.object({
    id: z.string().max(100).optional(),
    heroCards: z.string().max(20).optional(),
    board: z.string().max(100).optional(),
    street: z.string().max(20).optional(),
    heroPosition: z.string().max(20).optional(),
    villainPosition: z.string().max(20).optional(),
    actions: z.array(z.object({ player: z.string().max(50), action: z.string().max(100) }).passthrough()).max(50).optional(),
    rawText: z.string().max(5000).optional(),
  }).passthrough(),
  solverResult: z.object({
    spotHash: z.string().max(100),
    board: z.string().max(100).optional(),
    heroCards: z.string().max(20).optional(),
    heroPosition: z.string().max(20).optional(),
    villainPosition: z.string().max(20).optional(),
    pot: z.number().optional(),
    gtoFreq: z.object({ raise: z.number(), call: z.number(), fold: z.number() }).passthrough().optional(),
    evLoss: z.number().optional(),
    source: z.string().max(20).optional(),
  }).passthrough(),
  leakHistory: z.array(z.object({
    subcategory: z.string().max(100),
    category: z.string().max(50),
    severity: z.string().max(20),
    evLossBBper100: z.number(),
    frequency: z.string().max(100).optional(),
    sampleSize: z.number().optional(),
  }).passthrough()).max(20).optional(),
  tone: z.enum(["concise", "detailed", "math-heavy"]).optional(),
  promptVersion: z.string().max(20).optional(),
}).passthrough();

export const drillsGenerateSchema = z.object({
  leakId: z.string().min(1).max(100),
  count: z.number().int().min(1).max(20).optional().default(10),
}).passthrough();

export const drillsAttemptSchema = z.object({
  drillId: z.string().min(1).max(100),
  handId: z.string().min(1).max(100),
  chosenAction: z.string().min(1).max(20),
  timeMs: z.number().min(0).max(600000).optional(),
}).passthrough();

export const billingCheckoutSchema = z.object({
  plan: z.enum(["starter", "pro", "elite"]),
  email: z.string().trim().toLowerCase().max(254).email().optional(),
  userId: z.string().max(100).optional(),
}).passthrough();

export const emailSubscribeSchema = z.object({
  email: z.string().trim().toLowerCase().max(254).email(),
  source: z.string().max(100).optional(),
  website: z.string().max(500).optional(), // honeypot
}).passthrough();

// Manual fallback validators (used if zod not installed or for lightweight checks)
export function validateEmailStrict(email: unknown): { valid: boolean; error?: string } {
  if (typeof email !== "string") return { valid: false, error: "Email must be a string" };
  const s = email.trim().toLowerCase();
  if (!s) return { valid: false, error: "Email is required" };
  if (s.length > 254) return { valid: false, error: "Email too long" };
  const re = /^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$/i;
  if (!re.test(s)) return { valid: false, error: "Invalid email format" };
  if (s.includes("..")) return { valid: false, error: "Invalid email format" };
  return { valid: true };
}

export function validateRawText(raw: unknown): { valid: boolean; error?: string; value?: string } {
  const s = typeof raw === "string" ? raw : "";
  if (!s.trim()) return { valid: false, error: "rawText is required and must be non-empty" };
  if (s.length > 100 * 1024) return { valid: false, error: "rawText too large (max 100KB)" };
  return { valid: true, value: s };
}
