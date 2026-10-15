"""
Preflop GTO range database for 6-max cash (100bb) and common tournament spots.

Strategy encoding per hand: a string of action codes in priority order.
Actions: r = raise (open/3bet), c = call, l = limp (rare), f = fold.
Mixed frequencies are supported: "r80/c20" means raise 80%, call 20%.
"""

# ---------------------------------------------------------------------------
# Hand notation helpers
# ---------------------------------------------------------------------------

RANKS = "AKQJT98765432"


def all_hands():
    """Yield all 169 starting hands in standard notation (AKs, AKo, AA...)."""
    hands = []
    for i, r1 in enumerate(RANKS):
        for r2 in RANKS[i:]:
            if r1 == r2:
                hands.append(r1 + r2)
            else:
                # r1 is the higher rank here (r2 comes later in RANKS)
                hands.append(r1 + r2 + "s")
                hands.append(r1 + r2 + "o")
    return hands


def normalize_hand(h):
    """Normalize user input like 'as' 'Kd' 'aK' 'AhKd' 'Ah Kd' into canonical 'AKs'/'AKo'/'AA'."""
    if not isinstance(h, str):
        return None
    compact = h.replace(" ", "").strip()
    if len(compact) == 4:
        r1, s1, r2, s2 = compact[0].upper(), compact[1].lower(), compact[2].upper(), compact[3].lower()
        if r1 in RANKS and r2 in RANKS and s1 in "shdc" and s2 in "shdc":
            if r1 == r2 and s1 == s2:
                return None  # Duplicate identical card
            if r1 == r2:
                return r1 + r2
            suited = "s" if s1 == s2 else "o"
            if RANKS.index(r1) < RANKS.index(r2):
                return r1 + r2 + suited
            return r2 + r1 + suited
        return None

    h = compact.upper()
    if len(h) == 2:
        r1, r2 = h
        if r1 not in RANKS or r2 not in RANKS:
            return None
        if r1 == r2:
            return h
        if RANKS.index(r1) < RANKS.index(r2):
            return r1 + r2 + "s"
        return r2 + r1 + "o"
    if len(h) == 3 and h[2] in ("S", "O"):
        r1, r2, suited = h[0], h[1], h[2].lower()
        if r1 not in RANKS or r2 not in RANKS or r1 == r2:
            return None
        if RANKS.index(r1) < RANKS.index(r2):
            return r1 + r2 + suited
        return r2 + r1 + suited
    return None


# ---------------------------------------------------------------------------
# Range construction DSL
# ---------------------------------------------------------------------------

def _expand(spec):
    """Expand a shorthand spec like '77+', 'A2s+', 'KTo+', 'T9s' into hands."""
    return _clean(spec)


def _expand_pair_range(lo, hi):
    """Expand '22-JJ' or 'JJ-22' style pair ranges (inclusive)."""
    i_a, i_b = RANKS.index(lo), RANKS.index(hi)
    start, end = min(i_a, i_b), max(i_a, i_b)
    return {r + r for r in RANKS[start : end + 1]}


def _clean(spec):
    """Expand a range spec string into a set of hands.

    Supports: single hands (AKs, JJ, T9o), plus-ranges (77+, A5s+, KTo+),
    and dash ranges for pairs (22-JJ, 99-66) and suited/offsuit hands (A2s-A5s, ATo-AQo).
    """
    out = set()
    for token in spec.replace("\n", " ").replace(",", " ").split():
        token = token.strip().rstrip(",")
        if not token:
            continue
        # Dash range for pairs (e.g. 22-JJ, 99-66) or suited/offsuit hands (e.g. A2s-A5s, ATo-AQo)
        if "-" in token and len(token.split("-")) == 2:
            a, b = token.split("-")
            a_up, b_up = a.upper(), b.upper()
            if (
                len(a_up) == 2 and len(b_up) == 2
                and a_up[0] == a_up[1] and b_up[0] == b_up[1]
                and a_up[0] in RANKS and b_up[0] in RANKS
            ):
                out |= _expand_pair_range(a_up[0], b_up[0])
                continue
            if (
                len(a) == 3 and len(b) == 3
                and a_up[0] == b_up[0]
                and a[2].lower() == b[2].lower() and a[2].lower() in "so"
                and a_up[0] in RANKS and a_up[1] in RANKS and b_up[1] in RANKS
            ):
                hi_rank = a_up[0]
                s_char = a[2].lower()
                i_hi = RANKS.index(hi_rank)
                i_1 = RANKS.index(a_up[1])
                i_2 = RANKS.index(b_up[1])
                start, end = min(i_1, i_2), max(i_1, i_2)
                for idx in range(start, end + 1):
                    if idx == i_hi:
                        continue
                    r_other = RANKS[idx]
                    n = normalize_hand(hi_rank + r_other + s_char)
                    if n:
                        out.add(n)
                continue
        plus = token.endswith("+")
        base = token[:-1] if plus else token
        if plus:
            base_up = base.upper()
            if len(base_up) == 2 and base_up[0] == base_up[1] and base_up[0] in RANKS:
                start = RANKS.index(base_up[0])
                out.update(r + r for r in RANKS[: start + 1])
            elif len(base) == 3 and base[2].lower() in "so" and base_up[0] in RANKS and base_up[1] in RANKS:
                hi, lo, s = base_up[0], base_up[1], base[2].lower()
                i_hi, i_lo = RANKS.index(hi), RANKS.index(lo)
                if i_hi > i_lo:
                    hi, lo = lo, hi
                    i_hi, i_lo = i_lo, i_hi
                for r in RANKS[i_hi + 1 : i_lo + 1]:
                    out.add(hi + r + s)
            elif len(base_up) == 2 and base_up[0] != base_up[1] and base_up[0] in RANKS and base_up[1] in RANKS:
                hi, lo = base_up[0], base_up[1]
                i_hi, i_lo = RANKS.index(hi), RANKS.index(lo)
                if i_hi > i_lo:
                    hi, lo = lo, hi
                    i_hi, i_lo = i_lo, i_hi
                for r in RANKS[i_hi + 1 : i_lo + 1]:
                    out.add(hi + r + "o")
        else:
            n = normalize_hand(base)
            if n:
                out.add(n)
    return out


def _range(*specs):
    s = set()
    for spec in specs:
        s |= _clean(spec)
    return s


# ---------------------------------------------------------------------------
# 6-max 100bb cash ranges (approximate GTO / modern solver output)
# ---------------------------------------------------------------------------

OPEN_RANGES = {
    "UTG": _range(
        "22+ A2s+ K9s+ Q9s+ J9s+ T9s 98s 87s 76s 65s 54s ATo+ KTo+ QJo",
    ),
    "MP": _range(
        "22+ A2s+ K8s+ Q8s+ J8s+ T8s+ 98s 87s 76s 65s 54s A9o+ KTo+ QTo+ JTo",
    ),
    "CO": _range(
        "22+ A2s+ K5s+ Q6s+ J6s+ T6s+ 96s+ 86s+ 75s+ 64s+ 53s+ 43s A2o+ K8o+ Q9o+ J9o+ T9o 98o",
    ),
    "BTN": _range(
        "22+ A2s+ K2s+ Q3s+ J4s+ T5s+ 95s+ 84s+ 74s+ 63s+ 53s 42s 32s A2o+ K5o+ Q7o+ J8o+ T8o+ 98o 87o 76o 65o",
    ),
    "SB": _range(
        "22+ A2s+ K2s+ Q4s+ J5s+ T5s+ 95s+ 84s+ 74s+ 64s+ 53s 43s A2o+ K7o+ Q8o+ J8o+ T8o+ 97o+ 87o 76o 65o 54o",
    ),
}

# Facing a single raise: 3bet / call ranges by position matchup (vs open from X)
# Key: (our_pos, vs_pos) -> {"3b": set, "call": set}
THREEBET = {
    ("MP", "UTG"): {"3b": _range("QQ+ AKs A5s A4s AKo"), "call": _range("22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s AQo")},
    ("CO", "UTG"): {"3b": _range("QQ+ AKs A5s A4s AKo"), "call": _range("22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s AQo AJo")},
    ("CO", "MP"): {"3b": _range("TT+ AQs+ A5s A4s AKo AQo"), "call": _range("22-99 AJs ATs A9s KQs KJs QJs JTs T9s 98s 87s 76s AJo ATo KQo")},
    ("BTN", "UTG"): {"3b": _range("TT+ AQs+ A5s A4s AKo AQo"), "call": _range("22-99 AJs ATs A9s A8s KQs KJs QJs JTs T9s 98s 87s 76s AJo ATo KQo")},
    ("BTN", "MP"): {"3b": _range("99+ AJs+ ATs A5s A4s A3s AKo AQo"), "call": _range("22-88 AJo ATo A9s A8s A7s KQs KJs QJs JTs T9s 98s 87s 76s KQo QJo")},
    ("BTN", "CO"): {"3b": _range("88+ ATs+ A9s A5s A4s A3s KQs AKo AQo AJo"), "call": _range("22-77 A9s A8s A7s A6s A5s KJs KTs QJs QTs JTs T9s 98s 87s 76s ATo A9o KQo KJo QJo")},
    ("SB", "UTG"): {"3b": _range("QQ+ AKs A5s A4s AKo"), "call": _range("22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s AQo")},
    ("SB", "MP"): {"3b": _range("TT+ AQs+ A5s A4s AKo AQo"), "call": _range("22-99 AJs ATs A9s KQs KJs QJs JTs T9s 98s 87s AQo AJo")},
    ("SB", "CO"): {"3b": _range("99+ AJs+ ATs A5s A4s A3s AKo AQo AJo"), "call": _range("22-88 AJs ATs A9s A8s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s AQo ATo KQo")},
    ("SB", "BTN"): {"3b": _range("99+ AJs+ ATs A9s A5s A4s A3s KQs KJs AKo AQo AJo ATo"), "call": _range("22-88 AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s KQs KJs KTs K9s K8s K7s QJs QTs Q9s Q8s JTs J9s J8s T9s T8s 98s 97s 87s 86s 76s 75s 65s 64s 54s AQo AJo ATo A9o A8o A7o A5o KQo KJo KTo QJo QTo JTo J9o T9o 98o 87o 76o 65o 54o")},
    ("BB", "UTG"): {"3b": _range("QQ+ AKs A5s A4s AKo"), "call": _range("22-JJ AJs ATs A9s A8s A7s A5s A4s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s AQo AJo ATo")},
    ("BB", "MP"): {"3b": _range("TT+ AQs+ A5s A4s AKo AQo"), "call": _range("22-99 AJs ATs A9s A8s A7s A6s A5s A4s A3s KQs KJs KTs K9s QJs QTs JTs T9s 98s 87s 76s 65s 54s AQo AJo ATo KQo")},
    ("BB", "CO"): {"3b": _range("99+ AJs+ ATs A9s A5s A4s A3s KQs AKo AQo AJo"), "call": _range("22-88 AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s KQs KJs KTs K9s K8s QJs QTs Q9s JTs J9s T9s 98s 87s 76s 65s 54s AQo ATo A9o AJo KQo KJo QJo JTo")},
    ("BB", "BTN"): {"3b": _range("88+ ATs+ A9s A8s A5s A4s A3s KQs KJs AKo AQo AJo ATo"), "call": _range("22-77 A9s A8s A7s A6s A5s A4s A3s A2s KQs KJs KTs K9s K8s K7s K6s K5s QJs QTs Q9s Q8s JTs J9s J8s T9s T8s 98s 97s 87s 86s 76s 75s 65s 64s 54s AQo A9o A8o A7o A5o KQo KJo KTo QJo QTo JTo J9o T9o 98o 87o 76o 65o")},
    ("BB", "SB"): {"3b": _range("77+ A9s+ A5s A4s KQs KJs KTs AKo AQo AJo ATo A9o"), "call": _range("22-66 A9s A8s A7s A6s A5s A4s A3s A2s KQs KJs KTs K9s K8s K7s K6s K5s K4s QJs QTs Q9s Q8s Q7s Q6s Q5s JTs J9s J8s J7s T9s T8s T7s 98s 97s 96s 87s 86s 76s 75s 65s 64s 54s 53s AQo A9o A8o A7o A6o A5o A4o A3o KQo KJo KTo K9o QJo QTo Q9o JTo J9o T9o T8o 98o 97o 87o 86o 76o 75o 65o 54o")},
}

# Facing an open + 1 caller (Squeeze spots): 3-bet squeeze (~4x-5x) or overcall
# Key: (our_pos, vs_opener_pos) -> {"squeeze": set, "call": set}
SQUEEZE_RANGES = {
    ("CO", "UTG"): {"squeeze": _range("QQ+ AKs A5s AKo"), "call": _range("66-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s")},
    ("BTN", "UTG"): {"squeeze": _range("JJ+ AQs+ A5s A4s AKo AQo"), "call": _range("22-TT AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s")},
    ("BTN", "MP"): {"squeeze": _range("TT+ AJs+ A5s A4s KQs AKo AQo"), "call": _range("22-99 ATs A9s KJs QJs JTs T9s 98s 87s 76s 65s")},
    ("SB", "UTG"): {"squeeze": _range("QQ+ AKs A5s AKo"), "call": _range("88-JJ AQs AJs KQs QJs JTs")},
    ("SB", "MP"): {"squeeze": _range("JJ+ AQs+ A5s A4s AKo AQo"), "call": _range("77-TT AJs ATs KQs KJs QJs JTs")},
    ("SB", "CO"): {"squeeze": _range("TT+ AJs+ ATs A5s A4s KQs AKo AQo"), "call": _range("66-99 ATs A9s KJs QJs JTs T9s")},
    ("BB", "UTG"): {"squeeze": _range("QQ+ AKs A5s A4s AKo"), "call": _range("22-JJ AQs AJs ATs A9s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s AQo")},
    ("BB", "MP"): {"squeeze": _range("JJ+ AQs+ A5s A4s AKo AQo"), "call": _range("22-TT AJs ATs A9s A8s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s AJo KQo")},
    ("BB", "CO"): {"squeeze": _range("TT+ AJs+ ATs A5s A4s A3s KQs AKo AQo"), "call": _range("22-99 ATs A9s A8s A7s A6s KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s AJo ATo KQo QJo")},
    ("BB", "BTN"): {"squeeze": _range("99+ ATs+ A5s A4s A3s KQs KJs AKo AQo AJo"), "call": _range("22-88 A9s A8s A7s A6s A2s KTs K9s QJs QTs Q9s JTs J9s T9s T8s 98s 87s 76s 65s 54s ATo KQo KJo QJo JTo")},
}

# Default fallback squeeze sets by hero position when opener is unspecified or non-standard
SQUEEZE_BY_POS = {
    "MP": {"squeeze": _range("QQ+ AKs A5s AKo"), "call": _range("77-JJ AQs AJs KQs QJs JTs")},
    "CO": {"squeeze": _range("QQ+ AKs A5s AKo"), "call": _range("66-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s")},
    "BTN": {"squeeze": _range("TT+ AJs+ A5s A4s KQs AKo AQo"), "call": _range("22-99 ATs A9s KJs QJs JTs T9s 98s 87s 76s 65s")},
    "SB": {"squeeze": _range("TT+ AJs+ A5s A4s KQs AKo AQo"), "call": _range("66-99 ATs A9s KJs QJs JTs T9s")},
    "BB": {"squeeze": _range("TT+ AJs+ ATs A5s A4s A3s KQs AKo AQo"), "call": _range("22-99 ATs A9s A8s A7s KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s AJo ATo KQo")},
}

# Iso-raise vs limper(s) ranges by hero position: {"iso": set, "limp": set}
ISO_RAISE_BY_POS = {
    "MP": {
        "iso": _range("77+ ATs+ KJs+ QJs AJo+ KQo"),
        "limp": _range("22-66 A9s-A2s KTs QTs JTs T9s 98s 87s 76s 65s"),
    },
    "CO": {
        "iso": _range("66+ A8s+ A5s A4s KTs+ QTs+ JTs T9s ATo+ KJo+ QJo"),
        "limp": _range("22-55 A7s-A2s K9s Q9s J9s 98s 87s 76s 65s 54s"),
    },
    "BTN": {
        "iso": _range("55+ A2s+ K9s+ Q9s+ J9s+ T8s+ 98s 87s 76s A9o+ KTo+ QTo+ JTo"),
        "limp": _range("22-44 K8s-K5s Q8s J8s T7s 97s 86s 75s 65s 54s"),
    },
    "SB": {
        "iso": _range("77+ A9s+ A5s KTs+ QTs+ JTs ATo+ KJo+"),
        "limp": _range("22-66 A8s-A2s K9s-K6s Q9s J9s T9s 98s 87s 76s 65s 54s QJo JTo"),
    },
    "BB": {
        "iso": _range("88+ ATs+ A5s KJs+ QJs AJo+ KQo"),
        "limp": _range("22-77 A9s-A2s KTs-K2s QTs-Q2s JTs-J4s T9s-T6s 98s-96s 87s-85s 76s-75s 65s 54s ATo-A2o KJo-K5o QJo-Q7o JTo-J8o T9o 98o 87o"),
    },
}

ISO_RAISE_RANGES = dict(ISO_RAISE_BY_POS)

# Facing a 3bet when we opened (defend ranges)
FACING_3BET = {
    "UTG": {"4b": _range("QQ+ AKs AKo"), "call": _range("22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s AQo")},
    "MP": {"4b": _range("QQ+ AKs A5s A4s AKo"), "call": _range("22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s AQo")},
    "CO": {"4b": _range("JJ+ AQs+ A5s A4s AKo AQo"), "call": _range("22-TT AJs ATs A9s KQs KJs QJs JTs T9s 98s 87s 76s AQo AJo")},
    "BTN": {"4b": _range("TT+ AJs+ ATs A5s A4s A3s AKo AQo AJo"), "call": _range("22-99 ATs A9s A8s A7s A6s A5s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s AQo AJo ATo KQo")},
    "SB": {"4b": _range("TT+ AJs+ A5s A4s AKo AQo"), "call": _range("22-99 ATs A9s A8s A7s A6s A5s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s AQo AJo ATo KQo")},
}

# Facing a 4bet (when we 3bet and got 4bet): 5bet shove or call, else fold.
# Includes both default "5b"/"call" keys and position-aware overrides.
FACING_4BET_BY_POS = {
    "UTG": {"5b": _range("KK+ AKs"), "call": _range("QQ JJ AQs AKo")},
    "MP": {"5b": _range("QQ+ AKs AKo"), "call": _range("TT-JJ AQs AJs KQs")},
    "CO": {"5b": _range("QQ+ AKs A5s AKo"), "call": _range("88-JJ AQs AJs ATs KQs")},
    "BTN": {"5b": _range("QQ+ AKs A5s A4s AKo"), "call": _range("22-JJ AQs AJs ATs KQs")},
    "SB": {"5b": _range("QQ+ AKs A5s AKo"), "call": _range("77-JJ AQs AJs ATs KQs")},
    "BB": {"5b": _range("QQ+ AKs AKo"), "call": _range("22-JJ AQs AJs ATs KQs")},
}

FACING_4BET = {
    "5b": _range("QQ+ AKs AKo"),
    "call": _range("22-JJ AQs AJs ATs KQs"),
    **FACING_4BET_BY_POS,
}

# Big blind defense vs BTN open (heads-up postflop spot, simplified)
BB_VS_BTN_OPEN_CALL = _range(
    "22+ A2s+ K2s+ Q2s+ J4s+ T6s+ 96s+ 85s+ 75s+ 64s+ 53s+ 43s A2o+ K5o+ Q7o+ J8o+ T8o+ 97o+ 87o 76o 65o 54o"
)

# ---------------------------------------------------------------------------
# Lookup API
# ---------------------------------------------------------------------------

POSITIONS_6MAX = ["UTG", "MP", "CO", "BTN", "SB", "BB"]


def _freq(hand, rset):
    return 1.0 if hand in rset else 0.0


def _get_open_set(pos):
    if pos in OPEN_RANGES:
        return OPEN_RANGES[pos]
    if pos == "BB":
        return ISO_RAISE_BY_POS["BB"]["iso"]
    return None


def open_advice(pos, hand):
    """Return (action, detail) for opening from pos."""
    rng = _get_open_set(pos)
    if rng is None:
        return None
    if hand in rng:
        return ("RAISE", "Open raise ~2.2-2.5bb" if pos != "BB" else "Iso-raise / value raise from BB")
    if pos == "BB":
        return ("CALL", "Check option in BB")
    return ("FOLD", "Not in open range")


_FACING_OPEN_FALLBACK_VS = {
    "UTG": ("MP", "UTG"),
    "MP": ("MP", "UTG"),
    "CO": ("CO", "MP"),
    "BTN": ("BTN", "CO"),
    "SB": ("SB", "BTN"),
    "BB": ("BB", "BTN"),
}


def _get_facing_open_sets(pos, vs_pos=None):
    if pos not in POSITIONS_6MAX:
        return None
    if vs_pos and vs_pos not in POSITIONS_6MAX:
        return None
    key = (pos, vs_pos)
    if key in THREEBET:
        return THREEBET[key]
    fb_key = _FACING_OPEN_FALLBACK_VS.get(pos)
    if fb_key and fb_key in THREEBET:
        return THREEBET[fb_key]
    return None


def facing_open_advice(pos, vs_pos, hand):
    """Return (action, detail) facing a single open from vs_pos."""
    r = _get_facing_open_sets(pos, vs_pos)
    if r is None:
        return None
    if hand in r["3b"]:
        return ("3-BET", "3bet to ~3x open (IP) / ~4x (OOP)")
    if hand in r["call"]:
        return ("CALL", "Call the open")
    return ("FOLD", "Not in defend range")


def _get_squeeze_sets(pos, vs_pos=None):
    if pos not in POSITIONS_6MAX:
        return None
    if vs_pos and (pos, vs_pos) in SQUEEZE_RANGES:
        return SQUEEZE_RANGES[(pos, vs_pos)]
    if pos in SQUEEZE_BY_POS:
        return SQUEEZE_BY_POS[pos]
    if pos == "UTG":
        return SQUEEZE_BY_POS["MP"]
    return None


def squeeze_advice(pos, vs_pos, hand):
    """Return (action, detail) when facing an open raise and a caller (squeeze spot)."""
    r = _get_squeeze_sets(pos, vs_pos)
    if r is None:
        return None
    if hand in r["squeeze"]:
        return ("SQUEEZE", "Squeeze 3-bet to ~4x–5x open")
    if hand in r["call"]:
        return ("CALL", "Overcall multiway (high playability)")
    return ("FOLD", "Not in squeeze or overcall range")


def _get_iso_raise_sets(pos, vs_pos=None):
    if pos not in POSITIONS_6MAX:
        return None
    if pos in ISO_RAISE_BY_POS:
        return ISO_RAISE_BY_POS[pos]
    if pos == "UTG":
        return ISO_RAISE_BY_POS["MP"]
    return None


def iso_raise_advice(pos, vs_pos, hand=None):
    """Return (action, detail) when facing one or more limpers (iso-raise spot)."""
    if hand is None:
        target_hand = vs_pos
        vs = None
    else:
        target_hand = hand
        vs = vs_pos
    r = _get_iso_raise_sets(pos, vs)
    if r is None:
        return None
    if target_hand in r["iso"]:
        return ("RAISE", "Iso-raise vs limper to ~4bb (IP) / ~5bb (OOP)")
    if target_hand in r["limp"]:
        if pos == "BB":
            return ("CALL", "Check option in BB vs limper")
        return ("CALL", "Overlimp behind (speculative multiway hand)")
    return ("FOLD", "Fold vs limper")


def _get_facing_3bet_sets(pos):
    if pos not in POSITIONS_6MAX:
        return None
    if pos in FACING_3BET:
        return FACING_3BET[pos]
    if pos == "BB":
        return FACING_3BET["SB"]
    return None


def facing_3bet_advice(pos, hand):
    r = _get_facing_3bet_sets(pos)
    if r is None:
        return None
    if hand in r["4b"]:
        return ("4-BET", "4bet to ~2.2x the 3bet")
    if hand in r["call"]:
        return ("CALL", "Call the 3bet")
    return ("FOLD", "Not in defend range")


def _get_facing_4bet_sets(pos=None):
    """Return {'5b': set, 'call': set} for a given position, or default if pos is None."""
    if pos and isinstance(FACING_4BET.get(pos), dict):
        return FACING_4BET[pos]
    return {"5b": FACING_4BET["5b"], "call": FACING_4BET["call"]}


def facing_4bet_advice(hand_or_pos, hand=None):
    """Return (action, detail) when facing a 4-bet.

    Supports both `facing_4bet_advice(hand)` and `facing_4bet_advice(pos, hand)`.
    """
    if hand is None:
        pos = None
        target_hand = hand_or_pos
    else:
        pos = hand_or_pos
        target_hand = hand
        if pos and pos not in POSITIONS_6MAX:
            return None
    r = _get_facing_4bet_sets(pos)
    if target_hand in r["5b"]:
        return ("5-BET/SHOVE", "GTO shove range")
    if target_hand in r["call"]:
        return ("CALL", "Call the 4bet (careful with stack depth)")
    return ("FOLD", "Not in defend range")


def get_range_for_display(spot):
    """Return a set of hands for grid display given a spot dict."""
    kind = spot.get("kind")
    if kind == "open":
        return _get_open_set(spot.get("pos")) or set()
    if kind == "facing_open":
        r = _get_facing_open_sets(spot.get("pos"), spot.get("vs"))
        if r:
            return r["3b"] | r["call"]
    if kind == "facing_3bet":
        r = _get_facing_3bet_sets(spot.get("pos"))
        if r:
            return r["4b"] | r["call"]
    if kind == "squeeze":
        r = _get_squeeze_sets(spot.get("pos"), spot.get("vs"))
        if r:
            return r["squeeze"] | r["call"]
    if kind == "iso_raise":
        r = _get_iso_raise_sets(spot.get("pos"), spot.get("vs"))
        if r:
            return r["iso"] | r["limp"]
    if kind == "facing_4bet":
        pos = spot.get("pos")
        if pos and pos not in POSITIONS_6MAX:
            return set()
        r = _get_facing_4bet_sets(pos)
        return r["5b"] | r["call"]
    return set()


def get_action_sets(spot):
    """Return dict action->set for color-coded grid display."""
    kind = spot.get("kind")
    if kind == "open":
        return {"RAISE": _get_open_set(spot.get("pos")) or set()}
    if kind == "facing_open":
        r = _get_facing_open_sets(spot.get("pos"), spot.get("vs")) or {}
        return {"3-BET": r.get("3b", set()), "CALL": r.get("call", set())}
    if kind == "squeeze":
        r = _get_squeeze_sets(spot.get("pos"), spot.get("vs")) or {}
        return {"3-BET": r.get("squeeze", set()), "CALL": r.get("call", set())}
    if kind == "iso_raise":
        r = _get_iso_raise_sets(spot.get("pos"), spot.get("vs")) or {}
        return {"RAISE": r.get("iso", set()), "CALL": r.get("limp", set())}
    if kind == "facing_3bet":
        r = _get_facing_3bet_sets(spot.get("pos")) or {}
        return {"4-BET": r.get("4b", set()), "CALL": r.get("call", set())}
    if kind == "facing_4bet":
        pos = spot.get("pos")
        if pos and pos not in POSITIONS_6MAX:
            return {"5-BET": set(), "CALL": set()}
        r = _get_facing_4bet_sets(pos)
        return {"5-BET": r["5b"], "CALL": r["call"]}
    return {}


def advise(spot, hand):
    """Main entry: spot is dict with kind/pos/vs, hand is canonical notation."""
    kind = spot.get("kind")
    if kind == "open":
        return open_advice(spot.get("pos"), hand)
    if kind == "facing_open":
        return facing_open_advice(spot.get("pos"), spot.get("vs"), hand)
    if kind == "squeeze":
        return squeeze_advice(spot.get("pos"), spot.get("vs"), hand)
    if kind == "iso_raise":
        return iso_raise_advice(spot.get("pos"), spot.get("vs"), hand)
    if kind == "facing_3bet":
        return facing_3bet_advice(spot.get("pos"), hand)
    if kind == "facing_4bet":
        pos = spot.get("pos")
        return facing_4bet_advice(pos, hand) if pos else facing_4bet_advice(hand)
    return None


# Solver-calibrated borderline mixed open frequencies (raise_pct, fold_pct)
_BORDERLINE_OPEN = {
    "UTG": {
        "54s": (60, 40), "65s": (75, 25), "76s": (85, 15), "87s": (90, 10),
        "K9s": (70, 30), "Q9s": (65, 35), "J9s": (70, 30), "A2s": (80, 20), "A3s": (85, 15),
        "ATo": (65, 35), "KTo": (55, 45), "QJo": (50, 50),
        "22": (50, 50), "33": (65, 35), "44": (80, 20),
    },
    "MP": {
        "54s": (70, 30), "65s": (85, 15), "K8s": (65, 35), "Q8s": (60, 40), "J8s": (65, 35), "T8s": (75, 25),
        "A9o": (60, 40), "KTo": (80, 20), "QTo": (65, 35), "JTo": (60, 40),
        "22": (65, 35), "33": (80, 20),
    },
    "CO": {
        "43s": (60, 40), "53s": (70, 30), "64s": (80, 20), "75s": (85, 15),
        "K5s": (70, 30), "Q6s": (70, 30), "J6s": (65, 35), "T6s": (65, 35), "96s": (70, 30), "86s": (75, 25),
        "A2o": (55, 45), "A3o": (65, 35), "A4o": (75, 25), "A5o": (85, 15),
        "98o": (60, 40), "T9o": (75, 25), "J9o": (70, 30), "K8o": (55, 45), "Q9o": (65, 35),
    },
    "BTN": {
        "32s": (55, 45), "42s": (60, 40), "53s": (85, 15), "63s": (75, 25), "74s": (75, 25), "84s": (70, 30),
        "Q3s": (70, 30), "J4s": (70, 30), "T5s": (75, 25), "95s": (80, 20),
        "65o": (60, 40), "76o": (70, 30), "87o": (80, 20), "T8o": (75, 25), "J8o": (75, 25),
        "K5o": (65, 35), "K6o": (80, 20), "Q7o": (60, 40),
    },
    "SB": {
        "43s": (65, 35), "53s": (75, 25), "64s": (80, 20), "74s": (70, 30), "84s": (65, 35),
        "Q4s": (70, 30), "J5s": (70, 30), "T5s": (75, 25), "95s": (75, 25),
        "54o": (55, 45), "65o": (65, 35), "76o": (75, 25), "87o": (85, 15),
        "97o": (60, 40), "T8o": (75, 25), "J8o": (75, 25), "Q8o": (75, 25), "K7o": (65, 35),
    },
}

# Solver-calibrated mixed frequencies for facing_open: hand -> (3bet_pct, call_pct, fold_pct)
_MIXED_FACING_OPEN = {
    "JJ": (70, 30, 0),
    "TT": (65, 35, 0),
    "99": (55, 45, 0),
    "88": (50, 50, 0),
    "AQs": (75, 25, 0),
    "AJs": (65, 35, 0),
    "ATs": (60, 40, 0),
    "A9s": (50, 50, 0),
    "A5s": (75, 15, 10),
    "A4s": (70, 15, 15),
    "A3s": (60, 25, 15),
    "KQs": (65, 35, 0),
    "KJs": (55, 45, 0),
    "KTs": (45, 55, 0),
    "QJs": (45, 55, 0),
    "JTs": (40, 60, 0),
    "T9s": (35, 65, 0),
    "98s": (30, 70, 0),
    "87s": (25, 75, 0),
    "76s": (25, 75, 0),
    "AQo": (70, 30, 0),
    "AJo": (55, 30, 15),
    "ATo": (50, 25, 25),
    "KQo": (50, 35, 15),
}

# Solver-calibrated mixed frequencies for facing_3bet: hand -> (4bet_pct, call_pct, fold_pct)
_MIXED_FACING_3BET = {
    "QQ": (75, 25, 0),
    "JJ": (55, 45, 0),
    "TT": (45, 55, 0),
    "AQs": (65, 35, 0),
    "AJs": (50, 50, 0),
    "ATs": (40, 60, 0),
    "A5s": (75, 10, 15),
    "A4s": (70, 10, 20),
    "A3s": (60, 15, 25),
    "KQs": (35, 65, 0),
    "AQo": (65, 15, 20),
    "AJo": (55, 15, 30),
}

# Solver-calibrated mixed frequencies for facing_4bet: hand -> (5bet_pct, call_pct, fold_pct)
_MIXED_FACING_4BET = {
    "QQ": (70, 30, 0),
    "JJ": (25, 75, 0),
    "TT": (15, 70, 15),
    "AQs": (30, 70, 0),
    "A5s": (80, 0, 20),
    "A4s": (70, 0, 30),
    "AKo": (75, 25, 0),
}


def get_mixed_frequencies(spot: dict, hand: str) -> dict:
    """
    Return mixed-strategy action frequencies (summing to 100) for a given spot and canonical hand.
    Hands present in both aggressive and passive sets (e.g. 3b & call, or 4b & call) or
    borderline range hands receive realistic GTO mixed percentages.
    """
    norm = normalize_hand(hand) if hand else None
    h = norm or hand
    if not spot or not h:
        return {"FOLD": 100}

    kind = spot.get("kind")
    pos = spot.get("pos")
    vs_pos = spot.get("vs")

    if kind == "open":
        rng = _get_open_set(pos) or set()
        if h in rng:
            border = _BORDERLINE_OPEN.get(pos, {}).get(h)
            if border:
                return {"RAISE": border[0], "FOLD": border[1]}
            return {"RAISE": 100}
        return {"FOLD": 100}

    if kind == "facing_open":
        r = _get_facing_open_sets(pos, vs_pos)
        if not r:
            return {"FOLD": 100}
        in_3b = h in r["3b"]
        in_call = h in r["call"]
        if in_3b and in_call:
            mix = _MIXED_FACING_OPEN.get(h)
            if mix and mix[0] + mix[1] > 0:
                total_play = mix[0] + mix[1]
                p3 = int(round(mix[0] * 100 / total_play))
                return {"3-BET": p3, "CALL": 100 - p3}
            return {"3-BET": 65, "CALL": 35}
        if in_3b:
            if h in ("A5s", "A4s", "A3s", "KJs", "ATo", "A9o"):
                return {"3-BET": 75, "FOLD": 25}
            if h in _MIXED_FACING_OPEN and h not in ("AA", "KK", "QQ", "AKs", "AKo"):
                p3, pc, pf = _MIXED_FACING_OPEN[h]
                if pf > 0:
                    return {"3-BET": p3 + pc, "FOLD": pf}
            return {"3-BET": 100}
        if in_call:
            if h in ("22", "33", "44", "54s", "65s", "A9o", "KJo", "QJo", "JTo"):
                return {"CALL": 75, "FOLD": 25}
            return {"CALL": 100}
        return {"FOLD": 100}

    if kind == "squeeze":
        r = _get_squeeze_sets(pos, vs_pos)
        if not r:
            return {"FOLD": 100}
        in_sqz = h in r["squeeze"]
        in_call = h in r["call"]
        if in_sqz and in_call:
            return {"SQUEEZE": 65, "CALL": 35}
        if in_sqz:
            if h in ("A5s", "A4s", "A3s", "ATs", "KJs", "AJo"):
                return {"SQUEEZE": 75, "FOLD": 25}
            return {"SQUEEZE": 100}
        if in_call:
            if h in ("22", "33", "44", "54s", "65s", "AJo", "KQo"):
                return {"CALL": 70, "FOLD": 30}
            return {"CALL": 100}
        return {"FOLD": 100}

    if kind == "iso_raise":
        r = _get_iso_raise_sets(pos, vs_pos)
        if not r:
            return {"FOLD": 100}
        in_iso = h in r["iso"]
        in_limp = h in r["limp"]
        if in_iso and in_limp:
            return {"RAISE": 65, "CALL": 35}
        if in_iso:
            if h in ("A5s", "A4s", "K9s", "Q9s", "J9s", "T8s", "A9o", "KTo", "QTo"):
                return {"RAISE": 75, "CALL": 25}
            return {"RAISE": 100}
        if in_limp:
            if h in ("22", "33", "54s", "65s", "86s", "75s"):
                return {"CALL": 75, "FOLD": 25}
            return {"CALL": 100}
        return {"FOLD": 100}

    if kind == "facing_3bet":
        r = _get_facing_3bet_sets(pos)
        if not r:
            return {"FOLD": 100}
        in_4b = h in r["4b"]
        in_call = h in r["call"]
        if in_4b and in_call:
            mix = _MIXED_FACING_3BET.get(h)
            if mix and mix[0] + mix[1] > 0:
                total_play = mix[0] + mix[1]
                p4 = int(round(mix[0] * 100 / total_play))
                return {"4-BET": p4, "CALL": 100 - p4}
            return {"4-BET": 60, "CALL": 40}
        if in_4b:
            if h in ("A5s", "A4s", "A3s", "AQo", "AJo"):
                return {"4-BET": 70, "FOLD": 30}
            return {"4-BET": 100}
        if in_call:
            if h in ("22", "33", "44", "55", "76s", "87s", "ATo", "KQo"):
                return {"CALL": 70, "FOLD": 30}
            return {"CALL": 100}
        return {"FOLD": 100}

    if kind == "facing_4bet":
        r = _get_facing_4bet_sets(pos)
        in_5b = h in r["5b"]
        in_call = h in r["call"]
        if in_5b and in_call:
            return {"5-BET/SHOVE": 65, "CALL": 35}
        if in_5b:
            if h in ("A5s", "A4s"):
                return {"5-BET/SHOVE": 75, "FOLD": 25}
            return {"5-BET/SHOVE": 100}
        if in_call:
            if h in ("22", "33", "44", "55", "66", "77", "88", "ATs", "KQs"):
                return {"CALL": 70, "FOLD": 30}
            return {"CALL": 100}
        return {"FOLD": 100}

    return {"FOLD": 100}


def roll_mixed_action(spot: dict, hand: str, rng_value: int = None) -> tuple:
    """
    Roll a 1-100 RNG value and select the action according to get_mixed_frequencies(spot, hand).

    Returns:
        Tuple of (selected_action: str, rng_roll: int, frequencies: dict)
    """
    import random as _random
    freqs = get_mixed_frequencies(spot, hand)
    roll = rng_value if (rng_value is not None and 1 <= rng_value <= 100) else _random.randint(1, 100)

    cumulative = 0
    selected = "FOLD"
    for action, pct in freqs.items():
        cumulative += pct
        if roll <= cumulative:
            selected = action
            break

    return (selected, roll, freqs)
