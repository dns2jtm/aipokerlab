// Leak detectors per architecture — 12 core leaks v1
// Each detector takes array of Hand objects and returns ranked leak with EV loss

export type LeakCategory = "Preflop" | "Postflop" | "Turn" | "River";
export type Severity = "low" | "medium" | "high";

export interface LeakDef {
  id: string;
  category: LeakCategory;
  subcategory: string;
  description: string;
  gtoBenchmark: string;
}

export const LEAK_DEFS: LeakDef[] = [
  { id: "vpip_high", category: "Preflop", subcategory: "VPIP too high", description: "Playing too many hands preflop", gtoBenchmark: "GTO 22% VPIP (6-max 100bb)" },
  { id: "vpip_low", category: "Preflop", subcategory: "VPIP too low", description: "Playing too few hands — missing value", gtoBenchmark: "GTO 22% VPIP" },
  { id: "pfr_gap", category: "Preflop", subcategory: "VPIP/PFR gap", description: "VPIP/PFR gap too wide — calling too much, raising too little", gtoBenchmark: "GTO gap 4% (22/18)" },
  { id: "fold_to_3bet", category: "Preflop", subcategory: "Fold to 3-bet", description: "Over-folding vs 3-bets — exploitable", gtoBenchmark: "GTO 55% fold vs 3-bet" },
  { id: "three_bet_low", category: "Preflop", subcategory: "3-bet too low", description: "3-betting too rarely — missing value and fold equity", gtoBenchmark: "GTO 8% 3-bet" },
  { id: "cbet_high", category: "Postflop", subcategory: "c-bet too high", description: "c-betting too often — bluffing into strength", gtoBenchmark: "GTO 62% flop c-bet" },
  { id: "cbet_low", category: "Postflop", subcategory: "c-bet too low", description: "c-betting too rarely — missing value and fold equity", gtoBenchmark: "GTO 62% flop c-bet" },
  { id: "fold_vs_cbet", category: "Postflop", subcategory: "Fold vs c-bet", description: "Over-folding vs c-bets", gtoBenchmark: "GTO 45% fold vs c-bet" },
  { id: "check_raise_low", category: "Postflop", subcategory: "Check-raise too low", description: "Not check-raising enough — missing value and bluffs", gtoBenchmark: "GTO 12% check-raise flop" },
  { id: "turn_barrel_fold", category: "Turn", subcategory: "Fold vs turn barrel", description: "Over-folding vs turn barrels — MDF 60% vs 66% pot", gtoBenchmark: "GTO 38% fold vs turn barrel" },
  { id: "river_call_efficiency", category: "River", subcategory: "River call efficiency", description: "Bluff catching too little or too much", gtoBenchmark: "GTO 42% river call vs bet" },
  { id: "thin_value_missed", category: "River", subcategory: "Thin value missed", description: "Missing thin value bets on river", gtoBenchmark: "GTO 35% thin value bet" },
];

// Keep legacy defs for compat but map to new
export const LEGACY_LEAK_DEFS = LEAK_DEFS;

export interface DetectorHand {
  id: string;
  heroPosition: string;
  villainPosition?: string;
  street: string;
  board?: string;
  heroCards?: string;
  pot?: number;
  actions: Array<{ player: string; action: string; amount?: number }>;
  // Preflop flags
  isVPIP?: boolean;
  isPFR?: boolean;
  facedOpen?: boolean;
  faced3Bet?: boolean;
  foldedTo3Bet?: boolean;
  is3Bet?: boolean;
  openSizeBB?: number;
  // Postflop flags
  cBetOpportunity?: boolean;
  didCBet?: boolean;
  facedCBet?: boolean;
  foldedToCBet?: boolean;
  checkRaiseOpportunity?: boolean;
  didCheckRaise?: boolean;
  delayedCBetOpportunity?: boolean;
  didDelayedCBet?: boolean;
  turnProbeOpportunity?: boolean;
  didTurnProbe?: boolean;
  turnBarrelFaced?: boolean;
  foldedToTurnBarrel?: boolean;
  riverCallOpportunity?: boolean;
  didRiverCall?: boolean;
  riverValueOpportunity?: boolean;
  didThinValueBet?: boolean;
  resultBB?: number;
}

export interface LeakResult {
  leakId: string;
  category: LeakCategory;
  subcategory: string;
  description: string;
  severity: Severity;
  evLossBBper100: number;
  frequency: string;
  sampleSize: number;
  gtoBenchmark: string;
  userStat: string;
  affectedHands: string[];
  evLossPerHand?: number;
}

function severityFromEvLoss(ev: number): Severity {
  if (ev >= 3) return "high";
  if (ev >= 1.2) return "medium";
  return "low";
}

function makeResult(
  def: LeakDef,
  userStat: string,
  frequency: string,
  evLoss: number,
  sampleSize: number,
  affectedHands: string[]
): LeakResult {
  return {
    leakId: def.id,
    category: def.category,
    subcategory: def.subcategory,
    description: def.description,
    severity: severityFromEvLoss(evLoss),
    evLossBBper100: Math.round(evLoss * 10) / 10,
    frequency,
    sampleSize,
    gtoBenchmark: def.gtoBenchmark,
    userStat,
    affectedHands,
  };
}

// --- 12 Detectors ---

function detectVpipHigh(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[0];
  const preflopHands = hands.filter((h) => h.street === "preflop" || h.isVPIP !== undefined);
  const sample = preflopHands.length || hands.length;
  const vpipCount = hands.filter((h) => h.isVPIP).length;
  const vpip = sample ? (vpipCount / sample) * 100 : 0;
  if (vpip <= 26) return null; // GTO 22, leak if >26
  const evLoss = (vpip - 22) * 0.35; // ~0.35bb per % over
  return makeResult(def, `${vpip.toFixed(1)}% VPIP`, `${vpip.toFixed(1)}% (GTO 22%)`, evLoss, sample, hands.filter((h) => h.isVPIP).slice(0, 5).map((h) => h.id));
}

function detectVpipLow(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[1];
  const sample = hands.filter((h) => h.isVPIP !== undefined).length || hands.length;
  const vpipCount = hands.filter((h) => h.isVPIP).length;
  const vpip = sample ? (vpipCount / sample) * 100 : 0;
  if (vpip >= 18) return null;
  const evLoss = (18 - vpip) * 0.25;
  return makeResult(def, `${vpip.toFixed(1)}% VPIP`, `${vpip.toFixed(1)}% (GTO 22%)`, evLoss, sample, hands.filter((h) => !h.isVPIP).slice(0, 5).map((h) => h.id));
}

function detectPfrGap(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[2];
  const sample = hands.filter((h) => h.isVPIP !== undefined).length || hands.length;
  const vpip = sample ? (hands.filter((h) => h.isVPIP).length / sample) * 100 : 0;
  const pfr = sample ? (hands.filter((h) => h.isPFR).length / sample) * 100 : 0;
  const gap = vpip - pfr;
  if (gap <= 8) return null; // GTO gap 4, leak if >8
  const evLoss = (gap - 4) * 0.3;
  return makeResult(def, `${vpip.toFixed(0)}/${pfr.toFixed(0)} VPIP/PFR`, `${vpip.toFixed(0)}/${pfr.toFixed(0)} (GTO 22/18) gap ${gap.toFixed(0)}%`, evLoss, sample, hands.filter((h) => h.isVPIP && !h.isPFR).slice(0, 5).map((h) => h.id));
}

function detectFoldTo3Bet(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[3];
  const faced = hands.filter((h) => h.faced3Bet);
  if (faced.length < 5) return null;
  const folded = faced.filter((h) => h.foldedTo3Bet).length;
  const pct = (folded / faced.length) * 100;
  if (pct <= 62) return null; // GTO 55, leak if >62
  const evLoss = (pct - 55) * 0.12;
  return makeResult(def, `${pct.toFixed(0)}% fold vs 3-bet`, `${pct.toFixed(0)}% fold (GTO 55%)`, evLoss, faced.length, faced.filter((h) => h.foldedTo3Bet).map((h) => h.id).slice(0, 5));
}

function detect3BetLow(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[4];
  const opportunities = hands.filter((h) => h.facedOpen);
  if (opportunities.length < 8) return null;
  const threeBets = opportunities.filter((h) => h.is3Bet).length;
  const pct = (threeBets / opportunities.length) * 100;
  if (pct >= 5.5) return null; // GTO 8, leak if <5.5
  const evLoss = (8 - pct) * 0.4;
  return makeResult(def, `${pct.toFixed(1)}% 3-bet`, `${pct.toFixed(1)}% (GTO 8%)`, evLoss, opportunities.length, opportunities.filter((h) => !h.is3Bet).slice(0, 5).map((h) => h.id));
}

function detectCBetHigh(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[5];
  const opps = hands.filter((h) => h.cBetOpportunity);
  if (opps.length < 6) return null;
  const did = opps.filter((h) => h.didCBet).length;
  const pct = (did / opps.length) * 100;
  if (pct <= 72) return null; // GTO 62, leak if >72
  const evLoss = (pct - 62) * 0.08;
  return makeResult(def, `${pct.toFixed(0)}% c-bet`, `${pct.toFixed(0)}% (GTO 62%)`, evLoss, opps.length, opps.filter((h) => h.didCBet).map((h) => h.id).slice(0, 5));
}

function detectCBetLow(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[6];
  const opps = hands.filter((h) => h.cBetOpportunity);
  if (opps.length < 6) return null;
  const did = opps.filter((h) => h.didCBet).length;
  const pct = (did / opps.length) * 100;
  if (pct >= 48) return null; // leak if <48
  const evLoss = (62 - pct) * 0.09;
  return makeResult(def, `${pct.toFixed(0)}% c-bet`, `${pct.toFixed(0)}% (GTO 62%)`, evLoss, opps.length, opps.filter((h) => !h.didCBet).map((h) => h.id).slice(0, 5));
}

function detectFoldVsCBet(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[7];
  const faced = hands.filter((h) => h.facedCBet);
  if (faced.length < 6) return null;
  const folded = faced.filter((h) => h.foldedToCBet).length;
  const pct = (folded / faced.length) * 100;
  if (pct <= 52) return null; // GTO 45, leak if >52
  const evLoss = (pct - 45) * 0.11;
  return makeResult(def, `${pct.toFixed(0)}% fold vs c-bet`, `${pct.toFixed(0)}% (GTO 45%)`, evLoss, faced.length, faced.filter((h) => h.foldedToCBet).map((h) => h.id).slice(0, 5));
}

function detectCheckRaiseLow(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[8];
  const opps = hands.filter((h) => h.checkRaiseOpportunity);
  if (opps.length < 6) return null;
  const did = opps.filter((h) => h.didCheckRaise).length;
  const pct = (did / opps.length) * 100;
  if (pct >= 7) return null; // GTO 12, leak if <7
  const evLoss = (12 - pct) * 0.18;
  return makeResult(def, `${pct.toFixed(1)}% check-raise`, `${pct.toFixed(1)}% (GTO 12%)`, evLoss, opps.length, opps.filter((h) => !h.didCheckRaise).slice(0, 5).map((h) => h.id));
}

function detectTurnBarrelFold(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[9];
  const faced = hands.filter((h) => h.turnBarrelFaced);
  if (faced.length < 5) return null;
  const folded = faced.filter((h) => h.foldedToTurnBarrel).length;
  const pct = (folded / faced.length) * 100;
  if (pct <= 45) return null; // GTO 38, leak if >45
  const evLoss = (pct - 38) * 0.14;
  return makeResult(def, `${pct.toFixed(0)}% fold vs turn barrel`, `${pct.toFixed(0)}% (GTO 38%)`, evLoss, faced.length, faced.filter((h) => h.foldedToTurnBarrel).map((h) => h.id).slice(0, 5));
}

function detectRiverCallEfficiency(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[10];
  const opps = hands.filter((h) => h.riverCallOpportunity);
  if (opps.length < 5) return null;
  const called = opps.filter((h) => h.didRiverCall).length;
  const pct = (called / opps.length) * 100;
  // GTO 42% call, leak if <30 or >55
  if (pct >= 30 && pct <= 55) return null;
  const deviation = pct < 30 ? 30 - pct : pct - 42;
  const evLoss = deviation * 0.1;
  const label = pct < 30 ? `${pct.toFixed(0)}% river call (too low)` : `${pct.toFixed(0)}% river call (too high)`;
  return makeResult(def, label, `${pct.toFixed(0)}% (GTO 42%)`, evLoss, opps.length, opps.slice(0, 5).map((h) => h.id));
}

function detectThinValueMissed(hands: DetectorHand[]): LeakResult | null {
  const def = LEAK_DEFS[11];
  const opps = hands.filter((h) => h.riverValueOpportunity);
  if (opps.length < 5) return null;
  const did = opps.filter((h) => h.didThinValueBet).length;
  const pct = (did / opps.length) * 100;
  if (pct >= 24) return null; // GTO 35, leak if <24
  const evLoss = (35 - pct) * 0.12;
  return makeResult(def, `${pct.toFixed(0)}% thin value bet`, `${pct.toFixed(0)}% (GTO 35%)`, evLoss, opps.length, opps.filter((h) => !h.didThinValueBet).map((h) => h.id).slice(0, 5));
}

export const DETECTORS: Array<(hands: DetectorHand[]) => LeakResult | null> = [
  detectVpipHigh,
  detectVpipLow,
  detectPfrGap,
  detectFoldTo3Bet,
  detect3BetLow,
  detectCBetHigh,
  detectCBetLow,
  detectFoldVsCBet,
  detectCheckRaiseLow,
  detectTurnBarrelFold,
  detectRiverCallEfficiency,
  detectThinValueMissed,
];

export function runAllDetectors(hands: DetectorHand[]): LeakResult[] {
  const results: LeakResult[] = [];
  for (const fn of DETECTORS) {
    const r = fn(hands);
    if (r) results.push(r);
  }
  return results.sort((a, b) => b.evLossBBper100 - a.evLossBBper100);
}

// Legacy mock for backward compat
export function detectLeaksMock() {
  return LEAK_DEFS.slice(0, 4).map((d, i) => ({
    ...d,
    severity: (["high", "medium", "medium", "low"] as const)[i],
    evLossBBper100: [4.2, 2.1, 1.8, 0.9][i],
    sampleSize: [214, 98, 412, 76][i],
  }));
}
