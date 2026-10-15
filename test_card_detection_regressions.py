"""Regression coverage for real fanned cards and window capture failures."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

import ocr
from multitable import MultiTableManager


@pytest.mark.parametrize('name,expected', [('ggpoker_87s.png', '87s'), ('ggpoker_53o.png', '53o'), ('ggpoker_AJo.png', 'AJo')])
@pytest.mark.parametrize('scale', [1, .75, .5])
def test_real_overlapping_cards(name, expected, scale):
    # Fixtures omit the seat label; retain the original card geometry.
    with Image.open(Path(__file__).parent / 'tests' / 'fixtures' / name) as crop:
        cards = Image.new('RGB', (406, 274), 'white')
        cards.paste(crop)
    cards = cards.resize((round(406 * scale), round(274 * scale)))
    assert ocr._read_region_hand(cards, dict(x=0, y=0, w=1, h=1)) == expected


def test_quartz_discovery_filters_lobby_and_dialogs(monkeypatch):
    def window(name, number, visible=True):
        return {'kCGWindowOwnerName': 'GGPoker', 'kCGWindowName': name,
                'kCGWindowNumber': number, 'kCGWindowIsOnscreen': visible,
                'kCGWindowLayer': 0,
                'kCGWindowBounds': dict(X=-1200, Y=33, Width=1200, Height=800)}
    windows = [window('GGPoker', 1), window('Cashier', 2),
               window('NLHP Green 08 - 100 / 200', 3),
               window('NLHP White 18 - 200 / 500', 4, False)]
    import sys
    monkeypatch.setitem(sys.modules, 'Quartz', SimpleNamespace(
        CGWindowListCopyWindowInfo=lambda option, _: windows if option == 0 else [w for w in windows if w['kCGWindowIsOnscreen']],
        kCGWindowListOptionAll=0, kCGWindowListOptionOnScreenOnly=1, kCGNullWindowID=0))
    monkeypatch.setattr(ocr, '_WINDOW_IDS', {})
    monkeypatch.setattr(ocr.subprocess, 'run', Mock(side_effect=AssertionError('AppleScript used')))
    bounds = ocr.find_ggpoker_window()
    assert bounds == (-1200, 33, 1200, 800)
    assert ocr._WINDOW_IDS[bounds] == 3
    assert ocr._CLIENT == 'ggpoker'
    assert ocr.find_ggpoker_window('missing') is None


def test_no_table_does_not_scan_desktop(monkeypatch):
    monkeypatch.setattr(ocr, '_quartz_tables', lambda: [])
    monkeypatch.setattr(ocr, 'find_pokerfair_window', Mock(side_effect=AssertionError('desktop scan')))
    assert ocr.find_ggpoker_window() is None


def test_capture_uses_window_id_not_desktop_rectangle(monkeypatch):
    bounds = (20, 30, 1200, 800)
    monkeypatch.setattr(ocr, '_WINDOW_IDS', {bounds: 42})
    commands = []
    def capture(command, **kwargs):
        commands.append(command)
        Image.new('RGB', (2400, 1600), 'white').save(command[-1])
    monkeypatch.setattr(ocr.subprocess, 'run', capture)
    assert ocr.capture_window(bounds).size == (2400, 1600)
    assert commands[0][1:-1] == ['-x', '-o', '-l', '42']


def test_failed_window_capture_does_not_read_overlay(monkeypatch):
    bounds = (20, 30, 1200, 800)
    monkeypatch.setattr(ocr, '_WINDOW_IDS', {bounds: 42})
    capture = Mock()
    monkeypatch.setattr(ocr.subprocess, 'run', capture)
    assert ocr.capture_window(bounds) is None
    assert capture.call_count == 1


def test_capture_window_uses_in_memory_quartz_when_available(monkeypatch):
    import types
    bounds = (20, 30, 1200, 800)
    monkeypatch.setattr(ocr, '_WINDOW_IDS', {bounds: 42})
    fake_quartz = types.SimpleNamespace(
        CGRectNull=object(),
        kCGWindowListOptionIncludingWindow=8,
        kCGWindowImageBoundsIgnoreFraming=1,
        CGWindowListCreateImage=lambda rect, opt, wid, img_opt: ('cg_img', wid),
        CGImageGetWidth=lambda cg: 4,
        CGImageGetHeight=lambda cg: 2,
        CGImageGetDataProvider=lambda cg: 'provider',
        CGDataProviderCopyData=lambda prov: bytes([10, 20, 30, 255] * 8),
        CGImageGetBytesPerRow=lambda cg: 16,
    )
    monkeypatch.setitem(ocr.sys.modules, 'Quartz', fake_quartz)
    subproc = Mock(side_effect=AssertionError('subprocess should not be called when Quartz succeeds'))
    monkeypatch.setattr(ocr.subprocess, 'run', subproc)
    img = ocr.capture_window(bounds)
    assert img is not None
    assert img.size == (4, 2)
    assert img.mode == 'RGBA'
    assert img.getpixel((0, 0)) == (30, 20, 10, 255)
    assert subproc.call_count == 0


def test_window_error_survives_position_result(monkeypatch):
    monkeypatch.setattr(ocr, 'find_ggpoker_window', lambda: None)
    result = ocr.capture_and_read_with_position(max_retries=0)
    assert result['hand'] is None
    assert result['status'] == 'error'
    assert result['error'] == 'No poker window found'


def test_position_delegates_once_with_bounded_image(monkeypatch):
    detector = Mock(return_value={'dealer_button': (100, 100)})
    monkeypatch.setattr(ocr, 'HAS_POSITION_DETECTOR', True)
    monkeypatch.setattr(ocr, '_detect_position_and_spot', detector)
    result = ocr.detect_position_and_spot(Image.new('RGB', (3200, 2400)))
    assert detector.call_count == 1
    assert detector.call_args.args[0].size == (800, 600)
    assert result['dealer_button'] == (400, 400)


def test_table_selector_shares_discovery_and_stable_ids(monkeypatch):
    window = dict(name='NLHP Green 08 - 100 / 200', bounds=(0, 0, 1200, 800),
                  window_id=42, is_frontmost=True)
    monkeypatch.setattr(ocr, 'find_all_poker_tables', lambda: [window])
    manager = MultiTableManager()
    first, second = manager.detect_tables(), manager.detect_tables()
    assert list(first) == list(second) == ['window_42']
    manager.refresh()
    assert manager.get_active_table_id() == 'window_42'


def test_patterned_card_backs_are_not_a_hand():
    with Image.open(Path(__file__).parent / 'debug_capture.png') as image:
        assert ocr._read_hand_with_fallback(image) is None


@pytest.mark.parametrize('scale', [.75, 1, 1.5, 2])
def test_card_edge_fragment_is_not_a_rank(scale):
    # The black sliver touching the upper-left crop edge used to match J
    # ahead of the actual ace on this 1x-display screenshot.
    with Image.open(Path(__file__).parent / 'tests' / 'fixtures' / 'ggpoker_A3s.png') as image:
        cards = image.resize((round(image.width * scale), round(image.height * scale)))
    assert ocr._read_region_hand(cards, dict(x=0, y=0, w=1, h=1)) == 'A3s'


@pytest.mark.parametrize('name,expected', [('ggpoker_A3s.png', 'A3s'), ('ggpoker_T4s.png', 'T4s')])
def test_native_display_capture_with_edge_fragment(monkeypatch, name, expected):
    table = Image.new('RGB', (1517, 1074), (20, 100, 20))
    with Image.open(Path(__file__).parent / 'tests' / 'fixtures' / name) as cards:
        table.paste(cards, (int(table.width * ocr.CARD_REGION['x']),
                            int(table.height * ocr.CARD_REGION['y'])))
    monkeypatch.setattr(ocr, '_CLIENT', 'ggpoker')
    monkeypatch.setattr(ocr, 'find_ggpoker_window', lambda: (197, 6, 1517, 1074))
    monkeypatch.setattr(ocr, 'capture_window', lambda rect: table)
    result = ocr.capture_and_read_with_position(max_retries=0)
    assert result['hand'] == expected
    assert result['status'] == 'detected'


@pytest.mark.parametrize('scale', [.75, 1, 1.5, 2])
def test_red_badge_touching_spade_does_not_change_suit(scale):
    with Image.open(Path(__file__).parent / 'tests' / 'fixtures' / 'ggpoker_T4s.png') as image:
        cards = image.resize((round(image.width * scale), round(image.height * scale)))
    assert ocr._read_region_hand(cards, dict(x=0, y=0, w=1, h=1)) == 'T4s'
