"""Seat orientation, content sizing, and live guidance while the main UI is hidden."""
import tkinter as tk
from unittest.mock import Mock
import pytest
import rta
from ui import diagram_positions


@pytest.mark.parametrize('hero',['UTG','MP','CO','BTN','SB','BB'])
def test_manual_diagram_rotates_hero_to_bottom(hero):
    seats=diagram_positions(hero)
    assert seats[3]==hero
    assert set(seats.values())=={'UTG','MP','CO','BTN','SB','BB'}
    dealer=next(s for s,p in seats.items() if p=='BTN')
    assert seats[(dealer+1)%6]=='SB'
    assert seats[(dealer+2)%6]=='BB'


def test_detected_short_table_preserves_physical_seats():
    seats={0:'UTG',1:'BTN',2:'SB',3:'BB',4:'CO'}
    assert diagram_positions('BB',seats)==seats
    assert diagram_positions('',{})=={}
    assert diagram_positions('CO',seats,manual=True)[3]=='CO'


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(rta,'HAS_MULTITABLE',False)
    monkeypatch.setattr(rta,'HAS_ANALYTICS',False)
    try:
        root=tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display unavailable')
    root.withdraw()
    app=rta.RTAApp(root)
    app._play_sound=Mock()
    yield app
    app._on_close()


def test_diagram_and_opener_row_fit_at_runtime(app):
    app._preflop_context={'positions':{0:'UTG',1:'BTN',2:'SB',3:'BB',4:'CO'}}
    app.pos_var.set('BB')
    assert app._diagram_positions[3]=='BB'
    assert app._diagram_positions[1]=='BTN'
    assert 5 not in app._diagram_positions
    app.kind_var.set('facing_open')
    app._on_spot_change()
    app.root.deiconify()
    app.root.update_idletasks()
    container=app.vs_row_container
    assert container.winfo_height()>=app.vs_row.winfo_reqheight()
    for child in app.vs_row.winfo_children():
        assert child.winfo_y()+child.winfo_height()<=app.vs_row.winfo_height()


def test_compact_shares_live_advice_and_keeps_detection_running(app):
    stop=Mock()
    app._stop_ocr=stop
    app.compact.show()
    app.root.update_idletasks()
    assert app.root.state()=='withdrawn'
    assert app.compact.window.state()=='normal'
    app.advice_var.set('RAISE AA')
    app.advice_detail.set('Confirmed context')
    app._exact_cards=('As','Ah')
    app.compact.sync()
    assert app.compact.action.cget('text')=='RAISE AA'
    assert 'As Ah' in app.compact.context.get()
    app.mode_var.set('postflop')
    app._on_mode_change()
    assert app.compact.action.cget('text')=='Postflop inputs incomplete'
    app.board_entry.insert(0,'Td9cTh')
    app.equity_var.set('Equity: 45%')
    app.compact.sync()
    assert 'Td9cTh' in app.compact.context.get()
    assert '45%' in app.compact.metrics.get()
    stop.assert_not_called()
    app.compact.restore()
    app.root.update_idletasks()
    assert app.root.state()=='normal' and app.compact.window.state()=='withdrawn'
    assert app.compact.timer is None


def test_tray_check_synchronizes_and_persists_with_compact_on_minimise(app, tmp_path):
    cfg_file = tmp_path / 'config.ini'
    app._config_path = str(cfg_file)
    assert app.tray_var is app.compact.on_minimise
    assert app.compact.on_minimise.get() == bool(app._minimize_to_tray)

    app.tray_var.set(True)
    app._on_tray_change()
    assert app._minimize_to_tray is True
    assert app.compact.on_minimise.get() is True
    assert app._save_config(str(cfg_file)) is True
    assert app._load_config(str(cfg_file))['minimize_to_tray'] is True

    app.tray_var.set(False)
    app._on_tray_change()
    assert app._minimize_to_tray is False
    assert app.compact.on_minimise.get() is False
    assert app._save_config(str(cfg_file)) is True
    assert app._load_config(str(cfg_file))['minimize_to_tray'] is False
