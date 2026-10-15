"""
Monte Carlo Equity Calculator for Poker RTA.

A lightweight numpy-based equity calculator that simulates poker hands
to estimate win probabilities. Supports both preflop and postflop scenarios.

Based on DeeperMind's montecarlo_numpy.py implementation.
"""

import random
from functools import lru_cache
from typing import List, Tuple, Optional, Dict, Any

# Try to import numpy for vectorized operations
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Try to import phevaluator for ultra-fast C/lookup hand evaluation
try:
    from phevaluator import evaluate_cards as _pheval_cards
    HAS_FAST_EVAL = True
except ImportError:
    _pheval_cards = None
    HAS_FAST_EVAL = False


# Card representations
RANKS = "23456789TJQKA"
SUITS = "cdhs"  # clubs, diamonds, hearts, spades

# Category bases; five base-13 kicker digits fit below the next category.
HIGH_CARD = 1
PAIR = 1_000_000
TWO_PAIR = 10_000_000
THREE_OF_A_KIND = 100_000_000
STRAIGHT = 1_000_000_000
FLUSH = 10_000_000_000
FULL_HOUSE = 100_000_000_000
FOUR_OF_A_KIND = 1_000_000_000_000
STRAIGHT_FLUSH = 10_000_000_000_000


def card_to_index(rank: str, suit: str) -> int:
    """Convert rank and suit characters to a card index (0-51)."""
    return RANKS.index(rank) * 4 + SUITS.index(suit)


def index_to_card(idx: int) -> Tuple[str, str]:
    """Convert card index (0-51) to rank and suit characters."""
    return RANKS[idx // 4], SUITS[idx % 4]


def parse_card(card: str) -> int:
    """Parse a card string like 'Ah' or '2c' to an index (0-51)."""
    if len(card) != 2:
        raise ValueError(f"Invalid card format: {card}")
    rank, suit = card[0].upper(), card[1].lower()
    if rank not in RANKS:
        raise ValueError(f"Invalid rank: {rank}")
    if suit not in SUITS:
        raise ValueError(f"Invalid suit: {suit}")
    return card_to_index(rank, suit)


def parse_hand(hand: str) -> List[int]:
    """Parse a hand string like 'AhKh' or 'AKs' to card indices."""
    if len(hand) == 3 and hand[2] in 'so':
        # Preflop notation like 'AKs' or 'T9o'
        # First card: rank=hand[0], suit='c' (clubs)
        # Second card: rank=hand[1], suit='c' if suited else 'd' (diamonds)
        suit2 = 'c' if hand[2] == 's' else 'd'
        return [card_to_index(hand[0], 'c'), card_to_index(hand[1], suit2)]
    elif len(hand) == 2:
        # Pocket pair like 'AA'
        return [card_to_index(hand[0], 'c'), card_to_index(hand[1], 'd')]
    else:
        # Full card notation like 'AhKh'
        cards = []
        i = 0
        while i < len(hand):
            cards.append(parse_card(hand[i:i+2]))
            i += 2
        return cards


_POW13 = (1, 13, 169, 2197, 28561, 371293)


def _build_lookup_tables():
    straight_high = [-1] * 8192
    bit_count = [0] * 8192
    highest_rank = [-1] * 8192
    top2_value = [0] * 8192
    top3_value = [0] * 8192
    top5_value = [0] * 8192

    for mask in range(8192):
        # Straight detection (A-high down to 6-high, then 5-high wheel 0x100F)
        for start in range(8, -1, -1):
            if ((mask >> start) & 0x1F) == 0x1F:
                straight_high[mask] = start + 4
                break
        else:
            if (mask & 0x100F) == 0x100F:
                straight_high[mask] = 3

        ranks_desc = [r for r in range(12, -1, -1) if (mask >> r) & 1]
        bit_count[mask] = len(ranks_desc)
        if ranks_desc:
            highest_rank[mask] = ranks_desc[0]

        # Top 2 ranks (used as kickers for Three of a Kind: 2 digits at 13^1, 13^0)
        t2 = ranks_desc[:2]
        v2 = 0
        for r in t2:
            v2 = v2 * 13 + r
        top2_value[mask] = v2 * _POW13[2 - len(t2)]

        # Top 3 ranks (used as kickers for One Pair: 3 digits at 13^2, 13^1, 13^0)
        t3 = ranks_desc[:3]
        v3 = 0
        for r in t3:
            v3 = v3 * 13 + r
        top3_value[mask] = v3 * _POW13[3 - len(t3)]

        # Top 5 ranks (used for Flush and High Card: 5 digits)
        t5 = ranks_desc[:5]
        v5 = 0
        for r in t5:
            v5 = v5 * 13 + r
        top5_value[mask] = v5 * _POW13[5 - len(t5)]

    return (
        tuple(straight_high),
        tuple(bit_count),
        tuple(highest_rank),
        tuple(top2_value),
        tuple(top3_value),
        tuple(top5_value),
    )


(
    _STRAIGHT_HIGH,
    _BIT_COUNT,
    _HIGHEST_RANK,
    _TOP2_VALUE,
    _TOP3_VALUE,
    _TOP5_VALUE,
) = _build_lookup_tables()


def _rank_score(category: int, ranks: List[int]) -> int:
    """Encode kickers exactly, most significant rank first, padded to five digits."""
    value = 0
    for rank in ranks:
        value = value * 13 + rank
    return category + value * _POW13[5 - len(ranks)]


def evaluate_hand(cards: List[int]) -> int:
    """
    Evaluate a 5-to-7-card hand and return a score in strict descending rank order:
    1. Straight Flush
    2. Four of a Kind
    3. Full House
    4. Flush
    5. Straight
    6. Three of a Kind
    7. Two Pair
    8. One Pair
    9. High Card
    Higher score = better hand.
    """
    if not cards:
        return 0

    rc = [0] * 13
    sc0 = sc1 = sc2 = sc3 = 0
    sm0 = sm1 = sm2 = sm3 = 0
    rm = 0

    for c in cards:
        r = c >> 2
        s = c & 3
        rc[r] += 1
        bit = 1 << r
        rm |= bit
        if s == 0:
            sc0 += 1
            sm0 |= bit
        elif s == 1:
            sc1 += 1
            sm1 |= bit
        elif s == 2:
            sc2 += 1
            sm2 |= bit
        else:
            sc3 += 1
            sm3 |= bit

    flush_mask = 0
    if sc0 >= 5:
        flush_mask = sm0
    elif sc1 >= 5:
        flush_mask = sm1
    elif sc2 >= 5:
        flush_mask = sm2
    elif sc3 >= 5:
        flush_mask = sm3

    # 1. Straight Flush
    if flush_mask:
        sf_high = _STRAIGHT_HIGH[flush_mask]
        if sf_high >= 0:
            return STRAIGHT_FLUSH + sf_high * 28561

    # Fast path when all cards have distinct ranks (no pairs, trips, full house, or quads possible)
    if _BIT_COUNT[rm] == len(cards):
        if flush_mask:
            return FLUSH + _TOP5_VALUE[flush_mask]
        st_high = _STRAIGHT_HIGH[rm]
        if st_high >= 0:
            return STRAIGHT + st_high * 28561
        return HIGH_CARD + _TOP5_VALUE[rm]

    quad = -1
    trip1 = -1
    trip2 = -1
    pair1 = -1
    pair2 = -1
    for r in range(12, -1, -1):
        cnt = rc[r]
        if cnt == 4:
            if quad < 0:
                quad = r
        elif cnt == 3:
            if trip1 < 0:
                trip1 = r
            elif trip2 < 0:
                trip2 = r
        elif cnt == 2:
            if pair1 < 0:
                pair1 = r
            elif pair2 < 0:
                pair2 = r

    # 2. Four of a Kind
    if quad >= 0:
        kicker = _HIGHEST_RANK[rm & ~(1 << quad)]
        if kicker >= 0:
            return FOUR_OF_A_KIND + (quad * 13 + kicker) * 2197
        return FOUR_OF_A_KIND + quad * 28561

    # 3. Full House
    if trip1 >= 0 and (trip2 >= 0 or pair1 >= 0):
        second = trip2 if trip2 >= 0 else pair1
        return FULL_HOUSE + (trip1 * 13 + second) * 2197

    # 4. Flush
    if flush_mask:
        return FLUSH + _TOP5_VALUE[flush_mask]

    # 5. Straight
    st_high = _STRAIGHT_HIGH[rm]
    if st_high >= 0:
        return STRAIGHT + st_high * 28561

    # 6. Three of a Kind
    if trip1 >= 0:
        rem = rm & ~(1 << trip1)
        return THREE_OF_A_KIND + trip1 * 28561 + _TOP2_VALUE[rem] * 169

    # 7. Two Pair
    if pair2 >= 0:
        rem = rm & ~((1 << pair1) | (1 << pair2))
        kicker = _HIGHEST_RANK[rem]
        if kicker >= 0:
            return TWO_PAIR + (pair1 * 169 + pair2 * 13 + kicker) * 169
        return TWO_PAIR + (pair1 * 13 + pair2) * 2197

    # 8. One Pair
    if pair1 >= 0:
        rem = rm & ~(1 << pair1)
        return PAIR + pair1 * 28561 + _TOP3_VALUE[rem] * 13

    # 9. High Card
    return HIGH_CARD + _TOP5_VALUE[rm]


def evaluate_hand_fast(cards: List[int]) -> int:
    """
    Ultra-fast hand evaluation for 5-to-7 cards where higher score = better hand.
    Uses phevaluator (7462 - rank) when available, otherwise falls back to evaluate_hand().
    Note: phevaluator uses the exact same card index encoding (rank * 4 + suit, 2c=0..As=51).
    """
    if HAS_FAST_EVAL and 5 <= len(cards) <= 7:
        # phevaluator returns 1 for Royal Flush down to 7462 for 7-5-4-3-2 unsuited
        return 7463 - _pheval_cards(*cards)
    return evaluate_hand(cards)


def build_showdown_matrix(
    hero_combos: List[Tuple[int, int]],
    opp_combos: List[Tuple[int, int]],
    board: List[int]
) -> Dict[str, Any]:
    """
    Pre-evaluate 7-card hands on a 5-card board in O(N + M) evaluations instead of O(N * M),
    and build a vectorized showdown payoff/equity matrix (+1 win, 0 tie, -1 loss, NaN blocked).

    Args:
        hero_combos: List of (c0, c1) tuples for hero range
        opp_combos: List of (c0, c1) tuples for villain range
        board: List of 5 card indices (or 3-4 card board evaluated directly)

    Returns:
        Dict containing:
            - 'hero_combos': filtered valid hero combos (not colliding with board)
            - 'opp_combos': filtered valid villain combos (not colliding with board)
            - 'hero_scores': list/array of hand scores for valid hero combos
            - 'opp_scores': list/array of hand scores for valid villain combos
            - 'payoff_matrix': (N_hero, N_opp) float matrix where:
                +1.0 if hero > opp, 0.0 if tie, -1.0 if hero < opp,
                and 0.0 where cards collide (with 'valid_mask' False)
            - 'valid_mask': (N_hero, N_opp) boolean matrix (True if hero & opp share no hole cards)
            - 'equity_matrix': (N_hero, N_opp) float matrix (1.0 win, 0.5 tie, 0.0 loss/invalid)
    """
    board_mask = 0
    for c in board:
        board_mask |= 1 << c

    valid_hero = []
    hero_masks = []
    for c0, c1 in hero_combos:
        m = (1 << c0) | (1 << c1)
        if not (m & board_mask):
            valid_hero.append((c0, c1))
            hero_masks.append(m)

    valid_opp = []
    opp_masks = []
    for c0, c1 in opp_combos:
        m = (1 << c0) | (1 << c1)
        if not (m & board_mask):
            valid_opp.append((c0, c1))
            opp_masks.append(m)

    # Deduplicate combos needed for evaluation so each unique combo is scored once
    unique_combos = {}
    eval_fn = evaluate_hand_fast if len(board) >= 3 else evaluate_hand
    for c0, c1 in valid_hero:
        key = (min(c0, c1), max(c0, c1))
        if key not in unique_combos:
            unique_combos[key] = eval_fn([c0, c1] + board)
    for c0, c1 in valid_opp:
        key = (min(c0, c1), max(c0, c1))
        if key not in unique_combos:
            unique_combos[key] = eval_fn([c0, c1] + board)

    hero_scores = [unique_combos[(min(c0, c1), max(c0, c1))] for c0, c1 in valid_hero]
    opp_scores = [unique_combos[(min(c0, c1), max(c0, c1))] for c0, c1 in valid_opp]

    n_h = len(valid_hero)
    n_o = len(valid_opp)

    if HAS_NUMPY and n_h > 0 and n_o > 0:
        h_sc = np.array(hero_scores, dtype=np.int64)[:, None]
        o_sc = np.array(opp_scores, dtype=np.int64)[None, :]
        h_mk = np.array(hero_masks, dtype=np.int64)[:, None]
        o_mk = np.array(opp_masks, dtype=np.int64)[None, :]

        valid_mask = (h_mk & o_mk) == 0
        payoff = np.where(h_sc > o_sc, 1.0, np.where(h_sc < o_sc, -1.0, 0.0))
        payoff = np.where(valid_mask, payoff, 0.0)
        equity_mat = np.where(valid_mask, (payoff + 1.0) * 0.5, 0.0)
        return {
            "hero_combos": valid_hero,
            "opp_combos": valid_opp,
            "hero_scores": hero_scores,
            "opp_scores": opp_scores,
            "payoff_matrix": payoff,
            "valid_mask": valid_mask,
            "equity_matrix": equity_mat,
        }

    # Pure-Python fallback
    payoff_list = []
    valid_list = []
    equity_list = []
    for i in range(n_h):
        p_row = []
        v_row = []
        e_row = []
        hs = hero_scores[i]
        hm = hero_masks[i]
        for j in range(n_o):
            if hm & opp_masks[j]:
                v_row.append(False)
                p_row.append(0.0)
                e_row.append(0.0)
            else:
                v_row.append(True)
                os_val = opp_scores[j]
                if hs > os_val:
                    p_row.append(1.0)
                    e_row.append(1.0)
                elif hs < os_val:
                    p_row.append(-1.0)
                    e_row.append(0.0)
                else:
                    p_row.append(0.0)
                    e_row.append(0.5)
        payoff_list.append(p_row)
        valid_list.append(v_row)
        equity_list.append(e_row)

    return {
        "hero_combos": valid_hero,
        "opp_combos": valid_opp,
        "hero_scores": hero_scores,
        "opp_scores": opp_scores,
        "payoff_matrix": np.array(payoff_list) if HAS_NUMPY else payoff_list,
        "valid_mask": np.array(valid_list, dtype=bool) if HAS_NUMPY else valid_list,
        "equity_matrix": np.array(equity_list) if HAS_NUMPY else equity_list,
    }


def monte_carlo_equity(
    hero_cards: List[int],
    opponent_ranges: List[List[int]],
    board: List[int],
    iterations: int = 1000
) -> float:
    """
    Calculate hero's equity against opponent ranges using Monte Carlo simulation.
    
    Args:
        hero_cards: Hero's hole cards as indices (0-51)
        opponent_ranges: List of opponent hand ranges, each range is a list of card pairs
        board: Community cards as indices (empty for preflop)
        iterations: Number of simulations to run
    
    Returns:
        Hero's equity as a float between 0.0 and 1.0
    """
    if not HAS_NUMPY:
        return _monte_carlo_equity_python(hero_cards, opponent_ranges, board, iterations)
    
    return _monte_carlo_equity_numpy(hero_cards, opponent_ranges, board, iterations)


def _run_equity_simulation(
    hero_cards: List[int],
    opponent_ranges: List[List[int]],
    board: List[int],
    iterations: int
) -> float:
    """Core equity calculation with exact river/turn enumeration and bitmask collision checks."""
    if iterations <= 0:
        return 0.0

    used_mask = 0
    for c in hero_cards:
        used_mask |= 1 << c
    for c in board:
        used_mask |= 1 << c

    remaining_deck = [c for c in range(52) if not (used_mask & (1 << c))]
    cards_needed = max(0, 5 - len(board))

    # Pre-filter opponent ranges against known hero and board cards and precompute 52-bit masks
    filtered_ranges = []
    for opp_range in opponent_ranges:
        if not opp_range:
            continue
        valid_combos = [
            (c[0], c[1], (1 << c[0]) | (1 << c[1]))
            for c in opp_range
            if not (used_mask & ((1 << c[0]) | (1 << c[1])))
        ]
        if valid_combos:
            filtered_ranges.append(valid_combos)

    if not filtered_ranges:
        return 0.0

    # Exact deterministic calculation on the river against a single opponent range
    if cards_needed == 0 and len(filtered_ranges) == 1:
        hero_score = evaluate_hand_fast(hero_cards + board)
        opp_range = filtered_ranges[0]
        wins = 0
        ties = 0
        for c0, c1, _mask in opp_range:
            opp_score = evaluate_hand_fast([c0, c1] + board)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
        return (wins + ties * 0.5) / len(opp_range)

    # Exact deterministic calculation on the turn when total enumeration is smaller than iterations
    if (
        cards_needed == 1
        and len(filtered_ranges) == 1
        and len(remaining_deck) * len(filtered_ranges[0]) <= iterations * 2
    ):
        opp_range = filtered_ranges[0]
        wins = 0
        ties = 0
        total = 0
        for river_card in remaining_deck:
            river_bit = 1 << river_card
            complete_board = board + [river_card]
            hero_score = evaluate_hand_fast(hero_cards + complete_board)
            for c0, c1, opp_mask in opp_range:
                if opp_mask & river_bit:
                    continue
                opp_score = evaluate_hand_fast([c0, c1] + complete_board)
                total += 1
                if hero_score > opp_score:
                    wins += 1
                elif hero_score == opp_score:
                    ties += 1
        return (wins + ties * 0.5) / max(1, total)

    wins = 0
    ties = 0
    valid_iters = 0

    sample = random.sample
    choice = random.choice

    for _ in range(iterations):
        if cards_needed > 0:
            drawn = sample(remaining_deck, cards_needed)
            drawn_mask = 0
            for d in drawn:
                drawn_mask |= 1 << d
            complete_board = board + drawn
        else:
            drawn_mask = 0
            complete_board = board

        hero_score = evaluate_hand_fast(hero_cards + complete_board)

        opp_wins = 0
        opp_ties = 0

        for opp_range in filtered_ranges:
            opp_cards = None
            for _attempt in range(5):
                cand = choice(opp_range)
                if not (cand[2] & drawn_mask):
                    opp_cards = cand
                    break
            if opp_cards is None:
                continue

            opp_score = evaluate_hand_fast([opp_cards[0], opp_cards[1]] + complete_board)

            if opp_score > hero_score:
                opp_wins += 1
            elif opp_score == hero_score:
                opp_ties += 1

        valid_iters += 1
        if opp_wins == 0:
            if opp_ties > 0:
                ties += 1
            else:
                wins += 1

    return (wins + ties / 2) / max(1, valid_iters)


def _monte_carlo_equity_python(
    hero_cards: List[int],
    opponent_ranges: List[List[int]],
    board: List[int],
    iterations: int
) -> float:
    """Python fallback for Monte Carlo equity calculation."""
    return _run_equity_simulation(hero_cards, opponent_ranges, board, iterations)


def _monte_carlo_equity_numpy(
    hero_cards: List[int],
    opponent_ranges: List[List[int]],
    board: List[int],
    iterations: int
) -> float:
    """Numpy-accelerated Monte Carlo equity calculation for speed."""
    if not HAS_NUMPY or iterations <= 0:
        return _run_equity_simulation(hero_cards, opponent_ranges, board, iterations)

    used_mask = 0
    for c in hero_cards:
        used_mask |= 1 << c
    for c in board:
        used_mask |= 1 << c

    remaining_deck = [c for c in range(52) if not (used_mask & (1 << c))]
    cards_needed = max(0, 5 - len(board))

    filtered_ranges = []
    for opp_range in opponent_ranges:
        if not opp_range:
            continue
        valid_combos = [
            (c[0], c[1], (1 << c[0]) | (1 << c[1]))
            for c in opp_range
            if not (used_mask & ((1 << c[0]) | (1 << c[1])))
        ]
        if valid_combos:
            filtered_ranges.append(valid_combos)

    if not filtered_ranges:
        return 0.0

    # Use exact enumeration on river and turn (single opponent) when fast
    if cards_needed == 0 and len(filtered_ranges) == 1:
        return _run_equity_simulation(hero_cards, opponent_ranges, board, iterations)
    if (
        cards_needed == 1
        and len(filtered_ranges) == 1
        and len(remaining_deck) * len(filtered_ranges[0]) <= iterations * 2
    ):
        return _run_equity_simulation(hero_cards, opponent_ranges, board, iterations)

    # Pre-generate random indices in bulk with NumPy to avoid per-iteration Python RNG overhead
    rng = np.random.default_rng()
    n_rem = len(remaining_deck)
    rem_arr = np.array(remaining_deck, dtype=np.int32)
    rem_bits = np.int64(1) << rem_arr

    if cards_needed > 0:
        # Generate random keys and take argpartition/argsort to sample without replacement
        rand_matrix = rng.random((iterations, n_rem))
        drawn_idx = np.argpartition(rand_matrix, cards_needed - 1, axis=1)[:, :cards_needed]
        drawn_cards = rem_arr[drawn_idx].tolist()
        drawn_masks = np.bitwise_or.reduce(rem_bits[drawn_idx], axis=1).tolist()
    else:
        drawn_cards = [[] for _ in range(iterations)]
        drawn_masks = [0] * iterations

    opp_choices = [
        rng.integers(0, len(opp_r), size=(iterations, 5)).tolist()
        for opp_r in filtered_ranges
    ]

    wins = 0
    ties = 0
    valid_iters = 0
    eval_fn = evaluate_hand_fast

    for i in range(iterations):
        d_mask = drawn_masks[i]
        complete_board = board + drawn_cards[i] if cards_needed > 0 else board
        hero_score = eval_fn(hero_cards + complete_board)

        opp_wins = 0
        opp_ties = 0
        for r_idx, opp_range in enumerate(filtered_ranges):
            opp_cards = None
            for cand_idx in opp_choices[r_idx][i]:
                cand = opp_range[cand_idx]
                if not (cand[2] & d_mask):
                    opp_cards = cand
                    break
            if opp_cards is None:
                continue
            opp_score = eval_fn([opp_cards[0], opp_cards[1]] + complete_board)
            if opp_score > hero_score:
                opp_wins += 1
            elif opp_score == hero_score:
                opp_ties += 1

        valid_iters += 1
        if opp_wins == 0:
            if opp_ties > 0:
                ties += 1
            else:
                wins += 1

    return (wins + ties * 0.5) / max(1, valid_iters)


@lru_cache(maxsize=512)
def _cached_equity(
    hero_cards_tuple: Tuple[int, ...],
    opponent_range_norm: str,
    board_cards_tuple: Tuple[int, ...],
    iterations: int,
    num_opponents: int
) -> float:
    """LRU-cached equity calculation keyed on canonical card tuples and normalized range."""
    opp_range_cards = list(_cached_parse_range(opponent_range_norm))
    return monte_carlo_equity(
        list(hero_cards_tuple),
        [opp_range_cards] * num_opponents,
        list(board_cards_tuple),
        iterations
    )


def clear_equity_cache() -> None:
    """Clear the memoized equity and range caches."""
    _cached_equity.cache_clear()
    _cached_parse_range.cache_clear()


def calculate_equity(
    hero_hand: str,
    opponent_range: str,
    board: str = "",
    iterations: int = 1000,
    num_opponents: int = 1
) -> float:
    """
    Calculate equity for a hero hand against an opponent range.
    
    Args:
        hero_hand: Hero's hand in standard notation (e.g., 'AKs', 'AhKh', '77')
        opponent_range: Opponent's range in standard notation (e.g., '77+, AJs+, KQs')
        board: Board cards (e.g., 'AhKd5s' for flop, empty for preflop)
        iterations: Number of Monte Carlo iterations (default 1000)
        num_opponents: Number of active opponents (default 1)
    
    Returns:
        Hero's equity as a float between 0.0 and 1.0
    """
    hero_cards = tuple(parse_hand(hero_hand))
    board_cards = tuple(parse_hand(board)) if board else ()
    opp_count = max(1, int(num_opponents))
    norm_range = " ".join(opponent_range.replace(',', ' ').split()) if opponent_range else ""
    return _cached_equity(hero_cards, norm_range, board_cards, int(iterations), opp_count)


def _add_pair_combos(hands: List[Tuple[int, int]], rank: int) -> None:
    for s1 in range(4):
        for s2 in range(s1 + 1, 4):
            hands.append((rank * 4 + s1, rank * 4 + s2))


def _add_suited_combos(hands: List[Tuple[int, int]], high_rank: int, low_rank: int) -> None:
    for s in range(4):
        hands.append((high_rank * 4 + s, low_rank * 4 + s))


def _add_offsuit_combos(hands: List[Tuple[int, int]], high_rank: int, low_rank: int) -> None:
    for s1 in range(4):
        for s2 in range(4):
            if s1 != s2:
                hands.append((high_rank * 4 + s1, low_rank * 4 + s2))


@lru_cache(maxsize=256)
def _cached_parse_range(range_str: str) -> Tuple[Tuple[int, int], ...]:
    return tuple(_parse_range_uncached(range_str))


def parse_range(range_str: str) -> List[Tuple[int, int]]:
    norm = " ".join(range_str.replace(',', ' ').split()) if range_str else ""
    return list(_cached_parse_range(norm))


def _parse_range_uncached(range_str: str) -> List[Tuple[int, int]]:
    """
    Parse a range string into a list of card pairs.

    Supports:
        - Pairs: '77', 'AA', '22'
        - Suited: 'AKs', 'T9s'
        - Offsuit: 'AKo', 'T9o'
        - Unsuited shorthand: 'AK' (both suited and offsuit, 16 combos)
        - Plus notation: '77+', 'AJs+', 'ATo+' (expands upward: AJs+ -> AJs, AQs, AKs)
        - Dash notation: '22-JJ', 'A2s-A5s', 'ATo-AQo'
        - Combinations separated by commas or whitespace: '77+, AJs+, KQo'

    Args:
        range_str: Range notation string

    Returns:
        List of (card1_idx, card2_idx) tuples
    """
    hands: List[Tuple[int, int]] = []
    if not range_str:
        return hands

    # Split by comma or whitespace
    raw_parts = range_str.replace(',', ' ').split()

    for part in raw_parts:
        part = part.strip()
        if not part:
            continue

        # Normalize case: ranks uppercase, suitedness lowercase
        if len(part) >= 2:
            norm_chars = []
            for ch in part:
                if ch.upper() in RANKS:
                    norm_chars.append(ch.upper())
                else:
                    norm_chars.append(ch.lower())
            part = "".join(norm_chars)

        # Handle dash notation (e.g. '22-JJ', 'A2s-A5s', 'ATo-AQo')
        if '-' in part and len(part.split('-')) == 2:
            start_tok, end_tok = part.split('-')
            # Pair dash range: '22-JJ' or 'JJ-22'
            if (
                len(start_tok) == 2 and len(end_tok) == 2
                and start_tok[0] == start_tok[1] and end_tok[0] == end_tok[1]
                and start_tok[0] in RANKS and end_tok[0] in RANKS
            ):
                r1 = RANKS.index(start_tok[0])
                r2 = RANKS.index(end_tok[0])
                lo, hi = min(r1, r2), max(r1, r2)
                for r in range(lo, hi + 1):
                    _add_pair_combos(hands, r)
                continue
            # Suited/Offsuit dash range with same high card: 'A2s-A5s'
            if (
                len(start_tok) == 3 and len(end_tok) == 3
                and start_tok[0] == end_tok[0]
                and start_tok[2] == end_tok[2] and start_tok[2] in 'so'
                and start_tok[0] in RANKS and start_tok[1] in RANKS and end_tok[1] in RANKS
            ):
                high_rank = RANKS.index(start_tok[0])
                r1 = RANKS.index(start_tok[1])
                r2 = RANKS.index(end_tok[1])
                lo, hi = min(r1, r2), max(r1, r2)
                for r in range(lo, hi + 1):
                    if r == high_rank:
                        continue
                    if start_tok[2] == 's':
                        _add_suited_combos(hands, high_rank, r)
                    else:
                        _add_offsuit_combos(hands, high_rank, r)
                continue

        # Handle plus notation
        if part.endswith('+'):
            base = part[:-1]
            if len(base) == 2 and base[0] == base[1] and base[0] in RANKS:  # Pair like '77+'
                rank = RANKS.index(base[0])
                for r in range(rank, 13):
                    _add_pair_combos(hands, r)
            elif len(base) == 3 and base[2] == 's' and base[0] in RANKS and base[1] in RANKS:  # Suited like 'AJs+'
                r0, r1 = RANKS.index(base[0]), RANKS.index(base[1])
                high_rank, low_rank = max(r0, r1), min(r0, r1)
                # Expand upward from low_rank to high_rank - 1 (e.g. AJs+ -> AJs, AQs, AKs)
                for r in range(low_rank, high_rank):
                    _add_suited_combos(hands, high_rank, r)
            elif len(base) == 3 and base[2] == 'o' and base[0] in RANKS and base[1] in RANKS:  # Offsuit like 'ATo+'
                r0, r1 = RANKS.index(base[0]), RANKS.index(base[1])
                high_rank, low_rank = max(r0, r1), min(r0, r1)
                # Expand upward from low_rank to high_rank - 1 (e.g. ATo+ -> ATo, AJo, AQo, AKo)
                for r in range(low_rank, high_rank):
                    _add_offsuit_combos(hands, high_rank, r)
            elif len(base) == 2 and base[0] != base[1] and base[0] in RANKS and base[1] in RANKS:  # 'AT+'
                r0, r1 = RANKS.index(base[0]), RANKS.index(base[1])
                high_rank, low_rank = max(r0, r1), min(r0, r1)
                for r in range(low_rank, high_rank):
                    _add_suited_combos(hands, high_rank, r)
                    _add_offsuit_combos(hands, high_rank, r)
        elif len(part) == 2 and part[0] == part[1] and part[0] in RANKS:  # Pair like 'AA'
            rank = RANKS.index(part[0])
            _add_pair_combos(hands, rank)
        elif len(part) == 3 and part[2] in 'so' and part[0] in RANKS and part[1] in RANKS:  # Suited/offsuit like 'AKs'
            r0, r1 = RANKS.index(part[0]), RANKS.index(part[1])
            high_rank, low_rank = max(r0, r1), min(r0, r1)
            if part[2] == 's':
                _add_suited_combos(hands, high_rank, low_rank)
            else:
                _add_offsuit_combos(hands, high_rank, low_rank)
        elif len(part) == 2 and part[0] != part[1] and part[0] in RANKS and part[1] in RANKS:  # Unsuited 'AK'
            r0, r1 = RANKS.index(part[0]), RANKS.index(part[1])
            high_rank, low_rank = max(r0, r1), min(r0, r1)
            _add_suited_combos(hands, high_rank, low_rank)
            _add_offsuit_combos(hands, high_rank, low_rank)
        elif len(part) == 4 and part[0] in RANKS and part[2] in RANKS and part[1] in SUITS and part[3] in SUITS:
            c1 = card_to_index(part[0], part[1])
            c2 = card_to_index(part[2], part[3])
            if c1 != c2:
                hands.append((c1, c2))

    # Deduplicate unordered card combos while preserving order
    deduped: List[Tuple[int, int]] = []
    seen = set()
    for c1, c2 in hands:
        key = (min(c1, c2), max(c1, c2))
        if key not in seen:
            seen.add(key)
            deduped.append((c1, c2))
    return deduped


def get_equity_percentage(
    hero_hand: str,
    opponent_range: str = "22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 92s+, 82s+, 72s+, 62s+, 52s+, 42s+, 32s+, ATo+, KTo+, QTo+, JTo",
    board: str = "",
    iterations: int = 1000,
    num_opponents: int = 1
) -> float:
    """
    Get equity as a percentage (0-100).
    
    Args:
        hero_hand: Hero's hand
        opponent_range: Opponent's range (default: typical calling range)
        board: Board cards
        iterations: Monte Carlo iterations
        num_opponents: Number of active opponents (default 1)
    
    Returns:
        Equity percentage (0-100)
    """
    if num_opponents != 1:
        equity = calculate_equity(hero_hand, opponent_range, board, iterations, num_opponents=num_opponents)
    else:
        equity = calculate_equity(hero_hand, opponent_range, board, iterations)
    return equity * 100


# Simple fallback if numpy is not available
def _simple_equity(hero_hand: str, opponent_range: str = "", board: str = "", iterations: int = 1000) -> float:
    """Simple equity estimation without numpy."""
    if not HAS_NUMPY:
        print("Note: Install numpy for faster equity calculations: pip install numpy")
    
    return calculate_equity(hero_hand, opponent_range, board, iterations)


if __name__ == "__main__":
    # Example usage
    print("Equity Calculator Demo")
    print("=" * 40)
    
    # Preflop example
    equity = get_equity_percentage("AKs", "77+, AJo+")
    print(f"AKs vs 77+, AJo+ (preflop): {equity:.1f}%")
    
    # Flop example
    equity = get_equity_percentage("AhKh", "QQ", "QdJd8s")
    print(f"AhKh vs QQ on QdJd8s: {equity:.1f}%")
