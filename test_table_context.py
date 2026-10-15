from copy import deepcopy
from pathlib import Path
import time
from unittest.mock import Mock

from PIL import Image
import pytest

from table_context import PreflopTracker, PostflopTracker, convert_amount, parse_amount, parse_blinds


def observation(bets=None, **overrides):
    bets = bets or {0: 0, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0}
    data = dict(complete=True, big_blind=200, small_blind=100, units='chips',
                bets=bets, stacks={s: 20000 - bet for s, bet in bets.items()},
                positions={0: 'BTN', 1: 'SB', 2: 'BB', 3: 'UTG', 4: 'MP', 5: 'CO'},
                pot=sum(bets.values()), call=max(bets.values()) - bets[3], board_present=False)
    data.update(overrides)
    return dict(table_id=42, cards=('As', 'Kh'), hand='AKo', reliable=True, preflop=data,
                position='UTG', captured_at=time.monotonic())


def test_open_and_confirmed_stack():
    tracker = PreflopTracker()
    first = tracker.update(observation())
    assert first['spot'] == 'open' and first['effective_bb'] is None
    assert tracker.update(observation())['effective_bb'] == 100


def test_open_raise_and_opener_position():
    tracker = PreflopTracker()
    tracker.update(observation())
    result = tracker.update(observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0}))
    assert result['spot'] == 'facing_open' and result['vs'] == 'BTN'
    assert tracker.update(observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0}))['spot'] == 'facing_open'


def test_transient_unreadable_frame_recovers_when_fresh_wagers_are_unchanged():
    tracker = PreflopTracker()
    tracker.update(observation())
    raised = observation({0:600,1:100,2:200,3:0,4:0,5:0})
    assert tracker.update(raised)['spot'] == 'facing_open'
    assert tracker.update(observation(complete=False))['spot'] is None
    assert tracker.update(raised)['spot'] == 'facing_open'
    assert tracker.raises == [0]
    assert not tracker.lost


def test_seat_change_during_read_gap_does_not_reuse_old_action():
    tracker = PreflopTracker()
    tracker.update(observation())
    tracker.update(observation(complete=False))
    changed = observation()
    changed['preflop']['positions'][0] = 'CO'
    assert tracker.update(changed)['spot'] is None
    assert tracker.lost


def test_facing_three_bet_after_hero_open():
    tracker = PreflopTracker()
    tracker.update(observation())
    tracker.update(observation({0: 0, 1: 100, 2: 200, 3: 500, 4: 0, 5: 0}, call=None))
    result = tracker.update(observation({0: 1500, 1: 100, 2: 200, 3: 500, 4: 0, 5: 0}))
    assert result['spot'] == 'facing_3bet'
    assert result['effective_bb'] == 100  # Contributions remain in starting stack.
    assert len(result['action_history']) == 2
    assert result['action_history'][0]['pos'] == 'UTG' and result['action_history'][0]['action'] == 'raise_to'
    assert result['action_history'][0]['amount_bb'] == 2.5
    assert result['action_history'][1]['pos'] == 'BTN' and result['action_history'][1]['action'] == 'raise_to'
    assert result['action_history'][1]['amount_bb'] == 7.5


def test_facing_four_bet_after_hero_three_bet():
    tracker = PreflopTracker()
    tracker.update(observation())
    tracker.update(observation({0: 500, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0}))
    tracker.update(observation({0: 500, 1: 100, 2: 200, 3: 1500, 4: 0, 5: 0}, call=None))
    result = tracker.update(observation({0: 4000, 1: 100, 2: 200, 3: 1500, 4: 0, 5: 0}))
    assert result['spot'] == 'facing_4bet'


@pytest.mark.parametrize('kind', ['late', 'gap', 'limp', 'callers', 'board', 'ambiguous', 'no_call', 'ante'])
def test_ambiguous_and_unsupported_context_is_not_guessed(kind):
    tracker = PreflopTracker()
    if kind not in ('late', 'ante'):
        tracker.update(observation())
    if kind == 'gap':
        tracker.update(observation(complete=False))
    if kind == 'limp':
        result = tracker.update(observation({0: 0, 1: 100, 2: 200, 3: 0, 4: 200, 5: 0}))
    elif kind == 'callers':
        tracker.update(observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0}))
        result = tracker.update(observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 600, 5: 0}))
    elif kind == 'board':
        result = tracker.update(observation(board_present=True))
    elif kind == 'ambiguous':
        result = tracker.update(observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 1800, 5: 0}))
    elif kind == 'no_call':
        result = tracker.update(observation(call=None))
    elif kind == 'ante':
        result = tracker.update(observation(pot=400))
    else:
        result = tracker.update(observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0}))
    assert result['spot'] is None


def test_reset_on_table_change_and_disappeared_cards():
    tracker = PreflopTracker()
    tracker.update(observation())
    raised = observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0})
    assert tracker.update(dict(raised, table_id=43))['spot'] is None
    tracker.update(dict(reliable=False))
    assert tracker.update(raised)['spot'] is None
    tracker.update(dict(reliable=False))
    assert tracker.update(observation())['spot'] == 'open'


def test_effective_depth_uses_shorter_aggressor_stack():
    tracker = PreflopTracker()
    tracker.update(observation())
    raised = observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0})
    raised['preflop']['stacks'][0] = 4400
    tracker.update(raised)
    assert tracker.update(raised)['effective_bb'] == 25


@pytest.mark.parametrize('text,expected', [('4,900', (4900, None)), ('24.5 BB', (24.5, 'bb')),
    ('$0.50', (.5, None)), ('4,90', None), ('Raise 400', None), ('nan', None)])
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_blinds_and_unit_roundtrip():
    assert parse_blinds('Spin & Gold 6-Max $0.25 - Blinds 10 | 20') == (10, 20)
    assert parse_blinds('Spin & Gold 6-Max $0.25 - Blinds 20 | 40') == (20, 40)
    assert parse_blinds('NLHP Green 08 - 100 / 200 [6]') == (100, 200)
    assert parse_blinds('NLHE $0.50/$1') == (.5, 1)
    assert parse_blinds('NLHE 1,000 / 2,000') == (1000, 2000)
    assert parse_blinds('No stakes') is None
    assert convert_amount(4900, 'chips', 'bb', 200) == 24.5
    assert convert_amount(24.5, 'bb', 'chips', 200) == 4900
    with pytest.raises(ValueError):
        convert_amount(100, 'chips', 'bb', None)


@pytest.fixture
def table():
    with Image.open(Path(__file__).parent / 'tests/fixtures/position_five_seats.png') as image:
        return image.convert('RGB')


def test_preflop_screenshot_to_guidance_and_units(table, monkeypatch):
    import tkinter as tk
    import ocr
    import rta
    if not ocr._tesseract_executable():
        pytest.skip('Tesseract unavailable')
    monkeypatch.setattr(ocr, 'find_ggpoker_window', lambda *a: (0, 0, 760, 538))
    monkeypatch.setattr(ocr, 'capture_window', lambda bounds: table)
    monkeypatch.setattr(ocr, '_WINDOW_IDS', {(0, 0, 760, 538): 42})
    reading = ocr.capture_and_read_with_position(include_context=True)
    assert reading['cards'] == ('As', '3s')
    data = reading['preflop']
    assert data['complete'] and data['big_blind'] == 200
    assert data['stacks'][3] == 4900 and data['call'] == 200
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk unavailable')
    root.withdraw()
    app = rta.RTAApp(root)
    try:
        app._play_sound = Mock()
        app.ocr_var.set(True)
        app._ocr_generation = 1
        for _ in range(2):
            app._accept_ocr_result(dict(reading, captured_at=time.monotonic()), 1)
        assert app.kind_var.get() == 'open'
        assert app.pos_var.get() == 'UTG'
        assert app.stack_var.get() == '20'
        assert '24.5 BB' in app.table_amounts_var.get()
        assert 'Your seat: UTG' in app.table_amounts_var.get()
        assert 'Wagers · ' in app.table_amounts_var.get()
        assert app._current_action in ('RAISE', 'FOLD')
        # Test automatic opener selection; no need to manually populate vs.
        raised = deepcopy(reading)
        raised['preflop']['bets'][5] = 600
        raised['preflop']['stacks'][5] -= 600
        raised['preflop']['call'] = 600
        raised['preflop']['pot'] = 900
        raised['captured_at'] = time.monotonic()
        app._accept_ocr_result(raised, 1)
        assert app.kind_var.get() == 'facing_open' and app.vs_var.get() == 'BTN'
        # Manual action survives later automatic reads.
        app.kind_var.set('facing_3bet')
        app._on_spot_change()
        app._accept_ocr_result(raised, 1)
        assert app.kind_var.get() == 'facing_3bet'
        app.stack_var.set('50')
        app._on_stack_change()
        app._accept_ocr_result(raised, 1)
        assert app.stack_var.get() == '50' and not app.auto_stack_var.get()
        # Converting fields preserves amounts and pot odds in both directions.
        app.mode_var.set('postflop')
        app._on_mode_change()
        app.board_entry.insert(0, '7s3h9d')
        app.pot_entry.insert(0, '2000')
        app.call_entry.insert(0, '1200')
        advice = Mock(return_value=dict(equity_pct=40, decision='CALL', reasoning='test'))
        monkeypatch.setattr(rta, 'get_postflop_advice', advice)
        app.amount_units_var.set('bb')
        app._on_amount_units_change()
        assert app.pot_entry.get() == '10' and app.call_entry.get() == '6'
        assert advice.call_args.kwargs['pot_size'] == 2000
        assert advice.call_args.kwargs['call_amount'] == 1200
        app.amount_units_var.set('chips')
        app._on_amount_units_change()
        assert app.pot_entry.get() == '2000' and app.call_entry.get() == '1200'
    finally:
        app._on_close()


def test_bb_table_display_is_converted_once(table, monkeypatch):
    import ocr
    positions = {5: 'BTN', 1: 'SB', 2: 'BB', 3: 'UTG', 4: 'CO'}
    texts = iter(['145.255 BB', '0.5 BB', '147.395 BB', '1 BB',
                  '24.5 BB', '0 BB', '254.4 BB', '0 BB', '33.33 BB', '0 BB'])
    monkeypatch.setattr(ocr, '_extract_text_from_image', lambda *a, **k: next(texts))
    monkeypatch.setattr(ocr, 'detect_pot_size', lambda img: 1.5)
    monkeypatch.setattr(ocr, 'detect_call_amount', lambda img: 1)
    result = ocr.detect_preflop_context(table, dict(seat_positions=positions, occupied_seats=[1, 2, 3, 4, 5]),
                                      table_name='NLHP - 100 / 200')
    assert result['units'] == 'bb'
    assert result['stacks'][3] == 4900
    assert result['bets'][1] == 100 and result['bets'][2] == 200
    assert result['pot'] == 300 and result['call'] == 200


def test_inconsistent_pot_does_not_advance_betting_history():
    tracker = PreflopTracker()
    tracker.update(observation())
    bets = {0: 600, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0}
    assert tracker.update(observation(bets, pot=300))['spot'] is None
    assert tracker.update(observation(bets))['spot'] == 'facing_open'


def test_missing_non_blind_wagers_inferred_zero_when_pot_equals_known_wagers(table, monkeypatch):
    import ocr
    positions = {2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'}
    # Seats 2 (CO) and 3 (BTN) wager OCR return unparseable text,
    # while SB (100) and BB (200) already sum to Total Pot (300).
    texts = iter(['20,000', 'noise', '20,000', 'puck', '19,900', '100', '19,800', '200'])
    monkeypatch.setattr(ocr, '_extract_text_from_image', lambda *a, **k: next(texts))
    monkeypatch.setattr(ocr, 'detect_pot_size', lambda img: 300)
    monkeypatch.setattr(ocr, 'detect_call_amount', lambda img: 200)
    result = ocr.detect_preflop_context(
        table,
        dict(seat_positions=positions, occupied_seats=[2, 3, 4, 5]),
        table_name='NLHP - 100 / 200',
    )
    assert result['complete']
    assert result['bets'][2] == 0 and result['bets'][3] == 0


def test_mid_hand_lost_tracker_exposes_inferred_spot_and_vs():
    # Single open raise mid-hand without prior baseline
    tracker = PreflopTracker()
    res_open = tracker.update(observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 0, 5: 0}))
    assert res_open['spot'] is None
    assert res_open.get('inferred_spot') == 'facing_open'
    assert res_open.get('inferred_vs') == 'BTN'

    # Hero opened (500 = 2.5 BB) and faces a single 3-bet (1500 = 7.5 BB) mid-hand
    tracker = PreflopTracker()
    res_3b = tracker.update(observation({0: 1500, 1: 100, 2: 200, 3: 500, 4: 0, 5: 0}))
    assert res_3b['spot'] is None
    assert res_3b.get('inferred_spot') == 'facing_3bet'
    assert res_3b.get('inferred_vs') == 'BTN'

    # Hero 3-bet (1500 = 7.5 BB) and faces a 4-bet (4000 = 20 BB) mid-hand
    tracker = PreflopTracker()
    res_4b = tracker.update(observation({0: 4000, 1: 100, 2: 200, 3: 1500, 4: 0, 5: 0}))
    assert res_4b['spot'] is None
    assert res_4b.get('inferred_spot') == 'facing_4bet'
    assert res_4b.get('inferred_vs') == 'BTN'

    # Multiway caller suppresses inferred_spot
    tracker = PreflopTracker()
    res_multi = tracker.update(observation({0: 600, 1: 100, 2: 200, 3: 0, 4: 600, 5: 0}))
    assert res_multi['spot'] is None
    assert res_multi.get('inferred_spot') is None


def test_postflop_tracker_multi_street_bet_and_reset():
    tracker = PostflopTracker()
    # Flop starts with pot=600, facing a 200 bet (pot=800, call=200)
    f1 = tracker.update({
        'table_id': 1,
        'cards': ('Ah', 'Kh'),
        'board': 'QdJd2s',
        'pot_size': 600.0,
        'call_amount': 0.0,
        'big_blind': 100.0,
    })
    assert f1['street'] == 'flop'
    assert f1['street_start_pot']['flop'] == 600.0
    assert f1['postflop_history'] == []

    f2 = tracker.update({
        'table_id': 1,
        'cards': ('Ah', 'Kh'),
        'board': 'QdJd2s',
        'pot_size': 800.0,
        'call_amount': 200.0,
        'big_blind': 100.0,
    })
    assert f2['current_street_wager'] == 200.0

    # Turn arrives after Hero called the 200 flop bet (pot=1000, call=0)
    t1 = tracker.update({
        'table_id': 1,
        'cards': ('Ah', 'Kh'),
        'board': 'QdJd2s5c',
        'pot_size': 1000.0,
        'call_amount': 0.0,
        'big_blind': 100.0,
    })
    assert t1['street'] == 'turn'
    assert len(t1['postflop_history']) == 1
    assert t1['postflop_history'][0]['street'] == 'flop'
    assert t1['postflop_history'][0]['action'] == 'bet_call'
    assert t1['postflop_history'][0]['amount'] == 200.0
    assert t1['postflop_history'][0]['amount_bb'] == 2.0

    # Turn checks through to River (pot still 1000, facing 400 river bet -> pot=1400, call=400)
    r1 = tracker.update({
        'table_id': 1,
        'cards': ('Ah', 'Kh'),
        'board': 'QdJd2s5c9h',
        'pot_size': 1400.0,
        'call_amount': 400.0,
        'big_blind': 100.0,
    })
    assert r1['street'] == 'river'
    assert len(r1['postflop_history']) == 2
    assert r1['postflop_history'][1]['street'] == 'turn'
    assert r1['postflop_history'][1]['action'] == 'check_through'

    # Incompatible board or new hand resets cleanly
    reset_res = tracker.update({
        'table_id': 1,
        'cards': ('Ah', 'Kh'),
        'board': '2c3c4c',
        'pot_size': 300.0,
        'call_amount': 0.0,
        'big_blind': 100.0,
    })
    assert reset_res['street'] == 'flop'
    assert reset_res['postflop_history'] == []
