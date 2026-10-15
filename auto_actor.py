"""
Humanized Autonomous Action Executor for Poker RTA.

Provides normalized client button coordinates, truncated Gaussian coordinate
jitter, cubic Bezier mouse trajectories with ease-in/ease-out dwell times,
randomized thinking delays, state deduplication, and emergency kill-switch.
"""

import math
import random
import re
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Any

# Optional macOS Quartz mouse/keyboard event dispatch
try:
    import Quartz
    HAS_QUARTZ = True
except ImportError:
    Quartz = None
    HAS_QUARTZ = False

# Optional pynput fallback
try:
    from pynput.mouse import Button as PynputButton, Controller as PynputMouseController
    from pynput.keyboard import Controller as PynputKeyboardController, Key as PynputKey
    HAS_PYNPUT = True
except ImportError:
    PynputButton = None
    PynputMouseController = None
    PynputKeyboardController = None
    PynputKey = None
    HAS_PYNPUT = False


BUTTON_REGIONS: Dict[str, Dict[str, Dict[str, float]]] = {
    'ggpoker': {
        'fold': {'x': 0.595, 'y': 0.88, 'w': 0.125, 'h': 0.105},
        'call': {'x': 0.735, 'y': 0.88, 'w': 0.125, 'h': 0.105},
        'check': {'x': 0.735, 'y': 0.88, 'w': 0.125, 'h': 0.105},
        'raise': {'x': 0.870, 'y': 0.88, 'w': 0.120, 'h': 0.105},
        'bet': {'x': 0.870, 'y': 0.88, 'w': 0.120, 'h': 0.105},
        'open_cards': {'x': 0.693, 'y': 0.869, 'w': 0.096, 'h': 0.050},
        'sit_in': {'x': 0.80, 'y': 0.88, 'w': 0.14, 'h': 0.06},
        'bet_input': {'x': 0.810, 'y': 0.822, 'w': 0.075, 'h': 0.048},
        'preset_33': {'x': 0.612, 'y': 0.822, 'w': 0.044, 'h': 0.048},
        'preset_50': {'x': 0.662, 'y': 0.822, 'w': 0.044, 'h': 0.048},
        'preset_75': {'x': 0.712, 'y': 0.822, 'w': 0.044, 'h': 0.048},
        'preset_pot': {'x': 0.761, 'y': 0.822, 'w': 0.044, 'h': 0.048},
        'preset_allin': {'x': 0.761, 'y': 0.822, 'w': 0.044, 'h': 0.048},
    },
    'pokerstars': {
        'fold': {'x': 0.485, 'y': 0.902, 'w': 0.16, 'h': 0.087},
        'call': {'x': 0.665, 'y': 0.902, 'w': 0.16, 'h': 0.087},
        'check': {'x': 0.665, 'y': 0.902, 'w': 0.16, 'h': 0.087},
        'raise': {'x': 0.835, 'y': 0.902, 'w': 0.155, 'h': 0.087},
        'bet': {'x': 0.835, 'y': 0.902, 'w': 0.155, 'h': 0.087},
        'sit_in': {'x': 0.80, 'y': 0.88, 'w': 0.14, 'h': 0.06},
        'bet_input': {'x': 0.835, 'y': 0.835, 'w': 0.14, 'h': 0.05},
        'preset_33': {'x': 0.55, 'y': 0.835, 'w': 0.065, 'h': 0.045},
        'preset_50': {'x': 0.62, 'y': 0.835, 'w': 0.065, 'h': 0.045},
        'preset_75': {'x': 0.69, 'y': 0.835, 'w': 0.065, 'h': 0.045},
        'preset_pot': {'x': 0.76, 'y': 0.835, 'w': 0.065, 'h': 0.045},
        'preset_allin': {'x': 0.91, 'y': 0.835, 'w': 0.075, 'h': 0.045},
    },
}


@dataclass
class HumanizedConfig:
    """Configuration for humanized autonomous clicking."""
    enabled: bool = False
    min_delay: float = 0.8
    max_delay: float = 2.6
    jitter_sigma: float = 0.18
    bezier_steps: int = 18
    enter_bet_sizing: bool = True
    dry_run: bool = False
    retry_cooldown: float = 3.0


class AutoActor:
    """Executes recommended poker actions with humanized timing and trajectories."""

    def __init__(self, config: Optional[HumanizedConfig] = None, rng: Optional[random.Random] = None):
        self.config = config or HumanizedConfig()
        self._rng = rng or random.Random()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._in_flight_key: Optional[Tuple[Any, ...]] = None
        self._last_acted_key: Optional[Tuple[Any, ...]] = None
        self._last_acted_time: float = 0.0
        self._active_thread: Optional[threading.Thread] = None
        self._action_history: List[Dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        with self._lock:
            self.config.enabled = bool(value)
            if not value:
                self._stop_event.set()
            else:
                self._stop_event.clear()

    def emergency_stop(self) -> None:
        """Immediately cancel any pending delayed action and disarm autonomous mode."""
        with self._lock:
            self.config.enabled = False
            self._stop_event.set()

    def disarm(self) -> None:
        """Alias for emergency_stop."""
        self.emergency_stop()

    def reset_deduplication(self) -> None:
        """Clear the last acted state key."""
        with self._lock:
            self._in_flight_key = None
            self._last_acted_key = None
            self._last_acted_time = 0.0

    def get_action_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._action_history)

    @staticmethod
    def normalize_action_category(
        recommended_action: Optional[str],
        call_amount: Optional[float] = None,
        raise_available: bool = True,
    ) -> Optional[str]:
        """Map engine recommendation strings to 'fold', 'call', 'raise', 'open_cards', or 'sit_in'.

        If recommended_action is 'FOLD' when call_amount == 0, remaps safely to 'call' (check).
        If recommended_action is a raise/bet when raise_available is False (only Fold + Call or Check
        buttons exist on screen), remaps safely to 'call' (Slot 2 Call / Check button).
        """
        if not recommended_action or not isinstance(recommended_action, str):
            return None
        act = recommended_action.strip().upper()
        if not act:
            return None

        if act in ('OPEN_CARDS', 'REVEAL', 'PEEL') or 'OPEN_CARDS' in act:
            return 'open_cards'
        if act in ('SIT_IN', 'IM_BACK', "I'M BACK", 'SIT IN') or 'SIT_IN' in act or 'IM_BACK' in act:
            return 'sit_in'
        if any(tok in act for tok in ('RAISE', 'BET', '3-BET', '4-BET', '5-BET', 'SHOVE', 'ALL-IN', 'ALL IN', 'SQUEEZE')):
            return 'call' if not raise_available else 'raise'
        if any(tok in act for tok in ('CALL', 'CHECK')):
            return 'call'
        if 'FOLD' in act:
            if call_amount is not None and call_amount <= 0:
                return 'call'
            return 'fold'
        return None

    def sample_thinking_delay(self, action: str, street: str = 'preflop') -> float:
        """Sample a humanized thinking delay within [min_delay, max_delay]."""
        lo = max(0.0, float(self.config.min_delay))
        hi = max(lo, float(self.config.max_delay))
        if hi <= lo:
            return lo

        span = hi - lo
        act_upper = (action or '').upper()
        street_lower = (street or 'preflop').lower()

        # Weight complexity: raises/3-bets/postflop decisions take slightly longer on average
        is_complex_action = any(k in act_upper for k in ('RAISE', 'BET', '3-BET', '4-BET', '5-BET', 'SHOVE', 'SQUEEZE'))
        is_postflop = street_lower not in ('preflop', '')

        if is_complex_action and is_postflop:
            center_ratio = 0.62
        elif is_complex_action or is_postflop:
            center_ratio = 0.52
        elif 'CALL' in act_upper or 'CHECK' in act_upper:
            center_ratio = 0.42
        else:
            center_ratio = 0.32

        mean = lo + span * center_ratio
        sigma = max(0.05, span * 0.22)

        for _ in range(12):
            sample = self._rng.gauss(mean, sigma)
            if lo <= sample <= hi:
                return round(sample, 4)
        return round(min(hi, max(lo, sample)), 4)

    def sample_target_point(self, window_bounds: Tuple[int, int, int, int], region: Dict[str, float]) -> Tuple[int, int]:
        """Convert normalized (x, y, w, h) to screen coordinates (sx, sy) with truncated Gaussian jitter
        inside the safe inner 70% of the button box.
        """
        wx, wy, ww, wh = window_bounds
        bx = wx + region['x'] * ww
        by = wy + region['y'] * wh
        bw = max(2.0, region['w'] * ww)
        bh = max(2.0, region['h'] * wh)

        cx = bx + bw * 0.5
        cy = by + bh * 0.5

        # Inner 70% safe bounds: [center - 0.35 * size, center + 0.35 * size]
        half_safe_w = bw * 0.35
        half_safe_h = bh * 0.35
        sigma = max(0.01, float(self.config.jitter_sigma))

        dx = self._rng.gauss(0.0, bw * sigma)
        dy = self._rng.gauss(0.0, bh * sigma)
        dx = max(-half_safe_w, min(half_safe_w, dx))
        dy = max(-half_safe_h, min(half_safe_h, dy))

        sx = int(round(cx + dx))
        sy = int(round(cy + dy))

        # Strictly clamp within button bounds
        min_x = int(math.ceil(bx + bw * 0.15))
        max_x = int(math.floor(bx + bw * 0.85))
        min_y = int(math.ceil(by + bh * 0.15))
        max_y = int(math.floor(by + bh * 0.85))
        if min_x <= max_x:
            sx = max(min_x, min(max_x, sx))
        if min_y <= max_y:
            sy = max(min_y, min(max_y, sy))
        return sx, sy

    def generate_bezier_path(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        steps: Optional[int] = None,
    ) -> List[Tuple[int, int, float]]:
        """Generate a cubic Bezier trajectory from start to end with per-step dwell times."""
        num_steps = max(2, int(steps if steps is not None else self.config.bezier_steps))
        x0, y0 = float(start[0]), float(start[1])
        x3, y3 = float(end[0]), float(end[1])

        dx = x3 - x0
        dy = y3 - y0
        dist = math.hypot(dx, dy)

        # Perpendicular vector for natural arc curvature
        if dist > 1e-3:
            nx = -dy / dist
            ny = dx / dist
        else:
            nx, ny = 0.0, 1.0

        arc_scale = min(120.0, max(6.0, dist * 0.18))
        offset1 = self._rng.uniform(-arc_scale, arc_scale)
        offset2 = self._rng.uniform(-arc_scale * 0.6, arc_scale * 0.6)

        x1 = x0 + dx * self._rng.uniform(0.25, 0.40) + nx * offset1
        y1 = y0 + dy * self._rng.uniform(0.25, 0.40) + ny * offset1
        x2 = x0 + dx * self._rng.uniform(0.65, 0.82) + nx * offset2
        y2 = y0 + dy * self._rng.uniform(0.65, 0.82) + ny * offset2

        total_move_time = min(0.32, max(0.08, 0.06 + dist * 0.00025))
        path: List[Tuple[int, int, float]] = []

        for i in range(num_steps + 1):
            u = i / num_steps
            # Smoothstep ease-in / ease-out parameter
            t = u * u * (3.0 - 2.0 * u)
            omt = 1.0 - t
            bx = (omt ** 3) * x0 + 3 * (omt ** 2) * t * x1 + 3 * omt * (t ** 2) * x2 + (t ** 3) * x3
            by = (omt ** 3) * y0 + 3 * (omt ** 2) * t * y1 + 3 * omt * (t ** 2) * y2 + (t ** 3) * y3

            # Dwell time is slightly longer at the start and end (ease-in / ease-out)
            edge_weight = 1.35 - 0.7 * math.sin(math.pi * u)
            dwell = (total_move_time / (num_steps + 1)) * edge_weight
            path.append((int(round(bx)), int(round(by)), round(max(0.001, dwell), 5)))

        path[0] = (int(start[0]), int(start[1]), path[0][2])
        path[-1] = (int(end[0]), int(end[1]), path[-1][2])
        return path

    @staticmethod
    def extract_numeric_sizing(sizing: Optional[Any]) -> Optional[str]:
        """Extract a clean numeric bet/raise sizing string only when an explicit amount is given.

        Rejects descriptive range/multiplier strings such as 'Open raise ~2.2-2.5bb',
        '~3x open', or '66% pot' so bogus small numbers are never typed into chip inputs.
        """
        if sizing is None:
            return None
        if isinstance(sizing, (int, float)):
            if not math.isfinite(sizing) or sizing <= 0:
                return None
            return f"{sizing:.2f}".rstrip('0').rstrip('.') if sizing % 1 else str(int(sizing))
        if isinstance(sizing, str):
            raw = sizing.strip()
            if not raw:
                return None
            if '%' in raw or '~' in raw or '-' in raw:
                return None
            if re.search(r'\b\d+(?:\.\d+)?\s*(?:x|bb)\b', raw, re.IGNORECASE):
                return None
            m = re.fullmatch(r'[$£€]?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?\s*(?:chips?)?', raw, re.IGNORECASE)
            if m:
                val = float(raw.replace(',', '').lstrip('$£€ ').split()[0])
                if val > 0:
                    return f"{val:.2f}".rstrip('0').rstrip('.') if val % 1 else str(int(val))
        return None

    @staticmethod
    def extract_preset_button(sizing: Optional[Any]) -> Optional[str]:
        """Map a descriptive postflop sizing string (e.g. '33% pot', '75% pot', 'All-in (low SPR)')
        to a client preset button region key ('preset_33', 'preset_50', 'preset_75', 'preset_pot', 'preset_allin').
        """
        if not isinstance(sizing, str):
            return None
        raw = sizing.strip().lower()
        if not raw:
            return None
        if any(tok in raw for tok in ('all-in', 'all in', 'low spr', 'shove', 'jam')):
            return 'preset_allin'
        m = re.search(r'(\d+(?:\.\d+)?)\s*%\s*pot', raw)
        if m:
            pct = float(m.group(1))
            if pct <= 40:
                return 'preset_33'
            if pct <= 58:
                return 'preset_50'
            if pct <= 85:
                return 'preset_75'
            return 'preset_pot'
        if raw in ('pot', '1x pot', '1.0x pot', '100% pot'):
            return 'preset_pot'
        return None

    @staticmethod
    def resolve_chip_sizing(
        sizing: Optional[Any],
        pot_size: Optional[float] = None,
        call_amount: Optional[float] = None,
        big_blind: Optional[float] = None,
    ) -> Optional[str]:
        """Resolve a numeric or descriptive sizing string into a concrete chip amount string
        when contextual table amounts (pot_size, call_amount, or big_blind) are provided.
        """
        direct = AutoActor.extract_numeric_sizing(sizing)
        if direct is not None:
            return direct
        if not isinstance(sizing, str):
            return None
        raw = sizing.strip()
        if not raw:
            return None

        def _fmt(v: float) -> Optional[str]:
            if not math.isfinite(v) or v <= 0:
                return None
            return f"{v:.2f}".rstrip('0').rstrip('.') if round(v, 2) % 1 else str(int(round(v)))

        if big_blind is not None and big_blind > 0:
            m_range = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*bb\b', raw, re.IGNORECASE)
            if m_range:
                mid = (float(m_range.group(1)) + float(m_range.group(2))) * 0.5
                return _fmt(mid * big_blind)
            m_bb = re.search(r'(\d+(?:\.\d+)?)\s*bb\b', raw, re.IGNORECASE)
            if m_bb:
                return _fmt(float(m_bb.group(1)) * big_blind)

        if call_amount is not None and call_amount > 0:
            m_x = re.search(r'(\d+(?:\.\d+)?)\s*x\b', raw, re.IGNORECASE)
            if m_x:
                return _fmt(float(m_x.group(1)) * call_amount)

        if pot_size is not None and pot_size > 0:
            m_pot = re.search(r'(\d+(?:\.\d+)?)\s*%\s*pot\b', raw, re.IGNORECASE)
            if m_pot:
                pct = float(m_pot.group(1)) / 100.0
                base_pot = pot_size + (call_amount if (call_amount is not None and call_amount > 0) else 0.0)
                return _fmt(pct * base_pot)

        return None

    def _get_cursor_position(self, fallback: Tuple[int, int]) -> Tuple[int, int]:
        if HAS_QUARTZ and not self.config.dry_run:
            try:
                ev = Quartz.CGEventCreate(None)
                loc = Quartz.CGEventGetLocation(ev)
                return int(round(loc.x)), int(round(loc.y))
            except Exception:
                pass
        if HAS_PYNPUT and not self.config.dry_run:
            try:
                mouse = PynputMouseController()
                pos = mouse.position
                return int(round(pos[0])), int(round(pos[1]))
            except Exception:
                pass
        return fallback

    def _activate_poker_app(self, client: str = 'ggpoker') -> None:
        """Bring the poker client window to the foreground on macOS so clicks are not swallowed by window focus."""
        if self.config.dry_run:
            return
        try:
            import AppKit
            target_name = 'GGPoker' if (client or 'ggpoker').lower() == 'ggpoker' else 'PokerStars'
            ws = AppKit.NSWorkspace.sharedWorkspace()
            for app in ws.runningApplications():
                name = app.localizedName() or ''
                if target_name.lower() in name.lower():
                    if not app.isActive():
                        app.activateWithOptions_(2)
                        time.sleep(0.04)
                    break
        except Exception:
            pass

    def _dispatch_mouse_path_and_click(
        self,
        path: List[Tuple[int, int, float]],
        stop_event: threading.Event,
        ignore_enabled: bool = False,
    ) -> bool:
        """Move cursor along path and perform left click at the final coordinate."""
        if self.config.dry_run:
            return True

        for x, y, dwell in path:
            if stop_event.is_set() or (not ignore_enabled and not self.config.enabled):
                return False
            self._move_cursor(x, y)
            if stop_event.wait(dwell):
                return False

        if stop_event.is_set() or (not ignore_enabled and not self.config.enabled):
            return False

        end_x, end_y, _ = path[-1]
        self._click_at(end_x, end_y)
        return True

    def _move_cursor(self, x: int, y: int) -> None:
        if self.config.dry_run:
            return
        if HAS_QUARTZ:
            try:
                move_ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventMouseMoved, (float(x), float(y)), Quartz.kCGMouseButtonLeft
                )
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, move_ev)
                return
            except Exception:
                pass
        if HAS_PYNPUT:
            try:
                mouse = PynputMouseController()
                mouse.position = (x, y)
            except Exception:
                pass

    def _click_at(self, x: int, y: int) -> None:
        if self.config.dry_run:
            return
        if HAS_QUARTZ:
            try:
                pt = (float(x), float(y))
                move_ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventMouseMoved, pt, Quartz.kCGMouseButtonLeft
                )
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, move_ev)
                time.sleep(0.01)
                down_ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft
                )
                up_ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft
                )
                if hasattr(Quartz, 'CGEventSetIntegerValueField') and hasattr(Quartz, 'kCGMouseEventClickState'):
                    Quartz.CGEventSetIntegerValueField(down_ev, Quartz.kCGMouseEventClickState, 1)
                    Quartz.CGEventSetIntegerValueField(up_ev, Quartz.kCGMouseEventClickState, 1)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_ev)
                time.sleep(self._rng.uniform(0.035, 0.075))
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_ev)
                return
            except Exception:
                pass
        if HAS_PYNPUT:
            try:
                mouse = PynputMouseController()
                mouse.position = (x, y)
                mouse.press(PynputButton.left)
                time.sleep(self._rng.uniform(0.035, 0.075))
                mouse.release(PynputButton.left)
            except Exception:
                pass

    _QUARTZ_KEYCODES: Dict[str, int] = {
        '0': 29, '1': 18, '2': 19, '3': 20, '4': 21,
        '5': 23, '6': 22, '7': 26, '8': 28, '9': 25,
        '.': 47,
    }

    def _type_text(self, text: str, stop_event: threading.Event) -> bool:
        if self.config.dry_run:
            return True
        if HAS_QUARTZ and hasattr(Quartz, 'CGEventCreateKeyboardEvent'):
            try:
                # Backspace existing input (virtual keycode 51 = kVK_Delete)
                for _ in range(6):
                    if stop_event.is_set() or not self.config.enabled:
                        return False
                    bs_down = Quartz.CGEventCreateKeyboardEvent(None, 51, True)
                    bs_up = Quartz.CGEventCreateKeyboardEvent(None, 51, False)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, bs_down)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, bs_up)
                    time.sleep(0.015)
                for ch in text:
                    if stop_event.is_set() or not self.config.enabled:
                        return False
                    keycode = self._QUARTZ_KEYCODES.get(ch, 0)
                    kd = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
                    ku = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
                    if hasattr(Quartz, 'CGEventKeyboardSetUnicodeString'):
                        Quartz.CGEventKeyboardSetUnicodeString(kd, len(ch), ch)
                        Quartz.CGEventKeyboardSetUnicodeString(ku, len(ch), ch)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, kd)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ku)
                    time.sleep(self._rng.uniform(0.03, 0.07))
                return True
            except Exception:
                pass
        if HAS_PYNPUT:
            try:
                kb = PynputKeyboardController()
                # Select existing text or backspace a few times
                for _ in range(6):
                    if stop_event.is_set() or not self.config.enabled:
                        return False
                    kb.press(PynputKey.backspace)
                    kb.release(PynputKey.backspace)
                    time.sleep(0.015)
                for ch in text:
                    if stop_event.is_set() or not self.config.enabled:
                        return False
                    kb.press(ch)
                    kb.release(ch)
                    time.sleep(self._rng.uniform(0.03, 0.07))
                return True
            except Exception:
                return False
        return True

    def execute_action(
        self,
        recommended_action: str,
        client: str = 'ggpoker',
        window_bounds: Tuple[int, int, int, int] = (0, 0, 1000, 700),
        table_id: Any = None,
        hand: Optional[str] = None,
        street: str = 'preflop',
        board: Optional[str] = None,
        call_amount: Optional[float] = None,
        action_buttons_visible: bool = False,
        sizing: Optional[Any] = None,
        pot_size: Optional[float] = None,
        big_blind: Optional[float] = None,
        raise_available: bool = True,
        presets_available: bool = True,
        state_validator: Optional[Callable[[], bool]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        blocking: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Validate, delay, move along a Bezier trajectory, and click the action button.

        Returns the execution summary dict when blocking=True (or if rejected synchronously),
        or schedules execution on a background daemon thread when blocking=False.
        """
        if not self.config.enabled:
            return {'status': 'disabled', 'executed': False}

        # Live action turn check: require either call_amount is not None or explicit action_buttons_visible
        if call_amount is None and not action_buttons_visible:
            return {'status': 'no_action_buttons', 'executed': False}

        category = self.normalize_action_category(
            recommended_action,
            call_amount=call_amount,
            raise_available=raise_available,
        )
        if not category:
            return {'status': 'invalid_action', 'executed': False}

        client_key = (client or 'ggpoker').lower()
        regions = BUTTON_REGIONS.get(client_key, BUTTON_REGIONS['ggpoker'])
        if category not in regions:
            return {'status': 'unknown_region', 'executed': False}

        state_key = (table_id, hand, street, board or '', call_amount, category)
        now = time.monotonic()
        cooldown = max(0.0, float(getattr(self.config, 'retry_cooldown', 3.0)))
        with self._lock:
            if self._in_flight_key == state_key:
                return {'status': 'deduplicated', 'executed': False, 'state_key': state_key}
            if self._last_acted_key == state_key and (now - self._last_acted_time) < cooldown:
                return {'status': 'deduplicated', 'executed': False, 'state_key': state_key}
            # Reserve the in-flight key immediately so concurrent polls don't double-schedule
            self._in_flight_key = state_key
            self._stop_event.clear()
            stop_event = self._stop_event

        def _clear_in_flight() -> None:
            with self._lock:
                if self._in_flight_key == state_key:
                    self._in_flight_key = None

        def _run() -> Dict[str, Any]:
            delay = self.sample_thinking_delay(recommended_action, street=street)
            # Wait in small slices or via stop_event.wait so emergency_stop is instantaneous
            if delay > 0 and stop_event.wait(delay):
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': recommended_action, 'category': category}
                if on_complete:
                    on_complete(res)
                return res

            if not self.config.enabled or stop_event.is_set():
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': recommended_action, 'category': category}
                if on_complete:
                    on_complete(res)
                return res

            if state_validator is not None:
                try:
                    if not state_validator():
                        _clear_in_flight()
                        res = {'status': 'state_changed', 'executed': False, 'action': recommended_action, 'category': category}
                        if on_complete:
                            on_complete(res)
                        return res
                except Exception:
                    pass

            self._activate_poker_app(client_key)
            wx, wy, ww, wh = window_bounds
            start_pt = self._get_cursor_position((int(wx + ww * 0.5), int(wy + wh * 0.5)))

            sizing_text = None
            sizing_target = None
            preset_button = None
            preset_target = None
            if category == 'raise' and self.config.enter_bet_sizing:
                if pot_size is not None or big_blind is not None:
                    sizing_text = self.resolve_chip_sizing(
                        sizing, pot_size=pot_size, call_amount=call_amount, big_blind=big_blind
                    )
                else:
                    sizing_text = self.extract_numeric_sizing(sizing)

                if sizing_text and 'bet_input' in regions:
                    sizing_target = self.sample_target_point(window_bounds, regions['bet_input'])
                    sizing_path = self.generate_bezier_path(start_pt, sizing_target)
                    if not self._dispatch_mouse_path_and_click(sizing_path, stop_event):
                        _clear_in_flight()
                        res = {'status': 'cancelled', 'executed': False, 'action': recommended_action, 'category': category}
                        if on_complete:
                            on_complete(res)
                        return res
                    if not self._type_text(sizing_text, stop_event):
                        _clear_in_flight()
                        res = {'status': 'cancelled', 'executed': False, 'action': recommended_action, 'category': category}
                        if on_complete:
                            on_complete(res)
                        return res
                    start_pt = sizing_target
                elif presets_available:
                    preset_button = self.extract_preset_button(sizing)
                    if preset_button and preset_button in regions:
                        preset_target = self.sample_target_point(window_bounds, regions[preset_button])
                        preset_path = self.generate_bezier_path(start_pt, preset_target)
                        if not self._dispatch_mouse_path_and_click(preset_path, stop_event):
                            _clear_in_flight()
                            res = {'status': 'cancelled', 'executed': False, 'action': recommended_action, 'category': category}
                            if on_complete:
                                on_complete(res)
                            return res
                        start_pt = preset_target

            target_pt = self.sample_target_point(window_bounds, regions[category])
            path = self.generate_bezier_path(start_pt, target_pt)
            ok = self._dispatch_mouse_path_and_click(path, stop_event)
            if not ok:
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': recommended_action, 'category': category}
                if on_complete:
                    on_complete(res)
                return res

            res = {
                'status': 'dry_run' if self.config.dry_run else 'clicked',
                'executed': True,
                'dry_run': self.config.dry_run,
                'action': recommended_action,
                'category': category,
                'client': client_key,
                'target': target_pt,
                'sizing_typed': sizing_text,
                'sizing_target': sizing_target,
                'preset_button': preset_button,
                'preset_target': preset_target,
                'delay': delay,
                'path': path,
                'state_key': state_key,
            }
            with self._lock:
                if self._in_flight_key == state_key:
                    self._in_flight_key = None
                self._last_acted_key = state_key
                self._last_acted_time = time.monotonic()
                self._action_history.append(res)
            if on_complete:
                on_complete(res)
            return res

        if blocking:
            return _run()
        t = threading.Thread(target=_run, daemon=True)
        with self._lock:
            self._active_thread = t
        t.start()
        return {'status': 'scheduled', 'executed': False, 'state_key': state_key}

    def execute_open_cards(
        self,
        client: str = 'ggpoker',
        window_bounds: Tuple[int, int, int, int] = (0, 0, 1000, 700),
        table_id: Any = None,
        force: bool = False,
        state_validator: Optional[Callable[[], bool]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        blocking: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Click GGPoker's green 'Open' card-squeeze button to reveal Hero's hole cards."""
        if not self.config.enabled and not force:
            return {'status': 'disabled', 'executed': False}

        client_key = (client or 'ggpoker').lower()
        regions = BUTTON_REGIONS.get(client_key, BUTTON_REGIONS['ggpoker'])
        if 'open_cards' not in regions:
            return {'status': 'unknown_region', 'executed': False}

        state_key = (table_id, '__open_cards__', 'preflop', '', 0.0, 'open_cards')
        now = time.monotonic()
        open_cooldown = min(1.2, max(0.0, float(getattr(self.config, 'retry_cooldown', 3.0))))
        with self._lock:
            if self._in_flight_key == state_key:
                return {'status': 'deduplicated', 'executed': False, 'state_key': state_key}
            if self._last_acted_key == state_key and (now - self._last_acted_time) < open_cooldown:
                return {'status': 'deduplicated', 'executed': False, 'state_key': state_key}
            self._in_flight_key = state_key
            self._stop_event.clear()
            stop_event = self._stop_event

        def _clear_in_flight() -> None:
            with self._lock:
                if self._in_flight_key == state_key:
                    self._in_flight_key = None

        def _run() -> Dict[str, Any]:
            delay = self._rng.uniform(0.12, 0.28) if (self.config.min_delay > 0 or self.config.max_delay > 0) else 0.0
            if delay > 0 and stop_event.wait(delay):
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': 'OPEN_CARDS', 'category': 'open_cards'}
                if on_complete:
                    on_complete(res)
                return res

            if (not self.config.enabled and not force) or stop_event.is_set():
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': 'OPEN_CARDS', 'category': 'open_cards'}
                if on_complete:
                    on_complete(res)
                return res

            if state_validator is not None:
                try:
                    if not state_validator():
                        _clear_in_flight()
                        res = {'status': 'state_changed', 'executed': False, 'action': 'OPEN_CARDS', 'category': 'open_cards'}
                        if on_complete:
                            on_complete(res)
                        return res
                except Exception:
                    pass

            self._activate_poker_app(client_key)
            wx, wy, ww, wh = window_bounds
            start_pt = self._get_cursor_position((int(wx + ww * 0.5), int(wy + wh * 0.5)))
            target_pt = self.sample_target_point(window_bounds, regions['open_cards'])
            path = self.generate_bezier_path(start_pt, target_pt)
            ok = self._dispatch_mouse_path_and_click(path, stop_event, ignore_enabled=force)
            if not ok:
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': 'OPEN_CARDS', 'category': 'open_cards'}
                if on_complete:
                    on_complete(res)
                return res

            res = {
                'status': 'dry_run' if self.config.dry_run else 'clicked',
                'executed': True,
                'dry_run': self.config.dry_run,
                'action': 'OPEN_CARDS',
                'category': 'open_cards',
                'client': client_key,
                'target': target_pt,
                'delay': delay,
                'path': path,
                'state_key': state_key,
            }
            with self._lock:
                if self._in_flight_key == state_key:
                    self._in_flight_key = None
                self._last_acted_key = state_key
                self._last_acted_time = time.monotonic()
                self._action_history.append(res)
            if on_complete:
                on_complete(res)
            return res

        if blocking:
            return _run()
        t = threading.Thread(target=_run, daemon=True)
        with self._lock:
            self._active_thread = t
        t.start()
        return {'status': 'scheduled', 'executed': False, 'state_key': state_key}

    def execute_sit_in(
        self,
        client: str = 'ggpoker',
        window_bounds: Tuple[int, int, int, int] = (0, 0, 1000, 700),
        table_id: Any = None,
        force: bool = False,
        state_validator: Optional[Callable[[], bool]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        blocking: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Click GGPoker's 'I'm Back' / 'Sit In' button when Hero is sitting out."""
        if not self.config.enabled and not force:
            return {'status': 'disabled', 'executed': False}

        client_key = (client or 'ggpoker').lower()
        regions = BUTTON_REGIONS.get(client_key, BUTTON_REGIONS['ggpoker'])
        if 'sit_in' not in regions:
            return {'status': 'unknown_region', 'executed': False}

        state_key = (table_id, '__sit_in__', 'preflop', '', 0.0, 'sit_in')
        now = time.monotonic()
        sit_cooldown = min(2.0, max(0.0, float(getattr(self.config, 'retry_cooldown', 3.0))))
        with self._lock:
            if self._in_flight_key == state_key:
                return {'status': 'deduplicated', 'executed': False, 'state_key': state_key}
            if self._last_acted_key == state_key and (now - self._last_acted_time) < sit_cooldown:
                return {'status': 'deduplicated', 'executed': False, 'state_key': state_key}
            self._in_flight_key = state_key
            self._stop_event.clear()
            stop_event = self._stop_event

        def _clear_in_flight() -> None:
            with self._lock:
                if self._in_flight_key == state_key:
                    self._in_flight_key = None

        def _run() -> Dict[str, Any]:
            delay = self._rng.uniform(0.15, 0.35) if (self.config.min_delay > 0 or self.config.max_delay > 0) else 0.0
            if delay > 0 and stop_event.wait(delay):
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': 'SIT_IN', 'category': 'sit_in'}
                if on_complete:
                    on_complete(res)
                return res

            if (not self.config.enabled and not force) or stop_event.is_set():
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': 'SIT_IN', 'category': 'sit_in'}
                if on_complete:
                    on_complete(res)
                return res

            if state_validator is not None:
                try:
                    if not state_validator():
                        _clear_in_flight()
                        res = {'status': 'state_changed', 'executed': False, 'action': 'SIT_IN', 'category': 'sit_in'}
                        if on_complete:
                            on_complete(res)
                        return res
                except Exception:
                    pass

            self._activate_poker_app(client_key)
            wx, wy, ww, wh = window_bounds
            start_pt = self._get_cursor_position((int(wx + ww * 0.5), int(wy + wh * 0.5)))
            target_pt = self.sample_target_point(window_bounds, regions['sit_in'])
            path = self.generate_bezier_path(start_pt, target_pt)
            ok = self._dispatch_mouse_path_and_click(path, stop_event, ignore_enabled=force)
            if not ok:
                _clear_in_flight()
                res = {'status': 'cancelled', 'executed': False, 'action': 'SIT_IN', 'category': 'sit_in'}
                if on_complete:
                    on_complete(res)
                return res

            res = {
                'status': 'dry_run' if self.config.dry_run else 'clicked',
                'executed': True,
                'dry_run': self.config.dry_run,
                'action': 'SIT_IN',
                'category': 'sit_in',
                'client': client_key,
                'target': target_pt,
                'delay': delay,
                'path': path,
                'state_key': state_key,
            }
            with self._lock:
                if self._in_flight_key == state_key:
                    self._in_flight_key = None
                self._last_acted_key = state_key
                self._last_acted_time = time.monotonic()
                self._action_history.append(res)
            if on_complete:
                on_complete(res)
            return res

        if blocking:
            return _run()
        t = threading.Thread(target=_run, daemon=True)
        with self._lock:
            self._active_thread = t
        t.start()
        return {'status': 'scheduled', 'executed': False, 'state_key': state_key}

