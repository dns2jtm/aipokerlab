"""Regression coverage for the user's GGPoker postflop screenshot."""
from pathlib import Path
from unittest.mock import Mock
import threading
import time

import pytest
from PIL import Image, ImageDraw

import ocr


FIXTURE = Path(__file__).parent / 'tests/fixtures/ggpoker_postflop_739.png'


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setattr(ocr, '_CLIENT', 'ggpoker')
    with Image.open(FIXTURE) as image:
        return image.convert('RGB')


@pytest.mark.parametrize('scale', [.5, .75, 1, 1.5])
def test_board_at_different_window_and_retina_sizes(table, scale):
    table = table.resize((round(table.width * scale), round(table.height * scale)))
    info = ocr.detect_board_cards_advanced(table)
    assert info['board'] == '7s3h9d'
    assert info['street'] == 'flop'


@pytest.mark.parametrize('scale', [.5, .75, 1, 1.5])
def test_actual_amount_ocr(table, scale):
    if not ocr._tesseract_executable():
        pytest.skip('Tesseract not installed')
    table = table.resize((round(table.width * scale), round(table.height * scale)))
    assert ocr.detect_pot_size(table) == 2000
    assert ocr.detect_call_amount(table) == 1200


@pytest.mark.parametrize('text,expected', [('Call\n1,200', 1200), ('Call $12.50', 12.5),
    ('Check', 0), ('Raise to 2,400', None), ('', None), ('Call', None),
    ('Call 1,20', None)])
def test_call_amount_requires_explicit_label(table, monkeypatch, text, expected):
    monkeypatch.setattr(ocr, '_extract_text_from_image', lambda img: text)
    assert ocr.detect_call_amount(table) == expected


@pytest.mark.parametrize('text,expected', [('Total Pot : 2,000', 2000),
    ('Pot: £12.50', 12.5), ('2,000', None), ('', None)])
def test_pot_requires_explicit_label(table, monkeypatch, text, expected):
    monkeypatch.setattr(ocr, '_extract_text_from_image', lambda img: text)
    assert ocr.detect_pot_size(table) == expected


def test_missing_tesseract_is_reported(table, monkeypatch):
    monkeypatch.setattr(ocr, '_tesseract_executable', lambda: None)
    with pytest.raises(RuntimeError, match='Tesseract'):
        ocr.detect_pot_size(table)


def test_missing_suit_and_partial_board_are_rejected(table):
    card = table.crop((500, 505, 624, 680))
    ImageDraw.Draw(card).rectangle((0, 56, 56, 105), fill='white')
    assert ocr._read_single_board_card(card) is None
    # An unreadable third card must not produce a plausible two-card board.
    ImageDraw.Draw(table).rectangle((788, 505, 912, 680), fill=(20, 100, 20))
    assert ocr.detect_board_cards(table) is None


def test_blank_table_has_no_board():
    assert ocr.detect_board_cards(Image.new('RGB', (850, 615), (20, 100, 20))) is None


def test_club_board_card_and_translucent_banner_are_read(table):
    # Replace the first board card's spade (7s) with a GGPoker 3-lobed club (7c)
    card_x, card_y = 500, 505
    draw = ImageDraw.Draw(table)
    draw.rectangle((card_x + 4, card_y + 56, card_x + 54, card_y + 104), fill='white')
    # Draw 3-lobed club matching GGPoker's corner club geometry
    sx, sy = card_x + 8, card_y + 60
    draw.ellipse((sx + 10, sy + 1, sx + 28, sy + 19), fill='black')
    draw.ellipse((sx + 1, sy + 15, sx + 19, sy + 33), fill='black')
    draw.ellipse((sx + 19, sy + 15, sx + 37, sy + 33), fill='black')
    draw.ellipse((sx + 12, sy + 13, sx + 26, sy + 27), fill='black')
    draw.polygon([(sx + 17, sy + 22), (sx + 21, sy + 22), (sx + 25, sy + 37), (sx + 13, sy + 37)], fill='black')
    assert ocr.detect_board_cards(table) == '7c3h9d'

    # Simulate a dark translucent table timer banner across the lower 65% of the middle card (3h)
    mid_x0, mid_y0, mid_x1, mid_y1 = 640, 560, 775, 685
    for yy in range(mid_y0, mid_y1):
        for xx in range(mid_x0, mid_x1):
            r, g, b = table.getpixel((xx, yy))
            table.putpixel((xx, yy), (int(r * 0.29), int(g * 0.29), int(b * 0.29)))
    assert ocr.detect_board_cards(table) == '7c3h9d'


def test_screenshot_flows_through_capture_to_postflop_ui(table, monkeypatch):
    import tkinter as tk
    import rta
    if not ocr._tesseract_executable():
        pytest.skip('Tesseract not installed')
    monkeypatch.setattr(ocr, 'find_ggpoker_window', lambda *args: (0, 0, 1700, 1230))
    monkeypatch.setattr(ocr, 'capture_window', lambda bounds: table)
    monkeypatch.setattr(ocr, '_WINDOW_IDS', {(0, 0, 1700, 1230): 42})
    result = ocr.capture_and_read_full_state()
    assert result['error'] is None
    assert result['cards'] == ('As', 'Kh')
    assert (result['board'], result['pot_size'], result['call_amount']) == ('7s3h9d', 2000, 1200)
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display unavailable')
    root.withdraw()
    app = rta.RTAApp(root)
    try:
        app._play_sound = Mock()
        app.ocr_var.set(True)
        app._ocr_generation = 1
        observation = dict(result, hand='AKo', reliable=True, captured_at=time.monotonic())
        app._accept_ocr_result(observation, 1)
        app._accept_ocr_result(observation, 1)
        app.mode_var.set('postflop')
        app._on_mode_change()
        stop = threading.Event()
        app._accept_postflop_result(dict(result, captured_at=time.monotonic()), stop)
        assert app.board_entry.get() == '7s3h9d'
        assert app.pot_entry.get() == '2000'
        assert app.call_entry.get() == '1200'
        assert app._current_action in ('CALL', 'FOLD', 'RAISE')
        assert app.equity_var.get() != 'Equity: --'
        assert 'detected' in app.detection_status_label.cget('text')
        # OCR failure must invalidate prior automatic values and show its cause.
        app._accept_postflop_result(dict(status='error', error='Amount OCR needs Tesseract'), stop)
        assert app._current_action is None
        assert app.board_entry.get() == app.pot_entry.get() == app.call_entry.get() == ''
        assert 'Tesseract' in app.detection_status_label.cget('text')
        # Values manually supplied after the failure survive another failed read.
        app.pot_entry.insert(0, '2100')
        app._accept_postflop_result(dict(status='error', error='Screenshot failed'), stop)
        assert app.pot_entry.get() == '2100'
        # Even if hole cards are missed on one postflop frame, confirmed _exact_cards still allow board reading
        # across the combined (_accept_ocr_result, _accept_postflop_result) dispatch.
        missed_hole = dict(result, hand=None, cards=None, reliable=False, captured_at=time.monotonic())
        app._accept_ocr_result(missed_hole, 1)
        app._accept_postflop_result(missed_hole, stop)
        assert app.board_entry.get() == '7s3h9d'
    finally:
        app._on_close()


def test_auto_street_switching_and_no_button_call_fallback(monkeypatch):
    import tkinter as tk
    import rta
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display unavailable')
    root.withdraw()
    app = rta.RTAApp(root)
    try:
        app._play_sound = Mock()
        app.ocr_var.set(True)
        app._ocr_generation = 1
        assert app.mode == 'preflop'

        # 1. Confirm hand on flop: auto-switches from preflop to postflop and defaults call to 0
        flop_frame = dict(
            hand='AKo', cards=('As', 'Kh'), reliable=True, status='detected',
            position='BTN', active_opponents=2, table_id=42, captured_at=time.monotonic(),
            preflop=dict(
                complete=False, big_blind=200, small_blind=100, units='chips',
                positions={3: 'BTN', 4: 'SB', 5: 'BB'},
                pot=1800, call=None, inferred_call=0,
                board_present=True, board='7s3h9d', board_info={'street': 'flop'},
            ),
        )
        app._accept_ocr_result(flop_frame, 1)
        app._accept_ocr_result(dict(flop_frame, captured_at=time.monotonic()), 1)
        assert app.mode == 'postflop'
        assert app.board_entry.get() == '7s3h9d'
        assert app.pot_entry.get() == '1800'
        assert app.call_entry.get() == '0'
        assert app._active_opponents == 2
        assert app._current_action in ('CALL', 'FOLD', 'RAISE', 'BET', 'CHECK')
        assert app.equity_var.get() != 'Equity: --'

        # 2. Postflop update with facing wager inferred from seat bets when call_amount is None
        stop = threading.Event()
        app._accept_postflop_result(dict(
            cards=('As', 'Kh'), hole_cards='AKo', reliable=True, status='success',
            board='7s3h9d', board_info={'street': 'flop'},
            pot_size=2750, call_amount=None, inferred_call_amount=950,
            active_opponents=2, position='BTN', table_id=42, captured_at=time.monotonic(),
        ), stop)
        assert app.pot_entry.get() == '2750'
        assert app.call_entry.get() == '950'
        assert 'facing wager detected' in app.detection_status_label.cget('text')

        # 3. Next hand starts preflop with no board: auto-switches back to preflop
        new_hand = dict(
            hand='QQ', cards=('Qs', 'Qh'), reliable=True, status='detected',
            position='CO', active_opponents=5, table_id=42, captured_at=time.monotonic(),
            preflop=dict(
                complete=True, big_blind=200, small_blind=100, units='chips',
                bets={0: 0, 1: 0, 2: 0, 3: 0, 4: 100, 5: 200},
                stacks={0: 20000, 1: 20000, 2: 20000, 3: 20000, 4: 19900, 5: 19800},
                positions={0: 'UTG', 1: 'MP', 2: 'CO', 3: 'CO', 4: 'SB', 5: 'BB'},
                pot=300, call=200, board_present=False,
            ),
        )
        app._accept_ocr_result(new_hand, 1)
        app._accept_ocr_result(dict(new_hand, captured_at=time.monotonic()), 1)
        assert app.mode == 'preflop'
        assert app.board_entry.get() == ''
    finally:
        app._on_close()


def test_dimmed_seats_remain_occupied_while_active_opponents_tracks_unfolded():
    from position_detector import PositionDetector, detect_position_and_spot
    W, H = 800, 600
    img = Image.new('RGB', (W, H), (28, 72, 52))
    draw = ImageDraw.Draw(img)
    det = PositionDetector()
    # Draw all 6 seat nameplates; seats 2 and 3 (Hero) have dimmed text (105, 105, 105),
    # while seats 0, 1, 4, 5 have bright text (180, 180, 180).
    for idx, (cx, cy) in enumerate(det.SEATS):
        bx0, by0 = int((cx - .055) * W), int(cy * H)
        bx1, by1 = int((cx + .055) * W), int((cy + .065) * H)
        draw.rectangle([bx0, by0, bx1, by1], fill=(20, 24, 30))
        color = (105, 105, 105) if idx in (2, 3) else (180, 180, 180)
        # Fill ~12% of the nameplate with text-colored pixels
        tx0, ty0 = bx0 + 6, by0 + 6
        tx1, ty1 = bx0 + int((bx1 - bx0) * 0.65), by0 + int((by1 - by0) * 0.50)
        draw.rectangle([tx0, ty0, tx1, ty1], fill=color)
    # Draw yellow dealer button with dark 'D' near Seat 4 (BTN) -> Hero (Seat 3) is CO
    dx, dy = int(det.SEATS[4][0] * W + 35), int(det.SEATS[4][1] * H - 25)
    draw.ellipse([dx - 9, dy - 9, dx + 9, dy + 9], fill=(235, 195, 45))
    draw.rectangle([dx - 2, dy - 3, dx + 2, dy + 3], fill=(40, 35, 30))

    info = detect_position_and_spot(img)
    assert info['occupied_seats'] == [0, 1, 2, 3, 4, 5]
    assert info['position'] == 'CO'
    assert info['active_seats'] == [0, 1, 4, 5]
    assert info['active_opponents'] == 4


def test_multiway_postflop_advice_passes_num_opponents():
    from postflop import get_postflop_advice
    hu = get_postflop_advice('AsKh', '7s3h9d', pot_size=2000, call_amount=0, num_opponents=1, iterations=600)
    mw = get_postflop_advice('AsKh', '7s3h9d', pot_size=2000, call_amount=0, num_opponents=3, iterations=600)
    assert mw['num_opponents'] == 3
    assert mw['equity_pct'] < hu['equity_pct']


def test_postflop_suit_collision_and_partial_board_never_stuck(monkeypatch):
    import tkinter as tk
    import rta
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display unavailable')
    root.withdraw()
    app = rta.RTAApp(root)
    try:
        app._play_sound = Mock()
        app.ocr_var.set(True)
        app._ocr_generation = 1

        # 1. Confirm KJs preflop where tilted clubs were read as spades ('Ks', 'Js')
        preflop_frame = dict(
            hand='KJs', cards=('Ks', 'Js'), reliable=True, status='detected',
            position='BTN', active_opponents=2, table_id=42, captured_at=time.monotonic(),
            preflop=dict(
                complete=True, big_blind=200, small_blind=100, units='chips',
                bets={3: 500, 4: 100, 5: 500},
                stacks={3: 19500, 4: 19900, 5: 19500},
                positions={3: 'BTN', 4: 'SB', 5: 'BB'},
                pot=1100, call=0, board_present=False,
            ),
        )
        app._accept_ocr_result(preflop_frame, 1)
        app._accept_ocr_result(dict(preflop_frame, captured_at=time.monotonic()), 1)
        assert app.mode == 'preflop'
        assert app.hand == 'KJs'

        # 2. Mid-deal frame where board_present=True and board=None must never set 'Waiting for betting context'
        mid_deal = dict(
            preflop_frame,
            captured_at=time.monotonic(),
            preflop=dict(
                preflop_frame['preflop'],
                board_present=True, board=None,
            ),
        )
        app._accept_ocr_result(mid_deal, 1)
        assert 'Waiting for betting context' not in app.advice_var.get()

        # 3. Flop frame with Js7d2h (colliding with hole card 'Js') and pot=None (moving chips):
        #    disambiguates hole cards to ('Kc', 'Jc'), switches to postflop, and falls back pot to sum(bets)
        flop_collision = dict(
            preflop_frame,
            captured_at=time.monotonic(),
            preflop=dict(
                preflop_frame['preflop'],
                pot=None, call=None, inferred_call=0,
                board_present=True, board='Js7d2h', board_info={'street': 'flop'},
            ),
        )
        app._accept_ocr_result(flop_collision, 1)
        assert app.mode == 'postflop'
        assert app._exact_cards == ('Kc', 'Jc')
        assert app.board_entry.get() == 'Js7d2h'
        assert app.pot_entry.get() == '1100'
        assert app._current_action in ('CALL', 'FOLD', 'RAISE', 'BET', 'CHECK')
    finally:
        app._on_close()


