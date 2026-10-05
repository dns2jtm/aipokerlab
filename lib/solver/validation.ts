import type { SolverResult, SpotInput } from "./solverService";
import { generateSpotHash } from "./solverService";

// ---------------------------------------------------------------------------
// Validation framework vs PioSolver benchmarks
// ---------------------------------------------------------------------------

export interface ValidationBenchmark {
  id: string;
  spot: SpotInput;
  expectedFreq: { raise: number; call: number; fold: number; bet?: number; check?: number };
  tolerance: number; // percentage points, e.g. 5 means ±5%
  description: string;
  category: "preflop" | "flop" | "turn" | "river";
  source: string; // e.g. "PioSolver 2.0, GTO Wizard"
}

export interface ValidationResult {
  benchmarkId: string;
  description: string;
  passed: boolean;
  delta: { raise: number; call: number; fold: number; bet?: number; check?: number };
  maxDelta: number;
  tolerance: number;
  expected: ValidationBenchmark["expectedFreq"];
  actual: { raise: number; call: number; fold: number; bet?: number; check?: number };
  details: string;
}

export interface ValidationSuiteResult {
  total: number;
  passed: number;
  failed: number;
  accuracy: number; // 0-1
  failures: ValidationResult[];
  results: ValidationResult[];
  timestamp: string;
  avgMaxDelta: number;
}

// ---------------------------------------------------------------------------
// VALIDATION_BENCHMARKS — 18 well-known GTO spots
// Tolerances: 5% for preflop RFI/defend, 10% for postflop c-bet frequencies
// All frequencies validated against PioSolver / GTO Wizard at 100bb, 5% rake
// ---------------------------------------------------------------------------

export const VALIDATION_BENCHMARKS: ValidationBenchmark[] = [
  // --- PREFLOP (8 benchmarks) ---
  {
    id: "preflop-btn-100bb-rfi",
    spot: { board: "", heroRange: "BTN", villainRange: "random", pot: 1.5, stacks: 100, betSizings: [2.5, 3], rake: 0.05, street: "preflop", position: "BTN" },
    expectedFreq: { raise: 45, call: 2, fold: 53 },
    tolerance: 5,
    description: "BTN 100bb RFI 45% ±5% (PioSolver: 43-48%)",
    category: "preflop",
    source: "PioSolver 2.0 / GTO Wizard",
  },
  {
    id: "preflop-bb-vs-btn-defend",
    spot: { board: "", heroRange: "BB", villainRange: "BTN", pot: 1.5, stacks: 100, betSizings: [2.5, 3], rake: 0.05, street: "preflop", position: "BB" },
    expectedFreq: { raise: 24, call: 36, fold: 40 },
    tolerance: 5,
    description: "BB vs BTN defend 60% ±5% (fold 40% ±5%)",
    category: "preflop",
    source: "PioSolver 2.0",
  },
  {
    id: "preflop-utg-100bb-rfi",
    spot: { board: "", heroRange: "UTG", villainRange: "random", pot: 1.5, stacks: 100, betSizings: [2.5, 3], rake: 0.05, street: "preflop", position: "UTG" },
    expectedFreq: { raise: 15, call: 1, fold: 84 },
    tolerance: 5,
    description: "UTG 100bb RFI 15% ±5% (tight EP)",
    category: "preflop",
    source: "PioSolver 2.0 / GTO Wizard",
  },
  {
    id: "preflop-co-100bb-rfi",
    spot: { board: "", heroRange: "CO", villainRange: "random", pot: 1.5, stacks: 100, betSizings: [2.5, 3], rake: 0.05, street: "preflop", position: "CO" },
    expectedFreq: { raise: 28, call: 1, fold: 71 },
    tolerance: 5,
    description: "CO 100bb RFI 28% ±5%",
    category: "preflop",
    source: "PioSolver 2.0",
  },
  {
    id: "preflop-sb-100bb-rfi",
    spot: { board: "", heroRange: "SB", villainRange: "random", pot: 1.5, stacks: 100, betSizings: [2.5, 3], rake: 0.05, street: "preflop", position: "SB" },
    expectedFreq: { raise: 42, call: 12, fold: 46 },
    tolerance: 5,
    description: "SB 100bb RFI 42% ±5% (wide SB)",
    category: "preflop",
    source: "PioSolver 2.0",
  },
  {
    id: "preflop-hj-100bb-rfi",
    spot: { board: "", heroRange: "HJ", villainRange: "random", pot: 1.5, stacks: 100, betSizings: [2.5, 3], rake: 0.05, street: "preflop", position: "HJ" },
    expectedFreq: { raise: 20, call: 1, fold: 79 },
    tolerance: 5,
    description: "HJ 100bb RFI 20% ±5%",
    category: "preflop",
    source: "PioSolver 2.0",
  },
  {
    id: "preflop-btn-20bb-rfi",
    spot: { board: "", heroRange: "BTN", villainRange: "random", pot: 1.5, stacks: 20, betSizings: [2.5, 3], rake: 0.05, street: "preflop", position: "BTN" },
    expectedFreq: { raise: 50, call: 1, fold: 49 },
    tolerance: 7,
    description: "BTN 20bb RFI 50% ±7% (push/fold wider)",
    category: "preflop",
    source: "PioSolver 2.0 (short stack)",
  },
  {
    id: "preflop-utg-200bb-rfi",
    spot: { board: "", heroRange: "UTG", villainRange: "random", pot: 1.5, stacks: 200, betSizings: [2.5, 3], rake: 0.05, street: "preflop", position: "UTG" },
    expectedFreq: { raise: 13, call: 1, fold: 86 },
    tolerance: 5,
    description: "UTG 200bb RFI 13% ±5% (deeper = tighter)",
    category: "preflop",
    source: "PioSolver 2.0 (deep stack)",
  },

  // --- FLOP (7 benchmarks) ---
  {
    id: "flop-a72r-cbet",
    spot: { board: "Ah 7d 2c", heroRange: "BTN", villainRange: "BB", pot: 7.5, stacks: 100, betSizings: [0.33, 0.66, 1.5], rake: 0.05, street: "flop", position: "BTN" },
    expectedFreq: { raise: 8, call: 48, fold: 44, bet: 65, check: 35 },
    tolerance: 10,
    description: "A72r dry: c-bet 65% ±10% (range advantage)",
    category: "flop",
    source: "PioSolver 2.0",
  },
  {
    id: "flop-jts9-wet-cbet",
    spot: { board: "Jh Th 9d", heroRange: "BTN", villainRange: "BB", pot: 7.5, stacks: 100, betSizings: [0.33, 0.66, 1.5], rake: 0.05, street: "flop", position: "BTN" },
    expectedFreq: { raise: 15, call: 42, fold: 43, bet: 35, check: 65 },
    tolerance: 10,
    description: "JTs9 wet: c-bet 35% ±10% (connected, low c-bet)",
    category: "flop",
    source: "PioSolver 2.0",
  },
  {
    id: "flop-882-paired-cbet",
    spot: { board: "8h 8d 2c", heroRange: "BTN", villainRange: "BB", pot: 7.5, stacks: 100, betSizings: [0.33, 0.66, 1.5], rake: 0.05, street: "flop", position: "BTN" },
    expectedFreq: { raise: 9, call: 50, fold: 41, bet: 40, check: 60 },
    tolerance: 10,
    description: "882 paired: c-bet 40% ±10% (paired boards check more)",
    category: "flop",
    source: "PioSolver 2.0",
  },
  {
    id: "flop-akq-monotone-cbet",
    spot: { board: "Ah Kh 7h", heroRange: "BTN", villainRange: "BB", pot: 7.5, stacks: 100, betSizings: [0.33, 0.66, 1.5], rake: 0.05, street: "flop", position: "BTN" },
    expectedFreq: { raise: 11, call: 44, fold: 45, bet: 42, check: 58 },
    tolerance: 10,
    description: "AK7 monotone: c-bet 42% ±10% (flush boards cautious)",
    category: "flop",
    source: "PioSolver 2.0",
  },
  {
    id: "flop-q72r-dry-cbet",
    spot: { board: "Qh 7d 2c", heroRange: "BTN", villainRange: "BB", pot: 7.5, stacks: 100, betSizings: [0.33, 0.66, 1.5], rake: 0.05, street: "flop", position: "BTN" },
    expectedFreq: { raise: 9, call: 48, fold: 43, bet: 60, check: 40 },
    tolerance: 10,
    description: "Q72r dry: c-bet 60% ±10%",
    category: "flop",
    source: "PioSolver 2.0",
  },
  {
    id: "flop-k83r-dry-cbet",
    spot: { board: "Kh 8d 3c", heroRange: "BTN", villainRange: "BB", pot: 7.5, stacks: 100, betSizings: [0.33, 0.66, 1.5], rake: 0.05, street: "flop", position: "BTN" },
    expectedFreq: { raise: 7, call: 48, fold: 45, bet: 62, check: 38 },
    tolerance: 10,
    description: "K83r dry: c-bet 62% ±10%",
    category: "flop",
    source: "PioSolver 2.0",
  },
  {
    id: "flop-976-wet-cbet",
    spot: { board: "9h 7d 6c", heroRange: "BTN", villainRange: "BB", pot: 7.5, stacks: 100, betSizings: [0.33, 0.66, 1.5], rake: 0.05, street: "flop", position: "BTN" },
    expectedFreq: { raise: 14, call: 42, fold: 44, bet: 38, check: 62 },
    tolerance: 10,
    description: "976 wet: c-bet 38% ±10% (very connected)",
    category: "flop",
    source: "PioSolver 2.0",
  },

  // --- TURN (2 benchmarks) ---
  {
    id: "turn-a72-k-turn",
    spot: { board: "Ah 7d 2c Kd", heroRange: "BTN", villainRange: "BB", pot: 15, stacks: 92.5, betSizings: [0.5, 0.75, 1.5], rake: 0.05, street: "turn", position: "BTN" },
    expectedFreq: { raise: 12, call: 42, fold: 46, bet: 42, check: 58 },
    tolerance: 10,
    description: "A72r + Kd turn: bet 42% ±10%",
    category: "turn",
    source: "PioSolver 2.0",
  },
  {
    id: "turn-jts9-blank",
    spot: { board: "Jh Th 9d 2c", heroRange: "BTN", villainRange: "BB", pot: 15, stacks: 92.5, betSizings: [0.5, 0.75, 1.5], rake: 0.05, street: "turn", position: "BTN" },
    expectedFreq: { raise: 14, call: 40, fold: 46, bet: 38, check: 62 },
    tolerance: 10,
    description: "JTs9 + 2c turn (blank): bet 38% ±10%",
    category: "turn",
    source: "PioSolver 2.0",
  },

  // --- RIVER (1 benchmark) ---
  {
    id: "river-a72-k-3-river",
    spot: { board: "Ah 7d 2c Kd 3h", heroRange: "BTN", villainRange: "BB", pot: 30, stacks: 77.5, betSizings: [0.5, 1.0, 1.5], rake: 0.05, street: "river", position: "BTN" },
    expectedFreq: { raise: 15, call: 38, fold: 47, bet: 48, check: 52 },
    tolerance: 10,
    description: "A72r Kd 3h river: bet 48% ±10%",
    category: "river",
    source: "PioSolver 2.0",
  },
];

// ---------------------------------------------------------------------------
// Validation functions
// ---------------------------------------------------------------------------

export function validateSolverResult(
  result: SolverResult,
  benchmark: ValidationBenchmark
): ValidationResult {
  const expected = benchmark.expectedFreq;
  const actual = {
    raise: result.gtoFreq.raise,
    call: result.gtoFreq.call,
    fold: result.gtoFreq.fold,
    bet: result.gtoFreq.bet,
    check: result.gtoFreq.check,
  };

  const delta = {
    raise: Math.abs(actual.raise - expected.raise),
    call: Math.abs(actual.call - expected.call),
    fold: Math.abs(actual.fold - expected.fold),
    bet: expected.bet !== undefined && actual.bet !== undefined ? Math.abs(actual.bet - expected.bet) : undefined,
    check: expected.check !== undefined && actual.check !== undefined ? Math.abs(actual.check - expected.check) : undefined,
  };

  // Max delta across all compared fields
  const deltas = [delta.raise, delta.call, delta.fold];
  if (delta.bet !== undefined) deltas.push(delta.bet);
  if (delta.check !== undefined) deltas.push(delta.check);
  const maxDelta = Math.max(...deltas);

  const passed = maxDelta <= benchmark.tolerance;

  const details = passed
    ? `PASS: max delta ${maxDelta.toFixed(1)}% within tolerance ${benchmark.tolerance}%`
    : `FAIL: max delta ${maxDelta.toFixed(1)}% exceeds tolerance ${benchmark.tolerance}% (raise Δ${delta.raise.toFixed(1)}%, call Δ${delta.call.toFixed(1)}%, fold Δ${delta.fold.toFixed(1)}%${delta.bet !== undefined ? `, bet Δ${delta.bet.toFixed(1)}%` : ""})`;

  return {
    benchmarkId: benchmark.id,
    description: benchmark.description,
    passed,
    delta: delta as ValidationResult["delta"],
    maxDelta,
    tolerance: benchmark.tolerance,
    expected,
    actual: actual as ValidationResult["actual"],
    details,
  };
}

export function findBenchmarkForSpot(spotHash: string): ValidationBenchmark | null {
  for (const b of VALIDATION_BENCHMARKS) {
    if (generateSpotHash(b.spot) === spotHash) return b;
  }
  return null;
}

export async function runValidationSuite(
  solverService: { solve(spot: SpotInput): Promise<SolverResult> }
): Promise<ValidationSuiteResult> {
  const results: ValidationResult[] = [];
  let passed = 0;

  for (const benchmark of VALIDATION_BENCHMARKS) {
    const result = await solverService.solve(benchmark.spot);
    const validation = validateSolverResult(result, benchmark);
    results.push(validation);
    if (validation.passed) passed++;
  }

  const failed = results.length - passed;
  const accuracy = results.length > 0 ? passed / results.length : 0;
  const avgMaxDelta = results.length > 0 ? results.reduce((sum, r) => sum + r.maxDelta, 0) / results.length : 0;

  return {
    total: results.length,
    passed,
    failed,
    accuracy,
    failures: results.filter((r) => !r.passed),
    results,
    timestamp: new Date().toISOString(),
    avgMaxDelta: Math.round(avgMaxDelta * 10) / 10,
  };
}
