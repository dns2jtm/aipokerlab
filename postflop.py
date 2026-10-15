"""
Postflop Decision Engine for Poker RTA.

Provides postflop decision advice by:
- Calculating pot odds
- Comparing equity vs pot odds
- Suggesting CALL/FOLD based on expected value
- Including implied odds buffer (15%)
- Displaying outs information
- Board texture analysis (dry vs wet boards)
- Implied odds calculations

Based on DeeperMind's postflop decision-making logic.
"""

from typing import Dict, Any, Optional, Tuple, List
from enum import Enum

# Optional numpy import with graceful fallback
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Import our equity and outs calculators
try:
    from equity import (
        calculate_equity,
        get_equity_percentage,
        parse_hand,
        parse_range,
        evaluate_hand,
        evaluate_hand_fast,
        build_showdown_matrix,
    )
    from outs import get_outs, get_outs_simple
except ImportError:
    # Fallback if modules not in path
    calculate_equity = None
    get_equity_percentage = None
    parse_hand = None
    parse_range = None
    evaluate_hand = None
    evaluate_hand_fast = None
    build_showdown_matrix = None
    get_outs = None
    get_outs_simple = None


class BoardTexture(Enum):
    """Classification of board texture."""
    DRY = "dry"           # Low connectivity, few draws
    MODERATE = "moderate" # Some connectivity
    WET = "wet"           # High connectivity, many draws


def analyze_board_texture(board: str) -> Dict[str, Any]:
    """
    Analyze board texture to determine if it's dry or wet.
    
    Board texture is determined by:
    - Connectivity: How connected are the cards (straights possible?)
    - Pairs: Are there paired cards on board?
    - Flush draws: Are there 3+ cards of same suit?
    - Gaps: Large gaps between ranks indicate dry boards
    
    Args:
        board: Board cards string (e.g., 'QdJd8s')
        
    Returns:
        Dictionary with texture analysis:
        - texture: BoardTexture enum (DRY, MODERATE, WET)
        - connectivity: Score 0-10 (higher = more connected)
        - has_pairs: Boolean
        - flush_draws: Number of flush draw suits
        - straight_draws: Number of straight draw possibilities
        - description: Human-readable description
    """
    if not board:
        return {
            'texture': BoardTexture.DRY,
            'connectivity': 0,
            'has_pairs': False,
            'flush_draws': 0,
            'straight_draws': 0,
            'description': 'No board'
        }
    
    # Parse board cards
    ranks = []
    suits = []
    rank_order = '23456789TJQKA'
    
    i = 0
    while i < len(board):
        rank_char = board[i]
        if i + 1 < len(board) and board[i + 1] in 'shdc':
            suits.append(board[i + 1])
            i += 2
        else:
            suits.append('?')  # Unknown suit
            i += 1
        
        if rank_char in rank_order:
            ranks.append(rank_order.index(rank_char))
    
    if not ranks:
        return {
            'texture': BoardTexture.DRY,
            'connectivity': 0,
            'has_pairs': False,
            'flush_draws': 0,
            'straight_draws': 0,
            'description': 'Invalid board'
        }
    
    # Check for pairs
    has_pairs = len(ranks) != len(set(ranks))
    
    # Calculate connectivity on unique ranks so pairs don't inflate straight connectivity
    # and normalize against a 3-card flop baseline (3.0) so connected flops remain connected on turn/river
    ranks_sorted = sorted(set(ranks))
    connectivity = 0.0
    
    for i in range(len(ranks_sorted)):
        for j in range(i + 1, len(ranks_sorted)):
            gap = ranks_sorted[j] - ranks_sorted[i]
            if 1 <= gap <= 2:
                connectivity += 1.0
            elif gap == 3:
                connectivity += 0.5  # Partial connectivity (gutshot)
    
    connectivity_score = min(10.0, (connectivity / 3.0) * 10.0) if len(ranks_sorted) > 1 else 0.0
    
    # Count flush draws (3+ cards of same suit)
    suit_counts = {}
    for suit in suits:
        if suit != '?':
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
    flush_draws = sum(1 for count in suit_counts.values() if count >= 3)
    
    # Estimate straight draws based on connectivity
    straight_draws = 0
    if connectivity_score >= 6:
        straight_draws = 2  # Multiple straight possibilities
    elif connectivity_score >= 3:
        straight_draws = 1  # Some straight possibilities
    
    # Determine texture classification
    texture_score = connectivity_score + (flush_draws * 2) + (straight_draws * 1.5)
    
    if texture_score >= 6:
        texture = BoardTexture.WET
        description = "Wet board - high connectivity, many draws possible"
    elif texture_score >= 3:
        texture = BoardTexture.MODERATE
        description = "Moderate board - some connectivity and draws"
    else:
        texture = BoardTexture.DRY
        description = "Dry board - low connectivity, few draws"
    
    return {
        'texture': texture,
        'connectivity': round(connectivity_score, 1),
        'has_pairs': has_pairs,
        'flush_draws': flush_draws,
        'straight_draws': straight_draws,
        'description': description
    }


def calculate_implied_odds(
    pot_size: float,
    call_amount: float,
    effective_stack: float,
    equity_when_behind: float = 0.15,
    equity_when_ahead: float = 0.85
) -> Dict[str, float]:
    """
    Calculate implied odds for a calling decision.
    
    Implied odds account for potential future winnings if you hit your draw.
    
    Args:
        pot_size: Current pot size
        call_amount: Amount to call
        effective_stack: Effective stack size after the call
        equity_when_behind: Equity if draw misses (default 15%)
        equity_when_ahead: Equity if draw hits (default 85%)
        
    Returns:
        Dictionary with implied odds analysis:
        - implied_odds: Ratio of potential winnings to call amount
        - breakeven_equity: Equity needed considering implied odds
        - recommended_action: Suggested action based on implied odds
        - potential_profit: Expected profit if draw hits
    """
    # Total potential pot if we hit and get paid off
    potential_pot = pot_size + call_amount + effective_stack
    
    # Implied odds ratio
    implied_odds = potential_pot / call_amount if call_amount > 0 else float('inf')
    
    # Current pot odds
    current_pot_odds = call_amount / (pot_size + call_amount) if (pot_size + call_amount) > 0 else 0
    
    # Calculate expected value with implied odds
    # EV = (equity_when_ahead * potential_pot) - (equity_when_behind * call_amount)
    # We need to find the equity threshold where EV = 0
    
    # Simplified: breakeven equity considering implied odds
    # If we hit (probability p), we win potential_pot
    # If we miss (probability 1-p), we lose call_amount
    # EV = p * potential_pot - (1-p) * call_amount = 0
    # p * potential_pot = call_amount - p * call_amount
    # p * (potential_pot + call_amount) = call_amount
    # p = call_amount / (potential_pot + call_amount)
    
    breakeven_equity = call_amount / (potential_pot + call_amount) if (potential_pot + call_amount) > 0 else 0
    
    # Potential profit if we hit
    potential_profit = potential_pot - call_amount
    
    # Recommendation
    if implied_odds > 10:
        recommended_action = "favorable"
    elif implied_odds > 5:
        recommended_action = "moderate"
    else:
        recommended_action = "tight"
    
    return {
        'implied_odds': round(implied_odds, 2),
        'breakeven_equity': round(breakeven_equity, 3),
        'breakeven_equity_pct': round(breakeven_equity * 100, 1),
        'recommended_action': recommended_action,
        'potential_profit': round(potential_profit, 1),
        'effective_stack': effective_stack
    }


class Decision(Enum):
    """Possible postflop decisions."""
    CALL = "CALL"
    FOLD = "FOLD"
    RAISE = "RAISE"


POS_POSTFLOP_ORDER = ["SB", "BB", "UTG", "MP", "CO", "BTN"]


def is_hero_in_position(spot: Optional[Dict[str, Any]] = None) -> bool:
    """Determine whether hero acts in position (IP) postflop given a preflop spot dict."""
    if not spot or not isinstance(spot, dict):
        return True
    pos = spot.get("pos")
    vs_pos = spot.get("vs")
    kind = spot.get("kind", "open")
    if not pos or pos not in POS_POSTFLOP_ORDER:
        return True
    if vs_pos and vs_pos in POS_POSTFLOP_ORDER and vs_pos != pos:
        return POS_POSTFLOP_ORDER.index(pos) > POS_POSTFLOP_ORDER.index(vs_pos)
    if kind == "open":
        # BTN is always IP; CO/MP/UTG are IP vs blinds; SB is OOP
        return pos != "SB"
    return pos in ("BTN", "CO")


def spot_to_hero_range(
    spot: Optional[Dict[str, Any]] = None,
    hero_hand: Optional[str] = None,
) -> str:
    """Construct hero's perceived postflop range string from the active preflop spot."""
    default_hero = "22+, A2s+, K6s+, Q8s+, J8s+, T8s+, 98s, 87s, 76s, 65s, 54s, A9o+, KTo+, QTo+, JTo"
    hands = set()
    try:
        import ranges
        if spot and isinstance(spot, dict):
            hands = set(ranges.get_range_for_display(spot))
            if not hands and spot.get("pos") in ranges.OPEN_RANGES:
                hands = set(ranges.OPEN_RANGES[spot["pos"]])
        if hero_hand:
            norm = ranges.normalize_hand(hero_hand)
            if norm:
                hands.add(norm)
    except Exception:
        pass
    if not hands:
        return default_hero if not hero_hand else f"{default_hero}, {hero_hand}"
    return ", ".join(sorted(hands))


def compute_range_and_nut_advantage(
    hero_range_str: str,
    opponent_range_str: str,
    board_str: str,
    hero_hand: str = "",
) -> Dict[str, float]:
    """
    Compute Range Advantage and Nut Advantage on the given board.

    - range_advantage: Hero range mean score percentile vs Villain range mean score
      (centered at 0.0: positive means Hero range has higher average equity/strength, in [-1, +1]).
    - nut_advantage: Share of top-decile (or Two-Pair+) combos held by Hero vs Villain
      (centered at 0.0: positive means Hero has a higher density of nutted combos, in [-1, +1]).
    """
    if not HAS_NUMPY or parse_hand is None or parse_range is None or build_showdown_matrix is None or not board_str:
        return {"range_advantage": 0.0, "nut_advantage": 0.0, "hero_range_equity": 0.5}

    try:
        board_cards = parse_hand(board_str)
        if len(board_cards) < 3:
            return {"range_advantage": 0.0, "nut_advantage": 0.0, "hero_range_equity": 0.5}

        h_combos = parse_range(hero_range_str)
        o_combos = parse_range(opponent_range_str)
        if hero_hand:
            hc = parse_hand(hero_hand)
            if len(hc) == 2:
                h_tuple = (hc[0], hc[1])
                if h_tuple not in h_combos and (hc[1], hc[0]) not in h_combos:
                    h_combos = list(h_combos) + [h_tuple]

        if not h_combos or not o_combos:
            return {"range_advantage": 0.0, "nut_advantage": 0.0, "hero_range_equity": 0.5}

        mat = build_showdown_matrix(h_combos, o_combos, board_cards)
        valid_mask = mat["valid_mask"]
        eq_mat = mat["equity_matrix"]
        h_scores = np.asarray(mat["hero_scores"], dtype=np.float64)
        o_scores = np.asarray(mat["opp_scores"], dtype=np.float64)

        if h_scores.size == 0 or o_scores.size == 0:
            return {"range_advantage": 0.0, "nut_advantage": 0.0, "hero_range_equity": 0.5}

        valid_count = float(np.sum(valid_mask))
        hero_range_eq = float(np.sum(eq_mat) / valid_count) if valid_count > 0 else 0.5
        range_adv = max(-1.0, min(1.0, (hero_range_eq - 0.5) * 2.0))

        all_scores = np.concatenate([h_scores, o_scores])
        nut_cutoff = float(np.percentile(all_scores, 85))
        h_nut_share = float(np.mean(h_scores >= nut_cutoff))
        o_nut_share = float(np.mean(o_scores >= nut_cutoff))
        denom = max(0.05, h_nut_share + o_nut_share)
        nut_adv = max(-1.0, min(1.0, (h_nut_share - o_nut_share) / denom))

        return {
            "range_advantage": round(range_adv, 3),
            "nut_advantage": round(nut_adv, 3),
            "hero_range_equity": round(hero_range_eq, 3),
        }
    except Exception:
        return {"range_advantage": 0.0, "nut_advantage": 0.0, "hero_range_equity": 0.5}


def solve_cfr_subgame(
    hero_hand: str,
    board: str,
    pot_size: float,
    call_amount: float,
    effective_stack: float,
    opponent_range: str,
    hero_range: Optional[str] = None,
    iterations: int = 80,
    in_position: bool = True,
) -> Dict[str, Any]:
    """Approximate a restricted heads-up game, not full Hold'em equilibrium.

    Check/call ends at showdown. Turn equity enumerates every legal river;
    flop equity uses a reproducible sample. Future betting and opponent raises
    are absent. Position therefore does not change terminal chip payoffs.
    """
    fallback = {"cfr_frequencies": {}, "ev": 0.0, "mdf": 0.0,
                "solver_status": "unavailable", "future_betting": False,
                "solver_model": "heads_up_single_round_showdown"}
    if not HAS_NUMPY or parse_hand is None or build_showdown_matrix is None:
        return dict(fallback, solver_reason="Required numerical dependencies unavailable")
    try:
        import itertools
        import random
        from showdown_solver import solve_showdown_game

        hero_cards, board_cards = parse_hand(hero_hand), parse_hand(board)
        if (len(hero_cards) != 2 or len(board_cards) not in (3, 4, 5)
                or len(set(hero_cards + board_cards)) != len(hero_cards + board_cards)):
            raise ValueError("Invalid or overlapping hero and board cards")
        board_set = set(board_cards)

        def combos(spec):
            return list(dict.fromkeys(tuple(sorted(c)) for c in parse_range(spec or "")
                                      if len(set(c)) == 2 and not board_set.intersection(c)))

        h_key = tuple(sorted(hero_cards))
        hero_combos = [h_key] + [c for c in combos(hero_range) if c != h_key]
        opp_combos = combos(opponent_range)
        # A bounded, reproducible sample avoids ordering bias from taking every
        # nth combo. The reported gap applies only to the selected ranges.
        rng = random.Random(0)
        original_sizes = [len(hero_combos), len(opp_combos)]
        if len(hero_combos) > 90:
            hero_combos = [h_key] + rng.sample(hero_combos[1:], 89)
        if len(opp_combos) > 120:
            opp_combos = rng.sample(opp_combos, 120)
        if not opp_combos:
            raise ValueError("Opponent range has no board-compatible combinations")
        hm = np.array([(1 << a) | (1 << b) for a, b in hero_combos], dtype=np.int64)[:, None]
        om = np.array([(1 << a) | (1 << b) for a, b in opp_combos], dtype=np.int64)[None, :]
        valid = ((hm & om) == 0)
        if not valid[0].any():
            raise ValueError("Opponent range conflicts with Hero's cards")
        remaining = [c for c in range(52) if c not in board_set]
        if len(board_cards) == 5:
            runouts = [()]
        elif len(board_cards) == 4:
            runouts = [(c,) for c in remaining]
        else:
            all_runouts = list(itertools.combinations(remaining, 2))
            runouts = rng.sample(all_runouts, min(96, len(all_runouts)))
        score = np.zeros(valid.shape)
        count = np.zeros(valid.shape)
        for runout in runouts:
            mask = sum(1 << c for c in runout)
            complete = board_cards + list(runout)
            hs = np.array([evaluate_hand_fast(list(c) + complete) if not (int(hm[i, 0]) & mask) else -1
                           for i, c in enumerate(hero_combos)])[:, None]
            os = np.array([evaluate_hand_fast(list(c) + complete) if not (int(om[0, j]) & mask) else -1
                           for j, c in enumerate(opp_combos)])[None, :]
            legal = valid & (hs >= 0) & (os >= 0)
            score += legal * ((hs > os) + .5 * (hs == os))
            count += legal
        valid = valid & (count > 0)
        eq = np.divide(score, count, out=np.zeros_like(score), where=count > 0)
        # Use multi-sizing (33%, 66%, 100% pot) and opponent reraise response when stack > 0
        has_future_streets = len(board_cards) < 5 and float(effective_stack) > float(call_amount)
        realization_mat = None
        if has_future_streets:
            pos_factor = 1.04 if in_position else 0.95
            # Strong hands & nut draws realize >100% of raw equity across future streets;
            # marginal middle-equity hands out of position realize less.
            realization_mat = np.clip(eq * pos_factor + 0.04 * (eq - 0.5), 0.0, 1.0)
        solved = solve_showdown_game(
            eq,
            valid,
            float(pot_size),
            float(call_amount),
            float(effective_stack),
            iterations=int(iterations),
            bet_fractions=(0.33, 0.66, 1.0),
            allow_opponent_reraise=(float(effective_stack) > float(call_amount)),
            realization_matrix=realization_mat,
        )
        probabilities = {}
        for label, probability in zip(solved["actions"], solved["strategy"][0]):
            key = "CALL" if label == "CHECK" else "RAISE" if label.startswith("BET_") else label
            probabilities[key] = probabilities.get(key, 0.) + float(probability)
        # Largest-remainder rounding preserves a 100% probability distribution.
        frequencies = {k: int(v * 100) for k, v in probabilities.items()}
        for key in sorted(probabilities, key=lambda k: probabilities[k] * 100 - frequencies[k], reverse=True)[:100-sum(frequencies.values())]:
            frequencies[key] += 1
        result = {
            "cfr_frequencies": {k: v for k, v in frequencies.items() if v},
            "ev": round(float(solved["hand_values"][0]), 2),
            "mdf": round(pot_size / (pot_size + call_amount), 3) if call_amount > 0 else 1.0,
            "solver_status": "approximate",
            "solver_model": solved["model"],
            "future_betting": False,
            "solver_gap_chips": float(solved["gap_chips"]),
            "solver_iterations": solved["iterations"],
            "solver_range_sampled": original_sizes != [len(hero_combos), len(opp_combos)],
            "solver_runouts": len(runouts),
            "solver_equity_exact": len(board_cards) >= 4,
        }
        if call_amount <= 0 and solved["branch_sizes"]:
            best = max(solved["branch_sizes"], key=lambda b: solved["strategy"][0][solved["actions"].index(b["action"])])
            amount = best["hero_investment"]
            result["cfr_preferred_sizing"] = f"{amount / pot_size:.0%} pot" if pot_size else ""
        return result
    except (ValueError, TypeError, IndexError, ArithmeticError) as exc:
        return dict(fallback, solver_reason=str(exc))


class PostflopAdvice:
    """
    Postflop decision advisor that combines equity, outs, pot odds,
    board texture analysis, and implied odds calculations.
    """
    
    # Implied odds buffer percentage (15% as specified)
    IMPLIED_ODDS_BUFFER = 0.15
    
    def __init__(
        self,
        hero_hand: str,
        board: str,
        pot_size: float,
        call_amount: float,
        opponent_range: str = "22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 92s+, 82s+, 72s+, 62s+, 52s+, 42s+, 32s+, ATo+, KTo+, QTo+, JTo",
        iterations: int = 1000,
        effective_stack: float = None,
        num_opponents: int = 1,
        aggression_factor: float = 1.0,
        profile: Optional[Any] = None,
        spot: Optional[Dict[str, Any]] = None,
        in_position: Optional[bool] = None,
        opponent_vpip: Optional[float] = None,
        use_native_engine: bool = False,
        native_search_ms: int = 40,
        big_blind: Optional[float] = None,
        observed_actions: Optional[List[Dict[str, Any]]] = None,
        postflop_history: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize the postflop advisor.
        
        Args:
            hero_hand: Hero's hole cards (e.g., 'AhKh')
            board: Board cards (e.g., 'QdJd8s')
            pot_size: Current pot size before calling
            call_amount: Amount needed to call
            opponent_range: Opponent's perceived range
            iterations: Monte Carlo iterations for equity calculation
            effective_stack: Effective stack size for implied odds (optional)
            num_opponents: Number of active opponents in the hand (default 1)
            aggression_factor: Strategy aggression multiplier (0.5 to 2.0, default 1.0)
            profile: Strategy profile name or enum (e.g. 'TAG', 'LAG', 'ABC', 'Aggressive')
            opponent_vpip: Opponent VPIP percentage (0-100) for exploitative adjustments
        """
        self.hero_hand = hero_hand
        self.board = board
        self.pot_size = pot_size
        self.call_amount = call_amount
        self.opponent_range = opponent_range
        self.iterations = iterations
        self.effective_stack = effective_stack if (effective_stack is not None and effective_stack > 0) else (pot_size * 2)  # Default to 2x pot
        self.num_opponents = max(1, int(num_opponents or 1))
        self.aggression_factor = max(0.5, min(2.0, float(aggression_factor if aggression_factor is not None else 1.0)))
        self.profile = getattr(profile, 'value', str(profile)) if profile is not None else 'ABC'
        self.opponent_vpip = float(opponent_vpip) if opponent_vpip is not None else None
        self.use_native_engine = bool(use_native_engine)
        self.native_search_ms = max(0, min(10000, int(native_search_ms if native_search_ms is not None else 40)))
        self.big_blind = float(big_blind) if (big_blind is not None and float(big_blind) > 0) else 100.0
        self.observed_actions = list(observed_actions) if observed_actions else None
        self.postflop_history = list(postflop_history) if postflop_history else None
        
        self.spot = spot
        self.in_position = in_position if in_position is not None else is_hero_in_position(spot)
        self.street = self._detect_street()
        self.spr = round(self.effective_stack / self.pot_size, 2) if self.pot_size > 0 else 0.0
        self.mdf = round(self.pot_size / (self.pot_size + self.call_amount), 3) if (self.pot_size + self.call_amount) > 0 and self.call_amount > 0 else 1.0

        # Calculate metrics
        self.equity = self._calculate_equity()
        self.pot_odds = self._calculate_pot_odds()
        self.required_equity = self._calculate_required_equity()
        self.outs_info = self._calculate_outs()
        self.board_texture = self._analyze_board_texture()
        self.implied_odds_info = self._calculate_implied_odds()

        # Range Advantage, Nut Advantage & CFR+ Subgame Solver
        self.hero_range = spot_to_hero_range(self.spot, self.hero_hand)
        adv_metrics = compute_range_and_nut_advantage(
            self.hero_range, self.opponent_range, self.board, self.hero_hand
        )
        self.range_advantage = adv_metrics.get("range_advantage", 0.0)
        self.nut_advantage = adv_metrics.get("nut_advantage", 0.0)
        self._cfr_result = self._run_cfr_or_flop_solver()
        self.cfr_frequencies = self._cfr_result.get("cfr_frequencies", {})
        self.ev = self._cfr_result.get("ev", 0.0)

        # Make decision
        self.decision = self._make_decision()
        self.recommended_sizing = self._calculate_recommended_sizing()
        self.reasoning = self._generate_reasoning()
    
    def _detect_street(self) -> str:
        """Infer postflop street from board length."""
        if not self.board:
            return "preflop"
        clean = self.board.replace(" ", "")
        # Count rank characters in board
        n_cards = sum(1 for ch in clean.upper() if ch in "23456789TJQKA")
        if n_cards >= 5:
            return "river"
        elif n_cards == 4:
            return "turn"
        return "flop"

    def _analyze_board_texture(self) -> Dict[str, Any]:
        """Analyze board texture for dry/wet classification."""
        return analyze_board_texture(self.board)
    
    def _calculate_implied_odds(self) -> Dict[str, Any]:
        """Calculate implied odds for the current situation."""
        return calculate_implied_odds(
            self.pot_size,
            self.call_amount,
            self.effective_stack
        )
    
    def _calculate_equity(self) -> float:
        """Calculate hero's equity against opponent range."""
        if get_equity_percentage is None:
            return 0.5  # Default to 50% if module not available
        
        try:
            if self.num_opponents > 1:
                equity = get_equity_percentage(
                    self.hero_hand,
                    self.opponent_range,
                    self.board,
                    self.iterations,
                    num_opponents=self.num_opponents
                )
            else:
                equity = get_equity_percentage(
                    self.hero_hand,
                    self.opponent_range,
                    self.board,
                    self.iterations
                )
            return equity / 100.0  # Convert to 0-1 range
        except Exception:
            return 0.5
    
    def _calculate_pot_odds(self) -> float:
        """
        Calculate pot odds as a decimal.
        
        Pot odds = call_amount / (pot_size + call_amount)
        """
        if self.call_amount <= 0:
            return 0.0
        total_pot = self.pot_size + self.call_amount
        if total_pot <= 0:
            return 0.0
        return self.call_amount / total_pot
    
    def _calculate_required_equity(self) -> float:
        """
        Calculate required equity to break even.
        
        Applies street-aware implied odds buffer:
        - Flop (2 cards to come): full 15% buffer
        - Turn (1 card to come): half buffer (7.5%)
        - River (0 cards to come): 0% buffer (pure pot odds)
        """
        required = self.pot_odds
        if self.street == "river":
            buffer = 0.0
        elif self.street == "turn":
            buffer = self.IMPLIED_ODDS_BUFFER * 0.5
        else:
            buffer = self.IMPLIED_ODDS_BUFFER
        return required * (1 - buffer)

    def _run_cfr_or_flop_solver(self) -> Dict[str, Any]:
        """
        Run CFR+ subgame solver across Flop, Turn, and River (heads-up), with optional
        native Rust MCCFR blueprint + online subgame resolver (engine/noregrets) and
        automatic fallback to Python CFR+ or multiway heuristic realization.
        """
        native_res = None
        if self.use_native_engine and self.num_opponents == 1 and self.street in ("flop", "turn", "river") and self.board:
            try:
                import poker_lab
                native_res = poker_lab.query_native_subgame(
                    hero_hand=self.hero_hand,
                    board=self.board,
                    pot_size=self.pot_size,
                    call_amount=self.call_amount,
                    spot=self.spot,
                    in_position=self.in_position,
                    big_blind=self.big_blind,
                    search_ms=self.native_search_ms,
                    opponent_vpip=self.opponent_vpip,
                    observed_actions=self.observed_actions,
                    postflop_history=self.postflop_history,
                )
            except Exception:
                native_res = None

        if self.num_opponents == 1 and self.street in ("flop", "turn", "river") and self.board:
            cfr_iters = 60 if self.street == "flop" else 80
            res = solve_cfr_subgame(
                hero_hand=self.hero_hand,
                board=self.board,
                pot_size=self.pot_size,
                call_amount=self.call_amount,
                effective_stack=self.effective_stack,
                opponent_range=self.opponent_range,
                hero_range=self.hero_range,
                iterations=cfr_iters,
                in_position=self.in_position,
            )
            if native_res and native_res.get("status") in ("candidate", "uncovered") and native_res.get("cfr_frequencies"):
                res = dict(res)
                res["python_cfr_frequencies"] = dict(res.get("cfr_frequencies", {}))
                res["cfr_frequencies"] = native_res["cfr_frequencies"]
                if native_res.get("cfr_preferred_sizing"):
                    res["cfr_preferred_sizing"] = native_res["cfr_preferred_sizing"]
                res["solver_backend"] = "noregrets_mccfr"
                res["solver_blueprint_covered"] = native_res.get("blueprint_covered", False)
                res["solver_value_net_loaded"] = native_res.get("value_net_loaded", False)
                res["solver_worker_mode"] = native_res.get("worker_mode", False)
                res["solver_model_name"] = native_res.get("model_name")
                res["solver_training_iterations"] = native_res.get("training_iterations", 0)
                res["solver_search_ms"] = native_res.get("search_requested_ms", self.native_search_ms)
                return res
            if res.get("solver_status") == "approximate" and res.get("cfr_frequencies"):
                res["solver_backend"] = "python_cfr_plus"
                return res

        # Flop or multiway: heuristic frequencies, not a solved equilibrium.
        eq_realization = 1.05 if self.in_position else 0.94
        realized_eq = min(1.0, self.equity * eq_realization + 0.03 * self.range_advantage)
        clean_outs = self.outs_info.get("clean_outs", self.outs_info.get("outs", 0))

        if self.call_amount <= 0:
            # Facing check on flop
            bet_score = realized_eq + 0.08 * self.range_advantage + 0.06 * self.nut_advantage
            if clean_outs >= 8:
                bet_score += 0.12
            elif clean_outs >= 4:
                bet_score += 0.06
            p_bet = int(round(max(0.0, min(100.0, (bet_score - 0.35) * 180.0))))
            p_check = 100 - p_bet
            ev_est = round(self.pot_size * realized_eq, 2)
            freqs = {"RAISE": p_bet, "CALL": p_check}
            return {
                "cfr_frequencies": {k: v for k, v in freqs.items() if v > 0} or {"CALL": 100},
                "ev": ev_est,
                "mdf": 1.0,
            }
        else:
            total_pot_after_call = self.pot_size + self.call_amount * 2
            ev_call = round(realized_eq * total_pot_after_call - self.call_amount, 2)
            margin = realized_eq - self.required_equity
            if margin < -0.05:
                freqs = {"FOLD": 100}
                ev_est = 0.0
            elif realized_eq >= 0.68 or (clean_outs >= 8 and realized_eq >= 0.50):
                p_raise = int(round(min(85.0, max(35.0, (realized_eq - 0.50) * 160.0 + 25.0 * max(0.0, self.nut_advantage)))))
                freqs = {"RAISE": p_raise, "CALL": 100 - p_raise}
                ev_est = round(max(ev_call, ev_call * 1.15), 2)
            elif margin < 0.04:
                p_call = int(round(max(20.0, min(85.0, 50.0 + margin * 600.0))))
                freqs = {"CALL": p_call, "FOLD": 100 - p_call}
                ev_est = max(0.0, ev_call)
            else:
                freqs = {"CALL": 100}
                ev_est = ev_call
            return {
                "cfr_frequencies": {k: v for k, v in freqs.items() if v > 0} or {"FOLD": 100},
                "ev": ev_est,
                "mdf": self.mdf,
            }

    def _calculate_recommended_sizing(self) -> str:
        """Recommend geometric/texture-adjusted, CFR-preferred, and range/nut-advantage bet or raise sizing."""
        if self.decision == Decision.FOLD:
            return "Fold"
        if self.decision == Decision.CALL:
            return "Check" if self.call_amount <= 0 else "Call"

        # Decision is RAISE (or BET when call_amount <= 0)
        if 0 < self.spr <= 1.5:
            return "All-in (low SPR)"

        texture = self.board_texture.get('texture')
        texture_name = texture.value if isinstance(texture, BoardTexture) else str(texture)
        if self.call_amount <= 0:
            cfr_sizing = self._cfr_result.get("cfr_preferred_sizing") if isinstance(self._cfr_result, dict) else None
            if cfr_sizing and self.street in ("flop", "turn", "river"):
                return str(cfr_sizing)
            # High range advantage on dry/moderate board favors 33% pot range bet
            if texture_name == "dry" and self.range_advantage >= 0.05:
                return "33% pot"
            # Strong nut advantage or wet board favors polar 75% pot sizing
            if texture_name == "wet" or self.nut_advantage >= 0.18:
                return "75% pot"
            elif texture_name == "moderate":
                return "66% pot"
            return "33% pot"
        else:
            return "3.0x raise" if (texture_name == "wet" or not self.in_position) else "2.5x raise"
    
    def _calculate_outs(self) -> Dict[str, Any]:
        """Calculate outs information."""
        if get_outs is None:
            return {
                'outs': 0,
                'description': 'Unknown',
                'draw_type': 'none'
            }
        
        try:
            return get_outs(self.hero_hand, self.board, street=self.street)
        except Exception:
            return {
                'outs': 0,
                'description': 'Unknown',
                'draw_type': 'none'
            }
    
    def _get_strategy_adjustments(self) -> Tuple[float, float, float]:
        """
        Compute threshold adjustments based on aggression_factor, strategy profile,
        and opponent VPIP badge.

        Returns:
            Tuple of (value_raise_threshold, semi_bluff_threshold, call_adjustment)
        """
        agg_delta = self.aggression_factor - 1.0  # -0.5 to +1.0
        profile_upper = (self.profile or "ABC").upper()
        profile_raise_shift = 0.0
        profile_call_shift = 0.0
        if profile_upper == "LAG":
            profile_raise_shift = -0.03
            profile_call_shift = -0.02
        elif profile_upper == "AGGRESSIVE":
            profile_raise_shift = -0.02
            profile_call_shift = -0.01
        elif profile_upper == "TAG":
            profile_raise_shift = 0.02
            profile_call_shift = 0.02

        vpip_raise_shift = 0.0
        vpip_bluff_shift = 0.0
        vpip_call_shift = 0.0
        if self.opponent_vpip is not None:
            if self.opponent_vpip >= 45.0:
                vpip_raise_shift = -0.04  # Value bet thinner against loose-passive callers
                vpip_bluff_shift = 0.06   # Semi-bluff less against calling stations
                vpip_call_shift = 0.02
            elif self.opponent_vpip <= 18.0:
                vpip_raise_shift = 0.03   # Tighter value threshold against nits
                vpip_bluff_shift = -0.04  # Bluff more frequently against high-fold nits
                vpip_call_shift = 0.03    # Respect nit wagers

        value_raise_threshold = max(0.50, min(0.82, 0.68 - agg_delta * 0.06 + profile_raise_shift + vpip_raise_shift))
        semi_bluff_threshold = max(0.40, min(0.72, 0.55 - agg_delta * 0.06 + profile_raise_shift + vpip_bluff_shift))
        call_adjustment = -agg_delta * 0.02 + profile_call_shift + vpip_call_shift
        return value_raise_threshold, semi_bluff_threshold, call_adjustment

    def _make_decision(self) -> Decision:
        """
        Make a CALL/FOLD/RAISE decision based on equity vs required equity,
        CFR+ subgame frequencies/EV, board texture, strong value hands, drawing potential,
        and active strategy profile / aggression factor.

        Returns:
            Decision enum (CALL, FOLD, or RAISE)
        """
        value_raise_thresh, semi_bluff_thresh, call_adj = self._get_strategy_adjustments()
        clean_outs = self.outs_info.get('clean_outs', self.outs_info.get('outs', 0))
        can_semi_bluff = (
            self.street != "river"
            and self.equity > semi_bluff_thresh
            and clean_outs >= 4
        )
        cfr_raise = self.cfr_frequencies.get("RAISE", 0) if self.cfr_frequencies else 0
        cfr_call = self.cfr_frequencies.get("CALL", 0) if self.cfr_frequencies else 0
        cfr_fold = self.cfr_frequencies.get("FOLD", 0) if self.cfr_frequencies else 0

        # When facing no bet (free check), never recommend FOLD
        if self.call_amount <= 0:
            if self.equity >= value_raise_thresh or can_semi_bluff:
                return Decision.RAISE
            if self.num_opponents == 1 and self.street in ("flop", "turn", "river") and cfr_raise >= 65 and self.equity >= 0.52:
                return Decision.RAISE
            return Decision.CALL

        # Adjust decision based on board texture and reverse-implied-odds discipline
        texture = self.board_texture.get('texture')
        texture_name = texture.value if isinstance(texture, BoardTexture) else str(texture)

        # On wet boards, be more cautious with marginal calls; also guard against
        # reverse implied odds when holding 0 clean draw outs and weak equity on flop/turn.
        texture_adjustment = 0.0
        if texture_name == "wet":
            texture_adjustment = 0.03  # Require 3% more equity on wet boards
        elif texture_name == "dry":
            texture_adjustment = -0.02  # Can call with 2% less equity on dry boards

        rio_penalty = 0.0
        if self.street in ("flop", "turn") and clean_outs == 0 and self.equity < 0.45:
            # Discount optimistic implied-odds buffer when we have no draw outs and <45% equity
            rio_penalty = 0.03 if self.in_position else 0.05
        if self.num_opponents > 1:
            rio_penalty += 0.02 * (self.num_opponents - 1)

        adjusted_required = max(0.0, self.required_equity + texture_adjustment + call_adj + rio_penalty)

        # Incorporate CFR+ subgame solver across Flop/Turn/River when it strongly favors an action
        if self.num_opponents == 1 and self.street in ("flop", "turn", "river") and self.cfr_frequencies:
            if cfr_raise >= 60 and (self.equity >= value_raise_thresh - 0.05 or can_semi_bluff):
                return Decision.RAISE
            if cfr_fold >= 75 and self.ev <= 0 and self.equity < adjusted_required:
                return Decision.FOLD
            if (cfr_call + cfr_raise) >= 65 and self.ev > 0 and self.equity >= adjusted_required - 0.03:
                if self.equity >= value_raise_thresh or can_semi_bluff or (cfr_raise > cfr_call and self.equity >= 0.60):
                    return Decision.RAISE
                return Decision.CALL

        # If equity exceeds adjusted required equity, call or raise
        if self.equity >= adjusted_required:
            # Raise for value with strong made hands or semi-bluff/value-draw raise before river
            if self.equity >= value_raise_thresh or can_semi_bluff:
                return Decision.RAISE
            return Decision.CALL

        return Decision.FOLD

    def _generate_reasoning(self) -> str:
        """Generate human-readable reasoning for the decision."""
        parts = []

        # Equity information
        equity_pct = self.equity * 100
        required_pct = self.required_equity * 100
        parts.append(f"Equity: {equity_pct:.1f}%")
        parts.append(f"Required: {required_pct:.1f}%")

        # Pot odds
        pot_odds_pct = self.pot_odds * 100
        parts.append(f"Pot odds: {pot_odds_pct:.1f}%")
        if self.num_opponents > 1:
            parts.append(f"Opponents: {self.num_opponents}")
        if self.opponent_vpip is not None:
            vpip_tag = "Loose" if self.opponent_vpip >= 45 else ("Nit" if self.opponent_vpip <= 18 else "Reg")
            parts.append(f"VPIP: {self.opponent_vpip:.0f}% ({vpip_tag})")

        # Board texture
        texture = self.board_texture.get('texture')
        texture_name = texture.value if isinstance(texture, BoardTexture) else str(texture)
        parts.append(f"Board: {texture_name.upper()}")

        # Outs information
        if self.outs_info['outs'] > 0:
            parts.append(f"Outs: {self.outs_info['outs']} ({self.outs_info['description']})")
        elif self.outs_info.get('overcard_outs', 0) > 0:
            parts.append(f"Outs: {self.outs_info['overcard_outs']} ({self.outs_info.get('overcard_description', 'overcards')})")
        elif self.outs_info.get('improvement_outs', 0) > 0:
            parts.append(f"Outs: {self.outs_info['improvement_outs']} ({self.outs_info.get('improvement_description', 'improvement')})")
        else:
            parts.append("Outs: 0 (No significant draws)")

        # Implied odds & SPR
        implied_odds = self.implied_odds_info.get('implied_odds', 0)
        implied_action = self.implied_odds_info.get('recommended_action', '')
        parts.append(f"Implied odds: {implied_odds}x ({implied_action})")
        if self.spr > 0:
            parts.append(f"SPR: {self.spr:.1f}")

        # Decision rationale
        if self.decision == Decision.CALL:
            if self.call_amount <= 0:
                parts.append("Free check (no bet to call)")
            else:
                margin = (self.equity - self.required_equity) * 100
                parts.append(f"+{margin:.1f}% equity margin")
        elif self.decision == Decision.FOLD:
            deficit = (self.required_equity - self.equity) * 100
            parts.append(f"-{deficit:.1f}% equity deficit")
        elif self.decision == Decision.RAISE:
            clean_outs = self.outs_info.get('clean_outs', self.outs_info.get('outs', 0))
            if self.street != "river" and clean_outs >= 4 and self.equity < 0.68:
                parts.append(f"Strong hand with drawing potential ({self.recommended_sizing})")
            else:
                parts.append(f"Strong value hand ({self.recommended_sizing})")

        # Solver / Range-Advantage / CFR insights
        if self.call_amount > 0:
            parts.append(f"MDF: {self.mdf * 100:.0f}%")
        if abs(self.range_advantage) >= 0.05 or abs(self.nut_advantage) >= 0.05:
            parts.append(f"Range adv: {self.range_advantage:+.2f} (Nut: {self.nut_advantage:+.2f})")
        if self.cfr_frequencies:
            freq_str = "/".join(f"{k} {v}%" for k, v in self.cfr_frequencies.items())
            if self._cfr_result.get("solver_backend") == "noregrets_mccfr":
                label = "MCCFR Subgame"
            elif self._cfr_result.get("solver_status") == "approximate":
                label = "Restricted CFR"
            else:
                label = "Heuristic"
            parts.append(f"{label}: {freq_str} (EV: {self.ev:+.1f})")

        return " | ".join(parts)
    
    def get_decision(self) -> str:
        """Get the decision as a string."""
        return self.decision.value
    
    def get_advice(self) -> Dict[str, Any]:
        """
        Get complete advice as a dictionary.
        
        Returns:
            Dictionary with all advice information including board texture,
            implied odds analysis, range/nut advantage, and CFR+ subgame frequencies.
        """
        # Get texture info
        texture = self.board_texture.get('texture')
        texture_value = texture.value if isinstance(texture, BoardTexture) else str(texture)
        
        return {
            'decision': self.decision.value,
            'recommended_sizing': self.recommended_sizing,
            'street': self.street,
            'spr': self.spr,
            'num_opponents': self.num_opponents,
            'in_position': self.in_position,
            'opponent_vpip': self.opponent_vpip,
            'equity': self.equity,
            'equity_pct': self.equity * 100,
            'required_equity': self.required_equity,
            'required_equity_pct': self.required_equity * 100,
            'pot_odds': self.pot_odds,
            'pot_odds_pct': self.pot_odds * 100,
            'mdf': self.mdf,
            'mdf_pct': self.mdf * 100,
            'ev': self.ev,
            'cfr_frequencies': self.cfr_frequencies,
            'solver_diagnostics': {
                'solver_status': self._cfr_result.get('solver_status', 'heuristic'),
                **{k: v for k, v in self._cfr_result.items()
                   if k.startswith('solver_') or k == 'future_betting'},
            },
            'range_advantage': self.range_advantage,
            'nut_advantage': self.nut_advantage,
            'outs': self.outs_info['outs'],
            'clean_outs': self.outs_info.get('clean_outs', self.outs_info['outs']),
            'outs_description': self.outs_info['description'],
            'draw_type': self.outs_info['draw_type'],
            'board_texture': texture_value,
            'board_texture_description': self.board_texture.get('description', ''),
            'connectivity': self.board_texture.get('connectivity', 0),
            'has_pairs': self.board_texture.get('has_pairs', False),
            'flush_draws': self.board_texture.get('flush_draws', 0),
            'straight_draws': self.board_texture.get('straight_draws', 0),
            'implied_odds': self.implied_odds_info.get('implied_odds', 0),
            'implied_odds_action': self.implied_odds_info.get('recommended_action', ''),
            'breakeven_equity': self.implied_odds_info.get('breakeven_equity', 0),
            'potential_profit': self.implied_odds_info.get('potential_profit', 0),
            'reasoning': self.reasoning
        }


def get_postflop_advice(
    hero_hand: str,
    board: str,
    pot_size: float,
    call_amount: float,
    opponent_range: str = "22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 92s+, 82s+, 72s+, 62s+, 52s+, 42s+, 32s+, ATo+, KTo+, QTo+, JTo",
    iterations: int = 1000,
    effective_stack: float = None,
    num_opponents: int = 1,
    aggression_factor: float = 1.0,
    profile: Optional[Any] = None,
    spot: Optional[Dict[str, Any]] = None,
    in_position: Optional[bool] = None,
    opponent_vpip: Optional[float] = None,
    use_native_engine: bool = False,
    native_search_ms: int = 40,
    big_blind: Optional[float] = None,
    observed_actions: Optional[List[Dict[str, Any]]] = None,
    postflop_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Get postflop advice for a given situation.
    
    Args:
        hero_hand: Hero's hole cards
        board: Board cards
        pot_size: Current pot size
        call_amount: Amount to call
        opponent_range: Opponent's range
        iterations: Monte Carlo iterations
        effective_stack: Effective stack for implied odds calculation
        num_opponents: Number of active opponents in the hand (default 1)
        aggression_factor: Strategy aggression multiplier (default 1.0)
        profile: Strategy profile name or enum (optional)
        opponent_vpip: Opponent VPIP percentage (0-100) for exploitative adjustments
    
    Returns:
        Dictionary with decision and reasoning
    """
    advisor = PostflopAdvice(
        hero_hand=hero_hand,
        board=board,
        pot_size=pot_size,
        call_amount=call_amount,
        opponent_range=opponent_range,
        iterations=iterations,
        effective_stack=effective_stack,
        num_opponents=num_opponents,
        aggression_factor=aggression_factor,
        profile=profile,
        spot=spot,
        in_position=in_position,
        opponent_vpip=opponent_vpip,
        use_native_engine=use_native_engine,
        native_search_ms=native_search_ms,
        big_blind=big_blind,
        observed_actions=observed_actions,
        postflop_history=postflop_history,
    )
    return advisor.get_advice()


def check_numpy_availability() -> Dict[str, Any]:
    """
    Check if numpy is available and provide fallback information.
    
    Returns:
        Dictionary with numpy availability status and fallback info
    """
    return {
        'available': HAS_NUMPY,
        'fallback_mode': not HAS_NUMPY,
        'message': 'NumPy available' if HAS_NUMPY else 'NumPy not available - using fallback calculations'
    }


def calculate_pot_odds(pot_size: float, call_amount: float) -> float:
    """
    Calculate pot odds as a percentage.
    
    Args:
        pot_size: Current pot size
        call_amount: Amount to call
    
    Returns:
        Pot odds as a percentage (0-100)
    """
    if call_amount <= 0:
        return 0.0
    total_pot = pot_size + call_amount
    if total_pot <= 0:
        return 0.0
    return (call_amount / total_pot) * 100


def should_call(
    equity: float,
    pot_odds: float,
    implied_buffer: float = 0.15
) -> bool:
    """
    Determine if a call is profitable.
    
    Args:
        equity: Hero's equity (0-1)
        pot_odds: Pot odds (0-1)
        implied_buffer: Implied odds buffer (default 15%)
    
    Returns:
        True if call is profitable
    """
    required_equity = pot_odds * (1 - implied_buffer)
    return equity >= required_equity


def narrow_range_by_street_action(
    opponent_range: str,
    board: str,
    street: str = "flop",
    facing_bet: bool = False,
    opponent_vpip: Optional[float] = None,
    bet_fraction: Optional[float] = None,
) -> str:
    """
    Progressively narrow an opponent's preflop range across Flop -> Turn -> River
    based on board interaction, street progression, whether the opponent is betting,
    and the relative bet size (bet_fraction = call_amount / pot_size).
    """
    if not opponent_range or not board:
        return opponent_range
    rank_order = "23456789TJQKA"
    rank_val = {r: i for i, r in enumerate(rank_order)}
    clean_board = board.replace(" ", "")
    board_ranks = [clean_board[i].upper() for i in range(0, len(clean_board) - 1, 2) if clean_board[i].upper() in rank_val]
    board_suits = [clean_board[i + 1].lower() for i in range(0, len(clean_board) - 1, 2) if clean_board[i].upper() in rank_val]
    if len(board_ranks) < 3:
        return opponent_range

    inferred_street = (street or "").lower()
    if inferred_street not in ("flop", "turn", "river"):
        inferred_street = "river" if len(board_ranks) >= 5 else ("turn" if len(board_ranks) == 4 else "flop")

    # On flop without facing a bet, keep the full preflop range
    if inferred_street == "flop" and not facing_bet:
        return opponent_range

    board_rank_set = set(board_ranks)
    board_rank_vals = sorted({rank_val[r] for r in board_ranks})
    max_board_val = max(board_rank_vals) if board_rank_vals else 0
    has_flush_draw_board = any(board_suits.count(s) >= 2 for s in set(board_suits))

    tokens = [t.strip() for t in opponent_range.split(",") if t.strip()]
    # Only narrow explicit canonical hand lists (leave shorthand range strings like "22+" intact if not expanded)
    if any("+" in t or "-" in t for t in tokens):
        try:
            from equity import parse_range
            expanded_combos = parse_range(opponent_range)
            canonical = set()
            for c1, c2 in expanded_combos:
                r1, s1 = c1[0].upper(), c1[1].lower()
                r2, s2 = c2[0].upper(), c2[1].lower()
                if rank_val.get(r1, -1) < rank_val.get(r2, -1):
                    r1, r2 = r2, r1
                    s1, s2 = s2, s1
                if r1 == r2:
                    canonical.add(f"{r1}{r2}")
                elif s1 == s2:
                    canonical.add(f"{r1}{r2}s")
                else:
                    canonical.add(f"{r1}{r2}o")
            tokens = sorted(canonical)
        except Exception:
            return opponent_range

    def _score_hand_on_board(h: str) -> int:
        if len(h) < 2 or h[0] not in rank_val or h[1] not in rank_val:
            return 2
        r1, r2 = h[0], h[1]
        v1, v2 = rank_val[r1], rank_val[r2]
        suited = h.endswith("s")
        is_pair = (r1 == r2)

        # Sets / Two-pair / Pocket pairs
        if is_pair:
            if r1 in board_rank_set:
                return 5  # Set / Quads
            if v1 > max_board_val:
                return 4  # Overpair
            if v1 >= rank_val["9"]:
                return 3  # Mid-high pocket pair
            return 2      # Underpair

        hits = (1 if r1 in board_rank_set else 0) + (1 if r2 in board_rank_set else 0)
        if hits >= 2:
            return 5  # Two pair
        if hits == 1:
            paired_val = v1 if r1 in board_rank_set else v2
            if paired_val >= max_board_val:
                return 4  # Top pair
            return 3      # Middle / bottom pair

        # Straight connectivity (2 cards within 4 ranks of 2+ board ranks)
        hand_vals = {v1, v2}
        near_board = sum(1 for bv in board_rank_vals if any(abs(bv - hv) <= 2 for hv in hand_vals))
        if near_board >= 2 and abs(v1 - v2) <= 4:
            return 3  # Straight / combo draw candidate

        if suited and has_flush_draw_board and (v1 >= rank_val["T"] or near_board >= 1):
            return 3  # Suited flush draw candidate

        if v1 >= rank_val["A"] and v2 >= rank_val["J"]:
            return 2  # Strong overcards (AK, AQ, AJ)
        return 1      # Unimproved air

    min_score = 2
    if inferred_street == "flop" and facing_bet:
        min_score = 3 if (bet_fraction is not None and bet_fraction >= 0.85) else 2
    elif inferred_street == "turn":
        if facing_bet:
            min_score = 4 if (bet_fraction is not None and bet_fraction >= 1.0) else 3
        else:
            min_score = 2
    elif inferred_street == "river":
        if facing_bet:
            min_score = 4 if (bet_fraction is not None and bet_fraction >= 0.85) else 3
        else:
            min_score = 2

    if opponent_vpip is not None:
        if opponent_vpip >= 45.0:
            min_score = max(1, min_score - 1)
        elif opponent_vpip <= 18.0 and facing_bet:
            min_score = min(4, min_score + 1)

    kept = [h for h in tokens if _score_hand_on_board(h) >= min_score]
    if len(kept) < 6:
        # Fallback to lower threshold so Monte Carlo range is never starved
        kept = [h for h in tokens if _score_hand_on_board(h) >= max(1, min_score - 1)]
    if not kept:
        return opponent_range
    return ", ".join(sorted(kept))


def spot_to_opponent_range(
    spot: Optional[Dict[str, Any]] = None,
    strategy_manager: Optional[Any] = None,
    opponent_vpip: Optional[float] = None,
    board: Optional[str] = None,
    street: Optional[str] = None,
    facing_bet: bool = False,
    bet_fraction: Optional[float] = None,
) -> str:
    """
    Convert an active preflop spot dictionary into a comma-separated opponent range string
    for context-aware postflop equity calculations, optionally adjusted for opponent VPIP
    and narrowed across postflop streets.

    Args:
        spot: Dictionary with 'kind' ('open', 'facing_open', 'facing_3bet', 'facing_4bet'),
              'pos', and optional 'vs' keys.
        strategy_manager: Optional StrategyManager instance for stack-depth, profile,
                          aggression, and custom-range adjustments.
        opponent_vpip: Optional opponent VPIP percentage (0-100).
        board: Optional board string for multi-street range narrowing.
        street: Optional postflop street ('flop', 'turn', 'river').
        facing_bet: Whether hero is facing a postflop bet/raise on the current street.

    Returns:
        Comma-separated range string of canonical hands (or default calling range).
    """
    default_range = "22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 92s+, 82s+, 72s+, 62s+, 52s+, 42s+, 32s+, ATo+, KTo+, QTo+, JTo"
    if not spot or not isinstance(spot, dict):
        if board:
            return narrow_range_by_street_action(
                default_range,
                board,
                street=street or "flop",
                facing_bet=facing_bet,
                opponent_vpip=opponent_vpip,
                bet_fraction=bet_fraction,
            )
        return default_range

    try:
        import ranges
    except ImportError:
        return default_range

    kind = spot.get("kind", "open")
    pos = spot.get("pos", "BTN")
    vs_pos = spot.get("vs", "UTG")

    opp_hands = set()
    use_strategy = (
        strategy_manager is not None
        and hasattr(strategy_manager, "advise_with_strategy")
        and (not hasattr(strategy_manager, "is_default_state") or not strategy_manager.is_default_state())
    )

    if use_strategy:
        if kind == "open":
            defender_pos = "BB" if pos != "BB" else "BTN"
            def_spot = {"kind": "facing_open", "pos": defender_pos, "vs": pos}
            _, action_sets = strategy_manager.advise_with_strategy(def_spot, None)
            opp_hands = set(action_sets.get("3-BET", set())) | set(action_sets.get("CALL", set()))
            if not opp_hands and hasattr(strategy_manager, "get_ranges_for_spot"):
                r = strategy_manager.get_ranges_for_spot(def_spot)
                opp_hands = set(r.get("RAISE", [])) | set(r.get("CALL", []))
        elif kind == "facing_open":
            open_spot = {"kind": "open", "pos": vs_pos, "vs": None}
            _, action_sets = strategy_manager.advise_with_strategy(open_spot, None)
            opp_hands = set(action_sets.get("RAISE", set()))
            if not opp_hands and hasattr(strategy_manager, "get_ranges_for_spot"):
                r = strategy_manager.get_ranges_for_spot(open_spot)
                opp_hands = set(r.get("RAISE", [])) | set(r.get("CALL", []))
        elif kind == "facing_3bet":
            for p_3bettor, p_opener in ranges.THREEBET.keys():
                if p_opener == pos:
                    tb_spot = {"kind": "facing_open", "pos": p_3bettor, "vs": pos}
                    _, action_sets = strategy_manager.advise_with_strategy(tb_spot, None)
                    opp_hands |= set(action_sets.get("3-BET", set()))
            if not opp_hands:
                f3_spot = {"kind": "facing_3bet", "pos": pos, "vs": vs_pos}
                _, action_sets = strategy_manager.advise_with_strategy(f3_spot, None)
                opp_hands = set(action_sets.get("4-BET", set())) | set(action_sets.get("CALL", set()))
        elif kind == "facing_4bet":
            f4_spot = {"kind": "facing_4bet", "pos": pos, "vs": vs_pos}
            _, action_sets = strategy_manager.advise_with_strategy(f4_spot, None)
            opp_hands = set(action_sets.get("5-BET", set())) | set(action_sets.get("CALL", set()))
            if not opp_hands and hasattr(strategy_manager, "get_ranges_for_spot"):
                r = strategy_manager.get_ranges_for_spot(f4_spot)
                opp_hands = set(r.get("RAISE", [])) | set(r.get("CALL", []))
        elif kind == "squeeze":
            open_spot = {"kind": "open", "pos": vs_pos, "vs": None}
            _, action_sets = strategy_manager.advise_with_strategy(open_spot, None)
            opp_hands = set(action_sets.get("RAISE", set()))
        elif kind == "iso_raise":
            limp_spot = {"kind": "iso_raise", "pos": vs_pos or "CO", "vs": None}
            _, action_sets = strategy_manager.advise_with_strategy(limp_spot, None)
            opp_hands = set(action_sets.get("CALL", set())) | set(action_sets.get("RAISE", set()))

    if not opp_hands:
        if kind == "open":
            # When hero opens from `pos`, typical caller is BB or BTN
            if pos != "BB" and ("BB", pos) in ranges.THREEBET:
                r = ranges.THREEBET[("BB", pos)]
                opp_hands = r.get("call", set()) | r.get("3b", set())
            elif ("BTN", pos) in ranges.THREEBET:
                r = ranges.THREEBET[("BTN", pos)]
                opp_hands = r.get("call", set()) | r.get("3b", set())
            else:
                opp_hands = ranges.BB_VS_BTN_OPEN_CALL
        elif kind == "facing_open":
            # Opponent opened from vs_pos
            opp_hands = ranges.OPEN_RANGES.get(vs_pos, set())
        elif kind == "facing_3bet":
            # Hero opened from pos and faced a 3-bet; aggregate 3-betting ranges vs pos
            for (p_3bettor, p_opener), r in ranges.THREEBET.items():
                if p_opener == pos:
                    opp_hands |= r.get("3b", set())
            if not opp_hands:
                f3 = ranges.FACING_3BET.get(pos, {})
                opp_hands = f3.get("4b", set()) | f3.get("call", set())
        elif kind == "squeeze":
            opp_hands = ranges.OPEN_RANGES.get(vs_pos, set())
        elif kind == "iso_raise":
            r = ranges.ISO_RAISE_BY_POS.get(vs_pos or "CO", ranges.ISO_RAISE_BY_POS.get("CO", {}))
            opp_hands = r.get("limp", set()) | (ranges.OPEN_RANGES.get(vs_pos, set()) if vs_pos in ranges.OPEN_RANGES else set())
        elif kind == "facing_4bet":
            opp_hands = ranges.FACING_4BET.get("5b", set()) | ranges.FACING_4BET.get("call", set())

    if opponent_vpip is not None and opp_hands:
        opp_hands = set(opp_hands)
        if opponent_vpip >= 45.0:
            opp_hands |= set( getattr(ranges, "OPEN_RANGES", {}).get("BTN", set()) )
        elif opponent_vpip <= 18.0:
            utg_hands = set( getattr(ranges, "OPEN_RANGES", {}).get("UTG", set()) )
            tightened = opp_hands & utg_hands
            if len(tightened) >= 6:
                opp_hands = tightened

    if not opp_hands:
        base_str = default_range
    else:
        base_str = ", ".join(sorted(opp_hands))

    if board:
        return narrow_range_by_street_action(
            base_str,
            board=board,
            street=street or "flop",
            facing_bet=facing_bet,
            opponent_vpip=opponent_vpip,
            bet_fraction=bet_fraction,
        )
    return base_str


def get_rule_of_42_equity(outs: int, street: str = "flop") -> float:
    """
    Estimate equity using the Rule of 4 and 2.
    
    Rule of 4: On flop, multiply outs by 4 for river equity
    Rule of 2: On turn, multiply outs by 2 for river equity
    
    Args:
        outs: Number of outs
        street: Current street ('flop' or 'turn')
    
    Returns:
        Estimated equity percentage
    """
    if street == "flop":
        return outs * 4
    else:
        return outs * 2


if __name__ == "__main__":
    # Example usage
    print("Postflop Decision Engine Demo")
    print("=" * 50)
    
    # Example 1: Flush draw
    print("\nExample 1: Flush draw on flop")
    advice = get_postflop_advice(
        hero_hand="AhKh",
        board="QdJd8d",
        pot_size=100,
        call_amount=50
    )
    print(f"Decision: {advice['decision']}")
    print(f"Reasoning: {advice['reasoning']}")
    
    # Example 2: Gutshot on turn
    print("\nExample 2: Gutshot on turn")
    advice = get_postflop_advice(
        hero_hand="T7h",
        board="Jh9h5c2d",
        pot_size=200,
        call_amount=100
    )
    print(f"Decision: {advice['decision']}")
    print(f"Reasoning: {advice['reasoning']}")
    
    # Example 3: Made hand
    print("\nExample 3: Top pair on flop")
    advice = get_postflop_advice(
        hero_hand="AhKc",
        board="Ah8d5s",
        pot_size=150,
        call_amount=75
    )
    print(f"Decision: {advice['decision']}")
    print(f"Reasoning: {advice['reasoning']}")
