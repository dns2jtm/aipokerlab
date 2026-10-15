PokerStars classic card corner templates

These small monochrome glyphs were extracted from the local regression captures
in tests/fixtures/pokerstars_{preflop,river,kq,empty_seat}.png. They supplement
rendered font templates for this theme's ranks and all four exact suits.
The c_hole variant covers the club glyph partially overlapped by the hero
nameplate. Matching retains distance and separation checks; card color alone
never determines suitedness.

rank_T_10.png contains both digits of the printed "10" from pokerstars_t9t.png,
the user's 23:19:06 failure screenshot. The separate pokerstars_t62.png capture
is an independent regression. Rank segmentation preserves both aligned digits;
neither digit alone is treated as sufficient evidence for a ten.

pokerstars_flop_j9.png is a later independent capture, not a template source.
Tests additionally exercise half, three-quarter and 1.25x image sizes,
missing corners, hidden hero cards, an empty seat and pre-action checkboxes.
