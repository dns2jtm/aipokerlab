export type Position = "UTG" | "HJ" | "CO" | "BTN" | "SB" | "BB";
export type StackDepth = "20bb" | "40bb" | "100bb" | "200bb";
export type Action = "raise" | "call" | "fold";

export interface GtoFreq {
  raise: number;
  call: number;
  fold: number;
}

export interface HandGto {
  hand: string;
  freq: GtoFreq;
  ev: number; // bb
  primary: Action;
}

// 13 ranks high to low
export const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"] as const;

export function handLabel(row: number, col: number): string {
  const r1 = RANKS[row];
  const r2 = RANKS[col];
  if (row === col) return `${r1}${r2}`;
  if (row < col) return `${r1}${r2}s`;
  return `${r2}${r1}o`; // row>col means offsuit, but keep higher rank first
}

// Deterministic mock GTO frequencies based on hand strength + position + stack
export function mockGtoForHand(
  hand: string,
  position: Position,
  stack: StackDepth
): HandGto {
  // hash hand + position + stack to deterministic numbers
  let h = 0;
  const s = `${hand}-${position}-${stack}`;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  const rnd = (h % 100) / 100;

  // hand strength heuristic
  const isPair = hand.length === 2;
  const isSuited = hand.endsWith("s");
  const rank1 = hand[0];
  const rank2 = hand[1];
  const rIdx = (r: string) => RANKS.indexOf(r as (typeof RANKS)[number]);
  const i1 = rIdx(rank1);
  const i2 = rIdx(rank2);
  const gap = Math.abs(i1 - i2);
  const highCard = Math.min(i1, i2); // 0 = A is strongest

  let strength = 0;
  if (isPair) strength = 1 - i1 / 13 + 0.3; // pairs strong
  else {
    strength = 1 - (highCard / 13) * 0.7 - gap * 0.04;
    if (isSuited) strength += 0.08;
    if (gap === 0) strength += 0.05;
  }
  // position adjustment: BTN/CO stronger ranges
  const posBonus: Record<Position, number> = {
    UTG: -0.18,
    HJ: -0.1,
    CO: 0.0,
    BTN: 0.12,
    SB: 0.05,
    BB: 0.0,
  };
  strength += posBonus[position];
  // stack: deeper = tighter
  const stackAdj: Record<StackDepth, number> = {
    "20bb": 0.08,
    "40bb": 0.03,
    "100bb": 0,
    "200bb": -0.05,
  };
  strength += stackAdj[stack];
  strength = Math.max(0, Math.min(1, strength));

  // add deterministic noise
  strength = strength * 0.85 + rnd * 0.15;

  let freq: GtoFreq;
  let ev: number;
  if (strength > 0.72) {
    // premium: mostly raise
    const raise = 75 + rnd * 20;
    const call = (100 - raise) * 0.3;
    freq = { raise: Math.round(raise), call: Math.round(call), fold: Math.round(100 - raise - call) };
    ev = 1.5 + rnd * 1.2;
  } else if (strength > 0.52) {
    const raise = 35 + rnd * 30;
    const call = 20 + rnd * 20;
    freq = { raise: Math.round(raise), call: Math.round(call), fold: Math.round(100 - raise - call) };
    ev = 0.3 + rnd * 0.8;
  } else if (strength > 0.32) {
    const call = 25 + rnd * 25;
    const fold = 40 + rnd * 30;
    freq = { raise: Math.round(100 - call - fold), call: Math.round(call), fold: Math.round(fold) };
    ev = -0.1 + rnd * 0.4;
  } else {
    const fold = 70 + rnd * 25;
    const call = (100 - fold) * 0.5;
    freq = { raise: Math.round(100 - fold - call), call: Math.round(call), fold: Math.round(fold) };
    ev = -0.4 + rnd * 0.3;
  }
  // normalize to 100
  const sum = freq.raise + freq.call + freq.fold;
  if (sum !== 100) freq.fold += 100 - sum;

  let primary: Action = "fold";
  if (freq.raise >= freq.call && freq.raise >= freq.fold) primary = "raise";
  else if (freq.call >= freq.fold) primary = "call";

  return { hand, freq, ev: Math.round(ev * 100) / 100, primary };
}

export function getPreflopRange(position: Position, stack: StackDepth): HandGto[] {
  const out: HandGto[] = [];
  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < 13; c++) {
      const label = handLabel(r, c);
      out.push(mockGtoForHand(label, position, stack));
    }
  }
  return out;
}
