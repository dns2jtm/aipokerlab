"""PokerStars classic six-seat layout: exact corner glyphs and observable amounts.

Coordinates are relative to the complete table window, including its title bar.
Only the bottom-centre hero cards are eligible; opponent showdowns cannot be
used as the hero's hand. Different layouts fail closed on missing evidence.
"""
from functools import lru_cache
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont
from detection_state import CardReading

HOLE = dict(x=.43, y=.625, w=.14, h=.075)
BOARD = dict(x=.33, y=.34, w=.34, h=.145)
POT = dict(x=.445, y=.305, w=.13, h=.05)
CALL = dict(x=.665, y=.902, w=.16, h=.087)
STACKS = ((.435,.168,.075,.032), (.835,.264,.135,.032),
          (.87,.566,.11,.035), (.493,.743,.10,.033),
          (.045,.566,.11,.035), (.09,.263,.072,.035))
BETS = ((.548,.22,.095,.035), (.661,.287,.070,.045),
        (.648,.519,.115,.049), (.457,.568,.095,.047),
        (.256,.519,.11,.047), (.27,.313,.105,.037))
# Dealer puck positions vary slightly with seat label and chip placement.
SEATS = ((.50,.15),(.87,.25),(.89,.55),(.5,.73),(.11,.55),(.13,.25))


def crop_tuple(img, rect):
    import ocr
    return ocr._crop(img, dict(zip(('x','y','w','h'), rect)))


def amount_text(text):
    """Read a label even when adjacent chip artwork produces extra OCR tokens."""
    from table_context import parse_amount, NUMBER
    value = parse_amount(text)
    if value is not None:
        return value
    # Denominations printed on chip graphics are not wager labels. Require a
    # currency symbol for a partial-line match, and reject multiple amounts.
    matches = re.findall(r'[$£€]\s*' + NUMBER + r'(?:\s*BB)?(?=\s|$)', text, re.I)
    return parse_amount(matches[0]) if len(matches) == 1 else None


def _is_dealer_puck_component(area, points):
    """Return True if a bright neutral blob is the white PokerStars dealer puck."""
    xs, ys = zip(*points)
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if w < max(8, area.width * .06) or h < max(8, area.height * .25) or not (.65 <= w / h <= 2.1):
        return False
    rgb = area.convert('RGB')
    red_pixels = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            r, g, b = rgb.getpixel((x, y))
            if r > 155 and g < 115 and b < 115 and r > g + 45 and r > b + 45:
                red_pixels += 1
    return red_pixels >= max(4, round(w * h * .04))


def blank_amount(area):
    """Ignore clipped artwork at crop edges, but retain complete text glyphs."""
    import ocr
    # _ink_components expects dark foreground; build a neutral bright-text mask.
    mask = Image.new('L', area.size, 255)
    mask.putdata([0 if min(p) > 150 and max(p)-min(p) < 60 else 255
                  for p in area.convert('RGB').getdata()])
    for points in ocr._ink_components(mask.convert('RGB'), 128):
        xs, ys = zip(*points)
        if min(xs) == 0 or min(ys) == 0 or max(xs) == area.width-1 or max(ys) == area.height-1:
            continue
        if _is_dealer_puck_component(area, points):
            continue
        if max(ys)-min(ys) >= max(2, area.height*.15) and max(xs)-min(xs) >= 1:
            return False
    return True


def read_amount(area, *, bet=False):
    import ocr
    text = ocr._extract_text_from_image(area, threshold=130 if bet else 100, target_height=100 if bet else 80)
    value = amount_text(text)
    if value is not None or re.fullmatch(r'\s*Sitting\s+Out\s*', text, re.I):
        return value, text
    if bet and blank_amount(area):
        return (0, None), ''
    if bet:
        # Gold chip rims can make Tesseract merge '$' into the chip denomination
        # (e.g. '50.17'). Isolate the text beside the rim before retrying.
        import numpy as np
        px = np.asarray(area.convert('RGB')).astype(int)
        gold = (px[:,:,0]>140)&(px[:,:,1]>85)&(px[:,:,1]<px[:,:,0]*.9)&(px[:,:,2]<px[:,:,1]*.75)
        columns = np.flatnonzero(gold.sum(0) > max(2, area.height*.07))
        margin = max(2, round(area.height*.08))
        if len(columns) > area.height*.15:
            if columns[-1] < area.width*.45:
                area = area.crop((int(columns[-1])+margin, 0, area.width, area.height))
            elif columns[0] > area.width*.55:
                area = area.crop((0, 0, int(columns[0])-margin, area.height))
    # Retry dimmed/highlighted text locally, without another screen capture.
    retry = ocr._extract_text_from_image(area, threshold=170 if bet else 70, target_height=140)
    return amount_text(retry), retry or text


@lru_cache(maxsize=1)
def templates():
    import ocr
    ranks = {k: list(v) for k,v in ocr._build_templates().items()}
    suits = {k: [] for k in 'shdc'}
    for filename in ('Times New Roman.ttf', 'Times New Roman Bold.ttf', 'Georgia.ttf'):
        try:
            font = ImageFont.truetype('/System/Library/Fonts/Supplemental/' + filename, 80)
        except OSError:
            continue
        for rank in ranks:
            box = font.getbbox(rank)
            glyph = Image.new('L', (box[2]+10,box[3]-box[1]+10),255)
            ImageDraw.Draw(glyph).text((5,5-box[1]),rank,font=font,fill=0)
            ranks[rank].append(ocr._glyph_signature(glyph,255))
    for path in (Path(__file__).parent/'templates/pokerstars').glob('*.png'):
        kind, symbol = path.stem.split('_')[:2]
        signature = ocr._glyph_signature(Image.open(path),255)
        (ranks if kind == 'rank' else suits)[symbol].append(signature)
    return ranks, suits


def read_corner(card):
    """Use card width, since hero nameplates cover the lower card face."""
    import ocr
    width = card.width
    results = []
    for kind, rect in [('rank',(.035,.025,.285,.395)),('suit',(.035,.435,.285,.69))]:
        box = tuple(round(width*v) for v in rect)
        if box[3] > card.height:
            return None
        area = card.crop(box).convert('RGB')
        pixels = list(area.getdata())
        if sum(min(p)>115 and max(p)-min(p)<55 for p in pixels) / len(pixels) < .30:
            return None
        values = sorted(area.convert('L').getdata())
        background = max(180, values[int(len(values) * .75)]) if values else 240
        components = ocr._ink_components(area, background)
        if not components:
            return None
        points = max(components,key=len)
        if kind == 'rank':
            # This deck prints ten as "10": both disconnected digits belong
            # to the rank. Selecting only the largest component reads the zero.
            top, bottom = min(y for x,y in points), max(y for x,y in points)
            height = bottom-top+1
            aligned = [c for c in components
                       if max(y for x,y in c)-min(y for x,y in c)+1 >= height*.75
                       and abs(min(y for x,y in c)-top) <= width*.04
                       and abs(max(y for x,y in c)-bottom) <= width*.04]
            if len(aligned) == 2:
                left, right = sorted(aligned, key=lambda c:min(x for x,y in c))
                gap = min(x for x,y in right)-max(x for x,y in left)
                if 0 < gap <= width*.08:
                    points = left + right
        red = sum(ocr._is_red(area.getpixel(p)) for p in points)>len(points)/2
        candidates = templates()[0 if kind=='rank' else 1]
        if kind=='suit':
            candidates = {s:t for s,t in candidates.items() if s in ('hd' if red else 'sc')}
        symbol,distance,margin = ocr._match_rotated_glyph(ocr._component_image(points),candidates,with_margin=True)
        if symbol is None or distance > (12000 if kind=='rank' else 8500) or margin<600:
            return None
        results.append((symbol,distance,margin))
    return results


def hole_rects(img):
    """Locate two neutral card faces in a narrow hero-only region."""
    import numpy as np
    import ocr
    area = ocr._crop(img,HOLE)
    pixels = np.asarray(area.convert('RGB')).astype(int)
    for min_lum, max_spread in ((160, 40), (130, 50)):
        white = (pixels.min(2)>min_lum) & ((pixels.max(2)-pixels.min(2))<max_spread)
        # Horizontal runs of columns whose upper card section is largely white.
        columns = white.sum(0)>area.height*.15
        edges = np.flatnonzero(np.diff(np.r_[False,columns,False]))
        rects=[]
        for left,right in zip(edges[::2],edges[1::2]):
            if not img.width*.045 <= right-left <= img.width*.072:
                continue
            rows = np.flatnonzero(white[:,left:right].sum(1)>(right-left)*.60)
            if len(rows)==0:
                continue
            top=int(rows[0])
            rects.append((int(HOLE['x']*img.width)+int(left),int(HOLE['y']*img.height)+top,int(right-left)))
        if len(rects)==2:
            return rects
    return []


def read_hand(img):
    import ocr
    rects = hole_rects(img)
    if len(rects)!=2:
        return None
    results=[]
    for x,y,w in rects:
        reading = read_corner(img.crop((x,y,x+w,y+round(w*.72))))
        if not reading:
            return None
        results.append(reading)
    cards=tuple(r[0][0]+r[1][0] for r in results)
    if cards[0]==cards[1]:
        return None
    hi,lo=sorted((c[0] for c in cards),key=ocr.RANK_CHARS.index)
    hand=hi+lo if hi==lo else hi+lo+('s' if cards[0][1]==cards[1][1] else 'o')
    return CardReading(hand,cards,tuple(r[0][1] for r in results),tuple(r[0][2] for r in results),
                       tuple(r[1][1] for r in results),tuple(HOLE.values()))


def board_cards(img):
    import ocr
    for dy in (0.0, -0.02, 0.02):
        reg = dict(BOARD, y=max(0.0, min(1.0 - BOARD['h'], BOARD['y'] + dy)))
        area = ocr._crop(img, reg)
        rects = ocr._locate_board_cards(area)
        if len(rects) not in (3, 4, 5):
            continue
        cards = []
        for x, y, w, h in rects:
            reading = read_corner(area.crop((x, y, x + w, y + h)))
            if not reading:
                cards = []
                break
            cards.append(reading[0][0] + reading[1][0])
        if cards and len(set(cards)) == len(cards):
            return ''.join(cards)
    return None


def call_amount(img):
    """Require a live red action button; checkbox pre-actions are not a turn."""
    import numpy as np
    import ocr
    area=ocr._crop(img,CALL)
    pixels=np.asarray(area.convert('RGB')).astype(int)
    if ((pixels[:,:,0]>140)&(pixels[:,:,0]>pixels[:,:,1]*1.6)&(pixels[:,:,1]<110)).mean()<.35:
        return None
    text=ocr._extract_text_from_image(area)
    match=re.fullmatch(r'\s*Call\s*[$£€]?\s*('+ocr._AMOUNT_PATTERN+r')\s*(?:BB)?\s*',text,re.I)
    if match:
        return ocr._parse_amount(match[1])
    return 0 if re.fullmatch(r'\s*Check\s*',text,re.I) else None


def dealer_seat(img):
    """Identify the white PokerStars dealer puck by its red glyph and neutral rim."""
    import numpy as np
    small=img.copy(); small.thumbnail((800,600))
    px=np.asarray(small.convert('RGB')).astype(int)
    mask=(px[:,:,0]>165)&(px[:,:,1]<110)&(px[:,:,2]<110)
    ys,xs=np.where(mask)
    points={(int(x),int(y)) for x,y in zip(xs,ys) if .17*small.width<x<.83*small.width and .19*small.height<y<.60*small.height
            and not (.32*small.width<x<.68*small.width and .31*small.height<y<.50*small.height)}
    candidates=[]
    while points:
        seed=points.pop(); component=[seed]; queue=[seed]
        while queue:
            x,y=queue.pop()
            for p in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if p in points: points.remove(p);queue.append(p);component.append(p)
        xs,ys=zip(*component); w=max(xs)-min(xs)+1;h=max(ys)-min(ys)+1
        if not (.010*small.width<w<.03*small.width and .7<w/h<2.0): continue
        cx,cy=(min(xs)+max(xs))/2,(min(ys)+max(ys))/2
        # A chip with denomination text has a dark centre, not the red star/spade.
        radius=round(w*.85)
        patch=px[max(0,round(cy)-radius):round(cy)+radius,max(0,round(cx)-radius):round(cx)+radius]
        neutral=(patch.min(2)>145)&((patch.max(2)-patch.min(2))<45)
        if neutral.mean()<.28: continue
        candidates.append((cx/small.width,cy/small.height))
    if len(candidates)!=1: return None
    x,y=candidates[0]
    return min(range(6),key=lambda i:(x-SEATS[i][0])**2+(y-SEATS[i][1])**2)


def position(img):
    import ocr
    stacks={}
    empty=[]
    for seat,rect in enumerate(STACKS):
        value,stack_text=read_amount(crop_tuple(img,rect))
        stacks[seat]=value
        if value is None:
            if re.fullmatch(r'\s*Sitting\s+Out\s*',stack_text,re.I):
                empty.append(seat)
                continue
            cx,cy=SEATS[seat]
            text=ocr._extract_text_from_image(crop_tuple(img,(cx-.09,cy-.04,.18,.09)),threshold=80,target_height=100)
            if re.fullmatch(r'\s*Empty\s+Seat\s*',text,re.I):
                empty.append(seat)
    occupied=[s for s,v in stacks.items() if v is not None]
    dealer=dealer_seat(img)
    positions={}
    # Missing stacks need an explicit Empty Seat label; never infer vacancy
    # from a failed read or animation.
    if len(occupied)+len(empty)==6 and len(occupied)>=2 and dealer in occupied:
        order=sorted(occupied,key=lambda i:(i-dealer)%6)
        labels={2:('BTN','BB'),3:('BTN','SB','BB'),4:('BTN','SB','BB','CO'),
                5:('BTN','SB','BB','UTG','CO'),6:('BTN','SB','BB','UTG','MP','CO')}
        positions=dict(zip(order,labels[len(occupied)]))
    return dict(position=positions.get(3),spot=None,seat_positions=positions,
                occupied_seats=occupied,raw_stacks=stacks,dealer_seat=dealer,status='partial')
