"""
Strategy management module for the Poker RTA tool.

Provides:
- Custom GTO range import from JSON files
- Aggression factor adjustment (0.5x to 2.0x)
- Stack depth support (20bb, 50bb, 100bb, 150bb)
- Strategy profile selection (TAG, LAG, ABC, Aggressive)
"""

import json
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class StrategyProfile(Enum):
    """Strategy profile types."""
    TAG = "TAG"      # Tight-Aggressive
    LAG = "LAG"      # Loose-Aggressive
    ABC = "ABC"      # Basic/Standard
    AGGRESSIVE = "Aggressive"


@dataclass
class StrategyConfig:
    """Configuration for strategy settings."""
    profile: StrategyProfile = StrategyProfile.ABC
    aggression_factor: float = 1.0  # 0.5x to 2.0x
    stack_depth: int = 100  # in big blinds
    custom_ranges: Dict[str, Any] = field(default_factory=dict)
    range_file_path: Optional[str] = None


# Default GTO ranges for different stack depths and positions
# These are simplified GTO-inspired ranges for demonstration
DEFAULT_RANGES = {
    "20bb": {
        "open": {
            "UTG": ["77+", "ATs+", "KJs+", "QJs", "ATo+", "KQo"],
            "MP": ["55+", "A8s+", "KTs+", "QTs+", "JTs", "T9s", "ATo+", "KQo"],
            "CO": ["33+", "A2s+", "K8s+", "Q9s+", "J9s+", "T9s", "98s", "87s", "A9o+", "KTo+", "QJo"],
            "BTN": ["22+", "A2s+", "K5s+", "Q7s+", "J8s+", "T8s+", "98s", "87s", "76s", "65s", "54s", "A7o+", "K9o+", "QTo+", "JTo", "T9o"],
            "SB": ["22+", "A2s+", "K5s+", "Q7s+", "J8s+", "T8s+", "98s", "87s", "76s", "65s", "A8o+", "KTo+", "QTo+", "JTo"],
            "BB": ["22+", "A2s+", "K5s+", "Q6s+", "J8s+", "T9s", "98s", "87s", "76s", "65s", "54s", "A9o+", "K9o+", "Q9o+", "J9o+", "T9o"]
        },
        "facing_open": {
            "MP_vs_UTG": ["99+", "AJs+", "KQs", "AQo+"],
            "CO_vs_UTG": ["88+", "ATs+", "KJs+", "QJs", "AQo+"],
            "CO_vs_MP": ["77+", "ATs+", "KTs+", "QJs", "JTs", "AJo+", "KQo"],
            "BTN_vs_UTG": ["77+", "ATs+", "KJs+", "QJs", "JTs", "AQo+"],
            "BTN_vs_MP": ["66+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "AJo+", "KQo"],
            "BTN_vs_CO": ["55+", "A5s+", "K9s+", "Q9s+", "J9s+", "T9s", "98s", "ATo+", "KJo+", "QJo"],
            "SB_vs_UTG": ["99+", "AJs+", "KQs", "AQo+"],
            "SB_vs_MP": ["88+", "ATs+", "KJs+", "QJs", "AJo+", "KQo"],
            "SB_vs_CO": ["77+", "A8s+", "KTs+", "QTs+", "JTs", "ATo+", "KJo+"],
            "SB_vs_BTN": ["55+", "A4s+", "K9s+", "Q9s+", "J9s+", "T9s", "A9o+", "KTo+", "QJo"],
            "BB_vs_UTG": ["88+", "ATs+", "KJs+", "QJs", "JTs", "AQo+", "KQo"],
            "BB_vs_MP": ["77+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "AJo+", "KQo"],
            "BB_vs_CO": ["55+", "A4s+", "K8s+", "Q9s+", "J9s+", "T9s", "98s", "ATo+", "KJo+", "QJo"],
            "BB_vs_BTN": ["22+", "A2s+", "K6s+", "Q8s+", "J8s+", "T8s+", "98s", "87s", "76s", "A8o+", "K9o+", "QTo+", "JTo"],
            "BB_vs_SB": ["22+", "A2s+", "K5s+", "Q7s+", "J8s+", "T8s+", "98s", "87s", "76s", "65s", "A7o+", "K9o+", "Q9o+", "JTo"]
        },
        "facing_3bet": {
            "UTG": ["QQ+", "AKs", "AKo"],
            "MP": ["JJ+", "AKs", "AQs", "AKo"],
            "CO": ["TT+", "AQs+", "AKo"],
            "BTN": ["99+", "AJs+", "KQs", "AQo+"],
            "SB": ["TT+", "AQs+", "AKo"],
            "BB": ["JJ+", "AKs", "AQs"]
        },
        "facing_4bet": {
            "5b": ["KK+", "AKs"],
            "call": ["QQ", "JJ", "AKo"]
        },
        "squeeze": {
            "CO": {"squeeze": ["JJ+ AKs AQs AKo"], "call": []},
            "BTN": {"squeeze": ["TT+ AQs+ AKo AQo"], "call": ["77-99 AJs KQs"]},
            "SB": {"squeeze": ["TT+ AQs+ AKo AQo"], "call": []},
            "BB": {"squeeze": ["TT+ AJs+ AKo AQo"], "call": ["66-99 ATs KQs QJs JTs"]}
        }
    },
    "50bb": {
        "open": {
            "UTG": ["77+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "AJo+", "KQo"],
            "MP": ["66+", "A4s+", "K9s+", "QTs+", "JTs", "T9s", "98s", "ATo+", "KJo+"],
            "CO": ["44+", "A2s+", "K7s+", "Q8s+", "J8s+", "T8s+", "98s", "87s", "76s", "A9o+", "KTo+", "QTo+", "JTo"],
            "BTN": ["22+", "A2s+", "K4s+", "Q6s+", "J7s+", "T7s+", "97s+", "87s", "76s", "65s", "54s", "A7o+", "K9o+", "Q9o+", "J9o+", "T9o"],
            "SB": ["22+", "A2s+", "K5s+", "Q7s+", "J8s+", "T8s+", "98s", "87s", "76s", "65s", "A8o+", "K9o+", "QTo+", "JTo"],
            "BB": ["22+", "A2s+", "K5s+", "Q6s+", "J8s+", "T9s", "98s", "87s", "76s", "65s", "A8o+", "K9o+", "Q9o+", "J9o+"]
        },
        "facing_open": {
            "MP_vs_UTG": ["88+", "ATs+", "KJs+", "QJs", "AQo+"],
            "CO_vs_UTG": ["77+", "ATs+", "KTs+", "QJs", "JTs", "AQo+"],
            "CO_vs_MP": ["66+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "AJo+", "KQo"],
            "BTN_vs_UTG": ["66+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "AQo+"],
            "BTN_vs_MP": ["55+", "A8s+", "K9s+", "Q9s+", "J9s+", "T9s", "98s", "AJo+", "KQo"],
            "BTN_vs_CO": ["44+", "A2s+", "K8s+", "Q9s+", "J9s+", "T9s", "98s", "87s", "ATo+", "KJo+", "QJo"],
            "SB_vs_UTG": ["99+", "AJs+", "KQs", "AQo+"],
            "SB_vs_MP": ["88+", "ATs+", "KJs+", "QJs", "AJo+", "KQo"],
            "SB_vs_CO": ["77+", "A5s+", "KTs+", "QTs+", "JTs", "T9s", "ATo+", "KJo+"],
            "SB_vs_BTN": ["55+", "A2s+", "K8s+", "Q9s+", "J9s+", "T9s", "98s", "A9o+", "KTo+", "QJo"],
            "BB_vs_UTG": ["77+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "98s", "AJo+", "KQo"],
            "BB_vs_MP": ["66+", "A7s+", "K9s+", "Q9s+", "J9s+", "T9s", "98s", "87s", "ATo+", "KJo+", "QJo"],
            "BB_vs_CO": ["44+", "A2s+", "K7s+", "Q8s+", "J8s+", "T8s+", "98s", "87s", "76s", "A9o+", "KTo+", "QTo+", "JTo"],
            "BB_vs_BTN": ["22+", "A2s+", "K4s+", "Q6s+", "J7s+", "T7s+", "97s+", "87s", "76s", "65s", "54s", "A7o+", "K9o+", "Q9o+", "J9o+", "T9o"],
            "BB_vs_SB": ["22+", "A2s+", "K4s+", "Q6s+", "J7s+", "T7s+", "97s+", "87s", "76s", "65s", "54s", "A6o+", "K8o+", "Q9o+", "J9o+", "T9o"]
        },
        "facing_3bet": {
            "UTG": ["JJ+", "AQs+", "AKo"],
            "MP": ["TT+", "AJs+", "KQs", "AQo+"],
            "CO": ["99+", "ATs+", "KQs", "AQo+"],
            "BTN": ["88+", "A9s+", "KJs+", "QJs", "JTs", "T9s", "AQo+"],
            "SB": ["TT+", "AQs+", "AKo"],
            "BB": ["JJ+", "AQs+", "AKo"]
        },
        "facing_4bet": {
            "5b": ["KK+", "AKs"],
            "call": ["QQ", "JJ", "AQs", "AKo"]
        },
        "squeeze": {
            "CO": {"squeeze": ["QQ+ AKs A5s AKo"], "call": ["77-JJ AQs AJs KQs QJs JTs"]},
            "BTN": {"squeeze": ["TT+ AJs+ A5s A4s AKo AQo"], "call": ["55-99 ATs KQs KJs QJs JTs T9s"]},
            "SB": {"squeeze": ["JJ+ AQs+ A5s AKo AQo"], "call": ["77-TT AJs KQs QJs JTs"]},
            "BB": {"squeeze": ["TT+ AJs+ A5s A4s KQs AKo AQo"], "call": ["44-99 ATs A9s KJs QJs JTs T9s 98s 87s"]}
        }
    },
    "100bb": {
        "open": {
            "UTG": ["22+ A2s+ K9s+ Q9s+ J9s+ T9s 98s 87s 76s 65s 54s ATo+ KTo+ QJo"],
            "MP": ["22+ A2s+ K8s+ Q8s+ J8s+ T8s+ 98s 87s 76s 65s 54s A9o+ KTo+ QTo+ JTo"],
            "CO": ["22+ A2s+ K5s+ Q6s+ J6s+ T6s+ 96s+ 86s+ 75s+ 64s+ 53s+ 43s A2o+ K8o+ Q9o+ J9o+ T9o 98o"],
            "BTN": ["22+ A2s+ K2s+ Q3s+ J4s+ T5s+ 95s+ 84s+ 74s+ 63s+ 53s 42s 32s A2o+ K5o+ Q7o+ J8o+ T8o+ 98o 87o 76o 65o"],
            "SB": ["22+ A2s+ K2s+ Q4s+ J5s+ T5s+ 95s+ 84s+ 74s+ 64s+ 53s 43s A2o+ K7o+ Q8o+ J8o+ T8o+ 97o+ 87o 76o 65o 54o"],
            "BB": ["22+ A2s+ K5s+ Q6s+ J8s+ T9s 98s 87s 76s A7o+ K9o+ Q9o+ J9o+"]
        },
        "facing_open": {
            "MP_vs_UTG": {"3b": ["QQ+ AKs A5s A4s AKo"], "call": ["22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s AQo"]},
            "CO_vs_UTG": {"3b": ["QQ+ AKs A5s A4s AKo"], "call": ["22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s AQo AJo"]},
            "CO_vs_MP": {"3b": ["TT+ AQs+ A5s A4s AKo AQo"], "call": ["22-99 AJs ATs A9s KQs KJs QJs JTs T9s 98s 87s 76s AJo ATo KQo"]},
            "BTN_vs_UTG": {"3b": ["TT+ AQs+ A5s A4s AKo AQo"], "call": ["22-99 AJs ATs A9s A8s KQs KJs QJs JTs T9s 98s 87s 76s AJo ATo KQo"]},
            "BTN_vs_MP": {"3b": ["99+ AJs+ ATs A5s A4s A3s AKo AQo"], "call": ["22-88 AJo ATo A9s A8s A7s KQs KJs QJs JTs T9s 98s 87s 76s KQo QJo"]},
            "BTN_vs_CO": {"3b": ["88+ ATs+ A9s A5s A4s A3s KQs AKo AQo AJo"], "call": ["22-77 A9s A8s A7s A6s A5s KJs KTs QJs QTs JTs T9s 98s 87s 76s ATo A9o KQo KJo QJo"]},
            "SB_vs_UTG": {"3b": ["QQ+ AKs A5s A4s AKo"], "call": ["22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s AQo"]},
            "SB_vs_MP": {"3b": ["TT+ AQs+ A5s A4s AKo AQo"], "call": ["22-99 AJs ATs A9s KQs KJs QJs JTs T9s 98s 87s AQo AJo"]},
            "SB_vs_CO": {"3b": ["99+ AJs+ ATs A5s A4s A3s AKo AQo AJo"], "call": ["22-88 AJs ATs A9s A8s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s AQo ATo KQo"]},
            "SB_vs_BTN": {"3b": ["99+ AJs+ ATs A9s A5s A4s A3s KQs KJs AKo AQo AJo ATo"], "call": ["22-88 AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s KQs KJs KTs K9s K8s K7s QJs QTs Q9s Q8s JTs J9s J8s T9s T8s 98s 97s 87s 86s 76s 75s 65s 64s 54s AQo AJo ATo A9o A8o A7o A5o KQo KJo KTo QJo QTo JTo J9o T9o 98o 87o 76o 65o 54o"]},
            "BB_vs_UTG": {"3b": ["QQ+ AKs A5s A4s AKo"], "call": ["22-JJ AJs ATs A9s A8s A7s A5s A4s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s AQo AJo ATo"]},
            "BB_vs_MP": {"3b": ["TT+ AQs+ A5s A4s AKo AQo"], "call": ["22-99 AJs ATs A9s A8s A7s A6s A5s A4s A3s KQs KJs KTs K9s QJs QTs JTs T9s 98s 87s 76s 65s 54s AQo AJo ATo KQo"]},
            "BB_vs_CO": {"3b": ["99+ AJs+ ATs A9s A5s A4s A3s KQs AKo AQo AJo"], "call": ["22-88 AJs ATs A9s A8s A7s A6s A5s A4s A3s A2s KQs KJs KTs K9s K8s QJs QTs Q9s JTs J9s T9s 98s 87s 76s 65s 54s AQo ATo A9o AJo KQo KJo QJo JTo"]},
            "BB_vs_BTN": {"3b": ["88+ ATs+ A9s A8s A5s A4s A3s KQs KJs AKo AQo AJo ATo"], "call": ["22-77 A9s A8s A7s A6s A5s A4s A3s A2s KQs KJs KTs K9s K8s K7s K6s K5s QJs QTs Q9s Q8s JTs J9s J8s T9s T8s 98s 97s 87s 86s 76s 75s 65s 64s 54s AQo A9o A8o A7o A5o KQo KJo KTo QJo QTo JTo J9o T9o 98o 87o 76o 65o"]},
            "BB_vs_SB": {"3b": ["77+ A9s+ A5s A4s KQs KJs KTs AKo AQo AJo ATo A9o"], "call": ["22-66 A9s A8s A7s A6s A5s A4s A3s A2s KQs KJs KTs K9s K8s K7s K6s K5s K4s QJs QTs Q9s Q8s Q7s Q6s Q5s JTs J9s J8s J7s T9s T8s T7s 98s 97s 96s 87s 86s 76s 75s 65s 64s 54s 53s AQo A9o A8o A7o A6o A5o A4o A3o KQo KJo KTo K9o QJo QTo Q9o JTo J9o T9o T8o 98o 97o 87o 86o 76o 75o 65o 54o"]}
        },
        "facing_3bet": {
            "UTG": {"4b": ["QQ+ AKs AKo"], "call": ["22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s AQo"]},
            "MP": {"4b": ["QQ+ AKs A5s A4s AKo"], "call": ["22-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s AQo"]},
            "CO": {"4b": ["JJ+ AQs+ A5s A4s AKo AQo"], "call": ["22-TT AJs ATs A9s KQs KJs QJs JTs T9s 98s 87s 76s AQo AJo"]},
            "BTN": {"4b": ["TT+ AJs+ ATs A5s A4s A3s AKo AQo AJo"], "call": ["22-99 ATs A9s A8s A7s A6s A5s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s AQo AJo ATo KQo"]},
            "SB": {"4b": ["TT+ AJs+ A5s A4s AKo AQo"], "call": ["22-99 ATs A9s A8s A7s A6s A5s KQs KJs KTs QJs QTs JTs T9s 98s 87s 76s AQo AJo ATo KQo"]},
            "BB": ["99+", "AJs+", "KQs", "AQo+"]
        },
        "facing_4bet": {
            "5b": ["QQ+ AKs AKo"],
            "call": ["22-JJ AQs AJs ATs KQs"],
            "UTG": {"5b": ["KK+ AKs"], "call": ["QQ JJ AQs AKo"]},
            "MP": {"5b": ["QQ+ AKs AKo"], "call": ["TT-JJ AQs AJs KQs"]},
            "CO": {"5b": ["QQ+ AKs A5s AKo"], "call": ["88-JJ AQs AJs ATs KQs"]},
            "BTN": {"5b": ["QQ+ AKs A5s A4s AKo"], "call": ["22-JJ AQs AJs ATs KQs"]},
            "SB": {"5b": ["QQ+ AKs A5s AKo"], "call": ["77-JJ AQs AJs ATs KQs"]},
            "BB": {"5b": ["QQ+ AKs AKo"], "call": ["22-JJ AQs AJs ATs KQs"]}
        },
        "squeeze": {
            "CO": {"squeeze": ["QQ+ AKs A5s AKo"], "call": ["66-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s"]},
            "BTN": {"squeeze": ["TT+ AJs+ A5s A4s KQs AKo AQo"], "call": ["22-99 ATs A9s KJs QJs JTs T9s 98s 87s 76s 65s"]},
            "SB": {"squeeze": ["TT+ AJs+ A5s A4s KQs AKo AQo"], "call": ["66-99 ATs A9s KJs QJs JTs T9s"]},
            "BB": {"squeeze": ["TT+ AJs+ ATs A5s A4s A3s KQs AKo AQo"], "call": ["22-99 ATs A9s A8s A7s KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s AJo ATo KQo"]}
        }
    },
    "150bb": {
        "open": {
            "UTG": ["55+", "A2s+", "K9s+", "QTs+", "JTs", "T9s", "98s", "87s", "76s", "65s", "54s", "AJo+", "KQo"],
            "MP": ["44+", "A2s+", "K8s+", "Q9s+", "J9s+", "T9s", "98s", "87s", "76s", "65s", "54s", "ATo+", "KJo+", "QJo"],
            "CO": ["22+", "A2s+", "K4s+", "Q6s+", "J7s+", "T7s+", "97s+", "86s+", "75s+", "64s+", "53s+", "A9o+", "KTo+", "QTo+", "JTo"],
            "BTN": ["22+", "A2s+", "K2s+", "Q2s+", "J5s+", "T6s+", "95s+", "85s+", "74s+", "64s+", "53s+", "43s", "A2o+", "K8o+", "Q9o+", "J9o+", "T9o", "98o"],
            "SB": ["22+", "A2s+", "K2s+", "Q4s+", "J6s+", "T6s+", "96s+", "85s+", "75s+", "64s+", "53s+", "A4o+", "K9o+", "Q9o+", "J9o+", "T9o"],
            "BB": ["22+", "A2s+", "K5s+", "Q6s+", "J8s+", "T9s", "98s", "87s", "76s", "65s", "54s", "A7o+", "K9o+", "Q9o+"]
        },
        "facing_open": {
            "MP_vs_UTG": ["66+", "ATs+", "KJs+", "QJs", "JTs", "T9s", "AQo+"],
            "CO_vs_UTG": ["55+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "98s", "AQo+"],
            "CO_vs_MP": ["44+", "A4s+", "K9s+", "Q9s+", "J9s+", "T9s", "98s", "87s", "AJo+", "KQo"],
            "BTN_vs_UTG": ["22+", "A4s+", "K9s+", "Q9s+", "J9s+", "T9s", "98s", "87s", "76s", "65s", "54s", "AQo+"],
            "BTN_vs_MP": ["22+", "A2s+", "K8s+", "Q9s+", "J9s+", "T8s+", "98s", "87s", "76s", "65s", "54s", "AJo+", "KQo"],
            "BTN_vs_CO": ["22+", "A2s+", "K6s+", "Q8s+", "J8s+", "T8s+", "97s+", "86s+", "75s+", "64s+", "54s", "ATo+", "KJo+", "QJo"],
            "SB_vs_UTG": ["88+", "ATs+", "KJs+", "QJs", "JTs", "AQo+"],
            "SB_vs_MP": ["77+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "AQo+"],
            "SB_vs_CO": ["66+", "A2s+", "K9s+", "Q9s+", "J9s+", "T9s", "98s", "87s", "AJo+", "KQo"],
            "SB_vs_BTN": ["44+", "A2s+", "K7s+", "Q8s+", "J8s+", "T8s+", "97s+", "87s", "76s", "65s", "ATo+", "KJo+", "QJo"],
            "BB_vs_UTG": ["22+", "A2s+", "K8s+", "Q9s+", "J9s+", "T8s+", "98s", "87s", "76s", "65s", "54s", "AJo+", "KQo"],
            "BB_vs_MP": ["22+", "A2s+", "K6s+", "Q8s+", "J8s+", "T8s+", "97s+", "86s+", "75s+", "65s", "54s", "ATo+", "KJo+", "QJo"],
            "BB_vs_CO": ["22+", "A2s+", "K4s+", "Q6s+", "J7s+", "T7s+", "96s+", "86s+", "75s+", "64s+", "53s+", "43s", "A9o+", "KTo+", "QTo+", "JTo"],
            "BB_vs_BTN": ["22+", "A2s+", "K2s+", "Q2s+", "J3s+", "T5s+", "95s+", "85s+", "74s+", "63s+", "53s+", "43s", "A2o+", "K6o+", "Q8o+", "J8o+", "T8o+", "98o", "87o"],
            "BB_vs_SB": ["22+", "A2s+", "K2s+", "Q2s+", "J3s+", "T5s+", "95s+", "85s+", "74s+", "63s+", "53s+", "43s", "A2o+", "K5o+", "Q7o+", "J8o+", "T8o+", "98o", "87o"]
        },
        "facing_3bet": {
            "UTG": ["88+", "ATs+", "KJs+", "QJs", "JTs", "T9s", "AQo+"],
            "MP": ["77+", "A9s+", "KTs+", "QTs+", "JTs", "T9s", "98s", "AQo+"],
            "CO": ["66+", "A4s+", "K9s+", "Q9s+", "J9s+", "T9s", "98s", "87s", "AQo+"],
            "BTN": ["44+", "A2s+", "K8s+", "Q9s+", "J9s+", "T8s+", "98s", "87s", "76s", "65s", "54s", "AQo+"],
            "SB": ["77+", "ATs+", "KJs+", "QJs", "JTs", "T9s", "AQo+"],
            "BB": ["88+", "ATs+", "KJs+", "QJs", "JTs", "AQo+"]
        },
        "facing_4bet": {
            "5b": ["KK+", "AKs", "A5s", "A4s"],
            "call": ["QQ", "JJ", "TT", "99", "AQs", "AJs", "ATs", "KQs", "QJs", "JTs", "AKo"]
        },
        "squeeze": {
            "CO": {"squeeze": ["QQ+ AKs A5s A4s AKo"], "call": ["44-JJ AQs AJs ATs KQs KJs QJs JTs T9s 98s 87s 76s"]},
            "BTN": {"squeeze": ["TT+ AJs+ A5s A4s A3s KQs AKo AQo"], "call": ["22-99 ATs A9s A8s KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s"]},
            "SB": {"squeeze": ["TT+ AJs+ A5s A4s KQs AKo AQo"], "call": ["55-99 ATs A9s KJs QJs JTs T9s 98s 87s"]},
            "BB": {"squeeze": ["TT+ AJs+ ATs A5s A4s A3s KQs AKo AQo"], "call": ["22-99 ATs A9s A8s A7s A6s KJs KTs QJs QTs JTs T9s 98s 87s 76s 65s 54s AJo ATo KQo"]}
        }
    }
}

# Strategy profile modifiers - adjust ranges based on play style
PROFILE_MODIFIERS = {
    StrategyProfile.TAG: {
        "tighten_factor": 0.7,  # Play 70% of ABC range
        "description": "Tight-Aggressive: Selective hand selection, aggressive when playing"
    },
    StrategyProfile.LAG: {
        "tighten_factor": 1.3,  # Play 130% of ABC range
        "description": "Loose-Aggressive: Wide ranges, very aggressive postflop"
    },
    StrategyProfile.ABC: {
        "tighten_factor": 1.0,  # Standard range
        "description": "ABC Poker: Solid, fundamental-based play"
    },
    StrategyProfile.AGGRESSIVE: {
        "tighten_factor": 1.1,
        "description": "Aggressive: Slightly wider than ABC with more bluffs"
    }
}


class StrategyManager:
    """Manages poker strategy configuration and GTO ranges."""
    
    def __init__(self):
        self.config = StrategyConfig()
        self._ranges: Dict[str, Any] = {}
        self._load_default_ranges()
    
    def _expand_hand_list(self, hand_list: List[str]) -> List[str]:
        """Expand shorthand range notations ('22+', 'ATs+', etc.) into canonical hand names."""
        try:
            import ranges as _ranges_mod
        except ImportError:
            _ranges_mod = None

        expanded: List[str] = []
        seen = set()
        for token in hand_list:
            if _ranges_mod is not None:
                cleaned = _ranges_mod._clean(token)
                if cleaned:
                    for h in sorted(cleaned):
                        if h not in seen:
                            seen.add(h)
                            expanded.append(h)
                    continue
                if _ranges_mod.normalize_hand(token) is None:
                    continue
            if token not in seen:
                seen.add(token)
                expanded.append(token)
        return expanded

    def _load_default_ranges(self):
        """Load default GTO ranges and expand shorthand notations to canonical hands."""
        raw = json.loads(json.dumps(DEFAULT_RANGES))
        for stack_key, spots in raw.items():
            for spot_type, positions in spots.items():
                if isinstance(positions, dict):
                    for pos_key, hands in positions.items():
                        if isinstance(hands, list):
                            raw[stack_key][spot_type][pos_key] = self._expand_hand_list(hands)
                        elif isinstance(hands, dict):
                            raw[stack_key][spot_type][pos_key] = {
                                k: self._expand_hand_list(v) if isinstance(v, list) else v
                                for k, v in hands.items()
                            }
        self._ranges = raw
    
    def get_config(self) -> StrategyConfig:
        """Get current strategy configuration."""
        return self.config
    
    def set_profile(self, profile: StrategyProfile):
        """Set the strategy profile."""
        self.config.profile = profile
    
    def set_aggression_factor(self, factor: float):
        """Set aggression factor (0.5x to 2.0x)."""
        self.config.aggression_factor = max(0.5, min(2.0, factor))
    
    def set_stack_depth(self, depth: int):
        """Set stack depth in big blinds."""
        valid_depths = [20, 50, 100, 150]
        # Find closest valid depth
        self.config.stack_depth = min(valid_depths, key=lambda x: abs(x - depth))
    
    def get_ranges_for_spot(self, spot: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Get action ranges for a specific spot, adjusted by strategy settings.
        
        Args:
            spot: Dictionary with 'kind', 'pos', 'vs' keys
            
        Returns:
            Dictionary mapping actions to hand lists
        """
        stack_key = f"{self.config.stack_depth}bb"
        if stack_key not in self._ranges:
            stack_key = str(self.config.stack_depth)
        if stack_key not in self._ranges:
            stack_key = "100bb"  # Fallback
        
        spot_kind = spot.get('kind', 'open')
        position = spot.get('pos', 'BTN')
        vs_position = spot.get('vs')
        
        # Get base ranges
        if spot_kind == 'open':
            base_ranges = self._ranges[stack_key].get('open', {}).get(position, [])
            return self._convert_to_action_ranges(self._expand_hand_list(base_ranges))
        
        elif spot_kind == 'facing_open':
            vs_key = f"{position}_vs_{vs_position}" if (position and vs_position) else (f"BB_vs_{vs_position}" if vs_position else "BB_vs_BTN")
            facing_dict = self._ranges[stack_key].get('facing_open', {})
            base_ranges = facing_dict.get(vs_key)
            if base_ranges is None and vs_position:
                base_ranges = facing_dict.get(f"BB_vs_{vs_position}", [])
            elif base_ranges is None:
                base_ranges = []
            if isinstance(base_ranges, dict):
                r_3b = self._expand_hand_list(base_ranges.get('3b', base_ranges.get('RAISE', [])))
                r_call = self._expand_hand_list(base_ranges.get('call', base_ranges.get('CALL', [])))
                return {"RAISE": r_3b, "CALL": r_call, "FOLD": []}
            return self._convert_to_action_ranges(self._expand_hand_list(base_ranges))
        
        elif spot_kind == 'squeeze':
            sqz_dict = self._ranges[stack_key].get('squeeze', {})
            vs_key = f"{position}_vs_{vs_position}" if (position and vs_position) else position
            base_ranges = sqz_dict.get(vs_key) or sqz_dict.get(position, [])
            if isinstance(base_ranges, dict):
                r_sqz = self._expand_hand_list(base_ranges.get('squeeze', base_ranges.get('3b', base_ranges.get('RAISE', []))))
                r_call = self._expand_hand_list(base_ranges.get('call', base_ranges.get('CALL', [])))
                return {"RAISE": r_sqz, "CALL": r_call, "FOLD": []}
            return self._convert_to_action_ranges(self._expand_hand_list(base_ranges))

        elif spot_kind == 'iso_raise':
            import ranges as _ranges_mod
            iso_dict = self._ranges[stack_key].get('iso_raise', {})
            base_ranges = iso_dict.get(position)
            if isinstance(base_ranges, dict):
                r_iso = self._expand_hand_list(base_ranges.get('iso', base_ranges.get('RAISE', [])))
                r_limp = self._expand_hand_list(base_ranges.get('limp', base_ranges.get('call', base_ranges.get('CALL', []))))
                return {"RAISE": r_iso, "CALL": r_limp, "FOLD": []}
            elif isinstance(base_ranges, list) and base_ranges:
                return self._convert_to_action_ranges(self._expand_hand_list(base_ranges))
            r = _ranges_mod.ISO_RAISE_BY_POS.get(position, {})
            return {"RAISE": sorted(r.get("iso", set())), "CALL": sorted(r.get("limp", set())), "FOLD": []}

        elif spot_kind == 'facing_3bet':
            facing_3b_dict = self._ranges[stack_key].get('facing_3bet', {})
            base_ranges = facing_3b_dict.get(position, [])
            if isinstance(base_ranges, dict):
                r_4b = self._expand_hand_list(base_ranges.get('4b', base_ranges.get('RAISE', [])))
                r_call = self._expand_hand_list(base_ranges.get('call', base_ranges.get('CALL', [])))
                return {"RAISE": r_4b, "CALL": r_call, "FOLD": []}
            return self._convert_to_action_ranges(self._expand_hand_list(base_ranges))

        elif spot_kind == 'facing_4bet':
            facing_4b_data = self._ranges[stack_key].get('facing_4bet', {})
            if isinstance(facing_4b_data, list):
                return self._convert_to_action_ranges(self._expand_hand_list(facing_4b_data))
            elif isinstance(facing_4b_data, dict):
                if position and position in facing_4b_data:
                    pos_data = facing_4b_data[position]
                    if isinstance(pos_data, list):
                        return self._convert_to_action_ranges(self._expand_hand_list(pos_data))
                    elif isinstance(pos_data, dict):
                        r_5b = self._expand_hand_list(pos_data.get('5b', pos_data.get('RAISE', [])))
                        r_call = self._expand_hand_list(pos_data.get('call', pos_data.get('CALL', [])))
                        return {"RAISE": r_5b, "CALL": r_call, "FOLD": []}
                r_5b = self._expand_hand_list(facing_4b_data.get('5b', facing_4b_data.get('RAISE', [])))
                r_call = self._expand_hand_list(facing_4b_data.get('call', facing_4b_data.get('CALL', [])))
                if r_5b or r_call:
                    return {"RAISE": r_5b, "CALL": r_call, "FOLD": []}
        
        return {"FOLD": []}
    
    def _convert_to_action_ranges(self, hand_list: List[str]) -> Dict[str, List[str]]:
        """Convert a hand list to action-based ranges with frequencies."""
        if not hand_list:
            return {"FOLD": []}
        
        # Apply profile modifier
        modifier = PROFILE_MODIFIERS[self.config.profile]
        tighten = modifier['tighten_factor']
        
        # Apply aggression factor to determine action distribution
        aggression = self.config.aggression_factor
        
        # Filter candidate hands by tighten_factor when profile is not standard
        ranked = sorted(hand_list, key=lambda h: (self._estimate_hand_strength(h), h), reverse=True)
        if abs(tighten - 1.0) > 1e-6:
            keep_count = max(1, min(len(ranked), int(round(len(ranked) * tighten))))
            active_hands = set(ranked[:keep_count])
        else:
            active_hands = set(hand_list)
        
        # Calculate action frequencies based on hand strength
        raise_hands = []
        call_hands = []
        fold_hands = []
        
        for hand in hand_list:
            if hand not in active_hands:
                fold_hands.append(hand)
                continue
            strength = self._estimate_hand_strength(hand)
            
            # Adjust thresholds based on aggression and profile tighten factor
            profile_shift = (1.0 - tighten) * 0.1
            raise_threshold = 0.6 - (aggression - 1.0) * 0.15 + profile_shift
            call_threshold = 0.3 - (aggression - 1.0) * 0.1 + profile_shift
            
            if strength >= raise_threshold:
                raise_hands.append(hand)
            elif strength >= call_threshold:
                call_hands.append(hand)
            else:
                fold_hands.append(hand)
        
        return {
            "RAISE": raise_hands,
            "CALL": call_hands,
            "FOLD": fold_hands
        }
    
    def _estimate_hand_strength(self, hand: str) -> float:
        """Estimate hand strength (0-1) for solver-aligned action distribution and rake discipline."""
        if len(hand) < 2:
            return 0.0
        
        rank_order = "23456789TJQKA"
        r1 = hand[0]
        r2 = hand[1]
        suited = hand.endswith('s') if len(hand) > 2 else False
        offsuit = hand.endswith('o') if len(hand) > 2 else (r1 != r2)
        pair = r1 == r2
        
        try:
            idx1 = rank_order.index(r1)
            idx2 = rank_order.index(r2)
        except ValueError:
            return 0.0
        
        high = max(idx1, idx2)
        low = min(idx1, idx2)
        gap = high - low

        # Weight high card more heavily than kicker
        strength = (0.65 * high + 0.35 * low) / 12.0
        
        # Pocket pair bonus (scales with pair rank)
        if pair:
            strength += 0.28 + 0.015 * high
        
        # Suited bonus
        if suited:
            strength += 0.065
            # Suited wheel Aces (A5s-A2s) have extra nut-flush + wheel playability / 3-bet bluff value
            if high == 12 and low <= 3:
                strength += 0.045
            # Suited broadways (KTs+, QTs+, JTs) realize equity strongly
            elif high >= 9 and low >= 8:
                strength += 0.025
        elif offsuit and not pair:
            # Easily dominated offsuit hands with weak kickers suffer reverse implied odds
            if high >= 9 and low <= 7:
                strength -= 0.035
        
        # Connectedness bonus (connectors and 1-gappers)
        if gap == 1:
            strength += 0.04 if suited else 0.025
        elif gap == 2:
            strength += 0.02 if suited else 0.01
        
        return max(0.0, min(1.0, strength))
    
    def import_ranges_from_file(self, file_path: str) -> bool:
        """
        Import custom GTO ranges from a JSON file.
        
        Args:
            file_path: Path to JSON file with ranges
            
        Returns:
            True if import successful, False otherwise
        """
        try:
            with open(file_path, 'r') as f:
                custom_ranges = json.load(f)
            
            # Validate structure
            if not isinstance(custom_ranges, dict):
                return False
            
            # Merge with existing ranges
            self._merge_ranges(custom_ranges)
            self.config.custom_ranges = custom_ranges
            self.config.range_file_path = file_path
            return True
            
        except (json.JSONDecodeError, IOError):
            return False
    
    def _merge_ranges(self, custom_ranges: Dict[str, Any]):
        """Merge custom ranges with default ranges."""
        for stack_depth, spots in custom_ranges.items():
            if not isinstance(spots, dict):
                continue
            if stack_depth not in self._ranges:
                self._ranges[stack_depth] = {}
            
            for spot_type, positions in spots.items():
                if isinstance(positions, list):
                    self._ranges[stack_depth][spot_type] = self._expand_hand_list(positions)
                    continue
                if not isinstance(positions, dict):
                    continue
                if spot_type not in self._ranges[stack_depth] or not isinstance(self._ranges[stack_depth][spot_type], dict):
                    self._ranges[stack_depth][spot_type] = {}
                elif spot_type == "facing_4bet" and any(k in positions for k in ("5b", "call", "RAISE", "CALL")) and not any(k in positions for k in ("UTG", "MP", "CO", "BTN", "SB", "BB")):
                    # Global facing_4bet override clears default position-specific sub-dicts
                    self._ranges[stack_depth][spot_type] = {}
                
                for position, hands in positions.items():
                    if isinstance(hands, list):
                        self._ranges[stack_depth][spot_type][position] = self._expand_hand_list(hands)
                    elif isinstance(hands, str):
                        self._ranges[stack_depth][spot_type][position] = self._expand_hand_list([hands])
                    elif isinstance(hands, dict):
                        self._ranges[stack_depth][spot_type][position] = {
                            k: (self._expand_hand_list(v) if isinstance(v, list) else self._expand_hand_list([v]) if isinstance(v, str) else v)
                            for k, v in hands.items()
                        }
                    else:
                        self._ranges[stack_depth][spot_type][position] = hands

    def is_default_state(self) -> bool:
        """Return True if StrategyManager is at default settings (ABC, 100bb, 1.0x, no custom ranges)."""
        return (
            self.config.profile == StrategyProfile.ABC
            and abs(self.config.aggression_factor - 1.0) < 1e-6
            and self.config.stack_depth == 100
            and not self.config.custom_ranges
        )

    def advise_with_strategy(
        self,
        spot: Dict[str, Any],
        hand: Optional[str],
        base_action_sets: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Tuple[str, str]], Dict[str, Any]]:
        """
        Compute preflop advice and action sets adjusted by active strategy settings
        (profile, stack depth, aggression factor, or custom imported JSON ranges).
        When in default state (ABC, 100bb, 1.0x, no custom ranges), preserves exact
        ranges.py behavior.

        Returns:
            Tuple of ((action, detail_str) or None, adjusted_action_sets: dict)
        """
        import ranges as _ranges_mod

        if base_action_sets is None:
            base_action_sets = _ranges_mod.get_action_sets(spot)

        # Strategy preferences must not turn unsupported spots into advice.
        if _ranges_mod.advise(spot, hand or "AA") is None:
            return None, base_action_sets

        # Preserve exact default ranges.py behavior in default state
        if self.is_default_state():
            base_adv = _ranges_mod.advise(spot, hand) if hand else None
            return base_adv, base_action_sets

        kind = spot.get("kind", "open")
        all_169 = _ranges_mod.all_hands()
        ranked_169 = sorted(all_169, key=lambda h: self._estimate_hand_strength(h), reverse=True)

        # Determine effective scale factor from profile, aggression, and stack depth
        modifier = PROFILE_MODIFIERS.get(self.config.profile, PROFILE_MODIFIERS[StrategyProfile.ABC])
        tighten = modifier["tighten_factor"]
        agg = self.config.aggression_factor

        # Short stacks tighten speculative calls and increase shove/raise propensity
        stack_mult = 1.0
        if self.config.stack_depth <= 20:
            stack_mult = 0.85
        elif self.config.stack_depth <= 50:
            stack_mult = 0.92
        elif self.config.stack_depth >= 150:
            stack_mult = 1.08

        scale = tighten * agg * stack_mult

        # Copy base action sets so we don't mutate global sets
        adjusted_sets: Dict[str, set] = {k: set(v) for k, v in base_action_sets.items()}

        # Check if custom ranges or stack-specific ranges override this spot
        if self.config.custom_ranges or self.config.stack_depth != 100:
            spot_ranges = self.get_ranges_for_spot(spot)
            spot_raise = set(spot_ranges.get("RAISE", []))
            spot_call = set(spot_ranges.get("CALL", []))
            if kind == "open" and (spot_raise or spot_call):
                adjusted_sets["RAISE"] = spot_raise | spot_call
            elif kind == "facing_open" and (spot_raise or spot_call):
                if spot_raise:
                    adjusted_sets["3-BET"] = spot_raise
                if spot_call:
                    adjusted_sets["CALL"] = spot_call - adjusted_sets.get("3-BET", set())
            elif kind == "squeeze" and (spot_raise or spot_call):
                if spot_raise:
                    adjusted_sets["3-BET"] = spot_raise
                if spot_call:
                    adjusted_sets["CALL"] = spot_call - adjusted_sets.get("3-BET", set())
            elif kind == "iso_raise" and (spot_raise or spot_call):
                if spot_raise:
                    adjusted_sets["RAISE"] = spot_raise
                if spot_call:
                    adjusted_sets["CALL"] = spot_call - adjusted_sets.get("RAISE", set())
            elif kind == "facing_3bet" and (spot_raise or spot_call):
                if spot_raise:
                    adjusted_sets["4-BET"] = spot_raise
                if spot_call:
                    adjusted_sets["CALL"] = spot_call - adjusted_sets.get("4-BET", set())
                elif spot_raise:
                    adjusted_sets["CALL"] = adjusted_sets.get("CALL", set()) - spot_raise
            elif kind == "facing_4bet" and (spot_raise or spot_call):
                if spot_raise:
                    adjusted_sets["5-BET"] = spot_raise
                if spot_call:
                    adjusted_sets["CALL"] = spot_call - adjusted_sets.get("5-BET", set())
                elif spot_raise:
                    adjusted_sets["CALL"] = adjusted_sets.get("CALL", set()) - spot_raise

        # Adjust set sizes according to scale
        for act_key in list(adjusted_sets.keys()):
            current_set = adjusted_sets[act_key]
            base_count = len(current_set)
            if base_count == 0:
                continue

            is_aggressive_act = act_key in ("RAISE", "3-BET", "4-BET", "5-BET")
            is_polarized_act = act_key in ("3-BET", "4-BET", "5-BET")
            act_scale = scale if is_aggressive_act else (tighten * stack_mult / max(0.5, agg ** 0.3))
            target_count = max(1, min(169, int(round(base_count * act_scale))))

            def _hand_priority(h: str, _polarized: bool = is_polarized_act) -> Tuple[float, str]:
                score = self._estimate_hand_strength(h)
                if _polarized and h in ("A5s", "A4s", "A3s", "A2s"):
                    # Preserve solver polarized wheel-ace bluffs ahead of weaker linear hands
                    score += 0.14
                return (score, h)

            sorted_current = sorted(current_set, key=_hand_priority, reverse=True)
            if target_count < base_count:
                adjusted_sets[act_key] = set(sorted_current[:target_count])
            elif target_count > base_count:
                new_set = set(current_set)
                # Avoid overlapping with higher-priority actions
                already_assigned = set()
                for other_k, other_s in adjusted_sets.items():
                    if other_k != act_key:
                        already_assigned |= other_s
                for cand in ranked_169:
                    if len(new_set) >= target_count:
                        break
                    if cand not in new_set and cand not in already_assigned:
                        new_set.add(cand)
                adjusted_sets[act_key] = new_set

        # Ensure disjoint sets where both aggressive and passive actions exist
        if "RAISE" in adjusted_sets and "CALL" in adjusted_sets:
            adjusted_sets["CALL"] -= adjusted_sets["RAISE"]
        if "3-BET" in adjusted_sets and "CALL" in adjusted_sets:
            adjusted_sets["CALL"] -= adjusted_sets["3-BET"]
        if "4-BET" in adjusted_sets and "CALL" in adjusted_sets:
            adjusted_sets["CALL"] -= adjusted_sets["4-BET"]
        if "5-BET" in adjusted_sets and "CALL" in adjusted_sets:
            adjusted_sets["CALL"] -= adjusted_sets["5-BET"]

        if not hand:
            return None, adjusted_sets

        tag = f"[{self.config.profile.value} {self.config.stack_depth}bb {self.config.aggression_factor:.1f}x]"
        if kind == "open":
            if hand in adjusted_sets.get("RAISE", set()):
                return ("RAISE", f"Open raise {tag}"), adjusted_sets
            return ("FOLD", f"Not in open range {tag}"), adjusted_sets
        elif kind == "facing_open":
            if hand in adjusted_sets.get("3-BET", set()):
                return ("3-BET", f"3-bet {tag}"), adjusted_sets
            if hand in adjusted_sets.get("CALL", set()):
                return ("CALL", f"Call open {tag}"), adjusted_sets
            return ("FOLD", f"Fold vs open {tag}"), adjusted_sets
        elif kind == "squeeze":
            if hand in adjusted_sets.get("3-BET", set()):
                return ("SQUEEZE", f"Squeeze 3-bet {tag}"), adjusted_sets
            if hand in adjusted_sets.get("CALL", set()):
                return ("CALL", f"Overcall squeeze spot {tag}"), adjusted_sets
            return ("FOLD", f"Fold in squeeze spot {tag}"), adjusted_sets
        elif kind == "iso_raise":
            if hand in adjusted_sets.get("RAISE", set()):
                return ("RAISE", f"Iso-raise vs limper {tag}"), adjusted_sets
            if hand in adjusted_sets.get("CALL", set()):
                return ("CALL", f"Overlimp / check option {tag}"), adjusted_sets
            return ("FOLD", f"Fold vs limper {tag}"), adjusted_sets
        elif kind == "facing_3bet":
            if hand in adjusted_sets.get("4-BET", set()):
                return ("4-BET", f"4-bet {tag}"), adjusted_sets
            if hand in adjusted_sets.get("CALL", set()):
                return ("CALL", f"Call 3-bet {tag}"), adjusted_sets
            return ("FOLD", f"Fold vs 3-bet {tag}"), adjusted_sets
        elif kind == "facing_4bet":
            if hand in adjusted_sets.get("5-BET", set()):
                return ("5-BET/SHOVE", f"5-bet shove {tag}"), adjusted_sets
            if hand in adjusted_sets.get("CALL", set()):
                return ("CALL", f"Call 4-bet {tag}"), adjusted_sets
            return ("FOLD", f"Fold vs 4-bet {tag}"), adjusted_sets

        return _ranges_mod.advise(spot, hand), adjusted_sets
    
    def export_ranges_to_file(self, file_path: str) -> bool:
        """
        Export current ranges to a JSON file.
        
        Args:
            file_path: Path to save JSON file
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self._ranges, f, indent=2)
            return True
        except IOError:
            return False
    
    def get_confidence_percentage(self, hand: str, action: str, 
                                   action_ranges: Dict[str, List[str]]) -> float:
        """
        Calculate confidence percentage for a recommendation.
        
        Args:
            hand: The hand in question
            action: The recommended action
            action_ranges: Dictionary of action to hand lists
            
        Returns:
            Confidence percentage (0-100)
        """
        if hand not in action_ranges.get(action, []):
            return 0.0
        
        # Get all hands in this action category
        action_hands = action_ranges.get(action, [])
        total_hands = sum(len(hands) for hands in action_ranges.values())
        
        if total_hands == 0:
            return 0.0
        
        # Calculate frequency within action
        action_frequency = len(action_hands) / total_hands
        
        # Calculate hand's relative strength within action
        hand_strength = self._estimate_hand_strength(hand)
        action_strengths = [self._estimate_hand_strength(h) for h in action_hands]
        
        if action_strengths:
            avg_strength = sum(action_strengths) / len(action_strengths)
            strength_ratio = hand_strength / avg_strength if avg_strength > 0 else 1.0
        else:
            strength_ratio = 1.0
        
        # Combine factors for confidence
        # Base confidence from being in the range
        base_confidence = 50.0
        
        # Boost for high frequency actions
        frequency_bonus = action_frequency * 30.0
        
        # Boost for strong hands within action
        strength_bonus = min(20.0, (strength_ratio - 1.0) * 40.0)
        
        confidence = base_confidence + frequency_bonus + strength_bonus
        return min(100.0, max(0.0, confidence))
    
    def get_all_stack_depths(self) -> List[int]:
        """Get list of supported stack depths."""
        return [20, 50, 100, 150]
    
    def get_all_profiles(self) -> List[StrategyProfile]:
        """Get list of available strategy profiles."""
        return list(StrategyProfile)

    @staticmethod
    def get_exploitative_vpip_adjustment(opponent_vpip: Optional[float]) -> Dict[str, Any]:
        """Compute exploitative strategy adjustments from an opponent's VPIP percentage (0..100)."""
        if opponent_vpip is None:
            return {
                "player_type": "unknown",
                "vpip": None,
                "aggression_delta": 0.0,
                "value_thresh_shift": 0.0,
                "semi_bluff_shift": 0.0,
                "call_shift": 0.0,
            }
        vpip = max(0.0, min(100.0, float(opponent_vpip)))
        if vpip >= 45.0:
            # Recreational / loose-passive calling station: value-bet thinner, bluff less
            return {
                "player_type": "loose_passive",
                "vpip": vpip,
                "aggression_delta": 0.15,
                "value_thresh_shift": -0.04,
                "semi_bluff_shift": 0.03,
                "call_shift": -0.02,
            }
        if vpip <= 18.0:
            # Nit / ultra-tight: tighten value thresholds against their action, increase c-bet/steals
            return {
                "player_type": "nit",
                "vpip": vpip,
                "aggression_delta": -0.10,
                "value_thresh_shift": 0.03,
                "semi_bluff_shift": -0.02,
                "call_shift": 0.03,
            }
        return {
            "player_type": "regular",
            "vpip": vpip,
            "aggression_delta": 0.0,
            "value_thresh_shift": 0.0,
            "semi_bluff_shift": 0.0,
            "call_shift": 0.0,
        }


# Global strategy manager instance
_strategy_manager = StrategyManager()


def get_strategy_manager() -> StrategyManager:
    """Get the global strategy manager instance."""
    return _strategy_manager


def load_default_ranges_file() -> str:
    """Get path to default ranges JSON file."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_ranges.json")
