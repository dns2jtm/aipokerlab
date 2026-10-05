import type { CanonicalHand, ParseResult, Site } from "./types";
import { parsePokerStarsHand, isPokerStarsFormat } from "./pokerStarsParser";
import { parseGGPokerHand, isGGPokerFormat } from "./ggpokerParser";

export type { CanonicalHand, ParseResult, Site } from "./types";
export type Street = "preflop" | "flop" | "turn" | "river";

export interface ParsedAction {
  player: string;
  action: string;
  amount?: string;
}

export interface ParsedStreet {
  street: Street;
  board: string;
  actions: ParsedAction[];
  heroCards?: string;
  pot?: string;
}

export interface ParsedHand {
  raw: string;
  hero?: string;
  stakes?: string;
  streets: ParsedStreet[];
  summary?: string;
}

// Legacy heuristic parser kept for backwards compat — delegates to canonical
export function parseHandHistory(raw: string): ParsedHand {
  const canonical = parseSingleHand(raw, 0);
  if (!canonical) return { raw: raw.trim(), streets: [] };
  const streets: ParsedStreet[] = (["preflop", "flop", "turn", "river"] as const)
    .map((k) => {
      const actions = canonical.streets[k];
      const board = canonical.streetBoards[k] || (k === "preflop" ? "" : canonical.board);
      // For flop, use flop board; for turn/river, use that street's card; but keep full board for display
      const displayBoard = k === "flop" ? canonical.streetBoards.flop : k === "turn" ? canonical.streetBoards.turn : k === "river" ? canonical.streetBoards.river : "";
      return {
        street: k as Street,
        board: displayBoard || board,
        actions: actions.map((a) => ({
          player: a.player,
          action: `${a.action}${a.amount !== undefined ? ` $${a.amount}` : ""}${a.isAllIn ? " (all-in)" : ""}`,
          amount: a.amount !== undefined ? String(a.amount) : undefined,
        })),
        heroCards: k === "preflop" ? canonical.heroCards : undefined,
        pot: k === "river" ? String(canonical.pot) : undefined,
      };
    })
    .filter((s) => s.actions.length > 0 || s.street === "preflop");
  // Ensure at least one street
  const filtered = streets.filter((s, i) => !(i === 0 && s.actions.length === 0 && streets.length > 1));
  return {
    raw: canonical.raw,
    hero: canonical.hero,
    stakes: canonical.stakes,
    streets: filtered.length ? filtered : streets,
  };
}

function detectSite(text: string): Site {
  if (isPokerStarsFormat(text)) return "pokerstars";
  if (isGGPokerFormat(text)) return "ggpoker";
  // Heuristic: if contains GGPoker keyword
  if (/GGPoker/i.test(text)) return "ggpoker";
  if (/PokerStars/i.test(text)) return "pokerstars";
  return "generic";
}

function parseSingleHand(raw: string, index: number): CanonicalHand | null {
  const text = raw.trim();
  if (!text) return null;
  const site = detectSite(text);
  if (site === "pokerstars") return parsePokerStarsHand(text, index);
  if (site === "ggpoker") return parseGGPokerHand(text, index);
  // generic: try PokerStars parser as fallback (handles *** FLOP *** etc), else GGPoker
  if (text.includes("*** FLOP") || text.includes("*** TURN") || text.includes("*** RIVER")) {
    return parsePokerStarsHand(text, index);
  }
  // fallback to GGPoker parser for generic
  const gg = parseGGPokerHand(text, index);
  // If GGPoker parser produced no actions, try Stars
  const totalActions = Object.values(gg.streets).reduce((acc, arr) => acc + arr.length, 0);
  if (totalActions === 0) return parsePokerStarsHand(text, index);
  return gg;
}

function splitHands(rawText: string): string[] {
  const text = rawText.trim();
  if (!text) return [];
  // Split on hand headers: PokerStars Hand # or GGPoker Hand # / Game # / Hand #
  // Keep delimiter with hand
  const headerRe = /(?=(?:PokerStars Hand #|GGPoker Hand #))/g;
  const parts = text.split(headerRe).map((p) => p.trim()).filter(Boolean);
  if (parts.length <= 1) {
    // No headers found — treat as single hand if contains actions, else try double newline split for multiple pasted hands
    if (parts.length === 0) return [];
    // If raw contains multiple "*** SUMMARY ***" blocks, split there
    const summarySplit = text.split(/(?=\*\*\* SUMMARY)/g);
    // Actually better: if text has multiple "Total pot" or multiple "*** HOLE CARDS ***", split
    const holeCount = (text.match(/\*\*\* HOLE CARDS \*\*\*/gi) || []).length;
    if (holeCount > 1) {
      // Split on hole cards marker, but keep header
      const holeSplit = text.split(/(?=\*\*\* HOLE CARDS \*\*\*)/g);
      // Re-attach preceding header to each
      return holeSplit.map((p) => p.trim()).filter((p) => p.length > 20);
    }
    return [text];
  }
  return parts;
}

export function parseHands(rawText: string): ParseResult {
  const chunks = splitHands(rawText);
  const hands: CanonicalHand[] = [];
  const errors: ParseResult["errors"] = [];
  chunks.forEach((chunk, idx) => {
    try {
      const hand = parseSingleHand(chunk, idx);
      if (!hand) {
        errors.push({ index: idx, message: "Empty hand", snippet: chunk.slice(0, 120) });
        return;
      }
      // Validate: must have at least one action or hero
      const totalActions = Object.values(hand.streets).reduce((acc, arr) => acc + (arr as unknown[]).length, 0);
      if (totalActions === 0 && !hand.heroCards && !hand.board) {
        errors.push({ index: idx, message: "No actions or cards parsed", snippet: chunk.slice(0, 120) });
        // Still push as generic hand for visibility
        hands.push(hand);
        return;
      }
      hands.push(hand);
    } catch (e) {
      errors.push({ index: idx, message: String(e), snippet: chunk.slice(0, 120) });
    }
  });
  return { hands, errors };
}

// Re-export canonical type for consumers
export type Hand = CanonicalHand;

export const SAMPLE_HAND = `PokerStars Hand #123456789: Hold'em No Limit ($0.50/$1.00) - 2026/10/05 12:00:00 ET
Table 'Lab 1' 6-max Seat #3 is the button
Seat 1: Villain ($100 in chips)
Seat 3: Hero ($100 in chips)
Hero: posts small blind $0.50
Villain: posts big blind $1.00
*** HOLE CARDS ***
Dealt to Hero [As 5s]
Villain: raises $2.50 to $3.50
Hero: calls $3.00
*** FLOP *** [Qh 7d 2c]
Hero: checks
Villain: bets $4.00
Hero: folds
*** SUMMARY ***
Total pot $7.50 | Rake $0.35
Villain collected $7.15 from pot
`;

export const SAMPLE_GG_HAND = `GGPoker Hand #987654321: Hold'em No Limit ($0.25/$0.50) - 2026/10/05 12:00:00 UTC
Table 'GG Lab' 6-max Seat #2 is the button
Seat 1: Hero ($50.00 in chips)
Seat 2: Villain ($50.00 in chips)
Hero: posts small blind $0.25
Villain: posts big blind $0.50
*** HOLE CARDS ***
Dealt to Hero [Ah Kd]
Villain: raises $1.00 to $1.50
Hero: calls $1.00
*** FLOP *** [Qh 7d 2c]
Hero: checks
Villain: bets $2.00
Hero: calls $2.00
*** TURN *** [Qh 7d 2c] [Ks]
Hero: checks
Villain: bets $5.00
Hero: folds
*** SUMMARY ***
Total pot $7.50 | Rake $0.35
Villain collected $7.15 from pot
`;

export const SAMPLE_ALLIN_HAND = `PokerStars Hand #999999999: Hold'em No Limit ($1/$2) - 2026/10/05 12:00:00 ET
Table 'AllIn' 6-max Seat #1 is the button
Seat 1: Hero ($200 in chips)
Seat 2: Villain ($200 in chips)
Seat 3: Shorty ($20 in chips)
Hero: posts small blind $1
Villain: posts big blind $2
Shorty: posts ante $0.20
Hero: posts straddle $4
*** HOLE CARDS ***
Dealt to Hero [As Ks]
Shorty: raises $18 to $20 and is all-in
Hero: calls $19
Villain: folds
*** FLOP *** [Qh 7d 2c]
*** TURN *** [Qh 7d 2c] [Kd]
*** RIVER *** [Qh 7d 2c Kd] [2h]
*** SUMMARY ***
Total pot $42.20 | Rake $1.00
Main pot $42.20 | Side pot $0
Hero collected $42.20 from pot
`;
