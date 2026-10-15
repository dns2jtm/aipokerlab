from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

import ocr
from detection_state import CardReading, HandConfirmation, validate_exact_cards
from position_detector import PositionDetector, Spot, detect_position_and_spot

FIXTURES = Path(__file__).parent / 'tests' / 'fixtures'


@pytest.mark.parametrize('filename,cards', [
    ('ggpoker_AJo.png', ('Ah', 'Jd')), ('ggpoker_53o.png', ('5h', '3d')),
    ('ggpoker_87s.png', ('8h', '7h')), ('ggpoker_A3s.png', ('As', '3s')),
    ('ggpoker_T4s.png', ('Ts', '4s')),
])
@pytest.mark.parametrize('scale', [.75, 1, 1.5])
def test_exact_suits_survive_recognition(filename, cards, scale):
    with Image.open(FIXTURES / filename) as image:
        if image.height == 196:
            full = Image.new('RGB', (406, 274), 'white')
            full.paste(image)
        else:
            full = image.copy()
    full = full.resize((round(full.width * scale), round(full.height * scale)))
    reading = ocr._read_region_cards(full, dict(x=0, y=0, w=1, h=1))
    assert reading.cards == cards
    assert reading.reliable


def observation(cards=('Ts', '4s'), table=42, reliable=True):
    return dict(cards=cards, table_id=table, reliable=reliable)


def test_temporal_confirmation_and_invalidation():
    state = HandConfirmation()
    assert not state.update(observation())
    assert state.update(observation())
    # A changing rank/suit must not preserve the old recommendation.
    assert not state.update(observation(('Ts', '4h')))
    assert state.update(observation(('Ts', '4h')))
    assert not state.update(dict(cards=None))
    assert not state.update(observation(('Ts', '4h')))
    assert state.update(observation(('Ts', '4h')))


def test_identical_hand_on_another_table_requires_confirmation():
    state = HandConfirmation()
    state.update(observation())
    assert state.update(observation())
    assert not state.update(observation(table=43))
    assert state.update(observation(table=43))


def test_ambiguity_resets_confirmation():
    state = HandConfirmation()
    state.update(observation())
    assert not state.update(observation(reliable=False))
    assert not state.update(observation())
    assert state.update(observation())


@pytest.mark.parametrize('cards,distances,margins,suits', [
    (None, (1000, 1000), (1000, 1000), (1000, 1000)),
    (('As', 'As'), (1000, 1000), (1000, 1000), (1000, 1000)),
    (('As', '3s'), (13000, 1000), (1000, 1000), (1000, 1000)),
    (('As', '3s'), (1000, 1000), (100, 1000), (1000, 1000)),
    (('As', '3s'), (1000, 1000), (1000, 1000), (12000, 1000)),
])
def test_uncertain_reading_cannot_be_published(cards, distances, margins, suits):
    assert not CardReading('A3s', cards, distances, margins, suits).reliable


@pytest.mark.parametrize('hand,board', [('T4s', 'AsJs2s'), ('TsTs', 'AsJs2s'),
                                       ('Ts4s', 'TsJs2s'), ('Ts4s', 'AsJs'),
                                       ('Ts4s', 'AsJs2x')])
def test_postflop_rejects_unknown_or_impossible_cards(hand, board):
    with pytest.raises(ValueError):
        validate_exact_cards(hand, board)


def test_postflop_preserves_actual_suits():
    assert validate_exact_cards('Ts4s', 'AsJs2s') == ('Ts4s', 'AsJs2s')


@pytest.mark.parametrize('filename,expected', [('position_five_seats.png', 'UTG'),
                                              ('position_hero_button.png', 'BTN')])
def test_dealer_and_seats_from_real_tables(filename, expected):
    result = detect_position_and_spot(Image.open(FIXTURES / filename))
    assert result['dealer_button'] is not None
    assert result['position'] == expected
    assert result['spot'] is None
    assert result['status'] == 'partial'


def test_no_button_does_not_invent_bb_or_open():
    result = detect_position_and_spot(Image.new('RGB', (760, 538), (20, 100, 20)))
    assert result['position'] is result['spot'] is None


@pytest.mark.parametrize('text,expected', [('you fold', None), ('you raise to 500', None),
    ('unreadable', None), ('facing a raise', Spot.FACING_OPEN),
    ('facing 3bet', Spot.FACING_3BET), ('facing 4bet', Spot.FACING_4BET),
    ('folded to you', Spot.OPEN)])
def test_action_requires_explicit_evidence(text, expected):
    assert PositionDetector().detect_spot_from_text(text) == expected


def test_capture_cards_and_position_use_one_image(monkeypatch):
    image = Image.new('RGB', (1200, 800), 'green')
    reading = CardReading('T4s', ('Ts', '4s'), (2000, 2000), (1000, 1000), (1000, 1000))
    capture = Mock(return_value=image)
    position = Mock(return_value={'position': 'BTN', 'spot': None})
    monkeypatch.setattr(ocr, 'find_ggpoker_window', lambda: (0, 0, 1200, 800))
    monkeypatch.setattr(ocr, 'capture_window', capture)
    monkeypatch.setattr(ocr, '_read_hand_with_fallback', lambda *a, **k: reading)
    monkeypatch.setattr(ocr, 'detect_position_and_spot', position)
    result = ocr.capture_and_read_with_position()
    assert capture.call_count == 1
    assert position.call_args.args[0] is image
    assert result['cards'] == ('Ts', '4s')
    assert result['reliable']


def test_memory_units_on_macos(monkeypatch):
    import resource
    from types import SimpleNamespace
    monkeypatch.setattr(ocr.sys, 'platform', 'darwin')
    monkeypatch.setattr(resource, 'getrusage', lambda *_: SimpleNamespace(ru_maxrss=123 * 1024**2))
    assert ocr.MemoryMonitor().get_memory_usage_mb() == 123


def test_uncertain_primary_crop_can_recover_from_offset(monkeypatch):
    uncertain = CardReading('A3s', None, (1000, 1000), (1000, 1000), (float('inf'), 1000))
    certain = CardReading('A3s', ('As', '3s'), (1000, 1000), (1000, 1000), (1000, 1000))
    reads = iter((uncertain, certain))
    monkeypatch.setattr(ocr, '_read_region_cards', lambda *a, **k: next(reads))
    monkeypatch.setattr(ocr, '_CLIENT', 'ggpoker')
    monkeypatch.setattr(ocr, '_region_offsets', lambda region: iter([region, dict(region, y=.76)]))
    assert ocr._read_hand_with_fallback(Image.new('RGB', (100,100)), detailed=True) is certain


def test_no_suit_evidence_cannot_become_confirmed_from_ink_color():
    from test_ocr import _make_window
    reading = ocr._read_region_cards(_make_window(), ocr.CARD_REGION)
    assert reading.hand == 'AKs'  # Legacy shorthand API remains supported.
    assert reading.cards is None
    assert not reading.reliable


@pytest.mark.parametrize('occupied,dealer,expected', [
    ([0,1,2,3,4,5], 0, 'UTG'), ([0,1,2,3,4,5], 1, 'BB'),
    ([0,1,2,3,4,5], 2, 'SB'), ([0,1,2,3,4,5], 3, 'BTN'),
    ([0,1,2,3,4,5], 4, 'CO'), ([0,1,2,3,4,5], 5, 'MP'),
    ([1,2,3,4,5], 5, 'UTG'), ([1,2,3,5], 5, 'CO'),
    ([1,2,3], 1, 'BB'), ([1,3], 1, 'BB'),
])
def test_position_counts_seats_clockwise_not_geometric_angle(monkeypatch, occupied, dealer, expected):
    # Isolate ordering from pixel detection (real images cover the latter).
    detector = PositionDetector()
    detector.unknown_seats = []
    monkeypatch.setattr(detector, 'detect_occupied_seats', lambda img: occupied)
    image = Image.new('RGB', (1000,1000))
    x,y = detector.SEATS[dealer]
    assert detector.detect_hero_position(image, (x*1000,y*1000)).value == expected


def test_ambiguous_seat_map_does_not_publish_position(monkeypatch):
    detector = PositionDetector()
    detector.unknown_seats = [0]
    monkeypatch.setattr(detector, 'detect_occupied_seats', lambda img: [1,2,3,4,5])
    x,y = detector.SEATS[5]
    assert detector.detect_hero_position(Image.new('RGB',(1000,1000)), (x*1000,y*1000)) is None
