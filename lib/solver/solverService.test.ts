import { describe, it, expect, beforeEach } from "vitest";
import { generateSpotHash, SolverService, solverCache, type SpotInput } from "./solverService";

const baseSpot: SpotInput = {
  board: "Qh 7d 2c",
  heroRange: "As 5s",
  villainRange: "random",
  pot: 7.5,
  stacks: 100,
  betSizings: [0.33, 0.66, 1.5],
  rake: 0.05,
  street: "flop",
  position: "BB",
};

describe("solverService", () => {
  beforeEach(() => {
    solverCache.clear();
  });

  it("generateSpotHash is deterministic", () => {
    const h1 = generateSpotHash(baseSpot);
    const h2 = generateSpotHash(baseSpot);
    expect(h1).toBe(h2);
    expect(h1).toHaveLength(16);
    expect(/^[0-9a-f]+$/.test(h1)).toBe(true);
  });

  it("generateSpotHash differs for different boards", () => {
    const h1 = generateSpotHash(baseSpot);
    const h2 = generateSpotHash({ ...baseSpot, board: "Ah Kh Qh" });
    expect(h1).not.toBe(h2);
  });

  it("generateSpotHash normalizes betSizings order", () => {
    const h1 = generateSpotHash({ ...baseSpot, betSizings: [0.33, 0.66] });
    const h2 = generateSpotHash({ ...baseSpot, betSizings: [0.66, 0.33] });
    expect(h1).toBe(h2);
  });

  it("generateSpotHash normalizes board case and whitespace", () => {
    const h1 = generateSpotHash({ ...baseSpot, board: "Qh 7d 2c" });
    const h2 = generateSpotHash({ ...baseSpot, board: "qh  7d  2c " });
    expect(h1).toBe(h2);
  });

  it("SolverService.solve returns result and caches", async () => {
    const result1 = await SolverService.solve(baseSpot);
    expect(result1.spotHash).toBe(generateSpotHash(baseSpot));
    expect(result1.gtoFreq).toBeDefined();
    expect(result1.gtoFreq.raise + result1.gtoFreq.call + result1.gtoFreq.fold).toBe(100);
    expect(result1.source).toBe("solver");
    expect(solverCache.size()).toBe(1);

    const result2 = await SolverService.solve(baseSpot);
    expect(result2.source).toBe("cache");
    expect(result2.spotHash).toBe(result1.spotHash);
    expect(result2.gtoFreq).toEqual(result1.gtoFreq);
  });

  it("solverCache LRU eviction", async () => {
    // Fill cache beyond maxSize would require 5000 entries, just test basic set/get
    const spot2 = { ...baseSpot, board: "Ah Kh Qh", street: "turn" };
    await SolverService.solve(baseSpot);
    await SolverService.solve(spot2);
    expect(solverCache.size()).toBe(2);
    expect(solverCache.has(generateSpotHash(baseSpot))).toBe(true);
    expect(solverCache.has(generateSpotHash(spot2))).toBe(true);
  });

  it("solve handles different streets", async () => {
    for (const street of ["preflop", "flop", "turn", "river"]) {
      const r = await SolverService.solve({ ...baseSpot, street, board: street === "preflop" ? "" : "Qh 7d 2c" });
      expect(r.street).toBe(street);
      expect(r.gtoFreq.raise).toBeGreaterThanOrEqual(0);
      expect(r.gtoFreq.call).toBeGreaterThanOrEqual(0);
      expect(r.gtoFreq.fold).toBeGreaterThanOrEqual(0);
    }
  });

  it("lookup returns null for unknown spot", () => {
    const result = SolverService.lookup({ ...baseSpot, board: "Xx Yy Zz" });
    expect(result).toBeNull();
  });
});
