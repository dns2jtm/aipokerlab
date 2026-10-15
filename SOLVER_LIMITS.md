# Solver Scope, Architecture, and Benchmarks

## 1. Dual-Solver Architecture (`engine/noregrets` + `showdown_solver.py`)

The project provides two complementary postflop/subgame solving layers:

1. **Native Rust 6-Max Linear MCCFR Blueprint & Online Subgame Resolver (`engine/noregrets` via `poker_lab.py`)**:
   - **Training (`ochs_vr` profile)**: Parallel Linear MCCFR with Pluribus negative-regret pruning, **OCHS** (Opponent-Cluster Hand Strength combined with 8-quantile future-equity distributions clustered via L1/EMD k-medians), **VR-MCCFR** (Schmid et al. 2019 control-variate baselines at sampled opponent nodes), **postflop snapshot averaging** (mean of 18 periodic strategy snapshots after 10% warm-up), and **multiway-focused importance sampling** (`--multiway-focus 0.15`).
   - **Online Subgame Resolving (`review` / `query_native_subgame` / `query_native_preflop`)**: Replays a chip-reconciled 6-max action history with Bayesian range tracking (`RangeTracker`), using ReBeL-style depth-limited vector solving with learned belief-state leaf values (`--value-net value_net.bin`) on the flop (`flop.rs`), exact range-vs-range vector CFR+ on the turn (`turn.rs` with safety gadget continual resolving), and exact range-vs-range vector CFR+ on the river (`river.rs`).
   - **Persistent Low-Latency Worker (`--stdio` / `_NativeReviewWorker`)**: Keeps the Rust `pluribus` process warm in memory with `blueprint.bin` and `value_net.bin` preloaded once at startup, serving newline-delimited JSON requests over `stdin`/`stdout` without per-query disk deserialization overhead.
   - **Live RTA Bridge (`table_context.py` / `postflop.py` / `rta.py`)**: `PreflopTracker` exports structured `action_history` events (`call`, `raise_to` with normalized BB/chip amounts), which `poker_lab.synthesize_review_request` reconciles onto the 50/100 (10,000 stack) grid before querying `poker_lab.query_native_subgame` or `poker_lab.query_native_preflop`, falling back automatically to the fast Python CFR+ solver whenever a state is off-tree or when running in lightweight default mode.

2. **Fast Python NumPy CFR+ Restricted Subgame Solver (`showdown_solver.py` & `postflop.solve_cfr_subgame`)**:
   - Solves a restricted heads-up single-round game with multi-sizing (`33%`, `66%`, `100%` pot), optional opponent reraise branch (`allow_opponent_reraise`), and IP/OOP equity-realization matrices.
   - River and turn equities are exact for each selected private-card pair; flop equity uses 96 reproducibly sampled 2-card runouts.
   - `solver_gap_chips` reports the exact two-player NashConv (sum of both players' best-response improvements) in the restricted game.

---

## 2. Trained Blueprint Models, ReBeL Value Net & Distillation Results

### Model Summary

| Model | Table Size | Profile | Iterations | Buckets | Infosets / Strategies | Notes |
|---|---:|---|---:|---:|---:|---|
| `smoke-v1` | 6-Max | `smoke` (raw equity) | 10,000 | 4 | ~1.2M | Fast smoke validation |
| `local-v1` | 6-Max | `local` (EMD k-means) | 1,000,000 | 12 | 9,627,290 | Baseline 6-max blueprint |
| `ochs-vr-v1` | 6-Max | `ochs_vr` (OCHS + VR-MCCFR + Snapshot-Avg + Multiway 0.15) | 2,000,000 | 16 | 15,956,290 | Includes trained ReBeL turn belief-state `value_net.bin` |
| `distilled-v1` | 6-Max | `distilled` (Expert-iteration distillation from `ochs-vr-v1` + `value_net.bin` + `--safe-resolve`) | 2,000,000 + self-play search | 16 | 15,956,290+ | Preferred default GTO model in `poker_lab.best_available_model()` |
| `rnr-caller-v1` | 6-Max | `rnr_caller` (Restricted Nash Response `--rnr-model caller --rnr-p 0.5` + OCHS + VR + Snapshot-Avg) | 500,000 | 12 | ~4.4M | Auto-selected by `select_model_for_opponent` when opponent VPIP ≥ 40% |
| `hu-v1` | 2-Max (HU) | `hu_ochs_vr` (`--players 2` + OCHS + VR-MCCFR + Snapshot-Avg) | 500,000 | 12 | ~300K | Dedicated 2-player Heads-Up blueprint (`GAME_HU`) |

### Duplicate & AIVAT Winrate Benchmarks (`local-v1`, `ochs-vr-v1`, `rnr-caller-v1`, `hu-v1`)

| Model | Table Size | Estimator | vs Random (BB/100) | vs Caller (BB/100) |
|---|---:|---|---:|---:|
| `local-v1` | 6-Max | Duplicate (3 seeds × 24,000 hands) | +696.5 ± 121.0 | +284.6 ± 101.4 |
| `ochs-vr-v1` | 6-Max | Duplicate (3 seeds × 24,000 hands) | +635.8 ± 116.3 | +185.6 ± 100.8 |
| `rnr-caller-v1` | 6-Max | Duplicate (3 seeds × 24,000 hands) | +572.1 ± 128.4 | **+5501.1 ± 82.9** |
| `hu-v1` | 2-Max (HU) | Duplicate (3 seeds × 24,000 hands) | +359.5 ± 49.5 | **+690.1 ± 52.3** |
| `local-v1` | 6-Max | AIVAT (seed 11, 6,000 hands) | +507.8 ± 154.0 | +202.0 ± 105.6 |
| `ochs-vr-v1` | 6-Max | AIVAT (seed 11, 6,000 hands) | +486.7 ± 147.6 | +209.7 ± 105.0 |
| `rnr-caller-v1` | 6-Max | AIVAT (seed 11, 6,000 hands) | +578.7 ± 162.4 | **+5346.5 ± 387.4** |
| `hu-v1` | 2-Max (HU) | AIVAT (seed 11, 6,000 hands) | +348.1 ± 99.7 | **+546.6 ± 86.1** |

### Exploitability Lower-Bound Probes (`br` Exact Turn/River Expectimax & `lbr`)

| Model | Table Size | `br` Probe (1,000 hands, 60 runouts) | `lbr` Probe (4,000 hands, 60 runouts) |
|---|---:|---:|---:|
| `local-v1` | 6-Max | 528.5 BB/100 (±357.1) | 427.0 BB/100 (±170.0) |
| `ochs-vr-v1` | 6-Max | **304.0 BB/100 (±306.6)** | **376.3 BB/100 (±158.7)** |
| `rnr-caller-v1` | 6-Max | 852.4 BB/100 (±446.5) | 1034.2 BB/100 (±220.4) |
| `hu-v1` | 2-Max (HU) | **114.3 BB/100 (±235.4)** | **148.4 BB/100 (±120.6)** |

*Note*: `ochs-vr-v1` reduces the exact turn/river best-response (`br`) exploitability lower bound by **42.5%** (`304.0` vs `528.5 BB/100`) and reduces the Local Best Response (`lbr`) bound by **11.9%** (`376.3` vs `427.0 BB/100`), while improving AIVAT winrate vs Caller (`+209.7` vs `+202.0 BB/100`) with narrower confidence intervals. All trained models remain experimental research artifacts (`strength: "unvalidated"`) and are not original Pluribus or proven against professional human players.

---

## 3. Head-to-Head 6-Max Cross-Play & Safety Ablation Benchmarks

### 6-Max Cross-Play (`pluribus crossplay`, 24,000 hands, seed 11)

Each matchup places the **Focal** model in 1 rotating seat against 5 seats of the **Field** model on the 6-max 100bb table (`research_runs/*/crossplay.json`):

| Focal Model (1 Rotating Seat) | Field Model (5 Seats) | Hands | Focal Winrate (BB/100) | 95% CI (BB/100) |
|---|---|---:|---:|---:|
| `distilled-v1` | `ochs-vr-v1` | 24,000 | **+26.75** | ±111.62 |
| `ochs-vr-v1` | `local-v1` | 24,000 | **+40.57** | ±116.78 |
| `distilled-v1` | `local-v1` | 24,000 | **+40.57** | ±116.78 |

### Burch Gadget Safe-Resolving Ablation (`pluribus ablate-safety`, 24 spots, 250 CFR iters/solve, seed 11)

Measures opponent best-response margin `(BR value − safety value)⁺` in chips when the subgame resolver's range belief is corrupted by noise level `ε` (`research_runs/distilled-v1/safety_ablation.json`):

| Noise `ε` | Unsafe Mean Margin (chips) | Unsafe Max Margin (chips) | Safe (Gadget) Mean Margin (chips) | Safe (Gadget) Max Margin (chips) | Mean Pot (chips) |
|---:|---:|---:|---:|---:|---:|
| `0.25` | 3.0 | 85.6 | **1.5** | **21.0** | 2,083 |
| `0.50` | 4.8 | 117.9 | **1.6** | **15.0** | 2,083 |
| `1.00` | 9.8 | 317.4 | **1.7** | **42.7** | 2,083 |

*Finding*: Under maximally corrupted range beliefs (`ε = 1.0`), unsafe resolving exposes up to **317.4 chips** (`9.8` chips mean) of best-response exploitation beyond the blueprint safety value, whereas Burch gadget safe-resolving bounds the mean margin to **1.7 chips** (`< 0.1%` of the pot) and cuts worst-case combo exploitation by **86.5%** (`42.7` vs `317.4` chips).

---

## 4. PyTorch Belief-State Value Network, IR Ranking & Offline Evaluation (`value_net_torch.py`)

- **PyTorch ReBeL Turn Belief-State Value Network (`TurnValueNetTorch`)**: Trains a multi-layer perceptron (`torch.nn.Module`, `AdamW`, cosine annealing LR schedule, range-weighted Huber/MSE loss, gradient clipping) mapping 2,707-dim public turn states (`52` board multi-hot + `3` pot/stack scalars + `2 × 1,326` Bayesian range beliefs) to `2,652` counterfactual forward values. Exports binary weights directly into the Rust `bincode` / `VN01` `value_net.bin` format (`save_rust_mlp` / `load_rust_mlp`).
- **Offline Ranking & Calibration Evaluation (`evaluate_value_net_offline`)**: Computes Normalized Discounted Cumulative Gain (`NDCG@5`, `NDCG@10`, `NDCG@20`), Mean Reciprocal Rank (`MRR`), Spearman rank correlation (`ρ`), top-decile EV hit rate, range-weighted Huber/MSE loss, and Brier calibration scores on held-out exactly solved turn subgames.
- **Personalized Leak-to-Drill Recommender (`DrillRecommender`)**: Hybrid lexical (token + character 3-gram TF-IDF cosine similarity) and telemetry EV-loss severity ranking engine with novelty discounting, evaluated offline with `NDCG@k`, `MRR`, `Precision@k`, and `Recall@k` (`evaluate_drill_recommender`).
- **Statistical A/B Policy Testing (`ab_policy_test`)**: Two-sample Welch $t$-test with 95% confidence intervals and AIVAT-style control-variate variance reduction.

---

## 5. Validation Commands

```sh
python3 -m pytest -q
```
