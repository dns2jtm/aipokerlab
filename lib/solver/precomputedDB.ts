import type { SolverResult } from "./solverService";

// ---------------------------------------------------------------------------
// PrecomputedDB abstraction
// ---------------------------------------------------------------------------

export interface PrecomputedDB {
  get(spotHash: string): SolverResult | null;
  set(spotHash: string, result: SolverResult): void;
  has(spotHash: string): boolean;
  size(): number;
  export(): Record<string, SolverResult>;
  import(data: Record<string, SolverResult>): void;
}

// ---------------------------------------------------------------------------
// InMemoryPrecomputedDB — LRU eviction (5000 entries) + Prisma persistence
// ---------------------------------------------------------------------------

export class InMemoryPrecomputedDB implements PrecomputedDB {
  private map = new Map<string, SolverResult>();
  private maxSize: number;

  constructor(maxSize = 5000) {
    this.maxSize = maxSize;
  }

  get(spotHash: string): SolverResult | null {
    const entry = this.map.get(spotHash);
    if (!entry) return null;
    // LRU: re-insert to mark as recently used
    this.map.delete(spotHash);
    this.map.set(spotHash, entry);
    // Return with source overridden to precomputed for transparency
    return { ...entry, source: "precomputed" as unknown as SolverResult["source"], solveTimeMs: Math.min(entry.solveTimeMs, 5) };
  }

  /** Raw get without source override — for internal use */
  getRaw(spotHash: string): SolverResult | null {
    const entry = this.map.get(spotHash);
    if (!entry) return null;
    this.map.delete(spotHash);
    this.map.set(spotHash, entry);
    return { ...entry };
  }

  set(spotHash: string, result: SolverResult): void {
    if (this.map.has(spotHash)) {
      this.map.delete(spotHash);
    } else if (this.map.size >= this.maxSize) {
      const firstKey = this.map.keys().next().value as string | undefined;
      if (firstKey) this.map.delete(firstKey);
    }
    this.map.set(spotHash, { ...result });
  }

  has(spotHash: string): boolean {
    return this.map.has(spotHash);
  }

  size(): number {
    return this.map.size;
  }

  clear(): void {
    this.map.clear();
  }

  export(): Record<string, SolverResult> {
    const out: Record<string, SolverResult> = {};
    for (const [k, v] of this.map.entries()) out[k] = { ...v };
    return out;
  }

  import(data: Record<string, SolverResult>): void {
    for (const [k, v] of Object.entries(data)) {
      this.set(k, v);
    }
  }

  /** Return all hashes (for debugging / export) */
  keys(): string[] {
    return [...this.map.keys()];
  }

  // -----------------------------------------------------------------------
  // Persistence — Prisma SolverCache sync (graceful fallback to memory)
  // -----------------------------------------------------------------------

  /**
   * Load entries from Prisma SolverCache into memory.
   * No-op if DATABASE_URL is not set or Prisma is unavailable.
   * Returns number of entries loaded.
   */
  async syncFromDB(): Promise<number> {
    if (!process.env.DATABASE_URL) return 0;
    try {
      const { prisma } = await import("@/lib/db/prisma");
      const rows = await prisma.solverCache.findMany({
        take: this.maxSize,
        orderBy: { hitCount: "desc" },
      });
      let loaded = 0;
      for (const row of rows) {
        const sol = row.solutionJson as unknown as SolverResult | null;
        if (sol && sol.spotHash) {
          this.set(row.spotHash, sol);
          loaded++;
        } else if (row.strategyMap && row.evMap) {
          // Legacy shape — reconstruct minimal SolverResult
          const strat = row.strategyMap as unknown as { raise: number; call: number; fold: number };
          const evMap = row.evMap as unknown as { ev?: number };
          const reconstructed: SolverResult = {
            spotHash: row.spotHash,
            gtoFreq: {
              raise: strat.raise ?? 10,
              call: strat.call ?? 50,
              fold: strat.fold ?? 40,
            },
            ev: typeof evMap.ev === "number" ? evMap.ev : 0.5,
            exploitability: 0.005,
            source: "precomputed" as unknown as SolverResult["source"],
            solveTimeMs: 2,
            board: (row.board as string) ?? "",
            street: (row.stackDepth as string) ?? "flop",
          };
          this.set(row.spotHash, reconstructed);
          loaded++;
        }
      }
      return loaded;
    } catch {
      // Fallback to memory — DB unavailable
      return 0;
    }
  }

  /**
   * Persist all in-memory entries to Prisma SolverCache (upsert).
   * No-op if DATABASE_URL is not set.
   * Returns number of entries persisted.
   */
  async syncToDB(): Promise<number> {
    if (!process.env.DATABASE_URL) return 0;
    try {
      const { prisma } = await import("@/lib/db/prisma");
      let persisted = 0;
      for (const [hash, result] of this.map.entries()) {
        await prisma.solverCache.upsert({
          where: { spotHash: hash },
          update: {
            solutionJson: result as unknown as object,
            board: result.board,
            hitCount: { increment: 0 },
          },
          create: {
            spotHash: hash,
            board: result.board,
            solutionJson: result as unknown as object,
            evMap: { ev: result.ev } as unknown as object,
            strategyMap: result.gtoFreq as unknown as object,
          },
        });
        persisted++;
      }
      return persisted;
    } catch {
      return 0;
    }
  }

  /**
   * Persist a single entry to DB (fire-and-forget safe).
   */
  async persistEntry(spotHash: string, result: SolverResult): Promise<void> {
    if (!process.env.DATABASE_URL) return;
    try {
      const { prisma } = await import("@/lib/db/prisma");
      await prisma.solverCache.upsert({
        where: { spotHash },
        update: {
          solutionJson: result as unknown as object,
          board: result.board,
        },
        create: {
          spotHash,
          board: result.board,
          solutionJson: result as unknown as object,
          evMap: { ev: result.ev } as unknown as object,
          strategyMap: result.gtoFreq as unknown as object,
        },
      });
    } catch {
      // ignore — memory fallback
    }
  }

  /**
   * Load from JSON file data (e.g. data/precomputedDB.json) — synchronous import helper.
   * Accepts either Record<string, SolverResult> or { spots: Record<string, SolverResult> } shape.
   */
  importFromJson(json: unknown): number {
    if (!json || typeof json !== "object") return 0;
    const obj = json as Record<string, unknown>;
    // Support both { spots: {...} } and direct map
    const data = (obj.spots && typeof obj.spots === "object" ? obj.spots : obj) as Record<string, SolverResult>;
    let count = 0;
    for (const [k, v] of Object.entries(data)) {
      if (v && typeof v === "object" && "spotHash" in v && "gtoFreq" in v) {
        this.set(k, v as SolverResult);
        count++;
      }
    }
    return count;
  }
}

// Singleton — shared across server
export const precomputedDB = new InMemoryPrecomputedDB(5000);

// ---------------------------------------------------------------------------
// Lazy loader for data/precomputedDB.json (server-side only)
// ---------------------------------------------------------------------------

let _loadedFromJson = false;

/**
 * Ensure precomputedDB is hydrated from data/precomputedDB.json (once).
 * Safe to call multiple times; no-op in edge runtime or if already loaded.
 */
export async function ensurePrecomputedDBLoaded(): Promise<number> {
  if (_loadedFromJson) return precomputedDB.size();
  _loadedFromJson = true;
  try {
    // Dynamic import to avoid bundling JSON in client
    const fs = await import("fs");
    const path = await import("path");
    const jsonPath = path.join(process.cwd(), "data", "precomputedDB.json");
    if (!fs.existsSync(jsonPath)) return precomputedDB.size();
    const raw = fs.readFileSync(jsonPath, "utf-8");
    const parsed = JSON.parse(raw);
    const count = precomputedDB.importFromJson(parsed);
    return count;
  } catch {
    return precomputedDB.size();
  }
}

/** For testing — reset loaded flag */
export function _resetPrecomputedDBForTest(): void {
  _loadedFromJson = false;
  precomputedDB.clear();
}
