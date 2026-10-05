import { describe, it, expect, beforeEach } from "vitest";
import { InMemoryPrecomputedDB } from "./precomputedDB";
import type { SolverResult } from "./solverService";

function makeResult(hash: string, overrides: Partial<SolverResult> = {}): SolverResult {
  return {
    spotHash: hash,
    gtoFreq: { raise: 10, call: 50, fold: 40 },
    ev: 0.5,
    exploitability: 0.005,
    source: "precomputed" as unknown as SolverResult["source"],
    solveTimeMs: 2,
    board: "Ah 7d 2c",
    street: "flop",
    ...overrides,
  };
}

describe("InMemoryPrecomputedDB", () => {
  let db: InMemoryPrecomputedDB;

  beforeEach(() => {
    db = new InMemoryPrecomputedDB(5); // small for testing eviction
  });

  it("get/set/has/size basic operations", () => {
    expect(db.size()).toBe(0);
    expect(db.has("abc")).toBe(false);
    expect(db.get("abc")).toBeNull();

    const r = makeResult("abc");
    db.set("abc", r);
    expect(db.size()).toBe(1);
    expect(db.has("abc")).toBe(true);

    const got = db.get("abc");
    expect(got).not.toBeNull();
    expect(got!.spotHash).toBe("abc");
    expect(got!.gtoFreq).toEqual(r.gtoFreq);
    // source should be precomputed
    expect(got!.source).toBe("precomputed");
  });

  it("get returns null for missing key", () => {
    db.set("exists", makeResult("exists"));
    expect(db.get("missing")).toBeNull();
  });

  it("LRU eviction when exceeding maxSize", () => {
    // maxSize = 5
    for (let i = 0; i < 5; i++) {
      db.set(`key${i}`, makeResult(`key${i}`));
    }
    expect(db.size()).toBe(5);
    expect(db.has("key0")).toBe(true);

    // Adding 6th should evict key0 (LRU)
    db.set("key5", makeResult("key5"));
    expect(db.size()).toBe(5);
    expect(db.has("key0")).toBe(false);
    expect(db.has("key5")).toBe(true);
    expect(db.has("key1")).toBe(true);
  });

  it("LRU: get promotes entry, so oldest non-accessed is evicted", () => {
    for (let i = 0; i < 5; i++) {
      db.set(`k${i}`, makeResult(`k${i}`));
    }
    // Access k0 to make it recently used
    db.get("k0");
    // Now k1 is the LRU
    db.set("k5", makeResult("k5"));
    expect(db.has("k1")).toBe(false); // k1 evicted
    expect(db.has("k0")).toBe(true); // k0 survived due to get
    expect(db.has("k5")).toBe(true);
  });

  it("set overwrites existing key without growing size", () => {
    db.set("a", makeResult("a", { ev: 0.5 }));
    db.set("a", makeResult("a", { ev: 0.9 }));
    expect(db.size()).toBe(1);
    expect(db.get("a")!.ev).toBe(0.9);
  });

  it("export and import round-trip", () => {
    const r1 = makeResult("h1");
    const r2 = makeResult("h2", { board: "Kh 8d 3c" });
    db.set("h1", r1);
    db.set("h2", r2);

    const exported = db.export();
    expect(Object.keys(exported)).toHaveLength(2);
    expect(exported["h1"].spotHash).toBe("h1");
    expect(exported["h2"].board).toBe("Kh 8d 3c");

    const db2 = new InMemoryPrecomputedDB(10);
    db2.import(exported);
    expect(db2.size()).toBe(2);
    expect(db2.get("h1")!.spotHash).toBe("h1");
    expect(db2.get("h2")!.board).toBe("Kh 8d 3c");
  });

  it("importFromJson handles { spots: {...} } shape", () => {
    const json = {
      version: 1,
      count: 2,
      spots: {
        s1: makeResult("s1"),
        s2: makeResult("s2"),
      },
    };
    const count = db.importFromJson(json);
    expect(count).toBe(2);
    expect(db.size()).toBe(2);
    expect(db.has("s1")).toBe(true);
    expect(db.has("s2")).toBe(true);
  });

  it("importFromJson handles direct map shape", () => {
    const json = {
      s1: makeResult("s1"),
      s2: makeResult("s2"),
    };
    const count = db.importFromJson(json);
    expect(count).toBe(2);
    expect(db.size()).toBe(2);
  });

  it("importFromJson ignores invalid entries", () => {
    const json = {
      valid: makeResult("valid"),
      invalid: { foo: "bar" },
      alsoInvalid: null,
    };
    const count = db.importFromJson(json as unknown as Record<string, SolverResult>);
    expect(count).toBe(1);
    expect(db.has("valid")).toBe(true);
    expect(db.has("invalid")).toBe(false);
  });

  it("clear empties the DB", () => {
    db.set("a", makeResult("a"));
    db.set("b", makeResult("b"));
    expect(db.size()).toBe(2);
    db.clear();
    expect(db.size()).toBe(0);
    expect(db.has("a")).toBe(false);
  });

  it("keys returns all hashes", () => {
    db.set("x", makeResult("x"));
    db.set("y", makeResult("y"));
    const keys = db.keys();
    expect(keys).toContain("x");
    expect(keys).toContain("y");
    expect(keys).toHaveLength(2);
  });

  it("get returns copy with solveTimeMs capped to 5ms", () => {
    const r = makeResult("slow", { solveTimeMs: 50 });
    db.set("slow", r);
    const got = db.get("slow");
    expect(got!.solveTimeMs).toBeLessThanOrEqual(5);
  });
});
