"""
Unit and UI integration tests for humanized autonomous action execution (auto_actor.py, rta.py, ui.py).
"""

import random
import tempfile
import time
import tkinter as tk
from unittest.mock import Mock
import pytest

from auto_actor import AutoActor, BUTTON_REGIONS, HumanizedConfig
import rta


class TestActionNormalization:
    def test_normalize_fold_call_raise_categories(self):
        assert AutoActor.normalize_action_category('FOLD', call_amount=200) == 'fold'
        assert AutoActor.normalize_action_category('CALL', call_amount=200) == 'call'
        assert AutoActor.normalize_action_category('CHECK', call_amount=0) == 'call'
        assert AutoActor.normalize_action_category('RAISE', call_amount=200) == 'raise'
        assert AutoActor.normalize_action_category('BET', call_amount=0) == 'raise'
        assert AutoActor.normalize_action_category('3-BET', call_amount=600) == 'raise'
        assert AutoActor.normalize_action_category('4-BET', call_amount=1800) == 'raise'
        assert AutoActor.normalize_action_category('5-BET/SHOVE', call_amount=5000) == 'raise'
        assert AutoActor.normalize_action_category('SQUEEZE', call_amount=600) == 'raise'

    def test_free_check_protection_when_call_amount_is_zero(self):
        # Never fold when checking is free
        assert AutoActor.normalize_action_category('FOLD', call_amount=0) == 'call'
        assert AutoActor.normalize_action_category('FOLD', call_amount=0.0) == 'call'

    def test_invalid_or_empty_action_returns_none(self):
        assert AutoActor.normalize_action_category(None) is None
        assert AutoActor.normalize_action_category('') is None
        assert AutoActor.normalize_action_category('WAIT') is None


class TestHumanizedSampling:
    def test_sample_target_point_stays_strictly_within_inner_button_bounds(self):
        actor = AutoActor(HumanizedConfig(enabled=True, jitter_sigma=0.25), rng=random.Random(42))
        bounds = (100, 200, 1000, 700)
        for client in ('ggpoker', 'pokerstars'):
            for btn_name, region in BUTTON_REGIONS[client].items():
                bx = bounds[0] + region['x'] * bounds[2]
                by = bounds[1] + region['y'] * bounds[3]
                bw = region['w'] * bounds[2]
                bh = region['h'] * bounds[3]
                points = set()
                for _ in range(50):
                    sx, sy = actor.sample_target_point(bounds, region)
                    points.add((sx, sy))
                    assert bx + bw * 0.14 <= sx <= bx + bw * 0.86, f"{client}.{btn_name} x out of safe bounds"
                    assert by + bh * 0.14 <= sy <= by + bh * 0.86, f"{client}.{btn_name} y out of safe bounds"
                # Verify jitter produces distinct coordinates
                assert len(points) > 10

    def test_generate_bezier_path_starts_and_ends_at_exact_endpoints(self):
        actor = AutoActor(HumanizedConfig(enabled=True, bezier_steps=20), rng=random.Random(7))
        start = (250, 300)
        end = (840, 790)
        path = actor.generate_bezier_path(start, end)
        assert len(path) == 21
        assert (path[0][0], path[0][1]) == start
        assert (path[-1][0], path[-1][1]) == end
        assert all(step[2] > 0 for step in path)

    def test_sample_thinking_delay_respects_bounds_and_complexity(self):
        cfg = HumanizedConfig(enabled=True, min_delay=0.75, max_delay=2.4)
        actor = AutoActor(cfg, rng=random.Random(99))
        fold_delays = [actor.sample_thinking_delay('FOLD', 'preflop') for _ in range(100)]
        raise_delays = [actor.sample_thinking_delay('3-BET', 'flop') for _ in range(100)]
        assert all(0.75 <= d <= 2.4 for d in fold_delays)
        assert all(0.75 <= d <= 2.4 for d in raise_delays)
        assert sum(raise_delays) / len(raise_delays) > sum(fold_delays) / len(fold_delays)


class TestExecutionAndSafety:
    def test_deduplication_and_dry_run_execution(self):
        cfg = HumanizedConfig(enabled=True, min_delay=0.01, max_delay=0.02, dry_run=True, enter_bet_sizing=True)
        actor = AutoActor(cfg, rng=random.Random(123))

        res1 = actor.execute_action(
            recommended_action='RAISE',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=1,
            hand='AKs',
            street='preflop',
            call_amount=200,
            sizing='600',
            blocking=True,
        )
        assert res1['executed'] is True
        assert res1['status'] == 'dry_run'
        assert res1['category'] == 'raise'
        assert res1['sizing_typed'] == '600'
        assert res1['sizing_target'] is not None

        # Duplicate call on identical state must be suppressed
        res2 = actor.execute_action(
            recommended_action='RAISE',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=1,
            hand='AKs',
            street='preflop',
            call_amount=200,
            sizing='600',
            blocking=True,
        )
        assert res2['executed'] is False
        assert res2['status'] == 'deduplicated'

        # New hand or street executes normally
        res3 = actor.execute_action(
            recommended_action='CALL',
            client='pokerstars',
            window_bounds=(0, 0, 1000, 700),
            table_id=1,
            hand='AKs',
            street='flop',
            board='AhKd2c',
            call_amount=400,
            blocking=True,
        )
        assert res3['executed'] is True
        assert res3['category'] == 'call'

    def test_emergency_stop_cancels_pending_action_immediately(self):
        cfg = HumanizedConfig(enabled=True, min_delay=1.5, max_delay=2.0, dry_run=True)
        actor = AutoActor(cfg, rng=random.Random(5))
        completed = []

        sched = actor.execute_action(
            recommended_action='CALL',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=9,
            hand='QQ',
            street='preflop',
            call_amount=200,
            on_complete=lambda r: completed.append(r),
            blocking=False,
        )
        assert sched['status'] == 'scheduled'
        time.sleep(0.05)
        actor.emergency_stop()
        time.sleep(0.08)

        assert actor.enabled is False
        assert len(completed) == 1
        assert completed[0]['executed'] is False
        assert completed[0]['status'] == 'cancelled'

    def test_requires_live_action_buttons_or_call_amount(self):
        cfg = HumanizedConfig(enabled=True, min_delay=0.01, max_delay=0.02, dry_run=True)
        actor = AutoActor(cfg)
        res = actor.execute_action(
            recommended_action='RAISE',
            call_amount=None,
            action_buttons_visible=False,
            blocking=True,
        )
        assert res['executed'] is False
        assert res['status'] == 'no_action_buttons'

    def test_open_raise_descriptive_sizing_does_not_type_bogus_number(self):
        # Bug 1 regression: 'Open raise ~2.2-2.5bb' or '3bet to ~3x open' must NOT extract '2.2' or '3'
        assert AutoActor.extract_numeric_sizing('Open raise ~2.2-2.5bb') is None
        assert AutoActor.extract_numeric_sizing('3bet to ~3x open') is None
        assert AutoActor.extract_numeric_sizing('66% pot') is None
        assert AutoActor.extract_numeric_sizing('600') == '600'
        assert AutoActor.extract_numeric_sizing(450) == '450'

        cfg = HumanizedConfig(enabled=True, min_delay=0.01, max_delay=0.02, dry_run=True, enter_bet_sizing=True)
        actor = AutoActor(cfg, rng=random.Random(11))
        res = actor.execute_action(
            recommended_action='RAISE',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=1,
            hand='AKs',
            street='preflop',
            call_amount=200,
            sizing='Open raise ~2.2-2.5bb',
            action_buttons_visible=True,
            blocking=True,
        )
        assert res['executed'] is True
        assert res['category'] == 'raise'
        assert res['sizing_typed'] is None
        assert res['sizing_target'] is None

    def test_retry_after_cooldown_when_click_missed_or_too_early(self):
        # Bug 2 regression: deduplicate within retry_cooldown, but retry if same state persists past cooldown
        cfg = HumanizedConfig(
            enabled=True,
            min_delay=0.01,
            max_delay=0.02,
            dry_run=True,
            retry_cooldown=0.08,
        )
        actor = AutoActor(cfg, rng=random.Random(21))

        res1 = actor.execute_action(
            recommended_action='CALL',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=7,
            hand='QJs',
            street='preflop',
            call_amount=200,
            action_buttons_visible=True,
            blocking=True,
        )
        assert res1['executed'] is True

        # Immediate poll within cooldown is deduplicated
        res2 = actor.execute_action(
            recommended_action='CALL',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=7,
            hand='QJs',
            street='preflop',
            call_amount=200,
            action_buttons_visible=True,
            blocking=True,
        )
        assert res2['executed'] is False
        assert res2['status'] == 'deduplicated'

        # After retry_cooldown elapses and buttons are still visible, AutoActor retries instead of staying stuck
        time.sleep(0.10)
        res3 = actor.execute_action(
            recommended_action='CALL',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=7,
            hand='QJs',
            street='preflop',
            call_amount=200,
            action_buttons_visible=True,
            blocking=True,
        )
        assert res3['executed'] is True

    def test_preset_sizing_button_and_contextual_chip_sizing(self):
        cfg = HumanizedConfig(enabled=True, min_delay=0.01, max_delay=0.02, dry_run=True, enter_bet_sizing=True)
        actor = AutoActor(cfg, rng=random.Random(31))

        # 1. Preset button extraction & click when pot_size is not supplied
        assert actor.extract_preset_button('75% pot (Strong value)') == 'preset_75'
        assert actor.extract_preset_button('33% pot (Range c-bet)') == 'preset_33'
        assert actor.extract_preset_button('50% pot') == 'preset_50'
        assert actor.extract_preset_button('All-In (low SPR)') == 'preset_allin'

        res_preset = actor.execute_action(
            recommended_action='BET',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=9,
            hand='AA',
            street='flop',
            board='Kh7d2c',
            call_amount=0,
            sizing='75% pot (Strong value)',
            action_buttons_visible=True,
            blocking=True,
        )
        assert res_preset['executed'] is True
        assert res_preset['preset_button'] == 'preset_75'
        assert res_preset['preset_target'] is not None

        # 2. Contextual chip sizing resolution when pot_size / big_blind are supplied
        assert actor.resolve_chip_sizing('75% pot', pot_size=200, call_amount=0) == '150'
        assert actor.resolve_chip_sizing('Open raise ~2.2-2.5bb', big_blind=100) == '235'
        actor.reset_deduplication()
        res_chips = actor.execute_action(
            recommended_action='BET',
            client='ggpoker',
            window_bounds=(0, 0, 1000, 700),
            table_id=9,
            hand='AA',
            street='flop',
            board='Kh7d2c',
            call_amount=0,
            pot_size=200,
            sizing='75% pot (Strong value)',
            action_buttons_visible=True,
            blocking=True,
        )
        assert res_chips['executed'] is True
        assert res_chips['sizing_typed'] == '150'
        assert res_chips['sizing_target'] is not None



def test_rta_ui_autonomy_integration_and_persistence(monkeypatch):
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display is unavailable')
    root.withdraw()

    with tempfile.NamedTemporaryFile('w', suffix='.ini', delete=False) as tf:
        temp_cfg = tf.name

    app = rta.RTAApp(root)
    app._config_path = temp_cfg
    app._play_sound = Mock()

    # Verify UI controls exist and update AutoActor config
    assert hasattr(app, 'auto_act_var')
    assert hasattr(app, 'auto_act_status_var')
    assert app.auto_act_var.get() is False

    app.min_delay_var.set('0.01')
    app.max_delay_var.set('0.02')
    app.dry_run_var.set(True)
    app.enter_bet_sizing_var.set(True)
    app.auto_act_var.set(True)
    app._toggle_auto_act()

    assert app._auto_actor.enabled is True
    assert app._auto_actor.config.dry_run is True
    assert 'Armed (Dry-run)' in app.auto_act_status_var.get()

    # Save and reload config
    assert app._save_config(temp_cfg) is True
    loaded = app._load_config(temp_cfg)
    assert loaded['auto_act_enabled'] is True
    assert loaded['auto_min_delay'] == pytest.approx(0.01)
    assert loaded['auto_max_delay'] == pytest.approx(0.02)
    assert loaded['auto_dry_run'] is True

    # Simulate confirmed OCR hand with live preflop action turn
    app.ocr_var.set(True)
    app._ocr_generation = 1
    frame = dict(
        hand='AKs', cards=('As', 'Ks'), reliable=True, table_id=42,
        captured_at=time.monotonic(), position='BTN', spot='open',
        preflop=dict(
            complete=True, big_blind=200, small_blind=100, units='chips',
            bets={2: 0, 3: 0, 4: 100, 5: 200},
            stacks={2: 20000, 3: 20000, 4: 19900, 5: 19800},
            positions={2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'},
            pot=300, call=200, board_present=False,
        ),
    )
    app._accept_ocr_result(frame, 1)
    app._accept_ocr_result(frame, 1)
    deadline = time.monotonic() + 1.0
    while (len(app._auto_actor.get_action_history()) < 1 or 'Dry-run: RAISE' not in app.auto_act_status_var.get()) and time.monotonic() < deadline:
        time.sleep(0.02)
        root.update()

    history = app._auto_actor.get_action_history()
    assert len(history) == 1
    assert history[0]['category'] == 'raise'
    assert history[0]['sizing_typed'] is None
    assert 'Dry-run: RAISE' in app.auto_act_status_var.get()

    # Verify open spot triggers even when call is None if action_turn is True
    app._auto_actor.reset_deduplication()
    open_no_call_frame = dict(
        hand='QQ', cards=('Qh', 'Qs'), reliable=True, table_id=42,
        captured_at=time.monotonic(), position='CO', spot='open',
        preflop=dict(
            complete=True, big_blind=200, small_blind=100, units='chips',
            bets={2: 0, 3: 0, 4: 100, 5: 200},
            stacks={2: 20000, 3: 20000, 4: 19900, 5: 19800},
            positions={2: 'MP', 3: 'CO', 4: 'SB', 5: 'BB'},
            pot=300, call=None, action_turn=True, board_present=False,
        ),
    )
    app._accept_ocr_result(open_no_call_frame, 1)
    app._accept_ocr_result(open_no_call_frame, 1)
    deadline = time.monotonic() + 1.0
    while len(app._auto_actor.get_action_history()) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
        root.update()
    root.update()
    history = app._auto_actor.get_action_history()
    assert len(history) == 2
    assert history[1]['category'] == 'raise'

    # Verify GGPoker Card Squeeze "Open" button triggers OPEN_CARDS click before cards are revealed
    app._auto_actor.reset_deduplication()
    app.auto_act_var.set(True)
    app._toggle_auto_act()
    squeeze_frame = dict(
        hand=None, cards=None, reliable=False, table_id=42,
        window_bounds=(100, 50, 900, 640), client='ggpoker',
        open_cards_button=True,
        captured_at=time.monotonic(),
        status='watching',
        message='Card squeeze Open button detected — opening cards...',
    )
    app._accept_ocr_result(squeeze_frame, 1)
    deadline = time.monotonic() + 1.0
    while len(app._auto_actor.get_action_history()) < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
        root.update()
    root.update()
    history = app._auto_actor.get_action_history()
    assert len(history) == 3
    assert history[2]['category'] == 'open_cards'
    assert history[2]['action'] == 'OPEN_CARDS'
    assert 'OPEN_CARDS' in app.auto_act_status_var.get()

    # Emergency stop disarms immediately
    app._emergency_stop_auto_act()
    assert app.auto_act_var.get() is False
    assert app._auto_actor.enabled is False
    assert 'Disarmed' in app.auto_act_status_var.get()
    app._on_close()


def test_detect_open_cards_button_on_ggpoker_squeeze():
    from PIL import Image, ImageDraw
    import ocr

    img = Image.new('RGB', (900, 640), (20, 35, 25))
    assert ocr.detect_open_cards_button(img) is False

    # Draw bright green "Open" button in GGPoker squeeze region (0.693..0.789, 0.869..0.919)
    draw = ImageDraw.Draw(img)
    x1, y1 = int(0.693 * 900), int(0.869 * 640)
    x2, y2 = int(0.789 * 900), int(0.919 * 640)
    draw.rectangle([x1, y1, x2, y2], fill=(46, 175, 82))
    # Draw white "Open" text strokes inside the button
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    draw.rectangle([cx - 16, cy - 4, cx + 16, cy + 4], fill=(245, 250, 245))
    assert ocr.detect_open_cards_button(img) is True


def test_detect_sit_in_button_and_execute_sit_in():
    from PIL import Image, ImageDraw
    import ocr

    img = Image.new('RGB', (900, 640), (20, 35, 25))
    assert ocr.detect_sit_in_button(img) is False

    # Draw green "I'm Back" / "Sit In" button in right-hand region (0.76..0.94, 0.86..0.94)
    draw = ImageDraw.Draw(img)
    x1, y1 = int(0.78 * 900), int(0.87 * 640)
    x2, y2 = int(0.92 * 900), int(0.93 * 640)
    draw.rectangle([x1, y1, x2, y2], fill=(46, 175, 82))
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    draw.rectangle([cx - 25, cy - 5, cx + 25, cy + 5], fill=(245, 250, 245))

    # Mock _extract_text_vision to return "I'm Back"
    orig_vision = getattr(ocr, '_extract_text_vision', None)
    ocr._extract_text_vision = lambda *a, **k: "I'm Back"
    try:
        assert ocr.detect_sit_in_button(img) is True
    finally:
        if orig_vision is not None:
            ocr._extract_text_vision = orig_vision

    actor = AutoActor(
        config=HumanizedConfig(enabled=True, min_delay=0.01, max_delay=0.02, dry_run=True),
        rng=random.Random(11),
    )
    res = actor.execute_sit_in(
        client='ggpoker',
        window_bounds=(100, 50, 900, 640),
        table_id=42,
        blocking=True,
    )
    assert res['executed'] is True
    assert res['category'] == 'sit_in'
    assert res['action'] == 'SIT_IN'


def test_vpip_exploitative_adjustments_and_postflop_advice():
    from strategy import StrategyManager
    from postflop import PostflopAdvice, spot_to_opponent_range, narrow_range_by_street_action

    mgr = StrategyManager()
    loose_adj = mgr.get_exploitative_vpip_adjustment(54.0)
    assert loose_adj['player_type'] == 'loose_passive'
    assert loose_adj['value_thresh_shift'] < 0
    assert loose_adj['semi_bluff_shift'] > 0

    nit_adj = mgr.get_exploitative_vpip_adjustment(14.0)
    assert nit_adj['player_type'] == 'nit'
    assert nit_adj['value_thresh_shift'] > 0
    assert nit_adj['semi_bluff_shift'] < 0

    reg_adj = mgr.get_exploitative_vpip_adjustment(25.0)
    assert reg_adj['player_type'] == 'regular'

    # PostflopAdvice includes VPIP tag in reasoning and adjusts thresholds
    adv_loose = PostflopAdvice(
        hero_hand='AhKh',
        board='Ad9c4s',
        pot_size=100,
        call_amount=25,
        iterations=250,
        opponent_vpip=56.0,
    ).get_advice()
    assert adv_loose['opponent_vpip'] == 56.0
    assert 'VPIP: 56% (Loose)' in adv_loose['reasoning']

    # Multi-street range narrowing across Flop -> Turn -> River
    spot = {'kind': 'facing_open', 'pos': 'BTN', 'vs': 'CO'}
    flop_range = spot_to_opponent_range(spot, board='KsQd4c', street='flop', facing_bet=False)
    turn_bet_range = spot_to_opponent_range(spot, board='KsQd4c9h', street='turn', facing_bet=True)
    river_nit_range = spot_to_opponent_range(spot, board='KsQd4c9h2s', street='river', facing_bet=True, opponent_vpip=14.0)

    flop_hands = [h.strip() for h in flop_range.split(',') if h.strip()]
    turn_hands = [h.strip() for h in turn_bet_range.split(',') if h.strip()]
    river_hands = [h.strip() for h in river_nit_range.split(',') if h.strip()]
    assert len(flop_hands) >= len(turn_hands) >= len(river_hands) >= 6

    narrowed = narrow_range_by_street_action("AA, KK, QQ, 72o, 83o, 94o, A2o, KQo, QJs, JTs", "KsQd4c9h", street="turn", facing_bet=True)
    assert "72o" not in narrowed
    assert "AA" in narrowed
    assert "KQo" in narrowed


def test_auto_stack_delta_logging(tmp_path):
    from analytics import HandLogger, Analytics

    log_file = tmp_path / "hands.json"
    logger = HandLogger(str(log_file))
    entry = logger.log_analysis(
        hand="AKs",
        recommended_action="RAISE",
        confidence=90.0,
        position="BTN",
        spot="open",
    )
    assert entry is not None
    assert entry.result is None

    # Record a +12.5 BB win (2500 chips at 200 BB)
    updated = logger.record_stack_delta(prev_stack_chips=20000, new_stack_chips=22500, big_blind=200)
    assert updated is not None
    assert updated['result'] == "win"
    recent = logger.get_recent_hands(1)[0]
    assert recent.result == "win"
    assert recent.bb_delta == pytest.approx(12.5)
    assert recent.pot_size == pytest.approx(2500.0)

    engine = Analytics(logger)
    stats = engine.get_win_rate_stats()
    assert stats['wins'] == 1


def test_parse_amount_border_slashes_and_limp_iso_tracker():
    from table_context import parse_amount, PreflopTracker

    # Active turn box border characters around stack amount
    val, unit = parse_amount(r'\ 237,492 /')
    assert val == 237492.0
    assert unit is None

    # Mid-hand card reveal facing a limper infers iso_raise
    tracker = PreflopTracker()
    ctx = tracker.update({
        'table_id': 1,
        'table_name': ' Rush & Cash $100 / $200',
        'cards': ('Ah', 'Kh'),
        'reliable': True,
        'preflop': {
            'complete': True,
            'button_seat': 3,
            'big_blind': 200.0,
            'small_blind': 100.0,
            'units': 'chips',
            'bets': {0: 0.0, 1: 200.0, 2: 0.0, 3: 0.0, 4: 100.0, 5: 200.0},
            'stacks': {0: 20000.0, 1: 19800.0, 2: 20000.0, 3: 20000.0, 4: 19900.0, 5: 19800.0},
            'positions': {0: 'UTG', 1: 'MP', 2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'},
            'pot': 500.0,
            'call': 200.0,
            'board_present': False,
        },
    })
    assert ctx['inferred_spot'] == 'iso_raise'
    assert ctx['inferred_vs'] == 'MP'


def test_missing_raise_button_downgrades_to_call_or_check(monkeypatch):
    from pathlib import Path
    from PIL import Image
    import tkinter as tk
    import threading
    import ocr
    import rta

    monkeypatch.setattr(ocr, '_CLIENT', 'ggpoker')
    with Image.open(Path(__file__).parent / 'tests/fixtures/position_hero_button.png') as im_two_btn:
        assert ocr.is_raise_button_available(im_two_btn.convert('RGB')) is False
    with Image.open(Path(__file__).parent / 'tests/fixtures/ggpoker_postflop_739.png') as im_three_btn:
        assert ocr.is_raise_button_available(im_three_btn.convert('RGB')) is True

    # AutoActor remaps 'RAISE' / 'BET' to 'call' (Slot 2 Call/Check button) when raise_available=False
    assert AutoActor.normalize_action_category('RAISE', call_amount=4000, raise_available=False) == 'call'
    assert AutoActor.normalize_action_category('BET', call_amount=0, raise_available=False) == 'call'
    actor = AutoActor(HumanizedConfig(enabled=True, min_delay=0.0, max_delay=0.0, dry_run=True))
    res = actor.execute_action(
        recommended_action='RAISE',
        client='ggpoker',
        window_bounds=(0, 0, 1000, 700),
        table_id=99,
        hand='AKo',
        street='flop',
        board='3sAcTs',
        call_amount=4000,
        raise_available=False,
        blocking=True,
    )
    assert res['executed'] is True
    assert res['category'] == 'call'
    assert res['preset_button'] is None
    assert 735 <= res['target'][0] <= 860

    # End-to-end RTA postflop UI + AutoActor when raise_available=False
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display unavailable')
    root.withdraw()
    app = rta.RTAApp(root)
    try:
        app.ocr_var.set(True)
        app._ocr_generation = 1
        app._auto_actor.config.min_delay = 0.0
        app._auto_actor.config.max_delay = 0.0
        app._auto_actor.config.dry_run = True
        app._auto_actor.enabled = True
        app.auto_act_var.set(True)

        frame = dict(
            hand='AKo', cards=('Ad', 'Ks'), hole_cards='AKo', reliable=True, status='success',
            position='SB', active_opponents=2, table_id=42, window_bounds=(0, 0, 1000, 700),
            board='3sAcTs', board_info={'street': 'flop'},
            pot_size=30325, call_amount=4000, raise_available=False,
            captured_at=time.monotonic(),
        )
        stop = threading.Event()
        app._accept_ocr_result(frame, 1)
        app._accept_ocr_result(dict(frame, captured_at=time.monotonic()), 1)
        app._accept_postflop_result(dict(frame, captured_at=time.monotonic()), stop)
        assert app.mode == 'postflop'
        assert app._current_action == 'CALL'
        assert 'CALL' in app.advice_var.get()

        deadline = time.monotonic() + 1.0
        while len(app._auto_actor.get_action_history()) < 1 and time.monotonic() < deadline:
            time.sleep(0.02)
            root.update()
        hist = app._auto_actor.get_action_history()
        assert len(hist) >= 1
        assert hist[-1]['category'] == 'call'

        # Also verify call_amount=0 with raise_available=False downgrades BET/RAISE to CHECK
        app._auto_actor.reset_deduplication()
        check_only_frame = dict(frame, call_amount=0, raise_available=False, captured_at=time.monotonic())
        app._accept_postflop_result(check_only_frame, stop)
        assert app._current_action == 'CHECK'
        assert 'CHECK' in app.advice_var.get()
    finally:
        app._on_close()


def test_unopened_pot_not_iso_and_folded_hand_and_dedup_and_presets(tmp_path, monkeypatch):
    """Verify:
    1. Unopened pot (pot == sb + bb, single 1 BB blind) with shifted seat label is 'open', not 'iso_raise'.
    2. After Hero folds preflop, postflop analysis and logging pause until a new hand is dealt.
    3. Street logging deduplicates across >2s polls while updating in-place and preserving user_action.
    4. presets_available=False skips clicking preset buttons before clicking Raise/Bet.
    """
    import tkinter as tk
    from PIL import Image, ImageDraw
    from table_context import PreflopTracker
    from analytics import HandLogger
    import ocr as ocr_mod
    import rta

    # 1. Unopened pot on 200/500 table where BB seat is mislabeled 'CO' due to sitting-out player
    tracker = PreflopTracker()
    unopened_obs = {
        'table_id': 77,
        'cards': ('As', 'Kd'),
        'hand': 'AKo',
        'reliable': True,
        'position': 'BTN',
        'captured_at': time.monotonic(),
        'preflop': {
            'complete': True,
            'big_blind': 500.0,
            'small_blind': 200.0,
            'units': 'chips',
            'bets': {0: 0.0, 1: 200.0, 2: 500.0, 3: 0.0, 4: 0.0, 5: 0.0},
            'stacks': {s: 50000.0 for s in range(6)},
            'positions': {0: 'MP', 1: 'SB', 2: 'CO', 3: 'BTN', 4: 'UTG', 5: 'BB'},
            'pot': 700.0,
            'call': 500.0,
            'board_present': False,
        },
    }
    ctx = tracker.update(unopened_obs)
    assert ctx.get('inferred_spot') != 'iso_raise'

    # 4. Verify is_preset_bar_available and AutoActor presets_available guard
    img_no_presets = Image.new('RGB', (1000, 700), (25, 45, 35))
    draw = ImageDraw.Draw(img_no_presets)
    # Draw red Call and Raise buttons, but leave preset strip (y=0.818..0.850) dark
    draw.rectangle([735, 595, 860, 660], fill=(185, 55, 50))
    draw.rectangle([760, 618, 835, 635], fill=(240, 240, 240))
    draw.rectangle([868, 595, 990, 660], fill=(185, 55, 50))
    draw.rectangle([890, 618, 965, 635], fill=(240, 240, 240))
    assert ocr_mod.is_raise_button_available(img_no_presets) is True
    assert ocr_mod.is_preset_bar_available(img_no_presets) is False

    # Draw bright text in preset strip -> is_preset_bar_available becomes True
    draw.rectangle([700, 575, 735, 590], fill=(220, 220, 220))
    assert ocr_mod.is_preset_bar_available(img_no_presets) is True

    actor = AutoActor(HumanizedConfig(enabled=True, min_delay=0.0, max_delay=0.0, enter_bet_sizing=True, dry_run=True))
    res_no_preset = actor.execute_action(
        'BET',
        client='ggpoker',
        window_bounds=(0, 0, 1000, 700),
        table_id=77,
        hand='AKo',
        street='flop',
        board='QsJh2c',
        call_amount=0,
        sizing='75% pot',
        presets_available=False,
        blocking=True,
    )
    assert res_no_preset['executed'] is True
    assert res_no_preset['category'] == 'raise'
    assert res_no_preset['preset_button'] is None

    # 2 & 3. End-to-end RTA folded-hand pause and street log deduplication
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', True)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display unavailable')
    root.withdraw()
    app = rta.RTAApp(root)
    try:
        logger = HandLogger(log_path=str(tmp_path / 'dedup_fold_log.json'))
        app._logger = logger
        app.ocr_var.set(True)
        app._ocr_generation = 1

        # Confirm trash hand 72o in UTG open -> recommends FOLD
        fold_frame = dict(
            hand='72o', cards=('7s', '2d'), hole_cards='72o', reliable=True, status='detected',
            position='UTG', active_opponents=5, table_id=77, window_bounds=(0, 0, 1000, 700),
            preflop=unopened_obs['preflop'],
            captured_at=time.monotonic(),
        )
        app._accept_ocr_result(fold_frame, 1)
        app._accept_ocr_result(dict(fold_frame, captured_at=time.monotonic()), 1)
        assert app.kind_var.get() == 'open'
        assert app._current_action == 'FOLD'
        assert len(logger.get_hands()) == 1

        # Simulate >3 seconds passing on the same street and re-refreshing -> still 1 entry, user_action preserved
        app._record_user_action(True)
        assert app._hero_folded_hand is True
        assert logger.get_hands()[0].user_action == 'FOLD'
        app._last_log_timestamp -= 5.0
        app._log_hand_with_table()
        assert len(logger.get_hands()) == 1
        assert logger.get_hands()[0].user_action == 'FOLD'

        # Board cards appear while Hero's folded 72o is still visible -> must NOT switch to postflop or log postflop
        flop_after_fold = dict(
            fold_frame,
            board='7h7c2c',
            board_info={'street': 'flop'},
            pot_size=1500,
            call_amount=0,
            captured_at=time.monotonic(),
        )
        app._accept_ocr_result(flop_after_fold, 1)
        assert app.mode == 'preflop'
        assert len(logger.get_hands()) == 1

        # Dealing a new hand (AA) resets _hero_folded_hand and logs the new hand
        new_hand_frame = dict(
            fold_frame,
            hand='AA', cards=('As', 'Ah'), hole_cards='AA',
            captured_at=time.monotonic(),
        )
        app._accept_ocr_result(new_hand_frame, 1)
        app._accept_ocr_result(dict(new_hand_frame, captured_at=time.monotonic()), 1)
        assert app._hero_folded_hand is False
        assert app._current_action == 'RAISE'
        assert len(logger.get_hands()) == 2
    finally:
        app._on_close()




