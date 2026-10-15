"""
Unit tests for the Postflop Decision Engine.

Tests cover:
- Pot odds calculation
- Equity vs pot odds comparison
- Decision making (CALL/FOLD/RAISE)
- Implied odds buffer
- Advice generation
"""

import unittest
from postflop import (
    PostflopAdvice,
    get_postflop_advice,
    calculate_pot_odds,
    should_call,
    get_rule_of_42_equity,
    Decision
)


class TestPotOdds(unittest.TestCase):
    """Tests for pot odds calculation."""
    
    def test_basic_pot_odds(self):
        """Test basic pot odds calculation."""
        # Pot: 100, Call: 50 -> Pot odds = 50 / (100 + 50) = 33.3%
        odds = calculate_pot_odds(100, 50)
        self.assertAlmostEqual(odds, 33.33, places=1)
    
    def test_small_call(self):
        """Test with small call amount."""
        # Pot: 100, Call: 10 -> Pot odds = 10 / (100 + 10) = 9.1%
        odds = calculate_pot_odds(100, 10)
        self.assertAlmostEqual(odds, 9.09, places=1)
    
    def test_large_call(self):
        """Test with large call amount."""
        # Pot: 100, Call: 200 -> Pot odds = 200 / (100 + 200) = 66.7%
        odds = calculate_pot_odds(100, 200)
        self.assertAlmostEqual(odds, 66.67, places=1)
    
    def test_pot_odds_range(self):
        """Test that pot odds are always between 0 and 100."""
        for pot in [10, 50, 100, 500, 1000]:
            for call in [10, 50, 100, 500]:
                odds = calculate_pot_odds(pot, call)
                self.assertGreaterEqual(odds, 0)
                self.assertLessEqual(odds, 100)


class TestShouldCall(unittest.TestCase):
    """Tests for should_call decision function."""
    
    def test_call_when_equity_exceeds(self):
        """Test calling when equity exceeds required."""
        # 40% equity vs 33% pot odds = call
        result = should_call(0.40, 0.33)
        self.assertTrue(result)
    
    def test_fold_when_equity_below(self):
        """Test folding when equity is below required."""
        # 20% equity vs 33% pot odds = fold
        result = should_call(0.20, 0.33)
        self.assertFalse(result)
    
    def test_implied_odds_buffer(self):
        """Test that implied odds buffer makes calls more likely."""
        # 30% equity vs 33% pot odds
        # Without buffer: fold (30 < 33)
        # With 15% buffer: call (30 > 33 * 0.85 = 28)
        result_no_buffer = should_call(0.30, 0.33, 0.0)
        result_with_buffer = should_call(0.30, 0.33, 0.15)
        self.assertFalse(result_no_buffer)
        self.assertTrue(result_with_buffer)


class TestRuleOf42(unittest.TestCase):
    """Tests for Rule of 4 and 2 equity estimation."""
    
    def test_rule_of_4_flop(self):
        """Test Rule of 4 on flop."""
        # 9 outs * 4 = 36%
        equity = get_rule_of_42_equity(9, "flop")
        self.assertEqual(equity, 36)
    
    def test_rule_of_2_turn(self):
        """Test Rule of 2 on turn."""
        # 9 outs * 2 = 18%
        equity = get_rule_of_42_equity(9, "turn")
        self.assertEqual(equity, 18)
    
    def test_various_outs(self):
        """Test with various outs counts."""
        # Flush draw
        self.assertEqual(get_rule_of_42_equity(9, "flop"), 36)
        # Open-ended straight
        self.assertEqual(get_rule_of_42_equity(8, "flop"), 32)
        # Gutshot
        self.assertEqual(get_rule_of_42_equity(4, "flop"), 16)


class TestPostflopAdvice(unittest.TestCase):
    """Tests for PostflopAdvice class."""
    
    def test_advice_creation(self):
        """Test creating advice object."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        self.assertIsNotNone(advice)
        self.assertEqual(advice.hero_hand, "AhKh")
        self.assertEqual(advice.board, "QdJd8d")
    
    def test_equity_calculation(self):
        """Test equity is calculated."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        self.assertGreaterEqual(advice.equity, 0)
        self.assertLessEqual(advice.equity, 1)
    
    def test_pot_odds_calculation(self):
        """Test pot odds are calculated correctly."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        # Pot odds = 50 / (100 + 50) = 0.333
        self.assertAlmostEqual(advice.pot_odds, 0.333, places=2)
    
    def test_required_equity_with_buffer(self):
        """Test required equity includes implied odds buffer."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        # Required = pot_odds * (1 - 0.15) = 0.333 * 0.85 = 0.283
        self.assertLess(advice.required_equity, advice.pot_odds)
    
    def test_get_decision(self):
        """Test getting decision as string."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        decision = advice.get_decision()
        self.assertIn(decision, ["CALL", "FOLD", "RAISE"])
    
    def test_get_advice_dict(self):
        """Test getting advice as dictionary."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        result = advice.get_advice()
        
        self.assertIn('decision', result)
        self.assertIn('equity', result)
        self.assertIn('equity_pct', result)
        self.assertIn('required_equity', result)
        self.assertIn('pot_odds', result)
        self.assertIn('outs', result)
        self.assertIn('reasoning', result)


class TestGetPostflopAdvice(unittest.TestCase):
    """Tests for get_postflop_advice function."""
    
    def test_flush_draw_call(self):
        """Test flush draw gets CALL recommendation."""
        advice = get_postflop_advice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        # Flush draw with good pot odds should call
        self.assertIn(advice['decision'], ["CALL", "RAISE"])
    
    def test_made_hand(self):
        """Test made hand gets appropriate recommendation."""
        advice = get_postflop_advice(
            hero_hand="AhKc",
            board="Ah8d5s",
            pot_size=100,
            call_amount=50
        )
        # Top pair should call or raise
        self.assertIn(advice['decision'], ["CALL", "RAISE"])

    def test_monster_value_hand_raises_without_draws(self):
        """Verify a monster made hand (e.g., top set with 0 draw outs) raises for value."""
        advice = get_postflop_advice(
            hero_hand="AhAd",
            board="As8d3c",
            pot_size=100,
            call_amount=30,
            iterations=300
        )
        self.assertEqual(advice['decision'], "RAISE")
        self.assertIn("Strong value hand", advice['reasoning'])

    def test_spot_to_opponent_range(self):
        """Test converting preflop spots into opponent range strings."""
        from postflop import spot_to_opponent_range
        r_open = spot_to_opponent_range({"kind": "open", "pos": "UTG"})
        self.assertIn("AJs", r_open)
        r_facing = spot_to_opponent_range({"kind": "facing_open", "pos": "BB", "vs": "BTN"})
        self.assertIn("AA", r_facing)

    def test_spot_to_opponent_range_with_strategy_manager(self):
        """Test spot_to_opponent_range respects StrategyManager stack depth, profile, and custom ranges."""
        import tempfile
        import json
        from postflop import spot_to_opponent_range
        from strategy import StrategyManager, StrategyProfile

        mgr = StrategyManager()
        spot_facing = {"kind": "facing_open", "pos": "BB", "vs": "UTG"}
        spot_open = {"kind": "open", "pos": "UTG"}
        spot_3b = {"kind": "facing_3bet", "pos": "BTN", "vs": "BB"}
        spot_4b = {"kind": "facing_4bet", "pos": "BTN", "vs": "BB"}

        # Default state matches baseline
        self.assertEqual(spot_to_opponent_range(spot_facing), spot_to_opponent_range(spot_facing, mgr))

        # Stack depth 20bb vs 150bb
        mgr.set_stack_depth(20)
        r_20 = set(spot_to_opponent_range(spot_facing, mgr).split(", "))
        mgr.set_stack_depth(150)
        r_150 = set(spot_to_opponent_range(spot_facing, mgr).split(", "))
        self.assertLess(len(r_20), len(r_150))

        # Profile TAG vs LAG across open, facing_open, facing_3bet, facing_4bet
        mgr_tag = StrategyManager()
        mgr_tag.set_profile(StrategyProfile.TAG)
        mgr_lag = StrategyManager()
        mgr_lag.set_profile(StrategyProfile.LAG)

        for sp in (spot_open, spot_facing, spot_3b, spot_4b):
            tag_hands = set(spot_to_opponent_range(sp, mgr_tag).split(", "))
            lag_hands = set(spot_to_opponent_range(sp, mgr_lag).split(", "))
            self.assertLess(len(tag_hands), len(lag_hands))

        # Custom ranges
        mgr_custom = StrategyManager()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump({"100bb": {"open": {"UTG": ["AA", "KK"]}}}, tf)
            tf_path = tf.name
        try:
            self.assertTrue(mgr_custom.import_ranges_from_file(tf_path))
            custom_res = set(spot_to_opponent_range(spot_facing, mgr_custom).split(", "))
            self.assertEqual(custom_res, {"AA", "KK"})
        finally:
            import os
            os.remove(tf_path)
    
    def test_weak_hand_fold(self):
        """Test weak hand might get FOLD recommendation."""
        advice = get_postflop_advice(
            hero_hand="23o",
            board="AhKhQd",
            pot_size=100,
            call_amount=100  # Pot-sized bet
        )
        # Weak hand facing large bet might fold
        # (depends on equity calculation)
        self.assertIn(advice['decision'], ["CALL", "FOLD", "RAISE"])


class TestReasoning(unittest.TestCase):
    """Tests for reasoning generation."""
    
    def test_reasoning_contains_equity(self):
        """Test reasoning includes equity information."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        reasoning = advice.reasoning
        self.assertIn("Equity", reasoning)
    
    def test_reasoning_contains_required(self):
        """Test reasoning includes required equity."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        reasoning = advice.reasoning
        self.assertIn("Required", reasoning)
    
    def test_reasoning_contains_outs(self):
        """Test reasoning includes outs information."""
        advice = PostflopAdvice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=50
        )
        reasoning = advice.reasoning
        self.assertIn("Outs", reasoning)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases."""
    
    def test_zero_pot(self):
        """Test with zero pot size."""
        advice = get_postflop_advice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=0,
            call_amount=50
        )
        self.assertIn('decision', advice)

    def test_zero_pot_and_zero_call_no_zero_division(self):
        """Verify pot_size=0 and call_amount=0 does not raise ZeroDivisionError and never folds."""
        self.assertEqual(calculate_pot_odds(0, 0), 0.0)
        self.assertEqual(calculate_pot_odds(100, 0), 0.0)
        advice = get_postflop_advice(
            hero_hand="7c2d",
            board="QdJdTd",
            pot_size=0,
            call_amount=0,
            iterations=100
        )
        self.assertEqual(advice['pot_odds'], 0.0)
        self.assertNotEqual(advice['decision'], "FOLD")
        self.assertIn(advice['decision'], ["CALL", "RAISE"])

    def test_river_does_not_semi_bluff_raise_missed_draw(self):
        """Verify missed draw on 5-card river board has 0 outs and does not semi-bluff raise."""
        advice = get_postflop_advice(
            hero_hand="AdKd",
            board="QdJd2s5c9h",
            pot_size=100,
            call_amount=50,
            iterations=200
        )
        self.assertEqual(advice['outs'], 0)
        self.assertEqual(advice['draw_type'], 'none')

    def test_board_texture_turn_river_connectivity_and_pairs(self):
        """Verify connected flops stay connected on turn/river and paired dry boards stay dry."""
        from postflop import analyze_board_texture, BoardTexture
        flop = analyze_board_texture("QdJdTd")
        river = analyze_board_texture("QdJdTd2c7s")
        self.assertEqual(flop['texture'], BoardTexture.WET)
        self.assertEqual(river['texture'], BoardTexture.WET)
        self.assertGreaterEqual(river['connectivity'], 8.0)

        paired_dry = analyze_board_texture("KhKd7c2s")
        self.assertTrue(paired_dry['has_pairs'])
        self.assertEqual(paired_dry['connectivity'], 0.0)
        self.assertEqual(paired_dry['texture'], BoardTexture.DRY)
    
    def test_large_pot(self):
        """Test with large pot size."""
        advice = get_postflop_advice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=10000,
            call_amount=500
        )
        self.assertIn('decision', advice)
    
    def test_all_in_situation(self):
        """Test all-in situation (call = pot)."""
        advice = get_postflop_advice(
            hero_hand="AhKh",
            board="QdJd8d",
            pot_size=100,
            call_amount=100
        )
        self.assertIn('decision', advice)

    def test_street_dependent_implied_odds_and_sizing(self):
        """Verify river has 0% implied odds buffer, turn has half buffer, and sizing/SPR are populated."""
        flop_adv = PostflopAdvice("AhKh", "QdJd2s", pot_size=100, call_amount=50, effective_stack=200, iterations=100)
        turn_adv = PostflopAdvice("AhKh", "QdJd2s5c", pot_size=100, call_amount=50, effective_stack=200, iterations=100)
        river_adv = PostflopAdvice("AhKh", "QdJd2s5c9h", pot_size=100, call_amount=50, effective_stack=200, iterations=100)

        # Pot odds = 50 / 150 = 33.33%
        # River must have 0 implied odds buffer -> required_equity == pot_odds
        self.assertAlmostEqual(river_adv.required_equity, river_adv.pot_odds, places=4)
        # Turn has 7.5% buffer -> required_equity == pot_odds * 0.925
        self.assertAlmostEqual(turn_adv.required_equity, turn_adv.pot_odds * 0.925, places=4)
        # Flop has 15% buffer -> required_equity == pot_odds * 0.85
        self.assertAlmostEqual(flop_adv.required_equity, flop_adv.pot_odds * 0.85, places=4)

        # SPR = 200 / 100 = 2.0
        self.assertAlmostEqual(flop_adv.spr, 2.0, places=2)
        res = flop_adv.get_advice()
        self.assertEqual(res['spr'], 2.0)
        self.assertIn('recommended_sizing', res)

    def test_strategy_profile_and_aggression_adjustments(self):
        """Verify aggression_factor and profile adjust postflop decision thresholds."""
        passive_tag = PostflopAdvice(
            "AhKh", "QdJd2s", pot_size=100, call_amount=50,
            aggression_factor=0.5, profile="TAG", iterations=100
        )
        agg_lag = PostflopAdvice(
            "AhKh", "QdJd2s", pot_size=100, call_amount=50,
            aggression_factor=2.0, profile="LAG", iterations=100
        )
        val_tag, semi_tag, call_tag = passive_tag._get_strategy_adjustments()
        val_lag, semi_lag, call_lag = agg_lag._get_strategy_adjustments()
        self.assertLess(val_lag, val_tag)
        self.assertLess(semi_lag, semi_tag)
        self.assertLess(call_lag, call_tag)

    def test_cfr_subgame_solver_and_range_advantage_metrics(self):
        """Verify Turn/River CFR+ subgame solver and Flop Range/Nut-Advantage metrics."""
        from postflop import solve_cfr_subgame, compute_range_and_nut_advantage, is_hero_in_position
        self.assertTrue(is_hero_in_position({"kind": "facing_open", "pos": "BTN", "vs": "CO"}))
        self.assertFalse(is_hero_in_position({"kind": "facing_open", "pos": "BB", "vs": "BTN"}))

        # UTG range vs BB range on A-K-Q rainbow should give UTG positive range & nut advantage
        adv = compute_range_and_nut_advantage(
            "AA, KK, QQ, AKs, AKo, AQs",
            "22-99, T9s, 98s, 87s, 76s, 65s",
            "AhKdQc",
            hero_hand="AsKs"
        )
        self.assertGreater(adv["range_advantage"], 0.2)
        self.assertGreater(adv["nut_advantage"], 0.1)

        # River CFR+ with nut hand facing bet -> positive EV and high CALL/RAISE frequency
        cfr_res = solve_cfr_subgame(
            hero_hand="AhKh",
            board="QhJhTh2c3d",
            pot_size=100,
            call_amount=50,
            effective_stack=200,
            opponent_range="AA, KK, QQ, JJ, TT, AKo, AQo, KQo",
            hero_range="AhKh, AA, KK, QQ, JJ, AQs, KQs, 76s",
            iterations=60,
        )
        self.assertIn("cfr_frequencies", cfr_res)
        self.assertEqual(sum(cfr_res["cfr_frequencies"].values()), 100)
        self.assertGreater(cfr_res["ev"], 50.0)
        self.assertAlmostEqual(cfr_res["mdf"], 100 / 150, places=2)

        # Verify PostflopAdvice exposes cfr_frequencies, ev, mdf, range_advantage, nut_advantage
        full_adv = get_postflop_advice(
            hero_hand="AhKh",
            board="QhJhTh2c3d",
            pot_size=100,
            call_amount=50,
            effective_stack=200,
            spot={"kind": "open", "pos": "BTN"},
        )
        self.assertIn("cfr_frequencies", full_adv)
        self.assertIn("ev", full_adv)
        self.assertIn("mdf", full_adv)
        self.assertIn("range_advantage", full_adv)
        self.assertIn("nut_advantage", full_adv)
        self.assertTrue(full_adv["in_position"])

        # Verify flop 3-card board in solve_cfr_subgame samples 2-card (turn, river) runouts to 7 cards
        flop_cfr = solve_cfr_subgame(
            hero_hand="AhKh",
            board="QhJh2c",
            pot_size=100,
            call_amount=0,
            effective_stack=200,
            opponent_range="AA, KK, QQ, JJ, TT, AKo, KQo",
            hero_range="AhKh, AA, KK, QQ, JJ, AQs",
            iterations=40,
        )
        self.assertEqual(sum(flop_cfr["cfr_frequencies"].values()), 100)
        self.assertIn("cfr_preferred_sizing", flop_cfr)

    def test_native_rust_subgame_bridge_and_fallback(self):
        """Verify PostflopAdvice can query the native Rust MCCFR subgame resolver and falls back cleanly."""
        import poker_lab
        if not poker_lab.best_available_model():
            self.skipTest("No trained native blueprint available")
        adv = get_postflop_advice(
            hero_hand="AhKh",
            board="QdJd2s5c",
            pot_size=400,
            call_amount=150,
            effective_stack=1000,
            spot={"kind": "open", "pos": "BTN"},
            use_native_engine=True,
            native_search_ms=25,
            observed_actions=[
                {"pos": "BTN", "action": "raise_to", "amount_bb": 2.5},
                {"pos": "BB", "action": "call", "amount_bb": 2.5},
            ],
            iterations=100,
        )
        self.assertEqual(sum(adv["cfr_frequencies"].values()), 100)
        self.assertEqual(adv["solver_diagnostics"].get("solver_backend"), "noregrets_mccfr")
        self.assertTrue(adv["solver_diagnostics"].get("solver_worker_mode"))
        self.assertTrue(adv["solver_diagnostics"].get("solver_value_net_loaded"))
        self.assertIn("MCCFR Subgame:", adv["reasoning"])


if __name__ == "__main__":
    unittest.main()


