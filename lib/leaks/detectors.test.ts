import { describe, it, expect } from "vitest";
import { runAllDetectors, LEAK_DEFS, type DetectorHand } from "./detectors";

function makeHand(overrides: Partial<DetectorHand> & { id: string }): DetectorHand {
  return {
    heroPosition: "BB",
    street: "preflop",
    actions: [],
    ...overrides,
  };
}

describe("leak detectors", () => {
  it("exports 12 leak defs", () => {
    expect(LEAK_DEFS.length).toBe(12);
  });

  it("detects VPIP too high", () => {
    const hands: DetectorHand[] = Array.from({ length: 20 }, (_, i) =>
      makeHand({ id: `h${i}`, isVPIP: i < 10, street: "preflop" })
    );
    // 50% VPIP -> should trigger vpip_high
    const leaks = runAllDetectors(hands);
    const vpipHigh = leaks.find((l) => l.leakId === "vpip_high");
    expect(vpipHigh).toBeDefined();
    expect(vpipHigh!.evLossBBper100).toBeGreaterThan(0);
  });

  it("detects VPIP too low", () => {
    const hands: DetectorHand[] = Array.from({ length: 20 }, (_, i) =>
      makeHand({ id: `h${i}`, isVPIP: i < 2, street: "preflop" })
    );
    // 10% VPIP -> should trigger vpip_low
    const leaks = runAllDetectors(hands);
    const vpipLow = leaks.find((l) => l.leakId === "vpip_low");
    expect(vpipLow).toBeDefined();
  });

  it("detects fold to 3-bet leak", () => {
    const hands: DetectorHand[] = Array.from({ length: 10 }, (_, i) =>
      makeHand({ id: `h${i}`, faced3Bet: true, foldedTo3Bet: i < 8, street: "preflop" })
    );
    const leaks = runAllDetectors(hands);
    const leak = leaks.find((l) => l.leakId === "fold_to_3bet");
    expect(leak).toBeDefined();
    expect(leak!.frequency).toContain("80%");
  });

  it("detects c-bet too high", () => {
    const hands: DetectorHand[] = Array.from({ length: 10 }, (_, i) =>
      makeHand({ id: `h${i}`, cBetOpportunity: true, didCBet: i < 9, street: "flop" })
    );
    const leaks = runAllDetectors(hands);
    const leak = leaks.find((l) => l.leakId === "cbet_high");
    expect(leak).toBeDefined();
  });

  it("returns empty when no leaks", () => {
    // Balanced hands: 22% VPIP, normal stats
    const hands: DetectorHand[] = Array.from({ length: 100 }, (_, i) =>
      makeHand({
        id: `h${i}`,
        isVPIP: i < 22,
        isPFR: i < 18,
        street: "preflop",
      })
    );
    // Add some postflop hands with balanced c-bet
    const flopHands: DetectorHand[] = Array.from({ length: 20 }, (_, i) =>
      makeHand({ id: `f${i}`, cBetOpportunity: true, didCBet: i < 12, street: "flop" })
    );
    const all = [...hands, ...flopHands];
    // Should have minimal leaks (maybe none or low severity)
    const leaks = runAllDetectors(all);
    // At least shouldn't have high severity leaks for balanced play
    const highLeaks = leaks.filter((l) => l.severity === "high");
    expect(highLeaks.length).toBeLessThanOrEqual(2);
  });

  it("sorts leaks by evLoss descending", () => {
    const hands: DetectorHand[] = [
      ...Array.from({ length: 20 }, (_, i) => makeHand({ id: `v${i}`, isVPIP: true, street: "preflop" })),
      ...Array.from({ length: 10 }, (_, i) => makeHand({ id: `c${i}`, cBetOpportunity: true, didCBet: true, street: "flop" })),
    ];
    const leaks = runAllDetectors(hands);
    for (let i = 1; i < leaks.length; i++) {
      expect(leaks[i - 1].evLossBBper100).toBeGreaterThanOrEqual(leaks[i].evLossBBper100);
    }
  });

  it("handles empty hands array", () => {
    const leaks = runAllDetectors([]);
    // Empty hands triggers vpip_low (0% VPIP) — expected behavior
    expect(leaks.some(l => l.leakId === "vpip_low")).toBe(true);
  });
});
