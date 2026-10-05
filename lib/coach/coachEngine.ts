import {
  buildContext,
  type CoachingCardV2,
  type ContextBuilderInput,
  type SolverContext,
  type HandContext,
  type LeakHistoryItem,
} from "./promptComposer";

// Re-export for convenience
export type { CoachingCardV2, SolverContext, HandContext, LeakHistoryItem };

export interface CoachRequest {
  hand: HandContext;
  solverResult: SolverContext;
  leakHistory: LeakHistoryItem[];
  tone?: "concise" | "detailed" | "math-heavy";
}

export interface CoachResponseMeta {
  spotHash: string;
  solverGrounded: boolean;
  tokens: number;
  temp: number;
  model: string;
  cached: boolean;
}

// Realistic mock coaching templates grounded in solver EV
const MOCK_TEMPLATES: Array<{
  verdict: CoachingCardV2["verdict"];
  rule: string;
  example: string;
  drill: string;
  why: string;
  summary: string;
}> = [
  {
    verdict: "mistake",
    rule: "Call any backdoor flush + overcard vs a small (33%) c-bet — you have 38% equity and realize 85% when you call.",
    example: "A♠5♠, K♥9♥, Q♦J♦ all call on Q♥7♦2♣ vs 33% pot; A♦2♣ without a backdoor folds. Your hand has the same backdoor + overcard as the calls.",
    drill: "5 BB vs BTN spots on dry Q-high boards — practice calling vs small bets with backdoors.",
    why: "Solver says check-raise 12%, call 58%, fold 30% with A5s here. Folding gives up 0.8bb in EV because villain's small bet needs to work 25% of the time, but you fold 68% in this spot (GTO 42%). Villain can exploit by betting 100% of hands.",
    summary: "Fold was -0.8bb — backdoor + overcard is a clear call vs small bet.",
  },
  {
    verdict: "big_mistake",
    rule: "Never over-fold BB vs BTN open — defend at least 58% (call 45% + 3-bet 13%) or villain prints money opening 100%.",
    example: "BB vs BTN 100bb: defend K8s, Q9s, JTs, 22+, A2s+; fold only the bottom 42% like J4o, 92o, 73o. You folded K9s which is a mandatory defend.",
    drill: "10 BB defend spots vs BTN open — learn the 58% defend threshold and which hands mix 3-bet.",
    why: "You fold 68% vs BTN open, GTO is 42%. At 68% fold, villain's 2.5x open needs only 42% folds to profit — you're giving 4.2bb/100. Solver defends K9s 82% (call 62% / 3-bet 20%).",
    summary: "Over-folding BB vs BTN is your #1 leak: -4.2bb/100. K9s is a clear defend.",
  },
  {
    verdict: "mistake",
    rule: "Delayed c-bet turn when flop checks through and you pick up equity — bet 66% pot with 30%+ equity + backdoors.",
    example: "Flop Q72r checks through, turn 5♥ gives you A5s a gutshot + flush draw: bet 66% pot. Without equity (e.g., A2o on same runout) check again.",
    drill: "5 delayed c-bet spots where flop checked through — practice betting turns when you gain equity.",
    why: "You checked turn after flop checked through, missing a 38% delayed c-bet spot (GTO 38%, you 22%). Solver bets A5s 71% on this turn for 66% pot, gaining 0.6bb vs checking. Checking lets villain realize 100% equity for free.",
    summary: "Missed delayed c-bet on turn — checking cost 0.6bb, you do this 16% too often.",
  },
  {
    verdict: "good",
    rule: "Your fold vs c-bet is disciplined — keep folding bottom pair no kicker vs large bets, but call with second pair+ or draws.",
    example: "On Q72r vs 66% pot: fold 84o, A2o; call QJ, 77, A5s with backdoor; raise sets. Your fold with 92o was correct — solver folds it 88%.",
    drill: "5 fold-vs-c-bet spots to calibrate — learn which weak pairs are folds vs calls vs raises.",
    why: "Solver folds 45% vs c-bet on this texture, you fold 58% — slightly over-folding but this specific hand (92o, no draw) is a pure fold (88% fold). EV loss only 0.1bb, well within variance. Keep this discipline.",
    summary: "Good fold — 92o is a pure fold vs c-bet, only 0.1bb from GTO. Keep it up.",
  },
  {
    verdict: "mistake",
    rule: "3-bet more vs late position opens — 3-bet 12-15% vs BTN/CO, not 6%. Use suited blockers (A2s-A5s, K9s, QJs) as bluffs.",
    example: "BTN opens, you're in BB with A4s: 3-bet 35% / call 65% (GTO). You called 100% — missing value and fold equity. A4s blocks AA/AK and flops well when called.",
    drill: "10 3-bet spots BB vs BTN/CO — practice mixing 3-bets with suited Ax and broadways.",
    why: "You 3-bet 6% vs BTN open, GTO is 13%. Each missed 3-bet with A4s costs 0.4bb (call EV 0.1bb vs 3-bet EV 0.5bb). Over 100 hands that's 2.8bb/100. Solver 3-bets A4s 35% for balance and to deny BTN's equity.",
    summary: "Too passive preflop — A4s should 3-bet 35% vs BTN, you never do. -0.4bb this hand.",
  },
  {
    verdict: "big_mistake",
    rule: "Don't fold to turn barrels with top pair — call turn with any top pair+ or strong draw vs 66% pot (MDF 60%).",
    example: "You hold QJ on Q72-5, villain bets 66% pot on turn: call 100% (GTO). You folded — solver never folds top pair here. Fold only weak pairs like 72, 92 without draws.",
    drill: "8 turn barrel defense spots — practice calling top pair+ vs second barrels, folding only weak pairs.",
    why: "You folded QJ (top pair) to a turn barrel — solver calls 100%, EV loss 2.1bb. You fold 62% vs turn barrels, GTO 38%. Villain can barrel any two cards profitably. MDF says you must defend 60% vs 66% pot.",
    summary: "Huge mistake — folding top pair vs turn barrel is -2.1bb. You over-fold turns by 24%.",
  },
];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

export function generateMockCoachingCard(input: CoachRequest): CoachingCardV2 {
  const seed = `${input.hand.heroCards || "As5s"}-${input.hand.board || "Qh7d2c"}-${input.solverResult.spotHash || "abc"}-${input.leakHistory.length}`;
  const idx = hashString(seed) % MOCK_TEMPLATES.length;
  const tpl = MOCK_TEMPLATES[idx];

  // Derive EV loss from solver or template
  const evLoss = input.solverResult.evLoss ?? (tpl.verdict === "big_mistake" ? -1.8 : tpl.verdict === "mistake" ? -0.8 : -0.1);
  const absLoss = Math.abs(evLoss);

  // Adjust verdict by EV if solver provides it
  let verdict = tpl.verdict;
  if (absLoss > 1.2) verdict = "big_mistake";
  else if (absLoss > 0.3) verdict = "mistake";
  else verdict = "good";

  const spotHash = input.solverResult.spotHash || `mock-${hashString(seed).toString(16).slice(0, 8)}`;
  const gtoFreq = input.solverResult.gtoFreq || input.solverResult.strategyMap?.[input.hand.heroCards || "As5s"] || { raise: 12, call: 58, fold: 30 };

  // Personalize with leak history
  const topLeak = input.leakHistory[0];
  const leakNote = topLeak ? ` Your ${topLeak.subcategory} leak (${topLeak.frequency || topLeak.evLossBBper100 + "bb/100"}) makes this spot extra important.` : "";

  return {
    verdict,
    rule: tpl.rule,
    example: tpl.example,
    drill: tpl.drill + leakNote,
    evLoss,
    nextStep: verdict === "good" ? "Nice — queue 5 more spots to lock it in?" : `Fix this leak: drill 5 similar spots now?`,
    summary: tpl.summary,
    why: tpl.why + leakNote,
    heuristic: tpl.rule,
    drillSuggestion: { type: topLeak?.subcategory || "BB vs BTN", spotHash },
    spotHash,
    gtoFreq,
    solverGrounded: !!input.solverResult.spotHash,
  };
}

export function buildCoachingContext(input: CoachRequest) {
  const ctxInput: ContextBuilderInput = {
    hand: input.hand,
    solverResult: input.solverResult,
    leakHistory: input.leakHistory,
    userTone: input.tone,
  };
  return buildContext(ctxInput);
}

// Streaming helper — yields JSON chunks for mock LLM streaming
export async function* streamCoachingCard(card: CoachingCardV2, chunkSize = 40, delayMs = 18): AsyncGenerator<string> {
  const json = JSON.stringify(card);
  for (let i = 0; i < json.length; i += chunkSize) {
    yield json.slice(i, i + chunkSize);
    if (delayMs > 0) await new Promise((r) => setTimeout(r, delayMs));
  }
}

export function getStreamingHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-cache",
    "X-Coach-Temp": "0.3",
    "X-Coach-Grounded": "true",
    "X-Coach-Tos": "post-hand-only",
  };
}

export const COACH_CONFIG = {
  temp: 0.3,
  maxTokens: 800,
  model: "mock-gpt-4o",
  grounded: true,
  tos: "post-hand study only — not for use during play",
} as const;
