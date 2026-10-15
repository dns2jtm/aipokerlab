#!/usr/bin/env python3
"""End-to-end test: synthetic two-card region + production OCR pipeline.
Realistic GGPoker-style cards: black ink for black suits, red ink for red suits,
dark-green border (which the mask's green-skip excludes)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont
import ocr

FONT = "/System/Library/Fonts/Helvetica.ttc"
BORDER = (11, 61, 11)  # dark green border (excluded by mask's green-skip)
CARD_BG = (248, 242, 230)


def card(glyph, suit_color):
    """Build one 201x274 card like GGPoker: white face, green border, inked glyph.
    Corner suit is placed at y~160 (inside _split_rank_suit's sampling band y=137-246)."""
    W, H = 201, 274
    img = Image.new("RGB", (W, H), CARD_BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=BORDER, width=11)
    f = ImageFont.truetype(FONT, 30)
    ink = suit_color if suit_color[0] > 120 else (20, 20, 20)  # black ink for black suits
    d.text((22, 10), glyph, font=f, fill=ink)
    suit_glyph = "♥" if suit_color[0] > 120 else "♠"
    d.text((34, 160), suit_glyph, font=f, fill=suit_color)  # inside sampling band (y 137-246)
    return img


def two_cards(c1, c2):
    gap = int(406 * ocr.CARD_GAP)
    region = Image.new("RGB", (406, 274), (0, 0, 0))
    region.paste(c1, (0, 0))
    region.paste(c2, (c1.width + gap, 0))
    return region


def run_glyph_pipeline(verbose=False):
    results = []
    for (g1, g2, suit1, suit2, expect) in [
        ("K", "9", (11, 61, 11), (200, 20, 20), "K9o"),  # K offsuit
        ("A", "K", (11, 61, 11), (11, 61, 11), "AKs"),   # AK suited
        ("Q", "J", (200, 20, 20), (200, 20, 20), "QJs"), # QJs red suited
        ("T", "8", (11, 61, 11), (200, 20, 20), "T8o"),  # mixed
    ]:
        c1 = card(g1, suit1)
        c2 = card(g2, suit2)
        region = two_cards(c1, c2)
        full = Image.new("RGB", (3034, 2148), (20, 120, 20))
        full.paste(region, (int(3034 * 0.433), int(2148 * 0.72)))
        hand = ocr._read_region_hand(full, ocr.CARD_REGION, debug=False)
        status = "OK " if hand == expect else "FAIL"
        results.append(status == "OK ")
        if verbose:
            print(f"{status} expect={expect} got={hand}")
    if verbose:
        print("End-to-end pipeline test done:", "ALL PASS" if all(results) else "SOME FAILED")
    return results


def test_glyph_pipeline():
    results = run_glyph_pipeline(verbose=False)
    assert all(results), f"Glyph pipeline failed: {results}"


if __name__ == "__main__":
    results = run_glyph_pipeline(verbose=True)
    raise SystemExit(0 if all(results) else 1)
