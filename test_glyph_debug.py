#!/usr/bin/env python3
"""Debug the synthetic card match."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import ocr

FONT = "/System/Library/Fonts/Helvetica.ttc"


def run_glyph_debug(verbose=False):
    W, H = 201, 274
    img = Image.new("RGB", (W, H), (248, 242, 230))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=(8, 48, 8), width=11)
    f = ImageFont.truetype(FONT, 30)
    d.text((22, 10), "K", font=f, fill=(11, 61, 11))
    d.text((34, 36), "♥", font=f, fill=(200, 20, 20))

    # Replicate read_card_rank exactly
    margin_lr = max(16, int(W * 0.09))
    margin_top = max(8, int(W * 0.05))
    rank_h = int(H * 0.5)
    rank_area = img.crop((margin_lr, margin_top, W - margin_lr, rank_h))
    ra_W, ra_H = rank_area.width, rank_area.height
    if verbose:
        print(f"W={W}, margin_lr={margin_lr}, margin_top={margin_top}, rank_h={rank_h}, rank_area={ra_W}x{ra_H}")

    a = np.asarray(rank_area.convert("RGB"))
    lums = 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]
    bg_lum = np.percentile(lums, 75)
    dark_thresh = max(60, bg_lum - 50)
    red_thresh = max(120, bg_lum + 20)
    if verbose:
        print(f"bg_lum={bg_lum:.1f}, dark_thresh={dark_thresh:.1f}, red_thresh={red_thresh:.1f}")

    mask = Image.new("L", (ra_W, ra_H), 0)
    mp = mask.load()
    for y in range(ra_H):
        for x in range(ra_W):
            r, g, b = rank_area.getpixel((x, y))
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum < dark_thresh or (r > red_thresh and g < 120 and b < 120):
                mp[x, y] = 255

    dark = sum(1 for y in range(ra_H) for x in range(ra_W) if mask.getpixel((x, y)))
    if verbose:
        print(f"dark pixels in rank area: {dark}/{ra_W * ra_H}")

    seen = [[False] * ra_W for _ in range(ra_H)]

    def flood(x, y):
        stack = [(x, y)]
        pts = []
        seen[y][x] = True
        while stack:
            x, y = stack.pop()
            pts.append((x, y))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < ra_W and 0 <= ny < ra_H and not seen[ny][nx] and mask.getpixel((nx, ny)):
                    seen[ny][nx] = True
                    stack.append((nx, ny))
        return pts

    clusters = [
        flood(x, y)
        for y in range(ra_H)
        for x in range(ra_W)
        if mask.getpixel((x, y)) and not seen[y][x]
    ]
    if verbose:
        print(
            f"clusters: {[(min(p[0] for p in c), min(p[1] for p in c), max(p[0] for p in c), max(p[1] for p in c)) for c in sorted(clusters, key=lambda pts: min(p[1] for p in pts))]}"
        )

    matched_rank = None
    for c in sorted(clusters, key=lambda pts: min(p[1] for p in pts)):
        x0 = min(p[0] for p in c)
        y0 = min(p[1] for p in c)
        x1 = max(p[0] for p in c)
        y1 = max(p[1] for p in c)
        if verbose:
            print(f"  cluster ({x0},{y0})-({x1},{y1}) w={x1 - x0} (> {W * 0.6} -> border)")
        if x1 - x0 > W * 0.6:
            if verbose:
                print("    skipped as border")
            continue
        glyph_crop = rank_area.crop((x0, y0, x1 + 1, y1 + 1))
        vals = sorted(img.convert("L").getdata())
        card_bg = vals[int(len(vals) * 0.9)]
        matched, dist = ocr._match_rank(glyph_crop, card_bg)
        matched_rank = matched
        if verbose:
            print(f"    bg={card_bg:.0f}: rank={matched}, dist={dist}")
        break
    else:
        if verbose:
            print("no non-border clusters found")

    return matched_rank


def test_glyph_debug():
    matched = run_glyph_debug(verbose=False)
    assert matched == "K"


if __name__ == "__main__":
    run_glyph_debug(verbose=True)
