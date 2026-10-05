import type { CoachingCardV2 } from "./promptComposer";
import { generateMockCoachingCard } from "./coachEngine";
import type { CoachRequest } from "./coachEngine";

// ── Types ────────────────────────────────────────────────────────────────

export type LLMProviderName = "openai" | "anthropic" | "mock";

export interface LLMProvider {
  name: LLMProviderName;
  generateCoachingCard(prompt: string, context: CoachingContext): Promise<CoachingCardV2>;
  streamCoachingCard(prompt: string, context: CoachingContext): AsyncGenerator<string>;
}

export interface CoachingContext {
  hand: CoachRequest["hand"];
  solverResult: CoachRequest["solverResult"];
  leakHistory: CoachRequest["leakHistory"];
  tone?: string;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  estimatedCostUsd: number;
  provider: LLMProviderName;
  model: string;
}

// ── Cost estimation (approx per 1K tokens, 2024 pricing) ───────────────

const COST_PER_1K: Record<string, { input: number; output: number }> = {
  "gpt-4o": { input: 0.0025, output: 0.01 },
  "gpt-4o-mini": { input: 0.00015, output: 0.0006 },
  "claude-3-5-sonnet-20241022": { input: 0.003, output: 0.015 },
  "claude-3-5-sonnet-latest": { input: 0.003, output: 0.015 },
  mock: { input: 0, output: 0 },
};

function estimateCost(model: string, promptTokens: number, completionTokens: number): number {
  const c = COST_PER_1K[model] ?? COST_PER_1K["gpt-4o"];
  return (promptTokens / 1000) * c.input + (completionTokens / 1000) * c.output;
}

function logUsage(usage: TokenUsage) {
  const costStr = usage.estimatedCostUsd < 0.01 ? `$${usage.estimatedCostUsd.toFixed(5)}` : `$${usage.estimatedCostUsd.toFixed(4)}`;
  console.log(
    `[coach:llm] provider=${usage.provider} model=${usage.model} tokens=${usage.totalTokens} (in=${usage.promptTokens} out=${usage.completionTokens}) cost=${costStr}`
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────

function getEnv(key: string): string | undefined {
  try {
    return process.env[key];
  } catch {
    return undefined;
  }
}

export function selectProvider(): LLMProviderName {
  const forced = getEnv("COACH_PROVIDER")?.toLowerCase();
  if (forced === "openai" || forced === "anthropic" || forced === "mock") return forced;
  if (getEnv("ANTHROPIC_API_KEY")) return "anthropic";
  if (getEnv("OPENAI_API_KEY")) return "openai";
  return "mock";
}

export function getModelForProvider(provider: LLMProviderName): string {
  if (provider === "anthropic") return getEnv("ANTHROPIC_MODEL") || "claude-3-5-sonnet-20241022";
  if (provider === "openai") return getEnv("OPENAI_MODEL") || "gpt-4o";
  return "mock-gpt-4o";
}

// Retry with exponential backoff
async function withRetry<T>(fn: () => Promise<T>, retries = 2, baseDelayMs = 600): Promise<T> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (attempt === retries) break;
      const delay = baseDelayMs * Math.pow(2, attempt) + Math.random() * 200;
      console.warn(`[coach:llm] attempt ${attempt + 1} failed, retrying in ${Math.round(delay)}ms:`, String(err).slice(0, 300));
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  throw lastErr;
}

// Timeout wrapper
function withTimeout<T>(promise: Promise<T>, ms: number, label = "LLM"): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) => setTimeout(() => reject(new Error(`${label} timeout after ${ms}ms`)), ms)),
  ]);
}

// ── JSON parsing & validation ───────────────────────────────────────────

const REQUIRED_FIELDS: (keyof CoachingCardV2)[] = ["verdict", "rule", "example", "drill", "evLoss", "nextStep", "summary", "why"];

function parseAndValidateCoachingCard(raw: string, fallbackContext: CoachingContext): CoachingCardV2 {
  let jsonStr = raw.trim();
  const fenceMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenceMatch) jsonStr = fenceMatch[1].trim();
  if (!jsonStr.startsWith("{")) {
    const objMatch = jsonStr.match(/\{[\s\S]*\}/);
    if (objMatch) jsonStr = objMatch[0];
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(jsonStr) as Record<string, unknown>;
  } catch (e) {
    throw new Error(`Failed to parse LLM JSON: ${String(e).slice(0, 200)} | raw: ${jsonStr.slice(0, 400)}`);
  }

  for (const f of REQUIRED_FIELDS) {
    if (parsed[f] === undefined || parsed[f] === null || parsed[f] === "") {
      throw new Error(`LLM response missing required field: ${f}`);
    }
  }

  const verdict = String(parsed.verdict);
  if (!["good", "mistake", "big_mistake"].includes(verdict)) {
    (parsed as Record<string, unknown>).verdict = "mistake";
  }

  if (typeof parsed.evLoss !== "number") {
    const n = Number(parsed.evLoss);
    parsed.evLoss = isNaN(n) ? (fallbackContext.solverResult.evLoss ?? -0.5) : n;
  }

  const spotHash = (parsed.spotHash as string) || fallbackContext.solverResult.spotHash || "unknown";
  const gtoFreq =
    (parsed.gtoFreq as CoachingCardV2["gtoFreq"]) ||
    fallbackContext.solverResult.gtoFreq ||
    { raise: 12, call: 58, fold: 30 };

  const card: CoachingCardV2 = {
    verdict: parsed.verdict as CoachingCardV2["verdict"],
    rule: String(parsed.rule),
    example: String(parsed.example),
    drill: String(parsed.drill),
    evLoss: parsed.evLoss as number,
    nextStep: String(parsed.nextStep),
    summary: String(parsed.summary),
    why: String(parsed.why),
    heuristic: String(parsed.heuristic || parsed.rule),
    drillSuggestion: (parsed.drillSuggestion as CoachingCardV2["drillSuggestion"]) || {
      type: fallbackContext.leakHistory[0]?.subcategory || "general",
      spotHash,
    },
    spotHash,
    gtoFreq,
    solverGrounded: (parsed.solverGrounded as boolean) ?? !!fallbackContext.solverResult.spotHash,
  };

  return card;
}

// ── OpenAI provider ─────────────────────────────────────────────────────

async function callOpenAI(prompt: string, systemPrompt: string): Promise<{ text: string; usage: TokenUsage }> {
  const apiKey = getEnv("OPENAI_API_KEY");
  if (!apiKey) throw new Error("OPENAI_API_KEY not set");
  const model = getModelForProvider("openai");

  let OpenAI: unknown;
  try {
    const mod = (await import("openai")) as unknown as { default: unknown };
    OpenAI = mod.default;
  } catch {
    throw new Error("openai SDK not installed — run npm install openai");
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const client = new (OpenAI as any)({ apiKey });

  const completion: {
    choices?: Array<{ message?: { content?: string } }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  } = await withTimeout(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (client as any).chat.completions.create({
      model,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: prompt },
      ],
      temperature: 0.3,
      max_tokens: 800,
      response_format: { type: "json_object" },
    }),
    15000,
    "OpenAI"
  );

  const choice = completion.choices?.[0];
  const text: string = choice?.message?.content ?? "";
  if (!text) throw new Error("OpenAI returned empty content");

  const promptTokens = completion.usage?.prompt_tokens ?? Math.ceil(prompt.length / 4);
  const completionTokens = completion.usage?.completion_tokens ?? Math.ceil(text.length / 4);
  const totalTokens = completion.usage?.total_tokens ?? promptTokens + completionTokens;

  const usage: TokenUsage = {
    promptTokens,
    completionTokens,
    totalTokens,
    estimatedCostUsd: estimateCost(model, promptTokens, completionTokens),
    provider: "openai",
    model,
  };
  logUsage(usage);
  return { text, usage };
}

async function* streamOpenAI(prompt: string, systemPrompt: string): AsyncGenerator<string> {
  const apiKey = getEnv("OPENAI_API_KEY");
  if (!apiKey) throw new Error("OPENAI_API_KEY not set");
  const model = getModelForProvider("openai");

  let OpenAI: unknown;
  try {
    const mod = (await import("openai")) as unknown as { default: unknown };
    OpenAI = mod.default;
  } catch {
    throw new Error("openai SDK not installed");
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const client = new (OpenAI as any)({ apiKey });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const stream = await (client as any).chat.completions.create({
    model,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: prompt },
    ],
    temperature: 0.3,
    max_tokens: 800,
    response_format: { type: "json_object" },
    stream: true,
  });

  for await (const chunk of stream as AsyncIterable<{ choices?: Array<{ delta?: { content?: string } }> }>) {
    const content = chunk.choices?.[0]?.delta?.content;
    if (content) yield content;
  }
}

// ── Anthropic provider ──────────────────────────────────────────────────

async function callAnthropic(prompt: string, systemPrompt: string): Promise<{ text: string; usage: TokenUsage }> {
  const apiKey = getEnv("ANTHROPIC_API_KEY");
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY not set");
  const model = getModelForProvider("anthropic");

  let Anthropic: unknown;
  try {
    // Use Function to avoid static analysis requiring the module at build time
    const mod = (await Function("return import('@anthropic-ai/sdk')")()) as unknown as { default: unknown };
    Anthropic = mod.default;
  } catch {
    throw new Error("@anthropic-ai/sdk not installed — run npm install @anthropic-ai/sdk");
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const client = new (Anthropic as any)({ apiKey });

  const response: {
    content?: Array<{ type: string; text?: string }>;
    usage?: { input_tokens?: number; output_tokens?: number };
  } = await withTimeout(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (client as any).messages.create({
      model,
      max_tokens: 800,
      temperature: 0.3,
      system: systemPrompt,
      messages: [{ role: "user", content: prompt }],
    }),
    15000,
    "Anthropic"
  );

  const textBlock = response.content?.find((b: { type: string }) => b.type === "text");
  const text: string = textBlock?.text ?? "";
  if (!text) throw new Error("Anthropic returned empty content");

  const promptTokens = response.usage?.input_tokens ?? Math.ceil(prompt.length / 4);
  const completionTokens = response.usage?.output_tokens ?? Math.ceil(text.length / 4);
  const totalTokens = promptTokens + completionTokens;

  const usage: TokenUsage = {
    promptTokens,
    completionTokens,
    totalTokens,
    estimatedCostUsd: estimateCost(model, promptTokens, completionTokens),
    provider: "anthropic",
    model,
  };
  logUsage(usage);
  return { text, usage };
}

async function* streamAnthropic(prompt: string, systemPrompt: string): AsyncGenerator<string> {
  const apiKey = getEnv("ANTHROPIC_API_KEY");
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY not set");
  const model = getModelForProvider("anthropic");

  let Anthropic: unknown;
  try {
    const mod = (await Function("return import('@anthropic-ai/sdk')")()) as unknown as { default: unknown };
    Anthropic = mod.default;
  } catch {
    throw new Error("@anthropic-ai/sdk not installed");
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const client = new (Anthropic as any)({ apiKey });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const stream = await (client as any).messages.stream({
    model,
    max_tokens: 800,
    temperature: 0.3,
    system: systemPrompt,
    messages: [{ role: "user", content: prompt }],
  });

  for await (const chunk of stream as AsyncIterable<{ type: string; delta?: { text?: string } }>) {
    if (chunk.type === "content_block_delta" && chunk.delta?.text) {
      yield chunk.delta.text;
    }
  }
}

// ── System prompt for LLM calls ─────────────────────────────────────────

function getSystemPromptForLLM(): string {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { SYSTEM_PROMPT_V2 } = require("./promptComposer") as { SYSTEM_PROMPT_V2: string };
    return SYSTEM_PROMPT_V2;
  } catch {
    return "You are Lab Coach — a GTO expert. Respond with valid JSON only.";
  }
}

// ── Public API ───────────────────────────────────────────────────────────

export async function generateCoachingCard(prompt: string, context: CoachingContext): Promise<CoachingCardV2> {
  const provider = selectProvider();

  if (provider === "mock") {
    return generateMockCoachingCard({
      hand: context.hand,
      solverResult: context.solverResult,
      leakHistory: context.leakHistory,
      tone: (context.tone as "concise" | "detailed" | "math-heavy") || "concise",
    });
  }

  const systemPrompt = getSystemPromptForLLM();

  const attempt = async (): Promise<CoachingCardV2> => {
    let raw: string;
    if (provider === "anthropic") {
      const res = await callAnthropic(prompt, systemPrompt);
      raw = res.text;
    } else {
      const res = await callOpenAI(prompt, systemPrompt);
      raw = res.text;
    }
    return parseAndValidateCoachingCard(raw, context);
  };

  try {
    return await withRetry(() => withTimeout(attempt(), 15000, `LLM:${provider}`), 2, 600);
  } catch (err) {
    console.error(`[coach:llm] ${provider} failed after retries, falling back to mock:`, String(err).slice(0, 500));
    return generateMockCoachingCard({
      hand: context.hand,
      solverResult: context.solverResult,
      leakHistory: context.leakHistory,
      tone: (context.tone as "concise" | "detailed" | "math-heavy") || "concise",
    });
  }
}

export async function* streamCoachingCard(prompt: string, context: CoachingContext): AsyncGenerator<string> {
  const provider = selectProvider();

  if (provider === "mock") {
    const card = generateMockCoachingCard({
      hand: context.hand,
      solverResult: context.solverResult,
      leakHistory: context.leakHistory,
      tone: (context.tone as "concise" | "detailed" | "math-heavy") || "concise",
    });
    const json = JSON.stringify(card);
    const chunkSize = 40;
    for (let i = 0; i < json.length; i += chunkSize) {
      yield json.slice(i, i + chunkSize);
      await new Promise((r) => setTimeout(r, 18));
    }
    return;
  }

  const systemPrompt = getSystemPromptForLLM();

  try {
    if (provider === "anthropic") {
      yield* streamAnthropic(prompt, systemPrompt);
    } else {
      yield* streamOpenAI(prompt, systemPrompt);
    }
  } catch (err) {
    console.error(`[coach:llm] streaming ${provider} failed, falling back to mock:`, String(err).slice(0, 500));
    const card = generateMockCoachingCard({
      hand: context.hand,
      solverResult: context.solverResult,
      leakHistory: context.leakHistory,
      tone: (context.tone as "concise" | "detailed" | "math-heavy") || "concise",
    });
    const json = JSON.stringify(card);
    const chunkSize = 40;
    for (let i = 0; i < json.length; i += chunkSize) {
      yield json.slice(i, i + chunkSize);
      await new Promise((r) => setTimeout(r, 18));
    }
  }
}

// ── Helpers for API route ────────────────────────────────────────────────

export function getProviderName(): LLMProviderName {
  return selectProvider();
}

export function getPromptVersion(): string {
  return getEnv("COACH_PROMPT_VERSION") || "v2.1";
}

// Export for testing
export const _internal = {
  parseAndValidateCoachingCard,
  estimateCost,
  withRetry,
  withTimeout,
};
