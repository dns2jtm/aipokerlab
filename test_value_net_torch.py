"""Tests for the PyTorch Belief-State Value Network, IR Ranking Metrics & A/B Evaluation."""

import numpy as np
import pytest
import torch

import value_net_torch as vnt


def _make_synthetic_turn_samples(n: int = 24, seed: int = 7) -> list[vnt.TurnSampleRecord]:
    rng = np.random.default_rng(seed)
    samples = []
    for i in range(n):
        board = tuple(int(x) for x in rng.choice(52, size=4, replace=False))
        pot = int(rng.integers(200, 1600))
        stack = (int(rng.integers(4000, 9500)), int(rng.integers(4000, 9500)))
        commit = (pot // 2, pot // 2)
        r0 = rng.uniform(0.0, 1.0, size=vnt.NUM_COMBOS).astype(np.float32)
        r1 = rng.uniform(0.0, 1.0, size=vnt.NUM_COMBOS).astype(np.float32)
        r0 /= r0.sum()
        r1 /= r1.sum()
        scale = vnt.value_scale(pot, stack)
        # Structured forward values dependent on pot/stack and combo index
        combo_axis = np.linspace(-0.4, 0.4, vnt.NUM_COMBOS, dtype=np.float32)
        pot_factor = float(pot) / 2000.0
        v0 = ((0.5 + 0.3 * pot_factor + combo_axis) * scale).astype(np.float32)
        v1 = ((0.5 - 0.3 * pot_factor - combo_axis) * scale).astype(np.float32)
        samples.append(
            vnt.TurnSampleRecord(
                board=board,
                pot=pot,
                stack=stack,
                commit=commit,
                ranges=(r0, r1),
                values=(v0, v1),
            )
        )
    return samples


def test_encode_turn_state_shape_and_normalization():
    board = (0, 13, 26, 39)
    r0 = np.full(vnt.NUM_COMBOS, 2.0, dtype=np.float32)
    r1 = np.full(vnt.NUM_COMBOS, 5.0, dtype=np.float32)
    x = vnt.encode_turn_state(board, 600, (9700, 9700), (r0, r1))
    assert x.shape == (vnt.INPUT_DIM,)
    assert np.isclose(x[:52].sum(), 4.0)
    assert np.isclose(x[52], 0.06)
    assert np.isclose(x[55 : 55 + vnt.NUM_COMBOS].sum(), 1.0, atol=1e-4)
    assert np.isclose(x[55 + vnt.NUM_COMBOS :].sum(), 1.0, atol=1e-4)


def test_rust_mlp_and_vn01_binary_roundtrip(tmp_path):
    net = vnt.TurnValueNetTorch(hidden_sizes=(32, 16), input_dim=20, output_dim=8, seed=99)
    x = torch.randn(4, 20)
    expected = net(x).detach().numpy()

    for use_header in (False, True):
        path = tmp_path / ("vn01.bin" if use_header else "bincode.bin")
        vnt.save_rust_mlp(net, path, include_vn01_header=use_header)
        raw = path.read_bytes()
        if use_header:
            assert raw[:4] == b"VN01"
        restored = vnt.load_rust_mlp(path)
        assert restored.sizes == [20, 32, 16, 8]
        actual = restored(x).detach().numpy()
        np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)


def test_turn_samples_bincode_roundtrip(tmp_path):
    samples = _make_synthetic_turn_samples(n=5, seed=12)
    path = tmp_path / "turn_data.bin"
    vnt.save_turn_samples_bincode(samples, path)
    loaded = vnt.load_turn_samples_bincode(path)
    assert len(loaded) == 5
    for orig, back in zip(samples, loaded):
        assert orig.board == back.board
        assert orig.pot == back.pot
        assert orig.stack == back.stack
        np.testing.assert_allclose(orig.ranges[0], back.ranges[0], rtol=1e-6, atol=1e-6)
        np.testing.assert_allclose(orig.values[1], back.values[1], rtol=1e-5, atol=1e-5)


def test_pytorch_training_reduces_loss_and_improves_ndcg():
    samples = _make_synthetic_turn_samples(n=24, seed=21)
    untrained = vnt.TurnValueNetTorch(hidden_sizes=(64, 32), seed=1)
    before_eval = vnt.evaluate_value_net_offline(untrained, samples[:6], k_values=(5, 10))

    trained, metrics = vnt.train_value_net_torch(
        samples,
        hidden_sizes=(64, 32),
        epochs=35,
        lr=3e-3,
        batch_size=8,
        loss_type="huber",
        seed=21,
        val_fraction=0.25,
    )
    assert metrics["framework"] == "pytorch"
    assert metrics["history"][-1]["train_loss"] < metrics["history"][0]["train_loss"] * 0.4
    after_eval = vnt.evaluate_value_net_offline(trained, samples[:6], k_values=(5, 10))
    assert after_eval["weighted_mse"] < before_eval["weighted_mse"] * 0.4
    assert after_eval["ndcg@10"] > 0.85
    assert after_eval["mrr"] > 0.75


def test_ir_ranking_metrics_ndcg_mrr_precision_recall_brier():
    true_rel = [3.0, 2.0, 1.0, 0.0, 0.0]
    perfect_scores = [0.95, 0.80, 0.60, 0.20, 0.10]
    reversed_scores = [0.10, 0.20, 0.60, 0.80, 0.95]
    rel_mask = [True, True, False, False, False]

    assert vnt.ndcg_at_k(perfect_scores, true_rel, k=3) == pytest.approx(1.0)
    assert vnt.ndcg_at_k(reversed_scores, true_rel, k=3) < 0.5
    assert vnt.mrr_score(perfect_scores, rel_mask) == pytest.approx(1.0)
    assert vnt.mrr_score([0.1, 0.8, 0.9, 0.2, 0.0], rel_mask) == pytest.approx(0.5)
    assert vnt.precision_at_k(perfect_scores, rel_mask, k=2) == pytest.approx(1.0)
    assert vnt.recall_at_k(perfect_scores, rel_mask, k=1) == pytest.approx(0.5)
    assert vnt.spearman_rank_correlation(perfect_scores, true_rel) >= 0.9
    assert vnt.brier_score([0.9, 0.1], [1.0, 0.0]) == pytest.approx(0.01)


def test_drill_recommender_hybrid_ranking_and_evaluation():
    drills = [
        vnt.DrillCandidate("d_3bet_bb", "facing_3bet", "BB", "preflop", 8.5, ("3bet", "oop", "defense")),
        vnt.DrillCandidate("d_cbet_btn", "cbet_defense", "BTN", "flop", 5.0, ("cbet", "ip", "float")),
        vnt.DrillCandidate("d_river_bc", "river_bluff_catch", "BB", "river", 9.0, ("river", "bluffcatch")),
        vnt.DrillCandidate("d_turn_brl", "turn_barrel", "CO", "turn", 6.0, ("turn", "aggression")),
    ]
    rec = vnt.DrillRecommender(drills)
    leak = vnt.LeakProfile(
        category_ev_loss={"river_bluff_catch": 14.0, "facing_3bet": 9.0, "cbet_defense": 1.0},
        position_ev_loss={"BB": 10.0, "BTN": 1.0},
        street_ev_loss={"river": 11.0, "preflop": 6.0},
        recent_drill_counts={"d_cbet_btn": 4},
        query_terms=("river", "bluffcatch", "bb"),
    )
    ranked = rec.rank(leak, top_k=3)
    assert ranked[0][0].drill_id == "d_river_bc"
    assert ranked[1][0].drill_id == "d_3bet_bb"

    eval_metrics = vnt.evaluate_drill_recommender(
        rec,
        queries=[(leak, [7.5, 1.0, 10.0, 2.0])],
        k=2,
    )
    assert eval_metrics["ndcg@2"] == pytest.approx(1.0)
    assert eval_metrics["mrr"] == pytest.approx(1.0)


def test_ab_policy_test_with_control_variates():
    rng = np.random.default_rng(42)
    luck = rng.normal(0.0, 50.0, size=500)
    a = 8.0 + luck + rng.normal(0.0, 5.0, size=500)
    b = 0.0 + luck + rng.normal(0.0, 5.0, size=500)

    res = vnt.ab_policy_test(a, b, control_variates_a=luck, control_variates_b=luck)
    assert res["delta_mean"] == pytest.approx(8.0, abs=1.5)
    assert res["significant_95"] is True
    assert res["variance_reduction_ratio"] > 10.0
