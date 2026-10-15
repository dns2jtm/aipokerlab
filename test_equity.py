"""
Unit tests for the Monte Carlo Equity Calculator.

Tests cover:
- Card parsing
- Hand evaluation
- Range parsing
- Equity calculation
"""

import unittest
from equity import (
    parse_card,
    parse_hand,
    parse_range,
    evaluate_hand,
    calculate_equity,
    get_equity_percentage,
    RANKS,
    SUITS
)


class TestCardParsing(unittest.TestCase):
    """Tests for card parsing functions."""
    
    def test_parse_card_valid(self):
        """Test parsing valid cards."""
        # SUITS = "cdhs" -> c=0, d=1, h=2, s=3
        self.assertEqual(parse_card("Ah"), 12 * 4 + 2)  # Ace of hearts
        self.assertEqual(parse_card("2c"), 0 * 4 + 0)   # 2 of clubs
        self.assertEqual(parse_card("Tc"), 8 * 4 + 0)   # 10 of clubs
        self.assertEqual(parse_card("Kd"), 11 * 4 + 1)  # King of diamonds
    
    def test_parse_card_invalid(self):
        """Test parsing invalid cards."""
        with self.assertRaises(ValueError):
            parse_card("Xh")  # Invalid rank
        with self.assertRaises(ValueError):
            parse_card("A9")  # Invalid suit
        with self.assertRaises(ValueError):
            parse_card("A")   # Too short
    
    def test_parse_hand_preflop_notation(self):
        """Test parsing preflop hand notation."""
        # Suited hands
        hand = parse_hand("AKs")
        self.assertEqual(len(hand), 2)
        
        # Offsuit hands
        hand = parse_hand("T9o")
        self.assertEqual(len(hand), 2)
        
        # Pocket pairs
        hand = parse_hand("AA")
        self.assertEqual(len(hand), 2)
    
    def test_parse_hand_full_notation(self):
        """Test parsing full card notation."""
        hand = parse_hand("AhKh")
        self.assertEqual(len(hand), 2)
        self.assertEqual(hand[0], 12 * 4 + 2)  # Ah (h=2 in "cdhs")
        self.assertEqual(hand[1], 11 * 4 + 2)  # Kh (h=2 in "cdhs")


class TestRangeParsing(unittest.TestCase):
    """Tests for range parsing functions."""
    
    def test_parse_pair(self):
        """Test parsing pocket pairs."""
        hands = parse_range("AA")
        # AA has 6 combinations (4 choose 2)
        self.assertEqual(len(hands), 6)
    
    def test_parse_suited(self):
        """Test parsing suited hands."""
        hands = parse_range("AKs")
        # AKs has 4 combinations (one for each suit)
        self.assertEqual(len(hands), 4)
    
    def test_parse_offsuit(self):
        """Test parsing offsuit hands."""
        hands = parse_range("AKo")
        # AKo has 12 combinations (4 * 3)
        self.assertEqual(len(hands), 12)
    
    def test_parse_plus_pairs(self):
        """Test parsing pair ranges with plus notation."""
        hands = parse_range("77+")
        # 77+, 88+, 99+, TT+, JJ+, QQ+, KK+, AA+ = 8 pairs * 6 combos = 48
        self.assertEqual(len(hands), 48)
    
    def test_parse_plus_suited(self):
        """Test parsing suited ranges with plus notation (expands upward: AJs, AQs, AKs)."""
        hands = parse_range("AJs+")
        # AJs+ means AJs, AQs, AKs = 3 hands * 4 suits = 12 combinations
        self.assertEqual(len(hands), 12)
        # A2s+ means A2s..AKs = 12 hands * 4 suits = 48 combinations
        all_ax_suited = parse_range("A2s+")
        self.assertEqual(len(all_ax_suited), 48)

    def test_parse_plus_offsuit(self):
        """Test parsing offsuit ranges with plus notation (expands upward: AJo, AQo, AKo)."""
        hands = parse_range("AJo+")
        # AJo+ means AJo, AQo, AKo = 3 hands * 12 combos = 36 combinations
        self.assertEqual(len(hands), 36)

    def test_parse_dash_ranges(self):
        """Test parsing dash ranges for pairs and suited hands."""
        pair_dash = parse_range("22-55")
        # 22, 33, 44, 55 = 4 pairs * 6 combos = 24
        self.assertEqual(len(pair_dash), 24)
        suited_dash = parse_range("A2s-A5s")
        # A2s, A3s, A4s, A5s = 4 hands * 4 suits = 16
        self.assertEqual(len(suited_dash), 16)
    
    def test_parse_combined_range(self):
        """Test parsing combined ranges."""
        hands = parse_range("77+, AJo+")
        # 77+ = 48 hands, AJo+ = 36 hands -> 84 total
        self.assertEqual(len(hands), 84)

    def test_parse_range_deduplicates_overlapping_notations(self):
        """Verify overlapping notations like 'A2s+, ATs+' do not produce duplicate combos."""
        hands = parse_range("A2s+, ATs+, AKs")
        self.assertEqual(len(hands), 48)
        pairs = parse_range("22+, 77+, AA")
        self.assertEqual(len(pairs), 78)


class TestHandEvaluation(unittest.TestCase):
    """Tests for hand evaluation."""

    def test_every_flush_kicker_breaks_ties(self):
        for better, worse in [
            ('AhJh9h7h3h', 'KhJh9h7h3h'),
            ('AhKh9h7h3h', 'AhQh9h7h3h'),
            ('AhKhQh7h3h', 'AhKhJh7h3h'),
            ('AhKhQhJh3h', 'AhKhQhTh3h'),
            ('AhKhQhJh9h', 'AhKhQhJh8h'),
        ]:
            with self.subTest(better=better, worse=worse):
                self.assertGreater(evaluate_hand(parse_hand(better)), evaluate_hand(parse_hand(worse)))

    def test_kickers_and_wheels_across_categories(self):
        for better, worse in [
            ('AsKdQhJc9d', 'AsKdQhJc8d'),
            ('AcAdKhQsJd', 'AcAdKhQsTd'),
            ('AcAdKhKsQd', 'AcAdKhKsJd'),
            ('AcAdAhKsQd', 'AcAdAhKsJd'),
            ('AcAdAhKsKd', 'AcAdAhQsQd'),
            ('AcAdAhAsKd', 'AcAdAhAsQd'),
            ('2c3d4h5s6c', 'Ac2d3h4s5c'),
            ('2h3h4h5h6h', 'Ah2h3h4h5h'),
        ]:
            with self.subTest(better=better, worse=worse):
                self.assertGreater(evaluate_hand(parse_hand(better)), evaluate_hand(parse_hand(worse)))

    def test_category_order_and_integer_scores(self):
        hands = ['AcKdQhJs9c', '2c2d3h4s5c', '2c2d3h3s4c',
                 '2c2d2h3s4c', 'Ac2d3h4s5c', '2h3h4h5h7h',
                 '2c2d2h3s3c', '2c2d2h2s3c', 'Ah2h3h4h5h']
        scores = [evaluate_hand(parse_hand(hand)) for hand in hands]
        self.assertTrue(all(isinstance(score, int) for score in scores))
        self.assertTrue(all(a < b for a, b in zip(scores, scores[1:])))

    def test_best_five_ignore_unused_cards_and_suits(self):
        for a, b in [('AhKhQhJh9h2c3d', 'AsKsQsJs9s4c5d'),
                     ('AcAdAhKsKdKc2d', 'AcAdAhKsKd'),
                     ('AcAdKhKsQdQs2c', 'AcAdKhKsQd')]:
            with self.subTest(a=a, b=b):
                self.assertEqual(evaluate_hand(parse_hand(a)), evaluate_hand(parse_hand(b)))
    
    def test_high_card(self):
        """Test high card hand evaluation."""
        # Ace high
        cards = [12 * 4 + 0, 11 * 4 + 1, 10 * 4 + 2, 9 * 4 + 3, 8 * 4 + 0]
        score = evaluate_hand(cards)
        self.assertGreater(score, 0)
    
    def test_pair(self):
        """Test pair hand evaluation."""
        # Pair of Aces
        cards = [12 * 4 + 0, 12 * 4 + 1, 11 * 4 + 2, 10 * 4 + 3, 9 * 4 + 0]
        score = evaluate_hand(cards)
        self.assertGreater(score, 1_000_000)  # Should be > PAIR multiplier
    
    def test_two_pair(self):
        """Test two pair hand evaluation."""
        # Two pair: Aces and Kings
        cards = [12 * 4 + 0, 12 * 4 + 1, 11 * 4 + 2, 11 * 4 + 3, 10 * 4 + 0]
        score = evaluate_hand(cards)
        self.assertGreater(score, 10_000_000)  # Should be > TWO_PAIR multiplier
    
    def test_three_of_a_kind(self):
        """Test three of a kind hand evaluation."""
        # Three Aces
        cards = [12 * 4 + 0, 12 * 4 + 1, 12 * 4 + 2, 11 * 4 + 3, 10 * 4 + 0]
        score = evaluate_hand(cards)
        self.assertGreater(score, 100_000_000)  # Should be > THREE_OF_A_KIND multiplier
    
    def test_straight(self):
        """Test straight hand evaluation."""
        # 10-J-Q-K-A straight
        cards = [8 * 4 + 0, 9 * 4 + 1, 10 * 4 + 2, 11 * 4 + 3, 12 * 4 + 0]
        score = evaluate_hand(cards)
        self.assertGreater(score, 1_000_000_000)  # Should be > STRAIGHT multiplier
    
    def test_flush(self):
        """Test flush hand evaluation."""
        # All hearts
        cards = [0 * 4 + 3, 5 * 4 + 3, 8 * 4 + 3, 10 * 4 + 3, 12 * 4 + 3]
        score = evaluate_hand(cards)
        self.assertGreater(score, 10_000_000_000)  # Should be > FLUSH multiplier
    
    def test_full_house(self):
        """Test full house hand evaluation."""
        # Three Aces, two Kings (same suits for pair)
        cards = [12 * 4 + 0, 12 * 4 + 1, 12 * 4 + 2, 11 * 4 + 0, 11 * 4 + 1]
        score = evaluate_hand(cards)
        self.assertGreater(score, 100_000_000_000)  # Should be > FULL_HOUSE multiplier

    def test_full_house_beats_flush_and_straight_on_7_card_board(self):
        """Verify Full House does not fall through to Flush or Straight on 7-card hands."""
        # 7 cards containing both a Full House (AAA KK) AND 5 clubs (flush) AND a straight
        cards = [
            parse_card("Ac"), parse_card("Ad"), parse_card("Ah"),
            parse_card("Kc"), parse_card("Kd"),
            parse_card("Qc"), parse_card("Jc"),
        ]
        score = evaluate_hand(cards)
        self.assertGreaterEqual(score, 100_000_000_000)
        self.assertLess(score, 1_000_000_000_000)

    def test_straight_flush_beats_quads_and_full_house(self):
        """Verify Straight Flush is checked before Full House / Quads."""
        cards = [
            parse_card("9h"), parse_card("Th"), parse_card("Jh"),
            parse_card("Qh"), parse_card("Kh"),
            parse_card("Kd"), parse_card("Kc"),
        ]
        score = evaluate_hand(cards)
        self.assertGreaterEqual(score, 10_000_000_000_000)
    
    def test_four_of_a_kind(self):
        """Test four of a kind hand evaluation."""
        # Four Aces
        cards = [12 * 4 + 0, 12 * 4 + 1, 12 * 4 + 2, 12 * 4 + 3, 11 * 4 + 0]
        score = evaluate_hand(cards)
        self.assertGreater(score, 1_000_000_000_000)  # Should be > FOUR_OF_A_KIND multiplier


class TestEquityCalculation(unittest.TestCase):
    """Tests for equity calculation."""

    def test_river_flush_fifth_kicker_wins_in_both_backends(self):
        from equity import _monte_carlo_equity_python, _monte_carlo_equity_numpy
        board = parse_hand('AhKhQhJh2c')
        for backend in (_monte_carlo_equity_python, _monte_carlo_equity_numpy):
            with self.subTest(backend=backend.__name__):
                self.assertEqual(backend(parse_hand('9h3d'), [parse_range('8h4d')], board, 10), 1.0)
                self.assertEqual(backend(parse_hand('8h4d'), [parse_range('9h3d')], board, 10), 0.0)
    
    def test_equity_range(self):
        """Test that equity is between 0 and 1."""
        equity = calculate_equity("AhKh", "QQ", "", 100)
        self.assertGreaterEqual(equity, 0.0)
        self.assertLessEqual(equity, 1.0)
    
    def test_equity_percentage(self):
        """Test equity percentage calculation."""
        equity_pct = get_equity_percentage("AhKh", "QQ", "", 100)
        self.assertGreaterEqual(equity_pct, 0.0)
        self.assertLessEqual(equity_pct, 100.0)
    
    def test_preflop_equity(self):
        """Test preflop equity calculation."""
        # AKs should have good equity against random
        equity = get_equity_percentage("AKs", "22+, A2s+", "", 100)
        self.assertGreater(equity, 30)  # Should be > 30%
    
    def test_postflop_equity(self):
        """Test postflop equity calculation."""
        # On a favorable flop, equity should increase
        equity = get_equity_percentage("AhKh", "QQ", "JhTh9s", 100)
        self.assertGreater(equity, 0)  # Should have some equity

    def test_tie_equity_numpy(self):
        """Verify exact tie on board gives ~50% equity, not ~50% on every non-tie hand."""
        # Board is Royal Flush in spades: AsKsQsJsTs -> both hero and villain chop 100% of the time
        eq = calculate_equity("2c3c", "4d5d", "AsKsQsJsTs", iterations=100)
        self.assertAlmostEqual(eq, 0.5, places=2)
        # Hero has nut flush vs villain lower flush on river -> hero wins 100%, never ties
        eq_win = calculate_equity("AhKh", "7h6h", "QhJh2h3c4d", iterations=100)
        self.assertAlmostEqual(eq_win, 1.0, places=2)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases."""
    
    def test_empty_range(self):
        """Test with empty range."""
        hands = parse_range("")
        self.assertEqual(len(hands), 0)
    
    def test_whitespace_handling(self):
        """Test whitespace handling in ranges."""
        hands1 = parse_range("AA")
        hands2 = parse_range("  AA  ")
        hands3 = parse_range("AA, ")
        self.assertEqual(len(hands1), len(hands2))
        self.assertEqual(len(hands1), len(hands3))
    
    def test_case_insensitivity(self):
        """Test case insensitivity."""
        # parse_card should handle both cases
        self.assertEqual(parse_card("ah"), parse_card("Ah"))

    def test_equity_lru_cache_hits_on_repeated_queries(self):
        """Verify repeated calculate_equity / get_equity_percentage calls hit the LRU cache."""
        from equity import _cached_equity, clear_equity_cache
        clear_equity_cache()
        eq1 = get_equity_percentage("AhKh", "QQ, JJ", "QdJd8s", iterations=200)
        info1 = _cached_equity.cache_info()
        eq2 = get_equity_percentage("AhKh", "QQ,  JJ", "QdJd8s", iterations=200)
        info2 = _cached_equity.cache_info()
        self.assertEqual(eq1, eq2)
        self.assertGreater(info2.hits, info1.hits)

    def test_fast_eval_and_build_showdown_matrix(self):
        """Verify evaluate_hand_fast and build_showdown_matrix O(N+M) showdown matrix."""
        from equity import evaluate_hand_fast, build_showdown_matrix, HAS_FAST_EVAL
        self.assertIsInstance(HAS_FAST_EVAL, bool)
        board = parse_hand("QdJdTd2c3s")
        # Royal flush vs King-high straight flush
        s_rf = evaluate_hand_fast(parse_hand("AdKd") + board)
        s_sf = evaluate_hand_fast(parse_hand("9d8d") + board)
        self.assertGreater(s_rf, s_sf)

        hero_combos = parse_range("AA, KK")
        opp_combos = parse_range("QQ, JJ")
        mat = build_showdown_matrix(hero_combos, opp_combos, parse_hand("2c5d8hTs3c"))
        self.assertEqual(mat["payoff_matrix"].shape, (len(mat["hero_combos"]), len(mat["opp_combos"])))
        # AA and KK always beat unimproved QQ/JJ on 2c5d8hTs3c when not colliding
        valid = mat["valid_mask"]
        self.assertTrue((mat["payoff_matrix"][valid] == 1.0).all())
        self.assertTrue((mat["equity_matrix"][valid] == 1.0).all())


if __name__ == "__main__":
    unittest.main()
