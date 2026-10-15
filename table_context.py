"""Observed preflop betting state and explicit chip/big-blind conversions."""
import math
import re


NUMBER = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'


def parse_amount(text):
    """Return (value, unit), rejecting incomplete/grouping errors and labels."""
    match = re.fullmatch(r'[\s\\/|()]*[$£€]?\s*(' + NUMBER + r')\s*(BB)?[\s\\/|()]*', text, re.I)
    if not match:
        return None
    value = float(match[1].replace(',', ''))
    return (value, 'bb' if match[2] else None) if math.isfinite(value) else None


def parse_blinds(title):
    match = re.search(r'(?<![\d,.])[$£€]?\s*(' + NUMBER + r')\s*[/|]\s*[$£€]?\s*('
                      + NUMBER + r')(?![\d,.])', title)
    if not match:
        return None
    small, big = (float(match[i].replace(',', '')) for i in (1, 2))
    return (small, big) if 0 < small < big and math.isfinite(big) else None


def convert_amount(value, source, target, big_blind):
    if source not in ('chips', 'bb') or target not in ('chips', 'bb'):
        raise ValueError('Select chips or BB')
    if not math.isfinite(value) or value < 0:
        raise ValueError('Amount must be a non-negative number')
    if source == target:
        return value
    if big_blind is None or not math.isfinite(big_blind) or big_blind <= 0:
        raise ValueError('Enter the big blind to convert amounts')
    return value / big_blind if target == 'bb' else value * big_blind


def format_amount(value):
    return f'{value:,.2f}'.rstrip('0').rstrip('.') if value % 1 else f'{value:,.0f}'


class PreflopTracker:
    """Track raises only after observing a complete blind-only starting state.

    A snapshot taken after raising began cannot establish the raise count.
    Read gaps recover automatically when a fresh frame confirms unchanged
    wagers. Missed changes and unsupported limped / multiway spots suppress
    automatic recommendations until the next hand.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.key = None
        self.bets = None
        self.raises = []
        self.action_log = []
        self.limped = False
        self.lost = False
        self.gap = False
        self.positions = None
        self.previous_depth = None
        self.depth_count = 0

    def update(self, reading):
        cards = reading.get('cards')
        if not cards or not reading.get('reliable'):
            self.reset()
            return {}
        key = (reading.get('table_id'), tuple(sorted(cards)))
        if key != self.key:
            self.reset()
            self.key = key
        data = reading.get('preflop') or {}
        result = dict(data, spot=None, vs=None, effective_bb=None,
                      message=data.get('error') or 'Waiting for readable betting context')
        bb = data.get('big_blind')
        bets, stacks = data.get('bets', {}), data.get('stacks', {})
        positions = data.get('positions', {})
        if data.get('board_present'):
            self.lost = True
            result['message'] = 'Board is out — switch to Postflop'
            return result
        if not data.get('complete') or not bb or 3 not in bets:
            if self.bets is not None:
                self.gap = True
            return result
        epsilon = bb * .01
        if data.get('pot') is None or abs(data['pot'] - sum(bets.values())) > epsilon:
            result['message'] = 'Reading moving chips — waiting for pot and wagers to settle'
            return result
        if self.gap:
            # A transient OCR failure need not poison the whole hand. Resume
            # only when a fresh complete frame proves the wager state unchanged.
            unchanged = (self.bets is not None and self.bets.keys() == bets.keys()
                         and self.positions == positions
                         and all(abs(bets[s] - self.bets[s]) <= epsilon for s in bets))
            if not unchanged:
                self.lost = True
            self.gap = False
        if self.lost and self.bets is None and not self.raises and not self.limped:
            # Allow a clean blind-only baseline frame to recover if the initial
            # frame of the hand caught chips still settling.
            expected = {seat: (bb if pos == 'BB' else data['small_blind'] if pos == 'SB' else 0)
                        for seat, pos in positions.items()}
            if (expected.keys() == bets.keys() and
                    all(abs(bets[s] - value) <= epsilon for s, value in expected.items()) and
                    data.get('pot') is not None and
                    abs(data['pot'] - sum(expected.values())) <= epsilon):
                self.lost = False
        if self.bets is None and not self.lost:
            expected = {seat: (bb if pos == 'BB' else data['small_blind'] if pos == 'SB' else 0)
                        for seat, pos in positions.items()}
            # Pot matching blinds also excludes hidden limpers, antes and straddles.
            baseline = (expected.keys() == bets.keys() and
                        all(abs(bets[s] - value) <= epsilon for s, value in expected.items()) and
                        data.get('pot') is not None and
                        abs(data['pot'] - sum(expected.values())) <= epsilon)
            if baseline:
                self.bets = dict(bets)
                self.positions = dict(positions)
            else:
                self.lost = True
        elif self.bets is not None and not self.lost:
            if self.positions != positions or set(self.bets) != set(bets) or any(bets[s] < self.bets[s] - epsilon for s in bets):
                self.lost = True
            else:
                previous_max = max(self.bets.values())
                increases = [s for s in bets if bets[s] > self.bets[s] + epsilon]
                raises = [s for s in increases if bets[s] > previous_max + epsilon]
                if len(raises) > 1:
                    self.lost = True
                elif raises:
                    r_seat = raises[0]
                    self.raises.append(r_seat)
                    for s in increases:
                        if s != r_seat:
                            self.action_log.append({
                                'seat': s,
                                'pos': positions.get(s),
                                'action': 'call',
                                'amount': float(bets[s]),
                                'amount_bb': round(float(bets[s]) / float(bb), 2),
                            })
                    self.action_log.append({
                        'seat': r_seat,
                        'pos': positions.get(r_seat),
                        'action': 'raise_to',
                        'amount': float(bets[r_seat]),
                        'amount_bb': round(float(bets[r_seat]) / float(bb), 2),
                    })
                elif increases:
                    for s in increases:
                        self.action_log.append({
                            'seat': s,
                            'pos': positions.get(s),
                            'action': 'call',
                            'amount': float(bets[s]),
                            'amount_bb': round(float(bets[s]) / float(bb), 2),
                        })
                if not self.raises and any(positions.get(s) not in ('SB', 'BB') for s in increases):
                    self.limped = True
                if not self.raises and any(positions.get(s) == 'SB' and bets[s] >= bb - epsilon for s in increases):
                    self.limped = True
                self.bets = dict(bets)

        result['action_history'] = list(self.action_log) if not self.lost else []
        # Remaining stack plus street contribution restores the preflop stack.
        total_stacks = {s: stacks[s] + bets[s] for s in bets if stacks.get(s) is not None}
        opponents = [s for s in total_stacks if s != 3]
        aggressor = self.raises[-1] if self.raises else None
        if 3 in total_stacks and opponents and len(total_stacks) == len(bets):
            opposing = total_stacks.get(aggressor) if aggressor is not None and aggressor != 3 else max(total_stacks[s] for s in opponents)
            depth = min(total_stacks[3], opposing) / bb
            self.depth_count = self.depth_count + 1 if self.previous_depth is not None and abs(depth - self.previous_depth) < .05 else 1
            self.previous_depth = depth
            result['hero_bb'] = total_stacks[3] / bb
            if self.depth_count >= 2:
                result['effective_bb'] = depth
        else:
            self.previous_depth, self.depth_count = None, 0
        if self.lost:
            hero_bet = bets.get(3, 0)
            opp_raises = [s for s in bets if s != 3 and bets[s] > bb + epsilon]
            non_blind_callers = [
                s for s in bets
                if s != 3 and s not in opp_raises and bets[s] > bb + epsilon
            ]
            sb = data.get('small_blind') or (bb / 2)
            pot_val = data.get('pot')
            has_limped_pot = (
                (pot_val is None or pot_val > sb + bb + epsilon)
                and sum(1 for v in bets.values() if v is not None and v >= bb - epsilon) >= 2
            )
            limpers = [
                s for s in bets
                if has_limped_pot and s != 3 and s not in opp_raises
                and (
                    (positions.get(s) not in ('SB', 'BB') and bets[s] >= bb - epsilon)
                    or (positions.get(s) == 'SB' and abs(bets[s] - bb) <= epsilon)
                )
            ]
            call_amt = data.get('call')
            call_consistent = (
                call_amt is None
                or abs(call_amt + hero_bet - max(bets.values())) <= epsilon
            )
            if call_consistent and not non_blind_callers and not limpers:
                if len(opp_raises) == 1 and hero_bet <= bb + epsilon:
                    raiser = opp_raises[0]
                    if bets[raiser] <= 4.5 * bb + epsilon and positions.get(raiser) not in (None, 'BB'):
                        result['inferred_spot'] = 'facing_open'
                        result['inferred_vs'] = positions.get(raiser)
                elif len(opp_raises) == 1 and hero_bet > bb + epsilon:
                    raiser = opp_raises[0]
                    if bets[raiser] > hero_bet + epsilon:
                        result['inferred_spot'] = 'facing_3bet' if hero_bet <= 4.5 * bb + epsilon else 'facing_4bet'
                        result['inferred_vs'] = positions.get(raiser)
            elif call_consistent and not opp_raises and limpers and hero_bet <= bb + epsilon:
                result['inferred_spot'] = 'iso_raise'
                result['inferred_vs'] = positions.get(limpers[0])
            result['message'] = 'Earlier action was missed — select action and opener manually'
            return result
        if self.limped:
            limpers = [
                s for s in bets
                if s != 3 and (
                    (positions.get(s) not in ('SB', 'BB') and bets[s] > epsilon)
                    or (positions.get(s) == 'SB' and abs(bets[s] - bb) <= epsilon)
                )
            ]
            if limpers:
                result['inferred_spot'] = 'iso_raise'
                result['inferred_vs'] = positions.get(limpers[0])
            result['message'] = 'Limped pot — automatic ranges do not cover this spot'
            return result
        call = data.get('call')
        if call is None:
            if not self.raises and data.get('action_turn') and positions.get(3) not in (None, 'BB'):
                result.update(spot='open', message='Unopened pot detected')
                return result
            result['message'] = 'Tracking bets — waiting for your action buttons'
            return result
        if abs(call + bets[3] - max(bets.values())) > epsilon:
            result['message'] = 'Bet and call amounts are changing — waiting for a stable frame'
            return result
        if self.raises and any(bets[s] > bb + epsilon for s in bets if s not in (3, self.raises[-1])):
            if len(self.raises) == 1 and self.raises[0] != 3:
                result['inferred_spot'] = 'squeeze'
                result['inferred_vs'] = positions.get(self.raises[0])
            result['message'] = 'Raise and callers detected — multiway ranges unavailable'
            return result
        if not self.raises:
            if positions.get(3) == 'BB':
                result['message'] = 'Unraised big blind — check option; no opening range applies'
                return result
            result.update(spot='open', message='Unopened pot detected')
        elif len(self.raises) == 1 and self.raises[0] != 3:
            raiser = self.raises[0]
            if any(bets[s] > bb + epsilon for s in bets if s not in (3, raiser)):
                result['inferred_spot'] = 'squeeze'
                result['inferred_vs'] = positions.get(raiser)
                result['message'] = 'Raise and callers detected — multiway ranges unavailable'
            else:
                result.update(spot='facing_open', vs=positions.get(raiser), message='Open raise detected')
        elif len(self.raises) == 2 and self.raises[0] == 3 and self.raises[1] != 3:
            result.update(spot='facing_3bet', vs=positions.get(self.raises[1]), message='3-bet against your open detected')
        elif len(self.raises) == 3 and self.raises[1] == 3 and self.raises[2] != 3:
            result.update(spot='facing_4bet', vs=positions.get(self.raises[2]), message='4-bet against your 3-bet detected')
        else:
            result['message'] = 'Waiting for action, or betting sequence outside supported ranges'
        return result


class PostflopTracker:
    """Track postflop street transitions (flop -> turn -> river), starting pot per street,
    and observed postflop bets/calls/checks across frames.

    Resets cleanly when a new hand is dealt, table changes, or an incompatible board
    is observed.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.key = None
        self.board_cards = []
        self.current_street = None
        self.street_start_pot = {}
        self.street_max_wager = {}
        self.street_recorded = set()
        self.postflop_history = []
        self.last_pot = None
        self.last_call = None
        self.in_position = True

    @staticmethod
    def _parse_board(board_str):
        if not board_str or not isinstance(board_str, str):
            return []
        clean = board_str.replace(' ', '').strip()
        if len(clean) % 2 != 0:
            return []
        cards = []
        for i in range(0, len(clean), 2):
            r, s = clean[i].upper(), clean[i + 1].lower()
            if r not in '23456789TJQKA' or s not in 'shdc':
                return []
            cards.append(r + s)
        return cards if len(cards) in (3, 4, 5) and len(set(cards)) == len(cards) else []

    @staticmethod
    def _street_name(num_cards):
        if num_cards == 3:
            return 'flop'
        if num_cards == 4:
            return 'turn'
        if num_cards == 5:
            return 'river'
        return None

    def update(self, reading):
        if not isinstance(reading, dict):
            self.reset()
            return {}
        cards = reading.get('cards')
        if isinstance(cards, str):
            clean_c = cards.replace(' ', '').strip()
            if len(clean_c) == 4:
                cards = (clean_c[:2], clean_c[2:])
        if not cards or len(cards) != 2:
            self.reset()
            return {}
        board_str = reading.get('board') or ''
        parsed_board = self._parse_board(board_str)
        if not parsed_board:
            self.reset()
            return {}

        key = (reading.get('table_id'), tuple(sorted(c[0].upper() + c[1].lower() for c in cards)))
        if self.key != key:
            self.reset()
            self.key = key
        elif self.board_cards:
            # Check board prefix compatibility; if new board does not start with previous board cards, reset
            if len(parsed_board) < len(self.board_cards) or parsed_board[:len(self.board_cards)] != self.board_cards:
                self.reset()
                self.key = key

        bb = float(reading.get('big_blind') or 100.0)
        if bb <= 0:
            bb = 100.0
        epsilon = bb * 0.01
        pot = reading.get('pot_size') if reading.get('pot_size') is not None else reading.get('pot')
        call = reading.get('call_amount') if reading.get('call_amount') is not None else reading.get('call')
        pot = float(pot) if pot is not None else None
        call = float(call) if call is not None else 0.0
        if reading.get('in_position') is not None:
            self.in_position = bool(reading.get('in_position'))

        street = self._street_name(len(parsed_board))
        prev_street = self.current_street

        if prev_street is not None and street != prev_street:
            # Close out previous street(s) before transitioning
            street_order = ['flop', 'turn', 'river']
            prev_idx = street_order.index(prev_street)
            cur_idx = street_order.index(street)
            for idx in range(prev_idx, cur_idx):
                st_name = street_order[idx]
                if st_name in self.street_recorded:
                    continue
                start_p = self.street_start_pot.get(st_name)
                obs_wager = self.street_max_wager.get(st_name, 0.0)
                # Determine pot at the start of the newly reached street (before any new street bet)
                next_start_pot = (pot - call) if (pot is not None and idx == cur_idx - 1) else start_p
                wager = obs_wager
                if wager <= epsilon and start_p is not None and next_start_pot is not None:
                    delta = next_start_pot - start_p
                    if delta > 2 * epsilon:
                        wager = delta / 2.0
                if wager > epsilon:
                    self.postflop_history.append({
                        'street': st_name,
                        'action': 'bet_call',
                        'amount': round(float(wager), 2),
                        'amount_bb': round(float(wager) / bb, 2),
                        'aggressor': 'villain' if self.in_position else 'villain',
                    })
                else:
                    self.postflop_history.append({
                        'street': st_name,
                        'action': 'check_through',
                        'amount': 0.0,
                        'amount_bb': 0.0,
                    })
                self.street_recorded.add(st_name)
                if idx + 1 < cur_idx and start_p is not None:
                    self.street_start_pot.setdefault(street_order[idx + 1], start_p + 2.0 * wager)

        self.board_cards = parsed_board
        self.current_street = street

        if pot is not None:
            est_start = max(0.0, pot - call) if call > 0 else pot
            if street not in self.street_start_pot:
                self.street_start_pot[street] = est_start
            else:
                self.street_start_pot[street] = min(self.street_start_pot[street], est_start)

        if call is not None and call > epsilon:
            prev_w = self.street_max_wager.get(street, 0.0)
            if call > prev_w + epsilon:
                self.street_max_wager[street] = call

        self.last_pot = pot
        self.last_call = call

        return {
            'street': street,
            'board': ''.join(parsed_board),
            'street_start_pot': dict(self.street_start_pot),
            'postflop_history': [dict(item) for item in self.postflop_history],
            'current_street_wager': round(self.street_max_wager.get(street, 0.0), 2),
        }
