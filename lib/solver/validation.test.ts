import { describe, it, expect } from "vitest";
import {
  VALIDATION_BENCHMARKS,
  validateSolverResult,
  runValidationSuite,
  findBenchmarkForSpot,
} from "./validation";
import { generateSpotHash } from "./solverService";
import type { SolverResult } from "./solverService";
import type { ValidationBenchmark } from "./validation";

function makeResult(freq: { raise: number; call: number; fold: number; bet?: number; check?: number }): SolverResult {
  return {
    spotHash: "testhash12345678",
    gtoFreq: freq,
    ev: 0.5,
    exploitability: 0.005,
    source: "solver",
    solveTimeMs: 10,
    board: "Ah 7d 2c",
    street: "flop",
  };
}

describe("validation framework", () => {
  it("VALIDATION_BENCHMARKS has 15-20 entries", () => {
    expect(VALIDATION_BENCHMARKS.length).toBeGreaterThanOrEqual(15);
    expect(VALIDATION_BENCHMARKS.length).toBeLessThanOrEqual(20);
  });

  it("all benchmarks have required fields", () => {
    for (const b of VALIDATION_BENCHMARKS) {
      expect(b.id).toBeTruthy();
      expect(b.spot).toBeDefined();
      expect(b.expectedFreq).toBeDefined();
      expect(b.tolerance).toBeGreaterThan(0);
      expect(b.description).toBeTruthy();
      expect(b.category).toMatch(/preflop|flop|turn|river/);
      // Frequencies should sum to ~100
      const sum = b.expectedFreq.raise + b.expectedFreq.call + b.expectedFreq.fold;
      expect(sum).toBe(100);
    }
  });

  it("validateSolverResult passes when within tolerance", () => {
    const benchmark: ValidationBenchmark = {
      id: "test-pass",
      spot: { board: "", heroRange: "BTN", villainRange: "random", pot: 1.5, stacks: 100, betSizings: [2.5], rake: 0.05, street: "preflop", position: "BTN" },
      expectedFreq: { raise: 45, call: 2, fold: 53 },
      tolerance: 5,
      description: "test",
      category: "preflop",
      source: "test",
    };
    const result = makeResult({ raise: 46, call: 1, fold: 53 });
    const v = validateSolverResult(result, benchmark);
    expect(v.passed).toBe(true);
    expect(v.maxDelta).toBeLessThanOrEqual(5);
    expect(v.details).toContain("PASS");
  });

  it("validateSolverResult fails when outside tolerance", () => {
    const benchmark: ValidationBenchmark = {
      id: "test-fail",
      spot: { board: "", heroRange: "BTN", villainRange: "random", pot: 1.5, stacks: 100, betSizings: [2.5], rake: 0.05, street: "preflop", position: "BTN" },
      expectedFreq: { raise: 45, call: 2, fold: 53 },
      tolerance: 5,
      description: "test fail",
      category: "preflop",
      source: "test",
    };
    const result = makeResult({ raise: 60, call: 10, fold: 30 });
    const v = validateSolverResult(result, benchmark);
    expect(v.passed).toBe(false);
    expect(v.maxDelta).toBeGreaterThan(5);
    expect(v.details).toContain("FAIL");
  });

  it("validateSolverResult handles bet/check deltas", () => {
    const benchmark: ValidationBenchmark = {
      id: "test-bet",
      spot: { board: "Ah 7d 2c", heroRange: "BTN", villainRange: "BB", pot: 7.5, stacks: 100, betSizings: [0.33], rake: 0.05, street: "flop", position: "BTN" },
      expectedFreq: { raise: 8, call: 48, fold: 44, bet: 65, check: 35 },
      tolerance: 10,
      description: "test bet",
      category: "flop",
      source: "test",
    };
    // Within tolerance
    const passResult = makeResult({ raise: 9, call: 48, fold: 43, bet: 64, check: 36 });
    expect(validateSolverResult(passResult, benchmark).passed).toBe(true);

    // Bet delta exceeds tolerance
    const failResult = makeResult({ raise: 8, call: 48, fold: 44, bet: 80, check: 20 });
    const v = validateSolverResult(failResult, benchmark);
    expect(v.passed).toBe(false);
    expect(v.delta.bet).toBe(15);
  });

  it("validateSolverResult reports correct delta values", () => {
    const benchmark: ValidationBenchmark = {
      id: "test-delta",
      spot: { board: "", heroRange: "BTN", villainRange: "random", pot: 1.5, stacks: 100, betSizings: [2.5], rake: 0.05, street: "preflop", position: "BTN" },
      expectedFreq: { raise: 45, call: 2, fold: 53 },
      tolerance: 5,
      description: "delta test",
      category: "preflop",
      source: "test",
    };
    const result = makeResult({ raise: 47, call: 5, fold: 48 });
    const v = validateSolverResult(result, benchmark);
    expect(v.delta.raise).toBe(2);
    expect(v.delta.call).toBe(3);
    expect(v.delta.fold).toBe(5);
    expect(v.maxDelta).toBe(5);
    expect(v.passed).toBe(true); // exactly at tolerance
  });

  it("findBenchmarkForSpot finds correct benchmark by hash", () => {
    const first = VALIDATION_BENCHMARKS[0];
    const hash = generateSpotHash(first.spot);
    const found = findBenchmarkForSpot(hash);
    expect(found).not.toBeNull();
    expect(found!.id).toBe(first.id);
  });

  it("findBenchmarkForSpot returns null for unknown hash", () => {
    expect(findBenchmarkForSpot("nonexistenthash")).toBeNull();
  });

  it("runValidationSuite runs all benchmarks and returns summary", async () => {
    // Mock solver that returns expected frequencies (should pass all)
    const mockSolver = {
      async solve(spot: import("./solverService").SpotInput): Promise<SolverResult> {
        const hash = generateSpotHash(spot);
        const bench = VALIDATION_BENCHMARKS.find((b) => generateSpotHash(b.spot) === hash);
        if (bench) {
          return {
            spotHash: hash,
            gtoFreq: { ...bench.expectedFreq },
            ev: 0.5,
            exploitability: 0.005,
            source: "solver" as const,
            solveTimeMs: 5,
            board: spot.board,
            street: spot.street,
          };
        }
        return makeResult({ raise: 10, call: 50, fold: 40 });
      },
    };

    const suite = await runValidationSuite(mockSolver);
    expect(suite.total).toBe(VALIDATION_BENCHMARKS.length);
    expect(suite.passed).toBe(VALIDATION_BENCHMARKS.length);
    expect(suite.failed).toBe(0);
    expect(suite.accuracy).toBe(1);
    expect(suite.failures).toHaveLength(0);
    expect(suite.results).toHaveLength(VALIDATION_BENCHMARKS.length);
    expect(suite.timestamp).toBeTruthy();
  });

  it("runValidationSuite detects failures", async () => {
    const badSolver = {
      async solve(): Promise<SolverResult> {
        return makeResult({ raise: 90, call: 5, fold: 5 });
      },
    };
    const suite = await runValidationSuite(badSolver);
    expect(suite.failed).toBeGreaterThan(0);
    expect(suite.accuracy).toBeLessThan(1);
    expect(suite.failures.length).toBe(suite.failed);
  });
});
