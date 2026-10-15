"""
Position Detection Module for Poker RTA.

Detects player position (BTN, SB, BB, UTG, MP, CO) and spot (open, facing open, facing 3bet)
by parsing the GGPoker window using OCR and visual analysis.
"""

import re
from typing import Dict, Optional, Tuple, List
from enum import Enum

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class Position(Enum):
    """Player positions at a 6-max table."""
    UTG = "UTG"      # Under the Gun
    MP = "MP"        # Middle Position
    CO = "CO"        # Cutoff
    BTN = "BTN"      # Button
    SB = "SB"        # Small Blind
    BB = "BB"        # Big Blind


class Spot(Enum):
    """Pre-flop spots."""
    OPEN = "open"                    # First to act (open the action)
    FACING_OPEN = "facing_open"      # Facing an open raise
    FACING_3BET = "facing_3bet"      # Facing a 3-bet
    FACING_4BET = "facing_4bet"      # Facing a 4-bet


class PositionDetector:
    """
    Detects position and spot from poker table screenshots.
    
    Uses OCR and visual analysis to determine:
    - Dealer button position
    - Hero's position relative to dealer button
    - Current spot from action history
    """
    
    # Position order for 6-max (starting from UTG preflop)
    POSITION_ORDER_6MAX = [Position.UTG, Position.MP, Position.CO, Position.BTN, Position.SB, Position.BB]
    
    # Action patterns to detect from table text
    ACTION_PATTERNS = {
        Spot.OPEN: [
            r'you.*check',
            r'you.*fold',
            r'you.*call.*blinds?',
            r'you.*raise.*to',
            r'first.*in',
        ],
        Spot.FACING_OPEN: [
            r'.*raised.*to',
            r'.*opens.*to',
            r'facing.*raise',
            r'called.*by',
        ],
        Spot.FACING_3BET: [
            r'.*3-bet',
            r'.*re-raised',
            r'.*3bet',
            r'facing.*3bet',
        ],
        Spot.FACING_4BET: [
            r'.*4-bet',
            r'.*re-re-raised',
            r'.*4bet',
            r'facing.*4bet',
        ],
    }
    
    def __init__(self):
        self.detected_positions = {}  # Cache for learned positions
        self.last_position: Optional[Position] = None
        self.last_spot: Optional[Spot] = None
        self.detection_status = "idle"  # idle, detecting, success, error
    
    # Clockwise seat order; hero is always displayed at bottom centre.
    SEATS = ((.50, .16), (.86, .29), (.89, .70),
             (.50, .87), (.14, .70), (.14, .29))
    HERO_SEAT = 3

    def detect_dealer_button(self, img):
        """Find a yellow circular marker near a seat, excluding chips/text."""
        rgb = img.convert('RGB')
        width, height = rgb.size
        y0, y1 = int(height * .15), int(height * .84)
        x0, x1 = int(width * .08), int(width * .92)
        if HAS_NUMPY:
            arr = np.asarray(rgb, dtype=np.float32)[y0:y1, x0:x1]
            r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
            cond = (r > 170) & (g > 125) & (b < 110) & (r > b * 1.6) & (g > b * 1.5)
            ys, xs = np.nonzero(cond)
            mask = {(x + x0, y + y0) for y, x in zip(ys.tolist(), xs.tolist())}
        else:
            mask = set()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    r, g, b = rgb.getpixel((x, y))
                    if r > 170 and g > 125 and b < 110 and r > b * 1.6 and g > b * 1.5:
                        mask.add((x, y))
        candidates = []
        while mask:
            start = mask.pop()
            stack, points = [start], [start]
            while stack:
                x, y = stack.pop()
                for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
                    neighbor = x + dx, y + dy
                    if neighbor in mask:
                        mask.remove(neighbor)
                        stack.append(neighbor)
                        points.append(neighbor)
            xs, ys = zip(*points)
            w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            if not (height * .020 <= h <= height * .042 and .8 <= w / h <= 1.25):
                continue
            if not .5 <= len(points) / (w * h) <= .88:
                continue
            center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
            radius = max(2, round(h * .30))
            inner = rgb.crop((round(center[0]) - radius, round(center[1]) - radius,
                              round(center[0]) + radius, round(center[1]) + radius))
            dark_ink = sum(max(p) < 130 for p in inner.getdata()) / (inner.width * inner.height)
            if not .12 < dark_ink < .65:
                continue  # Yellow chips have no dark D in their centre.
            # Marker belongs inside the rail, next to a seat. Central yellow
            # pot text and distant controls cannot identify a dealer.
            cx, cy = center[0] / width, center[1] / height
            distance = min(((cx - sx)**2 + (cy - sy)**2)**.5 for sx, sy in self.SEATS)
            if distance < .21:
                candidates.append(center)
        return tuple(map(round, candidates[0])) if len(candidates) == 1 else None

    def detect_occupied_seats(self, img):
        """Require both a dark nameplate and bright/dimmed text in each seat band.

        A seat with inconclusive evidence is unknown, not assumed occupied.
        Folded players have dimmed stack text (mn > 90) but still occupy their
        seat for position mapping; active_seats tracks unfolded players with
        bright stack text (mn > 115).
        """
        rgb = img.convert('RGB')
        width, height = rgb.size
        occupied, active, unknown = [], [], []
        arr = np.asarray(rgb, dtype=np.int16) if HAS_NUMPY else None
        for index, (cx, cy) in enumerate(self.SEATS):
            # Nameplate is immediately below the avatar/cards.
            bx0, by0 = int((cx - .055) * width), int(cy * height)
            bx1, by1 = int((cx + .055) * width), int((cy + .065) * height)
            if arr is not None:
                band_arr = arr[by0:by1, bx0:bx1]
                mx = band_arr.max(axis=-1)
                mn = band_arr.min(axis=-1)
                dark = float((mx < 85).mean())
                text = float(((mn > 90) & (mx - mn < 45)).mean())
                bright_text = float(((mn > 115) & (mx - mn < 45)).mean())
            else:
                band = rgb.crop((bx0, by0, bx1, by1))
                pixels = list(band.getdata())
                dark = sum(max(p) < 85 for p in pixels) / len(pixels)
                text = sum(min(p) > 90 and max(p) - min(p) < 45 for p in pixels) / len(pixels)
                bright_text = sum(min(p) > 115 and max(p) - min(p) < 45 for p in pixels) / len(pixels)
            if dark > .40 and text > .025:
                occupied.append(index)
                active_threshold = .04 if index == self.HERO_SEAT else .085
                if bright_text >= active_threshold:
                    active.append(index)
            elif text > .015 or dark < .15:
                unknown.append(index)
        self.occupied_seats = occupied
        self.active_seats = active
        self.unknown_seats = unknown
        return occupied

    def detect_hero_position(self, img, dealer_button=None):
        if dealer_button is None:
            dealer_button = self.detect_dealer_button(img)
        occupied = self.detect_occupied_seats(img)
        if dealer_button is None:
            return None
        cx, cy = dealer_button[0] / img.width, dealer_button[1] / img.height
        dealer = min(range(6), key=lambda i: (cx - self.SEATS[i][0])**2 + (cy - self.SEATS[i][1])**2)
        if self.HERO_SEAT not in occupied or dealer not in occupied:
            return None
        if dealer == self.HERO_SEAT:
            return Position.BTN
        if self.unknown_seats or len(occupied) < 2:
            return None
        order = sorted(occupied, key=lambda i: (i - dealer) % 6)
        offset = order.index(self.HERO_SEAT)
        if len(order) == 2:
            return Position.BB
        names = {3: [Position.BTN, Position.SB, Position.BB],
                 4: [Position.BTN, Position.SB, Position.BB, Position.CO],
                 5: [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.CO],
                 6: [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.MP, Position.CO]}
        return names[len(order)][offset]

    def _angle_to_position(self, angle: float) -> Position:
        """
        Convert angle from dealer button to position name.
        
        For a 6-max table, positions are spaced ~60 degrees apart.
        """
        # Adjust angle so that 0 degrees points to BTN
        # Hero at bottom of screen, dealer button somewhere on table
        # The angle determines how many positions away from BTN hero is
        
        # Normalize to 0-360
        angle = angle % 360
        
        # 6-max positions are ~60 degrees apart
        # Map angle ranges to positions
        # This is approximate and may need calibration per table layout
        
        # Simplified mapping based on typical table layouts
        if 0 <= angle < 30 or 330 <= angle < 360:
            return Position.BTN
        elif 30 <= angle < 90:
            return Position.SB
        elif 90 <= angle < 150:
            return Position.BB
        elif 150 <= angle < 210:
            return Position.UTG
        elif 210 <= angle < 270:
            return Position.MP
        else:
            return Position.CO
    
    def detect_spot_from_text(self, text):
        """Only explicit context establishes a betting round; unknown stays unknown."""
        for spot, pattern in (
            (Spot.FACING_4BET, r'\b(?:4[- ]?bet|re-re-raised)\b'),
            (Spot.FACING_3BET, r'\b(?:3[- ]?bet|re-raised)\b'),
            (Spot.FACING_OPEN, r'\b(?:facing (?:an? )?(?:open|raise)|raised to|opens to)\b'),
            (Spot.OPEN, r'\b(?:first in|unopened|folded to you)\b'),
        ):
            if re.search(pattern, text, re.I):
                return spot
        return None

    def detect_spot_from_image(self, img):
        # A Call/Raise button alone cannot distinguish an open, 3-bet or
        # 4-bet. No action history reader is implemented, so do not guess.
        return None

    def get_position_info(self) -> Dict:
        """
        Get the last detected position and spot information.
        
        Returns:
            Dictionary with position, spot, and status information
        """
        return {
            'position': self.last_position.value if self.last_position else None,
            'spot': self.last_spot.value if self.last_spot else None,
            'status': self.detection_status,
            'cached_positions': self.detected_positions
        }
    
    def save_position_cache(self, position: Position, card_coords: Tuple[int, int, int, int]):
        """
        Save detected card position for future use.
        
        Args:
            position: Detected position
            card_coords: (x, y, w, h) of card region
        """
        self.detected_positions[position.value] = card_coords
    
    def load_position_cache(self) -> Dict:
        """Load cached position data."""
        return self.detected_positions.copy()


def detect_position_and_spot(img: Image.Image, action_text: str = "") -> Dict:
    """
    Convenience function to detect position and spot from an image.
    
    Args:
        img: Full table screenshot
        action_text: Optional action history text
        
    Returns:
        Dictionary with position, spot, and detection details
    """
    detector = PositionDetector()
    
    # Detect dealer button
    dealer_button = detector.detect_dealer_button(img)
    
    # Detect hero position
    position = detector.detect_hero_position(img, dealer_button)
    
    # Detect spot
    if action_text:
        spot = detector.detect_spot_from_text(action_text)
    else:
        spot = detector.detect_spot_from_image(img)
    
    occupied = getattr(detector, 'occupied_seats', [])
    active_seats = getattr(detector, 'active_seats', [])
    active_opponents = max(1, len([s for s in active_seats if s != detector.HERO_SEAT])) if active_seats else 1
    seat_positions = {}
    if dealer_button and not getattr(detector, 'unknown_seats', []) and len(occupied) >= 2:
        cx, cy = dealer_button[0] / img.width, dealer_button[1] / img.height
        dealer = min(range(6), key=lambda i: (cx - detector.SEATS[i][0])**2 + (cy - detector.SEATS[i][1])**2)
        if dealer in occupied:
            order = sorted(occupied, key=lambda i: (i - dealer) % 6)
            labels = {2: ['BTN', 'BB'], 3: ['BTN', 'SB', 'BB'],
                      4: ['BTN', 'SB', 'BB', 'CO'], 5: ['BTN', 'SB', 'BB', 'UTG', 'CO'],
                      6: ['BTN', 'SB', 'BB', 'UTG', 'MP', 'CO']}
            seat_positions = dict(zip(order, labels[len(order)]))
    return {
        'position': position.value if position else None,
        'spot': spot.value if spot else None,
        'dealer_button': dealer_button,
        'occupied_seats': occupied,
        'active_seats': active_seats,
        'active_opponents': active_opponents,
        'seat_positions': seat_positions,
        'status': 'success' if position and spot else 'partial'
    }


if __name__ == "__main__":
    # Test the position detector
    print("Position Detection Module")
    print("=" * 50)
    
    detector = PositionDetector()
    
    # Test angle to position mapping
    test_angles = [0, 45, 90, 135, 180, 225, 270, 315]
    for angle in test_angles:
        pos = detector._angle_to_position(angle)
        print(f"Angle {angle:3d}° -> {pos.value}")
    
    # Test spot detection from text
    test_texts = [
        "You raise to 30",
        "Player 2 raised to 45",
        "Player 3 3-bet to 120",
        "You are first in"
    ]
    
    print("\nSpot Detection Tests:")
    for text in test_texts:
        spot = detector.detect_spot_from_text(text)
        print(f"  '{text}' -> {spot.value if spot else 'None'}")
