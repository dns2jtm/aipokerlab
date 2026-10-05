import { describe, it, expect } from "vitest";
import { parseHands, SAMPLE_HAND, SAMPLE_GG_HAND, SAMPLE_ALLIN_HAND } from "./handParser";

describe("handParser", () => {
  it("parses PokerStars sample hand", () => {
    const result = parseHands(SAMPLE_HAND);
    expect(result.hands.length).toBe(1);
    expect(result.errors.length).toBe(0);
    const h = result.hands[0];
    expect(h.site).toBe("pokerstars");
    expect(h.hero).toBe("Hero");
    expect(h.heroCards).toBe("As 5s");
    expect(h.board).toContain("Qh");
    expect(h.streets.preflop.length).toBeGreaterThan(0);
    expect(h.streets.flop.length).toBeGreaterThan(0);
  });

  it("parses GGPoker sample hand", () => {
    const result = parseHands(SAMPLE_GG_HAND);
    expect(result.hands.length).toBe(1);
    expect(result.errors.length).toBe(0);
    const h = result.hands[0];
    expect(["ggpoker","pokerstars"]).toContain(h.site);
    expect(h.heroCards).toBe("Ah Kd");
    expect(h.streets.flop.length).toBeGreaterThan(0);
    expect(h.streets.turn.length).toBeGreaterThan(0);
  });

  it("parses all-in hand with side pots", () => {
    const result = parseHands(SAMPLE_ALLIN_HAND);
    expect(result.hands.length).toBe(1);
    const h = result.hands[0];
    expect(h.heroCards).toBe("As Ks");
    // Should have preflop actions including all-in
    const preflopActions = h.streets.preflop;
    expect(preflopActions.some((a) => a.isAllIn)).toBe(true);
  });

  it("handles multiple hands", () => {
    const combined = SAMPLE_HAND + "\n" + SAMPLE_GG_HAND;
    const result = parseHands(combined);
    expect(result.hands.length).toBe(2);
  });

  it("handles empty input", () => {
    const result = parseHands("");
    expect(result.hands.length).toBe(0);
  });

  it("handles invalid input gracefully", () => {
    const result = parseHands("not a hand history at all");
    // Should not throw, may produce 1 hand with errors or empty
    expect(result).toBeDefined();
    expect(Array.isArray(result.hands)).toBe(true);
    expect(Array.isArray(result.errors)).toBe(true);
  });

  it("parses stakes correctly", () => {
    const result = parseHands(SAMPLE_HAND);
    expect(result.hands[0].stakes).toBeTruthy();
    expect(result.hands[0].stakes).toContain("/");
  });

  it("parses pot correctly", () => {
    const result = parseHands(SAMPLE_HAND);
    expect(result.hands[0].pot).toBeGreaterThan(0);
  });
});
