import type { CanonicalHand, CanonicalAction, Site } from "./types";

function parseAmount(s: string): number | undefined {
  const m = s.match(/\$?([\d,]+\.?\d*)/);
  if (!m) return undefined;
  return parseFloat(m[1].replace(/,/g, ""));
}

function parseGGActionLine(line: string): CanonicalAction | null {
  // GGPoker examples:
  // "Hero: folds", "PlayerOne: calls $1.00", "PlayerTwo: raises $3.00 to $4.00", "Hero: checks", "Player: bets $2.50", "Player: all-in $25.00"
  // Also: "Hero: posts small blind $0.50", "Hero: posts big blind $1.00", "Player: posts ante $0.10", "Player: straddle $2"
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
  if (isAllIn) {
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

export function parseGGPokerHand(raw: string, index: number): CanonicalHand {
  const text = raw.trim();
  const lines = text.split("\n").map((l) => l.trim());

  // GGPoker header examples:
  // "Hand #123456789 - Hold'em No Limit ($0.50/$1.00) - 2026/10/05 12:00:00 UTC"
  // "Poker Hand #123: Hold'em No Limit ($1/$2 USD) - 2026/10/05"
  // "GGPoker Hand #123456789: Hold'em No Limit ($0.25/$0.50) - 2026/10/05"
  let id = `gg-${index}-${Date.now()}`;
  let stakes = "";
  let date = "";
  const ggIdMatch = text.match(/(?:Hand|Game)\s*#\s*([A-Za-z0-9-]+)/i);
  if (ggIdMatch) id = `GG${ggIdMatch[1].replace(/[^A-Za-z0-9]/g, "")}`;
  const stakesMatch = text.match(/\(\$?([\d.]+\/\$?[\d.]+)[^)]*\)/);
  if (stakesMatch) stakes = stakesMatch[1].replace(/\$/g, "");
  else {
    const alt = text.match(/\$?(\d+(?:\.\d+)?)\/\$?(\d+(?:\.\d+)?)/);
    if (alt) stakes = `${alt[1]}/${alt[2]}`;
  }
  const dateMatch = text.match(/(\d{4}\/\d{2}\/\d{2}|\d{4}-\d{2}-\d{2})[^\n]*?(\d{1,2}:\d{2}:\d{2})?/);
  if (dateMatch) date = dateMatch[0].trim();
  else {
    const iso = text.match(/\d{4}-\d{2}-\d{2}/);
    if (iso) date = iso[0];
  }

  // Seats: "Seat 1: Hero ($100.00)" or "Seat 1: PlayerName ( $50 )"
  const seats: { name: string; chips: number }[] = [];
  for (const line of lines) {
    const seatMatch = line.match(/^Seat \d+:\s*(\S+)\s*\(\$?([\d,.]+)/i);
    if (seatMatch) seats.push({ name: seatMatch[1], chips: parseFloat(seatMatch[2].replace(/,/g, "")) });
  }

  // Hero detection: "Dealt to Hero [Ah Kd]" or "Hero shows [Ah Kd]" or "Your hand is As 5s"
  let hero = "";
  let heroCards = "";
  const dealtMatch = text.match(/Dealt to\s+(\S+)\s*\[([^\]]+)\]/i);
  if (dealtMatch) {
    hero = dealtMatch[1];
    heroCards = dealtMatch[2].trim();
  } else {
    const yourHand = text.match(/Your hand is\s*\[?([AKQJT98765432][shdc]\s+[AKQJT98765432][shdc])\]?/i);
    if (yourHand) {
      heroCards = yourHand[1].trim();
      hero = "Hero";
    } else {
      const shows = text.match(/(\S+)\s+shows\s*\[([^\]]+)\]/i);
      if (shows) {
        hero = shows[1];
        heroCards = shows[2].trim();
      } else if (seats.length > 0) hero = seats[0].name;
    }
  }
  // Also try "Hero [As 5s]" pattern
  if (!heroCards) {
    const bracketCards = text.match(/\[([AKQJT98765432][shdc]\s+[AKQJT98765432][shdc])\]/);
    if (bracketCards && !heroCards) {
      // only use if we have a hero
      if (hero) heroCards = bracketCards[1].trim();
    }
  }

  // Board detection: GGPoker uses "*** FLOP *** [Qh 7d 2c]" similar to Stars, but also "Flop: Qh 7d 2c" or "Board [Qh 7d 2c Kd 2h]"
  let flopBoard = "";
  let turnBoard = "";
  let riverBoard = "";
  let fullBoard = "";
  for (const line of lines) {
    if (/^\*\*\* FLOP/i.test(line) || /^Flop:/i.test(line) || /Flop\s+\[/i.test(line)) {
      const m = line.match(/\[([^\]]+)\]/);
      if (m) flopBoard = m[1].trim();
      else {
        const after = line.split(/Flop:?/i)[1];
        if (after) {
          const cards = after.match(/([AKQJT98765432][shdc])/gi);
          if (cards && cards.length >= 3) flopBoard = cards.slice(0, 3).join(" ");
        }
      }
    }
    if (/^\*\*\* TURN/i.test(line) || /^Turn:/i.test(line) || /Turn\s+\[/i.test(line)) {
      const all = [...line.matchAll(/\[([^\]]+)\]/g)].map((x) => x[1]);
      if (all.length >= 2) {
        turnBoard = all[all.length - 1].trim();
        fullBoard = all.join(" ").trim();
      } else if (all.length === 1) {
        // Could be "[Kd]" or "[Qh 7d 2c Kd]"
        const content = all[0].trim();
        const cards = content.split(/\s+/);
        if (cards.length === 1) turnBoard = content;
        else if (cards.length === 4) {
          flopBoard = cards.slice(0, 3).join(" ");
          turnBoard = cards[3];
          fullBoard = content;
        } else turnBoard = content;
      } else {
        const after = line.split(/Turn:?/i)[1];
        if (after) {
          const cards = after.match(/([AKQJT98765432][shdc])/gi);
          if (cards && cards.length >= 1) turnBoard = cards[cards.length - 1];
        }
      }
    }
    if (/^\*\*\* RIVER/i.test(line) || /^River:/i.test(line) || /River\s+\[/i.test(line)) {
      const all = [...line.matchAll(/\[([^\]]+)\]/g)].map((x) => x[1]);
      if (all.length >= 2) {
        riverBoard = all[all.length - 1].trim();
        fullBoard = all.join(" ").trim();
      } else if (all.length === 1) {
        const content = all[0].trim();
        const cards = content.split(/\s+/);
        if (cards.length === 1) riverBoard = content;
        else if (cards.length === 5) {
          flopBoard = cards.slice(0, 3).join(" ");
          turnBoard = cards[3];
          riverBoard = cards[4];
          fullBoard = content;
        } else riverBoard = content;
      } else {
        const after = line.split(/River:?/i)[1];
        if (after) {
          const cards = after.match(/([AKQJT98765432][shdc])/gi);
          if (cards && cards.length >= 1) riverBoard = cards[cards.length - 1];
        }
      }
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
    if (/^\*\*\* SUMMARY/i.test(line) || /^SUMMARY/i.test(line)) inSummary = true;
    if (/^\*\*\* HOLE CARDS/i.test(line) || /HOLE CARDS/i.test(line)) { currentStreet = "preflop"; continue; }
    if (/^\*\*\* FLOP/i.test(line) || /^Flop:/i.test(line)) { currentStreet = "flop"; continue; }
    if (/^\*\*\* TURN/i.test(line) || /^Turn:/i.test(line)) { currentStreet = "turn"; continue; }
    if (/^\*\*\* RIVER/i.test(line) || /^River:/i.test(line)) { currentStreet = "river"; continue; }
    if (line.startsWith("***")) continue;
    if (/^(PokerStars|GGPoker|Hand #|Game #|Table )/i.test(line) || /^Seat \d+:/i.test(line)) continue;
    if (/^Board \[/i.test(line)) continue;
    if (/Dealt to/i.test(line) || /Your hand is/i.test(line)) continue;
    if (inSummary) continue;
    if (/collected/i.test(line) || /Uncalled bet/i.test(line) || /Total pot/i.test(line) || /Pot:/i.test(line)) continue;
    const action = parseGGActionLine(line);
    if (action) {
      streets[currentStreet].push(action);
    } else {
      if (line.includes("posts") || line.includes("calls") || line.includes("raises") || line.includes("bets") || line.includes("folds") || line.includes("checks") || line.includes("all-in")) {
        const parts = line.split(/\s+/);
        if (parts.length >= 2) {
          const player = parts[0];
          const rest = parts.slice(1).join(" ");
          const fakeLine = `${player}: ${rest}`;
          const a2 = parseGGActionLine(fakeLine);
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
  // GGPoker: "Player wins $X" or "Player collected $X"
  const winsRe = /(\S+)\s+wins\s+\$?([\d,.]+)/gi;
  while ((m = winsRe.exec(text)) !== null) {
    const player = m[1].trim();
    if (player.toLowerCase() === "pot" || player.toLowerCase() === "side") continue;
    const amount = parseFloat(m[2].replace(/,/g, ""));
    if (!winners.find((w) => w.player === player)) winners.push({ player, amount });
  }

  const sidePots: number[] = [];
  const sideRe = /Side pot\s+\$?([\d,.]+)/gi;
  while ((m = sideRe.exec(text)) !== null) sidePots.push(parseFloat(m[1].replace(/,/g, "")));
  const mainPotRe = /Main pot\s+\$?([\d,.]+)/gi;
  while ((m = mainPotRe.exec(text)) !== null) sidePots.push(parseFloat(m[1].replace(/,/g, "")));

  const site: Site = "ggpoker";
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

export function isGGPokerFormat(text: string): boolean {
  return /GGPoker/i.test(text) || /Hand #\d+.*Hold'em/i.test(text) && !/PokerStars/i.test(text) || /Game #\d+/i.test(text);
}
