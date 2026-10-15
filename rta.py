#!/usr/bin/env python3
"""
Undetectable Poker RTA — GTO preflop lookup overlay with optional OCR.

Design for undetectability:
  - No memory reading, no injection into the poker client, no network calls.
  - Manual mode: you type your hand + spot; zero client interaction.
  - Auto (OCR) mode: screenshots the GGPoker window with the standard
    macOS screencapture API (indistinguishable from any screen-sharing app)
    and reads your hole cards automatically.

Usage:
  python3 rta.py

Controls (in the app):
  Cmd/Ctrl+Space (global, if pynput installed) : show/hide overlay
  Esc                                          : hide overlay
  Type hand like "AKs", "JJ", "T9o"            : instant advice
  Click position buttons / spot buttons        : set the spot
  Auto checkbox                                : OCR your cards from GGPoker
  Preflop/Postflop toggle                      : switch between modes
"""

import sys
import os
import time
import threading
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

import ranges
from auto_actor import AutoActor, HumanizedConfig
from detection_state import HandConfirmation, validate_exact_cards
from table_context import PreflopTracker, PostflopTracker, convert_amount, format_amount

# Postflop modules (optional)
try:
    from equity import get_equity_percentage
    from outs import get_outs_simple
    from postflop import get_postflop_advice, spot_to_opponent_range
    HAS_POSTFLOP = True
except ImportError:
    HAS_POSTFLOP = False
    spot_to_opponent_range = None

# Strategy module
try:
    from strategy import StrategyManager, StrategyProfile, get_strategy_manager
    HAS_STRATEGY = True
except ImportError:
    HAS_STRATEGY = False
    StrategyManager = None
    StrategyProfile = None

# OCR module for performance features
try:
    import ocr as ocr_module
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# Multi-table support
try:
    from multitable import get_multitable_manager, MultiTableManager, TableState
    HAS_MULTITABLE = True
except ImportError:
    HAS_MULTITABLE = False
    MultiTableManager = None
    TableState = None

# Analytics module
try:
    from analytics import get_logger, get_analytics, get_exporter, HandLogEntry
    HAS_ANALYTICS = True
except ImportError:
    HAS_ANALYTICS = False
    HandLogEntry = None

# Sound notification (optional)
try:
    import playsound
    HAS_PLAYSOUND = True
except ImportError:
    HAS_PLAYSOUND = False

# ---------------------------------------------------------------------------
# Global hotkey (optional)
# ---------------------------------------------------------------------------

GLOBAL_HOTKEY_HINT = "Cmd+Space / Ctrl+Space toggles this window (if pynput installed)"


class RTAApp:
    # Colors
    BG = "#0d1520"
    FG = "#eef4fc"
    ACCENT = "#3b82f6"
    RAISE_C = "#10b981"     # emerald
    CALL_C = "#3b82f6"      # electric blue
    FOLD_C = "#1e2d42"      # muted dark
    GRID_EMPTY = "#1a2535"

    OCR_POLL_SECONDS = 1.0

    def __init__(self, root: tk.Tk):
        import queue
        tk._default_root = root
        self.root = root
        self._ui_queue = queue.Queue()
        self._ui_queue_after = None
        self.spot = {"kind": "open", "pos": "BTN", "vs": None}
        self.hand = None
        self.auto_ocr = False
        self._ocr_thread = None
        self._ocr_stop = threading.Event()
        self._last_ocr_hand = None
        self._exact_cards = None
        self._auto_hand_current = False
        self._context_cards = None
        self._manual_position = self._manual_spot = False
        self._last_frame_time = 0
        self._ocr_generation = 0
        self._hand_confirmation = HandConfirmation()
        self._preflop_tracker = PreflopTracker()
        self._postflop_tracker = PostflopTracker()
        self._preflop_context = {}
        self._postflop_context = {}
        self._big_blind = None
        self._big_blind_override = None
        self._table_units = 'chips'
        self._amount_units = 'chips'
        self.mode = "preflop"  # preflop or postflop
        self._ocr_status = "ready"  # ready, watching, detected, error, retrying
        self._ocr_status_message = "Ready"
        self._position_info = None  # Store detected position info
        self._current_action = None  # Current recommended action
        self._current_confidence = 0.0  # Current confidence percentage
        self._last_logged_hand = None  # Track last logged hand to avoid duplicates
        self._last_logged_key = None   # Track (mode, hand, board) to deduplicate within window
        self._last_log_timestamp = 0
        self._last_logged_entry = None
        self._last_logged_entry_ts = None
        self._postflop_debounce_after = None
        self._postflop_calc_generation = 0
        self._async_postflop = False
        self._mixed_rng_cache = {}

        # Postflop auto-detection
        self._postflop_auto_detect = False
        self._postflop_detect_thread = None
        self._postflop_detect_stop = threading.Event()
        self._last_detected_board = None
        self._last_detected_pot = None
        self._last_detected_call = None
        self._detection_status = "ready"
        self._detection_status_message = "Ready"
        self._active_opponents = 1
        self._auto_switched_to_postflop = False

        # Load configuration
        self._config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
        self._config = self._load_config()
        
        # Strategy manager
        self._strategy_manager = StrategyManager() if HAS_STRATEGY else None
        if self._strategy_manager:
            try:
                self._strategy_manager.set_profile(StrategyProfile(self._config['profile']))
            except ValueError:
                self._config['profile'] = 'ABC'
            self._strategy_manager.set_stack_depth(self._config['stack_depth'])
            self._strategy_manager.set_aggression_factor(self._config['aggression_factor'])
            self._config['stack_depth'] = self._strategy_manager.config.stack_depth
            self._config['aggression_factor'] = self._strategy_manager.config.aggression_factor
        
        # Multi-table manager
        self._multitable_manager = get_multitable_manager() if HAS_MULTITABLE else None
        self._current_table_id = None
        self._table_change_callback_id = None
        
        # Analytics
        self._logger = get_logger() if HAS_ANALYTICS else None
        self._analytics = get_analytics() if HAS_ANALYTICS else None
        self._exporter = get_exporter() if HAS_ANALYTICS else None
        
        # UI state variables
        self._window_opacity = self._config.get('window_opacity', 90)
        self._sound_enabled = self._config.get('enable_sound_notifications', True)
        self._minimize_to_tray = self._config.get('minimize_to_tray', False)
        self._show_confidence = self._config.get('show_confidence_percentages', True)
        self._use_native_solver = bool(self._config.get('use_native_solver', True))
        self._native_search_ms = int(self._config.get('native_search_ms', 250))
        self._sleep_mode = False
        self._table_detected = False
        self._postflop_call_from_button = False
        self._raise_button_available = True
        self._presets_available = True
        self._hero_folded_hand = False

        # Autonomous action executor
        self._auto_actor = AutoActor(
            HumanizedConfig(
                enabled=bool(self._config.get('auto_act_enabled', False)),
                min_delay=float(self._config.get('auto_min_delay', 0.8)),
                max_delay=float(self._config.get('auto_max_delay', 2.6)),
                enter_bet_sizing=bool(self._config.get('auto_enter_bet_sizing', True)),
                dry_run=bool(self._config.get('auto_dry_run', False)),
            )
        )

        # Memory monitoring
        self._memory_usage = "0 MB"

        root.title("RTA")
        root.configure(bg=self.BG)
        root.geometry("620x840")
        root.attributes("-topmost", True)
        root.minsize(560, 640)
        
        # Set initial opacity
        self._set_opacity(self._window_opacity)

        self._build_ui()
        self._on_mode_change()
        self._drain_ui_queue()

    def _schedule_on_ui(self, callback):
        """Thread-safely enqueue a callback onto the main Tk thread without blocking on tcl_lock."""
        if getattr(self, '_is_closing', False):
            return
        if threading.current_thread() is threading.main_thread():
            if hasattr(self, 'root') and self.root is not None:
                try:
                    self.root.after(0, callback)
                except Exception:
                    pass
            else:
                try:
                    callback()
                except Exception:
                    pass
            return
        q = getattr(self, '_ui_queue', None)
        if q is not None:
            q.put(callback)
        elif hasattr(self, 'root') and self.root is not None:
            try:
                self.root.after(0, callback)
            except Exception:
                pass
        else:
            try:
                callback()
            except Exception:
                pass

    def _drain_ui_queue(self):
        if getattr(self, '_is_closing', False):
            return
        q = getattr(self, '_ui_queue', None)
        if q is not None:
            while not q.empty():
                try:
                    cb = q.get_nowait()
                    cb()
                except Exception:
                    pass
        if hasattr(self, 'root') and self.root is not None and not getattr(self, '_is_closing', False):
            try:
                self._ui_queue_after = self.root.after(15, self._drain_ui_queue)
            except Exception:
                pass

    def _load_config(self, config_path: str = None) -> dict:
        """Load configuration from config.ini."""
        config = {
            'window_opacity': 90,
            'enable_sound_notifications': True,
            'minimize_to_tray': False,
            'show_confidence_percentages': True,
            'poll_interval_active': 1.0,
            'poll_interval_idle': 5.0,
            'profile': 'ABC',
            'aggression_factor': 1.0,
            'stack_depth': 100,
            'auto_act_enabled': False,
            'auto_min_delay': 0.8,
            'auto_max_delay': 2.6,
            'auto_enter_bet_sizing': True,
            'auto_dry_run': False,
            'use_native_solver': True,
            'native_search_ms': 250,
        }
        
        config_path = config_path or getattr(
            self, '_config_path',
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
        )
        if os.path.exists(config_path):
            try:
                parser = configparser.ConfigParser()
                parser.read(config_path)
                
                if 'ui' in parser:
                    config['window_opacity'] = int(parser.get('ui', 'window_opacity', fallback=90))
                    config['enable_sound_notifications'] = parser.get('ui', 'enable_sound_notifications', fallback='true').lower() == 'true'
                    config['minimize_to_tray'] = parser.get('ui', 'minimize_to_tray', fallback='false').lower() == 'true'
                    config['show_confidence_percentages'] = parser.get('ui', 'show_confidence_percentages', fallback='true').lower() == 'true'
                
                if 'ocr' in parser:
                    config['poll_interval_active'] = float(parser.get('ocr', 'poll_interval_active', fallback=1.0))
                    config['poll_interval_idle'] = float(parser.get('ocr', 'poll_interval_idle', fallback=5.0))
                
                if 'strategy' in parser:
                    config['profile'] = parser.get('strategy', 'profile', fallback='ABC')
                    config['aggression_factor'] = float(parser.get('strategy', 'aggression_factor', fallback=1.0))
                    config['stack_depth'] = int(parser.get('strategy', 'stack_depth', fallback=100))

                if 'postflop' in parser:
                    config['use_native_solver'] = parser.get('postflop', 'use_native_solver', fallback='true').lower() == 'true'
                    config['native_search_ms'] = max(0, min(2000, int(float(parser.get('postflop', 'native_search_ms', fallback=250)))))

                if 'autonomy' in parser:
                    config['auto_act_enabled'] = parser.get('autonomy', 'enabled', fallback='false').lower() == 'true'
                    config['auto_min_delay'] = float(parser.get('autonomy', 'min_delay', fallback=0.8))
                    config['auto_max_delay'] = float(parser.get('autonomy', 'max_delay', fallback=2.6))
                    config['auto_enter_bet_sizing'] = parser.get('autonomy', 'enter_bet_sizing', fallback='true').lower() == 'true'
                    config['auto_dry_run'] = parser.get('autonomy', 'dry_run', fallback='false').lower() == 'true'
            except Exception:
                pass
        
        return config

    def _save_config(self, config_path: str = None) -> bool:
        """Persist current UI and strategy settings to config.ini while preserving comments."""
        config_path = config_path or getattr(self, '_config_path', None)
        if not config_path:
            return False

        cfg = getattr(self, '_config', {})
        if hasattr(self, '_window_opacity'):
            cfg['window_opacity'] = int(self._window_opacity)
        if hasattr(self, '_sound_enabled'):
            cfg['enable_sound_notifications'] = bool(self._sound_enabled)
        if hasattr(self, '_minimize_to_tray'):
            cfg['minimize_to_tray'] = bool(self._minimize_to_tray)
        if hasattr(self, '_show_confidence'):
            cfg['show_confidence_percentages'] = bool(self._show_confidence)
        if hasattr(self, '_use_native_solver'):
            cfg['use_native_solver'] = bool(self._use_native_solver)
        if hasattr(self, '_native_search_ms'):
            cfg['native_search_ms'] = max(0, min(2000, int(self._native_search_ms)))
        if getattr(self, '_strategy_manager', None) is not None:
            cfg['profile'] = self._strategy_manager.config.profile.value
            cfg['aggression_factor'] = float(self._strategy_manager.config.aggression_factor)
            cfg['stack_depth'] = int(self._strategy_manager.config.stack_depth)
        if getattr(self, '_auto_actor', None) is not None:
            cfg['auto_act_enabled'] = bool(self._auto_actor.config.enabled)
            cfg['auto_min_delay'] = float(self._auto_actor.config.min_delay)
            cfg['auto_max_delay'] = float(self._auto_actor.config.max_delay)
            cfg['auto_enter_bet_sizing'] = bool(self._auto_actor.config.enter_bet_sizing)
            cfg['auto_dry_run'] = bool(self._auto_actor.config.dry_run)
        self._config = cfg

        updates = {
            'ui': {
                'window_opacity': str(cfg.get('window_opacity', 90)),
                'enable_sound_notifications': 'true' if cfg.get('enable_sound_notifications', True) else 'false',
                'minimize_to_tray': 'true' if cfg.get('minimize_to_tray', False) else 'false',
                'show_confidence_percentages': 'true' if cfg.get('show_confidence_percentages', True) else 'false',
            },
            'strategy': {
                'profile': str(cfg.get('profile', 'ABC')),
                'aggression_factor': f"{ float(cfg.get('aggression_factor', 1.0)):.1f}",
                'stack_depth': str(cfg.get('stack_depth', 100)),
            },
            'postflop': {
                'use_native_solver': 'true' if cfg.get('use_native_solver', True) else 'false',
                'native_search_ms': str(max(0, min(2000, int(cfg.get('native_search_ms', 250))))),
            },
            'autonomy': {
                'enabled': 'true' if cfg.get('auto_act_enabled', False) else 'false',
                'min_delay': str(cfg.get('auto_min_delay', 0.8)),
                'max_delay': str(cfg.get('auto_max_delay', 2.6)),
                'enter_bet_sizing': 'true' if cfg.get('auto_enter_bet_sizing', True) else 'false',
                'dry_run': 'true' if cfg.get('auto_dry_run', False) else 'false',
            },
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                current_section = None
                seen_keys = {sec: set() for sec in updates}
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith('[') and stripped.endswith(']'):
                        current_section = stripped[1:-1].strip()
                        new_lines.append(line)
                        continue
                    if current_section in updates and '=' in line and not stripped.startswith(('#', ';')):
                        key = line.split('=', 1)[0].strip()
                        if key in updates[current_section]:
                            new_lines.append(f"{key} = {updates[current_section][key]}\n")
                            seen_keys[current_section].add(key)
                            continue
                    new_lines.append(line)

                for sec, kv in updates.items():
                    missing = {k: v for k, v in kv.items() if k not in seen_keys[sec]}
                    if missing:
                        new_lines.append(f"\n[{sec}]\n")
                        for k, v in missing.items():
                            new_lines.append(f"{k} = {v}\n")

                with open(config_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
            else:
                parser = configparser.ConfigParser()
                for sec, kv in updates.items():
                    parser[sec] = kv
                with open(config_path, 'w', encoding='utf-8') as f:
                    parser.write(f)
            return True
        except Exception:
            return False

    def _set_opacity(self, percent: int):
        """Set window opacity (0-100)."""
        alpha = max(0, min(100, percent)) / 100
        self.root.attributes("-alpha", alpha)

    def _play_sound(self):
        """Play notification sound without blocking the UI thread."""
        if not self._sound_enabled:
            return
        
        try:
            if sys.platform == "darwin":
                import subprocess
                subprocess.Popen(
                    ["osascript", "-e", "beep"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                print('\a', flush=True)
        except Exception:
            pass

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        from ui import build
        build(self, multitable=HAS_MULTITABLE)

    def _open_settings(self):
        self.settings_window.deiconify()
        self.settings_window.lift()

    def _toggle_range_grid(self):
        if self.mode == 'preflop' and self.show_range_var.get():
            self.grid_frame.pack(fill='x', pady=(10, 0))
        else:
            self.grid_frame.pack_forget()

    def _on_grid_filter_change(self):
        self._refresh()

    def _retry_ocr(self):
        if self.ocr_var.get():
            self._stop_ocr()
            self.root.after(200, lambda: self.ocr_var.set(True) or self._start_ocr())
        else:
            self.ocr_var.set(True)
            self._start_ocr()

    def _on_mode_change(self):
        """Switch contextual panels without changing the detection state."""
        self.mode = self.mode_var.get()
        if self._exact_cards:
            self.hand_entry.delete(0, tk.END)
            self.hand_entry.insert(0, ''.join(self._exact_cards) if self.mode == 'postflop' else self.hand)
        for panel in (self.spot_frame, self.postflop_frame, self.range_panel,
                      self.analytics_frame, self.play_frame):
            panel.grid_remove()
        self.postflop_info_frame.pack_forget()
        # Always hide grid_frame when leaving preflop
        if self.mode != 'preflop':
            try:
                self.grid_frame.pack_forget()
            except Exception:
                pass
        if self.mode == 'analytics':
            self.analytics_frame.grid()
            self._refresh_analytics()
        else:
            self.play_frame.grid()
            if self.mode == 'preflop':
                self.spot_frame.grid()
                self.range_panel.grid()
            else:
                self.postflop_frame.grid()
                self.postflop_info_frame.pack(fill='x', pady=4)
                if self.ocr_var.get() and hasattr(self, 'postflop_autodetect_var') and not self.postflop_autodetect_var.get():
                    self.postflop_autodetect_var.set(True)
                    self._toggle_postflop_autodetect()
        self._toggle_range_grid()
        self.content_canvas.yview_moveto(0)
        self._refresh()

    def _update_table_list(self):
        """Update the table selector dropdown with current tables."""
        if not HAS_MULTITABLE or not self._multitable_manager:
            return
        
        table_list = self._multitable_manager.get_table_list()
        self._table_choices = table_list
        self.table_combo['values'] = [t[0] for t in table_list]
        
        # Set current selection to active table
        active_table = self._multitable_manager.get_active_table()
        if active_table:
            display_name = self._multitable_manager.get_table_display_name(active_table)
            display_name = "● " + display_name
            if display_name in self.table_combo['values']:
                self.table_combo.set(display_name)
                self._set_table_context(active_table.table_id)
            capability = ('Automatic OCR available · six-seat layout' if active_table.client in ('ggpoker', 'pokerstars')
                          else 'Manual cards/action input · automatic OCR not calibrated for this client')
            visibility = 'Bring this table onscreen. ' if not active_table.visible else ''
            self.table_connection_var.set(f'{len(table_list)} table(s) found · {visibility}{capability}')
        else:
            self.table_combo.set('Select a table' if table_list else 'No poker tables found')
            self.table_connection_var.set(f'{len(table_list)} table(s) found' if table_list else 'Open a GGPoker, PokerStars or PokerFair table')
            self._set_table_context(None)
        
        # Schedule next update
        self.root.after(2000, self._update_table_list)
    
    def _on_table_select(self, event):
        """Handle table selection from dropdown."""
        if not HAS_MULTITABLE:
            return
        
        index = self.table_combo.current()
        choices = getattr(self, '_table_choices', [])
        if 0 <= index < len(choices):
            table_id = choices[index][1]
            if self._multitable_manager.set_active_table(table_id):
                self.follow_table_var.set(False)
                self._set_table_context(table_id)

    def _on_follow_table_change(self):
        if self._multitable_manager:
            self._multitable_manager.set_follow_focus(self.follow_table_var.get())

    def _capture_target(self):
        if HAS_MULTITABLE and self._multitable_manager:
            table = self._multitable_manager.get_active_table()
            if table is None:
                raise RuntimeError('No table selected — choose a poker table above')
            if not table.visible:
                raise RuntimeError('Selected table is hidden — bring it onscreen')
            return dict(table_name=table.name, window_id=table.window_id)
        return dict(table_name=None)

    def _matches_selected_window(self, result):
        if HAS_MULTITABLE and self._multitable_manager:
            selected = self._multitable_manager.get_active_table()
            return selected is not None and (selected.window_id is None or result.get('table_id') == selected.window_id)
        return True
    
    def _on_table_state_change(self, table_id: str, table, new_state):
        """Callback for table state changes."""
        # Auto-switch to frontmost table when it gains focus
        if new_state == TableState.ACTIVE:
            self.root.after(0, lambda tid=table_id: self._set_active_table_ui(tid))
    
    def _set_active_table_ui(self, table_id: str):
        """Update UI when active table changes."""
        if not HAS_MULTITABLE:
            return
        
        table = self._multitable_manager.get_tables().get(table_id)
        if table:
            display_name = self._multitable_manager.get_table_display_name(table)
            display_name = "● " + display_name
            self.table_combo.set(display_name)
            self._set_table_context(table_id)
            self._log_hand_with_table()
    
    def _get_current_table_name(self) -> Optional[str]:
        """Get the name of the currently active table."""
        if HAS_MULTITABLE and self._multitable_manager:
            active_table = self._multitable_manager.get_active_table()
            if active_table:
                return active_table.name
        return None

    def _set_table_context(self, table_id):
        if table_id != self._current_table_id:
            self._preflop_tracker.reset()
            self._preflop_context = {}
            self._big_blind_override = None
            self._big_blind = None
            if HAS_MULTITABLE and self._multitable_manager:
                from table_context import parse_blinds
                table = self._multitable_manager.get_active_table()
                blinds = parse_blinds(table.name) if table else None
                self._big_blind = blinds[1] if blinds else None
            if hasattr(self, 'big_blind_var'):
                self.big_blind_var.set(format_amount(self._big_blind) if self._big_blind else '')
                self.table_amounts_var.set(f'1 BB = {format_amount(self._big_blind)} chips' if self._big_blind else 'Waiting for blinds and stacks')
            self._context_cards = None
            self._hero_folded_hand = False
            self._last_logged_key = None
            self._last_logged_hand = None
            self._hand_confirmation.reset()
            self._manual_position = self._manual_spot = False
            self._position_info = None
            for variable in (self.pos_var, self.kind_var, self.vs_var):
                variable.set('')
            for entry in (self.board_entry, self.pot_entry, self.call_entry):
                entry.delete(0, tk.END)
            self._clear_detection_indicators()
            self.preflop_status_var.set('Waiting for betting context')
            self._clear_auto_hand()
        self._current_table_id = table_id
    
    def _log_hand_with_table(self, hand: str = None, board: str = None, equity: float = None, pot_size: float = None):
        """Log current hand analysis with table information."""
        target_hand = hand if hand is not None else self.hand
        if not HAS_ANALYTICS or not self._logger or not target_hand:
            return
        if not isinstance(target_hand, str):
            return
        # Sanitize confidence: ensure finite
        try:
            import math
            if not math.isfinite(self._current_confidence):
                self._current_confidence = 0.0
        except Exception:
            self._current_confidence = 0.0
        
        mode = getattr(self, 'mode', 'preflop') or 'preflop'
        board_key = board if mode == 'postflop' else None
        dedup_key = (mode, target_hand, board_key)
        last_key = getattr(self, '_last_logged_key', None)
        if last_key is None and getattr(self, '_last_logged_hand', None) is not None:
            last_key = ('preflop', self._last_logged_hand, None)

        # Get table info
        table_name = self._get_current_table_name()
        stakes = None
        if HAS_MULTITABLE and getattr(self, '_multitable_manager', None):
            active_table = self._multitable_manager.get_active_table()
            if active_table:
                stakes = active_table.stakes
        
        pos_val = self.pos_var.get() if hasattr(self, 'pos_var') and self.pos_var.get() else None
        spot_dict = getattr(self, 'spot', None) or {}
        spot_val = spot_dict.get('kind') or None
        rec_action = self._current_action or "UNKNOWN"

        # Deduplicate across the entire street for the same (mode, hand, board);
        # update the existing street entry in-place if spot/recommendation/amounts refined.
        current_time = time.time()
        if last_key == dedup_key:
            existing = getattr(self, '_last_logged_entry', None)
            if existing is not None and existing.hand == target_hand and existing.mode == mode and existing.board == board_key:
                changed = False
                if existing.recommended_action != rec_action:
                    existing.recommended_action = rec_action
                    if existing.user_action is not None:
                        existing.followed_recommendation = (existing.user_action == rec_action)
                    changed = True
                if pos_val and existing.position != pos_val:
                    existing.position = pos_val
                    changed = True
                if spot_val and existing.spot != spot_val:
                    existing.spot = spot_val
                    changed = True
                if mode == 'postflop' and equity is not None and existing.equity != equity:
                    existing.equity = equity
                    changed = True
                if pot_size is not None and existing.pot_size != pot_size:
                    existing.pot_size = pot_size
                    changed = True
                if changed and hasattr(self._logger, '_save'):
                    self._logger._save()
            self._last_log_timestamp = current_time
            return

        # Log the hand
        entry = self._logger.log_analysis(
            hand=target_hand,
            recommended_action=rec_action,
            confidence=self._current_confidence,
            position=pos_val,
            spot=spot_val,
            table_name=table_name,
            stakes=stakes,
            mode=mode,
            board=board_key,
            equity=equity if mode == 'postflop' else None,
            pot_size=pot_size
        )
        if entry is not None:
            self._last_logged_entry = entry
            self._last_logged_entry_ts = entry.timestamp
        
        self._last_logged_hand = target_hand
        self._last_logged_key = dedup_key
        self._last_log_timestamp = current_time

    def _on_postflop_key(self, _event=None):
        """Debounce rapid keystrokes in postflop inputs before recalculating equity."""
        if getattr(self, '_postflop_debounce_after', None) is not None:
            try:
                self.root.after_cancel(self._postflop_debounce_after)
            except Exception:
                pass
            self._postflop_debounce_after = None
        if hasattr(self, 'root') and self.root is not None:
            self._postflop_debounce_after = self.root.after(120, self._on_postflop_change)
        else:
            self._on_postflop_change()

    def _on_postflop_change(self, _event=None):
        """Handle postflop input changes."""
        self._postflop_debounce_after = None
        self._refresh()

    def _on_strategy_change(self):
        """Handle strategy profile or stack depth change."""
        if self._strategy_manager:
            profile_str = self.profile_var.get()
            try:
                profile = StrategyProfile(profile_str)
                self._strategy_manager.set_profile(profile)
            except ValueError:
                pass
            
            stack_depth = int(self.stack_var.get())
            self._strategy_manager.set_stack_depth(stack_depth)
        
        self._refresh()

    def _on_stack_change(self):
        self.auto_stack_var.set(False)
        self._on_strategy_change()

    def _on_table_units_change(self):
        self._table_units = self.table_units_var.get()
        self._preflop_tracker.reset()
        self._preflop_context = {}
        if self.ocr_var.get() and not self._manual_spot:
            self.kind_var.set('')
            self.vs_var.set('')
        self._refresh()

    def _on_big_blind_change(self, _event=None):
        import math
        raw = self.big_blind_var.get().strip().replace(',', '')
        try:
            value = float(raw) if raw else None
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError()
        except ValueError:
            self.table_amounts_var.set('Enter a positive big blind, in chips')
            return
        if value == self._big_blind:
            return
        self._big_blind_override = value
        self._big_blind = value
        self._on_table_units_change()

    def _on_amount_units_change(self):
        target = self.amount_units_var.get()
        try:
            converted = [(field, convert_amount(float(field.get().replace(',', '')), self._amount_units,
                                                  target, self._big_blind))
                         for field in (self.pot_entry, self.call_entry) if field.get().strip()]
        except ValueError as exc:
            self.amount_units_var.set(self._amount_units)
            self.table_amounts_var.set(str(exc))
            return
        for field, value in converted:
            field.delete(0, tk.END)
            field.insert(0, f'{value:.6f}'.rstrip('0').rstrip('.') if value else '0')
        for attribute in ('_last_detected_pot', '_last_detected_call'):
            value = getattr(self, attribute)
            if value is not None:
                converted_value = convert_amount(float(value), self._amount_units, target, self._big_blind)
                text = f'{converted_value:.6f}'.rstrip('0').rstrip('.') if converted_value else '0'
                setattr(self, attribute, text)
        self._amount_units = target
        self._refresh()

    def _apply_preflop_context(self, context):
        self._preflop_context = context
        if hasattr(self, '_update_table_diagram'):
            self._update_table_diagram()
        if not context:
            return
        self.preflop_status_var.set(context.get('message', 'Waiting for betting context'))
        bb = context.get('big_blind')
        if bb:
            self._big_blind = bb
            self.big_blind_var.set(format_amount(bb))
        if context.get('units') == 'bb':
            self._table_units = 'bb'
            self.table_units_var.set('bb')
        parts = [f'1 BB = {format_amount(bb)} chips'] if bb else []
        position = context.get('positions', {}).get(3)
        if position:
            parts.insert(0, f'Your seat: {position}')
        for name, value in (('Pot', context.get('pot')), ('To call', context.get('call'))):
            if value is not None and bb:
                parts.append(f'{name}: {format_amount(value)} chips / {format_amount(value / bb)} BB')
        depth = context.get('effective_bb')
        if depth is not None:
            parts.append(f'Effective stack: {format_amount(depth)} BB')
            if self.auto_stack_var.get() and self._strategy_manager and 20 <= depth <= 150:
                self._strategy_manager.set_stack_depth(depth)
                self.stack_var.set(str(self._strategy_manager.config.stack_depth))
                parts.append(f'Using approximate {self.stack_var.get()} BB range')
            elif self.auto_stack_var.get() and not 20 <= depth <= 150:
                parts.append('Outside the supported 20–150 BB range depths')
        summary = ' · '.join(parts) or 'Waiting for blinds and stacks'
        if context.get('complete') and bb:
            wagers = [f"{context['positions'].get(seat, str(seat + 1))}: {format_amount(value)} chips / {format_amount(value / bb)} BB"
                      for seat, value in context.get('bets', {}).items() if value is not None and value > 0]
            if wagers:
                summary += '\nWagers · ' + ' · '.join(wagers)
        self.table_amounts_var.set(summary)

    def _on_aggression_change(self, value):
        """Handle aggression factor slider change."""
        factor = float(value)
        self.aggression_label.configure(text=f"{factor:.1f}x")
        
        if self._strategy_manager:
            self._strategy_manager.set_aggression_factor(factor)
        
        self._refresh()

    def _import_ranges(self):
        """Import custom GTO ranges from JSON file."""
        if not HAS_STRATEGY or not self._strategy_manager:
            messagebox.showwarning("Strategy", "Strategy module not available")
            return
        
        file_path = filedialog.askopenfilename(
            title="Import GTO Ranges",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            if self._strategy_manager.import_ranges_from_file(file_path):
                messagebox.showinfo("Success", f"Ranges imported from {file_path}")
                self._refresh()
            else:
                messagebox.showerror("Error", "Failed to import ranges. Invalid file format?")

    def _on_spot_change(self):
        self._manual_spot = True
        kind = self.kind_var.get()
        self.spot = {"kind": kind, "pos": self.pos_var.get(),
                     "vs": self.vs_var.get() if kind in ("facing_open", "squeeze", "iso_raise") else None}
        if kind in ("facing_open", "squeeze", "iso_raise"):
            self.vs_row.pack(fill="x", pady=(4, 0))
        else:
            self.vs_row.pack_forget()
        self._refresh()

    def _on_hand_type(self, _event=None):
        if self.ocr_var.get():
            self.ocr_var.set(False)
            self._ocr_stop.set()
            self._ocr_generation += 1
            self._update_ocr_status('ready', 'Manual input')
        self._exact_cards = None
        self._hero_folded_hand = False
        self._last_logged_key = None
        raw = self.hand_entry.get()
        if not raw.strip():
            self.hand = None
            if hasattr(self, 'exact_cards_label'):
                self.exact_cards_label.configure(text='Cards: unknown')
            self.hand_error.configure(text='')
            self.hand_hint.configure(text='e.g. AKs, JJ, T9o' if self.mode == 'preflop' else 'e.g. Ah Kd \u00b7 exact suits')
        else:
            compact = raw.replace(' ', '').strip()
            normalized = ranges.normalize_hand(raw)
            self.hand = normalized
            if normalized is not None and len(compact) == 4 and all(compact[i].upper() in ranges.RANKS and compact[i + 1].lower() in 'shdc' for i in (0, 2)):
                c1 = compact[0].upper() + compact[1].lower()
                c2 = compact[2].upper() + compact[3].lower()
                self._exact_cards = (c1, c2)
                if hasattr(self, 'exact_cards_label'):
                    self.exact_cards_label.configure(text=f'Cards: {c1} {c2}')
            elif hasattr(self, 'exact_cards_label'):
                self.exact_cards_label.configure(text='Cards: unknown')
            if normalized is None:
                self.hand_error.configure(text=f'Invalid hand: {raw!r} \u2014 try AKs, JJ, T9o', fg='#f87171')
            else:
                if self._exact_cards and self.mode == 'postflop':
                    self.hand_error.configure(text='')
                elif normalized != raw.strip():
                    self.hand_error.configure(text=f'Interpreted as {normalized}', fg='#8ba2bc')
                else:
                    self.hand_error.configure(text='')
        self._update_autocomplete()
        self._update_recent_chips()
        self._refresh()

    # --- Autocomplete ---
    def _update_autocomplete(self):
        if not hasattr(self, 'autocomplete_listbox'):
            return
        raw = self.hand_entry.get().strip().upper()
        if not raw or len(raw) < 1:
            self._hide_autocomplete()
            return
        # Filter all_hands by prefix
        try:
            all_h = ranges.all_hands()
        except Exception:
            all_h = []
        matches = [h for h in all_h if h.startswith(raw)]
        # Also match if raw is like "AK" show AKs/AKo (only for valid rank combos)
        if not matches and len(raw) == 2 and raw[0] in ranges.RANKS and raw[1] in ranges.RANKS:
            matches = [h for h in all_h if h[:2] == raw]
        matches = matches[:8]
        if not matches:
            self._hide_autocomplete()
            return
        self._autocomplete_items = matches
        self.autocomplete_listbox.delete(0, tk.END)
        for m in matches:
            self.autocomplete_listbox.insert(tk.END, m)
        if not self._autocomplete_visible:
            self.autocomplete_listbox.pack(fill='x', pady=(4, 0))
            self._autocomplete_visible = True
        self._autocomplete_index = -1

    def _show_autocomplete(self):
        self._update_autocomplete()

    def _hide_autocomplete(self):
        if hasattr(self, 'autocomplete_listbox') and self._autocomplete_visible:
            try:
                self.autocomplete_listbox.pack_forget()
            except Exception:
                pass
            self._autocomplete_visible = False
            self._autocomplete_index = -1

    def _autocomplete_next(self):
        if not self._autocomplete_visible or not self._autocomplete_items:
            return
        self._autocomplete_index = min(self._autocomplete_index + 1, len(self._autocomplete_items) - 1)
        self.autocomplete_listbox.selection_clear(0, tk.END)
        self.autocomplete_listbox.selection_set(self._autocomplete_index)
        self.autocomplete_listbox.see(self._autocomplete_index)
        return "break"

    def _autocomplete_prev(self):
        if not self._autocomplete_visible or not self._autocomplete_items:
            return
        self._autocomplete_index = max(self._autocomplete_index - 1, 0)
        self.autocomplete_listbox.selection_clear(0, tk.END)
        self.autocomplete_listbox.selection_set(self._autocomplete_index)
        self.autocomplete_listbox.see(self._autocomplete_index)
        return "break"

    def _autocomplete_select(self):
        if self._autocomplete_visible and self._autocomplete_index >= 0:
            hand = self._autocomplete_items[self._autocomplete_index]
            self._select_hand(hand)
            self._hide_autocomplete()
            return "break"
        elif self._autocomplete_visible and self._autocomplete_items:
            hand = self._autocomplete_items[0]
            self._select_hand(hand)
            self._hide_autocomplete()
            return "break"

    def _autocomplete_click(self, event):
        idx = self.autocomplete_listbox.nearest(event.y)
        if 0 <= idx < len(self._autocomplete_items):
            self._select_hand(self._autocomplete_items[idx])
            self._hide_autocomplete()

    def _update_recent_chips(self):
        if not hasattr(self, 'recent_frame'):
            return
        # Clear existing chips
        for w in self.recent_frame.winfo_children():
            w.destroy()
        if not hasattr(self, '_recent_hands'):
            self._recent_hands = []
        # Update recent list from current hand
        if self.hand and isinstance(self.hand, str) and self.hand not in self._recent_hands:
            self._recent_hands.insert(0, self.hand)
            self._recent_hands = self._recent_hands[:5]
        if not self._recent_hands:
            return
        tk.Label(self.recent_frame, text='Recent:', bg='#18212d', fg='#6b7280', font=('Helvetica', 9)).pack(side='left', padx=(0, 6))
        for h in self._recent_hands:
            btn = tk.Button(self.recent_frame, text=h, font=('Menlo', 9), bg='#222f40', fg='#9baec3',
                            activebackground='#294f72', activeforeground='#bfe2ff', relief='flat', bd=0,
                            padx=6, pady=2, cursor='hand2', command=lambda hh=h: self._select_hand(hh))
            btn.pack(side='left', padx=2)

    def _select_hand(self, hand):
        if self.ocr_var.get():
            self.ocr_var.set(False)
            self._ocr_stop.set()
            self._ocr_generation += 1
            self._update_ocr_status('ready', 'Manual input')
        self._exact_cards = None
        self._hero_folded_hand = False
        self._last_logged_key = None
        self.hand = hand
        self.hand_entry.delete(0, tk.END)
        self.hand_entry.insert(0, hand)
        if hasattr(self, 'hand_error'):
            self.hand_error.configure(text='')
        self._hide_autocomplete()
        self._update_recent_chips()
        self._refresh()

    def _copy_action(self):
        """Copy recommended action to clipboard."""
        if self._current_action:
            action_text = f"{self._current_action} {self.hand}" if self.hand else self._current_action
            self.root.clipboard_clear()
            self.root.clipboard_append(action_text)
            self.root.update()
            
            # Visual feedback
            original_text = self.quick_action_btn.cget("text")
            self.quick_action_btn.configure(text="✓ Copied!")
            self.root.after(1000, lambda: self.quick_action_btn.configure(text=original_text))

    def _toggle_sleep_mode(self):
        """Toggle sleep mode for OCR."""
        self._sleep_mode = self.sleep_var.get()
        if HAS_OCR:
            sleep_mgr = ocr_module.get_sleep_manager()
            if self._sleep_mode:
                sleep_mgr.enable()
            else:
                sleep_mgr.disable()

    def _on_opacity_change(self, value):
        """Handle opacity slider change."""
        self._set_opacity(int(value))
        self._window_opacity = int(value)

    def _on_tray_change(self):
        """Handle minimize to tray checkbox change."""
        if hasattr(self, 'tray_var'):
            val = bool(self.tray_var.get())
            self._minimize_to_tray = val
            if hasattr(self, 'compact') and hasattr(self.compact, 'on_minimise'):
                self.compact.on_minimise.set(val)
        elif hasattr(self, 'compact') and hasattr(self.compact, 'on_minimise'):
            self._minimize_to_tray = bool(self.compact.on_minimise.get())

    def _on_sound_change(self):
        """Handle sound notifications checkbox change."""
        if hasattr(self, 'sound_var'):
            self._sound_enabled = bool(self.sound_var.get())

    def _on_confidence_change(self):
        """Handle show confidence percentages checkbox change."""
        if hasattr(self, 'show_confidence_var'):
            self._show_confidence = bool(self.show_confidence_var.get())
            self._refresh()

    def _on_native_solver_change(self, _value=None):
        """Sync Native Rust MCCFR Solver toggle and search budget from UI controls."""
        if hasattr(self, 'use_native_solver_var'):
            self._use_native_solver = bool(self.use_native_solver_var.get())
        if hasattr(self, 'native_search_ms_var'):
            try:
                ms = max(0, min(2000, int(float(self.native_search_ms_var.get()))))
                self._native_search_ms = ms
                if hasattr(self, 'native_search_ms_label'):
                    self.native_search_ms_label.configure(text=f'{ms} ms')
            except (ValueError, TypeError):
                pass
        if getattr(self, 'mode', None) in ('preflop', 'postflop'):
            self._refresh()

    def _toggle_auto_act(self):
        """Toggle humanized autonomous action execution on/off."""
        enabled = bool(self.auto_act_var.get()) if hasattr(self, 'auto_act_var') else False
        self._on_autonomy_settings_change()
        if hasattr(self, '_auto_actor') and self._auto_actor is not None:
            self._auto_actor.enabled = enabled
            if not enabled:
                self._auto_actor.emergency_stop()
        if hasattr(self, 'auto_act_status_var'):
            if enabled:
                mode_tag = ' (Dry-run)' if getattr(self._auto_actor.config, 'dry_run', False) else ''
                self.auto_act_status_var.set(f'Autonomous mode: Armed{mode_tag}')
            else:
                self.auto_act_status_var.set('Autonomous mode: Off')

    def _emergency_stop_auto_act(self):
        """Emergency kill-switch for autonomous execution."""
        if hasattr(self, '_auto_actor') and self._auto_actor is not None:
            self._auto_actor.emergency_stop()
        if hasattr(self, 'auto_act_var'):
            self.auto_act_var.set(False)
        if hasattr(self, 'auto_act_status_var'):
            self.auto_act_status_var.set('Autonomous mode: Disarmed (Emergency stop)')

    def _on_autonomy_settings_change(self, _event=None):
        """Sync autonomy settings from UI controls into AutoActor config."""
        if not hasattr(self, '_auto_actor') or self._auto_actor is None:
            return
        min_d = None
        max_d = None
        try:
            if hasattr(self, 'min_delay_var'):
                val = float(self.min_delay_var.get().strip())
                if val >= 0:
                    min_d = val
        except ValueError:
            pass
        try:
            if hasattr(self, 'max_delay_var'):
                val = float(self.max_delay_var.get().strip())
                if val >= 0:
                    max_d = val
        except ValueError:
            pass
        if min_d is not None and max_d is not None:
            self._auto_actor.config.min_delay = min_d
            self._auto_actor.config.max_delay = max(min_d, max_d)
        elif min_d is not None:
            self._auto_actor.config.min_delay = min_d
            if self._auto_actor.config.max_delay < min_d:
                self._auto_actor.config.max_delay = min_d
        elif max_d is not None and max_d >= self._auto_actor.config.min_delay:
            self._auto_actor.config.max_delay = max_d
        if hasattr(self, 'enter_bet_sizing_var'):
            self._auto_actor.config.enter_bet_sizing = bool(self.enter_bet_sizing_var.get())
        if hasattr(self, 'dry_run_var'):
            self._auto_actor.config.dry_run = bool(self.dry_run_var.get())
        if hasattr(self, 'auto_act_var') and self.auto_act_var.get() and hasattr(self, 'auto_act_status_var'):
            mode_tag = ' (Dry-run)' if self._auto_actor.config.dry_run else ''
            self.auto_act_status_var.set(f'Autonomous mode: Armed{mode_tag}')

    def _maybe_trigger_open_cards(self, result: dict):
        """Automatically click GGPoker's green 'Open' card-squeeze button when detected during OCR."""
        if not hasattr(self, '_auto_actor') or self._auto_actor is None:
            return None
        if not self.ocr_var.get():
            return None
        has_live_bounds = bool(result.get('window_bounds') or getattr(self, '_last_window_bounds', None))
        should_open = bool(self._auto_actor.enabled or (getattr(self, '_auto_open_cards', True) and has_live_bounds))
        if not should_open:
            return None

        client = result.get('client') or getattr(self, '_last_client', None) or 'ggpoker'
        bounds = (
            tuple(result['window_bounds'])
            if result.get('window_bounds')
            else getattr(self, '_last_window_bounds', None) or (0, 0, 1000, 700)
        )
        table_id = result.get('table_id') or getattr(self, '_current_table_id', None) or getattr(self, '_last_table_id', None)
        if HAS_MULTITABLE and getattr(self, '_multitable_manager', None):
            active_table = self._multitable_manager.get_active_table()
            if active_table is not None:
                client = active_table.client or client
                if not result.get('window_bounds') and active_table.bounds:
                    bounds = active_table.bounds
                table_id = table_id or active_table.window_id or active_table.table_id

        expected_gen = getattr(self, '_ocr_generation', 0)

        def _validate_open_state() -> bool:
            return (
                not getattr(self, '_is_closing', False)
                and getattr(self, '_ocr_generation', 0) == expected_gen
                and not bool(getattr(self, '_auto_hand_current', False))
            )

        def _on_complete(res: dict):
            if getattr(self, '_is_closing', False):
                return
            if res.get('executed'):
                prefix = 'Dry-run' if res.get('dry_run') else 'Auto-clicked'
                pt = res.get('target') or (0, 0)
                delay = res.get('delay', 0.0)
                status_text = f"{prefix}: OPEN_CARDS (delay {delay:.1f}s) at ({pt[0]}, {pt[1]})"
                self._last_auto_act_status = status_text

                def _ui_update():
                    if getattr(self, '_is_closing', False):
                        return
                    if hasattr(self, 'auto_act_status_var'):
                        self.auto_act_status_var.set(status_text)
                self._schedule_on_ui(_ui_update)

        return self._auto_actor.execute_open_cards(
            client=client,
            window_bounds=bounds,
            table_id=table_id,
            force=should_open,
            state_validator=_validate_open_state,
            on_complete=_on_complete,
            blocking=False,
        )

    def _maybe_trigger_sit_in(self, result: dict):
        """Automatically click GGPoker's 'I'm Back' / 'Sit In' button when detected during OCR."""
        if not hasattr(self, '_auto_actor') or self._auto_actor is None:
            return None
        if not self.ocr_var.get():
            return None
        has_live_bounds = bool(result.get('window_bounds') or getattr(self, '_last_window_bounds', None))
        should_sit_in = bool(self._auto_actor.enabled or (getattr(self, '_auto_sit_in', True) and has_live_bounds))
        if not should_sit_in:
            return None

        client = result.get('client') or getattr(self, '_last_client', None) or 'ggpoker'
        bounds = (
            tuple(result['window_bounds'])
            if result.get('window_bounds')
            else getattr(self, '_last_window_bounds', None) or (0, 0, 1000, 700)
        )
        table_id = result.get('table_id') or getattr(self, '_current_table_id', None) or getattr(self, '_last_table_id', None)
        if HAS_MULTITABLE and getattr(self, '_multitable_manager', None):
            active_table = self._multitable_manager.get_active_table()
            if active_table is not None:
                client = active_table.client or client
                if not result.get('window_bounds') and active_table.bounds:
                    bounds = active_table.bounds
                table_id = table_id or active_table.window_id or active_table.table_id

        expected_gen = getattr(self, '_ocr_generation', 0)

        def _validate_sit_in_state() -> bool:
            return (
                not getattr(self, '_is_closing', False)
                and getattr(self, '_ocr_generation', 0) == expected_gen
                and not bool(getattr(self, '_auto_hand_current', False))
            )

        def _on_complete(res: dict):
            if getattr(self, '_is_closing', False):
                return
            if res.get('executed'):
                prefix = 'Dry-run' if res.get('dry_run') else 'Auto-clicked'
                pt = res.get('target') or (0, 0)
                delay = res.get('delay', 0.0)
                status_text = f"{prefix}: SIT_IN (delay {delay:.1f}s) at ({pt[0]}, {pt[1]})"
                self._last_auto_act_status = status_text

                def _ui_update():
                    if getattr(self, '_is_closing', False):
                        return
                    if hasattr(self, 'auto_act_status_var'):
                        self.auto_act_status_var.set(status_text)
                self._schedule_on_ui(_ui_update)

        return self._auto_actor.execute_sit_in(
            client=client,
            window_bounds=bounds,
            table_id=table_id,
            force=should_sit_in,
            state_validator=_validate_sit_in_state,
            on_complete=_on_complete,
            blocking=False,
        )

    def _get_active_opponent_vpip(self) -> Optional[float]:
        """Resolve the primary opponent's VPIP badge value from OCR seat VPIPs."""
        seat_vpips = getattr(self, '_seat_vpips', None) or {}
        if not seat_vpips:
            return None
        context = getattr(self, '_preflop_context', None) or {}
        positions = context.get('positions') or {}
        spot = getattr(self, 'spot', None) or {}
        vs_pos = spot.get('vs')
        if vs_pos and positions:
            for seat, pos_name in positions.items():
                if pos_name == vs_pos and seat in seat_vpips and seat != 3:
                    return float(seat_vpips[seat])
        opp_vals = [float(v) for s, v in seat_vpips.items() if s != 3 and v is not None]
        if not opp_vals:
            return None
        return round(sum(opp_vals) / len(opp_vals), 1)

    def _record_auto_stack_delta(self, context: dict, is_new_hand: bool):
        """Automatically record win/loss/push and BB delta on the previous hand when a new hand starts."""
        if not HAS_ANALYTICS or not getattr(self, '_logger', None) or not context:
            return
        stacks = context.get('stacks') or {}
        if 3 not in stacks or stacks[3] is None:
            return
        bets = context.get('bets') or {}
        hero_bet = float(bets.get(3) or 0.0)
        hero_stack = float(stacks[3]) + hero_bet
        bb = self._big_blind or context.get('big_blind')
        units = context.get('units') or self._table_units
        if units == 'bb' and bb and bb > 0:
            hero_stack *= float(bb)
            if bb:
                bb = float(bb)
        table_id = getattr(self, '_last_table_id', None) or getattr(self, '_current_table_id', None)
        prev_stack = getattr(self, '_last_hand_starting_stack', None)
        prev_table = getattr(self, '_last_stack_table_id', None)
        prev_hand_ctx = getattr(self, '_last_stack_hand_context', None)
        cur_hand_ctx = getattr(self, '_context_cards', None)

        if hero_stack <= 0:
            return
        if (is_new_hand or (cur_hand_ctx and cur_hand_ctx != prev_hand_ctx)):
            if prev_stack is not None and prev_table == table_id and cur_hand_ctx != prev_hand_ctx:
                entry_ts = getattr(self, '_last_logged_entry_ts', None)
                updated = self._logger.record_stack_delta(
                    prev_stack_chips=prev_stack,
                    new_stack_chips=hero_stack,
                    big_blind=float(bb) if bb else None,
                    timestamp=entry_ts,
                )
                if updated and getattr(self, 'mode', None) == 'analytics':
                    self._refresh_analytics()
            self._last_hand_starting_stack = hero_stack
            self._last_stack_table_id = table_id
            self._last_stack_hand_context = cur_hand_ctx

    def _maybe_trigger_auto_action(
        self,
        recommended_action: str,
        street: str = 'preflop',
        board: str = None,
        call_amount: float = None,
        sizing=None,
        action_buttons_visible: bool = False,
        raise_available: bool = True,
        presets_available: bool = True,
        pot_size: float = None,
    ):
        """Schedule humanized autonomous action execution when confirmed OCR and live action turn are active."""
        if not hasattr(self, '_auto_actor') or self._auto_actor is None or not self._auto_actor.enabled:
            return None
        if not (self.ocr_var.get() and getattr(self, '_auto_hand_current', False) and self.hand):
            return None
        if getattr(self, '_hero_folded_hand', False):
            return None
        if not action_buttons_visible and call_amount is None:
            return None

        client = getattr(self, '_last_client', None) or 'ggpoker'
        bounds = getattr(self, '_last_window_bounds', None) or (0, 0, 1000, 700)
        table_id = getattr(self, '_current_table_id', None) or getattr(self, '_last_table_id', None)
        if HAS_MULTITABLE and getattr(self, '_multitable_manager', None):
            active_table = self._multitable_manager.get_active_table()
            if active_table is not None:
                client = active_table.client or client
                if not getattr(self, '_last_window_bounds', None) and active_table.bounds:
                    bounds = active_table.bounds
                table_id = table_id or active_table.window_id or active_table.table_id

        expected_hand = self.hand
        expected_mode = self.mode

        def _validate_state() -> bool:
            return (
                not getattr(self, '_is_closing', False)
                and bool(getattr(self, '_auto_hand_current', False))
                and not bool(getattr(self, '_hero_folded_hand', False))
                and self.hand == expected_hand
                and self.mode == expected_mode
                and self._auto_actor.enabled
            )

        def _on_complete(res: dict):
            if getattr(self, '_is_closing', False):
                return
            if res.get('executed'):
                if res.get('category') == 'fold':
                    self._hero_folded_hand = True
                prefix = 'Dry-run' if res.get('dry_run') else 'Auto-clicked'
                pt = res.get('target') or (0, 0)
                delay = res.get('delay', 0.0)
                act_str = res.get('action', recommended_action)
                status_text = f"{prefix}: {act_str} (delay {delay:.1f}s) at ({pt[0]}, {pt[1]})"
                self._last_auto_act_status = status_text
            elif res.get('status') == 'cancelled':
                status_text = 'Autonomous mode: Action cancelled'
                self._last_auto_act_status = status_text
            else:
                status_text = None

            def _ui_update():
                if getattr(self, '_is_closing', False):
                    return
                if status_text and hasattr(self, 'auto_act_status_var'):
                    self.auto_act_status_var.set(status_text)
                if res.get('executed'):
                    self._record_user_action(True)
            self._schedule_on_ui(_ui_update)

        return self._auto_actor.execute_action(
            recommended_action=recommended_action,
            client=client,
            window_bounds=bounds,
            table_id=table_id,
            hand=self.hand,
            street=street,
            board=board,
            call_amount=call_amount,
            action_buttons_visible=action_buttons_visible,
            sizing=sizing,
            raise_available=raise_available,
            presets_available=presets_available,
            state_validator=_validate_state,
            on_complete=_on_complete,
            blocking=False,
        )

    def _close_settings(self):
        """Persist settings to config.ini and hide the settings window."""
        self._on_autonomy_settings_change()
        self._save_config()
        if hasattr(self, 'settings_window'):
            self.settings_window.withdraw()

    def _update_memory_usage(self):
        """Update memory usage display."""
        if HAS_OCR and hasattr(ocr_module, "get_memory_monitor"):
            try:
                mem_monitor = ocr_module.get_memory_monitor()
                usage_mb = mem_monitor.get_memory_usage_mb()
                self._memory_usage = f"{usage_mb:.0f} MB"
                self.memory_label.configure(text=f"Memory: {self._memory_usage}")
            except Exception:
                pass
        
        self.root.after(5000, self._update_memory_usage)

    # ------------------------------------------------------------- auto OCR

    def _toggle_ocr(self):
        if self.ocr_var.get():
            self._start_ocr()
        else:
            self._stop_ocr()

    def _update_ocr_status(self, status: str, message: str = "", hand: str = None, position: str = None):
        """Update OCR status display with color coding, pulse, and retry."""
        status_colors = {
            "ready": "#565d6e",
            "watching": "#8b93a7",
            "detected": "#2e9e5b",
            "error": "#e06c75",
            "uncertain": "#ffcc00",
            "retrying": "#ffcc00"
        }
        status_icons = {
            "ready": "\u25cf",
            "watching": "\u25d0",
            "detected": "\u2713",
            "error": "\u26a0",
            "uncertain": "\u25d1",
            "retrying": "\u21bb",
        }
        color = status_colors.get(status, "#565d6e")
        icon = status_icons.get(status, "\u25cf")
        self.ocr_status_icon.configure(text=icon, fg=color)
        self.ocr_status.configure(text=message, fg=color)
        # Pulse animation for watching
        if hasattr(self, '_ocr_pulse_after') and self._ocr_pulse_after is not None:
            try:
                self.root.after_cancel(self._ocr_pulse_after)
            except Exception:
                pass
            self._ocr_pulse_after = None
        if status == "watching":
            self._start_ocr_pulse()
        # Retry button on error
        if hasattr(self, 'ocr_retry_btn'):
            if status == "error":
                self.ocr_retry_btn.pack(side='right', padx=(8, 0))
            else:
                try:
                    self.ocr_retry_btn.pack_forget()
                except Exception:
                    pass
        if hand:
            self.last_hand_label.configure(text=f"Last Hand: {hand}", fg=self.ACCENT)
            if hand != self._last_ocr_hand:
                self._play_sound()
        elif self._last_ocr_hand:
            self.last_hand_label.configure(text=f"Last Hand: {self._last_ocr_hand}", fg="#8b93a7")
        else:
            self.last_hand_label.configure(text="Last Hand: --", fg="#8b93a7")
        if position:
            self.position_label.configure(text=f"Position: {position}", fg=self.ACCENT)
        else:
            self.position_label.configure(text="Position: unknown", fg="#8b93a7")
        self._table_detected = (status == "detected")

    def _start_ocr_pulse(self):
        if not hasattr(self, 'ocr_status_icon'):
            return
        self._ocr_pulse_on = not getattr(self, '_ocr_pulse_on', False)
        try:
            self.ocr_status_icon.configure(fg='#b0becf' if self._ocr_pulse_on else '#8b93a7')
        except Exception:
            return
        self._ocr_pulse_after = self.root.after(600, self._start_ocr_pulse)

    def _start_ocr(self):
        if not HAS_OCR:
            self.ocr_var.set(False)
            self._update_ocr_status('error', 'OCR dependencies missing')
            return
        self._ocr_stop.set()
        self._ocr_stop = threading.Event()
        self._ocr_generation += 1
        self._hand_confirmation.reset()
        self._preflop_tracker.reset()
        self._preflop_context = {}
        self._manual_position = self._manual_spot = False
        self.show_range_var.set(False)
        self._toggle_range_grid()
        self.pos_var.set('')
        self.kind_var.set('')
        self.vs_var.set('')
        generation = self._ocr_generation
        self._ocr_thread = threading.Thread(
            target=self._ocr_loop, args=(self._ocr_stop, generation), daemon=True)
        self._ocr_thread.start()
        self._update_ocr_status('watching', 'Scanning...')
        if self.mode == 'postflop' and hasattr(self, 'postflop_autodetect_var') and not self.postflop_autodetect_var.get():
            self.postflop_autodetect_var.set(True)
            self._toggle_postflop_autodetect()
        self.root.after(500, lambda: self._check_ocr_freshness(generation))

    def _stop_ocr(self):
        self._ocr_stop.set()
        self._ocr_generation += 1
        self._clear_auto_hand()
        self._update_ocr_status('ready', 'Ready')

    def _ocr_loop(self, stop_event, generation):
        while not stop_event.is_set():
            sleep_mgr = ocr_module.get_sleep_manager()
            if sleep_mgr.is_sleeping:
                stop_event.wait(1)
                continue
            target = {}
            is_postflop_full = (
                self.mode == 'postflop'
                and getattr(self, '_postflop_auto_detect', False)
                and hasattr(ocr_module, 'capture_and_read_full_state')
            )
            try:
                target = self._capture_target()
                if is_postflop_full:
                    result = ocr_module.capture_and_read_full_state(**target)
                else:
                    result = ocr_module.capture_and_read_with_position(
                        **target, include_context=self.mode == 'preflop',
                        table_units=self._table_units, big_blind=self._big_blind_override)
            except Exception as exc:
                result = dict(status='error', error=str(exc), message=str(exc),
                              table_id=target.get('window_id'), table_name=target.get('table_name'))
            if isinstance(result, dict) and (result.get('cards') or result.get('hand') or result.get('hole_cards')):
                if hasattr(sleep_mgr, 'record_activity'):
                    sleep_mgr.record_activity()
            if not stop_event.is_set():
                if is_postflop_full:
                    self._schedule_on_ui(lambda r=result: (
                        self._accept_ocr_result(r, generation),
                        self._accept_postflop_result(r, self._postflop_detect_stop),
                    ))
                else:
                    self._schedule_on_ui(lambda r=result: self._accept_ocr_result(r, generation))
            err_msg = str((result.get('error') or result.get('message') or '') if isinstance(result, dict) else '')
            is_no_window = isinstance(result, dict) and result.get('status') == 'error' and 'No poker window' in err_msg
            poll_wait = self._config.get('poll_interval_idle', 5.0) if is_no_window else self._config['poll_interval_active']
            stop_event.wait(poll_wait)

    def _clear_auto_hand(self):
        self._exact_cards = None
        self._auto_hand_current = False
        self._hero_folded_hand = False
        self._last_logged_key = None
        self._last_logged_hand = None
        self._current_action = None
        self.hand = None
        self.hand_entry.delete(0, tk.END)
        self.exact_cards_label.configure(text='Cards: unknown')
        self._refresh()

    def _check_ocr_freshness(self, generation):
        if generation != self._ocr_generation or not self.ocr_var.get():
            return
        if self._auto_hand_current and time.monotonic() - self._last_frame_time > 4:
            self._hand_confirmation.reset()
            self._preflop_tracker.reset()
            self._clear_auto_hand()
            self._update_ocr_status('watching', 'Capture is stale — waiting for a fresh frame')
        self.root.after(500, lambda: self._check_ocr_freshness(generation))

    def _accept_ocr_result(self, result, generation):
        if generation != self._ocr_generation or not self.ocr_var.get():
            return
        if result.get('table_id') is not None and not self._matches_selected_window(result):
            return
        if result.get('status') in ('error', 'unsupported'):
            self._hand_confirmation.reset()
            self._preflop_tracker.reset()
            self._clear_auto_hand()
            self._update_ocr_status('error', result.get('message') or result.get('error') or 'Capture failed')
            return
        if result.get('table_name') != self._get_current_table_name():
            self._hand_confirmation.reset()
            self._preflop_tracker.reset()
            self._clear_auto_hand()
            return
        if result.get('window_bounds'):
            self._last_window_bounds = tuple(result['window_bounds'])
        if result.get('client'):
            self._last_client = result['client']
        if result.get('table_id') is not None:
            self._last_table_id = result['table_id']
        if result.get('seat_vpips'):
            self._seat_vpips = dict(result['seat_vpips'])
        captured_at = result.get('captured_at', time.monotonic())
        if captured_at - self._last_frame_time > 4:
            self._preflop_tracker.reset()
        self._last_frame_time = captured_at
        if time.monotonic() - self._last_frame_time > 4:
            result = dict(status='watching', message='Discarded stale capture')
        context = self._preflop_tracker.update(result)
        preview = result.get('preview')
        if preview is not None:
            from PIL import ImageTk
            preview = preview.copy()
            preview.thumbnail((150, 90))
            self._preview_image = ImageTk.PhotoImage(preview, master=self.root)
            self.card_preview.configure(image=self._preview_image)
        else:
            self.card_preview.configure(image='')
            self._preview_image = None
        if (self.mode == 'postflop' and (result.get('board') or (result.get('preflop') or {}).get('board'))
                and self._auto_hand_current and self._exact_cards and not result.get('cards')):
            return
        if not self._hand_confirmation.update(result):
            if (self.mode == 'postflop' and (result.get('board') or (result.get('preflop') or {}).get('board'))
                    and self._auto_hand_current and self._exact_cards):
                if not result.get('cards'):
                    return
                if result.get('hand') == self.hand:
                    self._hand_confirmation.count = self._hand_confirmation.required
                else:
                    if not result.get('hand'):
                        self._context_cards = None
                    self._clear_auto_hand()
                    return
            else:
                if not result.get('hand'):
                    self._context_cards = None
                self._clear_auto_hand()
                status = result.get('status', 'watching')
                message = result.get('message') or result.get('error') or 'Waiting for cards'
                if result.get('reliable'):
                    status, message = 'watching', 'Confirming cards on the next frame...'
                self._update_ocr_status(status, message)
                if result.get('open_cards_button'):
                    self._maybe_trigger_open_cards(result)
                elif result.get('sit_in_button'):
                    self._maybe_trigger_sit_in(result)
                return
        cards = tuple(result['cards'])
        if result.get('active_opponents') is not None:
            self._active_opponents = result['active_opponents']
        board_str = (context.get('board') if context else None) or result.get('board')
        if board_str:
            cards, board_str = self._disambiguate_hole_vs_board(cards, board_str)
        hand_context = (result.get('table_id'), tuple(sorted(cards)))
        is_new_hand = hand_context != self._context_cards
        if is_new_hand:
            self._hero_folded_hand = False
            self._last_logged_key = None
            self._last_logged_hand = None
            self._manual_position = self._manual_spot = False
            self.kind_var.set('')
            self.vs_var.set('')
            for entry in (self.board_entry, self.pot_entry, self.call_entry):
                entry.delete(0, tk.END)
            self._clear_detection_indicators()
            self._context_cards = hand_context
            if (self.mode == 'postflop'
                    and (self._auto_switched_to_postflop or 'preflop' in result or 'board' in result)
                    and not board_str
                    and not (context and context.get('board_present'))):
                self._auto_switched_to_postflop = False
                self.mode_var.set('preflop')
                self._on_mode_change()
        raise_avail = (context.get('raise_available') if context and 'raise_available' in context
                       else result.get('raise_available'))
        self._raise_button_available = True if raise_avail is None else bool(raise_avail)
        presets_avail = (context.get('presets_available') if context and 'presets_available' in context
                         else result.get('presets_available'))
        self._presets_available = True if presets_avail is None else bool(presets_avail)
        self._exact_cards = cards
        self._auto_hand_current = True
        self._apply_preflop_context(context if 'preflop' in result else {})
        self._record_auto_stack_delta(context if 'preflop' in result else {}, is_new_hand)
        valid_board = False
        if board_str:
            try:
                validate_exact_cards(''.join(cards), board_str)
                valid_board = True
            except ValueError:
                board_str = None
        if valid_board and not getattr(self, '_hero_folded_hand', False):
            self._postflop_call_from_button = bool(
                (context and context.get('call') is not None)
                or result.get('call_amount') is not None
            )
            if not self.board_entry.get().strip() or self.board_entry.get() == str(self._last_detected_board):
                self.board_entry.delete(0, tk.END)
                self.board_entry.insert(0, board_str)
                self.board_detect_indicator.configure(text='✓')
                self._last_detected_board = board_str
                info = (context.get('board_info') if context else None) or result.get('board_info') or {}
                self.street_indicator.configure(text=info.get('street', ''))
            pot_chip = context.get('pot') if context else None
            pot_raw = pot_chip if pot_chip is not None else result.get('pot_size')
            pot_src_unit = 'chips' if pot_chip is not None else self._table_units
            if pot_raw is None and context and context.get('bets'):
                known_b = [v for v in context['bets'].values() if v is not None]
                if known_b and sum(known_b) > 0:
                    pot_raw = sum(known_b)
                    pot_src_unit = 'chips'
            if pot_raw is None and self._big_blind and not self.pot_entry.get().strip():
                pot_raw = 2.0 * float(self._big_blind)
                pot_src_unit = 'chips'
            if pot_raw is not None and (not self.pot_entry.get().strip() or self.pot_entry.get() == str(self._last_detected_pot)):
                try:
                    pot_val = convert_amount(pot_raw, pot_src_unit, self._amount_units, self._big_blind)
                    self.pot_entry.delete(0, tk.END)
                    self.pot_entry.insert(0, str(pot_val))
                    self.pot_detect_indicator.configure(text='✓')
                    self._last_detected_pot = pot_val
                except ValueError:
                    pass
            call_chip = (context.get('call') if context and context.get('call') is not None
                         else (context.get('inferred_call') if context else None))
            call_raw = call_chip if call_chip is not None else (
                result.get('call_amount') if result.get('call_amount') is not None
                else result.get('inferred_call_amount'))
            if call_raw is None and pot_raw is not None:
                call_raw = 0
            call_src_unit = 'chips' if call_chip is not None else self._table_units
            if call_raw is not None and (not self.call_entry.get().strip() or self.call_entry.get() == str(self._last_detected_call)):
                try:
                    call_val = convert_amount(call_raw, call_src_unit, self._amount_units, self._big_blind)
                    self.call_entry.delete(0, tk.END)
                    self.call_entry.insert(0, str(call_val))
                    self.call_detect_indicator.configure(text='✓')
                    self._last_detected_call = call_val
                except ValueError:
                    pass
            if self.mode == 'preflop':
                self._auto_switched_to_postflop = True
                self.mode_var.set('postflop')
                self._on_mode_change()
        if not self._manual_position:
            detected_pos = result.get('position') or (context.get('positions') or {}).get(3)
            if detected_pos:
                self.pos_var.set(detected_pos)
            elif is_new_hand:
                self.pos_var.set('')
        if not self._manual_spot:
            auto_spot = context.get('spot') or result.get('spot') or ''
            auto_vs = context.get('vs') or ''
            if ('preflop' in result and context
                    and (not auto_spot or (auto_spot in ('facing_open', 'squeeze', 'iso_raise') and not auto_vs))):
                inferred = self._infer_fallback_spot(self.pos_var.get(), context, use_current_kind=False)
                if inferred:
                    if not auto_spot:
                        auto_spot = inferred.get('kind') or ''
                    if not auto_vs:
                        auto_vs = inferred.get('vs') or ''
            if auto_spot or self.mode != 'postflop':
                self.kind_var.set(auto_spot)
                self.vs_var.set(auto_vs)
            if self.kind_var.get() in ('facing_open', 'squeeze', 'iso_raise'):
                self.vs_row.pack(fill='x', pady=(4, 0))
            else:
                self.vs_row.pack_forget()
        self.hand = result['hand']
        text = ''.join(cards) if self.mode == 'postflop' else self.hand
        self.hand_entry.delete(0, tk.END)
        self.hand_entry.insert(0, text)
        self.exact_cards_label.configure(text='Cards: ' + ' '.join(cards))
        position = self.pos_var.get()
        source = 'manual' if self._manual_spot else 'detected'
        spot = self.kind_var.get()
        message = f"Confirmed: {' '.join(cards)} | {position or 'position unknown'}"
        message += f" | {spot} ({source})" if spot else ' | ' + context.get('message', 'select betting action')
        self._update_ocr_status('detected', message, self.hand, position)
        self._last_ocr_hand = self.hand
        self._refresh()

    def _disambiguate_hole_vs_board(self, cards, board_str):
        """Resolve same-color suit collisions (s<->c, h<->d) between tilted hole cards and board cards."""
        if not cards or len(cards) != 2 or not board_str:
            return cards, board_str
        try:
            validate_exact_cards(''.join(cards), board_str)
            return cards, board_str
        except ValueError:
            pass
        clean_b = board_str.replace(' ', '')
        if len(clean_b) % 2 != 0:
            return cards, board_str
        comm = [clean_b[i:i + 2].upper()[0] + clean_b[i + 1:i + 2].lower() for i in range(0, len(clean_b), 2)]
        if len(comm) not in (3, 4, 5) or len(set(comm)) != len(comm):
            return cards, board_str
        hole = [cards[0][0].upper() + cards[0][1].lower(), cards[1][0].upper() + cards[1][1].lower()]
        same_color = {'s': 'c', 'c': 's', 'h': 'd', 'd': 'h'}
        was_suited = (hole[0][1] == hole[1][1]) and (hole[0][0] != hole[1][0])
        if was_suited and (hole[0] in comm or hole[1] in comm):
            alt_suit = same_color.get(hole[0][1])
            cand0, cand1 = hole[0][0] + alt_suit, hole[1][0] + alt_suit
            if cand0 not in comm and cand1 not in comm and cand0 != cand1:
                try:
                    validate_exact_cards(cand0 + cand1, board_str)
                    return (cand0, cand1), board_str
                except ValueError:
                    pass
        for idx in (0, 1):
            if hole[idx] in comm:
                r, s = hole[idx][0], hole[idx][1]
                alt = same_color.get(s)
                if alt:
                    cand = r + alt
                    if cand not in comm and cand != hole[1 - idx]:
                        hole[idx] = cand
        try:
            validate_exact_cards(''.join(hole), board_str)
            return (hole[0], hole[1]), board_str
        except ValueError:
            return cards, board_str

    def _apply_ocr_hand(self, hand):
        # Compatibility for manual callers; confirmed capture uses exact cards.
        if self.ocr_var.get():
            self.hand = hand
            self.hand_entry.delete(0, tk.END)
            self.hand_entry.insert(0, hand)
            self._refresh()

    def _on_position_change(self):
        self._manual_position = True
        self._refresh()

    # ------------------------------------------------------------------ Postflop Auto-Detection

    def _toggle_postflop_autodetect(self):
        """Toggle postflop auto-detection on/off."""
        self._postflop_auto_detect = self.postflop_autodetect_var.get()
        
        if self._postflop_auto_detect:
            self._start_postflop_detection()
        else:
            self._stop_postflop_detection()

    def _start_postflop_detection(self):
        self._postflop_detect_stop.set()
        self._postflop_detect_stop = threading.Event()
        self._postflop_detect_thread = threading.Thread(
            target=self._postflop_detect_loop, args=(self._postflop_detect_stop,), daemon=True)
        self._postflop_detect_thread.start()
        self._update_detection_status('watching', 'Scanning...')

    def _stop_postflop_detection(self):
        self._postflop_detect_stop.set()
        if self._postflop_detect_thread is not None and self._postflop_detect_thread.is_alive() and threading.current_thread() is not self._postflop_detect_thread:
            self._postflop_detect_thread.join(timeout=0.5)
        self._update_detection_status('ready', 'Ready')
        self._clear_detection_indicators()

    def _postflop_detect_loop(self, stop_event):
        if stop_event.wait(0.05):
            return
        while not stop_event.is_set():
            if self.ocr_var.get() and self._ocr_thread is not None and self._ocr_thread.is_alive():
                stop_event.wait(0.5)
                continue
            if self.mode == 'postflop':
                target = {}
                try:
                    target = self._capture_target()
                    result = ocr_module.capture_and_read_full_state(**target)
                except Exception as exc:
                    result = dict(status='error', error=str(exc), table_id=target.get('window_id'))
                if not stop_event.is_set():
                    try:
                        self.root.after(0, lambda r=result: self._accept_postflop_result(r, stop_event))
                    except Exception:
                        break
            stop_event.wait(2)

    def _accept_postflop_result(self, result, stop_event):
        # Apply all fields together on Tk's thread, only to the same confirmed
        # hand/table. Slow board OCR must not resurrect a previous hand.
        if stop_event.is_set() or self.mode != 'postflop':
            return
        if result.get('table_id') is not None and not self._matches_selected_window(result):
            return
        if result.get('status') in ('error', 'unsupported'):
            self._clear_postflop_auto_values()
            self._update_detection_status('error', result.get('error') or 'Postflop capture failed')
            return
        cards = result.get('cards')
        board = result.get('board')
        if cards and board:
            cards, board = self._disambiguate_hole_vs_board(tuple(cards), board)
        captured_at = result.get('captured_at')
        if captured_at is not None and time.monotonic() - captured_at > 4:
            self._clear_postflop_auto_values()
            self._update_detection_status('watching', 'Waiting for a fresh frame')
            return
        if self.ocr_var.get():
            if (not self._auto_hand_current or
                    (cards and self._exact_cards and tuple(sorted(cards)) != tuple(sorted(self._exact_cards))) or
                    (not cards and not self._exact_cards) or
                    (self._context_cards and result.get('table_id') is not None and result.get('table_id') != self._context_cards[0])):
                self._clear_postflop_auto_values()
                self._update_detection_status('watching', 'Waiting for the confirmed hand')
                return
            if getattr(self, '_hero_folded_hand', False):
                self._clear_postflop_auto_values()
                self._update_detection_status('watching', 'Folded — waiting for next hand')
                return
            if not cards and self._exact_cards:
                cards = self._exact_cards
        else:
            if cards and not self._exact_cards:
                self._exact_cards = tuple(cards)
                self.hand = result.get('hole_cards') or ranges.normalize_hand(''.join(cards))
                self.hand_entry.delete(0, tk.END)
                self.hand_entry.insert(0, ''.join(cards))
                self.exact_cards_label.configure(text='Cards: ' + ' '.join(cards))
            elif not cards and self._exact_cards:
                cards = self._exact_cards
        if result.get('active_opponents') is not None:
            self._active_opponents = result['active_opponents']
        if result.get('seat_vpips'):
            self._seat_vpips = dict(result['seat_vpips'])
        if result.get('sit_in_button') and not result.get('cards'):
            self._maybe_trigger_sit_in(result)
        if result.get('position') and not self._manual_position:
            self.pos_var.set(result['position'])
        if result.get('big_blind') and self._big_blind_override is None:
            self._big_blind = result['big_blind']
            self.big_blind_var.set(format_amount(self._big_blind))
        result = dict(result)
        call_from_button = result.get('call_amount') is not None
        self._postflop_call_from_button = call_from_button
        if result.get('raise_available') is not None:
            self._raise_button_available = bool(result['raise_available'])
        if result.get('presets_available') is not None:
            self._presets_available = bool(result['presets_available'])
        inferred_call = result.get('inferred_call_amount')
        if board and cards:
            cards, board = self._disambiguate_hole_vs_board(tuple(cards), board)
            try:
                validate_exact_cards(''.join(cards), board)
            except ValueError:
                board = None
        try:
            for key in ('pot_size', 'call_amount'):
                if result.get(key) is not None:
                    result[key] = convert_amount(result[key], self._table_units, self._amount_units, self._big_blind)
            if not call_from_button and board and result.get('pot_size') is not None:
                current_call = self.call_entry.get().strip()
                has_manual_call = bool(current_call and current_call != str(self._last_detected_call))
                if inferred_call is not None and inferred_call > 0:
                    result['call_amount'] = convert_amount(inferred_call, self._table_units, self._amount_units, self._big_blind)
                elif not has_manual_call:
                    result['call_amount'] = 0
        except ValueError as exc:
            self._update_detection_status('partial', str(exc))
            return
        for entry, indicator, attribute, value in (
            (self.board_entry, self.board_detect_indicator, '_last_detected_board', board),
            (self.pot_entry, self.pot_detect_indicator, '_last_detected_pot', result.get('pot_size')),
            (self.call_entry, self.call_detect_indicator, '_last_detected_call', result.get('call_amount')),
        ):
            # Clear disappeared auto-read data; leave explicit manual input.
            if value is not None or getattr(self, attribute) is not None:
                entry.delete(0, tk.END)
                if value is not None:
                    entry.insert(0, str(value))
                indicator.configure(text='✓' if value is not None else '')
            setattr(self, attribute, value)
        info = result.get('board_info') or {}
        self.street_indicator.configure(text=info.get('street', '') if board else '')
        effective_call = result.get('call_amount')
        if effective_call is None and self.call_entry.get().strip():
            effective_call = self.call_entry.get().strip()
        missing = [name for name, value in (('board', board), ('pot', result.get('pot_size')),
                   ('call amount', effective_call)) if value is None]
        if missing:
            status_msg = 'Could not read ' + ', '.join(missing) + '; enter manually'
        elif not call_from_button and inferred_call and inferred_call > 0:
            status_msg = 'Board, pot, and facing wager detected — verify against the table'
        elif not call_from_button:
            status_msg = 'Board and pot detected (0 to call / check baseline) — verify against the table'
        else:
            status_msg = 'Board and amounts detected — verify against the table'
        self._update_detection_status('partial' if missing else 'detected', status_msg)
        self._refresh()

    def _clear_postflop_auto_values(self):
        """Invalidate stale OCR values without deleting manually entered fields."""
        for entry, attribute in ((self.board_entry, '_last_detected_board'),
                                 (self.pot_entry, '_last_detected_pot'),
                                 (self.call_entry, '_last_detected_call')):
            previous = getattr(self, attribute)
            if previous is not None and entry.get() == str(previous):
                entry.delete(0, tk.END)
        self._clear_detection_indicators()
        self._refresh()

    def _update_street_indicator(self, text: str):
        """Update the street indicator display."""
        self.street_indicator.configure(text=text)
    
    def _update_action_indicator(self, text: str):
        """Update the action indicator display."""
        self.action_indicator.configure(text=text)
    
    def _debug_board_detection(self):
        """Run board detection debug and save visualization."""
        if not HAS_OCR:
            messagebox.showwarning("OCR", "OCR module not available")
            return
        
        try:
            save_path = ocr_module.calibrate_board("board_debug.png")
            if save_path:
                messagebox.showinfo("Debug", f"Board detection debug saved to:\n{save_path}\n\nOpen this image to see detected card positions.")
            else:
                messagebox.showerror("Debug", "No GGPoker window found")
        except Exception as e:
            messagebox.showerror("Debug", f"Error: {str(e)}")

    def _update_detection_status(self, status: str, message: str):
        """Update the detection status display."""
        status_colors = {
            "ready": "#565d6e",
            "watching": "#8b93a7",
            "detected": "#2e9e5b",  # Green
            "partial": "#ffcc00",   # Yellow
            "error": "#e06c75"      # Red
        }
        
        color = status_colors.get(status, "#565d6e")
        self.detection_status_icon.configure(fg=color)
        self.detection_status_label.configure(text=message, fg=color)

    def _update_board_field(self, board: str):
        """Update the board entry field with detected value."""
        self.board_entry.delete(0, tk.END)
        self.board_entry.insert(0, board)
        self.board_detect_indicator.configure(text="✓")
        self._on_postflop_change()

    def _update_pot_field(self, pot: int):
        """Update the pot entry field with detected value."""
        self.pot_entry.delete(0, tk.END)
        self.pot_entry.insert(0, str(pot))
        self.pot_detect_indicator.configure(text="✓")
        self._on_postflop_change()

    def _update_call_field(self, call: int):
        """Update the call entry field with detected value."""
        self.call_entry.delete(0, tk.END)
        self.call_entry.insert(0, str(call))
        self.call_detect_indicator.configure(text="✓")
        self._on_postflop_change()

    def _clear_detection_indicators(self):
        """Clear all detection indicators."""
        self.board_detect_indicator.configure(text="")
        self.pot_detect_indicator.configure(text="")
        self.call_detect_indicator.configure(text="")
        self._last_detected_board = None
        self._last_detected_pot = None
        self._last_detected_call = None

    def _refresh_analytics(self):
        """Refresh analytics display with empty state and canvas bars."""
        if not HAS_ANALYTICS or not self._analytics:
            return
        summary = self._analytics.get_summary()
        total = summary.get('total_hands', 0)
        # Empty state
        if total == 0:
            self.analytics_empty.pack(fill='x', pady=(0, 12))
            self._analytics_stats_row.pack_forget()
            self._analytics_dist_label.pack_forget()
            for row in self._analytics_action_rows:
                row.pack_forget()
            if hasattr(self, '_analytics_pos_label'):
                self._analytics_pos_label.pack_forget()
            if hasattr(self, '_analytics_pos_frame'):
                self._analytics_pos_frame.pack_forget()
            return
        else:
            try:
                self.analytics_empty.pack_forget()
            except Exception:
                pass
            self._analytics_stats_row.pack(fill='x', pady=4)
            self._analytics_dist_label.pack(anchor='w', pady=(16, 6))
            for row in self._analytics_action_rows:
                row.pack(fill='x', pady=4)
            if hasattr(self, '_analytics_pos_label'):
                self._analytics_pos_label.pack(anchor='w', pady=(16, 6))
            if hasattr(self, '_analytics_pos_frame'):
                if hasattr(self, '_analytics_exports'):
                    self._analytics_pos_frame.pack(fill='x', pady=4, before=self._analytics_exports)
                else:
                    self._analytics_pos_frame.pack(fill='x', pady=4)
        self.analytics_labels['total_hands'].configure(text=str(summary['total_hands']))
        adherence = summary['gto_adherence']
        self.analytics_labels['gto_adherence'].configure(
            text=f"{adherence['adherence_rate']:.1f}%" if adherence['total_with_actions'] > 0 else "--"
        )
        self.analytics_labels['followed'].configure(text=str(adherence['followed']))
        win_stats = summary['win_rate_stats']
        self.analytics_labels['wins'].configure(text=str(win_stats['wins']))
        self.analytics_labels['losses'].configure(text=str(win_stats['losses']))
        self.analytics_labels['win_rate'].configure(
            text=f"{win_stats['win_rate']:.1f}%" if win_stats['total_with_results'] > 0 else "--"
        )
        if 'net_bb' in self.analytics_labels:
            net_bb_val = win_stats.get('total_bb_net', 0.0)
            self.analytics_labels['net_bb'].configure(
                text=f"{net_bb_val:+.1f} BB" if win_stats['total_with_results'] > 0 else "--"
            )
        if 'bb_per_100' in self.analytics_labels:
            bb100_val = win_stats.get('bb_per_100', 0.0)
            self.analytics_labels['bb_per_100'].configure(
                text=f"{bb100_val:+.1f}" if win_stats['total_with_results'] > 0 else "--"
            )
        action_dist = summary['action_distribution']
        total_pct = sum(action_dist.values()) if action_dist else 0
        bar_colors = {'RAISE': '#2e9e5b', 'CALL': '#3d6fd6', 'FOLD': '#6b7280', 'CHECK': '#8b93a7'}
        for action, (canvas, pct_label) in self.action_labels.items():
            pct = action_dist.get(action, 0)
            pct_label.configure(text=f"{pct:.1f}%")
            # Draw bar on canvas
            try:
                canvas.delete('all')
                if total_pct > 0 and pct > 0:
                    w = canvas.winfo_width()
                    if w < 10:
                        w = 200
                    h = 14
                    bar_w = max(2, int((pct / 100) * w))
                    color = bar_colors.get(action, '#4da3ff')
                    canvas.create_rectangle(0, 0, bar_w, h, fill=color, outline='')
                    canvas.create_rectangle(bar_w, 0, w, h, fill='#1a2535', outline='')
                else:
                    w = canvas.winfo_width() or 200
                    canvas.create_rectangle(0, 0, w, 14, fill='#1a2535', outline='')
            except Exception:
                pass
        if hasattr(self, 'position_stat_labels'):
            pos_stats = summary.get('position_stats', {}) or {}
            for pos, lbl in self.position_stat_labels.items():
                pstat = pos_stats.get(pos)
                if pstat and pstat.get('total_hands', 0) > 0:
                    count = pstat['total_hands']
                    top_act = pstat.get('most_common_action') or '--'
                    lbl.configure(text=f"{count} ({top_act})")
                else:
                    lbl.configure(text="0 hands")
    
    def _export_json(self):
        """Export hand history to JSON file."""
        if not HAS_ANALYTICS or not self._exporter:
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Hand History as JSON"
        )
        
        if filepath:
            self._exporter.export_json(filepath)
            messagebox.showinfo("Export", f"Hand history exported to:\n{filepath}")
    
    def _export_csv(self):
        """Export hand history to CSV file."""
        if not HAS_ANALYTICS or not self._exporter:
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Hand History as CSV"
        )
        
        if filepath:
            self._exporter.export_csv(filepath)
            messagebox.showinfo("Export", f"Hand history exported to:\n{filepath}")

    def _get_latest_logged_entry(self):
        """Return the most recently logged HandLogEntry, if available."""
        entry = getattr(self, '_last_logged_entry', None)
        if entry is not None:
            return entry
        if HAS_ANALYTICS and getattr(self, '_logger', None) is not None:
            recent = self._logger.get_recent_hands(1)
            if recent:
                return recent[-1]
        return None

    def _record_user_action(self, followed: bool) -> bool:
        """Record whether the user followed or deviated from the latest recommendation."""
        if not HAS_ANALYTICS or not getattr(self, '_logger', None):
            return False
        entry = self._get_latest_logged_entry()
        if entry is None:
            return False
        user_action = entry.recommended_action if followed else f"DEVIATED_FROM_{entry.recommended_action}"
        if user_action == "FOLD":
            self._hero_folded_hand = True
        updated = self._logger.update_user_action(entry.timestamp, user_action)
        if updated:
            if hasattr(self, 'feedback_status_var'):
                self.feedback_status_var.set("✓ Logged: Followed" if followed else "Logged: Deviated")
            if getattr(self, 'mode', None) == 'analytics':
                self._refresh_analytics()
        return updated

    def _record_hand_result(self, result: str, pot_size: float = None) -> bool:
        """Record the outcome ('win', 'loss', 'push') for the latest logged hand."""
        if not HAS_ANALYTICS or not getattr(self, '_logger', None):
            return False
        entry = self._get_latest_logged_entry()
        if entry is None:
            return False
        updated = self._logger.update_result(entry.timestamp, result, pot_size=pot_size)
        if updated:
            if hasattr(self, 'feedback_status_var'):
                self.feedback_status_var.set(f"✓ Outcome: {result.upper()}")
            if getattr(self, 'mode', None) == 'analytics':
                self._refresh_analytics()
        return updated

    def _clear_analytics_history(self):
        """Clear all logged hands and refresh the analytics view."""
        if not HAS_ANALYTICS or not getattr(self, '_logger', None):
            return
        self._logger.clear()
        self._last_logged_entry = None
        self._last_logged_entry_ts = None
        self._last_logged_hand = None
        self._last_logged_key = None
        self._refresh_analytics()
    
    def _on_close(self):
        self._is_closing = True
        if hasattr(self, '_auto_actor') and self._auto_actor is not None:
            self._auto_actor.emergency_stop()
        if hasattr(self, 'compact'):
            self.compact.close()
        self._stop_ocr()
        self._stop_postflop_detection()
        if HAS_ANALYTICS and getattr(self, '_logger', None) and hasattr(self._logger, 'flush'):
            try:
                self._logger.flush()
            except Exception:
                pass
        
        # Stop multi-table monitoring
        if HAS_MULTITABLE and self._multitable_manager:
            if self._table_change_callback_id:
                self._multitable_manager.remove_callback(self._table_change_callback_id)
            self._multitable_manager.stop_monitoring()
        
        self.root.destroy()

    # ------------------------------------------------------------- refresh

    def _get_preflop_advice(self, hand, spot=None):
        """Keep advice, grid colors and tooltips on the same active strategy."""
        active_spot = spot if spot is not None else self.spot
        action_sets = ranges.get_action_sets(active_spot)
        if HAS_STRATEGY and self._strategy_manager:
            return self._strategy_manager.advise_with_strategy(active_spot, hand, action_sets)
        return (ranges.advise(active_spot, hand) if hand else None), action_sets

    def _infer_fallback_spot(self, pos, context, use_current_kind=True):
        """Infer a best-effort preflop spot when cards are known."""
        effective_pos = pos or (context.get('positions') or {}).get(3) if context else pos
        if not effective_pos:
            if not context:
                return None
            effective_pos = 'BTN'
        if context:
            if context.get('limped'):
                inferred_vs = context.get('inferred_vs')
                if not inferred_vs or inferred_vs == effective_pos:
                    inferred_vs = 'SB' if effective_pos == 'BB' else 'UTG'
                return {'kind': 'iso_raise', 'pos': effective_pos, 'vs': inferred_vs}
            if context.get('inferred_spot'):
                inferred_kind = context['inferred_spot']
                inferred_vs = context.get('inferred_vs') if inferred_kind in ('facing_open', 'squeeze', 'iso_raise') else None
                if inferred_kind in ('facing_open', 'squeeze', 'iso_raise') and (not inferred_vs or inferred_vs == effective_pos):
                    inferred_vs = 'BTN' if effective_pos in ('SB', 'BB') else 'UTG'
                return {'kind': inferred_kind, 'pos': effective_pos, 'vs': inferred_vs}
            bets = context.get('bets') or {}
            positions = context.get('positions') or {}
            bb = context.get('big_blind')
            sb = context.get('small_blind') or (bb / 2 if bb else 0)
            pot = context.get('pot')
            call = context.get('call')
            if bb and bets and positions:
                epsilon = bb * .01
                known_bets = {s: v for s, v in bets.items() if v is not None}
                hero_bet = known_bets.get(3)
                if hero_bet is None:
                    hero_bet = bb if effective_pos == 'BB' else (sb if effective_pos == 'SB' else 0)
                raises = [s for s, v in known_bets.items() if v > bb + epsilon and s != 3]
                max_opp_bet = max((known_bets[s] for s in raises), default=0)
                if call is not None:
                    max_opp_bet = max(max_opp_bet, hero_bet + call)
                if hero_bet > bb + epsilon and max_opp_bet > hero_bet + epsilon:
                    kind = 'facing_3bet' if hero_bet <= 4.5 * bb else 'facing_4bet'
                    return {'kind': kind, 'pos': effective_pos, 'vs': None}
                if len(raises) == 1 and hero_bet <= bb + epsilon:
                    opener = positions.get(raises[0])
                    if opener and opener != effective_pos and opener != 'BB':
                        return {'kind': 'facing_open', 'pos': effective_pos, 'vs': opener}
                if len(raises) >= 2 and hero_bet <= bb + epsilon:
                    distinct_high = {round(known_bets[s] / bb, 1) for s in raises}
                    if len(distinct_high) >= 2:
                        return {'kind': 'facing_3bet', 'pos': effective_pos, 'vs': None}
                    order = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
                    raise_positions = [
                        positions.get(s) for s in raises
                        if positions.get(s) in order and positions.get(s) not in (effective_pos, 'BB')
                    ]
                    opener = min(raise_positions, key=order.index) if raise_positions else ('BTN' if effective_pos in ('SB', 'BB') else 'UTG')
                    return {'kind': 'squeeze', 'pos': effective_pos, 'vs': opener}
                if not raises and ((pot is not None and pot > sb + bb + epsilon) or (call is not None and call > bb + epsilon) or
                                   (effective_pos == 'BB' and call is not None and call > epsilon)):
                    missing_seats = [s for s, v in bets.items() if v is None and s != 3]
                    if len(missing_seats) == 1:
                        opener = positions.get(missing_seats[0])
                        if opener and opener != effective_pos and opener != 'BB':
                            return {'kind': 'facing_open', 'pos': effective_pos, 'vs': opener}
                    elif len(missing_seats) > 1:
                        order = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
                        if effective_pos in order:
                            prior = set(order[:order.index(effective_pos)])
                            prior_missing = [positions.get(s) for s in missing_seats if positions.get(s) in prior]
                            if prior_missing:
                                return {'kind': 'facing_open', 'pos': effective_pos, 'vs': min(prior_missing, key=order.index)}
                        valid_missing = [
                            positions.get(s) for s in missing_seats
                            if positions.get(s) in order and positions.get(s) not in (effective_pos, 'BB')
                        ]
                        if valid_missing:
                            return {'kind': 'facing_open', 'pos': effective_pos, 'vs': min(valid_missing, key=order.index)}
                if not raises and hero_bet <= bb + epsilon:
                    has_limped_pot = (
                        (pot is None or pot > sb + bb + epsilon)
                        and (
                            sum(1 for v in known_bets.values() if v >= bb - epsilon) >= 2
                            or (any(v is None for s, v in bets.items() if s != 3) and pot is not None and pot > sb + bb + epsilon)
                        )
                    )
                    limpers = [
                        positions.get(s) for s, v in known_bets.items()
                        if has_limped_pot and s != 3 and (
                            (positions.get(s) not in ('SB', 'BB', None, effective_pos) and v >= bb - epsilon)
                            or (positions.get(s) == 'SB' and effective_pos == 'BB' and abs(v - bb) <= epsilon)
                        )
                    ]
                    if limpers:
                        return {'kind': 'iso_raise', 'pos': effective_pos, 'vs': limpers[0]}
        if use_current_kind and self.kind_var.get():
            vs = self.vs_var.get() if self.kind_var.get() in ('facing_open', 'squeeze', 'iso_raise') else None
            if self.kind_var.get() not in ('facing_open', 'squeeze', 'iso_raise') or vs:
                return {'kind': self.kind_var.get(), 'pos': effective_pos, 'vs': vs}
        if effective_pos != 'BB':
            return {'kind': 'open', 'pos': effective_pos, 'vs': None}
        opener = self.vs_var.get() if hasattr(self, 'vs_var') and self.vs_var.get() and self.vs_var.get() != 'BB' else 'BTN'
        return {'kind': 'facing_open', 'pos': 'BB', 'vs': opener}

    def _refresh(self):
        if hasattr(self, '_update_table_diagram'):
            self._update_table_diagram()
        from ui import render_cards
        render_cards(self)
        self.spot = {"kind": self.kind_var.get(),
                     "pos": self.pos_var.get(),
                     "vs": self.vs_var.get() if self.kind_var.get() in ("facing_open", "squeeze", "iso_raise") else None}

        # Handle postflop mode
        if self.mode == "postflop":
            self._refresh_postflop()
            return

        context = getattr(self, '_preflop_context', {})
        fallback_note = None
        eval_spot = self.spot
        is_confirmed_ocr = self.ocr_var.get() and getattr(self, '_auto_hand_current', False) and bool(self.hand)

        if self.ocr_var.get() and context and not self._manual_spot and not context.get('spot'):
            fallback_pos = self.pos_var.get() or (context.get('positions') or {}).get(3)
            fallback_spot = self._infer_fallback_spot(fallback_pos, context, use_current_kind=False) if is_confirmed_ocr else None
            if fallback_spot is None:
                self._current_action = None
                self.advice_var.set('Waiting for betting context')
                self.advice_detail.set(context.get('message', 'Select action and opener manually'))
                self.confidence_var.set('')
                self.advice_label.configure(bg=self.FOLD_C)
                for cell in self.cells.values():
                    cell.configure(bg=self.GRID_EMPTY, fg='#6b7280')
                return
            eval_spot = fallback_spot
            spot_labels = {
                'open': f"{fallback_spot['pos']} Open",
                'facing_open': f"{fallback_spot['pos']} vs {fallback_spot['vs']} Open",
                'iso_raise': f"{fallback_spot['pos']} Iso-Raise vs {fallback_spot['vs']}",
                'squeeze': f"{fallback_spot['pos']} Squeeze vs {fallback_spot['vs']}",
                'facing_3bet': f"{fallback_spot['pos']} Facing 3-Bet",
                'facing_4bet': f"{fallback_spot['pos']} Facing 4-Bet",
            }
            spot_desc = spot_labels.get(fallback_spot['kind'], f"{fallback_spot['pos']} {fallback_spot['kind']}")
            msg = context.get('message', 'Waiting for betting context')
            fallback_note = f"{msg} · using {spot_desc}"
            if hasattr(self, 'preflop_status_var'):
                self.preflop_status_var.set(fallback_note)

        if self.ocr_var.get() and context and getattr(self, 'auto_stack_var', None) and self.auto_stack_var.get():
            depth = context.get('effective_bb')
            if depth is None or not 20 <= depth <= 150:
                if not is_confirmed_ocr:
                    self._current_action = None
                    self.advice_var.set('Waiting for stack depth' if depth is None else 'Stack depth outside range coverage')
                    self.advice_detail.set('Confirm the effective stack or choose a manual depth in Settings.')
                    self.confidence_var.set('')
                    self.advice_label.configure(bg=self.FOLD_C)
                    return
                if depth is not None and self._strategy_manager:
                    self._strategy_manager.set_stack_depth(depth)
                    if hasattr(self, 'stack_var'):
                        self.stack_var.set(str(self._strategy_manager.config.stack_depth))
                stack_str = f"{self.stack_var.get()} BB" if hasattr(self, 'stack_var') else "default"
                stack_msg = (f"Confirming stack depth · using {stack_str} range"
                             if depth is None else f"Effective stack {format_amount(depth)} BB · using {stack_str} range")
                fallback_note = f"{fallback_note} · {stack_msg}" if fallback_note else stack_msg

        if self.ocr_var.get() and (not getattr(self, '_auto_hand_current', False) or
                not eval_spot.get('pos') or not eval_spot.get('kind') or
                (eval_spot.get('kind') in ('facing_open', 'squeeze', 'iso_raise') and not eval_spot.get('vs'))):
            fallback_pos = self.pos_var.get() or (context.get('positions') or {}).get(3)
            fallback_spot = self._infer_fallback_spot(fallback_pos, context, use_current_kind=False) if is_confirmed_ocr else None
            if fallback_spot is not None and (fallback_note is not None or bool(context)):
                eval_spot = fallback_spot
            else:
                self._current_action = None
                self.advice_var.set('Waiting for confirmed cards' if not getattr(self, '_auto_hand_current', False)
                                    else 'Select position / action')
                self.advice_detail.set('Waiting for detected context; you can select position, action and opener manually.')
                self.confidence_var.set('')
                self.advice_label.configure(bg=self.FOLD_C)
                for cell in self.cells.values():
                    cell.configure(bg=self.GRID_EMPTY, fg='#6b7280')
                return

        # Preflop mode - action sets for grid coloring
        result, action_sets = self._get_preflop_advice(self.hand, spot=eval_spot)
        color_map = {}
        for act_key, hset in action_sets.items():
            color = (self.RAISE_C if ("BET" in act_key or "RAISE" in act_key or "SQUEEZE" in act_key)
                     else self.CALL_C if act_key == "CALL" else self.FOLD_C)
            for h in hset:
                color_map[h] = color

        # Grid filter
        grid_filter = getattr(self, 'grid_filter_var', None)
        filter_val = grid_filter.get() if grid_filter else 'all'
        filter_color = {'raise': self.RAISE_C, 'call': self.CALL_C, 'fold': self.GRID_EMPTY}.get(filter_val)
        mix_indicators = getattr(self, 'cell_mix_indicators', {})

        for grid_hand, cell in self.cells.items():
            is_selected = (self.hand == grid_hand)
            base_color = color_map.get(grid_hand, self.GRID_EMPTY)
            # Apply filter dimming
            dimmed = False
            if filter_val != 'all' and not is_selected:
                if base_color != filter_color:
                    dimmed = True
            if is_selected:
                cell_bg = self.ACCENT
                cell.configure(bg=cell_bg, fg="#0c0e12",
                               font=("Menlo", 8, "bold"))
            elif dimmed:
                cell_bg = '#1a1e28'
                cell.configure(bg=cell_bg, fg="#4a5568",
                               font=("Menlo", 8))
            elif grid_hand in color_map:
                cell_bg = color_map[grid_hand]
                cell.configure(bg=cell_bg, fg="#ffffff",
                               font=("Menlo", 8))
            else:
                cell_bg = self.GRID_EMPTY
                cell.configure(bg=cell_bg, fg="#6b7280",
                               font=("Menlo", 8))
            if grid_hand in mix_indicators:
                try:
                    is_mixed = len(ranges.get_mixed_frequencies(eval_spot, grid_hand)) > 1
                    mix_indicators[grid_hand].configure(
                        bg='#f59e0b' if (is_mixed and not dimmed) else cell_bg
                    )
                except Exception:
                    pass

        # advice
        if self.hand is None:
            self.advice_var.set("Type a hand (e.g. AKs, JJ, T9o)")
            self.advice_detail.set("")
            self.advice_label.configure(bg=self.FOLD_C)
            self.confidence_var.set("")
            self._current_action = None
            self._current_confidence = 0.0
            return
        if not self.hand:
            self._current_action = None
            self.advice_var.set(f"Invalid hand: {self.hand_entry.get()!r}")
            self.advice_label.configure(bg=self.FOLD_C)
            self.confidence_var.set("")
            return
        if result is None:
            self._current_action = None
            self.advice_var.set("Pick a valid spot")
            self.advice_label.configure(bg=self.FOLD_C)
            self.confidence_var.set("")
            return
        action, detail = result
        preflop_call = context.get('call') if context else None
        is_open_spot = bool(eval_spot and eval_spot.get('kind') == 'open')
        has_action_turn = bool(
            preflop_call is not None
            or (context and context.get('action_turn'))
            or (is_open_spot and not context and self.kind_var.get() == 'open')
        )
        raise_avail = bool(
            getattr(self, '_raise_button_available', True)
            and (not context or context.get('raise_available', True) is not False)
        )
        if is_confirmed_ocr and has_action_turn and not raise_avail:
            if any(tok in action.upper() for tok in ('RAISE', 'BET', '3-BET', '4-BET', '5-BET', 'SQUEEZE', 'SHOVE', 'ALL-IN')):
                action = 'CALL' if (preflop_call is not None and preflop_call > 0) else 'CHECK'
                detail = f"{detail} ({action.title()} — no Raise button)" if detail else f"{action.title()} — no Raise button"
        color = (self.RAISE_C if ("BET" in action or "RAISE" in action or "SQUEEZE" in action)
                 else self.CALL_C if action in ("CALL", "CHECK") else self.FOLD_C)
        
        self._current_action = action
        if HAS_STRATEGY and self._strategy_manager:
            lookup_act = "3-BET" if action == "SQUEEZE" and "3-BET" in action_sets else action
            self._current_confidence = self._strategy_manager.get_confidence_percentage(
                self.hand, lookup_act, action_sets
            )
        # Icon for colorblind: ▲ Raise, ● Call, ■ Fold
        icon_map = {"RAISE": "\u25b2", "BET": "\u25b2", "SQUEEZE": "\u25b2", "CALL": "\u25cf", "FOLD": "\u25a0", "CHECK": "\u25cf"}
        icon = ""
        for k, v in icon_map.items():
            if k in action:
                icon = v + " "
                break
        self.advice_var.set(f"{icon}{action}  {self.hand}")
        try:
            freqs = ranges.get_mixed_frequencies(eval_spot, self.hand)
            if len(freqs) > 1:
                if not hasattr(self, '_mixed_rng_cache'):
                    self._mixed_rng_cache = {}
                cache_key = (
                    getattr(self, '_context_cards', None),
                    eval_spot.get('kind'),
                    eval_spot.get('pos'),
                    eval_spot.get('vs'),
                    self.hand,
                )
                cached_roll = self._mixed_rng_cache.get(cache_key)
                rolled_action, roll_pct, _ = ranges.roll_mixed_action(
                    eval_spot, self.hand, rng_value=cached_roll
                )
                self._mixed_rng_cache[cache_key] = roll_pct
                freq_str = " / ".join(f"{act} {pct}%" for act, pct in freqs.items())
                mix_note = f"Mix: {freq_str} · RNG {roll_pct}/100 \u2192 {rolled_action}"
                detail = f"{detail} · {mix_note}" if detail else mix_note
        except Exception:
            pass
        if getattr(self, '_use_native_solver', False) and getattr(self, '_query_native_preflop_enabled', False):
            try:
                import poker_lab
                hole_query = ''.join(self._exact_cards) if self._exact_cards else self.hand
                bb_val = self._big_blind or (context.get('big_blind') if context else None) or 100.0
                pot_val = (context.get('pot') if context and context.get('pot') is not None else 1.5 * float(bb_val))
                call_val = (context.get('call') if context and context.get('call') is not None else 1.0 * float(bb_val))
                native_pre = poker_lab.query_native_preflop(
                    hero_hand=hole_query,
                    spot=eval_spot,
                    pot_size=pot_val,
                    call_amount=call_val,
                    big_blind=bb_val,
                    preflop_context=context,
                )
                if native_pre.get('status') == 'candidate' and native_pre.get('cfr_frequencies'):
                    bp_str = "/".join(f"{k} {v}%" for k, v in native_pre['cfr_frequencies'].items())
                    detail = f"{detail} · MCCFR Blueprint: {bp_str}" if detail else f"MCCFR Blueprint: {bp_str}"
            except Exception:
                pass
        if fallback_note:
            detail = f"{detail} ({fallback_note})" if detail else fallback_note
        self.advice_detail.set(detail)
        self.advice_label.configure(bg=color)
        # Confidence bar
        if hasattr(self, 'confidence_bar'):
            try:
                self.confidence_bar.delete('all')
                if self._current_confidence > 0:
                    w = self.confidence_bar.winfo_width() or 400
                    h = 4
                    fill_w = int((min(100, self._current_confidence) / 100) * w)
                    self.confidence_bar.create_rectangle(0, 0, fill_w, h, fill=color, outline='')
                    self.confidence_bar.create_rectangle(fill_w, 0, w, h, fill='#1a2535', outline='')
                else:
                    w = self.confidence_bar.winfo_width() or 400
                    self.confidence_bar.create_rectangle(0, 0, w, 4, fill='#1a2535', outline='')
            except Exception:
                pass
        if self._show_confidence and self._current_confidence > 0:
            self.confidence_var.set(f"Heuristic range guidance · {self._current_confidence:.0f}% confidence")
        else:
            self.confidence_var.set("")
        if hasattr(self, 'feedback_status_var'):
            self.feedback_status_var.set("")
        
        if is_confirmed_ocr and getattr(self, '_hero_folded_hand', False):
            self.advice_detail.set(f"{detail} · Folded — waiting for next hand" if detail else "Folded — waiting for next hand")
            return

        # Log hand analysis with table info
        self._log_hand_with_table()

        # Trigger autonomous action if live call/action button is detected (including open spots)
        if is_confirmed_ocr and has_action_turn:
            effective_call = (
                float(preflop_call)
                if preflop_call is not None
                else (float(self._big_blind) if self._big_blind else 1.0)
            )
            presets_avail = bool(
                getattr(self, '_presets_available', True)
                and (not context or context.get('presets_available', True) is not False)
            )
            self._maybe_trigger_auto_action(
                recommended_action=action,
                street='preflop',
                board=None,
                call_amount=effective_call,
                sizing=detail,
                action_buttons_visible=True,
                raise_available=raise_avail,
                presets_available=presets_avail,
                pot_size=context.get('pot') if context else None,
            )

    def _refresh_postflop(self):
        """Refresh postflop advice display."""
        if not HAS_POSTFLOP:
            self.advice_var.set("Postflop modules not available")
            self.advice_detail.set("Install numpy for full functionality")
            self.advice_label.configure(bg=self.FOLD_C)
            return

        self._current_action = None
        self.equity_var.set('Equity: --')
        self.outs_var.set('Outs: --')
        self.pot_odds_var.set('Pot Odds: --')
        self.confidence_var.set('')
        if self.ocr_var.get() and getattr(self, '_hero_folded_hand', False):
            self.advice_var.set('Folded — waiting for next hand')
            self.advice_detail.set('Hand folded; postflop analysis paused until next deal')
            self.advice_label.configure(bg=self.FOLD_C)
            return
        hand = ''.join(self._exact_cards) if self._exact_cards else self.hand_entry.get().strip()
        board = self.board_entry.get().strip()
        try:
            import math
            if self.ocr_var.get() and not self._auto_hand_current:
                raise ValueError('Waiting for confirmed exact cards')
            hand, board = validate_exact_cards(hand, board)
            pot_raw = self.pot_entry.get().replace(',', '').strip()
            call_raw = self.call_entry.get().replace(',', '').strip()
            pot_size = float(pot_raw)
            call_amount = float(call_raw) if call_raw else 0.0
            pot_size = convert_amount(pot_size, self._amount_units, 'chips', self._big_blind)
            call_amount = convert_amount(call_amount, self._amount_units, 'chips', self._big_blind)
            if not all(math.isfinite(v) and v >= 0 for v in (pot_size, call_amount)):
                raise ValueError('Pot and call amounts must be non-negative numbers')
            if pot_size + call_amount <= 0:
                raise ValueError('Enter a positive pot size')
        except ValueError as exc:
            self.advice_var.set('Postflop inputs incomplete')
            self.advice_detail.set(str(exc) or 'Enter pot and call amounts')
            self.advice_label.configure(bg=self.FOLD_C)
            return

        # Calculate outs
        try:
            outs_count, outs_desc = get_outs_simple(hand, board)
            self.outs_var.set(f"Outs: {outs_count} ({outs_desc})")
        except Exception:
            self.outs_var.set("Outs: --")

        # Calculate pot odds
        total_pot = pot_size + call_amount
        pot_odds = (call_amount / total_pot) * 100
        self.pot_odds_var.set(f"Pot Odds: {pot_odds:.1f}%")

        # Get postflop advice
        try:
            self._postflop_calc_generation = getattr(self, '_postflop_calc_generation', 0) + 1
            calc_gen = self._postflop_calc_generation
            mgr = getattr(self, '_strategy_manager', None) if HAS_STRATEGY else None
            opp_vpip = self._get_active_opponent_vpip()
            street_str = self.street_indicator.cget('text').lower() if hasattr(self, 'street_indicator') and self.street_indicator.cget('text') else None
            opp_range = None
            if spot_to_opponent_range:
                try:
                    bet_frac = (call_amount / pot_size) if (pot_size and pot_size > 0 and call_amount > 0) else None
                    opp_range = spot_to_opponent_range(
                        self.spot,
                        strategy_manager=mgr,
                        opponent_vpip=opp_vpip,
                        board=board,
                        street=street_str,
                        facing_bet=(call_amount > 0),
                        bet_fraction=bet_frac,
                    )
                except TypeError:
                    opp_range = spot_to_opponent_range(self.spot, strategy_manager=mgr)
            effective_stack = None
            context = getattr(self, '_preflop_context', None) or {}
            eff_bb = context.get('effective_bb')
            bb = self._big_blind or context.get('big_blind')
            if eff_bb is not None and eff_bb > 0:
                if bb and bb > 0:
                    effective_stack = max(0.0, float(eff_bb) * float(bb) - call_amount)
                else:
                    effective_stack = max(0.0, float(eff_bb) - call_amount)
            elif context.get('stacks') and 3 in context['stacks'] and context['stacks'][3] is not None:
                hero_stack = float(context['stacks'][3])
                if self._table_units == 'bb' and bb and bb > 0:
                    hero_stack *= float(bb)
                effective_stack = max(0.0, hero_stack - call_amount)
            elif mgr is not None and mgr.config.stack_depth:
                eff_bb = mgr.config.stack_depth
                if bb and bb > 0:
                    effective_stack = max(0.0, float(eff_bb) * float(bb) - call_amount)
                else:
                    effective_stack = max(0.0, float(eff_bb) - call_amount)

            advice_kwargs = dict(
                hero_hand=hand,
                board=board,
                pot_size=pot_size,
                call_amount=call_amount,
                iterations=1000,
            )
            if getattr(self, 'spot', None):
                advice_kwargs["spot"] = self.spot
            if effective_stack is not None and effective_stack > 0:
                advice_kwargs["effective_stack"] = effective_stack
            if opp_range:
                advice_kwargs["opponent_range"] = opp_range
            if getattr(self, '_active_opponents', 1) > 1:
                advice_kwargs["num_opponents"] = self._active_opponents
            if mgr is not None:
                advice_kwargs["aggression_factor"] = mgr.config.aggression_factor
                advice_kwargs["profile"] = mgr.config.profile.value
            if opp_vpip is not None:
                advice_kwargs["opponent_vpip"] = opp_vpip
            if hasattr(self, '_postflop_tracker') and self._postflop_tracker is not None:
                pf_ctx = self._postflop_tracker.update({
                    'table_id': getattr(self, '_current_table_id', None) or getattr(self, '_last_table_id', None),
                    'cards': self._exact_cards or hand,
                    'board': board,
                    'pot_size': pot_size,
                    'call_amount': call_amount,
                    'big_blind': float(bb) if (bb and bb > 0) else 100.0,
                })
                self._postflop_context = pf_ctx
            else:
                pf_ctx = getattr(self, '_postflop_context', None) or {}
            if getattr(self, '_use_native_solver', False):
                advice_kwargs["use_native_engine"] = True
                advice_kwargs["native_search_ms"] = int(getattr(self, '_native_search_ms', 40))
                if bb and bb > 0:
                    advice_kwargs["big_blind"] = float(bb)
                if context and context.get('action_history'):
                    advice_kwargs["observed_actions"] = list(context['action_history'])
                if pf_ctx and pf_ctx.get('postflop_history'):
                    advice_kwargs["postflop_history"] = list(pf_ctx['postflop_history'])

            if getattr(self, '_async_postflop', False):
                self.advice_var.set("Calculating...")
                self.advice_detail.set("Running postflop equity simulation...")

                def _worker(gen=calc_gen, kw=advice_kwargs, h=hand, b=board, po=pot_odds, ps=pot_size):
                    try:
                        adv = get_postflop_advice(**kw)
                        if hasattr(self, 'root') and self.root is not None:
                            self.root.after(0, lambda: self._apply_postflop_advice_result(adv, h, b, po, gen, pot_size=ps))
                        else:
                            self._apply_postflop_advice_result(adv, h, b, po, gen, pot_size=ps)
                    except Exception as exc:
                        if hasattr(self, 'root') and self.root is not None:
                            self.root.after(0, lambda e=exc: self._apply_postflop_error(e, gen))
                        else:
                            self._apply_postflop_error(exc, gen)

                t = threading.Thread(target=_worker, daemon=True)
                self._postflop_calc_thread = t
                t.start()
            else:
                advice = get_postflop_advice(**advice_kwargs)
                self._apply_postflop_advice_result(advice, hand, board, pot_odds, calc_gen, pot_size=pot_size)

        except Exception as e:
            self._apply_postflop_error(e, getattr(self, '_postflop_calc_generation', 0))

    def _apply_postflop_error(self, error: Exception, generation: int):
        """Apply postflop calculation error if generation matches current calculation."""
        if generation != getattr(self, '_postflop_calc_generation', 0):
            return
        self.advice_var.set("Error calculating advice")
        self.advice_detail.set(str(error))
        self.advice_label.configure(bg=self.FOLD_C)
        self.confidence_var.set("")

    def _apply_postflop_advice_result(self, advice: dict, hand: str, board: str, pot_odds: float, generation: int, pot_size: float = None):
        """Apply calculated postflop advice if generation matches current calculation."""
        if generation != getattr(self, '_postflop_calc_generation', 0):
            return
        if self.ocr_var.get() and getattr(self, '_hero_folded_hand', False):
            return
        try:
            equity_pct = advice['equity_pct']
            self.equity_var.set(f"Equity: {equity_pct:.1f}%")

            decision = advice['decision']
            reasoning = advice['reasoning']
            sizing = advice.get('recommended_sizing')
            raw_call = self.call_entry.get().replace(',', '').strip()
            call_val = float(raw_call) if raw_call else 0.0
            raise_avail = bool(getattr(self, '_raise_button_available', True))
            if getattr(self, '_postflop_call_from_button', False) and not raise_avail and (
                decision in ("RAISE", "BET") or (call_val <= 0 and decision == "CALL")
            ):
                decision = "CALL" if call_val > 0 else "CHECK"
                sizing = "Call" if call_val > 0 else "Check"
                reasoning = f"{reasoning} | {decision.title()} only (no Raise button)"
            elif sizing and sizing not in reasoning:
                reasoning = f"{reasoning} | Sizing: {sizing}"
            self._current_action = decision

            # Set colors based on decision
            if decision in ("CALL", "CHECK"):
                color = self.CALL_C
            elif decision in ("RAISE", "BET"):
                color = self.RAISE_C
            else:
                color = self.FOLD_C

            self.advice_var.set(f"{decision}  {hand}")
            self.advice_detail.set(reasoning)
            self.advice_label.configure(bg=color)

            # Calculate confidence for postflop (incorporating CFR frequency if available)
            cfr_freqs = advice.get('cfr_frequencies') or {}
            if cfr_freqs:
                self._current_confidence = float(cfr_freqs.get(decision, max(cfr_freqs.values())))
            elif HAS_STRATEGY and getattr(self, '_strategy_manager', None):
                confidence = abs(equity_pct - pot_odds)
                self._current_confidence = max(0, 100 - confidence * 2)

            if getattr(self, '_show_confidence', False) and self._current_confidence > 0:
                cfr_ev = advice.get('ev')
                ev_tag = f" · EV {cfr_ev:+.1f}" if cfr_ev is not None else ""
                self.confidence_var.set(f"CFR+ / GTO subgame · {self._current_confidence:.0f}% frequency{ev_tag}")
            else:
                self.confidence_var.set("")
            if hasattr(self, 'feedback_status_var'):
                self.feedback_status_var.set("")

            # Log postflop hand analysis with street/board deduplication
            logged_hand = self.hand if isinstance(getattr(self, 'hand', None), str) and self.hand else hand
            self._log_hand_with_table(hand=logged_hand, board=board, equity=equity_pct, pot_size=pot_size)

            # Trigger autonomous postflop action if confirmed OCR and live action turn
            is_confirmed_postflop = self.ocr_var.get() and getattr(self, '_auto_hand_current', False)
            if is_confirmed_postflop and getattr(self, '_postflop_call_from_button', False):
                street_name = self.street_indicator.cget('text').lower() if hasattr(self, 'street_indicator') and self.street_indicator.cget('text') else 'postflop'
                presets_avail = bool(getattr(self, '_presets_available', True))
                self._maybe_trigger_auto_action(
                    recommended_action=decision,
                    street=street_name,
                    board=board,
                    call_amount=call_val,
                    sizing=sizing,
                    action_buttons_visible=True,
                    raise_available=raise_avail,
                    presets_available=presets_avail,
                    pot_size=pot_size,
                )
        except Exception as e:
            self._apply_postflop_error(e, generation)


# ---------------------------------------------------------------------------
# Global hotkey via pynput (optional)
# ---------------------------------------------------------------------------

    # --- Grid hover tooltip ---
    def _on_grid_hover(self, hand, event):
        if hasattr(self, '_grid_tooltip_after') and self._grid_tooltip_after:
            try:
                self.root.after_cancel(self._grid_tooltip_after)
            except Exception:
                pass
        def show():
            if self._grid_tooltip is not None:
                try:
                    self._grid_tooltip.destroy()
                except Exception:
                    pass
            # Determine action for this hand
            try:
                advice, _ = self._get_preflop_advice(hand)
                action = advice[0] if advice else "Select a valid spot"
                text = f"{hand} \u2014 {action}"
                freqs = ranges.get_mixed_frequencies(self.spot, hand)
                if len(freqs) > 1:
                    freq_str = " / ".join(f"{act} {pct}%" for act, pct in freqs.items())
                    text += f" ({freq_str})"
                if self.hand == hand:
                    text += " (selected)"
            except Exception:
                text = hand
            x = event.x_root + 12
            y = event.y_root + 12
            tip = tk.Toplevel(self.root)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            tip.attributes("-topmost", True)
            tk.Label(tip, text=text, bg='#1e2d42', fg='#eef4fc',
                     font=('Helvetica', 10), padx=8, pady=4,
                     relief='solid', bd=1).pack()
            self._grid_tooltip = tip
        self._grid_tooltip_after = self.root.after(300, show)

    def _on_grid_leave(self, event):
        if hasattr(self, '_grid_tooltip_after') and self._grid_tooltip_after:
            try:
                self.root.after_cancel(self._grid_tooltip_after)
            except Exception:
                pass
            self._grid_tooltip_after = None
        if getattr(self, '_grid_tooltip', None) is not None:
            try:
                self._grid_tooltip.destroy()
            except Exception:
                pass
            self._grid_tooltip = None

    # --- Help overlay ---
    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("RTA \u00b7 Help")
        win.configure(bg=self.BG, padx=20, pady=20)
        win.geometry("480x560")
        win.transient(self.root)
        win.attributes("-topmost", True)
        tk.Label(win, text="Keyboard Shortcuts", bg=self.BG, fg=self.FG,
                 font=('Helvetica', 16, 'bold')).pack(anchor='w', pady=(0, 12))
        shortcuts = [
            ("H", "Focus hand input"),
            ("1 \u2013 6", "Select position (BTN/SB/BB/UTG/MP/CO)"),
            ("O", "First in (open)"),
            ("F", "Facing open"),
            ("I", "Iso-raise"),
            ("S", "Squeeze"),
            ("T / #", "Facing 3-bet"),
            ("Q / $", "Facing 4-bet"),
            ("R", "Toggle hand matrix"),
            ("B", "Focus board (postflop)"),
            ("Esc", "Hide window"),
            ("\u2318 Shift Space", "Show / hide overlay"),
            ("?", "Show this help"),
        ]
        for key, desc in shortcuts:
            row = tk.Frame(win, bg=self.BG)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=key, bg='#222f40', fg='#bfe2ff', font=('Menlo', 10, 'bold'),
                     width=14, anchor='w', padx=8, pady=3).pack(side='left')
            tk.Label(row, text=desc, bg=self.BG, fg='#9baec3', font=('Helvetica', 11),
                     anchor='w').pack(side='left', padx=8)
        tk.Label(win, text="Tips: Type a hand like AKs, JJ, T9o for instant advice.\nUse Auto-read to capture cards from GGPoker.",
                 bg=self.BG, fg='#6b7280', font=('Helvetica', 10), justify='left').pack(anchor='w', pady=(16, 0))
        ttk.Button(win, text="Close", command=win.destroy).pack(anchor='e', pady=(16, 0))
        win.bind('<Escape>', lambda e: win.destroy())
        win.focus_set()

    # --- Keyboard shortcuts ---
    def _on_key_shortcut(self, event):
        # Ignore if typing in an entry
        focused = self.root.focus_get()
        is_entry = isinstance(focused, tk.Entry)
        key = event.keysym.lower() if event.keysym else ""
        # Always allow Esc and ?
        if key == "escape":
            if getattr(self, 'auto_act_var', None) and self.auto_act_var.get():
                self._emergency_stop_auto_act()
            return  # handled by root binding
        if key == "x" and (event.state & 0x1) and (event.state & 0x4 or event.state & 0x8):
            self._emergency_stop_auto_act()
            return "break"
        if key == "question" or event.char == "?":
            self._show_help()
            return "break"
        if is_entry and key not in ("escape", "question"):
            # Don't hijack typing, except for specific combos
            if key == "r" and (event.state & 0x4):  # Ctrl+R
                pass
            else:
                return
        if key == "h":
            self.hand_entry.focus_set()
            self.hand_entry.select_range(0, tk.END)
            return "break"
        if key == "o":
            self.kind_var.set("open")
            self._on_spot_change()
            return "break"
        if key == "f":
            self.kind_var.set("facing_open")
            self._on_spot_change()
            return "break"
        if key == "i":
            self.kind_var.set("iso_raise")
            self._on_spot_change()
            return "break"
        if key == "s":
            self.kind_var.set("squeeze")
            self._on_spot_change()
            return "break"
        if key == "t" or event.char == "#":
            self.kind_var.set("facing_3bet")
            self._on_spot_change()
            return "break"
        if key == "q" or event.char == "$":
            self.kind_var.set("facing_4bet")
            self._on_spot_change()
            return "break"
        pos_keys = {"1": "BTN", "2": "SB", "3": "BB", "4": "UTG", "5": "MP", "6": "CO"}
        if event.char in pos_keys:
            self.pos_var.set(pos_keys[event.char])
            self._on_position_change()
            return "break"
        if key == "r":
            self.show_range_var.set(not self.show_range_var.get())
            self._toggle_range_grid()
            return "break"
        if key == "b" and self.mode == "postflop":
            self.board_entry.focus_set()
            return "break"


def try_install_hotkey(root: tk.Tk, app: RTAApp):
    try:
        from pynput import keyboard
    except ImportError:
        return False

    def toggle():
        root.after(0, lambda: root.deiconify() if not root.winfo_viewable()
                   else root.withdraw())

    # Cmd+Space on macOS conflicts with Spotlight; use Cmd+Shift+Space there,
    # Ctrl+Space elsewhere.
    import sys as _sys
    if _sys.platform == "darwin":
        combo = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.Key.space}
    else:
        combo = {keyboard.Key.ctrl, keyboard.Key.space}

    current = set()

    def on_press(key):
        if key in combo:
            current.add(key)
            if current == combo:
                toggle()

    def on_release(key):
        current.discard(key)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()
    return True


def main():
    import sys as _sys
    root = tk.Tk()
    app = RTAApp(root)
    args = set(_sys.argv[1:])
    if '--auto-read' in args and not app.ocr_var.get():
        app.ocr_var.set(True)
        app._toggle_ocr()
    if '--auto-act' in args and hasattr(app, 'auto_act_var') and not app.auto_act_var.get():
        app.auto_act_var.set(True)
        app._on_autonomy_settings_change()
        if hasattr(app, '_auto_actor') and app._auto_actor is not None:
            app._auto_actor.enabled = True
        if hasattr(app, 'auto_act_status_var'):
            mode_tag = ' (Dry-run)' if getattr(app._auto_actor.config, 'dry_run', False) else ''
            app.auto_act_status_var.set(f'Autonomous mode: Armed{mode_tag}')
    if '--compact' in args and hasattr(app, 'compact'):
        root.after(100, app.compact.show)
    ok = try_install_hotkey(root, app)
    if not ok:
        print("Tip: pip install pynput for global hotkey (Cmd/Ctrl+Space toggle).")
    root.mainloop()


if __name__ == "__main__":
    main()
