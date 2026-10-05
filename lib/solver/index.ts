export * from "./mockPreflop";
export { SolverService, solverCache, generateSpotHash, inflightSolves } from "./solverService";
export type { SpotInput, SolverResult, GtoFreq as SolverGtoFreq } from "./solverService";
export { precomputedDB, InMemoryPrecomputedDB, ensurePrecomputedDBLoaded } from "./precomputedDB";
export type { PrecomputedDB } from "./precomputedDB";
export { accuracyTracker, getAccuracyStats } from "./accuracy";
export type { AccuracyStats, SolveLogEntry, SolveSource } from "./accuracy";
export {
  VALIDATION_BENCHMARKS,
  validateSolverResult,
  runValidationSuite,
  findBenchmarkForSpot,
} from "./validation";
export type { ValidationBenchmark, ValidationResult, ValidationSuiteResult } from "./validation";

// Legacy SpotInput/Solution kept for backwards compat — new code should use solverService.ts
export interface SpotInputLegacy {
  board: string;
  heroRange: string;
  villainRange: string;
  pot: number;
  stacks: number;
  betSizings: number[];
  rake: number;
  street: string;
}

export interface Solution {
  spotHash: string;
  evMap: Record<string, number>;
  strategyMap: Record<string, { raise: number; call: number; fold: number }>;
  nashDistance: number;
  solveTimeMs: number;
  source: "cache" | "solver";
}

export function spotHash(input: SpotInputLegacy): string {
  const s = `${input.board}|${input.heroRange}|${input.villainRange}|${input.pot}|${input.stacks}|${input.betSizings.join(",")}|${input.rake}|${input.street}`;
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h.toString(16).padStart(8, "0");
}

export const SolverServiceLegacy = {
  async solve(spot: SpotInputLegacy): Promise<Solution> {
    return {
      spotHash: spotHash(spot),
      evMap: { As5s: 0.42 },
      strategyMap: { As5s: { raise: 12, call: 58, fold: 30 } },
      nashDistance: 0.005,
      solveTimeMs: 12,
      source: "cache",
    };
  },
};
