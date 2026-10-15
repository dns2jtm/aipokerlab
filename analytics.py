"""
Logging & Analytics for Poker RTA

This module provides functionality to:
- Log all hands analyzed to a JSON file with timestamps
- Track GTO adherence (how often user follows vs deviates from recommendation)
- Calculate win rate impact
- Provide statistics and analytics
- Export data to CSV/JSON
"""

import atexit
import json
import csv
import os
import tempfile
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict


class Action(Enum):
    """Possible poker actions."""
    FOLD = "FOLD"
    CALL = "CALL"
    RAISE = "RAISE"
    CHECK = "CHECK"
    BET = "BET"


class HandResult(Enum):
    """Possible hand results."""
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"
    UNKNOWN = "unknown"


@dataclass
class HandLogEntry:
    """Represents a single hand analysis entry."""
    timestamp: float
    hand: str                    # e.g., "AKs", "JJ"
    position: Optional[str]      # e.g., "BTN", "SB", "BB"
    spot: Optional[str]          # e.g., "open", "facing_open", "facing_3bet"
    recommended_action: str      # e.g., "RAISE", "FOLD", "CALL"
    confidence: float            # Confidence percentage (0-100)
    user_action: Optional[str] = None  # What the user actually did
    followed_recommendation: Optional[bool] = None  # Did user follow advice?
    result: Optional[str] = None  # win/loss/push
    pot_size: Optional[float] = None
    table_name: Optional[str] = None
    stakes: Optional[str] = None
    mode: str = "preflop"        # preflop or postflop
    board: Optional[str] = None  # For postflop
    equity: Optional[float] = None  # For postflop
    bb_delta: Optional[float] = None  # Net BB won/lost from stack delta
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat(),
            'hand': self.hand,
            'position': self.position,
            'spot': self.spot,
            'recommended_action': self.recommended_action,
            'confidence': self.confidence,
            'user_action': self.user_action,
            'followed_recommendation': self.followed_recommendation,
            'result': self.result,
            'pot_size': self.pot_size,
            'table_name': self.table_name,
            'stakes': self.stakes,
            'mode': self.mode,
            'board': self.board,
            'equity': self.equity,
            'bb_delta': self.bb_delta,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HandLogEntry':
        """Create from dictionary."""
        return cls(
            timestamp=data['timestamp'],
            hand=data['hand'],
            position=data.get('position'),
            spot=data.get('spot'),
            recommended_action=data['recommended_action'],
            confidence=data.get('confidence', 0),
            user_action=data.get('user_action'),
            followed_recommendation=data.get('followed_recommendation'),
            result=data.get('result'),
            pot_size=data.get('pot_size'),
            table_name=data.get('table_name'),
            stakes=data.get('stakes'),
            mode=data.get('mode', 'preflop'),
            board=data.get('board'),
            equity=data.get('equity'),
            bb_delta=data.get('bb_delta'),
        )


class HandLogger:
    """
    Logs hand analysis to a JSON file.
    
    Features:
    - Append-only logging with timestamps
    - Thread-safe operations
    - Automatic file rotation
    """
    
    def __init__(self, log_path: str = None, async_save: bool = False, debounce_seconds: float = 0.05):
        """
        Initialize the hand logger.
        
        Args:
            log_path: Path to the JSON log file (default: hand_log.json in same directory)
            async_save: If True, buffer/debounce disk writes on a background timer.
            debounce_seconds: Debounce delay when async_save is True.
        """
        if log_path is None:
            log_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "hand_log.json"
            )
        self._log_path = log_path
        self._async_save = bool(async_save)
        self._debounce_seconds = float(debounce_seconds)
        self._lock = threading.RLock()
        self._save_timer: Optional[threading.Timer] = None
        self._dirty = False
        self._hands: List[HandLogEntry] = []
        self._load_existing()
        atexit.register(self.flush)
    
    def _load_existing(self):
        """Load existing hand history from file."""
        if not os.path.exists(self._log_path):
            return
        
        try:
            with open(self._log_path, 'r') as f:
                data = json.load(f)
            
            if 'hands' in data:
                for entry_data in data['hands']:
                    # Skip corrupted entries where hand is not a string
                    if not isinstance(entry_data.get('hand'), str):
                        continue
                    self._hands.append(HandLogEntry.from_dict(entry_data))
        except (json.JSONDecodeError, KeyError, Exception) as e:
            print(f"Error loading hand log: {e}")
            self._hands = []
    
    def _write_snapshot_to_disk(self, snapshot: List[Dict[str, Any]]):
        """Write serialized hand history snapshot atomically to disk."""
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'total_hands': len(snapshot),
            'hands': snapshot
        }
        try:
            log_dir = os.path.dirname(os.path.abspath(self._log_path)) or '.'
            os.makedirs(log_dir, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix='.hand_log_', suffix='.tmp', dir=log_dir)
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp_path, self._log_path)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise
        except Exception as e:
            print(f"Error saving hand log: {e}")

    def _save(self):
        """Save hand history to file (synchronously or debounced on a background thread)."""
        with self._lock:
            self._dirty = True
            if not self._async_save:
                snapshot = [h.to_dict() for h in self._hands]
                self._dirty = False
                self._write_snapshot_to_disk(snapshot)
                return
            if self._save_timer is not None:
                self._save_timer.cancel()
            timer = threading.Timer(self._debounce_seconds, self.flush)
            timer.daemon = True
            self._save_timer = timer
            timer.start()

    def flush(self):
        """Immediately flush any pending buffered hand log changes to disk."""
        with self._lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
            if not self._dirty and os.path.exists(self._log_path):
                return
            snapshot = [h.to_dict() for h in self._hands]
            self._dirty = False
            self._write_snapshot_to_disk(snapshot)

    def close(self):
        """Flush pending writes and clean up timer resources."""
        self.flush()
    
    def log_hand(self, entry: HandLogEntry):
        """
        Log a hand analysis entry.
        
        Args:
            entry: HandLogEntry object to log
        """
        if not isinstance(entry.hand, str):
            return
        # Sanitize confidence if non-finite
        try:
            import math
            if not math.isfinite(entry.confidence):
                entry.confidence = 0.0
        except Exception:
            pass
        with self._lock:
            self._hands.append(entry)
            self._save()
    
    def log_analysis(self, hand: str, recommended_action: str, confidence: float = 0.0,
                     position: str = None, spot: str = None, table_name: str = None,
                     stakes: str = None, mode: str = "preflop", board: str = None,
                     equity: float = None, pot_size: float = None) -> HandLogEntry:
        """
        Convenience method to log a hand analysis.
        
        Args:
            hand: Hand string (e.g., "AKs")
            recommended_action: Recommended action (e.g., "RAISE")
            confidence: Confidence percentage (0-100)
            position: Player position
            spot: Spot type
            table_name: Table name
            stakes: Stakes
            mode: preflop or postflop
            board: Board cards (for postflop)
            equity: Calculated equity (for postflop)
            
        Returns:
            The created HandLogEntry
        """
        if not isinstance(hand, str):
            return None
        # Sanitize confidence: ensure finite
        try:
            import math
            if not math.isfinite(confidence):
                confidence = 0.0
        except Exception:
            confidence = 0.0
        entry = HandLogEntry(
            timestamp=time.time(),
            hand=hand,
            position=position,
            spot=spot,
            recommended_action=recommended_action,
            confidence=confidence,
            pot_size=pot_size,
            table_name=table_name,
            stakes=stakes,
            mode=mode,
            board=board,
            equity=equity
        )
        self.log_hand(entry)
        return entry
    
    def update_user_action(self, timestamp: float, user_action: str):
        """
        Update a logged hand with the user's actual action.
        
        Args:
            timestamp: Timestamp of the hand to update
            user_action: What the user actually did
        """
        with self._lock:
            for entry in reversed(self._hands):
                if abs(entry.timestamp - timestamp) < 1:  # Within 1 second
                    entry.user_action = user_action
                    entry.followed_recommendation = (user_action == entry.recommended_action)
                    self._save()
                    return True
        return False
    
    def update_result(self, timestamp: float, result: str, pot_size: float = None):
        """
        Update a logged hand with the result.
        
        Args:
            timestamp: Timestamp of the hand to update
            result: "win", "loss", or "push"
            pot_size: Size of the pot won/lost
        """
        with self._lock:
            for entry in reversed(self._hands):
                if abs(entry.timestamp - timestamp) < 1:
                    entry.result = result
                    entry.pot_size = pot_size
                    self._save()
                    return True
        return False

    def record_stack_delta(
        self,
        prev_stack_chips: float,
        new_stack_chips: float,
        big_blind: Optional[float] = None,
        timestamp: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Automatically record WIN / LOSS / PUSH and net BB delta from Hero's hand-to-hand stack change.

        Enforces poker accounting invariants so OCR stack misreads or rebuys are not
        misattributed:
        - A preflop FOLD cannot win chips (clamped to push/0 if positive) and can only
          lose posted blind/ante commitments (<= 1.5 BB in standard spots).
        - Extreme single-hand stack jumps (> 250 BB) without a matching pot are rejected
          as OCR stack-read noise or table reloads.
        """
        try:
            chip_delta = float(new_stack_chips) - float(prev_stack_chips)
        except (TypeError, ValueError):
            return None
        bb_val = float(big_blind) if (big_blind and float(big_blind) > 0) else None

        with self._lock:
            target_entry = None
            if timestamp is not None:
                for entry in reversed(self._hands):
                    if abs(entry.timestamp - timestamp) < 1.0:
                        target_entry = entry
                        break
            if target_entry is None:
                for entry in reversed(self._hands):
                    if entry.result is None:
                        target_entry = entry
                        break
            if target_entry is None:
                return None

            effective_act = (target_entry.user_action or target_entry.recommended_action or "").upper()
            is_preflop_fold = (target_entry.mode == "preflop" and effective_act == "FOLD")

            if is_preflop_fold:
                pos = (target_entry.position or "").upper()
                spot = (target_entry.spot or "open").lower()
                # When folding preflop without having voluntarily invested, maximum loss is blind/straddle
                max_fold_loss_bb = 1.0 if pos == "BB" else (0.5 if pos == "SB" else 0.0)
                if spot in ("facing_3bet", "facing_4bet"):
                    max_fold_loss_bb = 12.0 if spot == "facing_3bet" else 28.0
                if chip_delta > 0:
                    # Cannot win chips by folding preflop
                    chip_delta = 0.0
                elif bb_val is not None:
                    loss_bb = abs(chip_delta) / bb_val
                    if loss_bb > max(1.5, max_fold_loss_bb + 0.5):
                        # OCR misread of stack on preflop fold; clamp to expected blind loss
                        chip_delta = -max_fold_loss_bb * bb_val
            elif bb_val is not None:
                # Reject implausible >250 BB single-hand OCR stack jumps unless pot size corroborates
                raw_bb_delta = abs(chip_delta) / bb_val
                if raw_bb_delta > 250.0 and (target_entry.pot_size is None or abs(chip_delta) > target_entry.pot_size * 2.5):
                    return None

            bb_delta = round(chip_delta / bb_val, 2) if bb_val is not None else None
            if abs(chip_delta) < 1e-6:
                result_str = "push"
                chip_delta = 0.0
                if bb_delta is not None:
                    bb_delta = 0.0
            elif chip_delta > 0:
                result_str = "win"
            else:
                result_str = "loss"

            target_entry.result = result_str
            target_entry.bb_delta = bb_delta
            if target_entry.pot_size is None or is_preflop_fold:
                target_entry.pot_size = round(abs(chip_delta), 2)
            self._save()
            return {
                'result': result_str,
                'chip_delta': chip_delta,
                'bb_delta': bb_delta,
                'hand': target_entry.hand,
            }
    
    def sanitize_history(self) -> Dict[str, int]:
        """Sanitize historical hand log entries in-place to repair OCR stack-delta artifacts.

        Repairs:
        - Preflop folds recorded with positive bb_delta or result == 'win' -> corrected to
          result='push', bb_delta=0.0, pot_size=0.0.
        - Preflop folds outside the blinds (position not in ('SB', 'BB')) with negative bb_delta
          -> corrected to result='push', bb_delta=0.0, pot_size=0.0.
        - Preflop blind folds ('SB' / 'BB') with excessive negative bb_delta (> 0.5 BB for SB
          or > 1.0 BB for BB) -> clamped to their blind forfeit (-0.5 BB for SB, -1.0 BB for BB).
        - Single-hand outliers where abs(bb_delta) > 250.0 (or preflop 3-bet/open OCR glitches
          exceeding 100 BB without all-in corroboration) -> clamped to realistic stack bounds.
        """
        stats = {
            'preflop_fold_wins_fixed': 0,
            'preflop_nonblind_fold_losses_fixed': 0,
            'preflop_blind_fold_losses_clamped': 0,
            'extreme_outliers_clamped': 0,
            'total_modified': 0,
        }
        with self._lock:
            for entry in self._hands:
                if not entry.result or entry.result == 'unknown':
                    continue
                modified = False
                effective_act = (entry.user_action or (entry.recommended_action if entry.user_action is None else '') or '').upper()
                is_preflop_fold = (
                    (entry.mode or 'preflop') == 'preflop'
                    and (entry.user_action == 'FOLD' or (entry.user_action is None and effective_act == 'FOLD'))
                )
                pos = (entry.position or '').upper()

                if is_preflop_fold:
                    if entry.result == 'win' or (entry.bb_delta is not None and entry.bb_delta > 0):
                        entry.result = 'push'
                        entry.bb_delta = 0.0
                        entry.pot_size = 0.0
                        stats['preflop_fold_wins_fixed'] += 1
                        modified = True
                    elif entry.result == 'loss' or (entry.bb_delta is not None and entry.bb_delta < 0):
                        if pos not in ('SB', 'BB'):
                            entry.result = 'push'
                            entry.bb_delta = 0.0
                            entry.pot_size = 0.0
                            stats['preflop_nonblind_fold_losses_fixed'] += 1
                            modified = True
                        else:
                            max_blind_loss = 0.5 if pos == 'SB' else 1.0
                            if entry.bb_delta is not None and abs(entry.bb_delta) > max_blind_loss:
                                old_bb = abs(entry.bb_delta)
                                inferred_bb_chips = (entry.pot_size / old_bb) if (entry.pot_size and old_bb > 0) else 500.0
                                entry.bb_delta = -max_blind_loss
                                entry.pot_size = round(max_blind_loss * inferred_bb_chips, 2)
                                entry.result = 'loss'
                                stats['preflop_blind_fold_losses_clamped'] += 1
                                modified = True
                else:
                    if entry.bb_delta is not None:
                        max_bound = 100.0 if (entry.mode or 'preflop') == 'preflop' else 250.0
                        if abs(entry.bb_delta) > max_bound:
                            sign = 1.0 if entry.bb_delta > 0 else -1.0
                            old_bb = abs(entry.bb_delta)
                            inferred_bb_chips = (entry.pot_size / old_bb) if (entry.pot_size and old_bb > 0) else 500.0
                            clamped_bb = 100.0 if max_bound == 100.0 else 250.0
                            if (entry.mode or 'preflop') == 'preflop' and '3-BET' in effective_act:
                                clamped_bb = 12.0
                            entry.bb_delta = round(sign * clamped_bb, 2)
                            entry.pot_size = round(clamped_bb * inferred_bb_chips, 2)
                            stats['extreme_outliers_clamped'] += 1
                            modified = True

                if modified:
                    stats['total_modified'] += 1

            if stats['total_modified'] > 0:
                self._save()
                self.flush()
        return stats

    def get_hands(self, limit: int = None, since: float = None) -> List[HandLogEntry]:
        """
        Get logged hands.
        
        Args:
            limit: Maximum number of hands to return (None for all)
            since: Only return hands since this timestamp
            
        Returns:
            List of HandLogEntry objects
        """
        with self._lock:
            hands = self._hands.copy()
        
        if since:
            hands = [h for h in hands if h.timestamp >= since]
        
        if limit:
            hands = hands[-limit:]
        
        return hands
    
    def get_recent_hands(self, count: int = 10) -> List[HandLogEntry]:
        """Get the most recent hands."""
        return self.get_hands(limit=count)
    
    def clear(self):
        """Clear all logged hands."""
        with self._lock:
            self._hands = []
            self._save()


class Analytics:
    """
    Provides analytics and statistics from logged hands.
    
    Features:
    - GTO adherence tracking
    - Win rate calculations
    - Position-based statistics
    - Action distribution
    - Most common hand types
    """
    
    def __init__(self, logger: HandLogger):
        """
        Initialize analytics with a hand logger.
        
        Args:
            logger: HandLogger instance to analyze
        """
        self._logger = logger
    
    def get_total_hands(self) -> int:
        """Get total number of logged hands."""
        return len(self._logger.get_hands())
    
    def get_gto_adherence(self) -> Dict[str, Any]:
        """
        Calculate GTO adherence statistics.
        
        Returns:
            Dictionary with adherence statistics
        """
        hands = self._logger.get_hands()
        
        # Filter hands with user actions
        hands_with_actions = [h for h in hands if h.user_action is not None]
        
        if not hands_with_actions:
            return {
                'total_with_actions': 0,
                'followed': 0,
                'deviated': 0,
                'adherence_rate': 0.0
            }
        
        followed = sum(1 for h in hands_with_actions if h.followed_recommendation)
        deviated = len(hands_with_actions) - followed
        
        return {
            'total_with_actions': len(hands_with_actions),
            'followed': followed,
            'deviated': deviated,
            'adherence_rate': (followed / len(hands_with_actions)) * 100
        }
    
    def get_action_distribution(self) -> Dict[str, float]:
        """
        Get distribution of recommended actions.
        
        Returns:
            Dictionary mapping action to percentage
        """
        hands = self._logger.get_hands()
        
        if not hands:
            return {}
        
        action_counts = defaultdict(int)
        for hand in hands:
            if not isinstance(hand.hand, str):
                continue
            action_counts[hand.recommended_action] += 1
        
        total = sum(action_counts.values())
        if total == 0:
            return {}
        return {action: (count / total) * 100 for action, count in action_counts.items()}
    
    def get_position_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics broken down by position.
        
        Returns:
            Dictionary mapping position to stats
        """
        hands = self._logger.get_hands()
        
        position_hands = defaultdict(list)
        for hand in hands:
            if not isinstance(hand.hand, str):
                continue
            if hand.position:
                position_hands[hand.position].append(hand)
        
        result = {}
        for position, pos_hands in position_hands.items():
            actions = self._get_action_counts(pos_hands)
            result[position] = {
                'total_hands': len(pos_hands),
                'actions': actions,
                'most_common_action': max(actions.keys(), key=lambda k: actions[k]) if actions else None
            }
        
        return result
    
    def get_spot_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics broken down by spot.
        
        Returns:
            Dictionary mapping spot to stats
        """
        hands = self._logger.get_hands()
        
        spot_hands = defaultdict(list)
        for hand in hands:
            if not isinstance(hand.hand, str):
                continue
            if hand.spot:
                spot_hands[hand.spot].append(hand)
        
        result = {}
        for spot, spot_hands_list in spot_hands.items():
            actions = self._get_action_counts(spot_hands_list)
            result[spot] = {
                'total_hands': len(spot_hands_list),
                'actions': actions
            }
        
        return result
    
    def _get_action_counts(self, hands: List[HandLogEntry]) -> Dict[str, int]:
        """Get action counts for a list of hands."""
        counts = defaultdict(int)
        for hand in hands:
            # Guard against corrupted entries
            if not isinstance(hand.hand, str):
                continue
            counts[hand.recommended_action] += 1
        return dict(counts)
    
    def get_most_common_hands(self, limit: int = 10) -> List[tuple]:
        """
        Get the most commonly analyzed hands.
        
        Args:
            limit: Maximum number of hands to return
            
        Returns:
            List of (hand, count) tuples
        """
        hands = self._logger.get_hands()
        
        hand_counts = defaultdict(int)
        for hand in hands:
            if not isinstance(hand.hand, str):
                continue
            hand_counts[hand.hand] += 1
        
        sorted_hands = sorted(hand_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_hands[:limit]
    
    def get_win_rate_stats(self) -> Dict[str, Any]:
        """
        Calculate win rate statistics, including BB/100 and VPIP win rate.
        
        Returns:
            Dictionary with win rate statistics
        """
        hands = self._logger.get_hands()
        
        # Filter hands with results
        hands_with_results = [h for h in hands if h.result and h.result != 'unknown']
        
        if not hands_with_results:
            return {
                'total_with_results': 0,
                'wins': 0,
                'losses': 0,
                'pushes': 0,
                'win_rate': 0.0,
                'total_won': 0.0,
                'total_lost': 0.0,
                'net': 0.0,
                'total_bb_net': 0.0,
                'bb_per_100': 0.0,
                'vpip_hands_win_rate': 0.0,
            }
        
        wins = sum(1 for h in hands_with_results if h.result == 'win')
        losses = sum(1 for h in hands_with_results if h.result == 'loss')
        pushes = sum(1 for h in hands_with_results if h.result == 'push')
        
        # Calculate total won/lost
        total_won = sum(h.pot_size or 0 for h in hands_with_results if h.result == 'win')
        total_lost = sum(h.pot_size or 0 for h in hands_with_results if h.result == 'loss')
        
        total_decided = wins + losses
        win_rate = (wins / total_decided * 100) if total_decided > 0 else 0.0

        # Calculate BB net and BB/100 across resolved hands
        total_bb_net = round(sum(float(h.bb_delta or 0.0) for h in hands_with_results), 2)
        bb_per_100 = round((total_bb_net / len(hands_with_results)) * 100.0, 2) if hands_with_results else 0.0

        # VPIP win rate (excluding trivial preflop folds)
        vpip_decided = [
            h for h in hands_with_results
            if h.result in ('win', 'loss') and not (
                (h.mode or 'preflop') == 'preflop'
                and ((h.user_action or h.recommended_action or '').upper() == 'FOLD')
            )
        ]
        vpip_wins = sum(1 for h in vpip_decided if h.result == 'win')
        vpip_win_rate = round((vpip_wins / len(vpip_decided)) * 100.0, 2) if vpip_decided else 0.0
        
        return {
            'total_with_results': len(hands_with_results),
            'wins': wins,
            'losses': losses,
            'pushes': pushes,
            'win_rate': win_rate,
            'total_won': total_won,
            'total_lost': total_lost,
            'net': total_won - total_lost,
            'total_bb_net': total_bb_net,
            'bb_per_100': bb_per_100,
            'vpip_hands_win_rate': vpip_win_rate,
        }
    
    def get_adherence_by_result(self) -> Dict[str, Dict[str, Any]]:
        """
        Analyze GTO adherence by result (did following GTO lead to wins?).
        
        Returns:
            Dictionary with adherence analysis by result
        """
        hands = self._logger.get_hands()
        
        # Filter hands with both user action and result
        relevant_hands = [h for h in hands 
                         if h.user_action is not None and h.result and h.result != 'unknown']
        
        if not relevant_hands:
            return {
                'followed_then_won': 0,
                'followed_then_lost': 0,
                'deviated_then_won': 0,
                'deviated_then_lost': 0,
                'followed_win_rate': 0.0,
                'deviated_win_rate': 0.0
            }
        
        followed_won = sum(1 for h in relevant_hands 
                          if h.followed_recommendation and h.result == 'win')
        followed_lost = sum(1 for h in relevant_hands 
                           if h.followed_recommendation and h.result == 'loss')
        deviated_won = sum(1 for h in relevant_hands 
                          if not h.followed_recommendation and h.result == 'win')
        deviated_lost = sum(1 for h in relevant_hands 
                           if not h.followed_recommendation and h.result == 'loss')
        
        followed_total = followed_won + followed_lost
        deviated_total = deviated_won + deviated_lost
        
        followed_win_rate = (followed_won / followed_total * 100) if followed_total > 0 else 0.0
        deviated_win_rate = (deviated_won / deviated_total * 100) if deviated_total > 0 else 0.0
        
        return {
            'followed_then_won': followed_won,
            'followed_then_lost': followed_lost,
            'deviated_then_won': deviated_won,
            'deviated_then_lost': deviated_lost,
            'followed_win_rate': followed_win_rate,
            'deviated_win_rate': deviated_win_rate,
            'gto_advantage': followed_win_rate - deviated_win_rate
        }
    
    def get_time_series(self, interval: str = "day") -> Dict[str, Dict[str, Any]]:
        """
        Get statistics over time.
        
        Args:
            interval: "hour", "day", or "week"
            
        Returns:
            Dictionary mapping time period to stats
        """
        hands = self._logger.get_hands()
        
        if not hands:
            return {}
        
        # Group hands by time period
        time_groups = defaultdict(list)
        
        for hand in hands:
            if not isinstance(hand.hand, str):
                continue
            dt = datetime.fromtimestamp(hand.timestamp)
            
            if interval == "hour":
                key = dt.strftime("%Y-%m-%d %H:00")
            elif interval == "day":
                key = dt.strftime("%Y-%m-%d")
            elif interval == "week":
                key = dt.strftime("%Y-W%W")
            else:
                key = dt.strftime("%Y-%m-%d")
            
            time_groups[key].append(hand)
        
        # Calculate stats for each period
        result = {}
        for period, period_hands in sorted(time_groups.items()):
            actions = self._get_action_counts(period_hands)
            result[period] = {
                'total_hands': len(period_hands),
                'actions': actions
            }
        
        return result
    
    def get_mode_stats(self) -> Dict[str, Any]:
        """
        Get statistics broken down by mode (preflop vs postflop).

        Returns:
            Dictionary with mode counts and average postflop equity
        """
        hands = [h for h in self._logger.get_hands() if isinstance(h.hand, str)]
        preflop_hands = [h for h in hands if (h.mode or 'preflop') == 'preflop']
        postflop_hands = [h for h in hands if h.mode == 'postflop']
        equities = [float(h.equity) for h in postflop_hands if h.equity is not None]
        avg_equity = (sum(equities) / len(equities)) if equities else 0.0
        return {
            'preflop_hands': len(preflop_hands),
            'postflop_hands': len(postflop_hands),
            'avg_postflop_equity': avg_equity,
        }

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of all statistics.
        
        Returns:
            Dictionary with all key statistics
        """
        mode_stats = self.get_mode_stats()
        return {
            'total_hands': self.get_total_hands(),
            'preflop_hands': mode_stats['preflop_hands'],
            'postflop_hands': mode_stats['postflop_hands'],
            'avg_postflop_equity': mode_stats['avg_postflop_equity'],
            'mode_stats': mode_stats,
            'gto_adherence': self.get_gto_adherence(),
            'action_distribution': self.get_action_distribution(),
            'position_stats': self.get_position_stats(),
            'spot_stats': self.get_spot_stats(),
            'most_common_hands': self.get_most_common_hands(10),
            'win_rate_stats': self.get_win_rate_stats(),
            'adherence_by_result': self.get_adherence_by_result()
        }


class Exporter:
    """
    Exports hand history to various formats.
    """
    
    def __init__(self, logger: HandLogger):
        """
        Initialize exporter with a hand logger.
        
        Args:
            logger: HandLogger instance to export from
        """
        self._logger = logger
    
    def export_json(self, filepath: str, hands: List[HandLogEntry] = None):
        """
        Export hands to JSON file.
        
        Args:
            filepath: Output file path
            hands: List of hands to export (None for all)
        """
        if hands is None:
            hands = self._logger.get_hands()
        
        data = {
            'exported_at': datetime.now().isoformat(),
            'total_hands': len(hands),
            'hands': [h.to_dict() for h in hands]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def export_csv(self, filepath: str, hands: List[HandLogEntry] = None):
        """
        Export hands to CSV file.
        
        Args:
            filepath: Output file path
            hands: List of hands to export (None for all)
        """
        if hands is None:
            hands = self._logger.get_hands()
        
        if not hands:
            return
        
        fieldnames = [
            'timestamp', 'timestamp_iso', 'hand', 'position', 'spot',
            'recommended_action', 'confidence', 'user_action',
            'followed_recommendation', 'result', 'pot_size',
            'table_name', 'stakes', 'mode', 'board', 'equity'
        ]
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for hand in hands:
                row = hand.to_dict()
                writer.writerow(row)
    
    def export_summary_csv(self, filepath: str, analytics: Analytics):
        """
        Export analytics summary to CSV.
        
        Args:
            filepath: Output file path
            analytics: Analytics instance
        """
        summary = analytics.get_summary()
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(['Metric', 'Value'])
            
            # Total hands
            writer.writerow(['Total Hands', summary['total_hands']])
            
            # GTO adherence
            adherence = summary['gto_adherence']
            writer.writerow(['GTO Adherence Rate', f"{adherence['adherence_rate']:.1f}%"])
            writer.writerow(['Hands Followed', adherence['followed']])
            writer.writerow(['Hands Deviated', adherence['deviated']])
            
            # Win rate
            win_stats = summary['win_rate_stats']
            writer.writerow(['Win Rate', f"{win_stats['win_rate']:.1f}%"])
            writer.writerow(['Wins', win_stats['wins']])
            writer.writerow(['Losses', win_stats['losses']])
            writer.writerow(['Net', win_stats['net']])
            
            # Action distribution
            writer.writerow([])
            writer.writerow(['Action Distribution', ''])
            for action, pct in summary['action_distribution'].items():
                writer.writerow([action, f"{pct:.1f}%"])


# Global instances
_logger: Optional[HandLogger] = None
_analytics: Optional[Analytics] = None
_exporter: Optional[Exporter] = None


def get_logger(async_save: bool = True) -> HandLogger:
    """Get or create the global HandLogger instance."""
    global _logger
    if _logger is None:
        _logger = HandLogger(async_save=async_save)
    return _logger


def get_analytics() -> Analytics:
    """Get or create the global Analytics instance."""
    global _analytics, _logger
    if _logger is None:
        _logger = get_logger(async_save=True)
    if _analytics is None:
        _analytics = Analytics(_logger)
    return _analytics


def get_exporter() -> Exporter:
    """Get or create the global Exporter instance."""
    global _exporter, _logger
    if _logger is None:
        _logger = HandLogger()
    if _exporter is None:
        _exporter = Exporter(_logger)
    return _exporter
