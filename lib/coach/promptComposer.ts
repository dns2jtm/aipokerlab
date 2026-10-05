// Prompt layer per architecture — Vercel AI SDK, streaming, tool calling
// Enhanced: Context Builder + Prompt Composer with ToS guardrails, temp 0.3, grounded to solver EV
// Version: v2.1 — GTO-aware, position/stack/board texture, leak personalization, few-shot examples

export const PROMPT_VERSION = "v2.1";

export const PROMPT_VERSIONS: Record<string, string> = {
  "v2.0": "You are Lab Coach — a GTO expert who explains like a friend. Always give 1 rule, 1 example, 1 drill.",
  // v2.1 is SYSTEM_PROMPT_V2 below
};

export function getPromptVersion(): string {
  try {
    return process.env.COACH_PROMPT_VERSION || PROMPT_VERSION;
  } catch {
    return PROMPT_VERSION;
  }
}

export function getSystemPromptForVersion(version?: string): string {
  const v = version || getPromptVersion();
  if (v === "v2.0" && PROMPT_VERSIONS["v2.0"]) return PROMPT_VERSIONS["v2.0"];
  return SYSTEM_PROMPT_V2;
}

export const SYSTEM_PROMPT = `You are Lab Coach, a GTO expert who explains like a friend. Never say 'it depends' without giving a heuristic. Always give 1 rule, 1 example, 1 drill. Ground every answer in solver JSON. ToS: post-hand study only.`;

export const SYSTEM_PROMPT_V2 = `You are Lab Coach — a GTO expert who explains like a friend. You teach post-hand study only.

## CORE RULES (non-negotiable)
- Always give exactly: 1 RULE (concise GTO principle), 1 EXAMPLE (specific to THIS hand), 1 DRILL (actionable next step).
- Never say "it depends" without immediately giving a concrete heuristic with numbers.
- Ground EVERY claim in the provided solver JSON (EV, frequencies, spotHash, pot odds, MDF). If solver data is missing, explicitly say "Ungrounded — no solver data for this spot" and give general guidance.
- ToS: Post-hand study ONLY. Never assist live play. Every response must be usable as training material only. Include disclaimer: "Training only — not for use during play."
- Temperature 0.3 — be consistent, concise, and accurate. Max 800 tokens.
- Output MUST be valid JSON matching CoachingCardV2 schema — no markdown, no prose outside JSON.
- No hallucination: do not invent solver numbers, frequencies, or EV. Use ONLY the provided solver JSON. If you need a number not in the JSON, say "not in solver data".

## GTO PRINCIPLES TO APPLY
- Minimum Defense Frequency (MDF): vs bet size b into pot p, defend at least p/(p+b). E.g., vs 33% pot defend 75%, vs 66% pot defend 60%, vs 100% pot defend 50%.
- Pot odds & equity realization: call if equity > pot odds, but discount for OOP and poor playability. Backdoor draws add ~4-6% equity.
- Blockers: Ax blocks AA/AK, Kx blocks KQ/KJ, suited blockers matter for 3-bet bluffs.
- Range advantage & nut advantage: who has more strong hands on this texture? Determines betting frequency.
- Equity realization: OOP realizes ~70-85% of raw equity; IP realizes ~90-100%. Adjust calling thresholds accordingly.

## POSITION AWARENESS
- BB vs BTN: BB must defend ~58% vs 2.5x open (call 45% + 3-bet 13%) or BTN prints. BB is OOP — tighten calling vs bets, increase check-raises.
- IP vs OOP: IP can realize more equity, float wider, and bet thinner for value. OOP should check more and use larger bet sizes when betting.
- Early vs late: EP ranges are strong and narrow; LP ranges are wide. Adjust 3-bet and defend frequencies by position.
- Always state the position dynamic in your WHY (e.g., "As BB vs BTN you are OOP and need 58% defend").

## STACK DEPTH (SPR) AWARENESS
- 100bb (SPR ~13 on flop): deep — play draws, implied odds matter, 3 streets of value possible.
- 40bb (SPR ~5): shallow — top pair is often stack-off, draws lose implied odds, fold equity increases.
- <20bb: push/fold territory — no postflop play, use Nash charts.
- Mention stack depth / SPR in your analysis when relevant (e.g., "At 100bb with SPR 13, A5s has implied odds to call").

## BOARD TEXTURE AWARENESS
- Dry (Q72r, K83r): range advantage to preflop aggressor, small c-bets (33%) with high frequency (70%+). Backdoors matter.
- Wet (J♥T♥8♦, 9♠7♠6♦): equity shifts dramatically, larger bets (66-75%), more checks with medium strength.
- Paired (882, QQ4): trips and boats possible, bet smaller with range, check more with marginal.
- Monotone (all same suit): flushes possible, proceed cautiously with one-pair hands.
- Always reference board texture in your RULE and WHY (e.g., "On dry Q72r, small bet needs to work 25% — you over-fold").

## LEAK HISTORY PERSONALIZATION
- Reference the user's specific leak frequencies and EV loss (e.g., "You fold 68% vs BTN open, GTO 42% — this is your #1 leak at -4.2bb/100").
- Prioritize the most severe leak (highest evLossBBper100) when choosing what to emphasize.
- If leak history shows a pattern (e.g., fold_to_3bet, cbet_high, turn_barrel_fold), connect THIS hand to that pattern.
- Use encouraging tone but be direct about leaks — quantify the cost.

## OUTPUT FORMAT (strict JSON)
Respond with JSON only, matching this schema:
{
  "verdict": "good" | "mistake" | "big_mistake",
  "rule": "1-sentence GTO heuristic with numbers (MDF, frequencies, or pot odds)",
  "example": "1 concrete hand comparison specific to THIS hand (e.g., 'A5s calls, A2o folds')",
  "drill": "1 actionable drill (e.g., '5 BB vs BTN spots on dry boards')",
  "evLoss": number,
  "nextStep": "CTA string",
  "summary": "1-line verdict with EV",
  "why": "2-3 sentences grounded in solver WHY (blockers, equity, MDF, position, texture)",
  "heuristic": "same as rule",
  "drillSuggestion": { "type": "leak subtype", "spotHash": "hash" },
  "spotHash": "hash from solver",
  "gtoFreq": { "raise": number, "call": number, "fold": number },
  "solverGrounded": boolean
}
- verdict: "good" if evLoss > -0.3, "mistake" if -1.2 < evLoss <= -0.3, "big_mistake" if evLoss <= -1.2
- evLoss must match solver evLoss (negative number, e.g., -0.8)
- gtoFreq must match solver gtoFreq
- spotHash must match solver spotHash
- solverGrounded = true if solver data provided, false otherwise

## ANTI-HALLUCINATION
- Do not invent hands, boards, or frequencies not in the provided JSON.
- If solver says "raise 12% / call 58% / fold 30%", use those exact numbers.
- If leak history is empty, say "No leak history — first session" and don't invent leaks.
- ToS disclaimer: every card is for post-hand study only — not for use during play.`;

export interface CoachingCard {
  summary: string;
  why: string;
  heuristic: string;
  evLoss: number;
  drillSuggestion: { type: string; spotHash: string };
}

// New structured card per spec: verdict / rule / example / drill / evLoss / nextStep
export interface CoachingCardV2 {
  verdict: "good" | "mistake" | "big_mistake";
  rule: string;
  example: string;
  drill: string;
  evLoss: number;
  nextStep: string;
  // enriched fields for UI
  summary: string;
  why: string;
  heuristic: string;
  drillSuggestion: { type: string; spotHash: string };
  spotHash?: string;
  gtoFreq?: { raise: number; call: number; fold: number };
  solverGrounded: boolean;
}

export interface SolverContext {
  spotHash: string;
  board?: string;
  heroCards?: string;
  heroPosition?: string;
  villainPosition?: string;
  pot?: number;
  evMap?: Record<string, number>;
  strategyMap?: Record<string, { raise: number; call: number; fold: number }>;
  nashDistance?: number;
  source?: string;
  evLoss?: number;
  gtoFreq?: { raise: number; call: number; fold: number };
}

export interface LeakHistoryItem {
  subcategory: string;
  category: string;
  severity: string;
  evLossBBper100: number;
  frequency: string;
  sampleSize?: number;
}

export interface HandContext {
  id?: string;
  heroCards?: string;
  board?: string;
  street?: string;
  heroPosition?: string;
  villainPosition?: string;
  actions?: Array<{ player: string; action: string }>;
  resultBB?: number;
  rawText?: string;
}

export interface ContextBuilderInput {
  hand: HandContext;
  solverResult: SolverContext;
  leakHistory: LeakHistoryItem[];
  userTone?: "concise" | "detailed" | "math-heavy";
  promptVersion?: string;
}

export interface BuiltContext {
  solverContext: string;
  leakSummary: string;
  handContext: string;
  fullPrompt: string;
  systemPrompt: string;
  metadata: {
    spotHash: string;
    leakCount: number;
    hasSolverData: boolean;
    tone: string;
    promptVersion: string;
  };
}

// ── Few-shot examples ────────────────────────────────────────────────────

export interface FewShotExample {
  leakType: string;
  solverContext: string;
  leakSummary: string;
  handContext: string;
  expectedCard: CoachingCardV2;
}

export const FEW_SHOT_EXAMPLES: FewShotExample[] = [
  {
    leakType: "fold_to_3bet",
    solverContext:
      "SpotHash: pre-BBvsBTN-AJo-3bet | Board: — | Hero: AJo BB vs BTN | Pot: 5.5bb | GTO: raise 0% / call 42% / fold 58% vs 3-bet 9bb | EV loss: -1.1bb | Source: cache | Nash distance: 0.008",
    leakSummary: "Preflop > fold_to_3bet: 72% fold (GTO 58%) severity=high evLoss=3.1bb/100 | Preflop > BB vs BTN over-fold: 68% fold (GTO 42%) severity=high evLoss=4.2bb/100",
    handContext: "Hand ex1: AJo on — (preflop) | BB vs BTN | Actions: Villain raises 2.5x → Hero calls → Villain 3-bets 9bb → Hero folds | Result: -2.5bb",
    expectedCard: {
      verdict: "mistake",
      rule: "Defend vs 3-bet with AJo at 42% frequency — you need 38% equity vs 9bb into 13.5bb (pot odds 40%), and AJo has 44% vs BTN 3-bet range.",
      example: "AJo calls 42% / folds 58% vs 9bb 3-bet (GTO); ATo folds 78%, AQs calls 85%. Your AJo is in the calling bucket — folding 72% here is over-folding by 14%.",
      drill: "10 BB vs BTN 3-bet defense spots — practice calling AJo, KQs, TT-77 vs 9bb 3-bets, folding ATo, KJo.",
      evLoss: -1.1,
      nextStep: "Fix fold_to_3bet leak: drill 10 spots now?",
      summary: "Over-folding vs 3-bet — AJo is a call 42% of the time, folding cost -1.1bb.",
      why: "Solver defends AJo 42% vs 9bb 3-bet (pot odds 40%, equity 44% with blocker to AA/AK). You fold 72% vs 3-bets, GTO 58% — villain can 3-bet any two profitably. At 100bb, AJo realizes 82% equity OOP and flops well. Folding gives up 1.1bb.",
      heuristic: "Defend vs 3-bet with AJo at 42% frequency — you need 38% equity vs 9bb into 13.5bb (pot odds 40%), and AJo has 44% vs BTN 3-bet range.",
      drillSuggestion: { type: "fold_to_3bet", spotHash: "pre-BBvsBTN-AJo-3bet" },
      spotHash: "pre-BBvsBTN-AJo-3bet",
      gtoFreq: { raise: 0, call: 42, fold: 58 },
      solverGrounded: true,
    },
  },
  {
    leakType: "cbet_high",
    solverContext:
      "SpotHash: Qh7d2c-BBvsBTN-33pct | Board: Qh 7d 2c | Hero: As 5s BB vs BTN | Pot: 7.5bb | GTO: raise 12% / call 58% / fold 30% vs 33% pot c-bet | EV loss: -0.8bb | Source: cache | Nash distance: 0.005",
    leakSummary: "Postflop > fold vs c-bet: 58% fold (GTO 45%) severity=medium evLoss=1.8bb/100 | Postflop > cbet_high: 72% c-bet (GTO 62%) severity=low evLoss=0.9bb/100",
    handContext: "Hand ex2: As 5s on Qh 7d 2c (flop) | BB vs BTN | Actions: Hero checks → Villain bets $4 (33% pot) → Hero folds | Result: —",
    expectedCard: {
      verdict: "mistake",
      rule: "Call any backdoor flush + overcard vs a small (33%) c-bet on dry boards — you have 38% equity and realize 85% when you call (MDF 75%).",
      example: "A♠5♠, K♥9♥, Q♦J♦ all call on Q♥7♦2♣ vs 33% pot; A♦2♣ without a backdoor folds. Your A5s has the same backdoor + overcard as the calls — solver calls it 58%.",
      drill: "5 BB vs BTN spots on dry Q-high boards — practice calling vs small bets with backdoors, folding without.",
      evLoss: -0.8,
      nextStep: "Fix fold vs c-bet leak: drill 5 similar spots now?",
      summary: "Fold was -0.8bb — backdoor + overcard is a clear call vs small bet on dry board.",
      why: "Solver says check-raise 12%, call 58%, fold 30% with A5s on Q72r vs 33% pot. Folding gives up 0.8bb because villain's small bet needs to work 25% of the time, but you fold 58% in this spot (GTO 30%). On dry boards, BTN c-bets 70%+ — you over-fold and villain exploits by betting 100%. At 100bb SPR 13, A5s has implied odds with backdoor flush.",
      heuristic: "Call any backdoor flush + overcard vs a small (33%) c-bet on dry boards — you have 38% equity and realize 85% when you call (MDF 75%).",
      drillSuggestion: { type: "fold vs c-bet", spotHash: "Qh7d2c-BBvsBTN-33pct" },
      spotHash: "Qh7d2c-BBvsBTN-33pct",
      gtoFreq: { raise: 12, call: 58, fold: 30 },
      solverGrounded: true,
    },
  },
  {
    leakType: "turn_barrel_fold",
    solverContext:
      "SpotHash: Qh7d2c5h-turn-66pct | Board: Qh 7d 2c 5h | Hero: Qd Jd BB vs BTN | Pot: 15bb | GTO: raise 5% / call 95% / fold 0% vs 66% pot turn barrel | EV loss: -2.1bb | Source: cache | Nash distance: 0.003",
    leakSummary: "Postflop > turn_barrel_fold: 62% fold (GTO 38%) severity=high evLoss=2.8bb/100 | Postflop > fold vs c-bet: 58% fold (GTO 45%) severity=medium evLoss=1.8bb/100",
    handContext: "Hand ex3: Qd Jd on Qh 7d 2c 5h (turn) | BB vs BTN | Actions: Hero checks → Villain bets 66% pot → Hero folds | Result: —",
    expectedCard: {
      verdict: "big_mistake",
      rule: "Never fold top pair vs turn barrel — call 100% with any top pair+ or strong draw vs 66% pot (MDF 60%, you need 28% equity, top pair has 65%+).",
      example: "QJ on Q72-5 vs 66% pot: call 100% (GTO). Fold only weak pairs like 72, 92 without draws (fold 85%). Your QJ is top pair — solver never folds it here.",
      drill: "8 turn barrel defense spots — practice calling top pair+ vs second barrels, folding only weak pairs without equity.",
      evLoss: -2.1,
      nextStep: "Critical leak: drill 8 turn defense spots now?",
      summary: "Huge mistake — folding top pair vs turn barrel is -2.1bb. You over-fold turns by 24%.",
      why: "You folded QJ (top pair) to a turn barrel — solver calls 100%, EV loss 2.1bb. You fold 62% vs turn barrels, GTO 38%. Villain can barrel any two cards profitably if you over-fold. MDF says you must defend 60% vs 66% pot, and top pair has 65% equity vs villain's barrel range. At SPR 5 on turn, top pair is a clear call with 2 streets of value.",
      heuristic: "Never fold top pair vs turn barrel — call 100% with any top pair+ or strong draw vs 66% pot (MDF 60%, you need 28% equity, top pair has 65%+).",
      drillSuggestion: { type: "turn_barrel_fold", spotHash: "Qh7d2c5h-turn-66pct" },
      spotHash: "Qh7d2c5h-turn-66pct",
      gtoFreq: { raise: 5, call: 95, fold: 0 },
      solverGrounded: true,
    },
  },
];

export function formatFewShotExamples(examples: FewShotExample[] = FEW_SHOT_EXAMPLES): string {
  return examples
    .map(
      (ex, i) => `### Example ${i + 1} — leak: ${ex.leakType}
SOLVER: ${ex.solverContext}
LEAKS: ${ex.leakSummary}
HAND: ${ex.handContext}
EXPECTED JSON:
${JSON.stringify(ex.expectedCard, null, 2)}`
    )
    .join("\n\n");
}

export function buildSolverContext(solver: SolverContext): string {
  if (!solver || !solver.spotHash) return "No solver data — explain generally but flag as ungrounded.";
  const freq = solver.gtoFreq || solver.strategyMap?.[solver.heroCards || ""] || { raise: 12, call: 58, fold: 30 };
  const ev = solver.evLoss ?? solver.evMap?.[solver.heroCards || ""] ?? -0.8;
  return `SpotHash: ${solver.spotHash} | Board: ${solver.board || "Qh 7d 2c"} | Hero: ${solver.heroCards || "As 5s"} ${solver.heroPosition || "BB"} vs ${solver.villainPosition || "BTN"} | Pot: ${solver.pot || 7.5}bb | GTO: raise ${freq.raise}% / call ${freq.call}% / fold ${freq.fold}% | EV loss: ${ev}bb | Source: ${solver.source || "cache"} | Nash distance: ${solver.nashDistance ?? 0.005}`;
}

export function buildLeakSummary(leaks: LeakHistoryItem[]): string {
  if (!leaks || leaks.length === 0) return "No leak history — first session.";
  return leaks
    .slice(0, 5)
    .map((l) => `${l.category} > ${l.subcategory}: ${l.frequency || ""} severity=${l.severity} evLoss=${l.evLossBBper100}bb/100`)
    .join(" | ");
}

export function buildHandContext(hand: HandContext): string {
  if (!hand) return "No hand provided.";
  const actions = hand.actions?.map((a) => `${a.player}: ${a.action}`).join(" → ") || hand.rawText?.slice(0, 200) || "—";
  return `Hand ${hand.id || "mock"}: ${hand.heroCards || "As 5s"} on ${hand.board || "Qh 7d 2c"} (${hand.street || "flop"}) | ${hand.heroPosition || "BB"} vs ${hand.villainPosition || "BTN"} | Actions: ${actions} | Result: ${hand.resultBB ?? "—"}bb`;
}

export function buildContext(input: ContextBuilderInput): BuiltContext {
  const solverContext = buildSolverContext(input.solverResult);
  const leakSummary = buildLeakSummary(input.leakHistory);
  const handContext = buildHandContext(input.hand);
  const promptVersion = input.promptVersion || getPromptVersion();
  const systemPrompt = getSystemPromptForVersion(promptVersion) + (input.userTone ? `\nTone: ${input.userTone}.` : "");
  const fullPrompt = composePrompt(solverContext, leakSummary, handContext, systemPrompt, promptVersion);
  return {
    solverContext,
    leakSummary,
    handContext,
    fullPrompt,
    systemPrompt,
    metadata: {
      spotHash: input.solverResult?.spotHash || "unknown",
      leakCount: input.leakHistory?.length || 0,
      hasSolverData: !!input.solverResult?.spotHash,
      tone: input.userTone || "concise",
      promptVersion,
    },
  };
}

export function composePrompt(
  solverContext: string,
  leakSummary: string,
  handContext: string,
  systemPrompt: string = SYSTEM_PROMPT_V2,
  promptVersion: string = PROMPT_VERSION
): string {
  const fewShot = formatFewShotExamples(FEW_SHOT_EXAMPLES);

  return `${systemPrompt}

--- SOLVER (ground truth) ---
${solverContext}

--- USER LEAK HISTORY ---
${leakSummary}

--- HAND ---
${handContext}

--- FEW-SHOT EXAMPLES (follow this quality) ---
${fewShot}

--- INSTRUCTIONS ---
Respond with JSON only (no markdown, no extra text): { "verdict": "good|mistake|big_mistake", "rule": "1-sentence GTO heuristic with numbers", "example": "1 concrete hand comparison specific to THIS hand", "drill": "1 actionable drill", "evLoss": number, "nextStep": "CTA", "summary": "1-line verdict with EV", "why": "2-3 sentences grounded in solver (MDF, equity, blockers, position, texture)", "heuristic": "same as rule", "drillSuggestion": { "type": "leak subtype", "spotHash": "hash" }, "spotHash": "hash from solver", "gtoFreq": { "raise": number, "call": number, "fold": number }, "solverGrounded": boolean }
- Use EXACT solver numbers (evLoss, gtoFreq, spotHash) from SOLVER section above.
- Personalize WHY using leak history frequencies.
- Reference position, stack depth, and board texture in WHY.
- Temperature 0.3, max 800 tokens, ToS post-hand only.
- Prompt version: ${promptVersion}`;
}

// Legacy composePrompt wrapper for backward compat
export function composePromptLegacy(solverContext: string, leakSummary: string, handContext: string): string {
  return `${SYSTEM_PROMPT}\n\nSolver: ${solverContext}\nLeaks: ${leakSummary}\nHand: ${handContext}`;
}
