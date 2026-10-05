import { runAllDetectors, type DetectorHand, type LeakResult } from "./detectors";

export interface AnalyzerInput {
  hands: DetectorHand[];
  userId?: string;
}

export interface AnalyzerOutput {
  leaks: LeakResult[];
  totalEvLossBBper100: number;
  handCount: number;
  worstLeak: LeakResult | null;
  generatedAt: string;
}

export function analyzeLeaks(input: AnalyzerInput): AnalyzerOutput {
  const leaks = runAllDetectors(input.hands);
  const total = leaks.reduce((acc, l) => acc + l.evLossBBper100, 0);
  return {
    leaks,
    totalEvLossBBper100: Math.round(total * 10) / 10,
    handCount: input.hands.length,
    worstLeak: leaks[0] || null,
    generatedAt: new Date().toISOString(),
  };
}

// Mock hand generator — 20-30 hands with realistic leak patterns
export function generateMockHands(count = 26): DetectorHand[] {
  const positions = ["BTN", "CO", "UTG", "BB", "SB", "HJ"];
  const boards = ["Qh 7d 2c", "Ah Kd 4s", "9s 8s 3c", "Kc Qd Jc", "7h 6h 2d", "As Ks Qs", "Th 9h 2c", "Jd Td 4h"];
  const heroCardsList = ["As 5s", "Kh 9h", "Qd Jd", "Ad 4s", "9c 2d", "Ah Kd", "7s 6s", "Kc Qc", "Jh Th", "Ac Kc", "8d 7d", "Qh Qd", "As Ks", "Td 9d", "6h 5h", "Kj", "A2o", "J4o", "92o", "73o", "K8s", "Q9s", "JTs", "22", "A5s", "K9s"];

  // Seeded deterministic
  let seed = 42;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return (seed % 1000) / 1000;
  };

  const hands: DetectorHand[] = [];
  for (let i = 0; i < count; i++) {
    const r = rnd();
    const r2 = rnd();
    const r3 = rnd();
    const heroPos = positions[Math.floor(rnd() * positions.length)];
    const villainPos = positions[Math.floor(rnd() * positions.length)];
    const board = boards[Math.floor(rnd() * boards.length)];
    const heroCards = heroCardsList[Math.floor(rnd() * heroCardsList.length)];
    const streetRoll = rnd();
    let street: string = "preflop";
    if (streetRoll > 0.7) street = "river";
    else if (streetRoll > 0.5) street = "turn";
    else if (streetRoll > 0.3) street = "flop";

    // Bias to create leaks: over-fold BB vs BTN, under 3-bet, over-fold vs c-bet, etc.
    const isBBvsBTN = heroPos === "BB" && villainPos === "BTN";
    const facedOpen = r < 0.55;
    const isVPIP = facedOpen ? r2 < 0.32 : r2 < 0.18; // low VPIP to trigger vpip_low or high depending
    // Make VPIP high for some, low for others — we want pfr_gap leak
    const isPFR = isVPIP ? r3 < 0.45 : false; // gap
    const faced3Bet = isPFR ? rnd() < 0.35 : false;
    const foldedTo3Bet = faced3Bet ? rnd() < 0.72 : false; // over-fold
    const is3Bet = facedOpen ? rnd() < 0.04 : false; // too low (GTO 8%)

    const cBetOpportunity = street === "flop" && rnd() < 0.5;
    const didCBet = cBetOpportunity ? rnd() < 0.38 : false; // too low (GTO 62)
    const facedCBet = !cBetOpportunity && street === "flop" && rnd() < 0.45;
    const foldedToCBet = facedCBet ? rnd() < 0.62 : false; // over-fold

    const checkRaiseOpportunity = street === "flop" && rnd() < 0.4;
    const didCheckRaise = checkRaiseOpportunity ? rnd() < 0.03 : false; // too low

    const turnBarrelFaced = street === "turn" && rnd() < 0.4;
    const foldedToTurnBarrel = turnBarrelFaced ? rnd() < 0.58 : false;

    const riverCallOpportunity = street === "river" && rnd() < 0.5;
    const didRiverCall = riverCallOpportunity ? rnd() < 0.28 : false; // too low

    const riverValueOpportunity = street === "river" && rnd() < 0.4;
    const didThinValueBet = riverValueOpportunity ? rnd() < 0.18 : false; // too low

    // Force some BB vs BTN over-folds
    const forcedFoldBB = isBBvsBTN && facedOpen && rnd() < 0.68;

    hands.push({
      id: `hand-${i + 1}`,
      heroPosition: heroPos,
      villainPosition: villainPos,
      street,
      board: street === "preflop" ? "" : board,
      heroCards,
      pot: 5 + rnd() * 20,
      actions: [{ player: "Hero", action: isVPIP ? (isPFR ? "raises" : "calls") : "folds" }],
      isVPIP: forcedFoldBB ? false : isVPIP,
      isPFR: forcedFoldBB ? false : isPFR,
      facedOpen,
      faced3Bet,
      foldedTo3Bet,
      is3Bet,
      cBetOpportunity,
      didCBet,
      facedCBet,
      foldedToCBet,
      checkRaiseOpportunity,
      didCheckRaise,
      turnBarrelFaced,
      foldedToTurnBarrel,
      riverCallOpportunity,
      didRiverCall,
      riverValueOpportunity,
      didThinValueBet,
      resultBB: (rnd() - 0.5) * 10,
    });
  }
  return hands;
}

export function getMockAnalyzerOutput(): AnalyzerOutput {
  const hands = generateMockHands(26);
  return analyzeLeaks({ hands });
}
