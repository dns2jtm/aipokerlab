import { describe, it, expect } from "vitest";
import {
  buildSolverContext,
  buildLeakSummary,
  buildHandContext,
  buildContext,
  composePrompt,
  PROMPT_VERSION,
  FEW_SHOT_EXAMPLES,
} from "./promptComposer";

describe("promptComposer", () => {
  it("buildSolverContext formats solver data", () => {
    const ctx = buildSolverContext({
      spotHash: "abc123",
      board: "Qh 7d 2c",
      heroCards: "As 5s",
      heroPosition: "BB",
      villainPosition: "BTN",
      pot: 7.5,
      gtoFreq: { raise: 12, call: 58, fold: 30 },
      evLoss: -0.8,
      source: "cache",
    });
    expect(ctx).toContain("abc123");
    expect(ctx).toContain("Qh 7d 2c");
    expect(ctx).toContain("raise 12%");
    expect(ctx).toContain("call 58%");
  });

  it("buildSolverContext handles missing data", () => {
    const ctx = buildSolverContext({ spotHash: "" } as unknown as Parameters<typeof buildSolverContext>[0]);
    expect(ctx).toContain("No solver data");
  });

  it("buildLeakSummary formats leaks", () => {
    const summary = buildLeakSummary([
      { category: "Preflop", subcategory: "VPIP too high", severity: "high", evLossBBper100: 4.2, frequency: "30% (GTO 22%)" },
    ]);
    expect(summary).toContain("VPIP too high");
    expect(summary).toContain("4.2");
  });

  it("buildLeakSummary handles empty", () => {
    expect(buildLeakSummary([])).toContain("No leak history");
  });

  it("buildHandContext formats hand", () => {
    const ctx = buildHandContext({
      id: "h1",
      heroCards: "As 5s",
      board: "Qh 7d 2c",
      street: "flop",
      heroPosition: "BB",
      villainPosition: "BTN",
      actions: [{ player: "Hero", action: "checks" }],
    });
    expect(ctx).toContain("As 5s");
    expect(ctx).toContain("Qh 7d 2c");
    expect(ctx).toContain("BB vs BTN");
  });

  it("buildContext produces full prompt", () => {
    const built = buildContext({
      hand: { id: "h1", heroCards: "As 5s", board: "Qh 7d 2c", street: "flop", heroPosition: "BB", villainPosition: "BTN", actions: [] },
      solverResult: { spotHash: "hash123", board: "Qh 7d 2c", heroCards: "As 5s", pot: 7.5, gtoFreq: { raise: 12, call: 58, fold: 30 }, evLoss: -0.8 },
      leakHistory: [],
      userTone: "concise",
    });
    expect(built.fullPrompt).toContain("hash123");
    expect(built.fullPrompt).toContain("As 5s");
    expect(built.metadata.spotHash).toBe("hash123");
    expect(built.metadata.promptVersion).toBe(PROMPT_VERSION);
    expect(built.metadata.hasSolverData).toBe(true);
  });

  it("composePrompt includes few-shot examples", () => {
    const prompt = composePrompt("solver ctx", "leak summary", "hand ctx");
    expect(prompt).toContain("Example 1");
    expect(prompt).toContain("MDF");
    expect(prompt).toContain(PROMPT_VERSION);
  });

  it("FEW_SHOT_EXAMPLES has 3 examples", () => {
    expect(FEW_SHOT_EXAMPLES.length).toBe(3);
    for (const ex of FEW_SHOT_EXAMPLES) {
      expect(ex.expectedCard.verdict).toMatch(/good|mistake|big_mistake/);
      expect(ex.expectedCard.rule).toBeTruthy();
      expect(ex.expectedCard.drill).toBeTruthy();
    }
  });
});
