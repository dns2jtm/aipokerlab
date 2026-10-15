"""GUI integration exercised with isolated capture/monitoring and real Tk widgets."""
import time
from unittest.mock import Mock
import tkinter as tk
import pytest
from PIL import Image
from pathlib import Path
import rta


def test_confirmed_cards_and_ui_lifecycle(monkeypatch):
    # Exercise real Tk widgets with capture, logging and monitoring isolated.
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display is unavailable')
    root.withdraw()
    app = rta.RTAApp(root)
    app._play_sound = Mock()
    app.ocr_var.set(True)
    app._ocr_generation = 1
    result = dict(hand='T4s', cards=('Ts', '4s'), reliable=True, table_id=42,
                  captured_at=time.monotonic(), position='BTN', spot=None,
                  preview=Image.open(Path(__file__).parent / 'tests/fixtures/ggpoker_T4s.png'))
    app._accept_ocr_result(result, 1)
    assert app.hand is None
    app._accept_ocr_result(result, 1)
    assert app.hand == 'T4s' and app._exact_cards == ('Ts', '4s')
    assert app.pos_var.get() == 'BTN' and app.kind_var.get() == ''
    assert app._current_action is None
    app.kind_var.set('open')
    app._on_spot_change()
    assert app._current_action is not None
    app.mode_var.set('postflop')
    app._on_mode_change()
    assert app._current_action is None  # No made-up default board/pot.
    for entry, value in [(app.board_entry,'AsJs2s'),(app.pot_entry,'100'),(app.call_entry,'0')]:
        entry.insert(0,value)
    advice = Mock(return_value=dict(equity_pct=80,decision='CHECK',reasoning='test'))
    monkeypatch.setattr(rta, 'get_postflop_advice', advice)
    app._big_blind = 2.0
    app._preflop_context = {'effective_bb': 100}
    app._refresh_postflop()
    assert advice.call_args.kwargs['hero_hand'] == 'Ts4s'
    assert advice.call_args.kwargs['call_amount'] == 0
    assert advice.call_args.kwargs['effective_stack'] == 200.0
    assert advice.call_args.kwargs['aggression_factor'] == app._strategy_manager.config.aggression_factor
    assert advice.call_args.kwargs['profile'] == app._strategy_manager.config.profile.value
    assert 'opponent_range' in advice.call_args.kwargs
    app._accept_ocr_result(dict(status='watching', message='No cards', captured_at=time.monotonic()),1)
    assert app.hand is None and app._exact_cards is None and app._current_action is None
    # Ignore callbacks from an earlier OCR worker.
    app._accept_ocr_result(result, 0)
    assert app.hand is None
    app._accept_ocr_result(result, 1)
    app._accept_ocr_result(result, 1)
    assert app._auto_hand_current
    app._last_frame_time = time.monotonic() - 10
    app._check_ocr_freshness(1)
    assert not app._auto_hand_current and app._current_action is None

    # Verify that when preflop context has a transient read gap (e.g. 'Re-reading BTN wager'),
    # confirmed hole cards still receive actionable Call/Fold/Raise guidance using the fallback spot.
    app.mode_var.set('preflop')
    app._on_mode_change()
    reread_frame = dict(
        hand='AKs', cards=('As', 'Ks'), reliable=True, table_id=42,
        captured_at=time.monotonic(), position='BTN', spot=None,
        preflop=dict(
            complete=False,
            big_blind=200,
            small_blind=100,
            units='chips',
            bets={3: None, 4: 100, 5: 200},
            stacks={3: 20000, 4: 19900, 5: 19800},
            positions={3: 'BTN', 4: 'SB', 5: 'BB'},
            pot=300,
            call=200,
            board_present=False,
            error='Re-reading BTN wager',
        ),
    )
    app._accept_ocr_result(reread_frame, 1)
    app._accept_ocr_result(reread_frame, 1)
    assert app.hand == 'AKs'
    assert app._current_action == 'RAISE'
    assert 'RAISE' in app.advice_var.get()
    assert 'Re-reading BTN wager' in app.advice_detail.get()
    assert 'using BTN Open' in app.advice_detail.get()

    # Verify Big Blind with an occluded opener wager (pot > sb + bb) infers facing_open vs that opener
    # instead of returning None / 'Waiting for betting context'.
    bb_reread_frame = dict(
        hand='AJs', cards=('As', 'Js'), reliable=True, table_id=42,
        captured_at=time.monotonic(), position='BB', spot=None,
        preflop=dict(
            complete=False,
            big_blind=200,
            small_blind=100,
            units='chips',
            bets={1: None, 2: 100, 3: 200},
            stacks={1: 19400, 2: 19900, 3: 19800},
            positions={1: 'BTN', 2: 'SB', 3: 'BB'},
            pot=900,
            call=400,
            board_present=False,
            error='Re-reading BTN wager',
        ),
    )
    app._accept_ocr_result(bb_reread_frame, 1)
    app._accept_ocr_result(bb_reread_frame, 1)
    assert app.hand == 'AJs'
    assert app._current_action in ('CALL', '3-BET', 'RAISE')
    assert 'Waiting for betting context' not in app.advice_var.get()
    assert 'using BB vs BTN Open' in app.advice_detail.get()

    # Verify transient position=None on a subsequent frame of the same hand preserves previously detected position.
    flicker_pos_frame = dict(bb_reread_frame, position=None, preflop=dict(bb_reread_frame['preflop'], positions={}))
    app._accept_ocr_result(flicker_pos_frame, 1)
    assert app.pos_var.get() == 'BB'
    assert app._current_action is not None

    # Verify that if Frame 1 was 'open' and Frame 2 has an opponent raise with a transient read gap,
    # the UI Situation updates to 'facing_open' and 'vs' instead of sticking to stale 'open'.
    open_frame = dict(
        hand='AQo', cards=('Ah', 'Qd'), reliable=True, table_id=42,
        captured_at=time.monotonic(), position='BTN', spot=None,
        preflop=dict(
            complete=True, big_blind=200, small_blind=100, units='chips',
            bets={2: 0, 3: 0, 4: 100, 5: 200},
            stacks={2: 20000, 3: 20000, 4: 19900, 5: 19800},
            positions={2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'},
            pot=300, call=200, board_present=False,
        ),
    )
    app._accept_ocr_result(open_frame, 1)
    app._accept_ocr_result(open_frame, 1)
    assert app.kind_var.get() == 'open'
    co_raised_with_gap = dict(
        open_frame,
        captured_at=time.monotonic(),
        preflop=dict(
            complete=False, big_blind=200, small_blind=100, units='chips',
            bets={2: 600, 3: None, 4: 100, 5: 200},
            stacks={2: 19400, 3: 20000, 4: 19900, 5: 19800},
            positions={2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'},
            pot=900, call=600, board_present=False, error='Re-reading BTN wager',
        ),
    )
    app._accept_ocr_result(co_raised_with_gap, 1)
    assert app.kind_var.get() == 'facing_open'
    assert app.vs_var.get() == 'CO'
    assert 'using BTN vs CO Open' in app.advice_detail.get()

    # Verify facing_3bet fallback inference when hero already opened and opponent 3-bets with a read gap.
    three_bet_with_gap = dict(
        open_frame,
        captured_at=time.monotonic(),
        preflop=dict(
            complete=False, big_blind=200, small_blind=100, units='chips',
            bets={2: None, 3: 500, 4: 1800, 5: 200},
            stacks={2: 20000, 3: 19500, 4: 18200, 5: 19800},
            positions={2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'},
            pot=2500, call=1300, board_present=False, error='Re-reading CO wager',
        ),
    )
    app._accept_ocr_result(three_bet_with_gap, 1)
    assert app.kind_var.get() == 'facing_3bet'

    # Verify limped pot resolves to iso_raise and never gets stuck on 'Waiting for betting context'.
    limp_frame = dict(
        open_frame,
        captured_at=time.monotonic(),
        preflop=dict(
            complete=True, big_blind=200, small_blind=100, units='chips',
            bets={2: 200, 3: 0, 4: 100, 5: 200},
            stacks={2: 19800, 3: 20000, 4: 19900, 5: 19800},
            positions={2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'},
            pot=500, call=200, board_present=False,
        ),
    )
    app._accept_ocr_result(limp_frame, 1)
    assert app.kind_var.get() == 'iso_raise'
    assert app.vs_var.get() == 'CO'
    assert app._current_action in ('RAISE', 'CALL', 'FOLD')
    assert 'Waiting for betting context' not in app.advice_var.get()
    assert 'Pick a valid spot' not in app.advice_var.get()

    # Verify open + caller (multiway) resolves to squeeze and never gets stuck on 'Waiting for betting context'.
    squeeze_frame = dict(
        open_frame,
        captured_at=time.monotonic(),
        preflop=dict(
            complete=True, big_blind=200, small_blind=100, units='chips',
            bets={1: 600, 2: 600, 3: 0, 4: 100, 5: 200},
            stacks={1: 19400, 2: 19400, 3: 20000, 4: 19900, 5: 19800},
            positions={1: 'MP', 2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'},
            pot=1500, call=600, board_present=False,
        ),
    )
    app._accept_ocr_result(squeeze_frame, 1)
    assert app.kind_var.get() == 'squeeze'
    assert app.vs_var.get() == 'MP'
    assert app._current_action in ('SQUEEZE', '3-BET', 'RAISE', 'CALL', 'FOLD')
    assert 'Waiting for betting context' not in app.advice_var.get()
    assert 'Pick a valid spot' not in app.advice_var.get()

    # Verify manual typing of 4-char exact cards ('Ah Kd') preserves _exact_cards and does not show Invalid hand
    app.hand_entry.delete(0, tk.END)
    app.hand_entry.insert(0, 'Ah Kd')
    app._on_hand_type()
    assert app.hand == 'AKo'
    assert app._exact_cards == ('Ah', 'Kd')
    assert 'Invalid hand' not in app.hand_error.cget('text')
    app._on_close()

