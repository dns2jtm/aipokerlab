"""
Outs Calculator for Poker RTA.

Detects drawing opportunities and calculates the number of outs for:
- Flush draws (9 outs)
- Open-ended straight draws (8 outs)
- Gutshot straight draws (4 outs)
- Combined draws (flush + straight)

Based on DeeperMind's outs_calculator.py implementation.
"""

from typing import List, Tuple, Optional, Dict, Any

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def parse_card(card: str) -> Tuple[int, int]:
    """Parse a card string like 'Ah' or '2c' to (rank_idx, suit_idx)."""
    if len(card) != 2:
        raise ValueError(f"Invalid card format: {card}")
    rank = card[0].upper()
    suit = card[1].lower()
    if rank not in RANKS:
        raise ValueError(f"Invalid rank: {rank}")
    if suit not in SUITS:
        raise ValueError(f"Invalid suit: {suit}")
    return RANKS.index(rank), SUITS.index(suit)


def parse_cards(cards_str: str) -> List[Tuple[int, int]]:
    """Parse a string of cards like 'AhKh5s' into a list of (rank, suit) tuples."""
    cards_str = cards_str.strip()
    if not cards_str:
        return []
    # Support shorthand hand strings like 'T9h' (two ranks + common suit),
    # '23o' / 'AKs' (preflop notation), or rank-only boards like 'KQJ'
    if len(cards_str) == 3 and cards_str[0].upper() in RANKS and cards_str[1].upper() in RANKS:
        r1 = RANKS.index(cards_str[0].upper())
        r2 = RANKS.index(cards_str[1].upper())
        s_char = cards_str[2].lower()
        if s_char in SUITS:
            s_idx = SUITS.index(s_char)
            return [(r1, s_idx), (r2, s_idx)]
        elif s_char == 's':
            return [(r1, 0), (r2, 0)]
        elif s_char == 'o':
            return [(r1, 0), (r2, 1)]
    if all(ch.upper() in RANKS for ch in cards_str):
        # Rank-only notation (e.g. 'KQJ' or 'AA'), assign distinct suits to avoid phantom flush draws
        return [(RANKS.index(ch.upper()), idx % 4) for idx, ch in enumerate(cards_str)]
    cards = []
    i = 0
    while i < len(cards_str):
        cards.append(parse_card(cards_str[i:i+2]))
        i += 2
    return cards


def get_outs(
    hero_hand: str,
    board: str,
    street: str = "flop"
) -> Dict[str, Any]:
    """
    Calculate outs for a given hand and board.
    
    Args:
        hero_hand: Hero's hole cards (e.g., 'AhKh')
        board: Board cards (e.g., 'QdJd8s' for flop)
        street: Current street ('flop', 'turn', or 'river')
    
    Returns:
        Dictionary with outs count and description
    """
    # Parse cards
    hero = parse_cards(hero_hand)
    board_cards = parse_cards(board)

    # Need at least 2 board cards (flop+) and fewer than 5 board cards (before river) to have future draws
    if len(board_cards) < 2 or len(board_cards) >= 5 or street == "river":
        return {
            'outs': 0,
            'clean_outs': 0,
            'description': 'No significant draws',
            'flush_draw': False,
            'straight_draw': False,
            'flush_outs': 0,
            'straight_outs': 0,
            'overcard_outs': 0,
            'overcard_description': '',
            'improvement_outs': 0,
            'improvement_description': '',
            'outs_pct': 0.0,
            'rule_of_4_2': 0.0,
            'breakdown': {},
            'draw_type': 'none'
        }
    
    # Combine all known cards
    all_cards = hero + board_cards
    
    # Get ranks and suits
    ranks = [c[0] for c in all_cards]
    suits = [c[1] for c in all_cards]
    
    # Count suits
    suit_counts = {s: suits.count(s) for s in range(4)}
    
    # Calculate outs
    flush_outs = _calculate_flush_outs(suit_counts, all_cards)
    straight_outs = _calculate_straight_outs(ranks, all_cards)
    overcard_info = _calculate_overcard_outs(hero, board_cards)
    improvement_info = _calculate_improvement_outs(hero, board_cards)

    # Classify draw before subtracting straight-flush overlap
    draw_type = _classify_draw(flush_outs, straight_outs)

    # Combine results
    total_outs = 0
    description_parts = []

    if flush_outs['has_draw']:
        total_outs += flush_outs['outs']
        description_parts.append(flush_outs['description'])

    if straight_outs['has_draw']:
        # Avoid double-counting straight flush outs
        overlap = _calculate_overlap(flush_outs, straight_outs, all_cards)
        straight_outs['outs'] -= overlap
        if straight_outs['outs'] > 0:
            total_outs += straight_outs['outs']
            description_parts.append(straight_outs['description'])

    if not description_parts:
        description_parts.append("No significant draws")

    # Calculate clean outs (discounting board-only 4-card draws where hero holds no contributing card)
    hero_suits = {c[1] for c in hero}
    hero_ranks = {c[0] for c in hero}
    board_ranks = {c[0] for c in board_cards}
    clean_outs = 0
    if flush_outs['has_draw']:
        flush_suit = max(suit_counts, key=suit_counts.get)
        if flush_suit in hero_suits or not hero:
            clean_outs += flush_outs['outs']
    if straight_outs['has_draw'] and straight_outs['outs'] > 0:
        # Check if hero contributes at least one rank not already on the board
        if (hero_ranks - board_ranks) or not hero:
            clean_outs += straight_outs['outs']

    unseen_cards = max(1, 52 - len(all_cards))
    outs_pct = round((total_outs / unseen_cards) * 100.0, 1)
    is_turn = len(board_cards) == 4 or street == "turn"
    rule_of_4_2 = float(min(100, total_outs * (2 if is_turn else 4)))

    breakdown: Dict[str, int] = {}
    if flush_outs['has_draw'] and flush_outs['outs'] > 0:
        breakdown['flush'] = flush_outs['outs']
    if straight_outs['has_draw'] and straight_outs['outs'] > 0:
        breakdown['straight'] = straight_outs['outs']
    if overcard_info['outs'] > 0:
        breakdown['overcards'] = overcard_info['outs']
    if improvement_info['outs'] > 0:
        breakdown['improvement'] = improvement_info['outs']

    return {
        'outs': total_outs,
        'clean_outs': clean_outs,
        'description': ', '.join(description_parts),
        'flush_draw': flush_outs['has_draw'],
        'straight_draw': straight_outs['has_draw'],
        'flush_outs': flush_outs['outs'] if flush_outs['has_draw'] else 0,
        'straight_outs': straight_outs['outs'] if straight_outs['has_draw'] else 0,
        'overcard_outs': overcard_info['outs'],
        'overcard_description': overcard_info['description'],
        'improvement_outs': improvement_info['outs'],
        'improvement_description': improvement_info['description'],
        'outs_pct': outs_pct,
        'rule_of_4_2': rule_of_4_2,
        'breakdown': breakdown,
        'draw_type': draw_type
    }


def _calculate_flush_outs(
    suit_counts: Dict[int, int],
    known_cards: List[Tuple[int, int]]
) -> Dict[str, Any]:
    """Calculate flush draw outs."""
    max_suit_count = max(suit_counts.values()) if suit_counts else 0

    if max_suit_count >= 5:
        # Already have a flush
        return {'has_draw': False, 'outs': 0, 'description': 'Already have flush'}

    if max_suit_count == 4:
        # Flush draw - 9 outs (13 - 4 known)
        return {
            'has_draw': True,
            'outs': 9,
            'description': 'Flush draw (9 outs)'
        }

    if max_suit_count == 3:
        # Backdoor flush draw - not counted as direct outs
        return {
            'has_draw': False,
            'outs': 0,
            'description': 'Backdoor flush draw'
        }

    return {'has_draw': False, 'outs': 0, 'description': ''}


def _calculate_straight_outs(
    ranks: List[int],
    known_cards: List[Tuple[int, int]]
) -> Dict[str, Any]:
    """Calculate straight draw outs."""

    unique_ranks = sorted(set(ranks))

    # Add Ace as low for wheel straight
    if 12 in unique_ranks:  # Ace
        unique_ranks_with_low = sorted(unique_ranks + [-1])
    else:
        unique_ranks_with_low = unique_ranks

    # Check if a 5-card straight is already made
    rank_set = set(unique_ranks_with_low)
    for start in range(-1, 9):
        if all((start + offset) in rank_set for offset in range(5)):
            return {
                'has_draw': False,
                'outs': 0,
                'completing_ranks': [],
                'description': 'Already have straight'
            }

    # Find all distinct missing ranks that complete a 5-card straight window of 4 known ranks
    completing_ranks = set()
    internal_completing_ranks = set()
    for start in range(-1, 9):
        window = [start + offset for offset in range(5)]
        missing = [r for r in window if r not in rank_set]
        if len(missing) == 1:
            m = missing[0]
            norm_m = 12 if m == -1 else m
            completing_ranks.add(norm_m)
            if m not in (window[0], window[-1]):
                internal_completing_ranks.add(norm_m)

    completing_list = sorted(completing_ranks)
    # Count remaining cards in deck for the completing ranks
    known_rank_counts = {}
    for r, _s in known_cards:
        known_rank_counts[r] = known_rank_counts.get(r, 0) + 1
    actual_outs = sum(max(0, 4 - known_rank_counts.get(r, 0)) for r in completing_list)

    # Check for open-ended straight draw (8 outs)
    oesd = _check_open_ended_straight(unique_ranks_with_low)
    if oesd:
        outs_count = actual_outs if actual_outs > 0 else 8
        return {
            'has_draw': True,
            'outs': outs_count,
            'completing_ranks': completing_list,
            'description': f'Open-ended straight draw ({outs_count} outs)'
        }

    # Double gutshot (double belly-buster): 2 distinct missing internal ranks complete a 5-card straight (8 outs)
    if len(internal_completing_ranks) >= 2 or len(completing_list) >= 2:
        outs_count = actual_outs if actual_outs > 0 else 8
        return {
            'has_draw': True,
            'outs': outs_count,
            'completing_ranks': completing_list,
            'description': f'Open-ended / double-gutshot straight draw ({outs_count} outs)'
        }

    # Check for gutshot / single-ended 4-out straight draw (e.g. A-2-3-4 or A-K-Q-J or inside gutshot)
    gutshot = len(completing_list) == 1 or _check_gutshot_straight(unique_ranks_with_low, known_cards)
    if gutshot:
        outs_count = actual_outs if actual_outs > 0 else 4
        return {
            'has_draw': True,
            'outs': outs_count,
            'completing_ranks': completing_list,
            'description': f'Gutshot straight draw ({outs_count} outs)'
        }

    return {'has_draw': False, 'outs': 0, 'completing_ranks': [], 'description': ''}


def _calculate_overcard_outs(
    hero: List[Tuple[int, int]],
    board_cards: List[Tuple[int, int]]
) -> Dict[str, Any]:
    """Calculate overcard outs when hero holds cards strictly higher than the highest board card."""
    if not hero or not board_cards:
        return {'outs': 0, 'description': ''}

    max_board_rank = max(c[0] for c in board_cards)
    all_ranks = [c[0] for c in hero + board_cards]
    hero_ranks = sorted({c[0] for c in hero})

    # If hero already has a pocket pair, don't count as unpaired overcards
    if len(hero) == 2 and hero[0][0] == hero[1][0]:
        return {'outs': 0, 'description': ''}

    overcards = [r for r in hero_ranks if r > max_board_rank and all_ranks.count(r) == 1]
    if not overcards:
        return {'outs': 0, 'description': ''}

    outs = sum(4 - all_ranks.count(r) for r in overcards)
    return {
        'outs': outs,
        'description': f"{len(overcards)} overcard{'s' if len(overcards) > 1 else ''} ({outs} outs)"
    }


def _calculate_improvement_outs(
    hero: List[Tuple[int, int]],
    board_cards: List[Tuple[int, int]]
) -> Dict[str, Any]:
    """Calculate made-hand improvement outs (e.g., pair to two-pair/trips, set to full house/quads)."""
    if not hero or not board_cards:
        return {'outs': 0, 'description': ''}

    all_ranks = [c[0] for c in hero + board_cards]
    rank_counts = {}
    for r in all_ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1

    hero_ranks = [c[0] for c in hero]
    pairs = [r for r, cnt in rank_counts.items() if cnt == 2]
    trips = [r for r, cnt in rank_counts.items() if cnt == 3]

    # Set / Trips improving to Full House or Quads
    if trips:
        board_unpaired = [r for r in {c[0] for c in board_cards} if rank_counts.get(r, 0) == 1]
        quad_outs = sum(4 - rank_counts[t] for t in trips)
        fh_outs = len(board_unpaired) * 3
        total = quad_outs + fh_outs
        return {
            'outs': total,
            'description': f"Trips/set improvement ({total} outs to full house/quads)"
        }

    # Pocket pair (unimproved) -> 2 outs to set
    if len(hero_ranks) == 2 and hero_ranks[0] == hero_ranks[1] and rank_counts.get(hero_ranks[0], 0) == 2:
        return {
            'outs': 2,
            'description': "Pocket pair to set (2 outs)"
        }

    # One pair using one hole card + one board card -> 2 outs to trips + 3 outs for kicker two-pair = 5 outs
    hero_paired = [r for r in set(hero_ranks) if rank_counts.get(r, 0) == 2]
    if len(pairs) == 1 and hero_paired:
        paired_rank = hero_paired[0]
        trip_outs = 4 - rank_counts[paired_rank]
        unpaired_kickers = [r for r in set(hero_ranks) if r != paired_rank and rank_counts.get(r, 0) == 1]
        two_pair_outs = sum(4 - rank_counts[k] for k in unpaired_kickers)
        total = trip_outs + two_pair_outs
        return {
            'outs': total,
            'description': f"Pair to two-pair/trips ({total} outs)"
        }

    # Two pair -> 4 outs to full house
    if len(pairs) >= 2:
        fh_outs = sum(4 - rank_counts[p] for p in pairs[:2])
        return {
            'outs': fh_outs,
            'description': f"Two pair to full house ({fh_outs} outs)"
        }

    return {'outs': 0, 'description': ''}


def _check_open_ended_straight(ranks: List[int]) -> bool:
    """Check if we have an open-ended straight draw (4 consecutive ranks with both ends open)."""
    if len(ranks) < 4:
        return False

    # Look for 4 consecutive ranks where both r_low - 1 >= -1 and r_high + 1 <= 12
    # (note: A-K-Q-J (9..12) and A-2-3-4 (-1..2) are one-ended gutshots, not open-ended!)
    for i in range(len(ranks) - 3):
        if ranks[i + 3] - ranks[i] == 3:
            if ranks[i] - 1 >= -1 and ranks[i + 3] + 1 <= 12:
                return True

    return False


def _check_gutshot_straight(
    ranks: List[int],
    known_cards: List[Tuple[int, int]]
) -> bool:
    """Check if we have a 4-out straight draw (strictly 4 of 5 ranks in a valid 5-card straight window)."""
    rank_set = set(ranks)
    if 12 in rank_set:
        rank_set = rank_set | {-1}

    if len(rank_set) < 4:
        return False

    # Exclude already-made straights
    for start in range(-1, 9):
        if all((start + offset) in rank_set for offset in range(5)):
            return False

    completing = set()
    for start in range(-1, 9):
        window = [start + offset for offset in range(5)]
        missing = [r for r in window if r not in rank_set]
        if len(missing) == 1:
            m = missing[0]
            completing.add(12 if m == -1 else m)

    return len(completing) == 1


def _calculate_overlap(
    flush_info: Dict[str, Any],
    straight_info: Dict[str, Any],
    known_cards: List[Tuple[int, int]]
) -> int:
    """Calculate exact overlap between flush and straight outs (straight-completing cards of the flush suit)."""
    if not flush_info['has_draw'] or not straight_info['has_draw']:
        return 0

    # Find the flush suit
    suits = [c[1] for c in known_cards]
    suit_counts = {s: suits.count(s) for s in range(4)}
    flush_suit = max(suit_counts, key=suit_counts.get)

    if suit_counts[flush_suit] != 4:
        return 0

    completing_ranks = straight_info.get('completing_ranks')
    if completing_ranks:
        known_set = set(known_cards)
        return sum(1 for r in completing_ranks if (r, flush_suit) not in known_set)

    return 2 if straight_info.get('outs', 0) >= 7 else 1


def _classify_draw(
    flush_info: Dict[str, Any],
    straight_info: Dict[str, Any]
) -> str:
    """Classify the type of draw."""
    if flush_info['has_draw'] and straight_info['has_draw']:
        if straight_info['outs'] >= 7:
            return 'open_straight_flush'
        return 'gutshot_flush'
    elif flush_info['has_draw']:
        return 'flush'
    elif straight_info['has_draw']:
        if straight_info['outs'] >= 7:
            return 'open_straight'
        return 'gutshot'
    return 'none'


def get_outs_simple(hero_hand: str, board: str) -> Tuple[int, str]:
    """
    Simple outs calculation returning just (count, description).
    
    Args:
        hero_hand: Hero's hole cards
        board: Board cards
    
    Returns:
        Tuple of (outs_count, description)
    """
    result = get_outs(hero_hand, board)
    return result['outs'], result['description']


def count_outs(hero_hand: str, board: str) -> int:
    """
    Get just the number of outs.
    
    Args:
        hero_hand: Hero's hole cards
        board: Board cards
    
    Returns:
        Number of outs
    """
    return get_outs(hero_hand, board)['outs']


def describe_draw(hero_hand: str, board: str) -> str:
    """
    Get a description of the draw.
    
    Args:
        hero_hand: Hero's hole cards
        board: Board cards
    
    Returns:
        Description string
    """
    return get_outs(hero_hand, board)['description']


if __name__ == "__main__":
    # Example usage
    print("Outs Calculator Demo")
    print("=" * 40)
    
    # Flush draw example
    outs, desc = get_outs_simple("AhKh", "QdJd8d")
    print(f"AhKh on QdJd8d: {outs} outs - {desc}")
    
    # Open-ended straight draw
    outs, desc = get_outs_simple("T9h", "Jh8h5c")
    print(f"T9h on Jh8h5c: {outs} outs - {desc}")
    
    # Gutshot
    outs, desc = get_outs_simple("T7h", "Jh9h5c")
    print(f"T7h on Jh9h5c: {outs} outs - {desc}")
    
    # Combined draw
    outs, desc = get_outs_simple("T9d", "Jd8d5d")
    print(f"T9d on Jd8d5d: {outs} outs - {desc}")
