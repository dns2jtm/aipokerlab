"""Tests for the RTA range engine (no GUI required)."""

import ranges


def test_all_hands_count():
    hands = ranges.all_hands()
    assert len(hands) == 169
    assert "AA" in hands and "AKs" in hands and "AKo" in hands


def test_normalize():
    assert ranges.normalize_hand("aks") == "AKs"
    assert ranges.normalize_hand("AK") == "AKs"
    assert ranges.normalize_hand("KA") == "AKo"
    assert ranges.normalize_hand("jj") == "JJ"
    assert ranges.normalize_hand("t9") == "T9s"
    assert ranges.normalize_hand("9t") == "T9o"
    assert ranges.normalize_hand("T9o") == "T9o"
    assert ranges.normalize_hand("XX") is None
    assert ranges.normalize_hand("AhKd") == "AKo"
    assert ranges.normalize_hand("Ah Kd") == "AKo"
    assert ranges.normalize_hand("AhKh") == "AKs"
    assert ranges.normalize_hand("AhAd") == "AA"
    assert ranges.normalize_hand("AhAh") is None


def test_open_ranges_sanity():
    # BTN opens wider than UTG
    assert len(ranges.OPEN_RANGES["BTN"]) > len(ranges.OPEN_RANGES["UTG"])
    # Premium hands always open
    for pos in ranges.OPEN_RANGES:
        assert "AA" in ranges.OPEN_RANGES[pos]
        assert "AKs" in ranges.OPEN_RANGES[pos]
    # Trash doesn't open UTG
    assert "72o" not in ranges.OPEN_RANGES["UTG"]


def test_open_advice():
    assert ranges.advise({"kind": "open", "pos": "UTG"}, "72o")[0] == "FOLD"
    assert ranges.advise({"kind": "open", "pos": "BTN"}, "72o")[0] == "FOLD"
    assert ranges.advise({"kind": "open", "pos": "UTG"}, "AA")[0] == "RAISE"
    assert ranges.advise({"kind": "open", "pos": "BTN"}, "72o")[0] == "FOLD"
    # BTN opens 72o? No — but 32s is in BTN range
    assert ranges.advise({"kind": "open", "pos": "BTN"}, "32s")[0] == "RAISE"


def test_facing_open():
    r = ranges.advise({"kind": "facing_open", "pos": "BB", "vs": "UTG"}, "AA")
    assert r[0] == "3-BET"
    r = ranges.advise({"kind": "facing_open", "pos": "BB", "vs": "UTG"}, "76s")
    assert r[0] == "CALL"
    r = ranges.advise({"kind": "facing_open", "pos": "BB", "vs": "UTG"}, "72o")
    assert r[0] == "FOLD"
    # SB vs BTN open: 3bet or call, not fold, with KQs
    r = ranges.advise({"kind": "facing_open", "pos": "SB", "vs": "BTN"}, "KQs")
    assert r[0] in ("3-BET", "CALL")


def test_facing_3bet():
    r = ranges.advise({"kind": "facing_3bet", "pos": "BTN"}, "AA")
    assert r[0] == "4-BET"
    r = ranges.advise({"kind": "facing_3bet", "pos": "BTN"}, "76s")
    assert r[0] == "CALL"
    r = ranges.advise({"kind": "facing_3bet", "pos": "BTN"}, "72o")
    assert r[0] == "FOLD"


def test_facing_4bet():
    assert ranges.advise({"kind": "facing_4bet"}, "AA")[0] == "5-BET/SHOVE"
    assert ranges.advise({"kind": "facing_4bet"}, "JJ")[0] == "CALL"
    assert ranges.advise({"kind": "facing_4bet"}, "72o")[0] == "FOLD"
    # Position-aware FACING_4BET lookups
    assert ranges.advise({"kind": "facing_4bet", "pos": "UTG"}, "22")[0] == "FOLD"
    assert ranges.advise({"kind": "facing_4bet", "pos": "BTN"}, "22")[0] == "CALL"
    assert ranges.facing_4bet_advice("UTG", "AKo")[0] == "CALL"
    assert ranges.facing_4bet_advice("BTN", "A5s")[0] == "5-BET/SHOVE"


def test_action_sets():
    s = ranges.get_action_sets({"kind": "open", "pos": "UTG"})
    assert "RAISE" in s and "AA" in s["RAISE"]
    s = ranges.get_action_sets({"kind": "facing_open", "pos": "BB", "vs": "BTN"})
    assert "3-BET" in s and "CALL" in s


def test_range_expansion():
    # 77+ expands to 77..AA
    s = ranges._clean("77+")
    assert "77" in s and "AA" in s and "KK" in s and "66" not in s
    # A5s+ expands to A5s..AKs
    s = ranges._clean("A5s+")
    assert "A5s" in s and "AKs" in s and "A4s" not in s
    # KTo+ expands to KTo..KQo
    s = ranges._clean("KTo+")
    assert "KTo" in s and "KQo" in s and "K9o" not in s
    # Dash ranges for pairs and suited/offsuit hands
    s_dash_suited = ranges._clean("A2s-A5s")
    assert s_dash_suited == {"A2s", "A3s", "A4s", "A5s"}
    s_dash_offsuit = ranges._clean("ATo-AQo")
    assert s_dash_offsuit == {"ATo", "AJo", "AQo"}
    s_dash_pairs = ranges._clean("99-66")
    assert s_dash_pairs == {"66", "77", "88", "99"}
    assert ranges._expand("A2s-A5s, 99-77") == {"A2s", "A3s", "A4s", "A5s", "77", "88", "99"}


def test_qts_and_bb_vs_sb_clean():
    # Ensure QTs is properly included in calling ranges where QTS was previously a typo
    assert "QTs" in ranges.THREEBET[("BTN", "CO")]["call"]
    assert "QTs" in ranges.THREEBET[("BB", "BTN")]["call"]
    assert "99" in ranges.THREEBET[("BB", "SB")]["3b"]


def test_mixed_frequencies_and_rng():
    freqs = ranges.get_mixed_frequencies({"kind": "open", "pos": "UTG"}, "AA")
    assert freqs == {"RAISE": 100}
    border = ranges.get_mixed_frequencies({"kind": "open", "pos": "UTG"}, "54s")
    assert sum(border.values()) == 100 and "RAISE" in border and "FOLD" in border
    act_low, roll_low, _ = ranges.roll_mixed_action({"kind": "open", "pos": "UTG"}, "54s", rng_value=10)
    act_high, roll_high, _ = ranges.roll_mixed_action({"kind": "open", "pos": "UTG"}, "54s", rng_value=95)
    assert act_low == "RAISE" and roll_low == 10
    assert act_high == "FOLD" and roll_high == 95

    # Facing open, facing 3bet, facing 4bet, and squeeze mixed frequencies
    f_open_mix = ranges.get_mixed_frequencies({"kind": "facing_open", "pos": "BTN", "vs": "CO"}, "A5s")
    assert sum(f_open_mix.values()) == 100 and "3-BET" in f_open_mix
    f_3b_mix = ranges.get_mixed_frequencies({"kind": "facing_3bet", "pos": "CO"}, "AQo")
    assert sum(f_3b_mix.values()) == 100 and "4-BET" in f_3b_mix
    f_sqz = ranges.get_mixed_frequencies({"kind": "squeeze", "pos": "BTN", "vs": "UTG"}, "AA")
    assert f_sqz == {"SQUEEZE": 100}
    assert ranges.advise({"kind": "squeeze", "pos": "BTN", "vs": "UTG"}, "AA")[0] == "SQUEEZE"
    assert ranges.advise({"kind": "squeeze", "pos": "BTN", "vs": "UTG"}, "87s")[0] == "CALL"
    assert ranges.advise({"kind": "squeeze", "pos": "BTN", "vs": "UTG"}, "72o")[0] == "FOLD"


def test_strategy_manager():
    from strategy import StrategyManager, StrategyProfile
    sm = StrategyManager()
    assert sm.is_default_state()
    spot = {"kind": "open", "pos": "UTG"}
    spot_ranges = sm.get_ranges_for_spot(spot)
    all_spot_hands = spot_ranges.get("RAISE", []) + spot_ranges.get("CALL", []) + spot_ranges.get("FOLD", [])
    assert "AA" in all_spot_hands
    assert "22+" not in all_spot_hands  # Shorthand must be expanded
    # Test stack depth lookup (20bb vs 100bb)
    sm.set_stack_depth(20)
    assert not sm.is_default_state()
    adv, adj_sets = sm.advise_with_strategy(spot, "AA")
    assert adv[0] == "RAISE"
    sm.set_profile(StrategyProfile.LAG)
    sm.set_aggression_factor(1.5)
    _, lag_sets = sm.advise_with_strategy(spot, "AA")
    assert len(lag_sets["RAISE"]) >= len(adj_sets["RAISE"])

    # Verify invalid tokens like 'KKo' are never present in expanded ranges
    bb_vs_utg_20 = sm.get_ranges_for_spot({"kind": "facing_open", "pos": "BB", "vs": "UTG"})
    for act_list in bb_vs_utg_20.values():
        assert "KKo" not in act_list
    assert sm._expand_hand_list(["KKo", "AKs"]) == ["AKs"]

    # Verify facing_3bet and facing_4bet custom/stack-specific ranges are respected
    sm2 = StrategyManager()
    sm2._merge_ranges({
        "100bb": {
            "facing_3bet": {"BTN": {"4b": ["AA"], "call": ["KK"]}},
            "facing_4bet": {"5b": ["AA"], "call": ["KK"]},
        }
    })
    sm2.config.custom_ranges = {"100bb": {}}
    adv_3b, sets_3b = sm2.advise_with_strategy({"kind": "facing_3bet", "pos": "BTN"}, "76s")
    assert adv_3b[0] == "FOLD"
    assert sets_3b["4-BET"] == {"AA"}
    assert sets_3b["CALL"] == {"KK"}

    adv_4b, sets_4b = sm2.advise_with_strategy({"kind": "facing_4bet", "pos": "BTN"}, "JJ")
    assert adv_4b[0] == "FOLD"
    assert sets_4b["5-BET"] == {"AA"}
    assert sets_4b["CALL"] == {"KK"}

    # Verify DEFAULT_RANGES['100bb'] matches canonical ranges.py sets
    sm_100 = StrategyManager()
    for pos, expected_open in ranges.OPEN_RANGES.items():
        raw_100_open = set(sm_100._ranges["100bb"]["open"][pos])
        assert raw_100_open == expected_open
    for (pos, vs_pos), expected_3b in ranges.THREEBET.items():
        entry = sm_100._ranges["100bb"]["facing_open"][f"{pos}_vs_{vs_pos}"]
        assert set(entry["3b"]) == expected_3b["3b"]
        assert set(entry["call"]) == expected_3b["call"]

    # Verify iso_raise ranges and advice
    iso_spot = {"kind": "iso_raise", "pos": "BTN", "vs": "UTG"}
    iso_act, iso_detail = ranges.advise(iso_spot, "AKs")
    assert iso_act == "RAISE"
    assert "Iso-raise" in iso_detail
    iso_sets = ranges.get_action_sets(iso_spot)
    assert "AKs" in iso_sets["RAISE"]
    sm_iso_adv, sm_iso_sets = sm_100.advise_with_strategy(iso_spot, "AKs")
    assert sm_iso_adv[0] == "RAISE"
    assert "AKs" in sm_iso_sets["RAISE"]


def test_all_positions_and_spot_combinations_resolve():
    for pos in ranges.POSITIONS_6MAX:
        for kind in ("open", "facing_open", "squeeze", "iso_raise", "facing_3bet", "facing_4bet"):
            for vs in (None, "UTG", "MP", "CO", "BTN", "SB", "BB"):
                spot = {"kind": kind, "pos": pos, "vs": vs}
                adv = ranges.advise(spot, "AA")
                assert adv is not None, f"advise returned None for {spot}"
                sets = ranges.get_action_sets(spot)
                assert sets, f"get_action_sets returned empty for {spot}"



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
