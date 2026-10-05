#!/usr/bin/env npx tsx
/**
 * CLI: validate solver accuracy vs PioSolver benchmarks
 * Usage: npx tsx scripts/validateSolver.ts
 */

import { SolverService } from "../lib/solver/solverService";
import { runValidationSuite, VALIDATION_BENCHMARKS } from "../lib/solver/validation";

async function main() {
  console.log("=".repeat(70));
  console.log("  AI Poker Lab — Solver Validation vs PioSolver");
  console.log("=".repeat(70));
  console.log(`  Benchmarks: ${VALIDATION_BENCHMARKS.length} spots`);
  console.log(`  Tolerance:  <1% EV delta, <5% frequency delta (preflop), <10% (postflop)`);
  console.log(`  Source:     PioSolver 2.0 / GTO Wizard @ 100bb, 5% rake`);
  console.log("=".repeat(70));
  console.log("");

  const suite = await runValidationSuite(SolverService);

  // Print per-benchmark results
  for (const r of suite.results) {
    const icon = r.passed ? "✓ PASS" : "✗ FAIL";
    const color = r.passed ? "\x1b[32m" : "\x1b[31m";
    const reset = "\x1b[0m";
    console.log(
      `${color}${icon}${reset} [${r.benchmarkId}] ${r.description}\n` +
        `       Expected: raise ${r.expected.raise}% / call ${r.expected.call}% / fold ${r.expected.fold}%` +
        (r.expected.bet !== undefined ? ` / bet ${r.expected.bet}%` : "") +
        `\n       Actual:   raise ${r.actual.raise}% / call ${r.actual.call}% / fold ${r.actual.fold}%` +
        (r.actual.bet !== undefined ? ` / bet ${r.actual.bet}%` : "") +
        `\n       ${r.details}\n`
    );
  }

  console.log("-".repeat(70));
  console.log(`  Results: ${suite.passed}/${suite.total} passed (${(suite.accuracy * 100).toFixed(1)}% accuracy)`);
  console.log(`  Avg max delta: ${suite.avgMaxDelta}%`);
  if (suite.failures.length > 0) {
    console.log(`  Failures: ${suite.failures.length}`);
    for (const f of suite.failures) {
      console.log(`    - ${f.benchmarkId}: ${f.details}`);
    }
  }
  console.log(`  Timestamp: ${suite.timestamp}`);
  console.log("-".repeat(70));

  if (suite.accuracy < 0.8) {
    console.log("\x1b[31m  WARNING: Accuracy below 80% — review solver frequencies!\x1b[0m");
  } else if (suite.accuracy < 0.95) {
    console.log("\x1b[33m  NOTE: Accuracy below 95% — some benchmarks outside tolerance.\x1b[0m");
  } else {
    console.log("\x1b[32m  All benchmarks within tolerance — solver validated ✓\x1b[0m");
  }

  process.exit(suite.failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error("Validation failed:", err);
  process.exit(1);
});
