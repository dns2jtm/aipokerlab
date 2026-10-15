"""CFR+ for a restricted, heads-up, single-betting-round game.

Calls/checks terminate at showdown; there are no future betting rounds or
opponent reraises. This is NOT a full Hold'em or multiplayer equilibrium solver.
Equity and card compatibility are supplied separately from the game tree.
"""
import math

import numpy as np


def solve_showdown_game(equity, valid, pot, call, stack, iterations=1000,
                        bet_fractions=(0.33, 0.75), tolerance=None,
                        allow_opponent_reraise=False, reraise_fraction=0.75,
                        realization_matrix=None):
    """Solve a uniform-combo Bayesian game and measure its best-response gap.

    pot includes the opponent's outstanding bet; stack is Hero's remaining
    effective stack BEFORE calling. Payoffs are net of all future investment.
    gap_chips is NashConv (sum of both unilateral improvement opportunities),
    averaged over compatible private-card pairs, for THIS restricted game only.

    When allow_opponent_reraise=True, Villain has a 3rd option (RERAISE) when
    stack remains after Hero's bet/raise, and Hero responds with FOLD/CALL.
    When realization_matrix is provided (same shape as equity, in [0, 1]),
    passive check/call lines use realization_matrix while aggressive lines
    blend toward raw showdown equity.
    """
    equity = np.asarray(equity, dtype=float)
    valid = np.asarray(valid, dtype=float)
    if equity.ndim != 2 or equity.shape != valid.shape or not equity.size:
        raise ValueError("Equity and compatibility must be nonempty matching matrices")
    if not np.all(np.isfinite(equity)) or np.any((equity < 0) | (equity > 1)):
        raise ValueError("Equity must be finite and between zero and one")
    if not np.all((valid == 0) | (valid == 1)) or not valid.sum():
        raise ValueError("At least one compatible private-card pair is required")
    if not all(math.isfinite(x) and x >= 0 for x in (pot, call, stack)):
        raise ValueError("Pot, call and stack must be finite nonnegative values")
    if call > pot:
        raise ValueError("Pot must include the outstanding opponent bet")
    if not isinstance(iterations, int) or iterations < 1:
        raise ValueError("iterations must be a positive integer")
    if tolerance is not None and (not math.isfinite(tolerance) or tolerance < 0):
        raise ValueError("tolerance must be finite and nonnegative")

    if realization_matrix is not None:
        passive_eq = np.clip(np.asarray(realization_matrix, dtype=float), 0.0, 1.0)
        if passive_eq.shape != equity.shape or not np.all(np.isfinite(passive_eq)):
            passive_eq = equity
    else:
        passive_eq = equity

    # Return the unmatched part of an opponent's bet on a short all-in call.
    if call > stack:
        pot -= call - stack
        call = stack

    nh, no = equity.shape
    rows = np.maximum(1, valid.sum(axis=1))
    cols = np.maximum(1, valid.sum(axis=0))
    labels, terminal, branches = [], [], []
    if call > 0:
        labels.extend(["FOLD", "CALL"])
        terminal.extend([np.zeros_like(equity), passive_eq * (pot + call) - call])
        additional = min(max(0, stack - call), max(call * 1.5, (pot + call) * .75))
        if additional > 0:
            labels.append("RAISE")
            # Hero invests call + additional; opponent calls additional.
            branches.append((len(labels) - 1, additional, call + additional))
    else:
        labels.append("CHECK")
        terminal.append(passive_eq * pot)
        sizes = []
        for fraction in bet_fractions:
            if not math.isfinite(fraction) or fraction <= 0:
                raise ValueError("Bet fractions must be finite and positive")
            size = min(stack, pot * fraction)
            if size > 0 and size not in sizes:
                sizes.append(size)
        for size in sizes:
            labels.append("BET_" + format(size, ".12g"))
            branches.append((len(labels) - 1, size, size))

    na, nb = len(labels), len(branches)
    # Utility of a called bet, and of a folding opponent, from Hero's root.
    called = [equity * (pot + extra + investment) - investment
              for _, extra, investment in branches]

    nv = 3 if allow_opponent_reraise else 2
    reraise_specs = []
    for _, extra, investment in branches:
        rem_stack = max(0.0, stack - investment)
        pot_after_v_call = pot + extra + investment
        rr_add = min(rem_stack, max(extra * 1.5, pot_after_v_call * reraise_fraction)) if (allow_opponent_reraise and rem_stack > 0) else 0.0
        # When Villain reraises by rr_add:
        # If Hero folds: Hero loses investment -> payoff = -investment
        # If Hero calls: total pot is pot_after_v_call + 2 * rr_add, Hero total investment is investment + rr_add
        hero_fold_payoff = np.full_like(equity, -float(investment))
        hero_call_payoff = equity * (pot_after_v_call + 2.0 * rr_add) - (investment + rr_add)
        reraise_specs.append((rr_add, hero_fold_payoff, hero_call_payoff))

    regret_h = np.zeros((nh, na))
    regret_v = np.zeros((nb, no, nv))
    regret_hr = np.zeros((nb, nh, 2))
    sum_h = np.zeros_like(regret_h)
    sum_v = np.zeros_like(regret_v)
    sum_hr = np.zeros_like(regret_hr)

    def matching(regret):
        denom = regret.sum(axis=-1, keepdims=True)
        return np.divide(regret, denom, out=np.full_like(regret, 1 / regret.shape[-1]),
                         where=denom > 0)

    def branch_reraise_matrix(b, hr_b):
        rr_add, hf_pay, hc_pay = reraise_specs[b]
        if rr_add <= 0:
            return called[b]
        return hr_b[:, 0:1] * hf_pay + hr_b[:, 1:2] * hc_pay

    def root_values(v, hr=None):
        values = np.zeros((nh, na))
        for action, payoff in enumerate(terminal):
            values[:, action] = (valid * payoff).sum(axis=1) / rows
        for b, (action, _, _) in enumerate(branches):
            if nv == 2 or reraise_specs[b][0] <= 0:
                v_fold = v[b, :, 0] + (v[b, :, 2] if nv == 3 else 0.0)
                v_call = v[b, :, 1]
                mat = v_fold[None, :] * pot + v_call[None, :] * called[b]
            else:
                rr_mat = branch_reraise_matrix(b, hr[b])
                mat = (v[b, :, 0][None, :] * pot +
                       v[b, :, 1][None, :] * called[b] +
                       v[b, :, 2][None, :] * rr_mat)
            values[:, action] = (valid * mat).sum(axis=1) / rows
        return values

    def measure(h, v, hr=None):
        values = root_values(v, hr)
        hero_values = (h * values).sum(axis=1)
        profile = float(np.dot(valid.sum(axis=1), hero_values) / valid.sum())
        # Hero best response also optimizes continuation vs reraise when enabled
        best_root = values.copy()
        if nv == 3 and hr is not None:
            for b, (action, _, _) in enumerate(branches):
                rr_add, hf_pay, hc_pay = reraise_specs[b]
                if rr_add > 0:
                    v_rr = v[b, :, 2][None, :]
                    hf_ev = (valid * v_rr * hf_pay).sum(axis=1) / rows
                    hc_ev = (valid * v_rr * hc_pay).sum(axis=1) / rows
                    base_no_rr = (valid * (v[b, :, 0][None, :] * pot + v[b, :, 1][None, :] * called[b])).sum(axis=1) / rows
                    best_root[:, action] = base_no_rr + np.maximum(hf_ev, hc_ev)
        hero_br = float(np.dot(valid.sum(axis=1), best_root.max(axis=1)) / valid.sum())
        # Villain independently picks fold/call(/reraise) for each private hand and branch.
        # Minimize Hero's utility, which is equivalent in this constant-sum game.
        minimum = sum(float((valid * payoff * h[:, a, None]).sum())
                      for a, payoff in enumerate(terminal))
        for b, (action, _, _) in enumerate(branches):
            reach = valid * h[:, action, None]
            opt_fold = (reach * pot).sum(axis=0)
            opt_call = (reach * called[b]).sum(axis=0)
            if nv == 3 and reraise_specs[b][0] > 0 and hr is not None:
                rr_mat = branch_reraise_matrix(b, hr[b])
                opt_rr = (reach * rr_mat).sum(axis=0)
                minimum += float(np.minimum(np.minimum(opt_fold, opt_call), opt_rr).sum())
            else:
                minimum += float(np.minimum(opt_fold, opt_call).sum())
        villain_br_value = minimum / valid.sum()
        return values, hero_values, profile, max(0., hero_br - villain_br_value)

    for step in range(1, iterations + 1):
        h, v = matching(regret_h), matching(regret_v)
        hr = matching(regret_hr) if nv == 3 else None
        values = root_values(v, hr)
        regret_h = np.maximum(0., regret_h + values - (h * values).sum(axis=1, keepdims=True))
        for b, (action, _, _) in enumerate(branches):
            reach = valid * h[:, action, None]
            # Counterfactual reach must retain probability of reaching this
            # branch; normalizing by branch reach changes the CFR algorithm.
            if nv == 3 and reraise_specs[b][0] > 0:
                _, hf_pay, hc_pay = reraise_specs[b]
                rr_mat = branch_reraise_matrix(b, hr[b])
                v_values = np.stack([-(reach * pot).sum(axis=0) / cols,
                                     -(reach * called[b]).sum(axis=0) / cols,
                                     -(reach * rr_mat).sum(axis=0) / cols], axis=1)
                # Update Hero's response regrets against Villain's reraise
                v_rr_reach = valid * h[:, action, None] * v[b, :, 2][None, :]
                hr_values = np.stack([(v_rr_reach * hf_pay).sum(axis=1) / rows,
                                      (v_rr_reach * hc_pay).sum(axis=1) / rows], axis=1)
                regret_hr[b] = np.maximum(0., regret_hr[b] + hr_values -
                                          (hr[b] * hr_values).sum(axis=1, keepdims=True))
            elif nv == 3:
                v_values = np.stack([-(reach * pot).sum(axis=0) / cols,
                                     -(reach * called[b]).sum(axis=0) / cols,
                                     -(reach * called[b]).sum(axis=0) / cols], axis=1)
            else:
                v_values = np.stack([-(reach * pot).sum(axis=0) / cols,
                                     -(reach * called[b]).sum(axis=0) / cols], axis=1)
            regret_v[b] = np.maximum(0., regret_v[b] + v_values -
                                     (v[b] * v_values).sum(axis=1, keepdims=True))
        sum_h += step * h
        sum_v += step * v
        if nv == 3:
            sum_hr += step * hr
        if tolerance is not None and step % 25 == 0:
            div_now = step * (step + 1) / 2
            avg_h, avg_v = sum_h / div_now, sum_v / div_now
            avg_hr = (sum_hr / div_now) if nv == 3 else None
            if measure(avg_h, avg_v, avg_hr)[3] <= tolerance:
                break

    divisor = step * (step + 1) / 2
    avg_h, avg_v = sum_h / divisor, sum_v / divisor
    avg_hr = (sum_hr / divisor) if nv == 3 else None
    values, hero_values, profile, gap = measure(avg_h, avg_v, avg_hr)
    out = dict(actions=labels, strategy=avg_h, opponent_strategy=avg_v,
               action_values=values, hand_values=hero_values, value=profile,
               gap_chips=gap, iterations=step,
               branch_sizes=[dict(action=labels[a], opponent_call=extra,
                                  hero_investment=investment)
                             for a, extra, investment in branches],
               model="heads_up_reraise_showdown" if allow_opponent_reraise else "heads_up_single_round_showdown",
               future_betting=False)
    if nv == 3:
        out["hero_reraise_response"] = avg_hr
    return out
