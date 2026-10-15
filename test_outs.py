"""
Unit tests for the Outs Calculator.

Tests cover:
- Card parsing
- Flush draw detection
- Straight draw detection
- Combined draw detection
- Outs counting
"""

import unittest
from outs import (
    parse_card,
    parse_cards,
    get_outs,
    get_outs_simple,
    count_outs,
    describe_draw,
    RANKS,
    SUITS
)


class TestCardParsing(unittest.TestCase):
    """Tests for card parsing functions."""
    
    def test_parse_card_valid(self):
        """Test parsing valid cards (SUITS = 'cdhs' -> c=0, d=1, h=2, s=3)."""
        self.assertEqual(parse_card("Ah"), (12, 2))  # Ace of hearts
        self.assertEqual(parse_card("2c"), (0, 0))   # 2 of clubs
        self.assertEqual(parse_card("Td"), (8, 1))   # 10 of diamonds
        self.assertEqual(parse_card("Ks"), (11, 3))  # King of spades
    
    def test_parse_card_invalid(self):
        """Test parsing invalid cards."""
        with self.assertRaises(ValueError):
            parse_card("Xh")  # Invalid rank
        with self.assertRaises(ValueError):
            parse_card("A9")  # Invalid suit
        with self.assertRaises(ValueError):
            parse_card("A")   # Too short
    
    def test_parse_cards_multiple(self):
        """Test parsing multiple cards."""
        cards = parse_cards("AhKhQd")
        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[0], (12, 2))  # Ah
        self.assertEqual(cards[1], (11, 2))  # Kh
        self.assertEqual(cards[2], (10, 1))  # Qd


class TestFlushDraws(unittest.TestCase):
    """Tests for flush draw detection."""
    
    def test_flush_draw_9_outs(self):
        """Test flush draw detection (9 outs)."""
        # 4 diamonds on board + hand = flush draw (no straight draw)
        outs, desc = get_outs_simple("AdKd", "Qd7d2s")
        self.assertEqual(outs, 9)
        self.assertIn("flush", desc.lower())
    
    def test_no_flush_draw(self):
        """Test no flush draw when suits are mixed."""
        outs, desc = get_outs_simple("AhKc", "QdJs8h")
        # May detect straight draws, so just check it's not a flush
        self.assertNotIn("flush", desc.lower())
    
    def test_made_flush(self):
        """Test when flush is already made."""
        # 5 hearts = made flush (no straight draw)
        outs, desc = get_outs_simple("AhKh", "Qh7h2h")
        # Should not count as a draw since flush is made
        self.assertLessEqual(outs, 0)


class TestStraightDraws(unittest.TestCase):
    """Tests for straight draw detection."""
    
    def test_open_ended_straight_draw(self):
        """Test open-ended straight draw (8 outs)."""
        # T9 on J85 board = open-ended (needs Q or 7)
        outs, desc = get_outs_simple("Ts9c", "Jh8d5c")
        self.assertEqual(outs, 8)
        self.assertIn("open", desc.lower())
    
    def test_double_gutshot_straight_draw(self):
        """Test double gutshot (double belly-buster) straight draw (8 outs)."""
        # T8 on Q96 board -> 6-x-8-9-T-x-Q (needs 7 or J -> 8 outs)
        outs, desc = get_outs_simple("Ts8c", "Qh9d6c")
        self.assertEqual(outs, 8)
        self.assertIn("double-gutshot", desc.lower())
    
    def test_gutshot_straight_draw(self):
        """Test gutshot straight draw (4 outs)."""
        # T7 on J92 board = gutshot (needs 8)
        outs, desc = get_outs_simple("Ts7c", "Jh9d2c")
        self.assertEqual(outs, 4)
        self.assertIn("gutshot", desc.lower())
    
    def test_no_straight_draw(self):
        """Test no straight draw with disconnected cards."""
        outs, desc = get_outs_simple("Ah2h", "KdQc8s")
        self.assertEqual(outs, 0)

    def test_no_false_positive_3_card_gutshot_spans(self):
        """Verify 3-card spans in a 5-card window (e.g., 2-3-6 or 2-4-6) do not trigger false gutshots."""
        self.assertEqual(count_outs("2c3d", "6hKsQd"), 0)
        self.assertEqual(count_outs("2c4d", "6hKsQd"), 0)
        self.assertEqual(count_outs("2c3d", "5hKsQd"), 0)

    def test_single_ended_wheel_and_broadway_gutshots(self):
        """Verify A-2-3-4 and A-K-Q-J are detected as 4-out gutshot straight draws."""
        outs_wheel, desc_wheel = get_outs_simple("Ac2d", "3h4s9c")
        self.assertEqual(outs_wheel, 4)
        self.assertIn("gutshot", desc_wheel.lower())
        outs_bway, desc_bway = get_outs_simple("AcKd", "QhJs2c")
        self.assertEqual(outs_bway, 4)
        self.assertIn("gutshot", desc_bway.lower())


class TestCombinedDraws(unittest.TestCase):
    """Tests for combined draw detection."""
    
    def test_straight_flush_draw(self):
        """Test combined straight and flush draw."""
        # Td9d on Jd8d2c = both OESD and 4-diamond flush draw
        outs, desc = get_outs_simple("Td9d", "Jd8d2c")
        # Should have outs for both (with overlap adjustment)
        self.assertGreater(outs, 8)  # More than just one draw
        self.assertIn("flush", desc.lower())
    
    def test_gutshot_flush_draw(self):
        """Test gutshot + flush draw combination."""
        outs, desc = get_outs_simple("Td7d", "Jd9d2c")
        self.assertGreater(outs, 4)  # At least gutshot + flush outs
        self.assertEqual(outs, 12)  # 9 flush outs + 4 gutshot outs - 1 overlap (8d) = 12

    def test_oesd_plus_flush_draw_exact_15_outs(self):
        """Verify OESD + flush draw subtracts 2 overlapping straight-flush outs (9 + 8 - 2 = 15)."""
        res = get_outs("Td9d", "Jd8d2c")
        self.assertEqual(res['outs'], 15)
        self.assertEqual(res['draw_type'], 'open_straight_flush')


class TestOutsCounting(unittest.TestCase):
    """Tests for outs counting functions."""
    
    def test_count_outs_function(self):
        """Test the count_outs helper function."""
        # Use a board with 4 diamonds total but no straight draw
        outs = count_outs("AdKd", "2d5d9s")
        self.assertGreaterEqual(outs, 4)  # At least some outs
    
    def test_describe_draw_function(self):
        """Test the describe_draw helper function."""
        desc = describe_draw("AdKd", "2d5d9s")
        self.assertIn("draw", desc.lower())  # Should mention some type of draw
    
    def test_get_outs_full(self):
        """Test the full get_outs function returns dict including overcard and improvement outs."""
        result = get_outs("AhKh", "QhJd8d")
        self.assertIn('outs', result)
        self.assertIn('description', result)
        self.assertIn('flush_draw', result)
        self.assertIn('straight_draw', result)
        self.assertIn('overcard_outs', result)
        self.assertIn('improvement_outs', result)
        self.assertIn('draw_type', result)
    
    def test_overcard_and_improvement_outs(self):
        """Test overcard outs and pair improvement outs."""
        # Two overcards (AhKc on 9d6s2c) -> 6 overcard outs
        res_over = get_outs("AhKc", "9d6s2c")
        self.assertEqual(res_over['overcard_outs'], 6)
        # One pair (AhKc on Ad8s2c) -> 5 improvement outs (2 aces + 3 kings)
        res_pair = get_outs("AhKc", "Ad8s2c")
        self.assertEqual(res_pair['improvement_outs'], 5)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases."""
    
    def test_empty_board(self):
        """Test with empty board (preflop)."""
        outs, desc = get_outs_simple("AhKh", "")
        self.assertEqual(outs, 0)
    
    def test_single_card_board(self):
        """Test with single card on board."""
        outs, desc = get_outs_simple("AhKh", "Qd")
        self.assertEqual(outs, 0)
    
    def test_full_board(self):
        """Test with 4-card turn board."""
        outs, desc = get_outs_simple("AhKh", "QdJd8d5d")
        # Should still detect flush draw on 4-card turn board
        self.assertGreater(outs, 0)

    def test_river_5_card_board_returns_zero_outs(self):
        """Verify a 5-card river board returns 0 outs because no more cards are dealt."""
        res = get_outs("AdKd", "QdJd2s5c9h")
        self.assertEqual(res['outs'], 0)
        self.assertEqual(res['draw_type'], 'none')
        self.assertEqual(res['outs_pct'], 0.0)
        self.assertEqual(res['rule_of_4_2'], 0.0)
        self.assertEqual(res['breakdown'], {})
    
    def test_no_significant_draws(self):
        """Test when there are no significant draws."""
        outs, desc = get_outs_simple("23o", "KQJ")
        self.assertEqual(outs, 0)
        self.assertIn("no significant", desc.lower())


class TestDrawClassification(unittest.TestCase):
    """Tests for draw type classification."""
    
    def test_classify_flush(self):
        """Test flush draw classification."""
        result = get_outs("AdKd", "Qd7d2s")
        self.assertEqual(result['draw_type'], 'flush')
    
    def test_classify_open_straight(self):
        """Test open-ended straight classification."""
        result = get_outs("Ts9c", "Jh8d5c")
        self.assertEqual(result['draw_type'], 'open_straight')
    
    def test_classify_gutshot(self):
        """Test gutshot classification."""
        result = get_outs("Ts7c", "Jh9d2c")
        self.assertEqual(result['draw_type'], 'gutshot')
    
    def test_classify_combined(self):
        """Test combined draw classification."""
        result = get_outs("Td9d", "Jd8d2c")
        self.assertIn('flush', result['draw_type'])

    def test_outs_breakdown_and_clean_outs_board_flush_discount(self):
        """Verify breakdown, outs_pct, rule_of_4_2, and board-only 4-flush discounting."""
        # Hero has flush draw (Ad Kd on Qd 7d 2s): 9 clean flush outs + 6 overcard outs = 15 outs
        res = get_outs("AdKd", "Qd7d2s")
        self.assertEqual(res['breakdown']['flush'], 9)
        self.assertEqual(res['clean_outs'], res['outs'])
        self.assertAlmostEqual(res['outs_pct'], round((res['outs'] / 47) * 100, 1))
        self.assertEqual(res['rule_of_4_2'], float(res['outs'] * 4))

        # Turn board has 4 diamonds (Qd Jd 7d 2d) and hero has NO diamonds (As Kh):
        # 9 diamond outs would only play the board flush, so clean_outs discounts them!
        turn_board_flush = get_outs("AsKh", "QdJd7d2d")
        self.assertEqual(turn_board_flush['breakdown']['flush'], 9)
        self.assertLess(turn_board_flush['clean_outs'], turn_board_flush['outs'])
        self.assertEqual(turn_board_flush['clean_outs'], turn_board_flush['outs'] - 9)


if __name__ == "__main__":
    unittest.main()

