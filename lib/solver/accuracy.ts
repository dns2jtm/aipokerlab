import type { SolverResult } from "./solverService";

// ---------------------------------------------------------------------------
// Accuracy tracking — log every solve with source, latency, benchmark delta
// ---------------------------------------------------------------------------

export type SolveSource = "precomputed" | "cache" | "solver";

export interface SolveLogEntry {
  spotHash: string;
  source: SolveSource;
  latencyMs: number;
  timestamp: number;
  board: string;
  street: string;
  ev: number;
  exploitability: number;
  // Optional benchmark comparison (populated when validation runs)
  benchmarkDelta?: number;
  passedBenchmark?: boolean;
}

export interface AccuracyStats {
  totalSolves: number;
  cacheHitRate: number; // 0-1
  precomputedHitRate: number; // 0-1
  solverRate: number; // 0-1 (on-demand)
  avgLatencyMs: number;
  p50LatencyMs: number;
  p95LatencyMs: number;
  validationAccuracy: number | null; // 0-1, null if not yet validated
  lastValidationAt: string | null;
}

class AccuracyTracker {
  private logs: SolveLogEntry[] = [];
  private maxLogs = 10000;
  private validationAccuracy: number | null = null;
  private lastValidationAt: string | null = null;

  log(entry: SolveLogEntry): void {
    this.logs.push(entry);
    if (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }
  }

  /** Convenience: log from a SolverResult + latency */
  logSolve(result: SolverResult, latencyMs: number): void {
    this.log({
      spotHash: result.spotHash,
      source: result.source as SolveSource,
      latencyMs,
      timestamp: Date.now(),
      board: result.board,
      street: result.street,
      ev: result.ev,
      exploitability: result.exploitability,
    });
  }

  setValidationResult(accuracy: number): void {
    this.validationAccuracy = accuracy;
    this.lastValidationAt = new Date().toISOString();
  }

  getStats(): AccuracyStats {
    const total = this.logs.length;
    if (total === 0) {
      return {
        totalSolves: 0,
        cacheHitRate: 0,
        precomputedHitRate: 0,
        solverRate: 0,
        avgLatencyMs: 0,
        p50LatencyMs: 0,
        p95LatencyMs: 0,
        validationAccuracy: this.validationAccuracy,
        lastValidationAt: this.lastValidationAt,
      };
    }

    const precomputed = this.logs.filter((l) => l.source === "precomputed").length;
    const cached = this.logs.filter((l) => l.source === "cache").length;
    const solver = this.logs.filter((l) => l.source === "solver").length;

    const latencies = this.logs.map((l) => l.latencyMs).sort((a, b) => a - b);
    const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length;
    const p50 = latencies[Math.floor(latencies.length * 0.5)] ?? 0;
    const p95 = latencies[Math.floor(latencies.length * 0.95)] ?? 0;

    return {
      totalSolves: total,
      cacheHitRate: cached / total,
      precomputedHitRate: precomputed / total,
      solverRate: solver / total,
      avgLatencyMs: Math.round(avg * 10) / 10,
      p50LatencyMs: p50,
      p95LatencyMs: p95,
      validationAccuracy: this.validationAccuracy,
      lastValidationAt: this.lastValidationAt,
    };
  }

  getLogs(limit = 100): SolveLogEntry[] {
    return this.logs.slice(-limit);
  }

  clear(): void {
    this.logs = [];
    this.validationAccuracy = null;
    this.lastValidationAt = null;
  }

  size(): number {
    return this.logs.length;
  }
}

export const accuracyTracker = new AccuracyTracker();

// Re-export for convenience
export function getAccuracyStats(): AccuracyStats {
  return accuracyTracker.getStats();
}

export function logSolve(result: SolverResult, latencyMs: number): void {
  accuracyTracker.logSolve(result, latencyMs);
}
