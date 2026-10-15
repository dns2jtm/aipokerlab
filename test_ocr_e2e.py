#!/usr/bin/env python3
"""End-to-end test of the production OCR path: capture_and_read() /
capture_and_read_with_position().

Synthetic GGPoker-style window is mocked (no real GGPoker window needed),
so this exercises the whole pipeline: find window -> screenshot -> crop
-> offset-grid fallback -> white-fraction gate -> left/right split ->
glyph template matching -> suited/offsuit."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont
import ocr

FONT = "/System/Library/Fonts/Helvetica.ttc"
BORDER = (11, 61, 11)
CARD_BG = (248, 242, 230)
FULL_W, FULL_H = 3034, 2148


def card(glyph, suit_color):
    W, H = 201, 274
    img = Image.new("RGB", (W, H), CARD_BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=BORDER, width=11)
    f = ImageFont.truetype(FONT, 30)
    ink = suit_color if suit_color[0] > 120 else (20, 20, 20)
    d.text((22, 10), glyph, font=f, fill=ink)
    suit_glyph = "♥" if suit_color[0] > 120 else "♠"
    d.text((34, 160), suit_glyph, font=f, fill=suit_color)
    return img


def two_cards(c1, c2):
    gap = int(406 * ocr.CARD_GAP)
    region = Image.new("RGB", (406, 274), (0, 0, 0))
    region.paste(c1, (0, 0))
    region.paste(c2, (c1.width + gap, 0))
    return region


def make_window(c1, c2):
    full = Image.new("RGB", (FULL_W, FULL_H), (20, 120, 20))
    full.paste(two_cards(c1, c2), (int(FULL_W * 0.433), int(FULL_H * 0.72)))
    return full


def run_e2e_checks(verbose=False):
    saved_find = ocr.find_ggpoker_window
    saved_find_poker = ocr.find_poker_window
    saved_cap = ocr.capture_window
    saved_window = None
    results = []

    def mock_find_ggpoker_window(*a, **k):
        return (0, 0, FULL_W, FULL_H)

    def mock_capture_window(rect, debug=False, window_id=None):
        return saved_window

    ocr.find_ggpoker_window = mock_find_ggpoker_window
    ocr.find_poker_window = mock_find_ggpoker_window
    ocr.capture_window = mock_capture_window
    try:
        for (g1, g2, suit1, suit2, expect), i in [
            (("K", "9", (11, 61, 11), (200, 20, 20), "K9o"), 0),
            (("A", "K", (11, 61, 11), (11, 61, 11), "AKs"), 1),
            (("Q", "J", (200, 20, 20), (200, 20, 20), "QJs"), 2),
            (("T", "8", (11, 61, 11), (200, 20, 20), "T8o"), 3),
        ]:
            saved_window = make_window(card(g1, suit1), card(g2, suit2))
            hand = ocr.capture_and_read(max_retries=0, debug=False)
            pos = ocr.capture_and_read_with_position(max_retries=0, debug=False)
            ok = hand == expect and pos["hand"] == expect
            results.append(ok)
            if verbose:
                status = "OK " if ok else "FAIL"
                print(
                    f"{status} e2e hand   expect={expect} got={hand}  "
                    f"(pos={pos.get('position')}, spot={pos.get('spot')})"
                )

        # --- No-hand case: window with green felt and no cards must return None ---
        saved_window = Image.new("RGB", (FULL_W, FULL_H), (20, 120, 20))
        hand = ocr.capture_and_read(max_retries=0, debug=False)
        ok = hand is None
        results.append(ok)
        if verbose:
            status = "OK " if ok else "FAIL"
            print(f"{status} e2e empty  expect=None got={hand}")
    finally:
        ocr.find_ggpoker_window = saved_find
        ocr.find_poker_window = saved_find_poker
        ocr.capture_window = saved_cap

    return results


def test_ocr_e2e():
    results = run_e2e_checks(verbose=False)
    assert all(results), f"OCR e2e checks failed: {results}"


if __name__ == "__main__":
    results = run_e2e_checks(verbose=True)
    print(
        "\nProduction OCR path e2e:",
        "ALL PASS" if all(results) else "SOME FAILED",
        f"({sum(results)}/{len(results)})",
    )
    raise SystemExit(0 if all(results) else 1)
