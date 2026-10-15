"""Gray-background card test mimicking GGPoker's card theme."""
import sys
sys.path.insert(0, "/Users/danielsawa/Desktop/poker-rta")
import ocr

from PIL import Image, ImageDraw, ImageFont

def _make_gray_window(cards=("A", "K"), red=(False, False)):
    """Synthetic window with gray card backgrounds (GGPoker-like)."""
    W, H = 1200, 800
    img = Image.new("RGBA", (W, H), (30, 80, 40, 255))  # green felt
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    except OSError:
        font = ImageFont.load_default()
    left, right = ocr._card_subregions(ocr.CARD_REGION)
    for region, rank, is_red in zip((left, right), cards, red):
        x = int(region["x"] * W)
        y = int(region["y"] * H)
        w = int(region["w"] * W)
        h = int(region["h"] * H)
        # GGPoker-style gray card background instead of white
        d.rectangle([x, y, x + w, y + h], fill=(200, 200, 200, 255))
        color = (200, 30, 30) if is_red else (25, 25, 25)
        d.text((x + int(w * 0.12), y + int(h * 0.08)), rank, font=font, fill=color)
    return img


def test_gray_aks():
    img = _make_gray_window(("A", "K"), red=(False, False))
    hand = ocr.read_hole_cards(img)
    assert hand == "AKs", hand

def test_gray_pairs():
    img = _make_gray_window(("J", "J"), red=(True, True))
    hand = ocr.read_hole_cards(img)
    assert hand == "JJ", hand

def test_gray_offsuit():
    img = _make_gray_window(("A", "K"), red=(False, True))
    hand = ocr.read_hole_cards(img)
    assert hand == "AKo", hand

def test_gray_suited_red():
    img = _make_gray_window(("T", "9"), red=(True, True))
    hand = ocr.read_hole_cards(img)
    assert hand == "T9s", hand

def test_gray_rank_ordering():
    img = _make_gray_window(("T", "K"), red=(False, False))
    hand = ocr.read_hole_cards(img)
    assert hand == "KTs", hand

if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError:
                failed += 1
                print(f"FAIL {name}")
    print(f"\n{'ALL TESTS PASSED' if failed == 0 else f'{failed} FAILURES'}")
    sys.exit(1 if failed else 0)
