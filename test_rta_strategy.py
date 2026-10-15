"""Exercise strategy callbacks and rendered advice without a display or capture."""
import json
from unittest.mock import Mock

import pytest
import ranges
import rta
import ui
from strategy import StrategyManager


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(ui, 'render_cards', lambda app: None)
    monkeypatch.setattr(rta, 'HAS_STRATEGY', True)
    app = rta.RTAApp.__new__(rta.RTAApp)
    app._strategy_manager = StrategyManager()
    app.mode = 'preflop'
    app.kind_var, app.pos_var, app.vs_var = Value('open'), Value('UTG'), Value('BTN')
    app.ocr_var = Value(False)
    app.profile_var, app.stack_var = Value('ABC'), Value('100')
    app.aggression_label = Mock()
    app.hand = 'AA'
    app.hand_entry = Mock()
    app.cells = {hand: Mock() for hand in ranges.all_hands()}
    app.advice_var, app.advice_detail, app.confidence_var = Value(''), Value(''), Value('')
    app.advice_label = Mock()
    app._current_confidence = 0
    app._show_confidence = False
    app._log_hand_with_table = Mock()
    app._refresh()
    return app


def assert_grid_matches_advice(app):
    # Use another selected hand so grid highlighting does not hide its action color.
    for hand in ranges.all_hands():
        if hand == app.hand:
            continue
        advice, _ = app._get_preflop_advice(hand)
        color = app.RAISE_C if advice[0] == 'RAISE' else app.GRID_EMPTY
        assert app.cells[hand].configure.call_args.kwargs['bg'] == color


def test_defaults_preserve_base_advice_and_grid(app):
    for hand in ranges.all_hands():
        advice, sets = app._get_preflop_advice(hand)
        assert advice == ranges.advise(app.spot, hand)
        assert sets == ranges.get_action_sets(app.spot)
    assert_grid_matches_advice(app)


@pytest.mark.parametrize('setting,value', [('profile', 'TAG'), ('stack', '20'), ('aggression', 0.5)])
def test_settings_change_displayed_advice_and_grid(app, setting, value):
    app.hand = '54s'
    app._refresh()
    assert app._current_action == 'RAISE'
    if setting == 'aggression':
        app._on_aggression_change(value)
    else:
        getattr(app, setting + '_var').set(value)
        app._on_strategy_change()
    assert app._current_action == 'FOLD'
    assert 'FOLD' in app.advice_var.get()
    assert_grid_matches_advice(app)


def test_import_changes_advice_and_grid(app, tmp_path, monkeypatch):
    path = tmp_path / 'ranges.json'
    path.write_text(json.dumps({'100bb': {'open': {'UTG': ['AA']}}}))
    monkeypatch.setattr(rta.filedialog, 'askopenfilename', lambda **kwargs: str(path))
    monkeypatch.setattr(rta.messagebox, 'showinfo', Mock())
    app.hand = 'AKs'
    app._refresh()
    assert app._current_action == 'RAISE'
    app._import_ranges()
    assert app._current_action == 'FOLD'
    assert_grid_matches_advice(app)


def test_unsupported_spot_clears_previous_action(app):
    app._on_aggression_change(1.5)
    assert app._current_action == 'RAISE'
    app.pos_var.set('unknown')
    app._refresh()
    assert app._current_action is None
    assert app.advice_var.get() == 'Pick a valid spot'


def test_optional_strategy_module_fallback(app, monkeypatch):
    monkeypatch.setattr(rta, 'HAS_STRATEGY', False)
    app._strategy_manager = None
    app._refresh()
    assert app._current_action == 'RAISE'
    assert_grid_matches_advice(app)


def test_mixed_frequency_and_rng_roll_shown_in_detail(app):
    # K5o in BTN open is a mixed RAISE 65% / FOLD 35% hand in ranges.py
    app.pos_var.set('BTN')
    app.kind_var.set('open')
    app.hand = 'K5o'
    app._refresh()
    assert app._current_action is not None
    detail = app.advice_detail.get()
    assert 'Mix:' in detail
    assert 'RAISE 65%' in detail
    assert 'RNG' in detail


def test_save_config_preserves_comments_and_roundtrips(app, tmp_path):
    cfg_file = tmp_path / 'config.ini'
    cfg_file.write_text(
        "[ui]\n# UI Configuration comment\nwindow_opacity = 90\nenable_sound_notifications = true\n"
        "minimize_to_tray = false\nshow_confidence_percentages = true\n\n"
        "[strategy]\n# Strategy comment\nprofile = ABC\naggression_factor = 1.0\nstack_depth = 100\n"
    )
    app._config_path = str(cfg_file)
    app._config = app._load_config(str(cfg_file))
    app._window_opacity = 75
    app._sound_enabled = False
    app._minimize_to_tray = True
    app._show_confidence = False
    app.profile_var.set('LAG')
    app.stack_var.set('50')
    app._on_strategy_change()
    app._on_aggression_change(1.4)

    assert app._save_config(str(cfg_file)) is True
    saved_text = cfg_file.read_text()
    assert '# UI Configuration comment' in saved_text
    assert '# Strategy comment' in saved_text

    app._use_native_solver = False
    app._native_search_ms = 500
    assert app._save_config(str(cfg_file)) is True

    loaded = app._load_config(str(cfg_file))
    assert loaded['window_opacity'] == 75
    assert loaded['enable_sound_notifications'] is False
    assert loaded['minimize_to_tray'] is True
    assert loaded['show_confidence_percentages'] is False
    assert loaded['profile'] == 'LAG'
    assert loaded['stack_depth'] == 50
    assert loaded['aggression_factor'] == pytest.approx(1.4)
    assert loaded['use_native_solver'] is False
    assert loaded['native_search_ms'] == 500


def test_analytics_adherence_and_outcome_recording(app, tmp_path, monkeypatch):
    from analytics import HandLogger, Analytics
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', True)
    logger = HandLogger(log_path=str(tmp_path / 'test_hand_log.json'))
    analytics_calc = Analytics(logger)
    app._logger = logger
    app._analytics = analytics_calc
    app.feedback_status_var = Value('')

    entry = logger.log_analysis(hand='AKs', recommended_action='RAISE', confidence=85.0, position='BTN', spot='open')
    app._last_logged_entry = entry
    app._last_logged_entry_ts = entry.timestamp

    assert app._record_user_action(True) is True
    assert app._record_hand_result('win', pot_size=120.0) is True

    summary = analytics_calc.get_summary()
    assert summary['total_hands'] == 1
    assert summary['gto_adherence']['followed'] == 1
    assert summary['gto_adherence']['adherence_rate'] == 100.0
    assert summary['win_rate_stats']['wins'] == 1
    assert summary['win_rate_stats']['win_rate'] == 100.0

    # Verify P&L stack-delta accounting clamps bogus wins/losses on preflop folds
    fold_entry = logger.log_analysis(hand='T4s', recommended_action='FOLD', confidence=0.0, position='BB', spot='iso_raise', mode='preflop')
    logger.update_user_action(fold_entry.timestamp, 'FOLD')
    # Simulating a +40,500 chip (+81 BB) OCR glitch after folding in BB:
    delta_res = logger.record_stack_delta(prev_stack_chips=50000.0, new_stack_chips=90500.0, big_blind=500.0, timestamp=fold_entry.timestamp)
    assert delta_res['result'] == 'push'
    assert delta_res['bb_delta'] == 0.0
    assert fold_entry.pot_size == 0.0

    # Simulating a -88,000 chip (-176 BB) OCR glitch after folding preflop in UTG:
    utg_fold = logger.log_analysis(hand='72o', recommended_action='FOLD', confidence=0.0, position='UTG', spot='open', mode='preflop')
    logger.update_user_action(utg_fold.timestamp, 'FOLD')
    delta_utg = logger.record_stack_delta(prev_stack_chips=90000.0, new_stack_chips=2000.0, big_blind=500.0, timestamp=utg_fold.timestamp)
    assert delta_utg['result'] == 'push'
    assert delta_utg['bb_delta'] == 0.0

    # Verify sanitize_history cleans corrupted legacy entries and get_win_rate_stats reports BB/100
    corrupted_win = logger.log_analysis(hand='T4s', recommended_action='FOLD', confidence=0.0, position='BB', spot='iso_raise', mode='preflop')
    corrupted_win.user_action = 'FOLD'
    corrupted_win.result = 'win'
    corrupted_win.pot_size = 40500.0
    corrupted_win.bb_delta = 81.0
    san_stats = logger.sanitize_history()
    assert san_stats['preflop_fold_wins_fixed'] == 1
    assert corrupted_win.result == 'push'
    assert corrupted_win.bb_delta == 0.0
    wstats = analytics_calc.get_win_rate_stats()
    assert 'total_bb_net' in wstats
    assert 'bb_per_100' in wstats
    assert 'vpip_hands_win_rate' in wstats

    app._refresh_analytics = Mock()
    app._clear_analytics_history()
    assert analytics_calc.get_total_hands() == 0


def test_polarized_wheel_ace_bluffs_preserved_when_scaling_3bet():
    from strategy import StrategyProfile
    mgr = StrategyManager()
    spot = {'kind': 'facing_open', 'pos': 'BTN', 'vs': 'CO'}
    # Under TAG or slightly tighter scaling, A5s/A4s in the base 3-bet range
    # should be retained ahead of weaker linear hands like A9s or KJs
    mgr.set_profile(StrategyProfile.TAG)
    mgr.set_aggression_factor(1.1)
    adv_a5s, sets = mgr.advise_with_strategy(spot, 'A5s')
    assert 'A5s' in sets['3-BET']
    assert adv_a5s[0] == '3-BET'


def test_postflop_refresh_uses_strategy_manager_and_handles_generations(app, monkeypatch):
    from strategy import StrategyProfile
    app.mode = 'postflop'
    app._exact_cards = ('Ah', 'Kh')
    app._big_blind = 2.0
    app._amount_units = 'chips'
    app._table_units = 'chips'
    app._preflop_context = {'effective_bb': 50}
    app.equity_var = Value('')
    app.outs_var = Value('')
    app.pot_odds_var = Value('')
    app.board_entry = Mock(get=Mock(return_value='QdJd2s'))
    app.pot_entry = Mock(get=Mock(return_value='100'))
    app.call_entry = Mock(get=Mock(return_value='50'))

    app._strategy_manager.set_profile(StrategyProfile.TAG)
    app._strategy_manager.set_stack_depth(20)

    captured_kwargs = {}

    def fake_advice(**kwargs):
        captured_kwargs.update(kwargs)
        return {'equity_pct': 65.0, 'decision': 'RAISE', 'reasoning': 'Strong draw', 'recommended_sizing': '75% pot'}

    monkeypatch.setattr(rta, 'get_postflop_advice', fake_advice)
    app._refresh_postflop()

    expected_range = rta.spot_to_opponent_range(app.spot, strategy_manager=app._strategy_manager)
    assert captured_kwargs['opponent_range'] == expected_range
    assert 'RAISE' in app.advice_var.get()
    assert app.equity_var.get() == 'Equity: 65.0%'

    # Verify stale generation results are ignored
    current_gen = app._postflop_calc_generation
    app._apply_postflop_advice_result(
        {'equity_pct': 10.0, 'decision': 'FOLD', 'reasoning': 'Stale'},
        'AhKh', 'QdJd2s', 33.3, current_gen - 1
    )
    assert app._current_action == 'RAISE'
    assert app.equity_var.get() == 'Equity: 65.0%'


def test_postflop_hand_logging_and_street_deduplication(app, tmp_path, monkeypatch):
    from analytics import HandLogger, Analytics
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', True)
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)

    logger = HandLogger(log_path=str(tmp_path / 'postflop_log.json'))
    analytics_calc = Analytics(logger)

    # Restore real _log_hand_with_table method on the fixture instance
    app._log_hand_with_table = rta.RTAApp._log_hand_with_table.__get__(app, rta.RTAApp)
    app._logger = logger
    app._analytics = analytics_calc
    app._last_logged_hand = None
    app._last_logged_key = None
    app._last_log_timestamp = 0
    app._last_logged_entry = None
    app._last_logged_entry_ts = None

    # 1. Log preflop AKs in BTN open
    app.mode = 'preflop'
    app.pos_var.set('BTN')
    app.kind_var.set('open')
    app.hand = 'AKs'
    app._exact_cards = ('Ah', 'Kh')
    app._refresh()

    hands = logger.get_hands()
    assert len(hands) == 1
    assert hands[0].mode == 'preflop'
    assert hands[0].hand == 'AKs'
    assert hands[0].position == 'BTN'
    assert hands[0].spot == 'open'

    # 2. Switch to postflop within the 2s window on flop QdJd2s -> must log new entry
    app.mode = 'postflop'
    app._big_blind = 2.0
    app._amount_units = 'chips'
    app._table_units = 'chips'
    app._preflop_context = {'effective_bb': 50}
    app.equity_var = Value('')
    app.outs_var = Value('')
    app.pot_odds_var = Value('')
    app.board_entry = Mock(get=Mock(return_value='QdJd2s'))
    app.pot_entry = Mock(get=Mock(return_value='120'))
    app.call_entry = Mock(get=Mock(return_value='40'))

    monkeypatch.setattr(
        rta,
        'get_postflop_advice',
        lambda **kw: {'equity_pct': 62.5, 'decision': 'CALL', 'reasoning': 'Combo draw'},
    )
    app._refresh_postflop()

    hands = logger.get_hands()
    assert len(hands) == 2
    flop_entry = hands[1]
    assert flop_entry.mode == 'postflop'
    assert flop_entry.hand == 'AKs'
    assert flop_entry.board == 'QdJd2s'
    assert flop_entry.equity == pytest.approx(62.5)
    assert flop_entry.pot_size == pytest.approx(120.0)
    assert flop_entry.position == 'BTN'
    assert flop_entry.spot == 'open'
    assert flop_entry.recommended_action == 'CALL'

    # 3. Repeating the exact same street/board within 2s is deduplicated
    app._refresh_postflop()
    assert len(logger.get_hands()) == 2

    # 4. Advancing to the turn (QdJd2sTs) within 2s logs a new entry
    app.board_entry = Mock(get=Mock(return_value='QdJd2sTs'))
    app.pot_entry = Mock(get=Mock(return_value='200'))
    monkeypatch.setattr(
        rta,
        'get_postflop_advice',
        lambda **kw: {'equity_pct': 88.0, 'decision': 'RAISE', 'reasoning': 'Nut straight'},
    )
    app._refresh_postflop()

    hands = logger.get_hands()
    assert len(hands) == 3
    turn_entry = hands[2]
    assert turn_entry.mode == 'postflop'
    assert turn_entry.board == 'QdJd2sTs'
    assert turn_entry.equity == pytest.approx(88.0)
    assert turn_entry.pot_size == pytest.approx(200.0)
    assert turn_entry.recommended_action == 'RAISE'

    summary = analytics_calc.get_summary()
    assert summary['total_hands'] == 3
    assert summary['preflop_hands'] == 1
    assert summary['postflop_hands'] == 2
    assert summary['avg_postflop_equity'] == pytest.approx((62.5 + 88.0) / 2)


def test_hand_logger_async_save_and_flush(tmp_path):
    from analytics import HandLogger
    log_file = tmp_path / 'buffered_log.json'
    logger = HandLogger(log_path=str(log_file), async_save=True, debounce_seconds=5.0)

    logger.log_analysis(hand='QQ', recommended_action='RAISE', confidence=90.0, position='CO', spot='open')
    logger.log_analysis(hand='JTs', recommended_action='CALL', confidence=75.0, position='BTN', spot='facing_open')
    assert logger._dirty is True

    # Explicitly flush and verify deterministic disk persistence
    logger.flush()
    assert logger._dirty is False
    assert log_file.exists()
    persisted = json.loads(log_file.read_text())
    assert persisted['total_hands'] == 2
    assert [h['hand'] for h in persisted['hands']] == ['QQ', 'JTs']


def test_refresh_analytics_populates_position_breakdown(app, tmp_path, monkeypatch):
    from analytics import HandLogger, Analytics
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', True)

    logger = HandLogger(log_path=str(tmp_path / 'pos_analytics.json'))
    analytics_calc = Analytics(logger)
    app._logger = logger
    app._analytics = analytics_calc

    app.analytics_empty = Mock()
    app._analytics_stats_row = Mock()
    app._analytics_dist_label = Mock()
    app._analytics_action_rows = [Mock(), Mock(), Mock(), Mock()]
    app._analytics_pos_label = Mock()
    app._analytics_pos_frame = Mock()
    app._analytics_exports = Mock()
    app.analytics_labels = {
        k: Mock() for k in ('total_hands', 'gto_adherence', 'wins', 'losses', 'win_rate', 'followed')
    }
    app.action_labels = {act: (Mock(winfo_width=Mock(return_value=200)), Mock()) for act in ('RAISE', 'CALL', 'FOLD', 'CHECK')}
    app.position_stat_labels = {pos: Mock() for pos in ('UTG', 'MP', 'CO', 'BTN', 'SB', 'BB')}

    # Empty state hides position breakdown widgets
    app._refresh_analytics()
    app._analytics_pos_label.pack_forget.assert_called_once()
    app._analytics_pos_frame.pack_forget.assert_called_once()

    # Log hands in BTN and BB and verify positional breakdown labels update
    logger.log_analysis(hand='AA', recommended_action='RAISE', confidence=95.0, position='BTN', spot='open')
    logger.log_analysis(hand='KQs', recommended_action='RAISE', confidence=85.0, position='BTN', spot='open')
    logger.log_analysis(hand='72o', recommended_action='FOLD', confidence=99.0, position='BB', spot='facing_open')

    app._refresh_analytics()
    app.position_stat_labels['BTN'].configure.assert_called_with(text='2 (RAISE)')
    app.position_stat_labels['BB'].configure.assert_called_with(text='1 (FOLD)')
    app.position_stat_labels['UTG'].configure.assert_called_with(text='0 hands')


def test_mixed_rng_cache_stability_and_non_colliding_shortcuts(app):
    # 1. Mixed RNG roll remains stable across repeated refreshes for the same hand/spot
    app.pos_var.set('UTG')
    app.kind_var.set('open')
    app.hand = '54s'  # Mixed UTG open hand (RAISE 50% / FOLD 50%)
    app.cell_mix_indicators = {h: Mock() for h in ranges.all_hands()}
    app._refresh()
    detail_first = app.advice_detail.get()
    assert 'RNG ' in detail_first
    for _ in range(5):
        app._refresh()
        assert app.advice_detail.get() == detail_first
    # Verify mixed indicator bar on '54s' is highlighted in amber (#f59e0b)
    app.cell_mix_indicators['54s'].configure.assert_called_with(bg='#f59e0b')

    # 2. Keyboard shortcuts '3' and '4' select BB and UTG (no collision with 3-bet/4-bet)
    app.root = Mock(focus_get=Mock(return_value=None))
    app.vs_row = Mock()
    ev_3 = Mock(keysym='3', char='3', state=0)
    app._on_key_shortcut(ev_3)
    assert app.pos_var.get() == 'BB'

    ev_4 = Mock(keysym='4', char='4', state=0)
    app._on_key_shortcut(ev_4)
    assert app.pos_var.get() == 'UTG'

    ev_t = Mock(keysym='t', char='t', state=0)
    app._on_key_shortcut(ev_t)
    assert app.kind_var.get() == 'facing_3bet'

    ev_q = Mock(keysym='q', char='q', state=0)
    app._on_key_shortcut(ev_q)
    assert app.kind_var.get() == 'facing_4bet'

    ev_i = Mock(keysym='i', char='i', state=0)
    app._on_key_shortcut(ev_i)
    assert app.kind_var.get() == 'iso_raise'


