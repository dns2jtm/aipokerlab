"""
Multi-Table Support for Poker RTA

This module provides functionality to detect and manage multiple poker clients and tables,
allowing users to switch between tables and monitor the active one.
"""

import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field, replace
from enum import Enum


class TableState(Enum):
    """Represents the state of a detected table."""
    ACTIVE = "active"      # Currently focused/being monitored
    INACTIVE = "inactive"  # Detected but not focused
    LOST = "lost"          # Previously detected but no longer found


@dataclass
class PokerTable:
    """Represents a detected poker table."""
    table_id: str
    name: str              # Table name (e.g., "NLHP White 18 - 200 / 500")
    process_name: str      # Process name (e.g., "GGnet")
    bounds: tuple          # (x, y, w, h) window bounds
    window_id: Optional[int] = None
    client: str = 'ggpoker'
    visible: bool = True
    is_frontmost: bool = False
    stakes: Optional[str] = None  # Extracted stakes info
    detected_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    state: TableState = TableState.INACTIVE
    
    def __hash__(self):
        return hash(self.table_id)
    
    def __eq__(self, other):
        if not isinstance(other, PokerTable):
            return False
        return self.table_id == other.table_id


class MultiTableManager:
    """
    Manages detection and switching between multiple poker tables.
    
    Features:
    - Detects GGPoker, PokerStars and PokerFair table windows
    - Tracks table state (active/inactive/lost)
    - Auto-switches to frontmost table when it gains focus
    - Provides callbacks for table state changes
    """
    
    def __init__(self):
        self._tables: Dict[str, PokerTable] = {}
        self._active_table_id: Optional[str] = None
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[str, PokerTable, TableState], None]] = []
        self._poll_interval = 1.0
        self._wake = threading.Event()
        self._follow_focus = True
    
    def add_callback(self, callback: Callable[[str, PokerTable, TableState], None]):
        """
        Add a callback for table state changes.
        
        Args:
            callback: Function(table_id, table, new_state) called on state changes
        """
        self._callbacks.append(callback)
        return callback
    
    def remove_callback(self, callback: Callable[[str, PokerTable, TableState], None]):
        """Remove a previously added callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _extract_stakes(self, table_name):
        from table_context import parse_blinds, format_amount
        blinds = parse_blinds(table_name)
        return '/'.join(format_amount(value) for value in blinds) if blinds else None

    def detect_tables(self):
        from ocr import find_all_poker_tables
        result = {}
        for window in find_all_poker_tables():
            client = window.get('client', 'ggpoker')
            window_id = window.get('window_id')
            table_id = f"window_{window_id}" if window_id is not None else f"{client}:{window['name']}:{window['bounds']}"
            result[table_id] = PokerTable(
                table_id=table_id, name=window['name'], bounds=window['bounds'],
                process_name=window.get('process_name', 'GGnet'), window_id=window_id,
                client=client, visible=window.get('visible', True),
                is_frontmost=window.get('is_frontmost', False), stakes=self._extract_stakes(window['name']))
        return result

    def refresh(self):
        """Reconcile one discovery snapshot; invoke callbacks after releasing the lock."""
        current = self.detect_tables()
        notifications = []
        with self._lock:
            selected = self._active_table_id
            if self._follow_focus:
                front = next((key for key, table in current.items() if table.is_frontmost and table.visible), None)
                selected = front or (selected if selected in current else next(iter(current), None))
            elif selected not in current:
                selected = None  # A pinned table closing must not redirect capture.
            for key, old in self._tables.items():
                if key not in current:
                    notifications.append((key, replace(old, state=TableState.LOST), TableState.LOST))
            for key, table in current.items():
                previous = self._tables.get(key)
                if previous:
                    table.detected_at = previous.detected_at
                table.state = TableState.ACTIVE if key == selected else TableState.INACTIVE
                if previous is None or previous.state != table.state:
                    notifications.append((key, replace(table), table.state))
            self._tables = current
            self._active_table_id = selected
        for args in notifications:
            self._notify_callbacks(*args)

    def set_follow_focus(self, enabled):
        with self._lock:
            self._follow_focus = bool(enabled)
        self._wake.set()

    def _notify_callbacks(self, table_id: str, table: PokerTable, new_state: TableState):
        """Notify all registered callbacks of a state change."""
        for callback in self._callbacks:
            try:
                callback(table_id, table, new_state)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def _monitor_loop(self):
        while self._running:
            try:
                self.refresh()
            except Exception as exc:
                print(f'Monitor loop error: {exc}')
            self._wake.wait(self._poll_interval)
            self._wake.clear()

    def start_monitoring(self):
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        self._running = False
        self._wake.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None

    def get_tables(self) -> Dict[str, PokerTable]:
        """
        Get all currently tracked tables.
        
        Returns:
            Dictionary mapping table_id to PokerTable objects
        """
        with self._lock:
            return {key: replace(table) for key, table in self._tables.items()}
    
    def get_active_table(self) -> Optional[PokerTable]:
        """
        Get the currently active table.
        
        Returns:
            PokerTable object or None if no active table
        """
        with self._lock:
            if self._active_table_id and self._active_table_id in self._tables:
                return replace(self._tables[self._active_table_id])
            return None
    
    def get_active_table_id(self) -> Optional[str]:
        """Get the ID of the currently active table."""
        with self._lock:
            return self._active_table_id
    
    def set_active_table(self, table_id):
        notifications = []
        with self._lock:
            if table_id not in self._tables:
                return False
            self._follow_focus = False
            self._active_table_id = table_id
            for key, table in self._tables.items():
                state = TableState.ACTIVE if key == table_id else TableState.INACTIVE
                if state != table.state:
                    table.state = state
                    notifications.append((key, replace(table), state))
        for args in notifications:
            self._notify_callbacks(*args)
        return True

    def get_table_display_name(self, table):
        client = {'ggpoker': 'GGPoker', 'pokerstars': 'PokerStars', 'pokerfair': 'PokerFair'}.get(table.client, table.process_name)
        # Avoid exposing the account name from a PokerStars window title.
        name = table.name.split(' - Logged In as ')[0]
        status = ' · hidden' if not table.visible else ''
        identity = f' · #{table.window_id}' if table.window_id is not None else ''
        return f'{client} · {name}{identity}{status}'

    def get_table_list(self) -> List[tuple]:
        """
        Get a sorted list of tables for display in a dropdown.
        
        Returns:
            List of (display_name, table_id) tuples, active table first
        """
        with self._lock:
            tables = list(self._tables.values())
            
            # Sort: active first, then by name
            def sort_key(t):
                is_active = t.state == TableState.ACTIVE
                return (not is_active, t.name)
            
            tables.sort(key=sort_key)
            
            result = []
            for table in tables:
                display_name = self.get_table_display_name(table)
                if table.state == TableState.ACTIVE:
                    display_name = "● " + display_name  # Add bullet for active
                result.append((display_name, table.table_id))
            
            return result


# Global instance for use across modules
_manager: Optional[MultiTableManager] = None


def get_multitable_manager() -> MultiTableManager:
    """Get or create the global MultiTableManager instance."""
    global _manager
    if _manager is None:
        _manager = MultiTableManager()
    return _manager


def detect_all_tables() -> Dict[str, PokerTable]:
    """Convenience function to detect all tables."""
    return get_multitable_manager().detect_tables()


def get_active_table() -> Optional[PokerTable]:
    """Convenience function to get the active table."""
    return get_multitable_manager().get_active_table()
