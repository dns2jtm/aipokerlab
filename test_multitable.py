from types import SimpleNamespace
from unittest.mock import Mock
import sys
import threading

import pytest
from PIL import Image

import ocr
from detection_state import CardReading
from multitable import MultiTableManager, TableState


@pytest.fixture(autouse=True)
def isolate_capture_state(monkeypatch):
    monkeypatch.setattr(ocr, '_CLIENT', 'ggpoker')
    monkeypatch.setattr(ocr, '_WINDOW_IDS', {})
    monkeypatch.setattr(ocr, '_WINDOW_CLIENTS', {})


def window(number, owner='GGnet', name='NLHP Green 02 - 100 / 200', x=0, y=0):
    return dict(kCGWindowNumber=number, kCGWindowOwnerName=owner, kCGWindowName=name,
                kCGWindowOwnerPID=100 + number, kCGWindowLayer=0,
                kCGWindowBounds=dict(X=x, Y=y, Width=1000, Height=700))


def quartz(monkeypatch, windows, visible):
    api = SimpleNamespace(kCGWindowListOptionAll=0, kCGWindowListOptionOnScreenOnly=1, kCGNullWindowID=0,
                          CGWindowListCopyWindowInfo=lambda option, _: windows if option == 0 else [w for w in windows if w['kCGWindowNumber'] in visible])
    monkeypatch.setitem(sys.modules, 'Quartz', api)


def test_multiple_clients_hidden_tables_and_lobby_filter(monkeypatch):
    windows = [window(1), window(2, 'PokerStarsOnBetfair', "Datura VII - No Limit Hold'em $0.01/$0.02 USD"),
               window(3, 'PokerStars', 'PokerStars Lobby'), window(4, 'GGnet', 'Cashier 1/2'),
               window(5, 'Safari', 'PokerStars 1/2'), window(6, 'PokerFair', "Hold'em 1/2"),
               window(7, 'GGnet', 'Hand History NLH 100/200')]
    quartz(monkeypatch, windows, {2, 3, 4, 5, 7})
    tables = ocr.find_all_poker_tables()
    assert {t['window_id'] for t in tables} == {1, 2, 6}
    assert {t['client'] for t in tables} == {'ggpoker', 'pokerstars', 'pokerfair'}
    assert tables[0]['window_id'] == 2 and tables[0]['is_frontmost']
    assert not next(t for t in tables if t['window_id'] == 1)['visible']


@pytest.mark.parametrize('owner', ['PokerStars', 'PokerStarsOnBetfair', 'PokerStars UK', 'PokerStarsEU'])
def test_pokerstars_process_variants(owner):
    assert ocr._poker_client(owner) == 'pokerstars'


def test_spin_and_gold_discovery_alongside_other_clients(monkeypatch):
    title = 'Spin & Gold 6-Max $0.25 - Blinds 10 | 20'
    windows = [window(195, 'GGPoker', title),
               window(196, 'GGPoker', title),
               window(2, 'PokerStars', "Datura VII - Hold'em $0.01/$0.02"),
               window(179, 'GGPoker', 'GGPoker'),
               window(180, 'GGPoker', 'Spin & Gold Lobby - Blinds 10 | 20')]
    quartz(monkeypatch, windows, {195, 2, 179})
    manager = MultiTableManager()
    manager.refresh()
    assert {t.window_id for t in manager.get_tables().values()} == {195,196,2}
    active = manager.get_active_table()
    assert active.window_id == 195 and active.client == 'ggpoker'
    assert active.stakes == '10/20'
    # A blind-level change updates the existing window, not its identity.
    windows[0]['kCGWindowName'] = title.replace('10 | 20', '20 | 40')
    manager.refresh()
    assert manager.get_active_table().window_id == 195
    assert manager.get_active_table().stakes == '20/40'


def test_same_titles_and_bounds_capture_exact_window(monkeypatch):
    quartz(monkeypatch, [window(1), window(2)], {1, 2})
    capture = Mock(return_value=Image.new('RGB', (1000, 700)))
    monkeypatch.setattr(ocr, 'capture_window', capture)
    monkeypatch.setattr(ocr, '_read_hand_with_fallback', lambda *a, **k: CardReading('AKs', ('As', 'Ks'), (1000, 1000), (1000, 1000), (1000, 1000)))
    monkeypatch.setattr(ocr, 'detect_position_and_spot', lambda img: dict(position='BTN'))
    result = ocr.capture_and_read_with_position(window_id=1)
    assert result['table_id'] == 1 and result['client'] == 'ggpoker'
    assert capture.call_args.kwargs['window_id'] == 1
    assert ocr.find_poker_window(window_id=999) is None
    capture.reset_mock()
    assert ocr.capture_and_read_with_position(window_id=999)['status'] == 'error'
    capture.assert_not_called()


def test_uncalibrated_client_never_uses_ggpoker_card_reader(monkeypatch):
    quartz(monkeypatch, [window(2, 'PokerFair', "Hold'em $0.01/$0.02")], {2})
    reader = Mock()
    monkeypatch.setattr(ocr, '_read_hand_with_fallback', reader)
    result = ocr.capture_and_read_with_position(window_id=2)
    assert result['status'] == 'unsupported' and result['client'] == 'pokerfair'
    assert result['cards'] is None
    reader.assert_not_called()


def table(number, front=False, visible=True, client='ggpoker', bounds=(0, 0, 1000, 700)):
    return dict(window_id=number, name='Same name 0.01/0.02', client=client,
                process_name=client, bounds=bounds, visible=visible, is_frontmost=front)


def test_first_snapshot_selects_table_and_preserves_identity_on_move(monkeypatch):
    discovered = [table(1, front=True), table(2, client='pokerstars')]
    monkeypatch.setattr(ocr, 'find_all_poker_tables', lambda: discovered)
    manager = MultiTableManager()
    manager.refresh()
    assert manager.get_active_table().window_id == 1
    assert len(manager.get_tables()) == 2
    identity = manager.get_active_table_id()
    discovered[0]['bounds'] = (-1200, 30, 1100, 800)
    discovered[0]['name'] = 'Renamed 0.02/0.04'
    manager.refresh()
    assert manager.get_active_table_id() == identity
    assert manager.get_active_table().bounds[0] == -1200
    assert manager.get_active_table().stakes == '0.02/0.04'
    assert len({label for label, _ in manager.get_table_list()}) == 2


def test_pin_survives_focus_changes_and_closed_table_never_redirects(monkeypatch):
    discovered = [table(1, front=True), table(2)]
    monkeypatch.setattr(ocr, 'find_all_poker_tables', lambda: discovered)
    manager = MultiTableManager()
    manager.refresh()
    assert manager.set_active_table('window_2')
    manager.refresh()
    assert manager.get_active_table().window_id == 2
    discovered.pop()
    manager.refresh()
    assert manager.get_active_table() is None
    manager.set_follow_focus(True)
    manager.refresh()
    assert manager.get_active_table().window_id == 1


def test_callbacks_can_read_manager_without_deadlock(monkeypatch):
    monkeypatch.setattr(ocr, 'find_all_poker_tables', lambda: [table(1, front=True)])
    manager = MultiTableManager()
    received = []
    callback = lambda *args: received.append(manager.get_tables())
    assert manager.add_callback(callback) is callback
    thread = threading.Thread(target=manager.refresh, daemon=True)
    thread.start()
    thread.join(timeout=1)
    assert not thread.is_alive() and received
    manager.remove_callback(callback)


def test_ui_rejects_result_from_other_window_with_identical_title(monkeypatch):
    import rta
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', True)
    app = rta.RTAApp.__new__(rta.RTAApp)
    app._multitable_manager = Mock()
    app._multitable_manager.get_active_table.return_value = SimpleNamespace(name='Same', window_id=2, visible=True)
    assert app._capture_target() == dict(table_name='Same', window_id=2)
    assert not app._matches_selected_window(dict(table_id=1, table_name='Same'))
    assert app._matches_selected_window(dict(table_id=2, table_name='Same'))
    app._multitable_manager.get_active_table.return_value.visible = False
    with pytest.raises(RuntimeError, match='hidden'):
        app._capture_target()


def test_client_context_is_local_to_each_worker(monkeypatch):
    barrier = threading.Barrier(2)
    clients = []
    def worker(client):
        token = ocr._capture_client.set(client)
        try:
            barrier.wait(timeout=1)
            clients.append((client, ocr._get_client()))
        finally:
            ocr._capture_client.reset(token)
    workers = [threading.Thread(target=worker, args=(client,)) for client in ('ggpoker', 'pokerstars')]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join(timeout=2)
    assert sorted(clients) == [('ggpoker', 'ggpoker'), ('pokerstars', 'pokerstars')]


def test_explicit_window_id_overrides_same_bounds_cache(monkeypatch):
    bounds = (0, 0, 1000, 700)
    ocr._WINDOW_IDS[bounds] = 2
    commands = []
    def capture(command, **kwargs):
        commands.append(command)
        Image.new('RGB', (1000, 700)).save(command[-1])
    monkeypatch.setattr(ocr.subprocess, 'run', capture)
    assert ocr.capture_window(bounds, window_id=1) is not None
    assert commands[0][1:-1] == ['-x', '-o', '-l', '1']


def test_switching_table_clears_hand_context_and_reads_new_blinds(monkeypatch):
    import tkinter as tk
    import rta
    monkeypatch.setattr(rta, 'HAS_MULTITABLE', False)
    monkeypatch.setattr(rta, 'HAS_ANALYTICS', False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display is unavailable')
    root.withdraw()
    app = rta.RTAApp(root)
    try:
        monkeypatch.setattr(rta, 'HAS_MULTITABLE', True)
        app._multitable_manager = Mock()
        app._multitable_manager.get_active_table.return_value = SimpleNamespace(name="Datura VII - Hold'em $0.01/$0.02")
        app._current_table_id = 'window_1'
        app.hand_entry.insert(0, 'AsKh')
        app.hand = 'AKo'
        app._context_cards = (1, ('As', 'Kh'))
        app._big_blind_override = 200
        for entry in (app.board_entry, app.pot_entry, app.call_entry):
            entry.insert(0, '100')
        app._set_table_context('window_2')
        assert app.hand is None and app._context_cards is None
        assert app.hand_entry.get() == app.board_entry.get() == app.pot_entry.get() == app.call_entry.get() == ''
        assert app.pos_var.get() == app.kind_var.get() == ''
        assert app._big_blind == .02 and app._big_blind_override is None
        assert app.big_blind_var.get() == '0.02'
        assert app._current_action is None
    finally:
        app._on_close()
