"""Tests for the OCR card reader using synthetic card images (no GGPoker needed)."""

import ocr


def _make_window(cards=("A", "K"), red=(False, False)):
    """Build a synthetic window screenshot with two hole cards rendered."""
    from PIL import Image, ImageDraw, ImageFont
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
        # card background
        d.rectangle([x, y, x + w, y + h], fill=(245, 245, 245, 255))
        color = (200, 30, 30) if is_red else (25, 25, 25)
        d.text((x + int(w * 0.12), y + int(h * 0.08)), rank, font=font, fill=color)
    return img


def test_read_aks():
    img = _make_window(("A", "K"), red=(False, False))
    hand = ocr.read_hole_cards(img)
    assert hand == "AKs", hand


def test_read_pairs():
    img = _make_window(("J", "J"), red=(False, False))
    hand = ocr.read_hole_cards(img)
    assert hand == "JJ", hand


def test_read_offsuit():
    # one black card, one red card -> offsuit
    img = _make_window(("A", "K"), red=(False, True))
    hand = ocr.read_hole_cards(img)
    assert hand == "AKo", hand


def test_read_suited_red():
    img = _make_window(("T", "9"), red=(True, True))
    hand = ocr.read_hole_cards(img)
    assert hand == "T9s", hand


def test_empty_table():
    from PIL import Image
    img = Image.new("RGBA", (1200, 800), (30, 34, 40, 255))
    hand = ocr.read_hole_cards(img)
    assert hand is None, hand


def test_rank_ordering():
    # K before T regardless of left/right order
    img = _make_window(("T", "K"), red=(False, False))
    hand = ocr.read_hole_cards(img)
    assert hand == "KTs", hand


if __name__ == "__main__":
    import traceback
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError:
                failed += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    print(f"\n{'ALL TESTS PASSED' if failed == 0 else f'{failed} FAILURES'}")
    raise SystemExit(1 if failed else 0)
