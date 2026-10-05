export type Site = "pokerstars" | "ggpoker" | "generic";
export type StreetKey = "preflop" | "flop" | "turn" | "river";

export type ActionKind =
  | "fold"
  | "check"
  | "call"
  | "bet"
  | "raise"
  | "post"
  | "straddle"
  | "ante"
  | "all-in";

export interface CanonicalAction {
  player: string;
  action: ActionKind;
  amount?: number;
  total?: number; // for raises: total to amount
  isAllIn?: boolean;
}

export interface CanonicalHand {
  id: string;
  site: Site;
  stakes: string; // e.g. "0.50/1.00" or "1/2"
  date: string; // ISO or raw
  hero: string;
  heroCards: string; // e.g. "As 5s"
  board: string; // full board e.g. "Qh 7d 2c Kd 2h"
  streets: Record<StreetKey, CanonicalAction[]>;
  streetBoards: Record<StreetKey, string>; // per street board slice; preflop is ""
  pot: number;
  winners: { player: string; amount: number }[];
  raw: string;
  ante?: number;
  straddle?: number;
  sidePots?: number[];
}

export interface ParseResult {
  hands: CanonicalHand[];
  errors: { index: number; message: string; snippet: string }[];
}
