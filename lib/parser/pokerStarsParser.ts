import type { CanonicalHand, CanonicalAction, Site } from "./types";

function parseAmount(s: string): number | undefined {
  const m = s.match(/\$?([\d,]+\.?\d*)/);
  if (!m) return undefined;
  return parseFloat(m[1].replace(/,/g, ""));
}

function parseActionLine(line: string): CanonicalAction | null {
  const colonIdx = line.indexOf(":");
  if (colonIdx === -1) return null;
  const player = line.slice(0, colonIdx).trim();
  const rest = line.slice(colonIdx + 1).trim();
  const lower = rest.toLowerCase();
  const isAllIn = lower.includes("all-in") || lower.includes("all in");
  const amount = parseAmount(rest);
  if (lower.includes("posts small blind") || lower.includes("posts big blind") || lower.startsWith("posts")) {
    return { player, action: "post", amount, isAllIn };
  }
  if (lower.includes("straddle")) return { player, action: "straddle", amount, isAllIn };
  if (lower.includes("ante")) return { player, action: "ante", amount, isAllIn };
  if (lower.startsWith("folds") || lower === "fold") return { player, action: "fold", isAllIn };
  if (lower.startsWith("checks") || lower === "check") return { player, action: "check", isAllIn };
  if (lower.startsWith("calls")) return { player, action: "call", amount, isAllIn };
  if (lower.startsWith("bets")) return { player, action: "bet", amount, isAllIn };
  if (lower.startsWith("raises")) {
    const toMatch = rest.match(/to\s+\$?([\d,.]+)/i);
    const total = toMatch ? parseFloat(toMatch[1].replace(/,/g, "")) : undefined;
    return { player, action: "raise", amount, total, isAllIn };
  }
  if (lower.includes("all-in") || lower.includes("all in")) {
    if (lower.includes("bets")) return { player, action: "bet", amount, isAllIn: true };
    if (lower.includes("raises")) return { player, action: "raise", amount, isAllIn: true };
    if (lower.includes("calls")) return { player, action: "call", amount, isAllIn: true };
    return { player, action: "all-in", amount, isAllIn: true };
  }
  if (lower.includes("fold")) return { player, action: "fold", isAllIn };
  if (lower.includes("check")) return { player, action: "check", isAllIn };
  if (lower.includes("call")) return { player, action: "call", amount, isAllIn };
  if (lower.includes("bet")) return { player, action: "bet", amount, isAllIn };
  if (lower.includes("raise")) return { player, action: "raise", amount, isAllIn };
  return null;
}

export function parsePokerStarsHand(raw: string, index: number): CanonicalHand {
  const text = raw.trim();
  const lines = text.split("\n").map((l) => l.trim());
  let id = `ps-${index}-${Date.now()}`;
  let stakes = "";
  let date = "";
  const headerMatch = text.match(/PokerStars Hand #(\d+)/i);
  if (headerMatch) id = `PS${headerMatch[1]}`;
  const stakesMatch = text.match(/\(\$?([\d.]+\/\$?[\d.]+)[^)]*\)/);
  if (stakesMatch) stakes = stakesMatch[1].replace(/\$/g, "");
  else {
    const alt = text.match(/\$?(\d+(?:\.\d+)?)\/\$?(\d+(?:\.\d+)?)/);
    if (alt) stakes = `${alt[1]}/${alt[2]}`;
  }
  const dateMatch = text.match(/-\s*(\d{4}\/\d{2}\/\d{2}\s+[\d:]+\s*\w*)/);
  if (dateMatch) date = dateMatch[1].trim();
  else {
    const iso = text.match(/\d{4}-\d{2}-\d{2}/);
    if (iso) date = iso[0];
  }
  const seats: { name: string; chips: number }[] = [];
  for (const line of lines) {
    const seatMatch = line.match(/^Seat \d+:\s*(\S+)\s*\(\$?([\d,.]+) in chips\)/i);
    if (seatMatch) seats.push({ name: seatMatch[1], chips: parseFloat(seatMatch[2].replace(/,/g, "")) });
  }
  let hero = "";
  let heroCards = "";
  const dealtMatch = text.match(/Dealt to\s+(\S+)\s*\[([^\]]+)\]/i);
  if (dealtMatch) {
    hero = dealtMatch[1];
    heroCards = dealtMatch[2].trim();
  } else if (seats.length > 0) {
    hero = seats[0].name;
  }
  let flopBoard = "";
  let turnBoard = "";
  let riverBoard = "";
  let fullBoard = "";
  for (const line of lines) {
    if (/^\*\*\* FLOP \*\*\*/i.test(line)) {
      const m = line.match(/\[([^\]]+)\]/);
      if (m) flopBoard = m[1].trim();
    }
    if (/^\*\*\* TURN \*\*\*/i.test(line)) {
      const all = [...line.matchAll(/\[([^\]]+)\]/g)].map((x) => x[1]);
      if (all.length >= 2) {
        turnBoard = all[all.length - 1].trim();
        fullBoard = all.join(" ").trim();
      } else if (all.length === 1) turnBoard = all[0].trim();
    }
    if (/^\*\*\* RIVER \*\*\*/i.test(line)) {
      const all = [...line.matchAll(/\[([^\]]+)\]/g)].map((x) => x[1]);
      if (all.length >= 2) {
        riverBoard = all[all.length - 1].trim();
        fullBoard = all.join(" ").trim();
      } else if (all.length === 1) riverBoard = all[0].trim();
    }
    if (/^Board \[/i.test(line)) {
      const m = line.match(/\[([^\]]+)\]/);
      if (m) fullBoard = m[1].trim();
    }
  }
  if (!fullBoard) {
    if (flopBoard && turnBoard && riverBoard) fullBoard = `${flopBoard} ${turnBoard} ${riverBoard}`;
    else if (flopBoard && turnBoard) fullBoard = `${flopBoard} ${turnBoard}`;
    else if (flopBoard) fullBoard = flopBoard;
  }
  let ante: number | undefined;
  let straddle: number | undefined;
  for (const line of lines) {
    if (/ante/i.test(line) && line.includes("$")) {
      const a = parseAmount(line);
      if (a !== undefined) ante = a;
    }
    if (/straddle/i.test(line) && line.includes("$")) {
      const s = parseAmount(line);
      if (s !== undefined) straddle = s;
    }
  }
  const streets: CanonicalHand["streets"] = { preflop: [], flop: [], turn: [], river: [] };
  let currentStreet: keyof typeof streets = "preflop";
  let inSummary = false;
  for (const line of lines) {
    if (/^\*\*\* SUMMARY/i.test(line)) inSummary = true;
    if (/^\*\*\* HOLE CARDS/i.test(line)) { currentStreet = "preflop"; continue; }
    if (/^\*\*\* FLOP/i.test(line)) { currentStreet = "flop"; continue; }
    if (/^\*\*\* TURN/i.test(line)) { currentStreet = "turn"; continue; }
    if (/^\*\*\* RIVER/i.test(line)) { currentStreet = "river"; continue; }
    if (/^\*\*\* SHOW DOWN/i.test(line) || /^\*\*\* SHOWDOWN/i.test(line)) continue;
    if (line.startsWith("***")) continue;
    if (/^PokerStars Hand #/i.test(line) || /^Table /i.test(line) || /^Seat \d+:/i.test(line)) continue;
    if (/^Board \[/i.test(line)) continue;
    if (/Dealt to/i.test(line)) continue;
    if (inSummary) continue;
    if (/collected/i.test(line) || /Uncalled bet/i.test(line) || /Total pot/i.test(line)) continue;
    const action = parseActionLine(line);
    if (action) {
      streets[currentStreet].push(action);
    } else {
      if (line.includes("posts") || line.includes("calls") || line.includes("raises") || line.includes("bets") || line.includes("folds") || line.includes("checks")) {
        const parts = line.split(/\s+/);
        if (parts.length >= 2) {
          const player = parts[0];
          const rest = parts.slice(1).join(" ");
          const fakeLine = `${player}: ${rest}`;
          const a2 = parseActionLine(fakeLine);
          if (a2) streets[currentStreet].push(a2);
        }
      }
    }
  }
  let pot = 0;
  const potMatch = text.match(/Total pot\s+\$?([\d,.]+)/i);
  if (potMatch) pot = parseFloat(potMatch[1].replace(/,/g, ""));
  else {
    const altPot = text.match(/Pot:\s*\$?([\d,.]+)/i);
    if (altPot) pot = parseFloat(altPot[1].replace(/,/g, ""));
  }
  if (!pot) {
    let sum = 0;
    const allStreets = Object.values(streets) as CanonicalAction[][];
    for (const s of allStreets) for (const a of s) if (a.amount) sum += a.amount;
    pot = Math.round(sum * 100) / 100;
  }
  const winners: { player: string; amount: number }[] = [];
  const collectedRe = /(\S+)\s+collected\s+\$?\(?([\d,.]+)\)?/gi;
  let m: RegExpExecArray | null;
  while ((m = collectedRe.exec(text)) !== null) {
    const player = m[1].replace(/:/g, "").trim();
    if (player.toLowerCase() === "seat") continue;
    const amount = parseFloat(m[2].replace(/,/g, ""));
    if (!winners.find((w) => w.player === player)) winners.push({ player, amount });
  }
  const winnerRe = /Winner\s+(\S+)\s+wins\s+\$?([\d,.]+)/gi;
  while ((m = winnerRe.exec(text)) !== null) {
    const player = m[1].trim();
    const amount = parseFloat(m[2].replace(/,/g, ""));
    if (!winners.find((w) => w.player === player)) winners.push({ player, amount });
  }
  const sidePots: number[] = [];
  const sideRe = /Side pot\s+\$?([\d,.]+)/gi;
  while ((m = sideRe.exec(text)) !== null) sidePots.push(parseFloat(m[1].replace(/,/g, "")));
  const mainPotRe = /Main pot\s+\$?([\d,.]+)/gi;
  while ((m = mainPotRe.exec(text)) !== null) sidePots.push(parseFloat(m[1].replace(/,/g, "")));
  const site: Site = "pokerstars";
  return {
    id,
    site,
    stakes,
    date: date || new Date().toISOString().slice(0, 10),
    hero: hero || "Hero",
    heroCards,
    board: fullBoard,
    streets,
    streetBoards: { preflop: "", flop: flopBoard, turn: turnBoard, river: riverBoard },
    pot,
    winners,
    raw: text,
    ante,
    straddle,
    sidePots: sidePots.length ? sidePots : undefined,
  };
}

export function isPokerStarsFormat(text: string): boolean {
  return /PokerStars Hand #/i.test(text) || /\*\*\* HOLE CARDS \*\*\*/i.test(text);
}
