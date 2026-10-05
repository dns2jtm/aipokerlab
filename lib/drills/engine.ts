import type { LeakResult } from "@/lib/leaks/detectors";

export type DrillAction = "raise" | "call" | "fold" | "check" | "bet" | "check-raise";

export interface DrillHand {
  id: string;
  board: string;
  heroCards: string;
  heroPosition: string;
  villainPosition: string;
  pot: number;
  stackBB: number;
  street: string;
  villainAction?: string;
  betSizePct?: number;
  gtoFreq: { raise: number; call: number; fold: number };
  gtoPrimary: DrillAction;
  ev: number;
  explanation: string;
  leakId: string;
}

export interface DrillPack {
  id: string;
  leakId: string;
  leakLabel: string;
  category: string;
  hands: DrillHand[];
  createdAt: string;
  dueAt: string;
  xpReward: number;
}

export interface DrillAttempt {
  drillId: string;
  handId: string;
  chosenAction: DrillAction;
  gtoAction: DrillAction;
  correct: boolean;
  evLoss: number;
  timeMs: number;
  createdAt: string;
}

export interface SpacedRepetitionState {
  drillId: string;
  leakId: string;
  attempts: DrillAttempt[];
  score: number;
  evScore: number;
  dueAt: string;
  intervalDays: number;
  streak: number;
  completedAt?: string;
}

const INTERVALS = [0, 1, 3, 7, 14, 30];

export function computeDueAt(score: number, streak: number): string {
  const idx = Math.min(streak, INTERVALS.length - 1);
  let days = INTERVALS[idx];
  if (score < 60) days = Math.max(0, days - 1);
  if (score < 40) days = 0;
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

export function computeXp(correct: boolean, evLoss: number): number {
  if (correct) return 10;
  if (evLoss > -0.3) return 5;
  return 2;
}

export function generateDrillPack(leak: LeakResult, count = 10): DrillPack {
  const hands: DrillHand[] = [];
  const seedBase = leak.leakId;
  for (let i = 0; i < count; i++) {
    const hand = generateHandForLeak(leak, i, seedBase);
    hands.push(hand);
  }
  const now = new Date();
  return {
    id: `drill-${leak.leakId}-${now.getTime()}`,
    leakId: leak.leakId,
    leakLabel: leak.subcategory,
    category: leak.category,
    hands,
    createdAt: now.toISOString(),
    dueAt: now.toISOString(),
    xpReward: 100,
  };
}

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

function generateHandForLeak(leak: LeakResult, idx: number, seedBase: string): DrillHand {
  const h = hashStr(`${seedBase}-${idx}`);
  const rnd = (h % 1000) / 1000;
  const rnd2 = ((h * 7) % 1000) / 1000;

  const templates: Record<string, Array<{ board: string; heroCards: string; heroPos: string; villainPos: string; street: string; villainAction: string; betPct?: number; gto: { raise: number; call: number; fold: number }; primary: DrillAction; ev: number; expl: string }>> = {
    vpip_high: [
      { board: "", heroCards: "J4o", heroPos: "CO", villainPos: "—", street: "preflop", villainAction: "folds to you", gto: { raise: 5, call: 0, fold: 95 }, primary: "fold", ev: -0.3, expl: "J4o CO is a pure fold — too weak, dominated, no playability." },
      { board: "", heroCards: "92o", heroPos: "BTN", villainPos: "—", street: "preflop", villainAction: "folds to you", gto: { raise: 12, call: 0, fold: 88 }, primary: "fold", ev: -0.2, expl: "92o BTN is mostly fold — GTO opens it 12% as steal, but mostly fold." },
    ],
    vpip_low: [
      { board: "", heroCards: "K9s", heroPos: "BTN", villainPos: "—", street: "preflop", villainAction: "folds to you", gto: { raise: 82, call: 0, fold: 18 }, primary: "raise", ev: 0.6, expl: "K9s BTN is a clear open — suited, broadway, 82% raise." },
      { board: "", heroCards: "Q9s", heroPos: "CO", villainPos: "—", street: "preflop", villainAction: "folds to you", gto: { raise: 65, call: 0, fold: 35 }, primary: "raise", ev: 0.4, expl: "Q9s CO is a 65% open — suited broadway with playability." },
    ],
    pfr_gap: [
      { board: "", heroCards: "A5s", heroPos: "BTN", villainPos: "—", street: "preflop", villainAction: "folds to you", gto: { raise: 78, call: 0, fold: 22 }, primary: "raise", ev: 0.7, expl: "A5s BTN should raise 78% — don't limp, raise for value and fold equity." },
      { board: "", heroCards: "KJs", heroPos: "CO", villainPos: "—", street: "preflop", villainAction: "folds to you", gto: { raise: 85, call: 0, fold: 15 }, primary: "raise", ev: 0.8, expl: "KJs CO is a premium open — raise 85%, never limp." },
    ],
    fold_to_3bet: [
      { board: "", heroCards: "AQo", heroPos: "CO", villainPos: "BTN", street: "preflop", villainAction: "3-bets to 9bb", gto: { raise: 15, call: 55, fold: 30 }, primary: "call", ev: 0.5, expl: "AQo vs 3-bet: call 55% / 4-bet 15% — too strong to fold, blocks AA/AK." },
      { board: "", heroCards: "TT", heroPos: "HJ", villainPos: "CO", street: "preflop", villainAction: "3-bets to 9bb", gto: { raise: 25, call: 60, fold: 15 }, primary: "call", ev: 0.9, expl: "TT vs 3-bet is a call 60% — set mining + overpair value, fold only 15%." },
    ],
    three_bet_low: [
      { board: "", heroCards: "A4s", heroPos: "BB", villainPos: "BTN", street: "preflop", villainAction: "opens 2.5x", gto: { raise: 35, call: 55, fold: 10 }, primary: "raise", ev: 0.5, expl: "A4s BB vs BTN: 3-bet 35% as bluff — blocks AA/AK, flops well." },
      { board: "", heroCards: "K9s", heroPos: "BB", villainPos: "CO", street: "preflop", villainAction: "opens 2.5x", gto: { raise: 28, call: 62, fold: 10 }, primary: "call", ev: 0.3, expl: "K9s BB vs CO: mix 3-bet 28% / call 62% — suited broadway plays well both ways." },
    ],
    cbet_high: [
      { board: "Ah Kd 4s", heroCards: "7c 6c", heroPos: "BTN", villainPos: "BB", street: "flop", villainAction: "checks to you", betPct: 33, gto: { raise: 0, call: 0, fold: 0 }, primary: "check", ev: 0.1, expl: "76s on AK4r has no equity — check back, don't c-bet air into strength." },
      { board: "Qh 7d 2c", heroCards: "As 5s", heroPos: "BTN", villainPos: "BB", street: "flop", villainAction: "checks to you", betPct: 33, gto: { raise: 45, call: 0, fold: 0 }, primary: "bet", ev: 0.4, expl: "A5s on Q72r has backdoor + overcard — c-bet 45% small, check 55%." },
    ],
    cbet_low: [
      { board: "Kc Qd Jc", heroCards: "Ah Kd", heroPos: "BTN", villainPos: "BB", street: "flop", villainAction: "checks to you", betPct: 33, gto: { raise: 78, call: 0, fold: 0 }, primary: "bet", ev: 0.9, expl: "AK on KQJ has top pair + straight draw — c-bet 78% for value and protection." },
      { board: "9s 8s 3c", heroCards: "As Ks", heroPos: "BTN", villainPos: "BB", street: "flop", villainAction: "checks to you", betPct: 66, gto: { raise: 62, call: 0, fold: 0 }, primary: "bet", ev: 0.6, expl: "AKs on 983ss has two overs + nut flush draw — c-bet 62% large." },
    ],
    fold_vs_cbet: [
      { board: "Qh 7d 2c", heroCards: "As 5s", heroPos: "BB", villainPos: "BTN", street: "flop", villainAction: "bets 33% pot", betPct: 33, gto: { raise: 12, call: 58, fold: 30 }, primary: "call", ev: 0.42, expl: "A5s on Q72r vs 33%: call 58% — backdoor flush + overcard, 38% equity." },
      { board: "Qh 7d 2c", heroCards: "9c 2d", heroPos: "BB", villainPos: "BTN", street: "flop", villainAction: "bets 33% pot", betPct: 33, gto: { raise: 2, call: 10, fold: 88 }, primary: "fold", ev: -0.1, expl: "92o on Q72r vs 33%: fold 88% — no draw, no pair, pure fold." },
    ],
    check_raise_low: [
      { board: "Qh 7d 2c", heroCards: "Qd Jd", heroPos: "BB", villainPos: "BTN", street: "flop", villainAction: "bets 33% pot", betPct: 33, gto: { raise: 18, call: 62, fold: 20 }, primary: "raise", ev: 0.7, expl: "QJ on Q72r vs 33%: check-raise 18% for value — top pair good kicker, protect vs draws." },
      { board: "7h 6h 2d", heroCards: "8d 7d", heroPos: "BB", villainPos: "BTN", street: "flop", villainAction: "bets 33% pot", betPct: 33, gto: { raise: 22, call: 55, fold: 23 }, primary: "raise", ev: 0.5, expl: "87s on 762hh vs 33%: check-raise 22% — pair + flush draw, semi-bluff." },
    ],
    turn_barrel_fold: [
      { board: "Qh 7d 2c 5h", heroCards: "Qd Jd", heroPos: "BB", villainPos: "BTN", street: "turn", villainAction: "bets 66% pot", betPct: 66, gto: { raise: 5, call: 95, fold: 0 }, primary: "call", ev: 1.2, expl: "QJ (top pair) vs turn barrel 66%: call 95% — MDF 60%, top pair never folds." },
      { board: "Qh 7d 2c Kh", heroCards: "As 5s", heroPos: "BB", villainPos: "BTN", street: "turn", villainAction: "bets 66% pot", betPct: 66, gto: { raise: 8, call: 42, fold: 50 }, primary: "fold", ev: -0.2, expl: "A5s on Q72Kh vs 66%: fold 50% — backdoor missed, no pair, overcard not enough." },
    ],
    river_call_efficiency: [
      { board: "Qh 7d 2c 5h 2s", heroCards: "Qd Jd", heroPos: "BB", villainPos: "BTN", street: "river", villainAction: "bets 66% pot", betPct: 66, gto: { raise: 0, call: 72, fold: 28 }, primary: "call", ev: 0.8, expl: "QJ on Q722 vs 66%: call 72% — top pair, blocks Qx value, unblocks bluffs." },
      { board: "Qh 7d 2c 5h 2s", heroCards: "9c 8c", heroPos: "BB", villainPos: "BTN", street: "river", villainAction: "bets 66% pot", betPct: 66, gto: { raise: 0, call: 12, fold: 88 }, primary: "fold", ev: -0.3, expl: "98s on Q722 vs 66%: fold 88% — no pair, no blocker, pure bluff catcher fail." },
    ],
    thin_value_missed: [
      { board: "Qh 7d 2c 5h 2s", heroCards: "Ah Qc", heroPos: "BTN", villainPos: "BB", street: "river", villainAction: "checks to you", betPct: 50, gto: { raise: 68, call: 0, fold: 0 }, primary: "bet", ev: 1.1, expl: "AQ on Q722 vs check: bet 68% thin value — top pair good kicker, get called by Qx worse." },
      { board: "Kc Qd Jc 2h 3s", heroCards: "Kc Qc", heroPos: "BTN", villainPos: "BB", street: "river", villainAction: "checks to you", betPct: 50, gto: { raise: 55, call: 0, fold: 0 }, primary: "bet", ev: 0.7, expl: "KQ on KQJ23 vs check: bet 55% thin value — two pair, but board straight possible, still value." },
    ],
  };

  const pool = templates[leak.leakId] || templates["fold_vs_cbet"];
  const tpl = pool[idx % pool.length];

  const jitter = (n: number) => Math.max(0, Math.min(100, n + Math.round((rnd - 0.5) * 6)));
  const gtoFreq = { raise: jitter(tpl.gto.raise), call: jitter(tpl.gto.call), fold: jitter(tpl.gto.fold) };
  const sum = gtoFreq.raise + gtoFreq.call + gtoFreq.fold;
  if (sum !== 100) gtoFreq.fold += 100 - sum;

  let primary: DrillAction = tpl.primary;
  if (gtoFreq.raise >= gtoFreq.call && gtoFreq.raise >= gtoFreq.fold) primary = "raise";
  else if (gtoFreq.call >= gtoFreq.fold) primary = "call";
  else primary = "fold";
  if (tpl.villainAction.includes("checks to you")) {
    if (primary === "raise") primary = "bet";
    if (primary === "fold") primary = "check";
    if (primary === "call") primary = "check";
  }

  return {
    id: `hand-${leak.leakId}-${idx + 1}`,
    board: tpl.board,
    heroCards: tpl.heroCards,
    heroPosition: tpl.heroPos,
    villainPosition: tpl.villainPos,
    pot: 7.5 + rnd2 * 15,
    stackBB: 100,
    street: tpl.street,
    villainAction: tpl.villainAction,
    betSizePct: tpl.betPct,
    gtoFreq,
    gtoPrimary: primary,
    ev: tpl.ev,
    explanation: tpl.expl,
    leakId: leak.leakId,
  };
}

const drillStore = new Map<string, DrillPack>();
const attemptStore = new Map<string, DrillAttempt[]>();

export function saveDrillPack(pack: DrillPack) {
  drillStore.set(pack.id, pack);
}

export function getDrillPack(id: string): DrillPack | undefined {
  return drillStore.get(id);
}

export function listDrillPacks(): DrillPack[] {
  return Array.from(drillStore.values());
}

export function recordAttempt(attempt: DrillAttempt) {
  const list = attemptStore.get(attempt.drillId) || [];
  list.push(attempt);
  attemptStore.set(attempt.drillId, list);
}

export function getAttempts(drillId: string): DrillAttempt[] {
  return attemptStore.get(drillId) || [];
}

export function computeProgress(drillId: string): { correct: number; total: number; xp: number; avgEvLoss: number } {
  const attempts = getAttempts(drillId);
  const correct = attempts.filter((a) => a.correct).length;
  const total = attempts.length;
  const xp = attempts.reduce((acc, a) => acc + computeXp(a.correct, a.evLoss), 0);
  const avgEvLoss = total ? attempts.reduce((acc, a) => acc + a.evLoss, 0) / total : 0;
  return { correct, total, xp, avgEvLoss };
}
