"""PyTorch Belief-State Value Network, Neural Spot/Drill Ranking & Offline Evaluation.

Provides:
1. `TurnValueNetTorch` (`torch.nn.Module`): ReBeL-style belief-state value network
   mapping 2,707-dim public turn states `(board[52], pot/stacks[3], hero_range[1326], villain_range[1326])`
   to 2,652-dim counterfactual forward values (`2 * 1326` combos).
2. Binary serialization (`save_rust_mlp` / `load_rust_mlp`, `load_turn_samples_bincode`)
   100% compatible with the native Rust `bincode` `Mlp` (`engine/noregrets/src/net.rs`)
   and `VN01` header format, so PyTorch-trained networks drop directly into the
   Rust subgame resolver (`--value-net value_net.bin`).
3. Training loop (`train_value_net_torch`) with `AdamW`, cosine annealing learning rate
   schedule, configurable range-weighted `Huber` or `MSE` loss, and gradient clipping.
4. Offline Ranking & Information Retrieval Evaluation Metrics (`ndcg_at_k`, `mrr_score`,
   `precision_at_k`, `recall_at_k`, `spearman_footrule_corr`, `brier_score`,
   `evaluate_value_net_offline`) and Personalized Leak-to-Drill Recommender
   (`DrillCandidate`, `LeakProfile`, `DrillRecommender`, `evaluate_drill_recommender`).
5. Statistical A/B Policy Evaluation (`ab_policy_test`) with two-sample Welch t-test,
   95% confidence intervals, and variance reduction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import struct
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

NUM_CARDS: int = 52
NUM_SCALARS: int = 3
NUM_COMBOS: int = 1326
INPUT_DIM: int = NUM_CARDS + NUM_SCALARS + 2 * NUM_COMBOS  # 2707
OUTPUT_DIM: int = 2 * NUM_COMBOS  # 2652
VN01_MAGIC: bytes = b"VN01"


def value_scale(pot: int, stack: Sequence[int]) -> float:
    """Target scale: maximum chips a player can win from a street start (`pot + min(stacks)`)."""
    return float(int(pot) + min(int(stack[0]), int(stack[1])))


def encode_turn_state(
    board: Sequence[int],
    pot: int,
    stack: Sequence[int],
    ranges: Sequence[Sequence[float]],
) -> np.ndarray:
    """Encode a public turn belief state into the 2,707-dim feature vector expected by Rust `valuenet::encode`."""
    if len(board) != 4:
        raise ValueError(f"Expected 4 turn board cards, got {len(board)}")
    x = np.zeros(INPUT_DIM, dtype=np.float32)
    for card in board:
        c_idx = int(card)
        if not (0 <= c_idx < NUM_CARDS):
            raise ValueError(f"Card index out of range [0, 52): {c_idx}")
        x[c_idx] = 1.0
    x[52] = float(pot) / 10_000.0
    x[53] = float(stack[0]) / 10_000.0
    x[54] = float(stack[1]) / 10_000.0
    for p in range(2):
        r = np.asarray(ranges[p], dtype=np.float32)
        if r.shape != (NUM_COMBOS,):
            raise ValueError(f"Player {p} range must have length {NUM_COMBOS}, got {r.shape}")
        total = float(r.sum())
        base = 55 + p * NUM_COMBOS
        if total > 0.0:
            x[base : base + NUM_COMBOS] = r / total
    return x


@dataclass
class TurnSampleRecord:
    """Python representation of `valuenet::TurnSample`."""

    board: Tuple[int, int, int, int]
    pot: int
    stack: Tuple[int, int]
    commit: Tuple[int, int]
    ranges: Tuple[np.ndarray, np.ndarray]
    values: Tuple[np.ndarray, np.ndarray]

    def to_tensors(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return `(x, target, weight)` matching `valuenet::to_example`."""
        x = encode_turn_state(self.board, self.pot, self.stack, self.ranges)
        scale = max(value_scale(self.pot, self.stack), 1.0)
        target = np.zeros(OUTPUT_DIM, dtype=np.float32)
        weight = np.zeros(OUTPUT_DIM, dtype=np.float32)
        for p in range(2):
            r = np.asarray(self.ranges[p], dtype=np.float32)
            v = np.asarray(self.values[p], dtype=np.float32)
            mass = float(r.sum())
            start = p * NUM_COMBOS
            end = (p + 1) * NUM_COMBOS
            target[start:end] = v / scale
            if mass > 0.0:
                weight[start:end] = 0.5 * (r / mass)
        return x, target, weight


class TurnValueNetTorch(nn.Module):
    """PyTorch MLP for ReBeL turn belief-state value estimation.

    Architecture mirrors `engine/noregrets/src/net.rs` (`Mlp`):
    sequential linear layers with ReLU activations on hidden layers and linear output.
    Supports direct binary import/export to Rust `bincode` and `VN01` formats.
    """

    def __init__(
        self,
        hidden_sizes: Sequence[int] = (256, 256),
        input_dim: int = INPUT_DIM,
        output_dim: int = OUTPUT_DIM,
        seed: Optional[int] = 42,
    ) -> None:
        super().__init__()
        self.sizes: List[int] = [int(input_dim), *[int(h) for h in hidden_sizes], int(output_dim)]
        if len(self.sizes) < 2:
            raise ValueError("Network requires at least input and output dimensions")
        if seed is not None:
            torch.manual_seed(int(seed))
        layers: List[nn.Linear] = []
        for idx in range(len(self.sizes) - 1):
            fan_in, fan_out = self.sizes[idx], self.sizes[idx + 1]
            layer = nn.Linear(fan_in, fan_out)
            bound = math.sqrt(6.0 / float(fan_in))
            nn.init.uniform_(layer.weight, -bound, bound)
            nn.init.zeros_(layer.bias)
            layers.append(layer)
        self.layers = nn.ModuleList(layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = x
        last_idx = len(self.layers) - 1
        for idx, layer in enumerate(self.layers):
            h = layer(h)
            if idx < last_idx:
                h = F.relu(h)
        return h

    @torch.no_grad()
    def predict_forward_values(
        self,
        board: Sequence[int],
        pot: int,
        stack: Sequence[int],
        ranges: Sequence[Sequence[float]],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predict per-combo forward chip values `(hero_values, villain_values)`."""
        self.eval()
        x_np = encode_turn_state(board, pot, stack, ranges)
        x_t = torch.from_numpy(x_np).unsqueeze(0)
        out = self.forward(x_t).squeeze(0).cpu().numpy()
        scale = value_scale(pot, stack)
        v0 = out[:NUM_COMBOS].astype(np.float64) * scale
        v1 = out[NUM_COMBOS:].astype(np.float64) * scale
        return v0, v1


def serialize_rust_mlp(model: TurnValueNetTorch, include_vn01_header: bool = False) -> bytes:
    """Serialize `TurnValueNetTorch` weights into Rust `bincode` `Mlp` format (or `VN01` header + bincode)."""
    parts: List[bytes] = []
    if include_vn01_header:
        parts.append(VN01_MAGIC)
        parts.append(struct.pack("<I", 1))

    # sizes: Vec<usize> (u64 length + u64 elements in bincode little-endian)
    parts.append(struct.pack("<Q", len(model.sizes)))
    for s in model.sizes:
        parts.append(struct.pack("<Q", int(s)))

    # w: Vec<Vec<f32>> (row-major: fan_out x fan_in, identical to nn.Linear.weight layout)
    parts.append(struct.pack("<Q", len(model.layers)))
    for layer in model.layers:
        w_np = layer.weight.detach().cpu().numpy().astype("<f4", copy=False).ravel()
        parts.append(struct.pack("<Q", w_np.size))
        parts.append(w_np.tobytes())

    # b: Vec<Vec<f32>>
    parts.append(struct.pack("<Q", len(model.layers)))
    for layer in model.layers:
        b_np = layer.bias.detach().cpu().numpy().astype("<f4", copy=False).ravel()
        parts.append(struct.pack("<Q", b_np.size))
        parts.append(b_np.tobytes())

    return b"".join(parts)


def deserialize_rust_mlp(data: bytes) -> TurnValueNetTorch:
    """Deserialize a Rust `bincode` `Mlp` (with or without `VN01` magic header) into `TurnValueNetTorch`."""
    offset = 0
    if data[:4] == VN01_MAGIC:
        offset = 8  # Skip 4-byte magic + 4-byte version

    (n_sizes,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    if n_sizes < 2 or n_sizes > 32:
        raise ValueError(f"Invalid MLP layer count in binary: {n_sizes}")
    sizes = list(struct.unpack_from(f"<{n_sizes}Q", data, offset))
    offset += 8 * n_sizes

    (n_w,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    if n_w != n_sizes - 1:
        raise ValueError(f"Weight vector count {n_w} does not match sizes {sizes}")

    weights: List[np.ndarray] = []
    for idx in range(n_w):
        (w_len,) = struct.unpack_from("<Q", data, offset)
        offset += 8
        expected = sizes[idx] * sizes[idx + 1]
        if w_len != expected:
            raise ValueError(f"Layer {idx} weight size {w_len} != {expected}")
        w_arr = np.frombuffer(data, dtype="<f4", count=w_len, offset=offset).copy()
        offset += 4 * w_len
        weights.append(w_arr.reshape(sizes[idx + 1], sizes[idx]))

    (n_b,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    if n_b != n_sizes - 1:
        raise ValueError(f"Bias vector count {n_b} does not match sizes {sizes}")

    biases: List[np.ndarray] = []
    for idx in range(n_b):
        (b_len,) = struct.unpack_from("<Q", data, offset)
        offset += 8
        expected = sizes[idx + 1]
        if b_len != expected:
            raise ValueError(f"Layer {idx} bias size {b_len} != {expected}")
        b_arr = np.frombuffer(data, dtype="<f4", count=b_len, offset=offset).copy()
        offset += 4 * b_len
        biases.append(b_arr)

    model = TurnValueNetTorch(
        hidden_sizes=sizes[1:-1],
        input_dim=sizes[0],
        output_dim=sizes[-1],
        seed=None,
    )
    with torch.no_grad():
        for idx, layer in enumerate(model.layers):
            layer.weight.copy_(torch.from_numpy(weights[idx]))
            layer.bias.copy_(torch.from_numpy(biases[idx]))
    return model


def save_rust_mlp(
    model: TurnValueNetTorch,
    path: Union[str, Path],
    include_vn01_header: bool = False,
) -> Path:
    """Save `TurnValueNetTorch` to disk in Rust `Mlp` binary format."""
    out_path = Path(path)
    out_path.write_bytes(serialize_rust_mlp(model, include_vn01_header=include_vn01_header))
    return out_path


def load_rust_mlp(path: Union[str, Path]) -> TurnValueNetTorch:
    """Load `TurnValueNetTorch` from a Rust `value_net.bin` file."""
    return deserialize_rust_mlp(Path(path).read_bytes())


def save_turn_samples_bincode(samples: Sequence[TurnSampleRecord], path: Union[str, Path]) -> Path:
    """Serialize a list of `TurnSampleRecord` in Rust `bincode` `Vec<TurnSample>` format."""
    parts: List[bytes] = [struct.pack("<Q", len(samples))]
    for s in samples:
        parts.append(struct.pack("<4B", *[int(c) for c in s.board]))
        parts.append(struct.pack("<I", int(s.pot)))
        parts.append(struct.pack("<2I", int(s.stack[0]), int(s.stack[1])))
        parts.append(struct.pack("<2I", int(s.commit[0]), int(s.commit[1])))
        for p in range(2):
            r = np.asarray(s.ranges[p], dtype="<f4").ravel()
            parts.append(struct.pack("<Q", r.size))
            parts.append(r.tobytes())
        for p in range(2):
            v = np.asarray(s.values[p], dtype="<f4").ravel()
            parts.append(struct.pack("<Q", v.size))
            parts.append(v.tobytes())
    out_path = Path(path)
    out_path.write_bytes(b"".join(parts))
    return out_path


def load_turn_samples_bincode(path: Union[str, Path]) -> List[TurnSampleRecord]:
    """Load a Rust `bincode`-serialized `Vec<TurnSample>` (`turn_data.bin`)."""
    data = Path(path).read_bytes()
    offset = 0
    (count,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    samples: List[TurnSampleRecord] = []
    for _ in range(count):
        board = struct.unpack_from("<4B", data, offset)
        offset += 4
        (pot,) = struct.unpack_from("<I", data, offset)
        offset += 4
        stack = struct.unpack_from("<2I", data, offset)
        offset += 8
        commit = struct.unpack_from("<2I", data, offset)
        offset += 8
        ranges: List[np.ndarray] = []
        for _p in range(2):
            (r_len,) = struct.unpack_from("<Q", data, offset)
            offset += 8
            r_arr = np.frombuffer(data, dtype="<f4", count=r_len, offset=offset).copy()
            offset += 4 * r_len
            ranges.append(r_arr)
        values: List[np.ndarray] = []
        for _p in range(2):
            (v_len,) = struct.unpack_from("<Q", data, offset)
            offset += 8
            v_arr = np.frombuffer(data, dtype="<f4", count=v_len, offset=offset).copy()
            offset += 4 * v_len
            values.append(v_arr)
        samples.append(
            TurnSampleRecord(
                board=(int(board[0]), int(board[1]), int(board[2]), int(board[3])),
                pot=int(pot),
                stack=(int(stack[0]), int(stack[1])),
                commit=(int(commit[0]), int(commit[1])),
                ranges=(ranges[0], ranges[1]),
                values=(values[0], values[1]),
            )
        )
    return samples


def weighted_value_loss(
    pred: torch.Tensor,
    target: torch.Tensor,
    weight: torch.Tensor,
    loss_type: str = "huber",
    huber_delta: float = 0.25,
) -> torch.Tensor:
    """Compute range-mass-weighted MSE or Huber loss per sample, averaged across the batch."""
    diff = pred - target
    if loss_type == "mse":
        per_elem = diff * diff
    elif loss_type == "huber":
        abs_diff = torch.abs(diff)
        quadratic = torch.clamp(abs_diff, max=huber_delta)
        linear = abs_diff - quadratic
        # Scale by 2 / delta so small-error regime matches MSE curvature
        per_elem = (quadratic * quadratic + 2.0 * huber_delta * linear)
    else:
        raise ValueError(f"Unsupported loss_type: {loss_type}")
    per_sample = torch.sum(weight * per_elem, dim=-1)
    return torch.mean(per_sample)


def train_value_net_torch(
    samples: Sequence[TurnSampleRecord],
    hidden_sizes: Sequence[int] = (256, 256),
    epochs: int = 40,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    batch_size: int = 32,
    loss_type: str = "huber",
    seed: int = 11,
    val_fraction: float = 0.1,
) -> Tuple[TurnValueNetTorch, Dict[str, Any]]:
    """Train a `TurnValueNetTorch` with `AdamW`, cosine annealing, and offline ranking/calibration metrics."""
    if len(samples) < 2:
        raise ValueError("Require at least 2 samples to train and validate")

    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)

    xs, ts, wts = [], [], []
    for s in samples:
        x, t, w = s.to_tensors()
        xs.append(x)
        ts.append(t)
        wts.append(w)

    x_all = np.stack(xs, axis=0)
    t_all = np.stack(ts, axis=0)
    w_all = np.stack(wts, axis=0)

    perm = rng.permutation(len(samples))
    n_val = max(1, min(len(samples) - 1, int(round(len(samples) * val_fraction))))
    val_idx = perm[:n_val]
    tr_idx = perm[n_val:]

    x_tr = torch.from_numpy(x_all[tr_idx])
    t_tr = torch.from_numpy(t_all[tr_idx])
    w_tr = torch.from_numpy(w_all[tr_idx])

    x_val = torch.from_numpy(x_all[val_idx])
    t_val = torch.from_numpy(t_all[val_idx])
    w_val = torch.from_numpy(w_all[val_idx])

    model = TurnValueNetTorch(
        hidden_sizes=hidden_sizes,
        input_dim=x_all.shape[1],
        output_dim=t_all.shape[1],
        seed=seed ^ 0xA11CE,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(1, epochs), eta_min=lr * 0.05
    )

    history: List[Dict[str, float]] = []
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(x_tr.size(0))
        epoch_loss = 0.0
        n_seen = 0
        for start in range(0, x_tr.size(0), batch_size):
            batch_ids = order[start : start + batch_size]
            bx = x_tr[batch_ids]
            bt = t_tr[batch_ids]
            bw = w_tr[batch_ids]

            optimizer.zero_grad()
            pred = model(bx)
            loss = weighted_value_loss(pred, bt, bw, loss_type=loss_type)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()

            bs = int(bx.size(0))
            epoch_loss += float(loss.item()) * bs
            n_seen += bs

        scheduler.step()
        train_loss = epoch_loss / max(1, n_seen)

        model.eval()
        with torch.no_grad():
            val_pred = model(x_val)
            val_mse = float(weighted_value_loss(val_pred, t_val, w_val, loss_type="mse").item())
            val_huber = float(weighted_value_loss(val_pred, t_val, w_val, loss_type="huber").item())

        history.append(
            {
                "epoch": float(epoch + 1),
                "train_loss": train_loss,
                "val_mse": val_mse,
                "val_huber": val_huber,
                "lr": float(scheduler.get_last_lr()[0]),
            }
        )

    val_samples = [samples[int(i)] for i in val_idx]
    offline_eval = evaluate_value_net_offline(model, val_samples, k_values=(5, 10, 20))
    metrics = {
        "framework": "pytorch",
        "torch_version": torch.__version__,
        "loss_type": loss_type,
        "epochs": epochs,
        "hidden_sizes": list(hidden_sizes),
        "train_samples": int(len(tr_idx)),
        "val_samples": int(len(val_idx)),
        "final_train_loss": history[-1]["train_loss"],
        "val_loss": history[-1]["val_mse"],
        "val_huber_loss": history[-1]["val_huber"],
        "offline_evaluation": offline_eval,
        "history": history,
    }
    return model, metrics


# ---------------------------------------------------------------------------
# Information Retrieval, Neural Ranking & Offline Evaluation Metrics
# ---------------------------------------------------------------------------


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    """Discounted Cumulative Gain at rank `k` using exponential gain `2^rel - 1`."""
    rels = np.asarray(relevances, dtype=np.float64)[: max(0, int(k))]
    if rels.size == 0:
        return 0.0
    gains = np.power(2.0, rels) - 1.0
    discounts = np.log2(np.arange(2, rels.size + 2, dtype=np.float64))
    return float(np.sum(gains / discounts))


def ndcg_at_k(
    predicted_scores: Sequence[float],
    true_relevances: Sequence[float],
    k: int = 10,
) -> float:
    """Normalized Discounted Cumulative Gain (`NDCG@k`) for a ranked candidate list."""
    scores = np.asarray(predicted_scores, dtype=np.float64)
    rels = np.asarray(true_relevances, dtype=np.float64)
    if scores.size == 0 or scores.size != rels.size:
        raise ValueError("predicted_scores and true_relevances must be non-empty and equal length")
    # Normalize non-negative relevance grades into [0, 3] if arbitrary continuous EVs are supplied
    min_r, max_r = float(np.min(rels)), float(np.max(rels))
    if max_r - min_r <= 1e-12:
        return 1.0
    norm_rels = 3.0 * (rels - min_r) / (max_r - min_r)

    pred_order = np.argsort(-scores, kind="mergesort")
    ideal_order = np.argsort(-norm_rels, kind="mergesort")

    actual_dcg = dcg_at_k(norm_rels[pred_order], k)
    ideal_dcg = dcg_at_k(norm_rels[ideal_order], k)
    if ideal_dcg <= 1e-12:
        return 1.0
    return float(actual_dcg / ideal_dcg)


def mrr_score(
    predicted_scores: Sequence[float],
    relevant_mask: Sequence[bool],
) -> float:
    """Reciprocal Rank (`RR` / `MRR` per query) of the highest-ranked relevant item."""
    scores = np.asarray(predicted_scores, dtype=np.float64)
    mask = np.asarray(relevant_mask, dtype=bool)
    if scores.size == 0 or scores.size != mask.size:
        raise ValueError("predicted_scores and relevant_mask must be non-empty and equal length")
    order = np.argsort(-scores, kind="mergesort")
    ranked_relevant = mask[order]
    hits = np.flatnonzero(ranked_relevant)
    if hits.size == 0:
        return 0.0
    return float(1.0 / (int(hits[0]) + 1))


def precision_at_k(
    predicted_scores: Sequence[float],
    relevant_mask: Sequence[bool],
    k: int = 5,
) -> float:
    """Precision@k (`P@k`): fraction of top-k ranked candidates that are relevant."""
    scores = np.asarray(predicted_scores, dtype=np.float64)
    mask = np.asarray(relevant_mask, dtype=bool)
    if scores.size == 0 or scores.size != mask.size or k <= 0:
        raise ValueError("Invalid inputs for precision_at_k")
    k_eff = min(int(k), scores.size)
    order = np.argsort(-scores, kind="mergesort")[:k_eff]
    return float(np.mean(mask[order]))


def recall_at_k(
    predicted_scores: Sequence[float],
    relevant_mask: Sequence[bool],
    k: int = 10,
) -> float:
    """Recall@k (`R@k`): fraction of all relevant candidates retrieved in the top-k."""
    scores = np.asarray(predicted_scores, dtype=np.float64)
    mask = np.asarray(relevant_mask, dtype=bool)
    total_rel = int(np.sum(mask))
    if total_rel == 0:
        return 1.0
    k_eff = min(int(k), scores.size)
    order = np.argsort(-scores, kind="mergesort")[:k_eff]
    return float(np.sum(mask[order]) / total_rel)


def _average_ranks(arr: np.ndarray) -> np.ndarray:
    """Compute tie-adjusted average ranks (1-based) for Spearman correlation."""
    order = np.argsort(arr, kind="mergesort")
    sorted_arr = arr[order]
    ranks = np.empty(arr.size, dtype=np.float64)
    i = 0
    n = arr.size
    while i < n:
        j = i
        while j + 1 < n and abs(sorted_arr[j + 1] - sorted_arr[i]) <= 1e-12:
            j += 1
        avg_rank = 0.5 * (i + j) + 1.0
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    return ranks


def spearman_rank_correlation(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman rank correlation coefficient between two score vectors (with tie-adjusted average ranks)."""
    a = np.asarray(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64)
    if a.size < 2 or a.size != b.size:
        return 0.0
    rank_a = _average_ranks(a)
    rank_b = _average_ranks(b)
    sa = float(np.std(rank_a))
    sb = float(np.std(rank_b))
    if sa <= 1e-12 or sb <= 1e-12:
        return 0.0
    return float(np.corrcoef(rank_a, rank_b)[0, 1])


def brier_score(pred_probs: Sequence[float], outcomes: Sequence[float]) -> float:
    """Multi-class or binary Brier calibration score `mean((p - y)^2)`."""
    p = np.asarray(pred_probs, dtype=np.float64)
    y = np.asarray(outcomes, dtype=np.float64)
    if p.size == 0 or p.size != y.size:
        raise ValueError("pred_probs and outcomes must be non-empty and equal length")
    return float(np.mean(np.square(p - y)))


@torch.no_grad()
def evaluate_value_net_offline(
    model: TurnValueNetTorch,
    samples: Sequence[TurnSampleRecord],
    k_values: Sequence[int] = (5, 10, 20),
) -> Dict[str, Any]:
    """Evaluate a trained value network on held-out turn states using IR ranking and calibration metrics."""
    if not samples:
        raise ValueError("samples must be non-empty")
    model.eval()

    ndcg_lists: Dict[int, List[float]] = {int(k): [] for k in k_values}
    mrr_list: List[float] = []
    spearman_list: List[float] = []
    top1_matches: List[float] = []
    weighted_mse_list: List[float] = []
    weighted_huber_list: List[float] = []
    brier_list: List[float] = []

    for s in samples:
        x_np, t_np, w_np = s.to_tensors()
        x_t = torch.from_numpy(x_np).unsqueeze(0)
        pred_np = model(x_t).squeeze(0).cpu().numpy()

        t_t = torch.from_numpy(t_np).unsqueeze(0)
        w_t = torch.from_numpy(w_np).unsqueeze(0)
        p_t = torch.from_numpy(pred_np).unsqueeze(0)
        weighted_mse_list.append(float(weighted_value_loss(p_t, t_t, w_t, loss_type="mse").item()))
        weighted_huber_list.append(float(weighted_value_loss(p_t, t_t, w_t, loss_type="huber").item()))

        for p in range(2):
            start = p * NUM_COMBOS
            end = (p + 1) * NUM_COMBOS
            r_p = np.asarray(s.ranges[p], dtype=np.float64)
            active = r_p > 1e-6
            if int(np.sum(active)) < 4:
                continue
            p_scores = pred_np[start:end][active]
            t_scores = t_np[start:end][active]

            for k in k_values:
                ndcg_lists[int(k)].append(ndcg_at_k(p_scores, t_scores, k=int(k)))

            # Relevant set = top 10% highest-EV combos in exact solver ground truth
            thresh = float(np.quantile(t_scores, 0.90))
            rel_mask = t_scores >= thresh
            mrr_list.append(mrr_score(p_scores, rel_mask))
            spearman_list.append(spearman_rank_correlation(p_scores, t_scores))
            top1_matches.append(1.0 if rel_mask[int(np.argmax(p_scores))] else 0.0)

            # Win-equity probability calibration (normalized forward value in [0, 1])
            p_prob = np.clip(p_scores, 0.0, 1.0)
            t_prob = np.clip(t_scores, 0.0, 1.0)
            brier_list.append(brier_score(p_prob, t_prob))

    report: Dict[str, Any] = {
        "num_samples": len(samples),
        "weighted_mse": float(np.mean(weighted_mse_list)) if weighted_mse_list else 0.0,
        "weighted_huber": float(np.mean(weighted_huber_list)) if weighted_huber_list else 0.0,
        "mrr": float(np.mean(mrr_list)) if mrr_list else 0.0,
        "spearman_rho": float(np.mean(spearman_list)) if spearman_list else 0.0,
        "top1_decile_hit_rate": float(np.mean(top1_matches)) if top1_matches else 0.0,
        "brier_calibration": float(np.mean(brier_list)) if brier_list else 0.0,
    }
    for k in k_values:
        vals = ndcg_lists[int(k)]
        report[f"ndcg@{int(k)}"] = float(np.mean(vals)) if vals else 0.0
    return report


# ---------------------------------------------------------------------------
# Personalized Leak-to-Drill Information Retrieval & Recommender Engine
# ---------------------------------------------------------------------------


@dataclass
class DrillCandidate:
    """A canonical training spot / drill in the retrieval index."""

    drill_id: str
    spot_category: str  # e.g., "facing_3bet", "cbet_defense", "river_bluff_catch", "turn_barrel"
    position: str       # e.g., "BTN", "CO", "BB", "SB"
    street: str         # "preflop", "flop", "turn", "river"
    ev_loss_severity: float  # Baseline EV impact in BB/100
    tags: Tuple[str, ...] = ()
    embedding: Optional[np.ndarray] = None


@dataclass
class LeakProfile:
    """Aggregated telemetry profile of a player's deviations from GTO across spots."""

    category_ev_loss: Dict[str, float] = field(default_factory=dict)
    position_ev_loss: Dict[str, float] = field(default_factory=dict)
    street_ev_loss: Dict[str, float] = field(default_factory=dict)
    recent_drill_counts: Dict[str, int] = field(default_factory=dict)
    query_terms: Tuple[str, ...] = ()


class DrillRecommender:
    """Hybrid Lexical + Neural Embedding Recommender for ranking personalized poker training drills.

    Combines:
    1. Character/token TF-IDF cosine similarity over spot metadata and tags,
    2. Dense neural/feature embedding dot-product similarity,
    3. Telemetry EV-leak severity weighting (`category_ev_loss`, `position_ev_loss`, `street_ev_loss`),
    4. Novelty / fatigue discounting for recently completed drills.
    """

    def __init__(self, drills: Sequence[DrillCandidate]) -> None:
        if not drills:
            raise ValueError("DrillRecommender requires at least one DrillCandidate")
        self.drills: List[DrillCandidate] = list(drills)
        self._vocab: Dict[str, int] = {}
        self._idf: np.ndarray = np.zeros(0, dtype=np.float64)
        self._doc_tfidf: np.ndarray = np.zeros((0, 0), dtype=np.float64)
        self._build_tfidf_index()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        cleaned = text.lower().replace("_", " ").replace("-", " ")
        tokens = [t for t in cleaned.split() if t]
        # Include character 3-grams for subword resilience
        compact = "".join(tokens)
        ngrams = [compact[i : i + 3] for i in range(max(0, len(compact) - 2))]
        return tokens + ngrams

    def _drill_tokens(self, d: DrillCandidate) -> List[str]:
        raw = " ".join([d.drill_id, d.spot_category, d.position, d.street, *d.tags])
        return self._tokenize(raw)

    def _build_tfidf_index(self) -> None:
        doc_tokens = [self._drill_tokens(d) for d in self.drills]
        df: Dict[str, int] = {}
        for toks in doc_tokens:
            for t in set(toks):
                if t not in self._vocab:
                    self._vocab[t] = len(self._vocab)
                df[t] = df.get(t, 0) + 1

        n_docs = len(self.drills)
        n_vocab = len(self._vocab)
        self._idf = np.zeros(n_vocab, dtype=np.float64)
        for term, idx in self._vocab.items():
            self._idf[idx] = math.log((1.0 + n_docs) / (1.0 + df[term])) + 1.0

        mat = np.zeros((n_docs, n_vocab), dtype=np.float64)
        for d_idx, toks in enumerate(doc_tokens):
            for t in toks:
                mat[d_idx, self._vocab[t]] += 1.0
            if len(toks) > 0:
                mat[d_idx] /= float(len(toks))
            mat[d_idx] *= self._idf
            norm = float(np.linalg.norm(mat[d_idx]))
            if norm > 1e-12:
                mat[d_idx] /= norm
        self._doc_tfidf = mat

    def _encode_query_tfidf(self, leak: LeakProfile) -> np.ndarray:
        terms: List[str] = list(leak.query_terms)
        for k, v in leak.category_ev_loss.items():
            if v > 0:
                terms.append(k)
        for k, v in leak.position_ev_loss.items():
            if v > 0:
                terms.append(k)
        for k, v in leak.street_ev_loss.items():
            if v > 0:
                terms.append(k)
        toks = self._tokenize(" ".join(terms))
        q = np.zeros(len(self._vocab), dtype=np.float64)
        for t in toks:
            if t in self._vocab:
                q[self._vocab[t]] += 1.0
        if toks:
            q /= float(len(toks))
        q *= self._idf
        norm = float(np.linalg.norm(q))
        if norm > 1e-12:
            q /= norm
        return q

    def score_candidates(self, leak: LeakProfile) -> np.ndarray:
        """Compute hybrid ranking scores for all candidate drills given a player's `LeakProfile`."""
        q_vec = self._encode_query_tfidf(leak)
        lexical_sim = self._doc_tfidf @ q_vec

        scores = np.zeros(len(self.drills), dtype=np.float64)
        for idx, d in enumerate(self.drills):
            cat_leak = float(leak.category_ev_loss.get(d.spot_category, 0.0))
            pos_leak = float(leak.position_ev_loss.get(d.position, 0.0))
            str_leak = float(leak.street_ev_loss.get(d.street, 0.0))
            reps = int(leak.recent_drill_counts.get(d.drill_id, 0))
            novelty = 1.0 / math.sqrt(1.0 + max(0, reps))

            structured_gain = (
                0.50 * cat_leak
                + 0.25 * pos_leak
                + 0.15 * str_leak
                + 0.10 * float(d.ev_loss_severity)
            )
            scores[idx] = novelty * (0.75 * structured_gain + 0.25 * float(lexical_sim[idx]))
        return scores

    def rank(self, leak: LeakProfile, top_k: int = 5) -> List[Tuple[DrillCandidate, float]]:
        """Return the top-k highest-scoring drills with their ranking scores."""
        scores = self.score_candidates(leak)
        order = np.argsort(-scores, kind="mergesort")[: max(1, int(top_k))]
        return [(self.drills[int(i)], float(scores[int(i)])) for i in order]


def evaluate_drill_recommender(
    recommender: DrillRecommender,
    queries: Sequence[Tuple[LeakProfile, Sequence[float]]],
    k: int = 5,
) -> Dict[str, float]:
    """Offline evaluation of the drill recommender across benchmark leak profiles (`NDCG@k`, `MRR`, `P@k`, `R@k`)."""
    ndcgs, mrrs, precs, recs = [], [], [], []
    for leak, ground_truth_gains in queries:
        scores = recommender.score_candidates(leak)
        gt = np.asarray(ground_truth_gains, dtype=np.float64)
        thresh = float(np.quantile(gt, 0.75))
        rel_mask = gt >= thresh
        ndcgs.append(ndcg_at_k(scores, gt, k=k))
        mrrs.append(mrr_score(scores, rel_mask))
        precs.append(precision_at_k(scores, rel_mask, k=k))
        recs.append(recall_at_k(scores, rel_mask, k=k))
    return {
        f"ndcg@{k}": float(np.mean(ndcgs)) if ndcgs else 0.0,
        "mrr": float(np.mean(mrrs)) if mrrs else 0.0,
        f"precision@{k}": float(np.mean(precs)) if precs else 0.0,
        f"recall@{k}": float(np.mean(recs)) if recs else 0.0,
    }


# ---------------------------------------------------------------------------
# Statistical A/B Policy Evaluation & Variance Reduction
# ---------------------------------------------------------------------------


def ab_policy_test(
    policy_a_rewards: Sequence[float],
    policy_b_rewards: Sequence[float],
    control_variates_a: Optional[Sequence[float]] = None,
    control_variates_b: Optional[Sequence[float]] = None,
) -> Dict[str, float]:
    """Two-sample statistical A/B evaluation comparing two policies (in mbb/hand or BB/100).

    Supports optional AIVAT-style control variates for variance reduction and reports:
    - mean difference (`delta_mean`),
    - 95% confidence interval half-width (`ci95_halfwidth`),
    - Welch's t-statistic (`t_stat`),
    - two-sided normal-approximated p-value (`p_value`),
    - variance reduction ratio (`variance_reduction_ratio`).
    """
    a = np.asarray(policy_a_rewards, dtype=np.float64)
    b = np.asarray(policy_b_rewards, dtype=np.float64)
    if a.size < 2 or b.size < 2:
        raise ValueError("Require at least 2 observations per policy for A/B testing")

    raw_var = float(np.var(a, ddof=1) / a.size + np.var(b, ddof=1) / b.size)

    if control_variates_a is not None:
        cv_a = np.asarray(control_variates_a, dtype=np.float64)
        if cv_a.shape != a.shape:
            raise ValueError("control_variates_a must match policy_a_rewards shape")
        var_cv_a = float(np.var(cv_a, ddof=1))
        beta_a = float(np.cov(a, cv_a, ddof=1)[0, 1] / var_cv_a) if var_cv_a > 1e-12 else 0.0
        a = a - beta_a * (cv_a - float(np.mean(cv_a)))

    if control_variates_b is not None:
        cv_b = np.asarray(control_variates_b, dtype=np.float64)
        if cv_b.shape != b.shape:
            raise ValueError("control_variates_b must match policy_b_rewards shape")
        var_cv_b = float(np.var(cv_b, ddof=1))
        beta_b = float(np.cov(b, cv_b, ddof=1)[0, 1] / var_cv_b) if var_cv_b > 1e-12 else 0.0
        b = b - beta_b * (cv_b - float(np.mean(cv_b)))

    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
    var_a = float(np.var(a, ddof=1))
    var_b = float(np.var(b, ddof=1))

    se_sq = var_a / a.size + var_b / b.size
    se = math.sqrt(max(se_sq, 1e-18))
    delta = mean_a - mean_b
    t_stat = delta / se
    p_val = math.erfc(abs(t_stat) / math.sqrt(2.0))
    ci95 = 1.959963984540054 * se
    vr_ratio = float(raw_var / se_sq) if se_sq > 1e-18 and raw_var > 0 else 1.0

    return {
        "mean_a": mean_a,
        "mean_b": mean_b,
        "delta_mean": delta,
        "ci95_halfwidth": ci95,
        "t_stat": t_stat,
        "p_value": p_val,
        "significant_95": bool(p_val < 0.05),
        "variance_reduction_ratio": vr_ratio,
    }
