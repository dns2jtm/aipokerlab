"""
OCR module for the RTA: captures the GGPoker table window and reads hole cards.
 
Approach:
    1. Find the GGPoker table window via Quartz (AppleScript fallback).
  2. Screenshot just that window with `screencapture -l<windowid>` (no deps).
  3. Crop the hole-card region (configurable, relative to window size).
  4. Read rank + suit by template matching on the card glyphs (PIL only).
 
Dependencies: Pillow; pyobjc-framework-Quartz for direct macOS window capture.
 
Note on detection risk: screencapture and AppleScript window queries are
normal OS operations used by countless apps (Slack, Zoom, OBS). The poker
client cannot distinguish this from ordinary screen sharing.
"""

import os
import re
import subprocess
import tempfile
import configparser
import time
import weakref
import gc
import sys
from detection_state import CardReading
from functools import lru_cache
from typing import Dict, Optional, Tuple, Any, List, Union

try:
    from PIL import Image
    import numpy as np
    HAS_PIL = True
    HAS_NUMPY = True
except ImportError:
    try:
        from PIL import Image
        HAS_PIL = True
        HAS_NUMPY = False
    except ImportError:
        HAS_PIL = False
        HAS_NUMPY = False

# Import position detector
try:
    from position_detector import PositionDetector, detect_position_and_spot as _detect_position_and_spot, Position, Spot
    HAS_POSITION_DETECTOR = True
except ImportError:
    HAS_POSITION_DETECTOR = False
    PositionDetector = None
    Position = None
    Spot = None

# Multi-table support
try:
    from multitable import get_multitable_manager, PokerTable
    HAS_MULTITABLE = True
except ImportError:
    HAS_MULTITABLE = False
    PokerTable = None

# Configuration file for learned positions
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")

# OCR Status tracking
class OCRStatus:
    """Tracks OCR detection status for visual feedback."""
    WATCHING = "watching"
    DETECTED = "detected"
    ERROR = "error"
    RETRYING = "retrying"
    
    _current_status = WATCHING
    _status_message = "Ready"
    _last_hand = None
    _retry_count = 0
    _last_detection_time = 0
    
    @classmethod
    def set_status(cls, status: str, message: str = ""):
        cls._current_status = status
        cls._status_message = message
        if status == cls.DETECTED:
            cls._retry_count = 0
            
    @classmethod
    def get_status(cls) -> Tuple[str, str]:
        return cls._current_status, cls._status_message
    
    @classmethod
    def get_last_hand(cls) -> Optional[str]:
        return cls._last_hand
    
    @classmethod
    def set_last_hand(cls, hand: Optional[str]):
        cls._last_hand = hand
        if hand:
            cls._last_detection_time = time.time()
            
    @classmethod
    def increment_retry(cls):
        cls._retry_count += 1
        
    @classmethod
    def get_retry_count(cls) -> int:
        return cls._retry_count
    
    @classmethod
    def reset_retry(cls):
        cls._retry_count = 0


# Performance optimization classes
class WindowPositionCache:
    """Caches window positions to avoid repeated AppleScript calls."""
    
    def __init__(self, ttl: int = 30):
        """
        Initialize cache with time-to-live.
        
        Args:
            ttl: Time-to-live in seconds (default 30)
        """
        self._cache: Dict[str, Tuple[Tuple[int, int, int, int], float]] = {}
        self._ttl = ttl
    
    def get(self, key: str) -> Optional[Tuple[int, int, int, int]]:
        """
        Get cached window position.
        
        Args:
            key: Cache key (e.g., client name)
            
        Returns:
            Window bounds (x, y, w, h) or None if not cached/expired
        """
        if key not in self._cache:
            return None
        
        bounds, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        
        return bounds
    
    def set(self, key: str, bounds: Tuple[int, int, int, int]):
        """
        Cache window position.
        
        Args:
            key: Cache key
            bounds: Window bounds (x, y, w, h)
        """
        self._cache[key] = (bounds, time.time())
    
    def clear(self):
        """Clear all cached positions."""
        self._cache.clear()
    
    def cleanup(self):
        """Remove expired entries."""
        current_time = time.time()
        expired = [k for k, (_, ts) in self._cache.items()
                   if current_time - ts > self._ttl]
        for k in expired:
            del self._cache[k]


class SleepModeManager:
    """Manages sleep mode for OCR when away from table."""
    
    def __init__(self, timeout: int = 300):
        """
        Initialize sleep mode manager.
        
        Args:
            timeout: Timeout in seconds before entering sleep mode (default 300)
        """
        self._enabled = False
        self._active = False
        self._timeout = timeout
        self._last_activity = time.time()
        self._activity_handlers: List[callable] = []
    
    @property
    def is_sleeping(self) -> bool:
        """Check if currently in sleep mode."""
        if not self._enabled:
            return False
        return self._active or (time.time() - self._last_activity > self._timeout)
    
    def enable(self):
        """Enable sleep mode."""
        self._enabled = True
        self._last_activity = time.time()
    
    def disable(self):
        """Disable sleep mode."""
        self._enabled = False
        self._active = False
    
    def toggle(self) -> bool:
        """Toggle sleep mode. Returns new state."""
        self._enabled = not self._enabled
        if self._enabled:
            self._last_activity = time.time()
        return self._enabled
    
    def record_activity(self):
        """Record user activity to prevent sleep mode."""
        self._last_activity = time.time()
        self._active = False
    
    def force_sleep(self):
        """Force enter sleep mode."""
        self._active = True
    
    def force_wake(self):
        """Force wake from sleep mode."""
        self._active = False
        self._last_activity = time.time()
    
    def set_timeout(self, timeout: int):
        """Set sleep mode timeout."""
        self._timeout = timeout


class MemoryMonitor:
    """Monitors and manages memory usage."""
    
    def __init__(self, threshold_mb: int = 200):
        """
        Initialize memory monitor.
        
        Args:
            threshold_mb: Memory threshold in MB before cleanup (default 200)
        """
        self._threshold_bytes = threshold_mb * 1024 * 1024
        self._image_cache: List[weakref.ref] = []
        self._cache_threshold = 10  # Max cached images
    
    def track_image(self, img: Image.Image):
        """
        Track an image for potential cleanup.
        
        Args:
            img: PIL Image to track
        """
        ref = weakref.ref(img)
        self._image_cache.append(ref)
        
        # Remove old dead references
        self._image_cache = [r for r in self._image_cache if r() is not None]
        
        # Limit cache size
        if len(self._image_cache) > self._cache_threshold:
            # Remove oldest entries
            self._image_cache = self._image_cache[-self._cache_threshold:]
    
    def get_memory_usage_mb(self) -> float:
        """
        Get approximate memory usage.
        
        Returns:
            Memory usage in MB
        """
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / (1024 * 1024 if sys.platform == 'darwin' else 1024)
        except (ImportError, AttributeError):
            return 0.0
    
    def needs_cleanup(self) -> bool:
        """
        Check if memory cleanup is needed.
        
        Returns:
            True if memory usage exceeds threshold
        """
        return self.get_memory_usage_mb() > (self._threshold_bytes / 1024 / 1024)
    
    def cleanup(self):
        """Perform memory cleanup."""
        # Clear dead references
        self._image_cache = [r for r in self._image_cache if r() is not None]
        
        # Force garbage collection
        gc.collect()
    
    def set_threshold(self, threshold_mb: int):
        """Set memory threshold for cleanup."""
        self._threshold_bytes = threshold_mb * 1024 * 1024


# Global performance instances
_window_cache = WindowPositionCache(ttl=30)
_sleep_manager = SleepModeManager(timeout=300)
_memory_monitor = MemoryMonitor(threshold_mb=200)


def get_window_cache() -> WindowPositionCache:
    """Get the global window position cache."""
    return _window_cache


def get_sleep_manager() -> SleepModeManager:
    """Get the global sleep mode manager."""
    return _sleep_manager


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor."""
    return _memory_monitor


def load_config() -> Dict[str, Any]:
    """Load configuration from config.ini."""
    config = {
        'poll_interval_active': 1.0,
        'poll_interval_idle': 5.0,
        'window_position_cache_ttl': 30,
        'enable_sleep_mode': False,
        'sleep_mode_timeout': 300,
        'memory_cleanup_threshold': 200,
        'enable_lazy_loading': True
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            parser = configparser.ConfigParser()
            parser.read(CONFIG_FILE)
            
            if 'ocr' in parser:
                config['poll_interval_active'] = float(parser.get('ocr', 'poll_interval_active', fallback=1.0))
                config['poll_interval_idle'] = float(parser.get('ocr', 'poll_interval_idle', fallback=5.0))
                config['window_position_cache_ttl'] = int(parser.get('ocr', 'window_position_cache_ttl', fallback=30))
            
            if 'performance' in parser:
                config['enable_sleep_mode'] = parser.get('performance', 'enable_sleep_mode', fallback='false').lower() == 'true'
                config['sleep_mode_timeout'] = int(parser.get('performance', 'sleep_mode_timeout', fallback=300))
                config['memory_cleanup_threshold'] = int(parser.get('performance', 'memory_cleanup_threshold', fallback=200))
                config['enable_lazy_loading'] = parser.get('performance', 'enable_lazy_loading', fallback='true').lower() == 'true'
        except Exception:
            pass
    
    return config


# Apply config to global instances
_config = load_config()
_window_cache = WindowPositionCache(ttl=_config['window_position_cache_ttl'])
_sleep_manager = SleepModeManager(timeout=_config['sleep_mode_timeout'])
_memory_monitor = MemoryMonitor(threshold_mb=_config['memory_cleanup_threshold'])


def load_learned_positions() -> Dict[str, Any]:
    """Load learned card positions from config file."""
    positions = {}
    if os.path.exists(CONFIG_FILE):
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            
            if 'card_positions' in config:
                for key, value in config['card_positions'].items():
                    try:
                        # Parse stored position data
                        parts = value.split(',')
                        if len(parts) == 4:
                            positions[key] = {
                                'x': float(parts[0]),
                                'y': float(parts[1]),
                                'w': float(parts[2]),
                                'h': float(parts[3])
                            }
                    except (ValueError, IndexError):
                        continue
        except Exception:
            pass
    return positions


def save_learned_position(client: str, region: Dict[str, float]):
    """Save learned card position to config file."""
    try:
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
        
        if 'card_positions' not in config:
            config['card_positions'] = {}
        
        key = f"{client}_hole_cards"
        config['card_positions'][key] = f"{region['x']},{region['y']},{region['w']},{region['h']}"
        
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
    except Exception:
        pass


def get_retry_delay(attempt: int) -> float:
    """Calculate exponential backoff delay (1s, 2s, 4s, 8s max)."""
    # Start at 1 second, double each time, max 8 seconds
    delay = min(2 ** attempt, 8)
    return delay

# ---------------------------------------------------------------------------
# Color normalization (from DeeperMind's adjust_colors)
# ---------------------------------------------------------------------------

def adjust_colors(img_array, tol=120):
    """
    Normalize card colors before template matching.
    
    Based on DeeperMind's adjust_colors() function from table_scraper_nn.py.
    This improves robustness for different table themes by normalizing
    card colors to standard values.
    
    Args:
        img_array: numpy array of image (H, W, 3) in RGB format
        tol: tolerance for color matching (default 120)
    
    Returns:
        Normalized numpy array with standardized colors
    """
    if not HAS_NUMPY:
        return img_array
    
    # Define colors to be worked upon (red, green, black, white, blue)
    colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 0], [255, 255, 255], [0, 0, 255]])
    
    # Mask of all elements that are closest to one of the colors
    mask0 = np.isclose(img_array, colors[:, None, None, :], atol=tol).all(-1)
    
    # Select the valid elements for edit. Sets all nearish colors to exact ones
    out = np.where(mask0.any(0)[..., None], colors[mask0.argmax(0)], img_array)
    
    # Finally set all green to black
    out[(out == colors[1]).all(-1)] = colors[2]
    
    # Finally set all blue to red
    out[(out == colors[4]).all(-1)] = colors[0]
    
    return out.astype(np.uint8)


def normalize_card_colors(img):
    """
    Apply color normalization to a PIL Image for improved OCR.
    
    Args:
        img: PIL Image
    
    Returns:
        PIL Image with normalized colors (or original if numpy not available)
    """
    if not HAS_NUMPY or not HAS_PIL:
        return img
    
    try:
        # Convert PIL to numpy array
        img_array = np.array(img.convert("RGB"))
        
        # Apply color normalization
        normalized_array = adjust_colors(img_array)
        
        # Convert back to PIL
        return Image.fromarray(normalized_array)
    except Exception:
        return img


# ---------------------------------------------------------------------------
# Window discovery (macOS AppleScript)
# ---------------------------------------------------------------------------

# PokerFair-specific configuration
# These are the screen coordinates for the PokerFair table window
# Set these manually by running: python3 ocr.py pokerfair-config "x,y,w,h"
POKERFAIR_WINDOW = None  # (x, y, w, h) in logical screen coordinates


def find_pokerfair_window():
    """Find PokerFair (PokerStarsOnBetfair) window.

    PokerFair uses an Electron-based window that doesn't expose windows via
    System Events. We first check for a manually configured window position,
    then fall back to detecting the green felt area on screen.

    Returns (x, y, w, h) bounds or None if not found.
    """
    global POKERFAIR_WINDOW
    if not HAS_PIL:
        return None

    # First try the configured window position
    if POKERFAIR_WINDOW:
        return POKERFAIR_WINDOW

    # Capture full screen
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        subprocess.run(["screencapture", "-x", path],
                       capture_output=True, timeout=5)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return None
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    # Look for green felt area (poker tables have distinctive green)
    pixels = img.load()
    w, h = img.size

    # Scan for large green regions
    green_threshold = 25  # minimum green dominance
    min_table_area = 100000  # minimum pixels for a valid table

    # Find bounding box of green areas using connected components approach
    green_pixels = []
    for y in range(0, h, 3):  # sample every 3rd row for speed
        for x in range(0, w, 3):
            r, g, b = pixels[x, y]
            # Green felt: G > R and G > B by significant margin
            if g > r + green_threshold and g > b + green_threshold:
                green_pixels.append((x, y))

    if not green_pixels:
        return None

    # Calculate bounding box
    min_x = min(p[0] for p in green_pixels)
    max_x = max(p[0] for p in green_pixels)
    min_y = min(p[1] for p in green_pixels)
    max_y = max(p[1] for p in green_pixels)

    table_w = max_x - min_x
    table_h = max_y - min_y

    if table_w * table_h < min_table_area:
        return None

    # Expand bounding box to include the full table area
    # Add margin around the felt to capture the entire window
    margin_x = int(table_w * 0.15)
    margin_y = int(table_h * 0.15)

    x = max(0, min_x - margin_x)
    y = max(0, min_y - margin_y)
    w = min(img.size[0] - x, table_w + 2 * margin_x)
    h = min(img.size[1] - y, table_h + 2 * margin_y)

    return (x, y, w, h)


_WINDOW_IDS = {}
_WINDOW_CLIENTS = {}

from contextvars import ContextVar
_capture_client = ContextVar('poker_capture_client', default=None)


def _get_client():
    return _capture_client.get() or _CLIENT


def _poker_client(owner):
    compact = re.sub(r'[^a-z0-9]', '', owner.lower())
    if compact in ('ggnet', 'ggpoker') or compact.startswith('ggpoker'):
        return 'ggpoker'
    if compact.startswith('pokerstars'):
        return 'pokerstars'
    if compact.startswith('pokerfair'):
        return 'pokerfair'
    return None


def _is_table_title(name):
    if re.search(r'\b(?:lobby|cashier|settings|preferences|hand history|replayer|replay)\b', name, re.I):
        return False
    from table_context import parse_blinds
    return bool(parse_blinds(name) or re.search(r'\b(?:NLH[PE]?|PLO|OMAHA|HOLD.EM)\b|\bTable\s+\d+\b', name, re.I))


def _quartz_tables():
    """Read table IDs and logical bounds without Accessibility/AppleScript.

    None means Quartz is unavailable; an empty list means no table windows.
    Window IDs let capture read the table even when the overlay covers it.
    """
    try:
        import Quartz
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
        onscreen = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
        visible_ids = {int(w['kCGWindowNumber']) for w in onscreen or []}
        tables = []
        for window in windows or []:
            owner = str(window.get('kCGWindowOwnerName', ''))
            client = _poker_client(owner)
            name = str(window.get('kCGWindowName') or '')
            if client is None:
                continue
            if window.get('kCGWindowLayer') != 0:
                continue
            # Exclude the lobby, cashier and utility dialogs.
            if not name or not _is_table_title(name):
                continue
            b = window['kCGWindowBounds']
            bounds = tuple(int(b[k]) for k in ('X', 'Y', 'Width', 'Height'))
            if bounds[2] < 300 or bounds[3] < 200:
                continue
            tables.append({'name': name, 'bounds': bounds,
                           'window_id': int(window['kCGWindowNumber']),
                           'process_name': owner, 'client': client,
                           'process_id': int(window.get('kCGWindowOwnerPID', 0)),
                           'visible': int(window['kCGWindowNumber']) in visible_ids,
                           'is_frontmost': False})
        front = next((table for table in tables if table['visible']), None)
        if front:
            front['is_frontmost'] = True
        tables.sort(key=lambda table: not table['visible'])
        return tables
    except (ImportError, AttributeError, RuntimeError):
        return None


def find_poker_window(table_name=None, window_id=None):
    """Select exactly one discovered table; a missing requested window never falls back."""
    global _CLIENT
    tables = find_all_poker_tables()
    for table in tables:
        if window_id is not None and table.get('window_id') != window_id:
            continue
        if window_id is None and table_name is not None and table['name'] != table_name:
            continue
        _CLIENT = table.get('client', 'ggpoker')  # Legacy single-threaded callers.
        if table.get('window_id') is not None:
            _WINDOW_IDS[table['bounds']] = table['window_id']
        return table['bounds']
    return None


def find_ggpoker_window(table_name=None):
    """Compatibility alias for multi-client table discovery."""
    return find_poker_window(table_name=table_name)


def find_all_poker_tables():
    tables = _quartz_tables()
    if tables is None:
        tables = _legacy_find_all_ggpoker_tables()
    for table in tables:
        if table.get('window_id') is not None:
            _WINDOW_IDS[table['bounds']] = table['window_id']
            _WINDOW_CLIENTS[table['window_id']] = table.get('client', 'ggpoker')
    return tables


def find_all_ggpoker_tables():
    """Compatibility alias; now returns every supported poker client."""
    return find_all_poker_tables()


def _legacy_find_all_ggpoker_tables() -> List[Dict[str, Any]]:
    """Find all GGPoker table windows.

    Returns:
        List of dictionaries with table info:
        - name: Table name
        - bounds: (x, y, w, h)
        - is_frontmost: Whether this is the frontmost window
    """
    result = []
    
    tables = _quartz_tables()
    if tables is not None:
        _WINDOW_IDS.update((t['bounds'], t['window_id']) for t in tables)
        return tables
    script = r'''
    tell application "System Events"
        set output to ""
        set ggnet_proc to first process whose name is "GGnet"
        if ggnet_proc exists then
            set front_win_name to ""
            try
                set front_win_name to name of (first window of ggnet_proc)
            end try
            repeat with w in (every window of ggnet_proc)
                try
                    set n to name of w
                    set pos to position of w
                    set siz to size of w
                    set is_front to (n is front_win_name)
                    set output to output & n & "|" & item 1 of pos & "," & item 2 of pos & "|" & item 1 of siz & "x" & item 2 of siz & "|" & is_front & linefeed
                end try
            end repeat
        end if
        return output
    end tell
    '''
    try:
        out = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return result
    
    for line in out.stdout.splitlines():
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        
        name = parts[0]
        size = parts[-2]
        pos = parts[-3]
        is_frontmost = parts[-1].lower() == 'true'
        
        # Skip the launcher window
        if name.lower() == "ggpoker":
            continue
        
        try:
            x, y = (int(v) for v in pos.split(","))
            w, h = (int(v) for v in size.split("x"))
        except ValueError:
            continue
        
        result.append({
            'name': name,
            'bounds': (x, y, w, h),
            'is_frontmost': is_frontmost
        })
    
    return result


def _window_id(proc_name, win_prefix):
    # use 'contains' + a unique prefix; avoids exact-name unicode issues
    safe = win_prefix.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "System Events"
        tell process "{proc_name}"
            set w to first window whose (name begins with "{safe[:20]}")
            if missing value then error "no window"
            return id of w
        end tell
    end tell
    '''
    try:
        out = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=5)
        return int(out.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        return None


def _window_bounds(proc_name, win_prefix):
    safe = win_prefix.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "System Events"
        tell process "{proc_name}"
            set w to first window whose (name begins with "{safe[:20]}")
            if missing value then error "no window"
            set b to position of w
            set s to size of w
            return (item 1 of b) & "," & (item 2 of b) & "," & (item 1 of s) & "," & (item 2 of s)
        end tell
    end tell
    '''
    try:
        out = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=5)
        x, y, w, h = (int(v) for v in out.stdout.strip().split(","))
        return (x, y, w, h)
    except (ValueError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------------------
# Multi-Monitor Support
# ---------------------------------------------------------------------------

# Cache for display information
_DISPLAY_INFO_CACHE = None
_DISPLAY_INFO_TIMESTAMP = 0
_DISPLAY_INFO_TTL = 30  # Cache display info for 30 seconds


def get_display_info() -> List[Dict[str, Any]]:
    """
    Get information about all connected displays.
    
    Returns:
        List of dictionaries with display info:
        - bounds: (x, y, width, height) in logical points
        - pixel_bounds: (x, y, width, height) in physical pixels
        - scale: Scale factor (physical / logical)
        - is_main: Whether this is the main display
        - display_id: Display identifier
    """
    global _DISPLAY_INFO_CACHE, _DISPLAY_INFO_TIMESTAMP
    
    # Check cache
    current_time = time.time()
    if _DISPLAY_INFO_CACHE is not None and (current_time - _DISPLAY_INFO_TIMESTAMP) < _DISPLAY_INFO_TTL:
        return _DISPLAY_INFO_CACHE
    
    displays = []
    
    # Use System Events to get display information
    script = '''
    tell application "System Events"
        set output to ""
        set screens to every screen of every application process whose name is "Finder"
        if (count of screens) = 0 then
            -- Fallback: get desktop bounds
            set bounds to bounds of window of desktop
            set output to "0,0," & ((item 3 of bounds) - (item 1 of bounds)) & "," & ((item 4 of bounds) - (item 2 of bounds)) & "|1|true|0"
        else
            repeat with i from 1 to (count of screens)
                try
                    set s to screen i
                    set bounds to bounds of s
                    set width to width of s
                    set height to height of s
                    -- bounds are in format {x, y, width, height}
                    set output to output & (item 1 of bounds) & "," & (item 2 of bounds) & "," & (item 3 of bounds) & "," & (item 4 of bounds) & "|" & width & "|" & (i = 1) & "|" & i & linefeed
                end try
            end repeat
        end if
        return output
    end tell
    '''
    
    try:
        out = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=10)
        
        for line in out.stdout.strip().splitlines():
            if not line:
                continue
            
            parts = line.split("|")
            if len(parts) < 4:
                continue
            
            try:
                bounds_str = parts[0]
                bounds_parts = bounds_str.split(",")
                x, y, w, h = int(bounds_parts[0]), int(bounds_parts[1]), int(bounds_parts[2]), int(bounds_parts[3])
                
                # Get physical pixel dimensions (for scale calculation)
                # We'll calculate scale by comparing with actual screenshot
                is_main = parts[2].lower() == 'true'
                display_id = int(parts[3]) if len(parts) > 3 else 0
                
                # Default scale of 1.0, will be refined later
                scale = 1.0
                
                displays.append({
                    'bounds': (x, y, w, h),
                    'pixel_bounds': (x, y, int(w * scale), int(h * scale)),
                    'scale': scale,
                    'is_main': is_main,
                    'display_id': display_id
                })
            except (ValueError, IndexError):
                continue
                
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Fallback: assume single display
        pass
    
    # If no displays found, use fallback
    if not displays:
        logical = _logical_screen_size()
        if logical:
            displays.append({
                'bounds': (0, 0, logical[0], logical[1]),
                'pixel_bounds': (0, 0, logical[0], logical[1]),
                'scale': 1.0,
                'is_main': True,
                'display_id': 0
            })
    
    # Cache the result
    _DISPLAY_INFO_CACHE = displays
    _DISPLAY_INFO_TIMESTAMP = current_time
    
    return displays


def window_on_display(window_bounds: Tuple[int, int, int, int],
                      displays: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Determine which display a window is on based on its bounds.
    
    Args:
        window_bounds: Window bounds (x, y, w, h) in logical points
        displays: List of display info (will fetch if None)
        
    Returns:
        Display info dictionary if found, None otherwise
    """
    if displays is None:
        displays = get_display_info()
    
    if not displays:
        return None
    
    x, y, w, h = window_bounds
    window_center_x = x + w / 2
    window_center_y = y + h / 2
    
    # Find the display whose bounds contain the window center
    for display in displays:
        dx, dy, dw, dh = display['bounds']
        if (dx <= window_center_x < dx + dw and
            dy <= window_center_y < dy + dh):
            return display
    
    # Fallback: find display with most overlap
    best_display = None
    best_overlap = 0
    
    for display in displays:
        dx, dy, dw, dh = display['bounds']
        
        # Calculate overlap area
        overlap_x = max(0, min(x + w, dx + dw) - max(x, dx))
        overlap_y = max(0, min(y + h, dy + dh) - max(y, dy))
        overlap = overlap_x * overlap_y
        
        if overlap > best_overlap:
            best_overlap = overlap
            best_display = display
    
    return best_display


def get_display_scale(display_info: Dict[str, Any]) -> float:
    """
    Get the scale factor for a specific display.
    
    Args:
        display_info: Display info dictionary from get_display_info()
        
    Returns:
        Scale factor (physical pixels / logical points)
    """
    # For now, return cached scale
    # In a more advanced implementation, we could capture a known region
    # and compare physical vs logical dimensions
    return display_info.get('scale', 1.0)


def update_display_scales():
    """
    Update scale factors for all displays by comparing screenshot dimensions.
    
    This captures the full screen and compares the physical pixel dimensions
    with the logical bounds to calculate accurate scale factors.
    """
    global _DISPLAY_INFO_CACHE
    
    displays = get_display_info()
    if not displays:
        return
    
    # Capture full screen to get actual pixel dimensions
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    
    try:
        subprocess.run(["screencapture", "-x", path],
                       capture_output=True, timeout=5)
        
        if os.path.exists(path) and os.path.getsize(path) > 0:
            img = Image.open(path)
            physical_width = img.width
            physical_height = img.height
            
            # Calculate total logical size
            total_logical_width = sum(d['bounds'][2] for d in displays)
            total_logical_height = max(d['bounds'][3] for d in displays)
            
            # Calculate overall scale
            if total_logical_width > 0:
                overall_scale = physical_width / total_logical_width
            elif total_logical_height > 0:
                overall_scale = physical_height / total_logical_height
            else:
                overall_scale = 1.0
            
            # Update scale for all displays (assuming uniform scale for now)
            for display in displays:
                display['scale'] = overall_scale
                dx, dy, dw, dh = display['bounds']
                display['pixel_bounds'] = (
                    dx, dy,
                    int(dw * overall_scale),
                    int(dh * overall_scale)
                )
                
    except Exception:
        pass
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

_LOGICAL_SCREEN = None


def _logical_screen_size():
    """Return the logical (points) screen size, or None."""
    global _LOGICAL_SCREEN
    if _LOGICAL_SCREEN is not None:
        return _LOGICAL_SCREEN
    
    # Directly get screen size from Finder to avoid circular dependency
    # with get_display_info() which also calls this function
    script = 'tell application "Finder" to get bounds of window of desktop'
    try:
        out = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=5)
        left, top, right, bottom = (int(v.strip())
                                    for v in out.stdout.strip().split(","))
        _LOGICAL_SCREEN = (right - left, bottom - top)
        return _LOGICAL_SCREEN
    except Exception:
        _LOGICAL_SCREEN = None
    return _LOGICAL_SCREEN


def _quartz_capture_window(window_id):
    """Capture a window directly in memory via Quartz CGWindowListCreateImage."""
    try:
        import Quartz
        cg_img = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            int(window_id),
            Quartz.kCGWindowImageBoundsIgnoreFraming,
        )
        if cg_img is None:
            return None
        width = Quartz.CGImageGetWidth(cg_img)
        height = Quartz.CGImageGetHeight(cg_img)
        if not width or not height:
            return None
        provider = Quartz.CGImageGetDataProvider(cg_img)
        if provider is None:
            return None
        data = Quartz.CGDataProviderCopyData(provider)
        if not data:
            return None
        bytes_per_row = Quartz.CGImageGetBytesPerRow(cg_img)
        raw = bytes(data)
        if len(raw) < height * bytes_per_row:
            return None
        return Image.frombuffer(
            'RGBA', (width, height), raw, 'raw', 'BGRA', bytes_per_row, 1
        ).copy()
    except Exception:
        return None


def capture_window(rect, debug: bool = False, window_id=None):
    """Capture the given screen rect (x, y, w, h) via Quartz or screencapture.

    Uses the discovered window ID when available to exclude covering windows.
    Otherwise uses `screencapture -R` to capture the exact rect directly, which
    correctly handles multi-monitor setups with negative coordinates and
    Retina scaling. Falls back to full-screen capture + crop if -R fails.

    Args:
        rect: Screen rect (x, y, w, h) in logical points
        debug: If True, print debug information
        
    Returns:
        PIL Image of the cropped window, or None if capture fails
    """
    x, y, w, h = rect

    if window_id is None:
        window_id = _WINDOW_IDS.get(tuple(rect))
    if window_id is not None:
        img = _quartz_capture_window(window_id)
        if img is not None:
            memory_monitor = get_memory_monitor()
            memory_monitor.track_image(img)
            if memory_monitor.needs_cleanup():
                memory_monitor.cleanup()
            return img
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            try:
                subprocess.run(['screencapture', '-x', '-o', '-l', str(window_id), f.name],
                               capture_output=True, timeout=5)
                if os.path.getsize(f.name):
                    with Image.open(f.name) as captured:
                        return captured.convert('RGBA')
            except (OSError, subprocess.TimeoutExpired):
                pass
        # Do not read an unrelated foreground window if this table closed.
        return None
    
    if debug:
        print(f"  [DEBUG] Window bounds: ({x}, {y}, {w}, {h})")
    
    # Try direct rect capture first (handles multi-monitor correctly)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        # Use -R to capture specific rect - macOS handles coordinate translation
        result = subprocess.run(["screencapture", "-R", f"{int(x)},{int(y)},{int(w)},{int(h)}", "-x", path],
                       capture_output=True, timeout=5)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            img = Image.open(path).convert("RGBA")
            if debug:
                print(f"  [DEBUG] Direct rect capture succeeded: {img.size}")
            # Track image for memory management
            memory_monitor = get_memory_monitor()
            memory_monitor.track_image(img)
            if memory_monitor.needs_cleanup():
                memory_monitor.cleanup()
            return img
        if debug:
            print(f"  [DEBUG] Direct rect capture failed, falling back to full-screen crop")
    except Exception as e:
        if debug:
            print(f"  [DEBUG] Direct capture exception: {e}")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    
    # Fallback: full-screen capture + crop with proper multi-monitor offset handling
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        subprocess.run(["screencapture", "-x", path],
                       capture_output=True, timeout=5)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return None
        img = Image.open(path).convert("RGBA")
        
        # Calculate scale factor using logical screen size
        logical = _logical_screen_size()
        if logical and logical[0]:
            scale = img.width / logical[0]
        else:
            scale = 2.0 if img.width > 3000 else 1.0
        if debug:
            print(f"  [DEBUG] Fallback scale: {scale}, image size: {img.size}, logical: {logical}")
        
        # For multi-monitor, screenshot origin is at leftmost display
        # Need to offset negative coordinates
        displays = get_display_info()
        min_x = min((d['bounds'][0] for d in displays), default=0) if displays else 0
        min_y = min((d['bounds'][1] for d in displays), default=0) if displays else 0
        
        # Translate window coords to screenshot coords
        x_phys = int(round((x - min_x) * scale))
        y_phys = int(round((y - min_y) * scale))
        w_phys = int(round(w * scale))
        h_phys = int(round(h * scale))
        
        if debug:
            print(f"  [DEBUG] Fallback crop rect: ({x_phys}, {y_phys}, {w_phys}, {h_phys}) with offset ({min_x}, {min_y})")
        
        # Clamp to image bounds
        x_phys = max(0, min(x_phys, img.width - 1))
        y_phys = max(0, min(y_phys, img.height - 1))
        w_phys = max(1, min(w_phys, img.width - x_phys))
        h_phys = max(1, min(h_phys, img.height - y_phys))
        
        cropped = img.crop((x_phys, y_phys, x_phys + w_phys, y_phys + h_phys))
        
        memory_monitor = get_memory_monitor()
        memory_monitor.track_image(cropped)
        if memory_monitor.needs_cleanup():
            memory_monitor.cleanup()
        
        return cropped
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Card reading via template matching
# ---------------------------------------------------------------------------

# Hole-card region as fractions of window size (GGPoker default table).
# Calibrated against a live table: the two hole cards sit at the bottom
# centre, spanning roughly x 0.433..0.566, y 0.72..0.848.
CARD_REGION = {"x": 0.433, "y": 0.72, "w": 0.134, "h": 0.128}
CARD_GAP = 0.012  # gap between the two cards, as fraction of window width

# Per-client hole-card regions (fractions of the window size).
CARD_REGIONS = {
    "ggpoker": {"x": 0.433, "y": 0.72, "w": 0.134, "h": 0.128},
    "pokerstars": {"x": 0.43, "y": 0.625, "w": 0.14, "h": 0.075},
    "pokerfair": {"x": 0.438, "y": 0.48, "w": 0.124, "h": 0.06},
}

# Board card region (community cards in center of table)
# Board cards are typically in the center of the table, above the hole cards
BOARD_REGION = {"x": 0.27, "y": 0.40, "w": 0.46, "h": 0.18}
BOARD_CARD_SPACING = 0.05  # Horizontal spacing between board cards as fraction of window width
BOARD_MAX_CARDS = 5  # Maximum number of board cards (river)

# Per-client board regions
BOARD_REGIONS = {
    "ggpoker": dict(BOARD_REGION),
    "pokerstars": {"x": 0.38, "y": 0.40, "w": 0.24, "h": 0.15},
    "pokerfair": {"x": 0.38, "y": 0.40, "w": 0.24, "h": 0.15},
}

# Action history region (bottom-left of table)
ACTION_REGION = {"x": 0.02, "y": 0.70, "w": 0.35, "h": 0.20}
ACTION_REGIONS = {
    "ggpoker": {"x": 0.02, "y": 0.70, "w": 0.35, "h": 0.20},
    "pokerstars": {"x": 0.02, "y": 0.75, "w": 0.30, "h": 0.15},
    "pokerfair": {"x": 0.02, "y": 0.75, "w": 0.30, "h": 0.15},
}

# Pot size display region (center-bottom of table)
POT_REGION = {"x": 0.40, "y": 0.355, "w": 0.23, "h": 0.055}
POT_REGIONS = {
    "ggpoker": dict(POT_REGION),
    "pokerstars": {"x": 0.42, "y": 0.48, "w": 0.16, "h": 0.08},
    "pokerfair": {"x": 0.42, "y": 0.48, "w": 0.16, "h": 0.08},
}

# The call/check button is separate from action history and raise sizing.
CALL_REGIONS = {"ggpoker": {"x": 0.735, "y": 0.88, "w": 0.125, "h": 0.105}}

_CLIENT = "ggpoker"  # set by find_ggpoker_window()

RANK_CHARS = "AKQJT98765432"
SUIT_CHARS = "shdc"


def _crop(img, region):
    W, H = img.size
    x = int(region["x"] * W)
    y = int(region["y"] * H)
    w = int(region["w"] * W)
    h = int(region["h"] * H)
    return img.crop((x, y, x + w, y + h))


def _card_subregions(region):
    """Split the hole-card region into left/right card boxes."""
    card_w = (region["w"] - CARD_GAP) / 2
    left = dict(region, w=card_w)
    right = dict(region, x=region["x"] + card_w + CARD_GAP, w=card_w)
    return left, right


def _region_offsets(region):
    """Yield the given region plus a grid of shifted variants.

    Tables can differ in theme/layout, so the hole-card band may sit higher,
    lower, or off to one side of the default CARD_REGION. We scan a modest
    grid of vertical and horizontal offsets; read_hole_cards picks the best
    match across all of them, so a wider scan is safe.
    """
    yield region
    for dy in (i * 0.04 for i in range(-6, 7)):
        for dx in (i * 0.04 for i in range(-3, 4)):
            if dy == 0 and dx == 0:
                continue
            r = dict(region)
            r["y"] = max(0.0, min(1.0 - r["h"], region["y"] + dy))
            r["x"] = max(0.0, min(1.0 - r["w"], region["x"] + dx))
            yield r


def _dominant_color(img):
    """Return the dominant non-transparent color channel signature of a small image."""
    img = img.convert("RGB").resize((8, 8))
    pixels = list(img.getdata())
    r = sum(p[0] for p in pixels) / len(pixels)
    g = sum(p[1] for p in pixels) / len(pixels)
    b = sum(p[2] for p in pixels) / len(pixels)
    return r, g, b


def _is_red(rgb, threshold=110):
    r, g, b = rgb
    return r > threshold and r > g + 40 and r > b + 40


def _otsu_threshold(px):
    """Two-class Otsu threshold on luminance pixels. Returns threshold or None."""
    hist = [0] * 256
    for v in px:
        hist[v] += 1
    total = len(px)
    sum_bg = 0.0
    sum_fg = 255.0 * total
    w_bg = 0
    w_fg = 0
    best = -1
    best_t = 0
    for t in range(256):
        w_bg += hist[t]
        w_fg -= hist[t]
        if w_bg == 0 or w_fg == 0:
            continue
        m_bg = sum_bg / w_bg
        m_fg = sum_fg / w_fg
        between = w_bg * w_fg * (m_bg - m_fg) ** 2
        if between > best:
            best = between
            best_t = t
        sum_bg += t * hist[t]
        sum_fg -= t * hist[t]
    return best_t if best > 0 else None


def _glyph_signature(img, bg=None):
    """Extract a text glyph and downscale to a fixed-size grayscale tuple.

    Handles both light cards (dark glyph) and dark cards (light glyph): the
    glyph polarity is detected from the dominant background (or taken from
    `bg` when supplied), and the result is binarised so the glyph is always
    dark (0) on a light (255) field, matching the rendered templates.

    Returns None when no plausible glyph is present.
    """
    g = img.convert("L")
    px = list(g.getdata())
    W = g.width
    hist = [0] * 256
    for v in px:
        hist[v] += 1
    if bg is None:
        bg = max(range(256), key=lambda v: hist[v])
        # Determine glyph polarity: is the minority colour darker or lighter
        # than the dominant card background?
        darker = sum(hist[v] for v in range(256) if v < bg - 40)
        lighter = sum(hist[v] for v in range(256) if v > bg + 40)
        if lighter > darker:
            mark = lambda v: v > bg + 40
        else:
            mark = lambda v: v < bg - 40
    else:
        # background known (e.g. the light card face): glyph is darker
        mark = lambda v: v < bg - 40
    idxs = [i for i, v in enumerate(px) if mark(v)]
    if not idxs:
        return None
    xs = list({i % W for i in idxs})
    ys = list({i // W for i in idxs})
    # Binarise: glyph -> 0, background -> 255 (normalises polarity).
    g = g.point(lambda v: 0 if mark(v) else 255)
    g = g.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    g = g.resize((12, 16))
    sig = tuple(g.getdata())
    # Ink-ratio sanity: a real rank glyph is ~5%..85% dark after downscale.
    ink = sum(1 for v in sig if v < 128) / len(sig)
    if ink < 0.05 or ink > 0.85:
        return None
    return sig


_FONT_CACHE = None


def _get_fonts():
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE
    from PIL import ImageFont
    fonts = []
    # GGPoker's rank glyphs are bold; try bold faces first.
    for path, idx in [("/System/Library/Fonts/Helvetica.ttc", 1),
                      ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
                      ("/System/Library/Fonts/Supplemental/Impact.ttf", 0),
                      ("/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf", 0),
                      ("/System/Library/Fonts/Helvetica.ttc", 0)]:
        try:
            fonts.append(ImageFont.truetype(path, 40, index=idx))
        except OSError:
            pass
    for name in ["Helvetica-Bold", "Arial Bold", "Helvetica", "Arial",
                 "Courier New", "DejaVu Sans", "Menlo", "Georgia"]:
        try:
            f = ImageFont.truetype(name, 40)
            if f not in fonts:
                fonts.append(f)
        except OSError:
            pass
    _FONT_CACHE = tuple(fonts)
    return _FONT_CACHE


@lru_cache(maxsize=1)
def _build_templates():
    """Build rank glyph templates from rendered text, one signature per
    candidate font. Matching (_match_rank) picks the closest across all fonts.

    'T' also gets a '10' template because GGPoker renders ten as '10'."""
    from PIL import ImageDraw, ImageFont
    templates = {}
    for ch in RANK_CHARS:
        sigs = []
        texts = [ch, "10"] if ch == "T" else [ch]
        for text in texts:
            # Font hinting changes narrow hooks and stems at small sizes.
            # Include Retina-size rendering as well as the original templates.
            fonts = [f.font_variant(size=size) for f in _get_fonts() for size in (40, 80)]
            for f in fonts:
                # Size the canvas from the font's bounds; fixed-height canvases
                # can clip the hook of J and descenders in condensed fonts.
                left, top, right, bottom = f.getbbox(text)
                img = Image.new("L", (right - left + 8, bottom - top + 8), 255)
                d = ImageDraw.Draw(img)
                d.text((4 - left, 4 - top), text, font=f, fill=0)
                sig = _glyph_signature(img, 255)
                if sig:
                    sigs.append(sig)
        templates[ch] = sigs
    return templates


# Max acceptable glyph match distance. Real rank glyphs from the GGPoker
# table score ~11000-18000 (stylised bold font); table text / avatars /
# badges score higher, so this threshold rejects those false matches.
# Increased to 25000 to accommodate different table themes and font renderings.
MATCH_TOLERANCE = 25000

def _match_rank(glyph_img, bg=None):
    sig = _glyph_signature(glyph_img, bg)
    if sig is None:
        return None, float("inf")
    best, best_d = None, float("inf")
    for ch, sigs in _build_templates().items():
        for tsig in sigs:
            if tsig is None:
                continue
            d = sum(abs(a - b) for a, b in zip(sig, tsig))
            if d < best_d:
                best, best_d = ch, d
    return best, best_d


def _split_rank_suit(card_img):
    """Card image -> (rank_glyph, is_red). Rank glyph = top-left corner.

    Suit color is sampled from the SUIT GLYPH area (bottom of card), not the
    rank area. This correctly distinguishes between different suits of the
    same color (e.g., clubs vs spades are both black but different suits).
    
    Returns:
        tuple: (rank_box_image, is_red_boolean)
    """
    W, H = card_img.size
    # The rank glyph sits in the top strip of the card
    rank_box = card_img.crop((int(W * 0.02), int(H * 0.02),
                              int(W * 0.80), int(H * 0.42)))
    # Clean up the rank box for glyph extraction
    rb = rank_box.convert("RGB")
    rpx = rb.load()
    for yy in range(rb.height):
        for xx in range(rb.width):
            r, gg, b = rpx[xx, yy]
            if min(r, gg, b) > 180 or (gg > r + 20 and gg > b + 20):
                rpx[xx, yy] = (255, 255, 255)
    rank_box = rb
    
    # Sample suit color from the SUIT GLYPH area (bottom portion of card)
    # This is the key fix: we need to sample from the suit symbol, not the rank
    suit_box = card_img.crop((int(W * 0.08), int(H * 0.50),
                              int(W * 0.50), int(H * 0.90)))
    
    # Get the dominant color from the suit glyph
    suit_rgb = _get_suit_glyph_color(suit_box)
    is_red = _is_red(suit_rgb) if suit_rgb else False
    
    return rank_box, is_red


def _get_suit_glyph_color(suit_box):
    """
    Extract the dominant color from a suit glyph area.
    
    Args:
        suit_box: PIL Image containing the suit symbol area
        
    Returns:
        tuple: (R, G, B) color values, or None if no valid color found
    """
    if not HAS_PIL:
        return None
    
    try:
        rgb = suit_box.convert("RGB")
        pixels = list(rgb.getdata())
        
        # Filter out background pixels (very light or very dark uniform areas)
        # and green felt
        glyph_pixels = []
        for p in pixels:
            r, g, b = p
            # Skip white/light background
            if min(r, g, b) > 200:
                continue
            # Skip green felt
            if g > r + 30 and g > b + 30:
                continue
            # Skip pure black (could be card border)
            if r < 30 and g < 30 and b < 30:
                continue
            glyph_pixels.append(p)
        
        if not glyph_pixels:
            return None
        
        # Find the most "colored" pixel (highest saturation)
        # This helps identify the suit glyph color
        def saturation(p):
            r, g, b = p
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            return max_c - min_c
        
        best_pixel = max(glyph_pixels, key=saturation)
        return best_pixel
        
    except Exception:
        return None


def _ink_components(image, background, ink_color=None):
    """Return isolated ink glyphs; card edges and felt are not rank glyphs."""
    rgb = image.convert('RGB')
    width, height = rgb.size
    dark_limit = min(45, max(20, background - 20)) if background < 150 else max(60, background - 50)
    if HAS_NUMPY:
        arr = np.asarray(rgb, dtype=np.int16)
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        not_felt = ~((g > r + 30) & (g > b + 30))
        mx = arr.max(axis=-1)
        mn = arr.min(axis=-1)
        dark = mx < dark_limit
        if ink_color == 'red':
            red = (r > g + 35) & (r > b + 35) & (r > 45)
        else:
            red = (r > g + 40) & (r > b + 40) & (r > max(80, background * .4))
        if ink_color == 'black':
            cond = not_felt & dark & ((mx - mn) < 45)
        elif ink_color == 'red':
            cond = not_felt & red
        else:
            cond = not_felt & (dark | red)
        ys, xs = np.nonzero(cond)
        mask = {(x, y) for y, x in zip(ys.tolist(), xs.tolist())}
    else:
        pixels = rgb.load()
        mask = set()
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                if g > r + 30 and g > b + 30:
                    continue
                dark = max(r, g, b) < dark_limit
                if ink_color == 'red':
                    red = r > g + 35 and r > b + 35 and r > 45
                else:
                    red = r > g + 40 and r > b + 40 and r > max(80, background * .4)
                if ink_color == 'black':
                    # Keep a black suit separate from colored badges/animations
                    # that touch its stem, including dark red edge pixels.
                    dark = dark and max(r, g, b) - min(r, g, b) < 45
                    red = False
                elif ink_color == 'red':
                    dark = False
                if dark or red:
                    mask.add((x, y))
    components = []
    while mask:
        point = mask.pop()
        stack, points = [point], [point]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((-1,-1), (0,-1), (1,-1), (-1,0), (1,0), (-1,1), (0,1), (1,1)):
                neighbor = (x + dx, y + dy)
                if neighbor in mask:
                    mask.remove(neighbor)
                    stack.append(neighbor)
                    points.append(neighbor)
        if len(points) >= max(5, width * height * .00015):
            components.append(points)
    return components


def _component_box(points):
    return (min(x for x, y in points), min(y for x, y in points),
            max(x for x, y in points) + 1, max(y for x, y in points) + 1)


def _component_image(points):
    x0, y0, x1, y1 = _component_box(points)
    glyph = Image.new('L', (x1 - x0, y1 - y0), 255)
    pixels = glyph.load()
    for x, y in points:
        pixels[x - x0, y - y0] = 0
    return glyph


def _match_rotated_glyph(glyph, templates, with_margin=False):
    """GGPoker fans hole cards by a few degrees, including the corner text."""
    best, distance = None, float('inf')
    distances = {}
    for angle in (0, -4, 4, -8, 8, -12, 12):
        rotated = glyph.rotate(angle, resample=Image.Resampling.BICUBIC,
                               expand=True, fillcolor=255)
        signature = _glyph_signature(rotated, 255)
        if signature is None:
            continue
        for name, signatures in templates.items():
            for candidate in signatures:
                d = sum(abs(a - b) for a, b in zip(signature, candidate))
                distances[name] = min(distances.get(name, float('inf')), d)
                if d < distance:
                    best, distance = name, d
    if with_margin:
        ordered = sorted(distances.values())
        margin = ordered[1] - ordered[0] if len(ordered) > 1 else 0
        return best, distance, margin
    return best, distance


@lru_cache(maxsize=1)
def _suit_templates():
    from PIL import ImageDraw
    templates = {}
    for suit, text in [('h', '♥'), ('d', '♦'), ('s', '♠'), ('c', '♣')]:
        signatures = []
        for font in _get_fonts():
            image = Image.new('L', (80, 80), 255)
            ImageDraw.Draw(image).text((5, 5), text, font=font, fill=0)
            signature = _glyph_signature(image, 255)
            if signature:
                signatures.append(signature)
        templates[suit] = signatures
    return templates


def _read_region_hand(img, region, debug=False):
    reading = _read_region_cards(img, region, debug=debug)
    return reading.hand if reading else None


def _read_region_cards(img, region, debug=False):
    """Read corner glyphs across both cards without slicing overlapping ranks."""
    card = _crop(img, region).convert('RGB')
    width, height = card.size
    if width < 20 or height < 20:
        return None
    if HAS_NUMPY:
        arr = np.asarray(card, dtype=np.int16)
        mx = arr.max(axis=-1)
        mn = arr.min(axis=-1)
        if float(((mn > 110) & ((mx - mn) < 45)).mean()) < .5:
            return None
    else:
        pixels = list(card.getdata())
        # Include gray card faces, but exclude felt and dark table chrome.
        faces = sum(min(p) > 110 and max(p) - min(p) < 45 for p in pixels)
        if faces / len(pixels) < .5:
            return None
    values = sorted(card.convert('L').getdata())
    background = values[int(len(values) * .75)]
    components = _ink_components(card, background)
    ranks = []
    for points in components:
        x0, y0, x1, y1 = _component_box(points)
        w, h = x1 - x0, y1 - y0
        # Cropping fanned cards can leave a sliver of the dark table at an
        # edge. It is often above the rank and used to win the topmost-glyph
        # selection (for example, a border was read as J instead of A).
        if (x0 > 0 and y0 > 0 and x1 < width and y1 < height
                and y0 < height * .40 and y1 < height * .60
                and max(7, height * .05) <= h <= height * .48
                and .15 <= w / h <= 1.7 and w < width * .30):
            ranks.append(points)
    # Join the two digits of '10' only when their baselines and heights agree.
    ranks.sort(key=lambda pts: _component_box(pts)[0])
    merged = []
    for points in ranks:
        if merged:
            a, b, c, d = _component_box(merged[-1])
            x0, y0, x1, y1 = _component_box(points)
            if (0 <= x0 - c <= max(3, (d - b) * .22)
                    and abs(y0 - b) < (d - b) * .2
                    and abs(y1 - d) < (d - b) * .2):
                merged[-1] += points
                continue
        merged.append(points)
    # Rank corners occupy separate horizontal bands, even on fanned cards.
    chosen = []
    for left, right in ((0, .38), (.38, .88)):
        candidates = [p for p in merged if left * width <= _component_box(p)[0] < right * width]
        if not candidates:
            return None
        chosen.append(min(candidates, key=lambda p: _component_box(p)[1]))
    suit_components = [
        (component, allowed)
        for color, allowed in (('black', 'sc'), ('red', 'hd'))
        for component in _ink_components(card, background, ink_color=color)
    ]
    results = []
    rank_distances, rank_margins, suit_distances = [], [], []
    for points in chosen:
        rank, distance, margin = _match_rotated_glyph(
            _component_image(points), _build_templates(), with_margin=True)
        rank_distances.append(distance)
        rank_margins.append(margin)
        # Isolated, deskewed glyphs match much more closely than the legacy
        # whole-card crops. The old 25000 limit accepts patterned card backs.
        if rank is None or distance > 12000:
            return None
        x0, y0, x1, y1 = _component_box(points)
        # Find the corner suit directly below this rank, not the large artwork
        # or the lower card area, which can be covered by the player's name.
        nearby = []
        for component, allowed in suit_components:
            a, b, c, d = _component_box(component)
            if (b >= y1 and b - y1 < height * .55
                    and abs((a + c) / 2 - (x0 + x1) / 2) < width * .09
                    and 4 <= d - b < height * .4
                    and .4 <= (c - a) / (d - b) <= 1.7):
                nearby.append((component, allowed))
        suit = None
        accepted_suit_distance = float('inf')
        for symbol, allowed in sorted(nearby, key=lambda item: _component_box(item[0])[1]):
            candidate, suit_distance = _match_rotated_glyph(
                _component_image(symbol),
                {s: t for s, t in _suit_templates().items() if s in allowed})
            if candidate is not None and suit_distance <= 10000:
                suit = candidate
                accepted_suit_distance = suit_distance
                break
        suit_distances.append(accepted_suit_distance)
        # Rank-only themes/test images still encode red/black in their ink.
        red = sum(_is_red(card.getpixel(p)) for p in points) > len(points) / 2
        results.append((rank, suit, red))
        if debug:
            print(f'  [DEBUG] Rank={rank} distance={distance} suit={suit} box={(x0,y0,x1,y1)}')
    (r1, s1, red1), (r2, s2, red2) = results
    hi, lo = sorted((r1, r2), key=RANK_CHARS.index)
    suited = s1 == s2 if s1 and s2 else red1 == red2
    hand = r1 + r2 if r1 == r2 else hi + lo + ('s' if suited else 'o')
    cards = (r1 + s1, r2 + s2) if s1 and s2 else None
    return CardReading(hand, cards, tuple(rank_distances), tuple(rank_margins),
                       tuple(suit_distances), tuple(region[k] for k in ('x', 'y', 'w', 'h')))


def read_hole_cards(img, debug=False):
    """Given a window screenshot PIL image, return hand like 'AKs' or None.

    Dispatches to the per-client reader. Returns None when the region
    doesn't contain two confident rank glyphs.
    
    Args:
        img: PIL Image of the poker window
        debug: If True, print debug information about suit detection
        
    Returns:
        Hand string like 'AKs' or None if detection fails
    """
    if not HAS_PIL:
        raise RuntimeError("Pillow required: pip3 install Pillow")
    if _get_client() == "pokerstars":
        from pokerstars import read_hand
        reading = read_hand(img)
        return reading.hand if reading else None
    return _read_region_hand(img, CARD_REGIONS.get(_get_client(), CARD_REGION), debug=debug)


def read_suit_glyph(card_img, debug=False):
    """
    Read the suit glyph below the rank using advanced shape analysis.
    
    Uses multiple shape characteristics to distinguish between the four suits:
    - Spades (♠): black, stem at bottom, rounded top with central point
    - Hearts (♥): red, two lobes at top, point at bottom, wide top
    - Clubs (♣): black, three lobes (clover shape), stem at bottom
    - Diamonds (♦): red, rhombus shape, point at top and bottom, symmetric
    
    Args:
        card_img: PIL Image of the card
        debug: If True, print debug information
        
    Returns:
        tuple: (suit_char, confidence) where suit_char is 's','h','d','c' or None,
               and confidence is 0.0-1.0
    """
    if not HAS_PIL:
        return None, 0.0
    
    W, H = card_img.size
    suit_box = card_img.crop((int(W * 0.08), int(H * 0.50),
                              int(W * 0.50), int(H * 0.90)))
    
    # Get suit color first
    suit_rgb = _get_suit_glyph_color(suit_box)
    is_red = _is_red(suit_rgb) if suit_rgb else False
    
    if debug:
        print(f"  [DEBUG] Suit color: RGB{suit_rgb}, is_red={is_red}")
    
    # Analyze shape using multiple heuristics
    shape_features = _analyze_suit_shape_advanced(suit_box)
    
    if debug:
        print(f"  [DEBUG] Shape features: {shape_features}")
    
    # Determine suit based on color and shape features
    suit, confidence = _classify_suit(is_red, shape_features, debug)
    
    if debug:
        print(f"  [DEBUG] Detected suit: {suit}, confidence: {confidence:.2f}")
    
    return suit, confidence


def _analyze_suit_shape_advanced(suit_box):
    """
    Advanced shape analysis for suit glyph classification.
    
    Analyzes multiple shape characteristics to distinguish between all 4 suits:
    - Spades (♠): stem at bottom, rounded top with central point
    - Hearts (♥): two lobes at top, point at bottom, wide top
    - Clubs (♣): three lobes (clover shape), stem at bottom
    - Diamonds (♦): rhombus shape, point at top and bottom, symmetric
    
    Args:
        suit_box: PIL Image of the suit glyph area
        
    Returns:
        dict: Shape features for classification
    """
    if not HAS_PIL:
        return _default_shape_features()
    
    try:
        # Convert to grayscale and resize for consistent analysis
        gray = suit_box.convert("L")
        W, H = gray.size
        
        # Resize to standard size for analysis (30x40 for better resolution)
        analyzed = gray.resize((30, 40), Image.BILINEAR)
        px = list(analyzed.getdata())
        
        # Otsu thresholding for better binarization
        threshold = _otsu_threshold(px) if px else 128
        if threshold is None:
            threshold = 128
        
        # Create binary mask (1 = glyph, 0 = background)
        mask = [[1 if px[y * 30 + x] < threshold else 0 for x in range(30)] for y in range(40)]
        
        # Calculate width profile at different vertical positions
        width_profile = []
        for y in range(40):
            width = sum(mask[y][x] for x in range(30))
            width_profile.append(width)
        
        # Key width measurements
        top_width = sum(width_profile[2:6]) / 4      # Top 10%
        upper_mid_width = sum(width_profile[10:14]) / 4  # Upper middle
        mid_width = sum(width_profile[18:22]) / 4    # Middle
        lower_mid_width = sum(width_profile[26:30]) / 4  # Lower middle
        bot_width = sum(width_profile[34:38]) / 4    # Bottom 10%
        
        # Width ratios for shape classification
        top_to_bot_ratio = top_width / (bot_width + 1)
        mid_to_top_ratio = mid_width / (top_width + 1)
        mid_to_bot_ratio = mid_width / (bot_width + 1)
        
        # Check for stem (narrow bottom section)
        has_stem = bot_width < top_width * 0.4 and bot_width < 8
        
        # Check for pointed top (diamonds have point at top)
        pointed_top = width_profile[2] < width_profile[8] * 0.5
        
        # Check for pointed bottom (hearts and diamonds have point at bottom)
        pointed_bottom = width_profile[38] < width_profile[32] * 0.5
        
        # Check for wide top (hearts have two lobes at top)
        wide_top = top_width > mid_width * 0.9
        
        # Check for clover shape (clubs have three lobes - wide in middle)
        clover_shape = mid_width > top_width * 1.1 and mid_width > bot_width * 1.5
        
        # Symmetry analysis (diamonds are symmetric top-to-bottom)
        top_half = sum(width_profile[:20])
        bot_half = sum(width_profile[20:])
        symmetry_ratio = min(top_half, bot_half) / (max(top_half, bot_half) + 1)
        
        # Lobe detection using local maxima in width profile
        lobe_count = _count_lobes(width_profile)
        
        # Calculate overall glyph density
        total_ink = sum(width_profile)
        density = total_ink / (30 * 40)
        
        # Bounding box analysis
        glyph_pixels = [(x, y) for y in range(40) for x in range(30) if mask[y][x]]
        if glyph_pixels:
            min_x = min(p[0] for p in glyph_pixels)
            max_x = max(p[0] for p in glyph_pixels)
            min_y = min(p[1] for p in glyph_pixels)
            max_y = max(p[1] for p in glyph_pixels)
            bbox_width = max_x - min_x + 1
            bbox_height = max_y - min_y + 1
            aspect_ratio = bbox_width / bbox_height if bbox_height > 0 else 1
        else:
            aspect_ratio = 1
        
        return {
            'top_width': top_width,
            'mid_width': mid_width,
            'bot_width': bot_width,
            'top_to_bot_ratio': top_to_bot_ratio,
            'mid_to_top_ratio': mid_to_top_ratio,
            'has_stem': has_stem,
            'pointed_top': pointed_top,
            'pointed_bottom': pointed_bottom,
            'wide_top': wide_top,
            'clover_shape': clover_shape,
            'symmetry_ratio': symmetry_ratio,
            'lobe_count': lobe_count,
            'density': density,
            'aspect_ratio': aspect_ratio,
            'width_profile': width_profile
        }
        
    except Exception:
        return _default_shape_features()


def _default_shape_features():
    """Return default shape features when analysis fails."""
    return {
        'top_width': 0,
        'mid_width': 0,
        'bot_width': 0,
        'top_to_bot_ratio': 1.0,
        'mid_to_top_ratio': 1.0,
        'has_stem': False,
        'pointed_top': False,
        'pointed_bottom': False,
        'wide_top': False,
        'clover_shape': False,
        'symmetry_ratio': 0.5,
        'lobe_count': 0,
        'density': 0.0,
        'aspect_ratio': 1.0,
        'width_profile': []
    }


def _count_lobes(width_profile):
    """
    Count the number of lobes in a suit glyph by finding local maxima.
    
    Hearts have 2 lobes (top), clubs have 3 lobes, spades have 1 (rounded top).
    
    Args:
        width_profile: List of width values at each vertical position
        
    Returns:
        int: Estimated number of lobes
    """
    if len(width_profile) < 10:
        return 0
    
    # Look for local maxima in the upper portion of the glyph
    # (where lobes would be visible)
    lobe_count = 0
    upper_profile = width_profile[:20]  # Focus on upper half
    
    for i in range(2, len(upper_profile) - 2):
        # Check if this is a local maximum
        is_max = (upper_profile[i] > upper_profile[i-1] and
                  upper_profile[i] > upper_profile[i-2] and
                  upper_profile[i] > upper_profile[i+1] and
                  upper_profile[i] > upper_profile[i+2])
        
        # Must be significant (not noise)
        is_significant = upper_profile[i] > 5
        
        if is_max and is_significant:
            lobe_count += 1
    
    return min(lobe_count, 3)  # Max 3 lobes (clubs)


def _classify_suit(is_red, shape_features, debug=False):
    """
    Classify the suit based on color and shape features.
    
    Args:
        is_red: Whether the suit is red (hearts/diamonds) or black (spades/clubs)
        shape_features: Dictionary of shape features from _analyze_suit_shape_advanced
        debug: If True, print debug information
        
    Returns:
        tuple: (suit_char, confidence) where suit_char is 's','h','d','c'
    """
    features = shape_features
    
    if is_red:
        # Red suits: hearts (♥) or diamonds (♦)
        # Hearts: wide top (two lobes), pointed bottom
        # Diamonds: symmetric, pointed top and bottom, rhombus shape
        
        hearts_score = 0.0
        diamonds_score = 0.0
        
        # Hearts indicators
        if features['wide_top']:
            hearts_score += 0.3
        if features['pointed_bottom']:
            hearts_score += 0.2
        if features['top_to_bot_ratio'] > 1.2:
            hearts_score += 0.2
        if features['lobe_count'] >= 2:
            hearts_score += 0.3
        
        # Diamonds indicators
        if features['pointed_top']:
            diamonds_score += 0.25
        if features['pointed_bottom']:
            diamonds_score += 0.25
        if features['symmetry_ratio'] > 0.7:
            diamonds_score += 0.25
        if 0.8 < features['top_to_bot_ratio'] < 1.2:
            diamonds_score += 0.25
        
        if debug:
            print(f"  [DEBUG] Red suit scores - Hearts: {hearts_score:.2f}, Diamonds: {diamonds_score:.2f}")
        
        if hearts_score > diamonds_score:
            return 'h', min(1.0, hearts_score + 0.3)
        else:
            return 'd', min(1.0, diamonds_score + 0.3)
    
    else:
        # Black suits: spades (♠) or clubs (♣)
        # Spades: stem at bottom, rounded top with central point
        # Clubs: three lobes (clover), stem at bottom
        
        spades_score = 0.0
        clubs_score = 0.0
        
        # Spades indicators
        if features['has_stem']:
            spades_score += 0.2
        if not features['clover_shape']:
            spades_score += 0.3
        if features['lobe_count'] <= 1:
            spades_score += 0.3
        if features['mid_to_top_ratio'] < 1.1:
            spades_score += 0.2
        
        # Clubs indicators
        if features['clover_shape']:
            clubs_score += 0.4
        if features['lobe_count'] >= 2:
            clubs_score += 0.3
        if features['has_stem']:
            clubs_score += 0.2
        if features['mid_to_top_ratio'] > 1.1:
            clubs_score += 0.1
        
        if debug:
            print(f"  [DEBUG] Black suit scores - Spades: {spades_score:.2f}, Clubs: {clubs_score:.2f}")
        
        if spades_score > clubs_score:
            return 's', min(1.0, spades_score + 0.3)
        else:
            return 'c', min(1.0, clubs_score + 0.3)


def _analyze_suit_shape(suit_box):
    """
    Legacy shape analysis for backward compatibility.
    
    Args:
        suit_box: PIL Image of the suit glyph area
        
    Returns:
        dict: Shape characteristics (legacy format)
    """
    advanced = _analyze_suit_shape_advanced(suit_box)
    
    # Convert to legacy format
    return {
        'top_wide': advanced['wide_top'],
        'bottom_wide': advanced['top_to_bot_ratio'] < 0.8,
        'has_stem': advanced['has_stem'],
        'has_lobes': advanced['clover_shape'] or advanced['lobe_count'] >= 2,
        'top_width': advanced['top_width'],
        'mid_width': advanced['mid_width'],
        'bot_width': advanced['bot_width'],
        'density': advanced['density'],
        'confidence': 0.5  # Base confidence
    }


# ---------------------------------------------------------------------------
# Board Card Detection (Postflop) - Fixed for GGPoker
# ---------------------------------------------------------------------------

def detect_board_cards(img, debug=False) -> Optional[str]:
    """
    Detect community cards (board) from the poker table.
    
    Board cards are located in the center of the table and can be 3-5 cards
    (flop through river). This function uses card localization to find
    individual cards and reads each one.
    
    Args:
        img: Full table screenshot
        debug: If True, print debug information
        
    Returns:
        Board string like "QdJd8s" or "QdJd8s5h" or None if detection fails
    """
    if not HAS_PIL:
        return None
    if _get_client() == 'pokerstars':
        from pokerstars import board_cards
        return board_cards(img)
    
    try:
        W, H = img.size
        base_region = BOARD_REGIONS.get(_get_client(), BOARD_REGION)
        for dy in (0.0, -0.025, 0.025):
            region = dict(base_region, y=max(0.0, min(1.0 - base_region["h"], base_region["y"] + dy)))
            # Calculate board area
            board_x = int(region["x"] * W)
            board_y = int(region["y"] * H)
            board_w = int(region["w"] * W)
            board_h = int(region["h"] * H)
            
            # Crop the board region
            board_area = img.crop((board_x, board_y, board_x + board_w, board_y + board_h))
            
            # Detect individual card positions using card localization
            card_positions = _locate_board_cards(board_area)
            
            if debug:
                print(f"  [DEBUG] Found {len(card_positions)} board cards (dy={dy})")
            
            if len(card_positions) not in (3, 4, 5):
                continue
            
            board_cards = []
            for i, (cx, cy, cw, ch) in enumerate(card_positions):
                # Crop individual card
                card_crop = board_area.crop((cx, cy, cx + cw, cy + ch))
                
                # Try to read the card with full suit detection
                card_result = _read_single_board_card(card_crop, debug=debug)
                if card_result is None or card_result in board_cards:
                    board_cards = []
                    break  # Never publish a partial board or invent a suit.
                board_cards.append(card_result)
                if debug:
                    print(f"  [DEBUG] Card {i+1}: {card_result}")
            
            if board_cards:
                return "".join(board_cards)
        return None
        
    except Exception as e:
        if debug:
            print(f"  [DEBUG] Board detection error: {e}")
        return None


def _locate_board_cards(board_area) -> List[Tuple[int, int, int, int]]:
    """
    Locate individual card positions within the board area.
    
    Uses connected component analysis to find card-like rectangles.
    
    Args:
        board_area: Cropped board region image
        
    Returns:
        List of (x, y, w, h) tuples for each detected card
    """
    if not HAS_PIL:
        return []
    
    try:
        W, H = board_area.size
        rgb = board_area.convert('RGB')
        if HAS_NUMPY:
            arr = np.asarray(rgb, dtype=np.int16)
            mn_arr = arr.min(axis=-1)
            spread_arr = arr.max(axis=-1) - mn_arr
            px = None
        else:
            px = list(rgb.getdata())
            mn_arr = spread_arr = None

        filtered = []
        for min_lum, max_spread in ((130, 45), (110, 55)):
            # Neutral card faces, excluding felt and colored chips/text.
            if HAS_NUMPY:
                mask = ((mn_arr > min_lum) & (spread_arr < max_spread)).tolist()
            else:
                mask = [[min(px[y * W + x]) > min_lum and
                         max(px[y * W + x]) - min(px[y * W + x]) < max_spread
                         for x in range(W)] for y in range(H)]
            
            # Find connected components
            seen = [[False] * W for _ in range(H)]
            components = []
            top_strips = []
            
            for y in range(H):
                row_mask = mask[y]
                row_seen = seen[y]
                for x in range(W):
                    if row_mask[x] and not row_seen[x]:
                        # BFS to find connected component
                        stack = [(x, y)]
                        row_seen[x] = True
                        min_x, max_x = x, x
                        min_y, max_y = y, y
                        
                        while stack:
                            cx, cy = stack.pop()
                            if cx < min_x:
                                min_x = cx
                            if cx > max_x:
                                max_x = cx
                            if cy < min_y:
                                min_y = cy
                            if cy > max_y:
                                max_y = cy
                            
                            for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                                if (0 <= nx < W and 0 <= ny < H and
                                    mask[ny][nx] and not seen[ny][nx]):
                                    seen[ny][nx] = True
                                    stack.append((nx, ny))
                        
                        w = max_x - min_x + 1
                        h = max_y - min_y + 1
                        
                        # Filter for card-sized components
                        if (.08 * W <= w <= .25 * W and .38 * H <= h <= H
                                and .45 <= w / h <= .92):
                            components.append((min_x, min_y, w, h))
                        elif .08 * W <= w <= .25 * W and .15 * H <= h < .38 * H:
                            top_strips.append((min_x, min_y, w, h))
            
            # Sort components left to right
            components.sort(key=lambda c: c[0])
            
            # Remove overlapping components (keep larger one)
            filtered = []
            for comp in components:
                overlaps = False
                for existing in filtered:
                    # Check for significant overlap
                    cx, cy, cw, ch = comp
                    ex, ey, ew, eh = existing
                    if not (cx + cw < ex or cx > ex + ew or cy + ch < ey or cy > ey + eh):
                        overlaps = True
                        break
                if not overlaps:
                    filtered.append(comp)
            
            # Recover board cards whose bottom half is darkened by a translucent table banner/timer
            if filtered and len(filtered) < 5 and top_strips:
                ref_y = sorted(c[1] for c in filtered)[len(filtered) // 2]
                ref_w = sorted(c[2] for c in filtered)[len(filtered) // 2]
                ref_h = sorted(c[3] for c in filtered)[len(filtered) // 2]
                for sx, sy, sw, sh in top_strips:
                    if (abs(sy - ref_y) <= max(3, int(0.015 * H))
                            and abs(sw - ref_w) <= max(5, int(0.015 * W))):
                        no_overlap = all(sx + sw < ex or sx > ex + ew for ex, _, ew, _ in filtered)
                        on_grid = any(1.08 * ref_w <= abs(sx - ex) <= 1.28 * ref_w for ex, _, _, _ in filtered)
                        if no_overlap and on_grid:
                            filtered.append((sx, ref_y, sw, ref_h))
                filtered.sort(key=lambda c: c[0])
            
            if len(filtered) in (3, 4, 5):
                return filtered
        
        return filtered
        
    except Exception:
        return []


def _is_club_glyph(glyph_img) -> bool:
    """Verify GGPoker club ('c') vs spade ('s') geometry via top-lobe and neck width."""
    gw, gh = glyph_img.size
    if gw < 8 or gh < 8:
        return False

    def row_span(y_frac: float) -> float:
        y = min(gh - 1, max(0, int(gh * y_frac)))
        xs = [x for x in range(gw) if glyph_img.getpixel((x, y)) == 0]
        return (max(xs) - min(xs) + 1) / gw if xs else 0.0

    # A club has a wide rounded top lobe (y=15%) and a narrower neck (y=38%) before the side lobes,
    # whereas a spade has a narrow pointed top tip (y=15%) and widens rapidly through y=38%.
    return row_span(0.15) > 0.36 and row_span(0.38) < 0.66


def _read_single_board_card(card_img, debug=False) -> Optional[str]:
    """Read isolated corner glyphs; require both a rank and an actual suit."""
    card_img = card_img.convert('RGB')
    width, height = card_img.size
    rank_area = card_img.crop((int(width * .02), int(height * .02),
                               int(width * .45), int(height * .34)))
    rank_vals = sorted(rank_area.convert('L').getdata())
    rank_bg = max(180, rank_vals[int(len(rank_vals) * .75)]) if rank_vals else 240
    components = _ink_components(rank_area, rank_bg)
    if components:
        lx0, ly0, lx1, ly1 = _component_box(max(components, key=len))
        if lx1 >= rank_area.width - 2 and ly1 >= rank_area.height - 2:
            components = (
                _ink_components(rank_area, 72, ink_color='red')
                + _ink_components(rank_area, 72, ink_color='black')
            )
    if not components:
        return None
    # Join aligned digits for clients that render ten as '10'.
    largest = max(components, key=len)
    _, top, _, bottom = _component_box(largest)
    points = [p for component in components
              if abs(_component_box(component)[1] - top) <= max(2, (bottom - top) * .2)
              and abs(_component_box(component)[3] - bottom) <= max(2, (bottom - top) * .2)
              for p in component]
    rank, distance, margin = _match_rotated_glyph(
        _component_image(points), _build_templates(), with_margin=True)
    if rank is None or distance > 12000 or margin < 600:
        return None
    rank_red = sum(
        (r > 45 and r > g + 35 and r > b + 35)
        for r, g, b in (rank_area.getpixel(p) for p in points)
    ) > len(points) / 2
    suit_area = card_img.crop((int(width * .025), int(height * .32),
                               int(width * .45), int(height * .59)))
    suit_vals = sorted(suit_area.convert('L').getdata())
    raw_suit_bg = suit_vals[int(len(suit_vals) * .75)] if suit_vals else 240
    suit_bg = raw_suit_bg if raw_suit_bg < 150 else max(180, raw_suit_bg)
    expected_color = 'red' if rank_red else 'black'
    components = _ink_components(suit_area, suit_bg, ink_color=expected_color)
    if components:
        sx0, sy0, sx1, sy1 = _component_box(max(components, key=len))
        if sx1 >= suit_area.width - 2 and sy1 >= suit_area.height - 2:
            components = _ink_components(suit_area, 72, ink_color=expected_color)
    # Ignore edge fragments from the large center pip in the bottom-right corner
    corner_components = [
        c for c in components
        if _component_box(c)[0] < suit_area.width * 0.65 and _component_box(c)[1] < suit_area.height * 0.65
    ]
    if corner_components:
        components = corner_components
    elif not components:
        components = _ink_components(suit_area, max(180, raw_suit_bg))
    if not components:
        return None
    symbol = max(components, key=len)
    x0, y0, x1, y1 = _component_box(symbol)
    if not (.4 <= (x1 - x0) / max(1, y1 - y0) <= 1.7):
        return None
    red = sum(
        (r > 45 and r > g + 35 and r > b + 35)
        for r, g, b in (suit_area.getpixel(p) for p in symbol)
    ) > len(symbol) / 2
    allowed = 'hd' if red else 'sc'
    glyph_img = _component_image(symbol)
    suit, suit_distance, suit_margin = _match_rotated_glyph(
        glyph_img,
        {s: t for s, t in _suit_templates().items() if s in allowed}, with_margin=True)
    if suit is None or suit_distance > 10000:
        return None
    if suit_margin < 600:
        if not red and suit_distance <= 6500 and suit_margin >= 100:
            suit = 'c' if _is_club_glyph(glyph_img) else 's'
        else:
            return None
    if debug:
        print(f'  [DEBUG] Board card: {rank}{suit}, rank distance={distance}, suit distance={suit_distance}')
    return rank + suit


def detect_board_cards_advanced(img) -> Dict[str, Any]:
    """
    Advanced board detection with card-by-card analysis.
    
    Args:
        img: Full table screenshot
        
    Returns:
        Dictionary with:
        - board: Board string
        - card_count: Number of cards detected (3-5)
        - street: Current street (flop, turn, river)
        - confidence: Detection confidence score
    """
    board = detect_board_cards(img)
    
    if not board:
        return {
            'board': None,
            'card_count': 0,
            'street': None,
            'confidence': 0.0
        }
    
    # Count cards (each card is 2 characters: rank + suit)
    card_count = len(board) // 2
    
    # Determine street
    if card_count == 3:
        street = "flop"
    elif card_count == 4:
        street = "turn"
    elif card_count == 5:
        street = "river"
    else:
        street = "unknown"
    
    # Calculate confidence based on card count and detection quality
    confidence = min(1.0, card_count / 3.0)  # Higher confidence with more cards
    
    return {
        'board': board,
        'card_count': card_count,
        'street': street,
        'confidence': confidence
    }


# ---------------------------------------------------------------------------
# Action and Pot Detection
# ---------------------------------------------------------------------------

# Accept comma-grouped chips and decimal currency, never truncate at a comma.
_AMOUNT_PATTERN = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"


def _parse_amount(text):
    value = float(text.replace(',', ''))
    return int(value) if value.is_integer() else value


def detect_pot_size(img) -> Optional[float]:
    """Read the labeled total pot, including bets already on the table."""
    import re
    region = POT_REGIONS.get(_get_client(), POT_REGION)
    if _get_client() == 'pokerstars':
        from pokerstars import POT
        region = POT
    text = _extract_text_from_image(_crop(img, region))
    match = re.search(r'\b(?:total\s+)?pot\s*:?\s*[$£€]?\s*(' + _AMOUNT_PATTERN + r')(?![\d,.])',
                      text, re.IGNORECASE)
    return _parse_amount(match.group(1)) if match else None


def _is_preaction_checkbox(crop_img) -> bool:
    """Detect a GGPoker pre-action checkbox outline on the left side of the button area."""
    if not HAS_PIL or crop_img is None or crop_img.width < 20 or crop_img.height < 12:
        return False
    try:
        # Pre-action checkboxes on GGPoker have a small hollow/tick square on the left 25% of the region
        # and lack the filled colored/warm action button background.
        rgb = crop_img.convert('RGB')
        pixels = list(rgb.getdata())
        if not pixels:
            return False
        # Live GGPoker action buttons have warm red/gold/brown or bright button fill;
        # if we see a distinct small square box in the left margin on a dark neutral background, treat as checkbox.
        left_area = rgb.crop((0, int(rgb.height * 0.15), int(rgb.width * 0.25), int(rgb.height * 0.85)))
        comps = _ink_components(left_area.convert('L').point(lambda p: 0 if p > 140 else 255).convert('RGB'), 128)
        for pts in comps:
            x0, y0, x1, y1 = _component_box(pts)
            w, h = x1 - x0 + 1, y1 - y0 + 1
            if 8 <= w <= left_area.width * 0.85 and 8 <= h <= left_area.height * 0.85 and 0.75 <= w / h <= 1.35:
                # Hollow square check: perimeter ink much higher than interior ink
                box_set = set(pts)
                border = sum(1 for x, y in pts if x in (x0, x0 + 1, x1 - 1, x1) or y in (y0, y0 + 1, y1 - 1, y1))
                if border / max(1, len(box_set)) > 0.60 and (w * h) > len(box_set) * 1.6:
                    return True
    except Exception:
        pass
    return False


def detect_raise_button(img) -> bool:
    """Return True if a live Raise / Bet / All-In action button is visible in the raise button region."""
    if not HAS_PIL or img is None:
        return False
    try:
        from auto_actor import BUTTON_REGIONS
        client = _get_client()
        if client not in ('ggpoker', 'pokerstars'):
            client = 'ggpoker'
        region = BUTTON_REGIONS.get(client, BUTTON_REGIONS['ggpoker']).get('raise')
        if not region:
            return False
        crop = _crop(img, region)
        if _is_preaction_checkbox(crop):
            return False
        text = _extract_text_from_image(crop)
        return bool(re.search(r'\b(?:raise|bet|all[\s-]?in|shove)\b', text, re.IGNORECASE))
    except Exception:
        return False


def is_raise_button_available(img) -> bool:
    """Return False when a live Call/Check button is visible in Slot 2 but the Slot 3 (Raise/Bet) button is absent."""
    if not HAS_PIL or img is None:
        return True
    try:
        from auto_actor import BUTTON_REGIONS
        client = _get_client()
        if client not in ('ggpoker', 'pokerstars'):
            client = 'ggpoker'
        regions = BUTTON_REGIONS.get(client, BUTTON_REGIONS['ggpoker'])
        call_reg = regions.get('call')
        raise_reg = regions.get('raise')
        if not call_reg or not raise_reg:
            return True
        call_crop = _crop(img, call_reg).convert('RGB')
        raise_crop = _crop(img, raise_reg).convert('RGB')
        call_px = list(call_crop.getdata())
        raise_px = list(raise_crop.getdata())
        if not call_px or not raise_px:
            return True
        call_red = sum(1 for r, g, b in call_px if r > 110 and r > g + 35 and r > b + 35) / len(call_px)
        if call_red >= 0.25:
            raise_red = sum(1 for r, g, b in raise_px if r > 110 and r > g + 35 and r > b + 35) / len(raise_px)
            raise_white = sum(1 for r, g, b in raise_px if r > 185 and g > 185 and b > 185) / len(raise_px)
            return bool(raise_red >= 0.25 and raise_white >= 0.005 and not _is_preaction_checkbox(raise_crop))
        return True
    except Exception:
        return True


def is_preset_bar_available(img) -> bool:
    """Return False when live GGPoker action buttons are visible on screen but the preset sizing bar above them is absent."""
    if not HAS_PIL or img is None:
        return True
    try:
        if not is_raise_button_available(img):
            return False
        from auto_actor import BUTTON_REGIONS
        client = _get_client()
        if client not in ('ggpoker', 'pokerstars'):
            client = 'ggpoker'
        regions = BUTTON_REGIONS.get(client, BUTTON_REGIONS['ggpoker'])
        call_reg = regions.get('call')
        if not call_reg:
            return True
        call_crop = _crop(img, call_reg).convert('RGB')
        call_px = list(call_crop.getdata())
        if not call_px:
            return True
        call_red = sum(1 for r, g, b in call_px if r > 110 and r > g + 35 and r > b + 35) / len(call_px)
        if call_red >= 0.25:
            preset_strip = _crop(img, {'x': 0.690, 'y': 0.818, 'w': 0.270, 'h': 0.032}).convert('RGB')
            strip_px = list(preset_strip.getdata())
            if not strip_px:
                return True
            bright_text = sum(1 for r, g, b in strip_px if r > 165 and g > 165 and b > 165) / len(strip_px)
            return bool(bright_text >= 0.003)
        return True
    except Exception:
        return True


def detect_open_cards_button(img) -> bool:
    """Return True if GGPoker's bright green 'Open' (card squeeze / reveal) button is visible."""
    if not HAS_PIL or img is None:
        return False
    try:
        client = _get_client()
        if client not in ('ggpoker', None):
            return False
        region = {'x': 0.68, 'y': 0.85, 'w': 0.12, 'h': 0.09}
        crop = _crop(img, region).convert('RGB')
        if crop.width < 8 or crop.height < 6:
            return False
        pixels = list(crop.getdata())
        if not pixels:
            return False
        total = len(pixels)
        green_count = sum(1 for r, g, b in pixels if g > 125 and (g - r) > 50 and (g - b) > 50)
        white_count = sum(1 for r, g, b in pixels if r > 200 and g > 200 and b > 200)
        green_frac = green_count / total
        white_frac = white_count / total
        return green_frac >= 0.20 and 0.01 <= white_frac <= 0.25
    except Exception:
        return False


def detect_sit_in_button(img) -> bool:
    """Return True if GGPoker's 'I'm Back' / 'Sit In' button is visible when Hero is sitting out."""
    import re
    if not HAS_PIL or img is None:
        return False
    try:
        client = _get_client()
        if client not in ('ggpoker', 'pokerstars', None):
            return False
        region = {'x': 0.76, 'y': 0.86, 'w': 0.18, 'h': 0.08}
        crop = _crop(img, region).convert('RGB')
        if crop.width < 8 or crop.height < 6:
            return False
        pixels = list(crop.getdata())
        if not pixels:
            return False
        total = len(pixels)
        # Require visible button fill (cyan/blue/green/amber) and bright text pixels before running OCR
        button_fill = sum(
            1 for r, g, b in pixels
            if (b > 120 and b - r > 35) or (g > 125 and g - r > 40) or (r > 150 and g > 100 and b < 70)
        )
        white_count = sum(1 for r, g, b in pixels if r > 195 and g > 195 and b > 195)
        if (button_fill / total) < 0.18 or not (0.008 <= (white_count / total) <= 0.30):
            return False
        text = _extract_text_vision(crop, threshold=165, target_height=100)
        if not text:
            text = _extract_text_from_image(crop, threshold=165, target_height=100)
        return bool(re.search(r"\b(?:i\s*'?m\s*back|sit\s*in|post\s*bb|join)\b", text, re.IGNORECASE))
    except Exception:
        return False



def has_live_action_buttons(img, client: Optional[str] = None) -> bool:
    """Return True when live hero action buttons (Call/Check or Raise/Bet) are visible."""
    if not HAS_PIL or img is None:
        return False
    token = None
    try:
        if client is not None:
            token = _capture_client.set(client)
        if detect_call_amount(img) is not None:
            return True
        return detect_raise_button(img)
    except Exception:
        return False
    finally:
        if token is not None:
            _capture_client.reset(token)


def detect_call_amount(img) -> Optional[float]:
    """Read only the call/check button, excluding raise, preset amounts, and pre-action checkboxes."""
    import re
    if _get_client() == 'pokerstars':
        from pokerstars import call_amount
        return call_amount(img)
    region = CALL_REGIONS.get(_get_client(), ACTION_REGIONS.get(_get_client(), ACTION_REGION))
    crop = _crop(img, region)
    if _is_preaction_checkbox(crop):
        return None
    text = _extract_text_from_image(crop)
    match = re.search(r'\bcall\s*:?\s*[$£€]?\s*(' + _AMOUNT_PATTERN + r')(?![\d,.])',
                      text, re.IGNORECASE)
    if match:
        return _parse_amount(match.group(1))
    if re.fullmatch(r'\s*check\s*', text, re.IGNORECASE):
        return 0
    return None


def detect_action_history(img) -> Dict[str, Any]:
    """
    Detect action history from the table.
    
    Args:
        img: Full table screenshot
        
    Returns:
        Dictionary with:
        - actions: List of detected actions
        - current_action: Current action to take
        - bet_size: Current bet size
        - aggressor: Position of current aggressor
    """
    if not HAS_PIL:
        return {
            'actions': [],
            'current_action': None,
            'bet_size': None,
            'aggressor': None
        }
    
    try:
        W, H = img.size
        region = ACTION_REGIONS.get(_get_client(), ACTION_REGION)
        
        # Crop action region
        action_x = int(region["x"] * W)
        action_y = int(region["y"] * H)
        action_w = int(region["w"] * W)
        action_h = int(region["h"] * H)
        
        action_area = img.crop((action_x, action_y, action_x + action_w, action_y + action_h))
        
        # Extract text
        action_text = _extract_text_from_image(action_area)
        
        if not action_text:
            return {
                'actions': [],
                'current_action': None,
                'bet_size': None,
                'aggressor': None
            }
        
        # Parse actions from text
        actions = []
        import re
        
        # Common action patterns
        action_patterns = {
            'fold': r'(\w+)\s+fold(ed)?',
            'call': r'(\w+)\s+call(ed)?',
            'check': r'(\w+)\s+check(ed)?',
            'raise': r'(\w+)\s+rais(ed|e)\s+to\s+(\d+)',
            'bet': r'(\w+)\s+bet\s+(\d+)',
        }
        
        for action_type, pattern in action_patterns.items():
            matches = re.finditer(pattern, action_text, re.IGNORECASE)
            for match in matches:
                player = match.group(1)
                amount = match.group(2) if match.lastindex >= 2 else None
                actions.append({
                    'type': action_type,
                    'player': player,
                    'amount': int(amount) if amount else None
                })
        
        # Determine current action and bet size
        current_action = None
        bet_size = None
        aggressor = None
        
        if actions:
            last_action = actions[-1]
            current_action = last_action['type']
            if last_action['amount']:
                bet_size = last_action['amount']
                aggressor = last_action['player']
        
        return {
            'actions': actions,
            'current_action': current_action,
            'bet_size': bet_size,
            'aggressor': aggressor,
            'raw_text': action_text
        }
        
    except Exception:
        return {
            'actions': [],
            'current_action': None,
            'bet_size': None,
            'aggressor': None
        }


def _tesseract_executable():
    import shutil
    found = shutil.which('tesseract')
    if found:
        return found
    for candidate in ('/opt/homebrew/bin/tesseract', '/usr/local/bin/tesseract'):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _extract_numbers_from_image(img) -> List[str]:
    import re
    return re.findall(_AMOUNT_PATTERN, _extract_text_from_image(img))


_OCR_TEXT_CACHE: Dict[Tuple[Any, ...], str] = {}
_OCR_TEXT_CACHE_MAX = 512

try:
    import Vision as _MacVision
    HAS_MAC_VISION = True
except Exception:
    _MacVision = None
    HAS_MAC_VISION = False


def _extract_text_vision(img, threshold: int = 160, target_height: int = 120, fast: bool = True) -> str:
    """In-process macOS Vision (VNRecognizeTextRequest) OCR fast-path (~15-25ms, zero subprocess overhead)."""
    if not HAS_MAC_VISION or not HAS_PIL or img is None:
        return ''
    if img.width < 1 or img.height < 1:
        return ''
    import hashlib
    import io
    from PIL import ImageOps
    cache_key = (
        'vision',
        img.size,
        img.mode,
        threshold,
        target_height,
        fast,
        hashlib.blake2b(img.tobytes(), digest_size=12).digest(),
    )
    cached = _OCR_TEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        scaled = img.resize(
            (max(1, round(img.width * target_height / img.height)), target_height),
            Image.Resampling.LANCZOS,
        )
        binary = scaled.convert('L').point(lambda p: 0 if p > threshold else 255)
        if binary.getextrema() == (255, 255):
            if len(_OCR_TEXT_CACHE) >= _OCR_TEXT_CACHE_MAX:
                _OCR_TEXT_CACHE.pop(next(iter(_OCR_TEXT_CACHE)))
            _OCR_TEXT_CACHE[cache_key] = ''
            return ''
        binary = ImageOps.expand(binary, border=10, fill=255)
        buf = io.BytesIO()
        binary.save(buf, format='PNG')
        handler = _MacVision.VNImageRequestHandler.alloc().initWithData_options_(buf.getvalue(), None)
        req = _MacVision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(
            _MacVision.VNRequestTextRecognitionLevelFast
            if fast
            else _MacVision.VNRequestTextRecognitionLevelAccurate
        )
        req.setUsesLanguageCorrection_(False)
        ok, _ = handler.performRequests_error_([req], None)
        if not ok or not req.results():
            text = ''
        else:
            text = '\n'.join(
                obs.topCandidates_(1)[0].string()
                for obs in req.results()
                if obs.topCandidates_(1)
            ).strip()
        if len(_OCR_TEXT_CACHE) >= _OCR_TEXT_CACHE_MAX:
            _OCR_TEXT_CACHE.pop(next(iter(_OCR_TEXT_CACHE)))
        _OCR_TEXT_CACHE[cache_key] = text
        return text
    except Exception:
        return ''


def _extract_text_from_image(img, threshold=160, target_height=160, prefer_vision: bool = False) -> str:
    """Read bright table labels locally with Tesseract (or macOS Vision when prefer_vision=True); missing OCR is explicit."""
    import hashlib
    from PIL import ImageOps
    executable = _tesseract_executable()
    if executable is None:
        raise RuntimeError('Amount OCR needs Tesseract. Install it with: brew install tesseract')
    if img.width < 1 or img.height < 1:
        return ''
    if prefer_vision and HAS_MAC_VISION:
        v_text = _extract_text_vision(img, threshold=threshold, target_height=target_height, fast=False)
        if v_text:
            return v_text
    cache_key = (
        executable,
        img.size,
        img.mode,
        threshold,
        target_height,
        hashlib.blake2b(img.tobytes(), digest_size=12).digest(),
    )
    cached = _OCR_TEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    # Normalize Retina/window scaling and turn white/yellow text into black ink.
    scaled = img.resize((max(1, round(img.width * target_height / img.height)), target_height),
                        Image.Resampling.LANCZOS)
    binary = scaled.convert('L').point(lambda p: 0 if p > threshold else 255)
    if binary.getextrema() == (255, 255):
        if len(_OCR_TEXT_CACHE) >= _OCR_TEXT_CACHE_MAX:
            _OCR_TEXT_CACHE.pop(next(iter(_OCR_TEXT_CACHE)))
        _OCR_TEXT_CACHE[cache_key] = ''
        return ''
    binary = ImageOps.expand(binary, border=10, fill=255)
    with tempfile.NamedTemporaryFile(suffix='.png') as image_file:
        binary.save(image_file.name)
        result = subprocess.run([executable, image_file.name, 'stdout', '--psm', '6'],
                                capture_output=True, text=True, timeout=2)
    if result.returncode:
        raise RuntimeError('Amount OCR failed: ' + result.stderr.strip())
    text = result.stdout.strip()
    if not text and HAS_MAC_VISION:
        text = _extract_text_vision(img, threshold=threshold, target_height=target_height, fast=False)
    if len(_OCR_TEXT_CACHE) >= _OCR_TEXT_CACHE_MAX:
        _OCR_TEXT_CACHE.pop(next(iter(_OCR_TEXT_CACHE)))
    _OCR_TEXT_CACHE[cache_key] = text
    return text


def _extract_texts_batch(crops: List[Tuple[Any, int, int]], prefer_vision: bool = False) -> List[str]:
    """Extract text for a list of (img_crop, threshold, target_height) tuples."""
    if prefer_vision and HAS_MAC_VISION:
        return [
            _extract_text_vision(crop, threshold=thresh, target_height=th)
            or _extract_text_from_image(crop, threshold=thresh, target_height=th)
            for crop, thresh, th in crops
        ]
    return [
        _extract_text_from_image(crop, threshold=thresh, target_height=th)
        for crop, thresh, th in crops
    ]


STACK_REGIONS = ((.44, .235, .12, .04), (.80, .318, .13, .048),
                 (.82, .727, .14, .04), (.455, .895, .09, .033),
                 (.04, .727, .14, .04), (.06, .318, .13, .048))
BET_REGIONS = ((.455, .30, .09, .045), (.69, .352, .09, .04),
               (.73, .607, .09, .04), (.455, .665, .09, .045),
               (.18, .607, .09, .04), (.18, .352, .09, .04))
VPIP_REGIONS = (
    (0.436, 0.150, 0.028, 0.028),  # seat 0 (top center)
    (0.796, 0.250, 0.028, 0.028),  # seat 1 (top right)
    (0.828, 0.660, 0.028, 0.028),  # seat 2 (bottom right)
    (0.434, 0.814, 0.028, 0.028),  # seat 3 (Hero bottom center)
    (0.047, 0.660, 0.028, 0.028),  # seat 4 (bottom left)
    (0.077, 0.250, 0.028, 0.028),  # seat 5 (top left)
)


def detect_seat_vpips(img, seats: Optional[List[int]] = None) -> Dict[int, int]:
    """Read GGPoker avatar VPIP badges (0..100%) for each occupied seat."""
    import re
    if not HAS_PIL or img is None or _get_client() not in ('ggpoker', None):
        return {}
    vpips: Dict[int, int] = {}
    seat_list = seats if seats is not None else list(range(len(VPIP_REGIONS)))
    for seat in seat_list:
        if not (0 <= seat < len(VPIP_REGIONS)):
            continue
        try:
            rx, ry, rw, rh = VPIP_REGIONS[seat]
            crop = _crop(img, {'x': rx, 'y': ry, 'w': rw, 'h': rh})
            gray = crop.convert('L')
            lo, hi = gray.getextrema()
            # Skip solid/blank regions immediately (0ms on synthetic images or empty seats)
            if hi < 175 or (hi - lo) < 60:
                continue
            txt = _extract_text_vision(crop, threshold=180, target_height=100, fast=True)
            if not txt and getattr(_extract_text_from_image, '__name__', '') == '_extract_text_from_image':
                txt = _extract_text_from_image(crop, threshold=180, target_height=100)
            matches = [int(m) for m in re.findall(r'\b(\d{1,2}|100)\b', txt) if 0 <= int(m) <= 100]
            if matches:
                vpips[seat] = matches[-1]
        except Exception:
            continue
    return vpips


def detect_preflop_context(img, position_info, table_name=None, table_units='chips', big_blind=None):
    """Read observable amounts; action classification belongs to the frame tracker."""
    from table_context import parse_amount, parse_blinds, convert_amount
    data = dict(complete=False, bets={}, stacks={}, positions=position_info.get('seat_positions') or {},
                units=table_units, big_blind=None, small_blind=None, board_present=False)
    if _get_client() not in ('ggpoker', 'pokerstars'):
        data['error'] = 'Automatic betting context is currently calibrated for GGPoker'
        return data
    try:
        title = table_name or _extract_text_from_image(
            _crop(img, dict(x=.05, y=0, w=.6, h=.03)), threshold=100, target_height=100)
        blinds = parse_blinds(title)
        if big_blind is not None and (not blinds or blinds[1] != big_blind):
            blinds = (big_blind / 2, big_blind)
        if not blinds:
            data['error'] = 'Blinds unreadable — enter the big blind'
            return data
        data['small_blind'], data['big_blind'] = blinds
        # Any visible card face suppresses preflop advice, even if its rank is unreadable.
        board_region = BOARD_REGIONS['ggpoker']
        stack_regions, bet_regions = STACK_REGIONS, BET_REGIONS
        if _get_client() == 'pokerstars':
            from pokerstars import BOARD, STACKS, BETS
            board_region, stack_regions, bet_regions = BOARD, STACKS, BETS
        data['board_present'] = len(_locate_board_cards(_crop(img, board_region))) in (3, 4, 5)
        seats = position_info.get('occupied_seats') or []
        raw_stacks, raw_bets = {}, {}
        for seat in seats:
            if 'raw_stacks' in position_info:
                raw_stacks[seat] = position_info['raw_stacks'].get(seat)
            else:
                stack_crop = _crop(img, dict(zip(('x', 'y', 'w', 'h'), stack_regions[seat])))
                text = _extract_text_from_image(stack_crop, threshold=100, target_height=100)
                raw_stacks[seat] = parse_amount(text)
                if (raw_stacks[seat] is None and _get_client() == 'ggpoker'
                        and getattr(_extract_text_from_image, '__name__', '') == '_extract_text_from_image'):
                    rx, ry, rw, rh = stack_regions[seat]
                    alt_crop = _crop(img, {
                        'x': rx + 0.012,
                        'y': 0.218 if seat == 0 else ry,
                        'w': max(0.06, rw - 0.024),
                        'h': 0.036 if seat == 0 else rh,
                    })
                    if alt_crop.convert('L').getextrema()[0] != alt_crop.convert('L').getextrema()[1]:
                        raw_stacks[seat] = parse_amount(
                            _extract_text_from_image(alt_crop, threshold=100, target_height=100)
                        )
            bet_crop = _crop(img, dict(zip(('x', 'y', 'w', 'h'), bet_regions[seat])))
            if _get_client() == 'pokerstars':
                from pokerstars import read_amount
                raw_bets[seat], _ = read_amount(bet_crop, bet=True)
            else:
                text = _extract_text_from_image(bet_crop, threshold=130, target_height=100)
                raw_bets[seat] = parse_amount(text)
                bright_px = sum(p > 150 for p in bet_crop.convert('L').getdata())
                min_bright = max(3, bet_crop.width * bet_crop.height * .002)
                if not text and bright_px < min_bright:
                    raw_bets[seat] = (0, None)
                elif (raw_bets[seat] is None and bright_px >= min_bright
                      and getattr(_extract_text_from_image, '__name__', '') == '_extract_text_from_image'):
                    bx, by, bw, bh = bet_regions[seat]
                    alt_bet_crop = _crop(img, {
                        'x': max(0.0, bx - 0.005),
                        'y': max(0.0, by - 0.010),
                        'w': bw + 0.025,
                        'h': bh + 0.012,
                    })
                    for thr in (130, 160):
                        v_txt = _extract_text_vision(alt_bet_crop, threshold=thr, target_height=100, fast=True) if HAS_MAC_VISION else ''
                        parsed_bet = parse_amount(v_txt) if v_txt else None
                        if parsed_bet is None:
                            parsed_bet = parse_amount(_extract_text_from_image(alt_bet_crop, threshold=thr, target_height=100))
                        if parsed_bet is not None:
                            raw_bets[seat] = parsed_bet
                            break
        explicit_units = {v[1] for v in list(raw_stacks.values()) + list(raw_bets.values()) if v and v[1]}
        if explicit_units == {'bb'}:
            data['units'] = 'bb'
        for source, destination in ((raw_stacks, 'stacks'), (raw_bets, 'bets')):
            data[destination] = {s: convert_amount(value[0], value[1] or data['units'], 'chips', blinds[1])
                                 if value else None for s, value in source.items()}
        pot, call = detect_pot_size(img), detect_call_amount(img)
        data['pot'] = convert_amount(pot, data['units'], 'chips', blinds[1]) if pot is not None else None
        data['call'] = convert_amount(call, data['units'], 'chips', blinds[1]) if call is not None else None
        data['raise_available'] = is_raise_button_available(img)
        data['presets_available'] = is_preset_bar_available(img)
        data['action_turn'] = bool(data['call'] is not None or detect_raise_button(img))
        # If non-blind seats have occluded/unparseable wager crops (e.g. dealer
        # puck or avatar chrome) and the known wagers already account for the
        # entire total pot, every missing seat's wager must be 0 because wagers
        # are non-negative.
        missing_bets = [s for s, v in data['bets'].items() if v is None]
        if (missing_bets and data['pot'] is not None and not data['board_present']
                and all(data['positions'].get(s) not in ('SB', 'BB', None) for s in missing_bets)):
            known_sum = sum(v for v in data['bets'].values() if v is not None)
            if abs(data['pot'] - known_sum) <= blinds[1] * .01:
                for s in missing_bets:
                    data['bets'][s] = 0
        if (len(missing_bets) == 1 and data['pot'] is not None and not data['board_present']
                and set(data['positions']) == set(seats)):
            missing_seat = missing_bets[0]
            known_sum = sum(v for v in data['bets'].values() if v is not None)
            inferred = round(data['pot'] - known_sum, 6)
            if inferred >= 0:
                if (missing_seat != 3 or data['call'] is None or
                        abs(inferred + data['call'] - max([inferred] + [v for v in data['bets'].values() if v is not None])) <= blinds[1] * .01):
                    data['bets'][missing_seat] = int(inferred) if float(inferred).is_integer() else inferred
        data['complete'] = (3 in seats and set(data['positions']) == set(seats)
                            and all(v is not None for v in data['bets'].values()))
        if not data['complete']:
            pending = []
            if not data['positions']:
                pending.append('dealer / occupied seats')
            pending.extend(f"{data['positions'].get(s, 'seat ' + str(s + 1))} wager"
                           for s, value in data['bets'].items() if value is None)
            data['error'] = 'Re-reading ' + ', '.join(pending or ['your seat'])
    except Exception as exc:
        data['error'] = str(exc)
    return data


def detect_postflop_wager_call(img, position_info=None, big_blind=None, table_units='chips') -> Optional[float]:
    """Infer facing postflop call amount from seat wagers when action buttons are not visible.

    Returns the positive amount needed to match the highest visible opponent wager
    on the felt, or 0 when no opponent wager is present.
    """
    from table_context import parse_amount, convert_amount
    try:
        client = _get_client()
        bet_regions = BET_REGIONS
        if client == 'pokerstars':
            from pokerstars import BETS, read_amount
            bet_regions = BETS
        seats = (position_info or {}).get('occupied_seats') or list(range(6))
        bets = {}
        for seat in seats:
            if not (0 <= seat < len(bet_regions)):
                continue
            bet_crop = _crop(img, dict(zip(('x', 'y', 'w', 'h'), bet_regions[seat])))
            bright = sum(p > 150 for p in bet_crop.convert('L').getdata())
            if bright < max(3, bet_crop.width * bet_crop.height * .002):
                bets[seat] = 0.0
                continue
            if client == 'pokerstars':
                parsed, _ = read_amount(bet_crop, bet=True)
            else:
                text = _extract_text_from_image(bet_crop, threshold=130, target_height=100)
                parsed = parse_amount(text)
            if parsed:
                val, unit = parsed
                if unit and big_blind and unit != table_units:
                    val = convert_amount(val, unit, table_units, big_blind)
                bets[seat] = float(val)
        hero_bet = bets.get(3, 0.0)
        max_opp_bet = max((v for s, v in bets.items() if s != 3), default=0.0)
        if max_opp_bet > hero_bet:
            diff = round(max_opp_bet - hero_bet, 4)
            return int(diff) if float(diff).is_integer() else diff
        return 0
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Full State Capture (Postflop Auto-Detection)
# ---------------------------------------------------------------------------

def capture_and_read_full_state(table_name=None, window_id=None) -> Dict[str, Any]:
    """
    Capture and read the full poker table state for postflop analysis.
    
    This function automatically detects:
    - Hero's hole cards
    - Board cards (flop/turn/river)
    - Pot size
    - Call amount
    - Current action
    
    Args:
        None (will capture the active poker window)
        
    Returns:
        Dictionary with:
        - hole_cards: Hero's hand (e.g., "AKs")
        - board: Board cards (e.g., "QdJd8s")
        - board_info: Detailed board information
        - pot_size: Current pot size
        - call_amount: Amount to call
        - action_info: Action history and current action
        - status: Capture status
        - error: Error message if any
    """
    result = {
        'hole_cards': None,
        'cards': None,
        'table_id': None,
        'captured_at': time.monotonic(),
        'board': None,
        'board_info': None,
        'pot_size': None,
        'call_amount': None,
        'inferred_call_amount': None,
        'position': None,
        'occupied_seats': None,
        'active_seats': None,
        'active_opponents': 1,
        'action_info': None,
        'status': 'success',
        'error': None
    }
    
    client_token = None
    try:
        # Find and capture the poker window
        found = (find_poker_window(window_id=window_id) if window_id is not None else
                 find_ggpoker_window(table_name) if table_name else find_ggpoker_window())
        if not found:
            result['status'] = 'error'
            result['error'] = 'No poker window found'
            return result
        
        result['table_id'] = window_id if window_id is not None else _WINDOW_IDS.get(tuple(found), tuple(found))
        result['window_bounds'] = tuple(found)
        client = _WINDOW_CLIENTS.get(result['table_id'], _CLIENT)
        client_token = _capture_client.set(client)
        result['client'] = client
        if client not in ('ggpoker', 'pokerstars'):
            result.update(status='unsupported', message=f'{client}: table connected; use manual cards and action context')
            result['error'] = 'Automatic card and betting OCR is currently calibrated for GGPoker'
            return result
        x, y, w, h = found
        img = capture_window(found, window_id=window_id) if window_id is not None else capture_window(found)
        
        if img is None:
            result['status'] = 'error'
            result['error'] = 'Screenshot failed'
            return result
        
        # Detect hole cards (with multi-strategy fallback)
        reading = _read_hand_with_fallback(img, detailed=True)
        hole_cards = reading.hand if reading else None
        result['hole_cards'] = hole_cards
        result['hand'] = hole_cards if (reading and reading.reliable) else None
        result['cards'] = reading.cards if reading and reading.reliable else None
        result['reliable'] = bool(reading and reading.reliable)
        result['table_name'] = table_name
        if not result['reliable'] and client == 'ggpoker':
            result['open_cards_button'] = detect_open_cards_button(img)
            if not result['open_cards_button']:
                result['sit_in_button'] = detect_sit_in_button(img)
        
        # Detect board cards
        board_info = detect_board_cards_advanced(img)
        result['board'] = board_info.get('board')
        result['board_info'] = board_info
        
        # Detect pot size
        pot_size = detect_pot_size(img)
        result['pot_size'] = pot_size
        
        # Detect call amount
        call_amount = detect_call_amount(img)
        result['call_amount'] = call_amount
        result['raise_available'] = is_raise_button_available(img)
        result['presets_available'] = is_preset_bar_available(img)
        from table_context import parse_blinds
        title = table_name or _extract_text_from_image(
            _crop(img, dict(x=.05, y=0, w=.6, h=.03)), threshold=100, target_height=100)
        blinds = parse_blinds(title)
        result['big_blind'] = blinds[1] if blinds else None

        # Detect seat occupancy, position, and active opponents
        if client in ('ggpoker', 'pokerstars'):
            position_info = detect_position_and_spot(img)
            result['position'] = position_info.get('position')
            result['occupied_seats'] = position_info.get('occupied_seats')
            result['active_seats'] = position_info.get('active_seats')
            result['active_opponents'] = position_info.get('active_opponents', 1)
        else:
            position_info = {}

        if call_amount is None and result['board']:
            result['inferred_call_amount'] = detect_postflop_wager_call(
                img, position_info, result.get('big_blind'))
        elif result.get('reliable') and not result['board'] and client in ('ggpoker', 'pokerstars'):
            result['preflop'] = detect_preflop_context(img, position_info, table_name)
            result['vpips'] = detect_seat_vpips(img, position_info.get('occupied_seats'))
        
        # Detect action history
        action_info = detect_action_history(img)
        result['action_info'] = action_info
        
        # Update status based on what was detected
        detected_items = sum([
            1 if hole_cards else 0,
            1 if board_info.get('board') else 0,
            1 if pot_size else 0,
        ])
        
        if detected_items >= 2:
            result['status'] = 'success'
        elif detected_items >= 1:
            result['status'] = 'partial'
        else:
            result['status'] = 'no_data'
        
        return result
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        return result
    finally:
        if client_token is not None:
            _capture_client.reset(client_token)


# ---------------------------------------------------------------------------
# Calibration helper
# ---------------------------------------------------------------------------

def calibrate(save_path="card_region.png", region=None):
    """Save the current hole-card crop so the user can verify/adjust CARD_REGION.

    If `region` is given it overrides CARD_REGION (dict with x/y/w/h fractions).
    The saved image is the full window with the card region outlined in red,
    plus the two card sub-regions outlined in green, so alignment is obvious.
    """
    found = find_ggpoker_window()
    if not found:
        return None
    x, y, w, h = found
    img = capture_window((x, y, w, h))
    if img is None:
        return None
    reg = region or CARD_REGION
    from PIL import ImageDraw
    vis = img.convert("RGB")
    d = ImageDraw.Draw(vis)
    W, H = vis.size
    left_r, right_r = _card_subregions(reg)
    for r, color in ((reg, (255, 0, 0)), (left_r, (0, 255, 0)), (right_r, (0, 255, 0))):
        x0 = int(r["x"] * W); y0 = int(r["y"] * H)
        x1 = int((r["x"] + r["w"]) * W); y1 = int((r["y"] + r["h"]) * H)
        d.rectangle([x0, y0, x1, y1], outline=color, width=2)
    vis.save(save_path)
    return save_path


# ---------------------------------------------------------------------------
# One-shot capture + read
# ---------------------------------------------------------------------------

def _locate_cards_in_image(img) -> Optional[Dict[str, float]]:
    """Locate hole cards in an already-captured image without re-capturing.
    
    Finds the largest light blob in the lower 60% of the image and returns
    a CARD_REGION-style dict. Returns None if no plausible card blob found.
    """
    g = img.convert("L")
    W, H = g.size
    px = list(g.getdata())
    hist = [0] * 256
    for v in px:
        hist[v] += 1
    felt = max(range(256), key=lambda v: hist[v])
    # Light pixels (cards) in the lower 60% of the window
    y0 = int(H * 0.4)
    light = [[1 if px[yy * W + xx] > felt + 40 else 0 for xx in range(W)]
             for yy in range(y0, H)]
    ys = [yy for yy in range(len(light)) if any(light[yy])]
    xs = [xx for xx in range(W) if any(light[yy][xx] for yy in range(len(light)))]
    if not ys or not xs:
        return None
    top, bot = min(ys), max(ys)
    left, right = min(xs), max(xs)
    bw, bh = right - left + 1, bot - top + 1
    # Require a card-like aspect (two cards side by side ~ 1.4:1)
    if bw < 40 or bh < 30 or bw / bh < 1.0 or bw / bh > 3.0:
        return None
    return {
        "x": left / W,
        "y": (y0 + top) / H,
        "w": bw / W,
        "h": bh / H,
    }


def _read_hand_with_fallback(img, debug: bool = False, detailed=False):
    """Read hole cards using fixed region, then offset grid, then dynamic scan.
    
    Tries three strategies in order:
    1. Fixed CARD_REGION (fast path, works when layout matches default)
    2. _region_offsets grid (handles slight misalignment / theme differences)
    3. Dynamic card locator (finds light blobs in lower half of image)
    
    Returns:
        Hand string like 'AKs' or None if all strategies fail
    """
    if _get_client() == 'pokerstars':
        from pokerstars import read_hand
        reading = read_hand(img)
        return reading if detailed else reading.hand if reading else None
    reader = _read_region_cards if detailed else _read_region_hand
    # Strategy 1: Fixed region (fast path)
    region = CARD_REGIONS.get(_get_client(), CARD_REGION)
    hand = reader(img, region, debug=debug)
    uncertain = hand if detailed else None
    if hand and (not detailed or hand.reliable):
        return hand
    
    if debug:
        print("[DEBUG _read_hand_with_fallback] Fixed region failed, trying offset grid...")
    
    # Strategy 2: Offset grid (handles slight position shifts)
    for r in _region_offsets(region):
        if r is region:
            continue  # Already tried the base region
        if detailed and _get_client() == 'ggpoker' and r['y'] < .55:
            continue
        hand = reader(img, r, debug=debug)
        if hand and (not detailed or hand.reliable):
            if debug:
                print(f"[DEBUG _read_hand_with_fallback] Offset region matched: x={r['x']:.3f} y={r['y']:.3f}")
            return hand
    
    if debug:
        print("[DEBUG _read_hand_with_fallback] Offset grid failed, trying dynamic scan...")
    
    # Strategy 3: Dynamic card locator (finds light blobs)
    dyn_region = _locate_cards_in_image(img)
    if dyn_region and (not detailed or (dyn_region['y'] >= .55 and
                                       dyn_region['w'] <= .3 and dyn_region['h'] <= .25)):
        if debug:
            print(f"[DEBUG _read_hand_with_fallback] Dynamic region found: x={dyn_region['x']:.3f} y={dyn_region['y']:.3f} w={dyn_region['w']:.3f} h={dyn_region['h']:.3f}")
        hand = reader(img, dyn_region, debug=debug)
        if hand and (not detailed or hand.reliable):
            return hand
    
    return uncertain


def capture_and_read(max_retries: int = 4, debug: bool = False) -> Optional[str]:
    """Find GGPoker window, screenshot, read hole cards with retry logic.
    
    Uses exponential backoff (1s, 2s, 4s, 8s max) when cards aren't detected.
    Employs a multi-strategy fallback: fixed region -> offset grid -> dynamic scan.
    
    Args:
        max_retries: Maximum number of retry attempts (default 4)
        debug: If True, print debug information about suit detection
        
    Returns:
        Hand string like 'AKs' or None if detection fails
    """
    OCRStatus.set_status(OCRStatus.WATCHING, "Scanning for cards...")
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = get_retry_delay(attempt - 1)
            OCRStatus.increment_retry()
            OCRStatus.set_status(OCRStatus.RETRYING, f"Retry {attempt}/{max_retries} in {delay:.1f}s...")
            time.sleep(delay)
        
        try:
            found = find_ggpoker_window()
            if not found:
                if debug:
                    print(f"[DEBUG capture_and_read] Attempt {attempt}: No poker window found")
                OCRStatus.set_status(OCRStatus.ERROR, "No poker window found")
                continue
                
            x, y, w, h = found
            if debug:
                print(f"[DEBUG capture_and_read] Attempt {attempt}: Window found at ({x}, {y}, {w}, {h})")
            
            img = capture_window((x, y, w, h))
            if img is None:
                if debug:
                    print(f"[DEBUG capture_and_read] Attempt {attempt}: Screenshot failed")
                OCRStatus.set_status(OCRStatus.ERROR, "Screenshot failed")
                continue
            
            if debug:
                print(f"[DEBUG capture_and_read] Attempt {attempt}: Screenshot captured, size={img.size}")
                
            hand = _read_hand_with_fallback(img, debug=debug)
            
            if hand:
                if debug:
                    print(f"[DEBUG capture_and_read] Attempt {attempt}: Hand detected: {hand}")
                OCRStatus.reset_retry()
                OCRStatus.set_status(OCRStatus.DETECTED, f"Detected: {hand}")
                OCRStatus.set_last_hand(hand)
                return hand
            else:
                if debug:
                    print(f"[DEBUG capture_and_read] Attempt {attempt}: Cards not detected in image")
                OCRStatus.set_status(OCRStatus.WATCHING, "No face-up hole cards detected")
                
        except Exception as e:
            if debug:
                print(f"[DEBUG capture_and_read] Attempt {attempt}: Exception: {str(e)}")
            OCRStatus.set_status(OCRStatus.ERROR, f"Error: {str(e)}")
            continue
    
    # All retries exhausted
    if debug:
        print(f"[DEBUG capture_and_read] All {max_retries} retries exhausted")
    # Preserve the actual failure (window, capture, or no visible cards).
    return None


def capture_and_read_with_position(max_retries: int = 0, debug: bool = False,
                                   table_name=None, include_context=False,
                                   table_units='chips', big_blind=None, window_id=None) -> Dict[str, Any]:
    """Read cards and position from one frame; publish evidence, never defaults."""
    result = dict(hand=None, cards=None, reliable=False, position=None, spot=None,
                  status='watching', error=None, table_id=None, table_name=table_name,
                  captured_at=time.monotonic())
    client_token = None
    try:
        found = (find_poker_window(window_id=window_id) if window_id is not None else
                 find_ggpoker_window(table_name) if table_name else find_ggpoker_window())
        if not found:
            raise RuntimeError('No poker window found')
        result['table_id'] = window_id if window_id is not None else _WINDOW_IDS.get(tuple(found), tuple(found))
        result['window_bounds'] = tuple(found)
        client = _WINDOW_CLIENTS.get(result['table_id'], _CLIENT)
        client_token = _capture_client.set(client)
        result['client'] = client
        if client not in ('ggpoker', 'pokerstars'):
            result.update(status='unsupported', message=f'{client}: table connected; use manual cards and action context')
            result['error'] = 'Automatic card and betting OCR is currently calibrated for GGPoker'
            return result
        img = capture_window(found, window_id=window_id) if window_id is not None else capture_window(found)
        if img is None:
            raise RuntimeError('Screenshot failed')
        reading = _read_hand_with_fallback(img, debug=debug, detailed=True)
        preview_region = (dict(zip(('x', 'y', 'w', 'h'), reading.region))
                          if reading and reading.region else CARD_REGIONS.get(_get_client(), CARD_REGION))
        result['preview'] = _crop(img, preview_region)
        if reading:
            result.update(hand=reading.hand, cards=reading.cards, reliable=reading.reliable,
                          rank_distances=reading.rank_distances, rank_margins=reading.rank_margins)
            result['status'] = 'detected' if reading.reliable else 'uncertain'
            result['message'] = ('Cards read; awaiting confirmation' if reading.reliable
                                 else 'Uncertain rank or suit — waiting for a clearer frame')
            position_info = detect_position_and_spot(img)
            result.update(position=position_info.get('position'), spot=position_info.get('spot'),
                          occupied_seats=position_info.get('occupied_seats'),
                          active_seats=position_info.get('active_seats'),
                          active_opponents=position_info.get('active_opponents', 1))
            if include_context and reading.reliable:
                preflop = detect_preflop_context(
                    img, position_info, table_name, table_units, big_blind)
                if preflop.get('board_present'):
                    board_info = detect_board_cards_advanced(img)
                    preflop['board'] = board_info.get('board')
                    preflop['board_info'] = board_info
                    if preflop.get('call') is None:
                        known_bets = {s: v for s, v in (preflop.get('bets') or {}).items() if v is not None}
                        hero_bet = known_bets.get(3, 0)
                        max_opp = max((v for s, v in known_bets.items() if s != 3), default=0)
                        preflop['inferred_call'] = round(max_opp - hero_bet, 4) if max_opp > hero_bet else 0
                if client == 'ggpoker':
                    vpips = detect_seat_vpips(img, seats=position_info.get('occupied_seats'))
                    if vpips:
                        preflop['seat_vpips'] = vpips
                        result['seat_vpips'] = vpips
                result['preflop'] = preflop
                result['raise_available'] = preflop.get('raise_available', True)
                result['presets_available'] = preflop.get('presets_available', True)
            elif client == 'ggpoker':
                result['raise_available'] = is_raise_button_available(img)
                result['presets_available'] = is_preset_bar_available(img)
                open_btn = detect_open_cards_button(img)
                result['open_cards_button'] = open_btn
                if open_btn:
                    result['message'] = 'Card squeeze Open button detected — opening cards...'
                else:
                    sit_in_btn = detect_sit_in_button(img)
                    result['sit_in_button'] = sit_in_btn
                    if sit_in_btn:
                        result['message'] = "Sit-out 'I'm Back' button detected — sitting back in..."
        else:
            open_btn = detect_open_cards_button(img) if client == 'ggpoker' else False
            sit_in_btn = (detect_sit_in_button(img) if (client == 'ggpoker' and not open_btn) else False)
            result['open_cards_button'] = open_btn
            result['sit_in_button'] = sit_in_btn
            if open_btn:
                result['message'] = 'Card squeeze Open button detected — opening cards...'
            elif sit_in_btn:
                result['message'] = "Sit-out 'I'm Back' button detected — sitting back in..."
            else:
                result['message'] = 'No face-up hole cards detected'
    except Exception as exc:
        result.update(status='error', message=str(exc), error=str(exc))
    finally:
        if client_token is not None:
            _capture_client.reset(client_token)
    return result


def detect_position_and_spot(img: Optional[Image.Image] = None,
                             action_text: str = "") -> Dict[str, Any]:
    """
    Detect player position and current spot from table screenshot.
    
    This function:
    1. Parses the GGPoker window to detect the dealer button position
    2. Auto-detects hero's position (BTN, SB, BB, UTG, MP, CO) based on dealer button
    3. Auto-detects the spot (open, facing open, facing 3bet) from action history
    
    Args:
        img: Optional table screenshot (will capture if not provided)
        action_text: Optional action history text for spot detection
        
    Returns:
        Dictionary with:
        - position: Hero's position (BTN, SB, BB, UTG, MP, CO)
        - spot: Current spot (open, facing_open, facing_3bet, facing_4bet)
        - dealer_button: (x, y) coordinates of dealer button
        - status: Detection status (success, error, partial)
    """
    if not HAS_POSITION_DETECTOR:
        return {
            'position': None,
            'spot': None,
            'dealer_button': None,
            'status': 'error',
            'error': 'Position detector not available'
        }
    
    try:
        # Capture image if not provided
        if img is None:
            found = find_ggpoker_window()
            if not found:
                return {
                    'position': None,
                    'spot': None,
                    'dealer_button': None,
                    'status': 'error',
                    'error': 'No poker window found'
                }
            x, y, w, h = found
            img = capture_window((x, y, w, h))
            if img is None:
                return {
                    'position': None,
                    'spot': None,
                    'dealer_button': None,
                    'status': 'error',
                    'error': 'Screenshot failed'
                }
        
        if _get_client() == 'pokerstars':
            from pokerstars import position
            return position(img)
        # Position detection repeatedly flood-fills bright areas. Bound its
        # input so Retina screenshots do not delay publishing the card result.
        analysis_image = img.copy()
        analysis_image.thumbnail((800, 600))
        position_info = _detect_position_and_spot(analysis_image, action_text)
        button = position_info.get('dealer_button')
        if button:
            position_info['dealer_button'] = (
                round(button[0] * img.width / analysis_image.width),
                round(button[1] * img.height / analysis_image.height))
        return position_info
        
    except Exception as e:
        return {
            'position': None,
            'spot': None,
            'dealer_button': None,
            'status': 'error',
            'error': str(e)
        }


def scan_region():
    """Heuristically locate the two hole cards and return a CARD_REGION dict.

    GGPoker hole cards are two light rectangles side by side near the bottom
    centre of the dark table. We find the largest light blob in the lower
    half of the window and assume it is the card pair, then split it in two.
    Returns None if no plausible card blob is found.
    """
    found = find_ggpoker_window()
    if not found:
        return None
    x, y, w, h = found
    img = capture_window((x, y, w, h))
    if img is None:
        return None
    g = img.convert("L")
    W, H = g.size
    px = list(g.getdata())
    hist = [0] * 256
    for v in px:
        hist[v] += 1
    felt = max(range(256), key=lambda v: hist[v])
    # light pixels (cards) in the lower 60% of the window
    y0 = int(H * 0.4)
    light = [[1 if px[yy * W + xx] > felt + 40 else 0 for xx in range(W)]
             for yy in range(y0, H)]
    # bounding box of light pixels
    ys = [yy for yy in range(len(light)) if any(light[yy])]
    xs = [xx for xx in range(W) if any(light[yy][xx] for yy in range(len(light)))]
    if not ys or not xs:
        return None
    top, bot = min(ys), max(ys)
    left, right = min(xs), max(xs)
    # require a card-like aspect (two cards side by side ~ 1.4:1)
    bw, bh = right - left + 1, bot - top + 1
    if bw < 40 or bh < 30 or bw / bh < 1.0 or bw / bh > 3.0:
        return None
    return {
        "x": left / W,
        "y": (y0 + top) / H,
        "w": bw / W,
        "h": bh / H,
    }


# Global debug flag for suit detection
DEBUG_SUIT_DETECTION = False


def set_debug_suit_detection(enabled: bool):
    """Enable or disable debug output for suit detection."""
    global DEBUG_SUIT_DETECTION
    DEBUG_SUIT_DETECTION = enabled


def calibrate_suits(save_path="suit_calibration.png"):
    """
    Capture and save suit glyph crops for debugging suit detection.
    
    This saves individual suit glyph areas from the hole cards so you can
    verify the suit detection is working correctly.
    
    Args:
        save_path: Path to save the calibration image
        
    Returns:
        Path to saved image or None if capture failed
    """
    found = find_ggpoker_window()
    if not found:
        return None
    x, y, w, h = found
    img = capture_window((x, y, w, h))
    if img is None:
        return None
    
    # Create a visualization showing suit glyph areas
    from PIL import ImageDraw, ImageFont
    
    vis = Image.new("RGB", (800, 400), (40, 40, 40))
    draw = ImageDraw.Draw(vis)
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    
    # Draw title
    draw.text((10, 10), "Suit Glyph Calibration", fill=(255, 255, 255), font=font)
    
    # Split into left and right card regions
    left_r, right_r = _card_subregions(CARD_REGIONS.get(_get_client(), CARD_REGION))
    
    # Extract suit glyph areas from each card
    W, H = img.size
    
    # Left card suit area
    left_suit_x = int(left_r["x"] * W + left_r["w"] * W * 0.08)
    left_suit_y = int(left_r["y"] * H + left_r["h"] * H * 0.50)
    left_suit_w = int(left_r["w"] * W * 0.42)
    left_suit_h = int(left_r["h"] * H * 0.40)
    
    # Right card suit area
    right_suit_x = int(right_r["x"] * W + right_r["w"] * W * 0.08)
    right_suit_y = int(right_r["y"] * H + right_r["h"] * H * 0.50)
    right_suit_w = int(right_r["w"] * W * 0.42)
    right_suit_h = int(right_r["h"] * H * 0.40)
    
    # Crop and display suit areas
    try:
        left_suit = img.crop((left_suit_x, left_suit_y,
                              left_suit_x + left_suit_w,
                              left_suit_y + left_suit_h))
        left_suit = left_suit.resize((150, 150), Image.BILINEAR)
        vis.paste(left_suit, (10, 50))
        draw.rectangle([10, 50, 160, 200], outline=(0, 255, 0), width=2)
        draw.text((10, 205), "Left Card Suit Area", fill=(255, 255, 255), font=font)
        
        # Analyze left suit
        left_color = _get_suit_glyph_color(left_suit)
        left_is_red = _is_red(left_color) if left_color else False
        left_suit_char, left_conf = read_suit_glyph(img.crop((
            int(left_r["x"] * W), int(left_r["y"] * H),
            int((left_r["x"] + left_r["w"]) * W), int((left_r["y"] + left_r["h"]) * H)
        )))
        
        draw.text((10, 220), f"Color: RGB{left_color}, Red: {left_is_red}",
                  fill=(255, 200, 100), font=font)
        draw.text((10, 235), f"Detected: {left_suit_char}, Confidence: {left_conf:.2f}",
                  fill=(100, 255, 100), font=font)
    except Exception as e:
        draw.text((10, 205), f"Error: {str(e)}", fill=(255, 100, 100), font=font)
    
    # Right card suit area
    try:
        right_suit = img.crop((right_suit_x, right_suit_y,
                               right_suit_x + right_suit_w,
                               right_suit_y + right_suit_h))
        right_suit = right_suit.resize((150, 150), Image.BILINEAR)
        vis.paste(right_suit, (200, 50))
        draw.rectangle([200, 50, 350, 200], outline=(0, 255, 0), width=2)
        draw.text((200, 205), "Right Card Suit Area", fill=(255, 255, 255), font=font)
        
        # Analyze right suit
        right_color = _get_suit_glyph_color(right_suit)
        right_is_red = _is_red(right_color) if right_color else False
        right_suit_char, right_conf = read_suit_glyph(img.crop((
            int(right_r["x"] * W), int(right_r["y"] * H),
            int((right_r["x"] + right_r["w"]) * W), int((right_r["y"] + right_r["h"]) * H)
        )))
        
        draw.text((200, 220), f"Color: RGB{right_color}, Red: {right_is_red}",
                  fill=(255, 200, 100), font=font)
        draw.text((200, 235), f"Detected: {right_suit_char}, Confidence: {right_conf:.2f}",
                  fill=(100, 255, 100), font=font)
    except Exception as e:
        draw.text((200, 205), f"Error: {str(e)}", fill=(255, 100, 100), font=font)
    
    # Draw suited/offsuit determination
    draw.text((400, 50), "Suited/Offsuit Determination", fill=(255, 255, 255), font=font)
    
    if left_color and right_color:
        suited = left_is_red == right_is_red
        result = "SUITED" if suited else "OFFSUIT"
        color = (100, 255, 100) if suited else (255, 200, 100)
        draw.text((400, 80), f"Left is red: {left_is_red}", fill=(255, 255, 255), font=font)
        draw.text((400, 100), f"Right is red: {right_is_red}", fill=(255, 255, 255), font=font)
        draw.text((400, 130), f"Result: {result}", fill=color, font=font)
        
        # Draw explanation
        draw.text((400, 170), "Explanation:", fill=(200, 200, 200), font=font)
        if suited:
            draw.text((400, 190), "Both suits are the same color", fill=(150, 150, 150), font=font)
            draw.text((400, 205), "(both red OR both black)", fill=(150, 150, 150), font=font)
        else:
            draw.text((400, 190), "Suits are different colors", fill=(150, 150, 150), font=font)
            draw.text((400, 205), "(one red, one black)", fill=(150, 150, 150), font=font)
    
    vis.save(save_path)
    return save_path


def calibrate_board(save_path="board_calibration.png"):
    """
    Capture and save board region for debugging board detection.
    
    This saves a visualization of the board region with detected card
    positions outlined, so you can verify the board detection is working.
    
    Args:
        save_path: Path to save the calibration image
        
    Returns:
        Path to saved image or None if capture failed
    """
    found = find_ggpoker_window()
    if not found:
        return None
    x, y, w, h = found
    img = capture_window((x, y, w, h))
    if img is None:
        return None
    
    from PIL import ImageDraw, ImageFont
    
    W, H = img.size
    region = BOARD_REGIONS.get(_get_client(), BOARD_REGION)
    
    # Create visualization
    vis = img.convert("RGB")
    draw = ImageDraw.Draw(vis)
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    
    # Draw board region outline
    board_x = int(region["x"] * W)
    board_y = int(region["y"] * H)
    board_w = int(region["w"] * W)
    board_h = int(region["h"] * H)
    
    draw.rectangle([board_x, board_y, board_x + board_w, board_y + board_h],
                   outline=(255, 0, 0), width=3)
    draw.text((board_x, board_y - 20), "BOARD REGION", fill=(255, 0, 0), font=font)
    
    # Crop board area and detect cards
    board_area = img.crop((board_x, board_y, board_x + board_w, board_y + board_h))
    card_positions = _locate_board_cards(board_area)
    
    # Draw detected card positions
    for i, (cx, cy, cw, ch) in enumerate(card_positions):
        abs_x = board_x + cx
        abs_y = board_y + cy
        draw.rectangle([abs_x, abs_y, abs_x + cw, abs_y + ch],
                       outline=(0, 255, 0), width=2)
        draw.text((abs_x, abs_y - 15), f"Card {i+1}", fill=(0, 255, 0), font=font)
    
    # Add legend
    legend_y = H - 80
    draw.text((10, legend_y), "Legend:", fill=(255, 255, 255), font=font)
    draw.rectangle([10, legend_y + 10, 50, legend_y + 30], outline=(255, 0, 0), width=2)
    draw.text((60, legend_y + 12), "Board Region", fill=(255, 255, 255), font=font)
    draw.rectangle([10, legend_y + 35, 50, legend_y + 55], outline=(0, 255, 0), width=2)
    draw.text((60, legend_y + 37), "Detected Cards", fill=(255, 255, 255), font=font)
    
    # Add detection summary
    summary_y = H - 40
    draw.text((10, summary_y), f"Cards detected: {len(card_positions)}",
              fill=(0, 255, 0), font=font)
    
    vis.save(save_path)
    return save_path


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args and args[0] == "calibrate":
        region = None
        if len(args) == 5:
            region = {"x": float(args[1]), "y": float(args[2]),
                      "w": float(args[3]), "h": float(args[4])}
        p = calibrate(region=region)
        print(f"Saved annotated screenshot to {p}" if p else "No GGPoker window found")
    elif args and args[0] == "calibrate-board":
        save_path = args[1] if len(args) > 1 else "board_calibration.png"
        p = calibrate_board(save_path)
        print(f"Saved board calibration to {p}" if p else "No GGPoker window found")
    elif args and args[0] == "calibrate-suits":
        save_path = args[1] if len(args) > 1 else "suit_calibration.png"
        p = calibrate_suits(save_path)
        print(f"Saved suit calibration to {p}" if p else "No GGPoker window found")
    elif args and args[0] == "scan":
        r = scan_region()
        if r:
            print("Suggested CARD_REGION = "
                  f'{{"x": {r["x"]:.3f}, "y": {r["y"]:.3f}, '
                  f'"w": {r["w"]:.3f}, "h": {r["h"]:.3f}}}')
        else:
            print("No card region found (is the table visible?)")
    elif args and args[0] == "debug":
        # Debug mode: show detailed suit detection info
        hand = capture_and_read(debug=True)
        print(f"Detected hand: {hand}" if hand else "No cards detected")
    elif args and args[0] == "debug-board":
        # Debug board detection
        found = find_ggpoker_window()
        if found:
            x, y, w, h = found
            img = capture_window((x, y, w, h))
            if img:
                board = detect_board_cards(img, debug=True)
                print(f"Detected board: {board}" if board else "No board cards detected")
        else:
            print("No GGPoker window found")
    elif args and args[0] == "debug-monitors":
        # Debug multi-monitor setup
        print("=== Multi-Monitor Debug Info ===\n")
        
        # Get display information
        displays = get_display_info()
        
        if not displays:
            print("No displays found!")
        else:
            print(f"Number of displays: {len(displays)}\n")
            
            for i, display in enumerate(displays):
                print(f"Display {i}:")
                print(f"  Bounds (logical): {display['bounds']}")
                print(f"  Pixel bounds: {display['pixel_bounds']}")
                print(f"  Scale factor: {display['scale']}")
                print(f"  Is main display: {display['is_main']}")
                print(f"  Display ID: {display['display_id']}")
                print()
        
        # Try to find poker window and determine which display it's on
        print("=== Poker Window Location ===\n")
        found = find_ggpoker_window()
        
        if found:
            x, y, w, h = found
            print(f"Poker window bounds: ({x}, {y}, {w}, {h})")
            
            window_display = window_on_display(found, displays)
            if window_display:
                print(f"Window is on display with bounds: {window_display['bounds']}")
                print(f"Display scale: {window_display['scale']}")
            else:
                print("Could not determine which display the window is on")
        else:
            print("No poker window found")
        
        # Update display scales
        print("\n=== Updating Display Scales ===\n")
        update_display_scales()
        displays = get_display_info()
        
        for i, display in enumerate(displays):
            print(f"Display {i} updated scale: {display['scale']}")
    else:
        hand = capture_and_read()
        print(hand if hand else "No cards detected")
