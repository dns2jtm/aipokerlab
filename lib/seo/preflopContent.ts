export type PositionKey = "utg" | "hj" | "co" | "btn" | "sb" | "bb";
export type StackKey = "20" | "40" | "100" | "200";

export const POSITION_LABELS: Record<PositionKey, string> = {
  utg: "UTG",
  hj: "HJ",
  co: "CO",
  btn: "BTN",
  sb: "SB",
  bb: "BB",
};

export const POSITION_FULL: Record<PositionKey, string> = {
  utg: "Under the Gun",
  hj: "Hijack",
  co: "Cutoff",
  btn: "Button",
  sb: "Small Blind",
  bb: "Big Blind",
};

export const STACK_LABELS: Record<StackKey, string> = {
  "20": "20bb",
  "40": "40bb",
  "100": "100bb",
  "200": "200bb",
};

export interface PreflopSeoContent {
  title: string;
  description: string;
  keywords: string[];
  h1: string;
  intro: string;
  strategy: string;
  tip: string;
  faq: { q: string; a: string }[];
}

const POS_INTROS: Record<PositionKey, string> = {
  utg: "Playing from Under the Gun is the tightest spot at a 6-max table — five players act after you, so every hand you open must be robust against 3-bets and multi-way pressure. GTO keeps UTG ranges narrow and value-heavy, especially deep-stacked.",
  hj: "The Hijack is the first step toward looser play — one fewer player behind than UTG, but still early enough that dominated hands cost you. GTO widens slightly here, adding suited broadways and stronger suited connectors while keeping offsuit junk out.",
  co: "The Cutoff is where GTO starts to open up. With only the Button and blinds behind, you can profitably raise a much wider range — suited aces, most suited connectors, and even some offsuit broadways become opens. Position is starting to pay.",
  btn: "The Button is the most profitable seat in poker — you act last postflop every hand. GTO exploits this by opening extremely wide, often 45–50% of hands at 100bb. If you are not stealing aggressively from the BTN, you are leaving money on the table.",
  sb: "The Small Blind is poker's trickiest preflop spot — you are out of position postflop and have already invested 0.5bb. GTO balances a tight open-raise range with selective 3-bets vs late opens, and folds a lot. Discipline here saves bb/100.",
  bb: "The Big Blind is a defensive position — you close the action preflop and get a discount to call. GTO defends wide vs small opens (especially from the BTN) but knows when to fold vs tight UTG ranges. Mastering BB defense is the fastest win-rate boost for most players.",
};

const STACK_INTROS: Record<StackKey, string> = {
  "20": "At 20bb you are in push/fold and short-stack territory — many hands become all-in or fold, and postflop play is shallow. GTO at 20bb is about maximizing fold equity and avoiding dominated calls. Rake matters less; raw equity matters more.",
  "40": "At 40bb you are in the mid-stack zone — deep enough for postflop play but shallow enough that implied odds are reduced. GTO tightens slightly vs 100bb, cutting speculative hands like small suited connectors that need deep stacks to realize equity.",
  "100": "At 100bb — the standard cash-game depth — GTO ranges are at their most balanced. You have full implied odds for suited connectors and small pairs, and 3-bet/4-bet dynamics are fully in play. This is the baseline every serious student should master first.",
  "200": "At 200bb you are deep-stacked — implied odds skyrocket, but so does the cost of dominated hands. GTO actually tightens from early position at 200bb (reverse implied odds hurt), while late position can still open wide. Postflop skill matters most here.",
};

const POS_STRATEGY: Record<PositionKey, string> = {
  utg: "From UTG, prioritize hands that play well multi-way and dominate typical calling ranges: big pairs, AK/AQ, and suited broadways. Fold hands like AJo and KQo more often than you think — they look pretty but bleed EV when dominated.",
  hj: "From the Hijack, you can add hands like AJs, KQs, and T9s to your open. Still fold the weakest offsuit aces (A6o–A9o) and most suited gappers — they do not realize enough equity from early position.",
  co: "From the Cutoff, open all suited aces, most suited kings, and connectors down to 76s. Offsuit broadways like KJo and QJo become profitable opens. Mix in a few 3-bets vs UTG/HJ opens with suited blockers.",
  btn: "From the Button, open any ace, any suited king, most suited connectors, and even hands like T8o and 97s. Your edge comes from position — you will outplay opponents postflop. Defend vs 3-bets by calling with suited hands that realize equity well.",
  sb: "From the Small Blind, keep your open-raise range tighter than the Button (you are OOP), but 3-bet aggressively vs CO/BTN opens — hands like A5s and K9s make great 3-bet bluffs with blocker value. Fold the bottom 40% without hesitation.",
  bb: "From the Big Blind, defend wide vs BTN/SB opens (call with any suited hand, most offsuit broadways, and pairs), but fold more vs UTG/HJ. Vs a 2.5x BTN open at 100bb, GTO defends ~55–60% — if you fold more, regs exploit you by opening 100%.",
};

const STACK_STRATEGY: Record<StackKey, string> = {
  "20": "Short-stack strategy: shove or fold with many hands — ATo+, KJs+, and pairs 66+ are often jams from late position. Limping is almost never GTO at 20bb. Study push/fold charts alongside these ranges.",
  "40": "Mid-stack strategy: you can still open-raise normally, but size down 3-bets and avoid calling 3-bets with speculative hands. Pairs and suited broadways go up in value; small suited connectors go down.",
  "100": "Standard-depth strategy: this is where GTO is most nuanced — balanced open, 3-bet, and call ranges. Study how frequencies shift by position, and drill the borderline hands (A5s, KJo, 77) until decisions are automatic.",
  "200": "Deep-stack strategy: prioritize hands that make nutted postflop hands — suited connectors, suited aces, and big pairs. Avoid dominated offsuit hands from early position; they lose huge pots when outkicked. Postflop edge matters more than preflop frequency.",
};

export function getPreflopSeoContent(pos: PositionKey, stack: StackKey): PreflopSeoContent {
  const posLabel = POSITION_LABELS[pos];
  const posFull = POSITION_FULL[pos];
  const stackLabel = STACK_LABELS[stack];
  const title = "GTO Preflop Chart " + posLabel + " " + stackLabel + " \u2014 AI Poker Lab";
  const h1 = "GTO Preflop Chart: " + posLabel + " (" + posFull + ") at " + stackLabel;
  const description =
    "Free GTO preflop chart for " + posLabel + " (" + posFull + ") at " + stackLabel + " \u2014 6-max, rake 5% cap $3. See raise/call/fold frequencies for all 169 hands, EV, and study tips. ToS-compliant training.";
  const keywords = [
    "gto preflop chart " + posLabel.toLowerCase() + " " + stackLabel,
    posLabel.toLowerCase() + " preflop range " + stackLabel,
    "gto " + posLabel.toLowerCase() + " range",
    "preflop chart " + stackLabel + " " + posLabel.toLowerCase(),
    "gto poker preflop " + posLabel.toLowerCase(),
    "6max preflop chart " + posLabel.toLowerCase(),
  ];

  const intro =
    POS_INTROS[pos] + " " + STACK_INTROS[stack] + " Below is the GTO range grid for " + posLabel + " at " + stackLabel + " (6-max, rake 5% cap $3) \u2014 green = raise, amber = call, red = fold. Hover any hand for exact frequencies and EV.";

  const strategy = POS_STRATEGY[pos] + " " + STACK_STRATEGY[stack];

  const tip =
    pos === "btn"
      ? "Pro tip: BTN is where most players leak the most EV by opening too tight. If your BTN VPIP is under 40% at 100bb, you are likely over-folding — drill this chart until 45%+ feels natural."
      : pos === "bb"
        ? "Pro tip: BB defense is the #1 leak for microstakes players. If you fold BB vs BTN more than 45% at 100bb, regs print money against you. Study which suited hands GTO calls and why."
        : pos === "utg"
          ? "Pro tip: UTG discipline is what separates winners from break-even regs. If you open wider than ~15% UTG at 100bb, you are likely bleeding EV — tighten up and watch your red line improve."
          : "Pro tip: Compare this chart to your actual VPIP from this position in your tracker. The gap between GTO and your play is your leak — Lab's leak detector quantifies it in bb/100.";

  const faq = [
    {
      q: "What is the GTO open-raise frequency for " + posLabel + " at " + stackLabel + "?",
      a:
        "GTO open-raise frequency for " + posLabel + " at " + stackLabel + " depends on rake and field, and our validated O(1) spotHash + Linear MCCFR chart (5% rake cap $3) shows the equilibrium raise/call/fold mix for all 169 hands. Hover the grid above for exact frequencies per hand. Generally, " + posLabel + " is " + (pos === "utg" ? "tightest (~15% at 100bb)" : pos === "btn" ? "widest (~48% at 100bb)" : pos === "bb" ? "defensive (call-heavy vs steals)" : "moderate") + " \u2014 see the grid for " + stackLabel + " specifics.",
    },
    {
      q: "How should I study this " + posLabel + " " + stackLabel + " chart?",
      a: "Use the 3-step method: (1) Quiz yourself \u2014 cover the grid and ask 'What does GTO do with AJo " + posLabel + " " + stackLabel + "?' (2) Check and note surprises. (3) Drill the borderline hands (the amber/mixed cells) with Lab's spaced-repetition drills. 10 minutes a day per position beats cramming.",
    },
    {
      q: "Is this chart accurate for my stakes?",
      a: "These ranges are solved for 6-max cash, 5% rake cap $3, which matches most micro-to-mid stakes online games. At very low stakes with high rake or vs extremely tight/loose opponents, exploitative adjustments beat pure GTO \u2014 but you need to know GTO first to know when to deviate. See our Methodology for solver details.",
    },
    {
      q: "Can I use this chart during live play?",
      a: "No. This chart is for post-hand study only. Using any solver chart or AI assistance during live play violates PokerStars and GGPoker Terms ofService and risks account bans and fund seizure. Study off-table, play your A-game on-table.",
    },
  ];

  return { title, description, keywords, h1, intro, strategy, tip, faq };
}

export const ALL_POSITIONS: PositionKey[] = ["utg", "hj", "co", "btn", "sb", "bb"];
export const ALL_STACKS: StackKey[] = ["20", "40", "100", "200"];
export const SITE_URL = "https://aipokerlab.com";
