"""Independent payoff/equilibrium checks for the restricted solver."""
import numpy as np
import pytest

from showdown_solver import solve_showdown_game
from postflop import solve_cfr_subgame, get_postflop_advice
from equity import parse_hand, evaluate_hand


def test_fractional_equity_is_not_a_certain_win():
    result = solve_showdown_game([[.6]], [[1]], 100, 100, 100, iterations=1000)
    assert result['actions'] == ['FOLD', 'CALL']
    assert result['action_values'][0, 1] == pytest.approx(20)
    assert result['hand_values'][0] == pytest.approx(20, abs=.001)


def test_losing_showdown_can_still_be_profitable_call():
    result = solve_showdown_game([[.4]], [[1]], 150, 50, 50, iterations=1000)
    assert result['action_values'][0, 1] == pytest.approx(30)
    assert result['strategy'][0, 1] > .999


def test_known_polarized_bluffing_equilibrium():
    # Half nuts, half air vs a bluff catcher. Pot-sized betting equilibrium:
    # nuts always bet, air bets half, defender calls half; value = 0.75 pot.
    result = solve_showdown_game([[1], [0]], [[1], [1]], 100, 0, 100,
                                 iterations=5000, bet_fractions=(1,))
    assert result['strategy'][0, 1] > .999
    assert result['strategy'][1, 1] == pytest.approx(.5, abs=.02)
    assert result['opponent_strategy'][0, 0, 1] == pytest.approx(.5, abs=.02)
    assert result['value'] == pytest.approx(75, abs=.1)
    assert result['gap_chips'] < .5


def test_card_collisions_do_not_change_values():
    result = solve_showdown_game([[.6, 0]], [[1, 0]], 100, 100, 100)
    assert result['action_values'][0, 1] == pytest.approx(20)


def test_short_all_in_returns_uncalled_excess():
    result = solve_showdown_game([[1]], [[1]], 200, 150, 50)
    assert result['actions'] == ['FOLD', 'CALL']
    assert result['action_values'][0, 1] == pytest.approx(100)


def test_raise_reserves_call_from_stack():
    result = solve_showdown_game([[.6]], [[1]], 100, 50, 60)
    assert result['branch_sizes'][0]['hero_investment'] == 60
    assert result['branch_sizes'][0]['opponent_call'] == 10


def test_zero_stack_has_no_bet_and_ties_split_pot():
    result = solve_showdown_game([[.5]], [[1]], 100, 0, 0)
    assert result['actions'] == ['CHECK']
    assert result['value'] == 50
    assert result['gap_chips'] == 0


@pytest.mark.parametrize('equity,valid', [([[float('nan')]], [[1]]),
                                        ([[1.1]], [[1]]), ([[.5]], [[0]])])
def test_invalid_games_rejected(equity, valid):
    with pytest.raises(ValueError):
        solve_showdown_game(equity, valid, 100, 0, 100)


def test_requested_training_budget_is_not_silently_capped():
    result = solve_showdown_game([[.5]], [[1]], 100, 0, 100, iterations=321)
    assert result['iterations'] == 321
    assert np.allclose(result['strategy'].sum(axis=1), 1)


def test_turn_runouts_match_independent_enumeration():
    hero, opponent, board = 'AhKd', 'QsQh', '2c7dJsTc'
    h, o, b = map(parse_hand, (hero, opponent, board))
    shares = []
    for river in set(range(52)) - set(h + o + b):
        hs, os = evaluate_hand(h + b + [river]), evaluate_hand(o + b + [river])
        shares.append(1 if hs > os else .5 if hs == os else 0)
    expected = sum(shares) / len(shares) * 100
    result = solve_cfr_subgame(hero, board, 100, 0, 0, opponent)
    assert result['solver_status'] == 'approximate'
    assert result['solver_equity_exact'] is True
    assert result['ev'] == pytest.approx(expected, abs=.01)
    assert result['future_betting'] is False


def test_invalid_cards_do_not_fabricate_a_strategy():
    result = solve_cfr_subgame('AhKd', 'Ah2c3d4s5h', 100, 50, 100, 'QQ')
    assert result['solver_status'] == 'unavailable'
    assert result['cfr_frequencies'] == {}


def test_terminal_values_do_not_depend_on_position():
    args = ('AhKd', '2c7dJsTc3s', 100, 0, 0, 'QQ')
    assert solve_cfr_subgame(*args, in_position=True)['ev'] == solve_cfr_subgame(*args, in_position=False)['ev']


def test_advice_exposes_limits_of_solver():
    advice = get_postflop_advice('AhKh', 'QhJhTh2c3d', 100, 50, effective_stack=200)
    assert advice['solver_diagnostics']['solver_status'] == 'approximate'
    assert advice['solver_diagnostics']['future_betting'] is False
    assert advice['solver_diagnostics']['solver_gap_chips'] >= 0


def test_opponent_reraise_branch_and_flop_cfr_solving():
    # Verify Villain reraise branch is solved when allow_opponent_reraise=True
    res = solve_showdown_game([[1.0], [0.0]], [[1.0], [1.0]], 100, 0, 200,
                              iterations=600, allow_opponent_reraise=True)
    assert res['model'] == 'heads_up_reraise_showdown'
    assert res['opponent_strategy'].shape[2] == 3
    assert 'hero_reraise_response' in res
    assert res['gap_chips'] < 2.0

    # Verify flop advice uses CFR+ subgame solver rather than coarse heuristic
    flop_adv = get_postflop_advice('AhKh', 'QhJh2c', 100, 50, effective_stack=200, iterations=200)
    assert flop_adv['solver_diagnostics']['solver_status'] == 'approximate'
    assert sum(flop_adv['cfr_frequencies'].values()) == 100
