import { NextResponse } from "next/server";
import { SolverService } from "@/lib/solver/solverService";
import { runValidationSuite, VALIDATION_BENCHMARKS } from "@/lib/solver/validation";
import { accuracyTracker } from "@/lib/solver/accuracy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const suite = await runValidationSuite(SolverService);
    accuracyTracker.setValidationResult(suite.accuracy);
    return NextResponse.json(
      {
        status: "ok",
        summary: {
          total: suite.total,
          passed: suite.passed,
          failed: suite.failed,
          accuracy: suite.accuracy,
          accuracyPercent: `${(suite.accuracy * 100).toFixed(1)}%`,
          avgMaxDelta: suite.avgMaxDelta,
          timestamp: suite.timestamp,
        },
        benchmarks: VALIDATION_BENCHMARKS.map((b) => ({
          id: b.id,
          description: b.description,
          category: b.category,
          tolerance: b.tolerance,
          source: b.source,
        })),
        results: suite.results.map((r) => ({
          benchmarkId: r.benchmarkId,
          description: r.description,
          passed: r.passed,
          maxDelta: r.maxDelta,
          tolerance: r.tolerance,
          expected: r.expected,
          actual: r.actual,
          details: r.details,
        })),
        failures: suite.failures.map((f) => ({
          benchmarkId: f.benchmarkId,
          description: f.description,
          maxDelta: f.maxDelta,
          tolerance: f.tolerance,
          expected: f.expected,
          actual: f.actual,
          details: f.details,
        })),
      },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (err) {
    console.error("[solver/validate] error", err);
    return NextResponse.json({ error: "Validation failed", details: String(err) }, { status: 500 });
  }
}
