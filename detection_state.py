"""Per-table confirmation of exact cards; no GUI or capture dependencies."""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CardReading:
    hand: str
    cards: Optional[Tuple[str, str]]
    rank_distances: Tuple[float, float]
    rank_margins: Tuple[float, float]
    suit_distances: Tuple[float, float]
    region: Optional[Tuple[float, float, float, float]] = None

    @property
    def reliable(self):
        return (self.cards is not None and self.cards[0] != self.cards[1]
                and max(self.rank_distances) <= 12000
                and min(self.rank_margins) >= 600
                and max(self.suit_distances) <= 10000)


class HandConfirmation:
    """Publish only consecutive matching observations from the same table.

    Missing/ambiguous observations invalidate advice immediately. A later
    identical hand must be confirmed again; old data never remains current.
    """
    def __init__(self, required=2):
        self.required = required
        self.reset()

    def reset(self):
        self.table = None
        self.candidate = None
        self.count = 0

    def update(self, result):
        table = result.get('table_id')
        cards = result.get('cards')
        key = tuple(sorted(cards)) if cards else None
        if not key or not result.get('reliable'):
            self.reset()
            return False
        if table != self.table or key != self.candidate:
            self.table, self.candidate, self.count = table, key, 1
        else:
            self.count += 1
        return self.count >= self.required


def validate_exact_cards(hand, board):
    """Validate postflop inputs without inventing suits or accepting duplicates."""
    ranks, suits = '23456789TJQKA', 'cdhs'
    def parse(text):
        text = text.replace(' ', '')
        if len(text) % 2:
            raise ValueError('Enter exact cards, for example AsKh')
        cards = tuple(text[i].upper() + text[i + 1].lower() for i in range(0, len(text), 2))
        if any(c[0] not in ranks or c[1] not in suits for c in cards):
            raise ValueError('Enter exact ranks and suits, for example AsKh')
        return cards
    hole, community = parse(hand), parse(board)
    if len(hole) != 2 or len(community) not in (3, 4, 5):
        raise ValueError('Enter two hole cards and 3–5 board cards')
    if len(set(hole + community)) != len(hole + community):
        raise ValueError('A card cannot appear twice')
    return ''.join(hole), ''.join(community)
