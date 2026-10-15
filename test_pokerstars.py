"""Real PokerStars captures plus adverse-input and capture-pipeline regressions."""
from pathlib import Path
from unittest.mock import Mock
import time

import pytest
from PIL import Image, ImageDraw
import ocr
import pokerstars as ps
from table_context import PreflopTracker

FIXTURES=Path(__file__).parent/'tests/fixtures'

@pytest.fixture(autouse=True)
def client():
    token=ocr._capture_client.set('pokerstars')
    yield
    ocr._capture_client.reset(token)


def frame(name):
    return Image.open(FIXTURES/f'pokerstars_{name}.png').convert('RGB')


@pytest.mark.parametrize('scale',[.5,.75,1,1.25])
@pytest.mark.parametrize('name,cards',[('preflop',('Qh','8s')),('kq',('Kc','Qd')),('flop_j9',('Jc','9s'))])
def test_exact_hole_cards_at_multiple_scales(name,cards,scale):
    img=frame(name);img=img.resize((round(img.width*scale),round(img.height*scale)))
    reading=ocr._read_hand_with_fallback(img,detailed=True)
    assert reading and reading.reliable and reading.cards==cards


@pytest.mark.parametrize('scale',[.5,.75,1,1.25])
@pytest.mark.parametrize('name,board',[('river','2sKhQs8d9h'),('empty_seat','JcAs4d3s4c')])
def test_exact_boards_and_opponent_showdown_never_becomes_hero(name,board,scale):
    img=frame(name);img=img.resize((round(img.width*scale),round(img.height*scale)))
    assert ocr.detect_board_cards(img)==board
    assert ocr._read_hand_with_fallback(img,detailed=True) is None


def test_live_buttons_only_and_decimal_amounts():
    assert ocr.detect_pot_size(frame('kq'))==.03
    assert ocr.detect_call_amount(frame('kq'))==.01
    assert ocr.detect_pot_size(frame('river'))==.05
    # The supplied preflop screenshot has Call $0.02 as a checkbox.
    assert ocr.detect_call_amount(frame('preflop')) is None
    assert ocr.detect_call_amount(frame('river')) is None


def test_real_frame_to_position_stack_depth_and_guidance():
    img=frame('kq')
    reading=ps.read_hand(img)
    position=ocr.detect_position_and_spot(img)
    assert position['position']=='SB'
    data=ocr.detect_preflop_context(img,position,"Datura VII - Hold'em $0.01/$0.02")
    assert data['complete'] and data['bets']=={0:0,1:0,2:0,3:.01,4:.02,5:0}
    assert data['stacks'][3]==5.72
    tracker=PreflopTracker()
    observation=dict(table_id=42,cards=reading.cards,reliable=True,preflop=data)
    tracker.update(observation)
    result=tracker.update(observation)
    assert result['spot']=='open'
    assert result['effective_bb']==126
    assert result['hero_bb']==pytest.approx(286.5)
    assert data['call']==.01 and data['pot']==.03


def test_empty_seat_is_explicit_and_occlusion_does_not_change_position():
    position=ps.position(frame('empty_seat'))
    assert position['position']=='UTG' and len(position['occupied_seats'])==5
    # The RTA overlay obscures two stacks and dealer in the supplied screenshot.
    assert ps.position(frame('preflop'))['position'] is None


def test_missing_rank_and_card_backs_are_rejected():
    img=frame('preflop')
    ImageDraw.Draw(img).rectangle((1175,1202,1218,1266),fill='white')
    assert ps.read_hand(img) is None
    for x,y,w in ps.hole_rects(frame('preflop')):
        ImageDraw.Draw(img).rectangle((x,y,x+w,y+w),fill=(174,142,54))
    assert ps.read_hand(img) is None


def test_capture_pipeline_enables_pokerstars_and_preserves_identity(monkeypatch):
    img=frame('kq')
    monkeypatch.setattr(ocr,'find_poker_window',lambda **kwargs:(0,0,1337,950))
    monkeypatch.setattr(ocr,'_WINDOW_CLIENTS',{42:'pokerstars'})
    capture=Mock(return_value=img)
    monkeypatch.setattr(ocr,'capture_window',capture)
    result=ocr.capture_and_read_with_position(window_id=42,table_name='0.01/0.02',include_context=True)
    assert result['status']=='detected' and result['cards']==('Kc','Qd')
    assert result['table_id']==42 and result['preflop']['complete']
    assert capture.call_args.kwargs=={'window_id':42}
    capture.return_value=frame('river')
    result=ocr.capture_and_read_full_state(window_id=42,table_name='0.01/0.02')
    assert result['board']=='2sKhQs8d9h' and result['pot_size']==.05
    assert result['cards'] is None and result['call_amount'] is None


def test_independent_live_flop_capture():
    # This later capture was not used to create the glyph templates.
    img=frame('flop_j9')
    assert ocr.detect_board_cards(img)=='9d7c6h'
    assert ocr.detect_pot_size(img)==.18
    assert ocr.detect_call_amount(img) is None


def test_sitting_out_and_live_check_button():
    img=frame('sitting_out')
    position=ps.position(img)
    assert position['position']=='CO'
    assert 1 not in position['occupied_seats']
    assert ocr.detect_board_cards(img)=='5cAsJc'
    assert ocr.detect_call_amount(img)==0
    assert ocr._read_hand_with_fallback(img,detailed=True).cards==('Ad','2s')


def test_blinds_at_top_and_upper_left_with_sitting_out_seat():
    img=frame('baseline_j6')
    position=ps.position(img)
    assert position['position']=='CO'
    data=ocr.detect_preflop_context(img,position,'0.01/0.02')
    assert data['complete']
    assert data['bets']=={0:.02,2:0,3:0,4:0,5:.01}
    assert data['stacks'][0]==1.98
    reading=ps.read_hand(img)
    assert reading.cards==('Jh','6s')
    tracker=PreflopTracker()
    observation=dict(table_id=42,cards=reading.cards,reliable=True,preflop=data)
    tracker.update(observation)
    result=tracker.update(observation)
    assert result['effective_bb']==100
    assert result['spot'] is None  # Still showing pre-action checkboxes.
    assert not tracker.lost


@pytest.mark.parametrize('scale', [.5, .75, 1, 1.25])
@pytest.mark.parametrize('name,position,bets', [
    ('kq', 'SB', {0:0,1:0,2:0,3:.01,4:.02,5:0}),
    ('four_seat_blinds', 'BB', {0:0,2:.01,3:.02,4:0}),
    ('four_seat_call', 'BB', {0:0,2:.05,3:.02,4:.05}),
    ('wide_wagers', 'CO', {0:0,1:0,2:0,3:0,4:.16,5:.17}),
])
def test_positions_and_wagers_with_chip_artwork_and_red_hero_suit(name, position, bets, scale):
    img=frame(name)
    img=img.resize((round(img.width*scale), round(img.height*scale)))
    info=ps.position(img)
    assert info['position']==position
    data=ocr.detect_preflop_context(img,info,'0.01/0.02')
    assert data['complete'] and data['bets']==bets
    assert data['pot']==pytest.approx(sum(bets.values()))


@pytest.mark.parametrize('text,expected', [
    ('$0.05 f=', (.05,None)), ('i\nt=} $0.05', (.05,None)),
    ('1c', None), ('$4,90', None), ('$0.05 $0.10', None), ('25 BB',(25,'bb')),
])
def test_amount_labels_are_distinct_from_chip_denominations(text,expected):
    assert ps.amount_text(text)==expected


def test_illegible_wager_is_not_assumed_zero():
    img=Image.new('RGB',(200,60),(20,90,35))
    draw=ImageDraw.Draw(img)
    draw.rectangle((70,15,85,45),fill='white')
    assert not ps.blank_amount(img)


@pytest.mark.parametrize('scale', [.5, .75, 1, 1.25])
@pytest.mark.parametrize('name,board,pot', [('t9t','Td9cTh',.23), ('t62','Th6d2c',.06)])
def test_reported_boards_with_two_digit_tens(name,board,pot,scale):
    # t9t supplied the ten template; t62 is a separate, independent screenshot.
    img=frame(name)
    img=img.resize((round(img.width*scale),round(img.height*scale)))
    assert ocr.detect_board_cards(img)==board
    assert ocr.detect_pot_size(img)==pot
    assert ocr.detect_call_amount(img)==0


@pytest.mark.parametrize('digit', ['one','zero'])
def test_incomplete_ten_is_not_accepted(digit):
    area=ocr._crop(frame('t62'),ps.BOARD)
    x,y,w,h=ocr._locate_board_cards(area)[0]
    card=area.crop((x,y,x+w,y+h))
    # Keep the other digit and suit intact: partial rank evidence must fail.
    box=(7,6,20,65) if digit=='one' else (20,6,48,65)
    ImageDraw.Draw(card).rectangle(box,fill='white')
    reading=ps.read_corner(card)
    assert reading is None or reading[0][0]!='T'


def test_reported_ten_board_through_full_capture(monkeypatch):
    monkeypatch.setattr(ocr,'find_poker_window',lambda **kwargs:(0,0,1334,947))
    monkeypatch.setattr(ocr,'_WINDOW_CLIENTS',{42:'pokerstars'})
    monkeypatch.setattr(ocr,'capture_window',lambda *args,**kwargs:frame('t62'))
    result=ocr.capture_and_read_full_state(window_id=42,table_name='0.01/0.02')
    assert result['board']=='Th6d2c'
    assert result['cards']==('Ah','6s')
    assert result['pot_size']==.06 and result['call_amount']==0


def test_pokerstars_rank_5_6_7_templates_present_and_match_at_small_scales():
    for r in ('5', '6', '7'):
        assert (Path(__file__).parent / f'templates/pokerstars/rank_{r}.png').exists()
    for name, expected in [('flop_j9', '9d7c6h'), ('sitting_out', '5cAsJc'), ('wide_wagers', '7cQcAs9hTc')]:
        orig = frame(name)
        for scale in (.45, .6, 1.0):
            img = orig.resize((round(orig.width * scale), round(orig.height * scale)))
            assert ocr.detect_board_cards(img) == expected
