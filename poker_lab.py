"""Local six-player training, evaluation and complete-history review.

The native backend is an independent MIT implementation, not original Pluribus.
All trained models remain experimental: beating simple baselines is not proof
of strength against professional players. No live-table actions are performed.
"""
import argparse
import atexit
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / 'engine' / 'noregrets'
RUNS = ROOT / 'research_runs'
GAME = dict(players=6, starting_stack=10000, small_blind=50, big_blind=100, rake=0, antes=0)
GAME_HU = dict(players=2, starting_stack=10000, small_blind=50, big_blind=100, rake=0, antes=0)
SUPPORTED_GAMES = (GAME, GAME_HU)
PROFILES = {
    'smoke': ['--iters', '10000', '--buckets', '4', '--rollouts', '30', '--runouts', '4', '--raw-buckets'],
    'local': ['--iters', '1000000', '--buckets', '12', '--rollouts', '100', '--runouts', '12', '--kmeans-samples', '2000'],
    'ochs_vr': [
        '--iters', '2000000',
        '--buckets', '16',
        '--rollouts', '150',
        '--runouts', '16',
        '--kmeans-samples', '5000',
        '--ochs',
        '--vr-baseline',
        '--snapshot-avg',
        '--multiway-focus', '0.15',
    ],
    'rnr_caller': [
        '--iters', '500000',
        '--buckets', '12',
        '--rollouts', '100',
        '--runouts', '12',
        '--kmeans-samples', '2000',
        '--ochs',
        '--vr-baseline',
        '--snapshot-avg',
        '--rnr-model', 'caller',
        '--rnr-p', '0.5',
    ],
    'hu_ochs_vr': [
        '--iters', '500000',
        '--buckets', '12',
        '--rollouts', '100',
        '--runouts', '12',
        '--kmeans-samples', '2000',
        '--ochs',
        '--vr-baseline',
        '--snapshot-avg',
    ],
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def runtime():
    cfg_path = ROOT / '.engine' / 'runtime.json'
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    env = os.environ.copy()
    for key in ('CARGO_HOME', 'RUSTUP_HOME', 'CARGO_TARGET_DIR'):
        if key in cfg:
            env[key] = cfg[key]
    env.setdefault('RAYON_NUM_THREADS', '4')
    cargo = cfg.get('cargo') or shutil.which('cargo')
    target = Path(cfg.get('CARGO_TARGET_DIR', ENGINE / 'target'))
    return cargo, target / 'release' / 'pluribus', env


def bounded_run(command, log, *, env=None, timeout=900, memory_mb=6144):
    """Limit the native process's wall time and resident memory; preserve logs."""
    started = time.monotonic()
    peak = 0
    with open(log, 'w') as stream:
        proc = subprocess.Popen([str(x) for x in command], stdout=stream, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
        try:
            while proc.poll() is None:
                if time.monotonic() - started > timeout:
                    raise RuntimeError(f'Run exceeded {timeout}s; log: {log}')
                rss = subprocess.run(['ps', '-o', 'rss=', '-p', str(proc.pid)],
                                     capture_output=True, text=True, timeout=5)
                if rss.stdout.strip():
                    peak = max(peak, int(rss.stdout.strip()))
                    if peak > memory_mb * 1024:
                        raise RuntimeError(f'Run exceeded {memory_mb} MiB RSS; log: {log}')
                time.sleep(.25)
            if proc.returncode:
                raise RuntimeError(f'Engine exited {proc.returncode}; log: {log}')
        finally:
            if proc.poll() is None:
                import signal
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
    return dict(seconds=round(time.monotonic()-started, 3), peak_rss_mib=round(peak/1024, 1))


def run_dir(name):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', name):
        raise ValueError('Use a simple run name containing letters, numbers, hyphens or underscores')
    return RUNS / name


def model(name):
    directory = run_dir(name)
    manifest = json.loads((directory / 'manifest.json').read_text())
    bp = directory / 'blueprint.bin'
    if manifest.get('status') != 'trained' or manifest.get('game') not in SUPPORTED_GAMES:
        raise ValueError('Model is incomplete or game configuration is incompatible')
    if sha256(bp) != manifest['blueprint_sha256']:
        raise ValueError('Blueprint hash differs from the training record')
    _, binary, env = runtime()
    if sha256(binary) != manifest['engine_sha256']:
        raise ValueError('Engine changed since training; rebuild/retrain or explicitly revalidate compatibility')
    return directory, manifest, bp, binary, env


def build():
    cargo, binary, env = runtime()
    if not cargo:
        raise RuntimeError('Rust is required; install it or configure .engine/runtime.json')
    (ROOT / '.engine').mkdir(exist_ok=True)
    result = bounded_run([cargo, 'build', '--release', '--locked', '-j', '4', '--manifest-path', ENGINE/'Cargo.toml'],
                         ROOT/'.engine'/'build.log', env=env, timeout=600)
    return dict(binary=str(binary), sha256=sha256(binary), **result)


def train(name, profile, threads, players=None):
    if not 1 <= threads <= 8:
        raise ValueError('Local thread count must be between 1 and 8')
    if players is None:
        players = 2 if profile == 'hu_ochs_vr' else 6
    if players not in (2, 6):
        raise ValueError('Supported player counts are 2 (Heads-Up) or 6 (6-Max)')
    game_cfg = GAME_HU if players == 2 else GAME
    directory = run_dir(name)
    directory.mkdir(parents=True, exist_ok=False)
    _, binary, env = runtime()
    command = [str(binary), 'train', *PROFILES[profile], '--players', str(players), '--stack', '10000',
               '--threads', str(threads), '--train-seed', '20261015',
               '--checkpoint', str(directory/'checkpoint.bin'), '--out', str(directory/'blueprint.bin')]
    manifest = dict(status='training', strength='unvalidated', live_enabled=False, game=game_cfg,
                    profile=profile, created_utc=datetime.now(timezone.utc).isoformat(), command=command,
                    upstream=json.loads((ENGINE/'UPSTREAM.json').read_text()), engine_sha256=sha256(binary))
    write_json(directory/'manifest.json', manifest)
    try:
        metrics = bounded_run(command, directory/'train.log', env=env, timeout=1800)
        manifest.update(status='trained', blueprint_sha256=sha256(directory/'blueprint.bin'), training=metrics)
    except Exception as exc:
        manifest.update(status='failed', error=str(exc))
        write_json(directory/'manifest.json', manifest)
        raise
    write_json(directory/'manifest.json', manifest)
    return manifest


def parse_eval(text):
    match = re.search(r'winrate: ([+-]?[\d.]+) mbb/hand \(95% CI ±([\d.]+)\) over (\d+) hands', text)
    if not match:
        raise ValueError('Native output did not contain a supported evaluation result')
    mean, halfwidth = float(match[1]) / 10, float(match[2]) / 10
    if not all(math.isfinite(v) for v in (mean, halfwidth)) or halfwidth < 0:
        raise ValueError('Invalid evaluation numbers')
    # 1 milli-BB/hand = 0.1 BB/100; intervals are estimates, not guarantees.
    return dict(bb_per_100=mean, ci95_halfwidth=halfwidth, hands=int(match[3]))


def parse_probe(text):
    match = re.search(r'(?:BR probe|LBR) wins ([+-]?[\d.]+) mbb/hand \(95% CI ±([\d.]+)\) over (\d+) hands', text)
    if not match:
        raise ValueError('Native output did not contain a supported exploitability probe result')
    mean, halfwidth = float(match[1]) / 10, float(match[2]) / 10
    if not all(math.isfinite(v) for v in (mean, halfwidth)) or halfwidth < 0:
        raise ValueError('Invalid probe numbers')
    return dict(bb_per_100=mean, ci95_halfwidth=halfwidth, hands=int(match[3]))


def evaluate(name, hands, seeds):
    if hands < 1000 or hands > 1_000_000 or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError('Use 1,000–1,000,000 hands and distinct seeds')
    directory, manifest, bp, binary, env = model(name)
    players = int((manifest.get('game') or {}).get('players', 6))
    rows = []
    for opponent in ('random', 'caller'):
        for seed in seeds:
            log = directory/f'eval-{opponent}-{seed}-{hands}.log'
            command = [binary, 'eval', '--blueprint', bp, '--players', str(players), '--hands', str(hands),
                       '--baseline', opponent, '--seed', str(seed), '--duplicate']
            metrics = bounded_run(command, log, env=env)
            rows.append(dict(opponent=opponent, seed=seed, **parse_eval(log.read_text()), **metrics))
    report = dict(strength='unvalidated', model_sha256=manifest['blueprint_sha256'],
                  comparison='fixed weak baselines; not Pluribus or professional players',
                  method='duplicate deals with seats rotated; 95% intervals reported per independent seed',
                  results=rows)
    write_json(directory/'evaluation.json', report)
    return report


def parse_turn_data(text):
    match = re.search(r'wrote (\d+) samples to .+ in ([\d.]+)s', text)
    if not match:
        raise ValueError('Native output did not contain a supported gen-turn-data result')
    return dict(samples=int(match[1]), engine_seconds=float(match[2]))


def parse_value_net(text):
    match = re.search(r'value net saved to .+ \(final val loss ([\d.eE+-]+), ([\d.]+)s\)', text)
    if not match:
        raise ValueError('Native output did not contain a supported train-value-net result')
    val_loss = float(match[1])
    if not math.isfinite(val_loss) or val_loss < 0:
        raise ValueError('Invalid value net validation loss')
    return dict(val_loss=val_loss, engine_seconds=float(match[2]))


def parse_distill(text):
    coll = re.search(r'collected (\d+) searched decisions at (\d+) infosets in ([\d.]+)s', text)
    upd = re.search(r'updated (\d+) infosets \((\d+) skipped on menu mismatch\); distilled blueprint saved to .+ \((\d+) strategies\)', text)
    if not coll or not upd:
        raise ValueError('Native output did not contain a supported distill result')
    return dict(
        searched_decisions=int(coll[1]),
        recorded_infosets=int(coll[2]),
        updated_infosets=int(upd[1]),
        skipped_infosets=int(upd[2]),
        total_strategies=int(upd[3]),
    )


def train_value_net(name, samples=500, solve_iters=120, solve_ms=5000, hidden='256,256', epochs=40, lr=1e-3, batch=64, seed=11):
    """Generate solved turn spots from a trained blueprint and train its ReBeL belief-state value network."""
    if samples < 10 or epochs < 1:
        raise ValueError('Require at least 10 samples and 1 epoch')
    directory, manifest, bp, binary, env = model(name)
    turn_data_path = directory / 'turn_data.bin'
    value_net_path = directory / 'value_net.bin'

    gen_log = directory / 'gen-turn-data.log'
    gen_cmd = [
        str(binary), 'gen-turn-data',
        '--blueprint', str(bp),
        '--out', str(turn_data_path),
        '--samples', str(samples),
        '--solve-iters', str(solve_iters),
        '--solve-ms', str(solve_ms),
        '--seed', str(seed),
    ]
    gen_metrics = bounded_run(gen_cmd, gen_log, env=env, timeout=1800)
    gen_parsed = parse_turn_data(gen_log.read_text())

    train_log = directory / 'train-value-net.log'
    train_cmd = [
        str(binary), 'train-value-net',
        '--data', str(turn_data_path),
        '--out', str(value_net_path),
        '--hidden', str(hidden),
        '--epochs', str(epochs),
        '--lr', str(lr),
        '--batch', str(batch),
        '--seed', str(seed),
    ]
    train_metrics = bounded_run(train_cmd, train_log, env=env, timeout=900)
    train_parsed = parse_value_net(train_log.read_text())

    vnet_info = dict(
        value_net_sha256=sha256(value_net_path),
        turn_data_sha256=sha256(turn_data_path),
        samples=gen_parsed['samples'],
        solve_iters=solve_iters,
        hidden=hidden,
        epochs=epochs,
        val_loss=train_parsed['val_loss'],
        gen_metrics=gen_metrics,
        train_metrics=train_metrics,
    )
    manifest['value_net'] = vnet_info
    write_json(directory / 'manifest.json', manifest)
    return vnet_info


def distill_model(source_name, target_name, hands=400, search_ms=40, alpha=0.5, safe_resolve=True, use_value_net=True, seed=11):
    """Run expert-iteration distillation (self-play with online search + ReBeL value net) into a new blueprint run."""
    if hands < 10 or not (0.0 < alpha <= 1.0):
        raise ValueError('Require at least 10 hands and alpha in (0, 1]')
    src_dir, src_manifest, src_bp, binary, env = model(source_name)
    target_dir = run_dir(target_name)
    target_dir.mkdir(parents=True, exist_ok=True)

    vnet_src = src_dir / 'value_net.bin'
    vnet_arg = []
    if use_value_net and vnet_src.exists():
        target_vnet = target_dir / 'value_net.bin'
        if vnet_src.resolve() != target_vnet.resolve():
            shutil.copy2(vnet_src, target_vnet)
        vnet_arg = ['--value-net', str(target_vnet)]

    out_bp = target_dir / 'blueprint.bin'
    distill_log = target_dir / 'distill.log'
    command = [
        str(binary), 'distill',
        '--blueprint', str(src_bp),
        '--out', str(out_bp),
        '--hands', str(hands),
        '--search-ms', str(search_ms),
        '--alpha', str(alpha),
        '--seed', str(seed),
        *(['--safe-resolve'] if safe_resolve else []),
        *vnet_arg,
    ]
    manifest = dict(
        status='distilling',
        strength='unvalidated',
        live_enabled=False,
        game=GAME,
        profile='distilled',
        parent_model=source_name,
        parent_blueprint_sha256=src_manifest['blueprint_sha256'],
        created_utc=datetime.now(timezone.utc).isoformat(),
        command=command,
        upstream=json.loads((ENGINE / 'UPSTREAM.json').read_text()),
        engine_sha256=sha256(binary),
    )
    if (target_dir / 'value_net.bin').exists():
        manifest['value_net_sha256'] = sha256(target_dir / 'value_net.bin')
        if 'value_net' in src_manifest:
            manifest['value_net'] = src_manifest['value_net']
    write_json(target_dir / 'manifest.json', manifest)
    try:
        metrics = bounded_run(command, distill_log, env=env, timeout=1800)
        parsed = parse_distill(distill_log.read_text())
        manifest.update(
            status='trained',
            blueprint_sha256=sha256(out_bp),
            distillation=dict(**parsed, hands=hands, search_ms=search_ms, alpha=alpha, safe_resolve=safe_resolve, **metrics),
        )
    except Exception as exc:
        manifest.update(status='failed', error=str(exc))
        write_json(target_dir / 'manifest.json', manifest)
        raise
    write_json(target_dir / 'manifest.json', manifest)
    return manifest


def benchmark_exploitability(name, br_hands=1000, lbr_hands=4000, aivat_hands=6000, seed=11):
    """Run BR (exact turn/river expectimax best response), LBR, and AIVAT benchmarks on a trained blueprint."""
    directory, manifest, bp, binary, env = model(name)
    results = {}

    br_log = directory / f'br-{seed}-{br_hands}.log'
    br_cmd = [str(binary), 'br', '--blueprint', str(bp), '--hands', str(br_hands), '--runouts', '60', '--seed', str(seed)]
    br_metrics = bounded_run(br_cmd, br_log, env=env, timeout=600)
    results['br'] = dict(**parse_probe(br_log.read_text()), **br_metrics)

    lbr_log = directory / f'lbr-{seed}-{lbr_hands}.log'
    lbr_cmd = [str(binary), 'lbr', '--blueprint', str(bp), '--hands', str(lbr_hands), '--runouts', '60', '--seed', str(seed)]
    lbr_metrics = bounded_run(lbr_cmd, lbr_log, env=env, timeout=600)
    results['lbr'] = dict(**parse_probe(lbr_log.read_text()), **lbr_metrics)

    players = int((manifest.get('game') or {}).get('players', 6))
    aivat_rows = []
    for opponent in ('random', 'caller'):
        alog = directory / f'aivat-{opponent}-{seed}-{aivat_hands}.log'
        acmd = [str(binary), 'eval', '--blueprint', str(bp), '--players', str(players), '--hands', str(aivat_hands),
                '--baseline', opponent, '--seed', str(seed), '--aivat']
        ametrics = bounded_run(acmd, alog, env=env, timeout=600)
        aivat_rows.append(dict(opponent=opponent, seed=seed, **parse_eval(alog.read_text()), **ametrics))
    results['aivat'] = aivat_rows

    report = dict(
        strength='unvalidated',
        model_sha256=manifest['blueprint_sha256'],
        seed=seed,
        benchmarks=results,
    )
    write_json(directory / 'benchmarks.json', report)
    return report


def _resolve_value_net_path(directory, manifest):
    """Return validated value_net.bin path if present in the model directory, else None."""
    vnet_path = Path(directory) / 'value_net.bin'
    if not vnet_path.exists():
        return None
    expected_sha = manifest.get('value_net_sha256') or (manifest.get('value_net') or {}).get('value_net_sha256')
    if expected_sha and sha256(vnet_path) != expected_sha:
        return None
    return vnet_path


def parse_crossplay(text):
    match = re.search(r'focal winrate: ([+-]?[\d.]+) mbb/hand \(95% CI ±([\d.]+)\) over (\d+) hands', text)
    if not match:
        raise ValueError('Native output did not contain a supported crossplay result')
    mean, halfwidth = float(match[1]) / 10, float(match[2]) / 10
    if not all(math.isfinite(v) for v in (mean, halfwidth)) or halfwidth < 0:
        raise ValueError('Invalid crossplay numbers')
    return dict(bb_per_100=mean, ci95_halfwidth=halfwidth, hands=int(match[3]))


def parse_ablate_safety(text):
    rows = []
    for line in text.splitlines():
        m = re.match(r'^\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$', line)
        if m:
            rows.append(dict(
                epsilon=float(m[1]),
                unsafe_mean_chips=float(m[2]),
                unsafe_max_chips=float(m[3]),
                safe_mean_chips=float(m[4]),
                safe_max_chips=float(m[5]),
                pot_chips=float(m[6]),
            ))
    if not rows:
        raise ValueError('Native output did not contain a supported ablate-safety table')
    return rows


def crossplay(focal_name, field_name, hands=24000, seed=11):
    """Run 6-max cross-play with focal_name in 1 rotating seat against 5 seats of field_name."""
    if hands < 100 or hands > 1_000_000:
        raise ValueError('Use 100–1,000,000 hands for crossplay')
    focal_dir, focal_manifest, focal_bp, binary, env = model(focal_name)
    field_dir, field_manifest, field_bp, _, _ = model(field_name)
    log = focal_dir / f'crossplay-vs-{field_name}-{seed}-{hands}.log'
    command = [
        str(binary), 'crossplay',
        '--focal', str(focal_bp),
        '--field', str(field_bp),
        '--hands', str(hands),
        '--seed', str(seed),
    ]
    metrics = bounded_run(command, log, env=env, timeout=900)
    parsed = parse_crossplay(log.read_text())
    entry = dict(
        focal=focal_name,
        field=field_name,
        focal_sha256=focal_manifest['blueprint_sha256'],
        field_sha256=field_manifest['blueprint_sha256'],
        seed=seed,
        **parsed,
        **metrics,
    )
    cp_path = focal_dir / 'crossplay.json'
    existing = json.loads(cp_path.read_text()) if cp_path.exists() else {'matchups': []}
    matchups = [m for m in existing.get('matchups', []) if not (m.get('focal') == focal_name and m.get('field') == field_name and m.get('seed') == seed and m.get('hands') == hands)]
    matchups.append(entry)
    report = dict(strength='unvalidated', updated_utc=datetime.now(timezone.utc).isoformat(), matchups=matchups)
    write_json(cp_path, report)
    return entry


def ablate_safety(spots=24, iters=250, seed=11, target_model='distilled-v1'):
    """Run Burch gadget safe-resolving vs unsafe river resolving ablation under corrupted range beliefs."""
    if spots < 2 or iters < 10:
        raise ValueError('Require at least 2 spots and 10 iterations')
    _, binary, env = runtime()
    out_dir = run_dir(target_model) if (RUNS / target_model).exists() else (ROOT / '.engine')
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / f'ablate-safety-{spots}-{iters}-{seed}.log'
    command = [
        str(binary), 'ablate-safety',
        '--spots', str(spots),
        '--iters', str(iters),
        '--seed', str(seed),
    ]
    metrics = bounded_run(command, log, env=env, timeout=600)
    rows = parse_ablate_safety(log.read_text())
    report = dict(
        spots=spots,
        iters=iters,
        seed=seed,
        rows=rows,
        **metrics,
    )
    write_json(out_dir / 'safety_ablation.json', report)
    return report


_ORIG_BOUNDED_RUN = bounded_run


class _NativeReviewWorker:
    """Thread-safe persistent stdio worker keeping the Rust blueprint and ReBeL ValueNet warm in memory."""
    def __init__(self):
        self._lock = threading.Lock()
        self._proc = None
        self._key = None
        self._manifest = None

    def close(self):
        with self._lock:
            self._stop_locked()

    def _stop_locked(self):
        proc = self._proc
        self._proc = None
        self._key = None
        self._manifest = None
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _ensure_started_locked(self, name):
        directory, manifest, bp, binary, env = model(name)
        vnet = _resolve_value_net_path(directory, manifest)
        key = (
            str(binary),
            manifest['engine_sha256'],
            str(bp),
            manifest['blueprint_sha256'],
            str(vnet) if vnet else None,
        )
        if self._proc is not None and self._proc.poll() is None and self._key == key:
            return self._proc, manifest
        self._stop_locked()
        cmd = [str(binary), 'review', '--blueprint', str(bp), '--stdio']
        if vnet is not None:
            cmd.extend(['--value-net', str(vnet)])
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
        self._key = key
        self._manifest = manifest
        return self._proc, manifest

    def query(self, name, state_dict, search_ms=0, search_iters=100_000):
        if not 0 <= search_ms <= 10000:
            raise ValueError('Search budget must be 0–10000 ms')
        payload = json.dumps(
            {'request': state_dict, 'search_ms': int(search_ms), 'search_iters': int(search_iters)},
            allow_nan=False,
        )
        with self._lock:
            proc, manifest = self._ensure_started_locked(name)
            try:
                proc.stdin.write(payload + '\n')
                proc.stdin.flush()
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError('Persistent review worker closed stdout unexpectedly')
                result = json.loads(line)
            except Exception:
                self._stop_locked()
                raise
            if result.get('status') != 'unavailable':
                result['model_sha256'] = manifest['blueprint_sha256']
                result['worker_mode'] = True
            return result


_REVIEW_WORKER = _NativeReviewWorker()
atexit.register(_REVIEW_WORKER.close)


def shutdown_review_worker():
    """Explicitly stop the persistent native review worker process if running."""
    _REVIEW_WORKER.close()


def review(name, request, search_ms, use_value_net=True):
    directory, manifest, bp, binary, env = model(name)
    if not 0 <= search_ms <= 10000:
        raise ValueError('Search budget must be 0–10000 ms')
    request = Path(request).resolve()
    vnet = _resolve_value_net_path(directory, manifest) if use_value_net else None
    command = [
        str(binary), 'review',
        '--blueprint', str(bp),
        '--request', str(request),
        '--search-ms', str(search_ms),
        *(['--value-net', str(vnet)] if vnet else []),
    ]
    # The outer timeout includes model loading and game-tree construction.
    log = directory/'review-latest.log'
    try:
        bounded_run(command, log, env=env, timeout=60, memory_mb=4096)
    except RuntimeError:
        if log.exists():
            try:
                error = json.loads(log.read_text())
                if error.get('status') == 'unavailable':
                    return error
            except (ValueError, TypeError):
                pass
        raise
    result = json.loads(log.read_text())
    result['model_sha256'] = manifest['blueprint_sha256']
    return result


def best_available_model(preferred=('distilled-v1', 'ochs-vr-v1', 'local-v1', 'smoke-v1'), players=6):
    """Return the name of the strongest trained, hash-verified blueprint model available locally."""
    for name in preferred:
        try:
            _, manifest, _, _, _ = model(name)
            if players is None or int((manifest.get('game') or {}).get('players', 6)) == int(players):
                return name
        except Exception:
            continue
    if RUNS.exists():
        for cand in sorted(RUNS.iterdir()):
            if cand.is_dir():
                try:
                    _, manifest, _, _, _ = model(cand.name)
                    if players is None or int((manifest.get('game') or {}).get('players', 6)) == int(players):
                        return cand.name
                except Exception:
                    continue
    return None


def select_model_for_opponent(opponent_vpip=None, num_opponents=1, stack_bb=100, players=6):
    """Select the optimal trained blueprint model based on table size and opponent VPIP profile.

    - When players == 2 (Heads-Up), selects 'hu-v1' if available.
    - When opponent_vpip >= 40.0 (loose-passive calling station), routes to the
      Restricted Nash Response exploitative blueprint ('rnr-caller-v1') if available.
    - Otherwise routes to the strongest equilibrium blueprint ('distilled-v1' / 'ochs-vr-v1').
    """
    if int(players or 6) == 2:
        hu_cand = best_available_model(preferred=('hu-v1',), players=2)
        if hu_cand:
            return hu_cand
    if opponent_vpip is not None and float(opponent_vpip) >= 40.0:
        rnr_cand = best_available_model(preferred=('rnr-caller-v1',), players=6)
        if rnr_cand:
            return rnr_cand
    return best_available_model(players=6) or best_available_model(players=None)


def review_state(state_dict, search_ms=0, model_name=None, use_worker=True):
    """Query the trained Rust MCCFR blueprint/subgame resolver using an in-memory state dict."""
    import tempfile
    chosen = model_name or best_available_model()
    if not chosen:
        return {'status': 'unavailable', 'error': 'No trained blueprint model available'}
    if use_worker and bounded_run is _ORIG_BOUNDED_RUN:
        try:
            return _REVIEW_WORKER.query(chosen, state_dict, search_ms=search_ms)
        except ValueError:
            raise
        except Exception:
            pass
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as tf:
        json.dump(state_dict, tf, allow_nan=False)
        req_path = Path(tf.name)
    try:
        return review(chosen, req_path, search_ms)
    finally:
        try:
            req_path.unlink()
        except OSError:
            pass


POS_TO_SEAT = {'BTN': 0, 'SB': 1, 'BB': 2, 'UTG': 3, 'MP': 4, 'CO': 5}
PREFLOP_ORDER = [3, 4, 5, 0, 1, 2]
POSTFLOP_ORDER = [1, 2, 3, 4, 5, 0]


def _parse_card_tokens(card_str):
    if not card_str:
        return []
    clean = card_str.replace(' ', '').strip()
    if len(clean) % 2 != 0:
        raise ValueError(f'Invalid card string: {card_str!r}')
    cards = []
    for i in range(0, len(clean), 2):
        r, s = clean[i].upper(), clean[i + 1].lower()
        if r not in '23456789TJQKA' or s not in 'shdc':
            raise ValueError(f'Invalid card token: {clean[i:i+2]!r}')
        cards.append(r + s)
    return cards


def _reconcile_observed_preflop(
    observed_actions,
    hero_seat,
    villain_seat,
    board_cards,
    bb_scale,
):
    """
    Attempt to replay structured observed preflop actions from PreflopTracker onto the
    6-max 50/100 (10,000 stack) engine state. Returns (stacks, street_commit, actions, live_seats)
    if valid, or None if the observed sequence cannot be cleanly reconciled.
    """
    if not observed_actions or not isinstance(observed_actions, (list, tuple)):
        return None
    stacks = [10000, 9950, 9900, 10000, 10000, 10000]
    street_commit = [0, 50, 100, 0, 0, 0]
    folded = [False] * 6
    actions = []

    def _fold(s):
        actions.append({'seat': s, 'action': 'fold', 'amount': None})
        folded[s] = True

    def _check(s):
        actions.append({'seat': s, 'action': 'check', 'amount': None})

    def _call(s, target):
        pay = min(stacks[s], max(0, target - street_commit[s]))
        stacks[s] -= pay
        street_commit[s] += pay
        actions.append({'seat': s, 'action': 'call', 'amount': None})

    def _raise_to(s, amt):
        pay = amt - street_commit[s]
        stacks[s] -= pay
        street_commit[s] = amt
        actions.append({'seat': s, 'action': 'raise_to', 'amount': int(amt)})

    # Map each observed event to engine seat (by position name if available)
    norm_events = []
    for ev in observed_actions:
        if not isinstance(ev, dict):
            continue
        pos = (ev.get('pos') or '').upper()
        seat = POS_TO_SEAT.get(pos) if pos in POS_TO_SEAT else ev.get('seat')
        if seat is None or not (0 <= int(seat) < 6):
            continue
        seat = int(seat)
        act = (ev.get('action') or '').lower()
        if act not in ('fold', 'check', 'call', 'raise_to'):
            continue
        amt = ev.get('amount')
        amt_bb = ev.get('amount_bb')
        if act == 'raise_to':
            if amt_bb is not None and float(amt_bb) > 0:
                eng_amt = int(round(float(amt_bb) * 100.0))
            elif amt is not None and float(amt) > 0:
                eng_amt = int(round(float(amt) * bb_scale))
            else:
                continue
        else:
            eng_amt = None
        norm_events.append({'seat': seat, 'action': act, 'amount': eng_amt})

    if not norm_events:
        return None

    # Replay along the 6-max preflop action order, inserting folds for skipped seats
    idx = 0
    order_cycle = PREFLOP_ORDER * 4
    cur_idx = 0
    while idx < len(norm_events) and cur_idx < len(order_cycle):
        target_ev = norm_events[idx]
        seat = order_cycle[cur_idx]
        cur_idx += 1
        if folded[seat]:
            continue
        current_max = max(street_commit)
        if seat != target_ev['seat']:
            if street_commit[seat] < current_max or current_max == 100:
                _fold(seat)
            continue
        act = target_ev['action']
        if act == 'fold':
            if street_commit[seat] >= current_max and current_max == 100 and seat == 2:
                _check(seat)
            else:
                _fold(seat)
        elif act == 'check':
            if street_commit[seat] == current_max:
                _check(seat)
            else:
                _call(seat, current_max)
        elif act == 'call':
            if street_commit[seat] == current_max:
                _check(seat)
            else:
                _call(seat, current_max)
        elif act == 'raise_to':
            min_raise = current_max + max(100, current_max - 50) if current_max > 100 else 200
            amt = max(min_raise, min(10000, int(target_ev['amount'])))
            _raise_to(seat, amt)
        idx += 1

    if idx < len(norm_events) or folded[hero_seat]:
        return None

    if len(board_cards) == 0:
        # Advance with folds up to hero_seat
        while cur_idx < len(order_cycle):
            seat = order_cycle[cur_idx]
            cur_idx += 1
            if folded[seat]:
                continue
            if seat == hero_seat:
                return stacks, street_commit, actions, [s for s in range(6) if not folded[s]]
            _fold(seat)
        return None

    # Postflop requires closing preflop action with exactly 2 live players (hero and villain)
    current_max = max(street_commit)
    if current_max <= 100:
        return None
    while cur_idx < len(order_cycle):
        live = [s for s in range(6) if not folded[s]]
        if len(live) == 2 and all(street_commit[s] == current_max for s in live):
            break
        seat = order_cycle[cur_idx]
        cur_idx += 1
        if folded[seat]:
            continue
        if seat in (hero_seat, villain_seat):
            if street_commit[seat] < current_max:
                _call(seat, current_max)
        else:
            _fold(seat)

    live = [s for s in range(6) if not folded[s]]
    if len(live) != 2 or hero_seat not in live:
        return None
    return stacks, street_commit, actions, live


def _synthesize_hu_review_request(
    hole,
    board_cards,
    scaled_pot,
    scaled_call,
    spot,
    in_position,
    postflop_history=None,
    bb_scale=1.0,
):
    """Synthesize a legal, chip-reconciled 2-player (Heads-Up) Request dictionary on 50/100 (10,000 stack)."""
    # In 2-player Heads-Up (engine.rs): button=0 posts SB (50) and acts first preflop & second postflop;
    # seat 1 posts BB (100) and acts second preflop & first postflop.
    pos_name = (spot.get('pos') or ('BTN' if in_position else 'BB')).upper()
    kind = (spot.get('kind') or 'open').lower()
    if pos_name in ('BTN', 'SB'):
        hero_seat = 0
    elif pos_name == 'BB':
        hero_seat = 1
    else:
        hero_seat = 0 if in_position else 1
    villain_seat = 1 - hero_seat

    stacks = [9950, 9900]
    street_commit = [50, 100]
    actions = []

    def _do_check(s):
        actions.append({'seat': s, 'action': 'check', 'amount': None})

    def _do_call(s, target):
        pay = min(stacks[s], max(0, target - street_commit[s]))
        stacks[s] -= pay
        street_commit[s] += pay
        actions.append({'seat': s, 'action': 'call', 'amount': None})

    def _do_raise_to(s, amt):
        pay = amt - street_commit[s]
        stacks[s] -= pay
        street_commit[s] = amt
        actions.append({'seat': s, 'action': 'raise_to', 'amount': int(amt)})

    def _reset_street():
        street_commit[0] = 0
        street_commit[1] = 0

    if len(board_cards) == 0:
        if hero_seat == 0:
            if kind == 'facing_3bet':
                _do_raise_to(0, 250)
                _do_raise_to(1, max(600, min(3500, 250 + (scaled_call if scaled_call >= 350 else 550))))
        else:
            if kind in ('facing_open', 'open', 'iso_raise'):
                open_amt = max(200, min(2500, 100 + (scaled_call if scaled_call >= 100 else 150)))
                _do_raise_to(0, open_amt)
            elif kind == 'facing_4bet':
                _do_raise_to(0, 250)
                _do_raise_to(1, 750)
                _do_raise_to(0, max(1800, min(5000, 750 + (scaled_call if scaled_call >= 1050 else 1250))))
        return {
            'players': 2,
            'button': 0,
            'hero': hero_seat,
            'hole': hole,
            'board': [],
            'actions': actions,
            'expected_pot': 20000 - sum(stacks),
            'expected_stacks': stacks,
        }

    # Postflop HU: calculate prior postflop street commits if postflop_history is provided
    prior_street_names = ['flop', 'turn'][:max(0, len(board_cards) - 3)]
    hist_by_street = {}
    for item in (postflop_history or []):
        if isinstance(item, dict) and item.get('street') in prior_street_names:
            hist_by_street[item['street']] = item

    prior_postflop_commits = 0
    for st in prior_street_names:
        ev = hist_by_street.get(st)
        if ev and ev.get('action') == 'bet_call':
            amt_bb = ev.get('amount_bb')
            amt_raw = ev.get('amount')
            if amt_bb is not None and float(amt_bb) > 0:
                w = max(100, int(round(float(amt_bb) * 100.0)))
            elif amt_raw is not None and float(amt_raw) > 0:
                w = max(100, int(round(float(amt_raw) * bb_scale)))
            else:
                w = 0
            prior_postflop_commits += 2 * w

    target_p0 = max(200, min(18000, scaled_pot - scaled_call - prior_postflop_commits))
    per_player_pre = max(100, min(4000, target_p0 // 2))
    if 100 < per_player_pre < 200:
        per_player_pre = 200

    if per_player_pre <= 100:
        _do_call(0, 100)
        _do_check(1)
    else:
        _do_raise_to(0, per_player_pre)
        _do_call(1, per_player_pre)

    _reset_street()
    # Postflop HU order: seat 1 (BB) acts first, seat 0 (BTN/SB) acts second
    first_post, second_post = 1, 0
    hero_acts_first = (hero_seat == first_post)

    for st in prior_street_names:
        ev = hist_by_street.get(st)
        max_s = min(stacks[0], stacks[1])
        w = 0
        if ev and ev.get('action') == 'bet_call' and max_s >= 100:
            amt_bb = ev.get('amount_bb')
            amt_raw = ev.get('amount')
            if amt_bb is not None and float(amt_bb) > 0:
                w = min(max_s, max(100, int(round(float(amt_bb) * 100.0))))
            elif amt_raw is not None and float(amt_raw) > 0:
                w = min(max_s, max(100, int(round(float(amt_raw) * bb_scale))))
        if w >= 100:
            _do_raise_to(first_post, w)
            _do_call(second_post, w)
        else:
            _do_check(first_post)
            _do_check(second_post)
        _reset_street()

    max_wager = min(stacks[hero_seat], stacks[villain_seat])
    wager = min(max_wager, max(100, scaled_call)) if scaled_call > 0 else 0
    if wager <= 0 or max_wager == 0:
        if not hero_acts_first:
            _do_check(first_post)
    else:
        if hero_acts_first:
            _do_check(hero_seat)
            _do_raise_to(villain_seat, wager)
        else:
            _do_raise_to(villain_seat, wager)

    return {
        'players': 2,
        'button': 0,
        'hero': hero_seat,
        'hole': hole,
        'board': board_cards,
        'actions': actions,
        'expected_pot': 20000 - sum(stacks),
        'expected_stacks': stacks,
    }


def synthesize_review_request(
    hero_hand,
    board='',
    pot_size=150.0,
    call_amount=0.0,
    spot=None,
    in_position=True,
    big_blind=100.0,
    observed_actions=None,
    preflop_context=None,
    postflop_history=None,
    players=None,
):
    """
    Synthesize a legal, chip-reconciled 6-max (or 2-player Heads-Up) Request dictionary for
    engine/noregrets/src/review.rs on the 50/100 (10,000 starting stack) grid from a live
    preflop or postflop spot.
    When observed_actions or preflop_context['action_history'] is provided, replays the real
    tracked preflop sequence before falling back to spot synthesis.
    When postflop_history is provided, replays completed prior postflop street bets/calls.
    """
    hole = _parse_card_tokens(hero_hand)
    board_cards = _parse_card_tokens(board)
    if len(hole) != 2 or len(board_cards) not in (0, 3, 4, 5):
        raise ValueError('Require 2 hole cards and 0, 3, 4, or 5 board cards')
    if len(set(hole + board_cards)) != len(hole) + len(board_cards):
        raise ValueError('Duplicate known cards between hole and board')

    spot = spot if isinstance(spot, dict) else {}
    if observed_actions is None and isinstance(preflop_context, dict):
        observed_actions = preflop_context.get('action_history')
    if observed_actions is None and isinstance(spot, dict):
        observed_actions = spot.get('action_history')
    if postflop_history is None and isinstance(preflop_context, dict):
        postflop_history = preflop_context.get('postflop_history')
    if postflop_history is None and isinstance(spot, dict):
        postflop_history = spot.get('postflop_history')

    num_players = int(players or spot.get('players') or spot.get('table_size') or 6)
    bb_scale = 100.0 / float(big_blind) if (big_blind and float(big_blind) > 0) else 1.0
    scaled_pot = max(150, int(round(float(pot_size) * bb_scale)))
    scaled_call = max(0, int(round(float(call_amount) * bb_scale)))

    if num_players == 2:
        return _synthesize_hu_review_request(
            hole=hole,
            board_cards=board_cards,
            scaled_pot=scaled_pot,
            scaled_call=scaled_call,
            spot=spot,
            in_position=in_position,
            postflop_history=postflop_history,
            bb_scale=bb_scale,
        )

    pos_name = (spot.get('pos') or ('BTN' if in_position else 'BB')).upper()
    vs_name = (spot.get('vs') or '').upper()
    kind = (spot.get('kind') or 'open').lower()

    hero_seat = POS_TO_SEAT.get(pos_name, 0 if in_position else 2)
    if vs_name in POS_TO_SEAT and POS_TO_SEAT[vs_name] != hero_seat:
        villain_seat = POS_TO_SEAT[vs_name]
    else:
        if hero_seat == 2:
            villain_seat = 0
        elif hero_seat == 1:
            villain_seat = 2
        else:
            villain_seat = 2

    # Scale live amounts to the 50/100 (BB=100) engine grid
    bb_scale = 100.0 / float(big_blind) if (big_blind and float(big_blind) > 0) else 1.0
    scaled_pot = max(150, int(round(float(pot_size) * bb_scale)))
    scaled_call = max(0, int(round(float(call_amount) * bb_scale)))

    # Track exact 6-max state to guarantee 100% reconciliation with review.rs
    stacks = [10000, 9950, 9900, 10000, 10000, 10000]
    street_commit = [0, 50, 100, 0, 0, 0]
    folded = [False] * 6
    actions = []

    def _do_fold(seat):
        actions.append({'seat': seat, 'action': 'fold', 'amount': None})
        folded[seat] = True

    def _do_check(seat):
        actions.append({'seat': seat, 'action': 'check', 'amount': None})

    def _do_call(seat, target_bet):
        pay = min(stacks[seat], max(0, target_bet - street_commit[seat]))
        stacks[seat] -= pay
        street_commit[seat] += pay
        actions.append({'seat': seat, 'action': 'call', 'amount': None})

    def _do_raise_to(seat, amount):
        pay = amount - street_commit[seat]
        stacks[seat] -= pay
        street_commit[seat] = amount
        actions.append({'seat': seat, 'action': 'raise_to', 'amount': int(amount)})

    def _reset_street():
        for i in range(6):
            street_commit[i] = 0

    replayed = _reconcile_observed_preflop(observed_actions, hero_seat, villain_seat, board_cards, bb_scale)

    if len(board_cards) == 0:
        if replayed is not None:
            stacks, street_commit, actions, _ = replayed
            expected_pot = 10000 * 6 - sum(stacks)
            return {
                'players': 6,
                'button': 0,
                'hero': hero_seat,
                'hole': hole,
                'board': [],
                'actions': actions,
                'expected_pot': expected_pot,
                'expected_stacks': stacks,
            }
        # Preflop active decision for hero_seat
        if kind == 'open':
            for s in PREFLOP_ORDER:
                if s == hero_seat:
                    break
                _do_fold(s)
        elif kind in ('facing_open', 'iso_raise'):
            if PREFLOP_ORDER.index(villain_seat) > PREFLOP_ORDER.index(hero_seat):
                villain_seat = PREFLOP_ORDER[0] if hero_seat != PREFLOP_ORDER[0] else PREFLOP_ORDER[1]
            open_amt = max(200, min(2500, street_commit[hero_seat] + (scaled_call if scaled_call >= 100 else 150)))
            for s in PREFLOP_ORDER:
                if s == hero_seat:
                    break
                if s == villain_seat:
                    _do_raise_to(s, open_amt)
                else:
                    _do_fold(s)
        elif kind == 'facing_3bet':
            # Hero opened, villain 3-bet, action back on Hero
            hero_idx = PREFLOP_ORDER.index(hero_seat)
            if PREFLOP_ORDER.index(villain_seat) < hero_idx:
                villain_seat = 2 if hero_seat != 2 else 0
            open_amt = 250
            threebet_amt = max(600, min(3500, open_amt + (scaled_call if scaled_call >= 350 else 550)))
            for s in PREFLOP_ORDER:
                if s == hero_seat:
                    _do_raise_to(s, open_amt)
                elif s == villain_seat:
                    _do_raise_to(s, threebet_amt)
                else:
                    _do_fold(s)
            for s in PREFLOP_ORDER:
                if s == hero_seat:
                    break
                if not folded[s] and s != villain_seat:
                    _do_fold(s)
        elif kind == 'facing_4bet':
            # Villain opened, Hero 3-bet, Villain 4-bet, action back on Hero.
            # Use canonical on-tree abstract bet sizes (MenuShape::Pluribus preflop:
            # open Bet(2)=50% -> 225, 3-bet Bet(4)=100% -> 825, 4-bet Bet(4)=100% -> 2625)
            # so the shadow hand history aligns with visited blueprint infosets.
            if PREFLOP_ORDER.index(villain_seat) > PREFLOP_ORDER.index(hero_seat):
                villain_seat = PREFLOP_ORDER[0] if hero_seat != PREFLOP_ORDER[0] else PREFLOP_ORDER[1]
            open_amt = 225
            threebet_amt = 825
            fourbet_amt = max(1800, min(5000, threebet_amt + (scaled_call if scaled_call >= 1050 else 1800)))
            for s in PREFLOP_ORDER:
                if s == villain_seat:
                    _do_raise_to(s, open_amt)
                elif s == hero_seat:
                    _do_raise_to(s, threebet_amt)
                else:
                    _do_fold(s)
            for s in PREFLOP_ORDER:
                if s == villain_seat:
                    _do_raise_to(s, fourbet_amt)
                elif s == hero_seat:
                    break
                elif not folded[s]:
                    _do_fold(s)
        else:
            for s in PREFLOP_ORDER:
                if s == hero_seat:
                    break
                _do_fold(s)
        expected_pot = 10000 * 6 - sum(stacks)
        return {
            'players': 6,
            'button': 0,
            'hero': hero_seat,
            'hole': hole,
            'board': [],
            'actions': actions,
            'expected_pot': expected_pot,
            'expected_stacks': stacks,
        }

    prior_street_names = ['flop', 'turn'][:max(0, len(board_cards) - 3)]
    hist_by_street = {}
    for item in (postflop_history or []):
        if isinstance(item, dict) and item.get('street') in prior_street_names:
            hist_by_street[item['street']] = item

    prior_postflop_commits = 0
    for st in prior_street_names:
        ev = hist_by_street.get(st)
        if ev and ev.get('action') == 'bet_call':
            amt_bb = ev.get('amount_bb')
            amt_raw = ev.get('amount')
            if amt_bb is not None and float(amt_bb) > 0:
                w = max(100, int(round(float(amt_bb) * 100.0)))
            elif amt_raw is not None and float(amt_raw) > 0:
                w = max(100, int(round(float(amt_raw) * bb_scale)))
            else:
                w = 0
            prior_postflop_commits += 2 * w

    if replayed is not None:
        stacks, street_commit, actions, live_seats = replayed
        other = [s for s in live_seats if s != hero_seat]
        if other:
            villain_seat = other[0]
    else:
        dead_blinds = (50 if 1 not in (hero_seat, villain_seat) else 0) + (100 if 2 not in (hero_seat, villain_seat) else 0)
        target_p0 = max(200, min(9000, scaled_pot - scaled_call - prior_postflop_commits))
        per_player_pre = max(100, min(4000, (target_p0 - dead_blinds) // 2))
        if 100 < per_player_pre < 200:
            per_player_pre = 200

        pre_pair = sorted([hero_seat, villain_seat], key=lambda s: PREFLOP_ORDER.index(s))
        first_pre, second_pre = pre_pair[0], pre_pair[1]

        if per_player_pre <= 100:
            for s in PREFLOP_ORDER:
                if s == first_pre:
                    _do_call(s, 100)
                elif s == second_pre:
                    if street_commit[s] < 100:
                        _do_call(s, 100)
                    else:
                        _do_check(s)
                else:
                    _do_fold(s)
        else:
            for s in PREFLOP_ORDER:
                if s == first_pre:
                    _do_raise_to(s, per_player_pre)
                elif s not in (first_pre, second_pre):
                    _do_fold(s)
                elif s == second_pre:
                    _do_call(s, per_player_pre)

    # Postflop: determine first and second actor between hero and villain
    active_pair = sorted([hero_seat, villain_seat], key=lambda s: POSTFLOP_ORDER.index(s))
    first_post, second_post = active_pair[0], active_pair[1]
    hero_acts_first = (hero_seat == first_post)

    _reset_street()

    # Replay completed prior postflop streets (bet+call if recorded in postflop_history, else check-check)
    for st in prior_street_names:
        ev = hist_by_street.get(st)
        max_s = min(stacks[hero_seat], stacks[villain_seat])
        w = 0
        if ev and ev.get('action') == 'bet_call' and max_s >= 100:
            amt_bb = ev.get('amount_bb')
            amt_raw = ev.get('amount')
            if amt_bb is not None and float(amt_bb) > 0:
                w = min(max_s, max(100, int(round(float(amt_bb) * 100.0))))
            elif amt_raw is not None and float(amt_raw) > 0:
                w = min(max_s, max(100, int(round(float(amt_raw) * bb_scale))))
        if w >= 100:
            aggressor = ev.get('aggressor') if isinstance(ev, dict) else None
            if aggressor == 'second':
                _do_check(first_post)
                _do_raise_to(second_post, w)
                _do_call(first_post, w)
            elif aggressor == 'hero' and not hero_acts_first:
                _do_check(first_post)
                _do_raise_to(hero_seat, w)
                _do_call(villain_seat, w)
            elif aggressor == 'villain' and hero_acts_first:
                _do_check(hero_seat)
                _do_raise_to(villain_seat, w)
                _do_call(hero_seat, w)
            else:
                _do_raise_to(first_post, w)
                _do_call(second_post, w)
        else:
            _do_check(first_post)
            _do_check(second_post)
        _reset_street()

    # Current postflop street action up to Hero's decision
    max_wager = min(stacks[hero_seat], stacks[villain_seat])
    wager = min(max_wager, max(100, scaled_call)) if scaled_call > 0 else 0

    if wager <= 0 or max_wager == 0:
        if not hero_acts_first:
            _do_check(first_post)
    else:
        if hero_acts_first:
            _do_check(hero_seat)
            _do_raise_to(villain_seat, wager)
        else:
            _do_raise_to(villain_seat, wager)

    expected_pot = 10000 * 6 - sum(stacks)
    return {
        'players': 6,
        'button': 0,
        'hero': hero_seat,
        'hole': hole,
        'board': board_cards,
        'actions': actions,
        'expected_pot': expected_pot,
        'expected_stacks': stacks,
    }


_NATIVE_SUBGAME_CACHE = {}
_NATIVE_SUBGAME_CACHE_MAX = 256


def clear_native_subgame_cache():
    """Clear the in-memory LRU cache for query_native_subgame."""
    _NATIVE_SUBGAME_CACHE.clear()


_CANON_SUITS = ('s', 'h', 'd', 'c')


def canonical_hand_to_hole_cards(hand_str):
    """Expand a canonical hand string (e.g. 'AKs', 'JJ', 'T9o') or exact 4-char hand into 2 concrete cards."""
    if not hand_str:
        raise ValueError('Empty hand')
    clean = hand_str.replace(' ', '').strip()
    if len(clean) == 4 and clean[0].upper() in '23456789TJQKA' and clean[2].upper() in '23456789TJQKA':
        return clean[0].upper() + clean[1].lower() + clean[2].upper() + clean[3].lower()
    if len(clean) == 2 and clean[0].upper() == clean[1].upper() and clean[0].upper() in '23456789TJQKA':
        r = clean[0].upper()
        return f'{r}s{r}h'
    if len(clean) == 3 and clean[0].upper() in '23456789TJQKA' and clean[1].upper() in '23456789TJQKA':
        r1, r2, kind = clean[0].upper(), clean[1].upper(), clean[2].lower()
        if kind == 's':
            return f'{r1}s{r2}s'
        if kind == 'o':
            return f'{r1}s{r2}d'
    raise ValueError(f'Cannot convert hand {hand_str!r} to concrete hole cards')


def query_native_preflop(
    hero_hand,
    spot=None,
    pot_size=150.0,
    call_amount=100.0,
    big_blind=100.0,
    observed_actions=None,
    preflop_context=None,
    model_name=None,
    opponent_vpip=None,
    players=None,
    use_cache=True,
):
    """Query the native MCCFR blueprint for preflop action frequencies (RAISE, CALL, FOLD)."""
    concrete_hand = canonical_hand_to_hole_cards(hero_hand)
    return query_native_subgame(
        hero_hand=concrete_hand,
        board='',
        pot_size=pot_size,
        call_amount=call_amount,
        spot=spot,
        in_position=True,
        big_blind=big_blind,
        search_ms=0,
        model_name=model_name,
        opponent_vpip=opponent_vpip,
        players=players,
        use_cache=use_cache,
        observed_actions=observed_actions,
        preflop_context=preflop_context,
    )


def _fallback_preflop_frequencies(hero_hand, spot_dict):
    """Compute deterministic preflop frequencies when a deep 4-bet infoset was unvisited in blueprint training."""
    try:
        import ranges
        norm = ranges.normalize_hand(hero_hand)
        freqs = ranges.get_mixed_frequencies(spot_dict, norm) if norm else {}
        if freqs:
            mapped = {}
            for act, pct in freqs.items():
                key = 'RAISE' if ('BET' in act or 'RAISE' in act or 'SQUEEZE' in act) else ('CALL' if act in ('CALL', 'CHECK') else 'FOLD')
                mapped[key] = mapped.get(key, 0) + int(pct)
            total = sum(mapped.values())
            if total > 0:
                if total != 100:
                    top_k = max(mapped, key=mapped.get)
                    mapped[top_k] += (100 - total)
                return {k: v for k, v in mapped.items() if v > 0}
        adv = ranges.advise(spot_dict, norm) if norm else None
        if adv and adv[0]:
            act = adv[0]
            key = 'RAISE' if ('BET' in act or 'RAISE' in act or 'SQUEEZE' in act) else ('CALL' if act in ('CALL', 'CHECK') else 'FOLD')
            return {key: 100}
    except Exception:
        pass
    return {'CALL': 100}


def query_native_subgame(
    hero_hand,
    board,
    pot_size,
    call_amount,
    spot=None,
    in_position=True,
    big_blind=100.0,
    search_ms=50,
    model_name=None,
    opponent_vpip=None,
    postflop_history=None,
    players=None,
    use_cache=True,
    observed_actions=None,
    preflop_context=None,
):
    """
    Synthesize a reconciled 6-max (or 2-player HU) state and query the native Rust MCCFR blueprint /
    online subgame resolver, mapping abstract actions into RTA {'FOLD', 'CALL', 'RAISE'} frequencies.
    Uses an in-memory LRU cache keyed on normalized spot parameters for instant repeated lookups.
    """
    spot_dict = spot if isinstance(spot, dict) else {}
    num_players = int(players or spot_dict.get('players') or spot_dict.get('table_size') or 6)
    if model_name:
        resolved_model = model_name
    else:
        resolved_model = select_model_for_opponent(
            opponent_vpip=opponent_vpip,
            num_opponents=max(1, num_players - 1),
            players=num_players,
        )
    if resolved_model:
        try:
            _, manifest, _, _, _ = model(resolved_model)
            num_players = int((manifest.get('game') or {}).get('players', num_players))
        except Exception:
            pass

    if observed_actions is None and isinstance(preflop_context, dict):
        observed_actions = preflop_context.get('action_history')
    if observed_actions is None and isinstance(spot_dict, dict):
        observed_actions = spot_dict.get('action_history')
    if postflop_history is None and isinstance(preflop_context, dict):
        postflop_history = preflop_context.get('postflop_history')
    if postflop_history is None and isinstance(spot_dict, dict):
        postflop_history = spot_dict.get('postflop_history')

    obs_sig = tuple(
        (ev.get('pos') or ev.get('seat'), ev.get('action'), ev.get('amount_bb') or ev.get('amount'))
        for ev in (observed_actions or [])
        if isinstance(ev, dict)
    )
    post_sig = tuple(
        (ev.get('street'), ev.get('action'), ev.get('amount_bb') or ev.get('amount'), ev.get('aggressor'))
        for ev in (postflop_history or [])
        if isinstance(ev, dict)
    )
    bb_val = float(big_blind) if (big_blind and float(big_blind) > 0) else 100.0
    pot_bb = round(float(pot_size) / bb_val, 2)
    call_bb = round(float(call_amount) / bb_val, 2)
    cache_key = (
        resolved_model,
        num_players,
        (hero_hand or '').replace(' ', '').strip(),
        (board or '').replace(' ', '').strip(),
        pot_bb,
        call_bb,
        (spot_dict.get('kind') or 'open').lower(),
        (spot_dict.get('pos') or ('BTN' if in_position else 'BB')).upper(),
        (spot_dict.get('vs') or '').upper(),
        bool(in_position),
        int(search_ms),
        obs_sig,
        post_sig,
    )
    if use_cache and cache_key in _NATIVE_SUBGAME_CACHE:
        cached = _NATIVE_SUBGAME_CACHE.pop(cache_key)
        _NATIVE_SUBGAME_CACHE[cache_key] = cached
        return dict(cached, cached=True)

    req = synthesize_review_request(
        hero_hand=hero_hand,
        board=board,
        pot_size=pot_size,
        call_amount=call_amount,
        spot=spot,
        in_position=in_position,
        big_blind=big_blind,
        observed_actions=observed_actions,
        preflop_context=preflop_context,
        postflop_history=postflop_history,
        players=num_players,
    )
    raw = review_state(req, search_ms=search_ms, model_name=resolved_model)
    if raw.get('status') == 'uncovered' and not raw.get('actions'):
        if not board:
            fb_freqs = _fallback_preflop_frequencies(hero_hand, spot_dict)
            result = {
                'status': 'uncovered',
                'blueprint_covered': False,
                'value_net_loaded': bool(raw.get('value_net_loaded', False)),
                'worker_mode': bool(raw.get('worker_mode', False)),
                'cfr_frequencies': fb_freqs,
                'cfr_preferred_sizing': None,
                'training_iterations': raw.get('training_iterations', 0),
                'search_requested_ms': raw.get('search_requested_ms', search_ms),
                'model_name': resolved_model,
                'model_sha256': raw.get('model_sha256'),
                'raw_actions': [],
                'request': req,
                'cached': False,
            }
            if use_cache:
                if len(_NATIVE_SUBGAME_CACHE) >= _NATIVE_SUBGAME_CACHE_MAX:
                    oldest_key = next(iter(_NATIVE_SUBGAME_CACHE))
                    _NATIVE_SUBGAME_CACHE.pop(oldest_key, None)
                _NATIVE_SUBGAME_CACHE[cache_key] = result
            return dict(result)
        raw = review_state(req, search_ms=max(15, int(search_ms or 15)), model_name=resolved_model)

    if raw.get('status') not in ('candidate', 'uncovered') or not raw.get('actions'):
        return {
            'status': raw.get('status', 'unavailable'),
            'error': raw.get('error', 'No actions returned'),
            'request': req,
        }

    probs = {}
    best_raise_amt = None
    best_raise_prob = -1.0
    for item in raw['actions']:
        act = item.get('action', '')
        p = float(item.get('probability', 0.0))
        if act == 'fold':
            key = 'FOLD'
        elif act in ('check', 'call'):
            key = 'CALL'
        elif act == 'raise_to':
            key = 'RAISE'
            if p > best_raise_prob:
                best_raise_prob = p
                best_raise_amt = item.get('amount')
        else:
            continue
        probs[key] = probs.get(key, 0.0) + p

    frequencies = {k: int(v * 100) for k, v in probs.items()}
    remainder = 100 - sum(frequencies.values())
    for k in sorted(probs, key=lambda x: probs[x] * 100 - frequencies[x], reverse=True)[:max(0, remainder)]:
        frequencies[k] += 1

    preferred_sizing = None
    if best_raise_amt is not None and raw.get('pot', 0) > 0:
        to_call_eng = raw.get('to_call', 0)
        pot_before_call = max(1, raw['pot'] - to_call_eng)
        if to_call_eng <= 0:
            pct = int(round((best_raise_amt / pot_before_call) * 100))
            preferred_sizing = f'{pct}% pot'
        else:
            mult = round(best_raise_amt / max(1, to_call_eng), 1)
            preferred_sizing = f'{mult:.1f}x raise'

    result = {
        'status': raw['status'],
        'blueprint_covered': bool(raw.get('blueprint_covered', False)),
        'value_net_loaded': bool(raw.get('value_net_loaded', False)),
        'worker_mode': bool(raw.get('worker_mode', False)),
        'cfr_frequencies': {k: v for k, v in frequencies.items() if v > 0},
        'cfr_preferred_sizing': preferred_sizing,
        'training_iterations': raw.get('training_iterations', 0),
        'search_requested_ms': raw.get('search_requested_ms', search_ms),
        'model_name': resolved_model,
        'model_sha256': raw.get('model_sha256'),
        'raw_actions': raw['actions'],
        'request': req,
        'cached': False,
    }
    if use_cache:
        if len(_NATIVE_SUBGAME_CACHE) >= _NATIVE_SUBGAME_CACHE_MAX:
            oldest_key = next(iter(_NATIVE_SUBGAME_CACHE))
            _NATIVE_SUBGAME_CACHE.pop(oldest_key, None)
        _NATIVE_SUBGAME_CACHE[cache_key] = result
    return dict(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='cmd', required=True)
    subs.add_parser('build')
    p = subs.add_parser('train'); p.add_argument('--name', required=True)
    p.add_argument('--profile', choices=PROFILES, default='smoke'); p.add_argument('--threads', type=int, default=4)
    p.add_argument('--players', type=int, default=None)
    p = subs.add_parser('evaluate'); p.add_argument('--name', required=True)
    p.add_argument('--hands', type=int, default=12000); p.add_argument('--seeds', type=int, nargs='+', default=[11,29,47])
    p = subs.add_parser('benchmark'); p.add_argument('--name', required=True)
    p.add_argument('--br-hands', type=int, default=1000); p.add_argument('--lbr-hands', type=int, default=4000)
    p.add_argument('--aivat-hands', type=int, default=6000); p.add_argument('--seed', type=int, default=11)
    p = subs.add_parser('train-value-net'); p.add_argument('--name', required=True)
    p.add_argument('--samples', type=int, default=500); p.add_argument('--solve-iters', type=int, default=120)
    p.add_argument('--solve-ms', type=int, default=5000); p.add_argument('--hidden', default='256,256')
    p.add_argument('--epochs', type=int, default=40); p.add_argument('--seed', type=int, default=11)
    p = subs.add_parser('distill'); p.add_argument('--source', required=True); p.add_argument('--target', required=True)
    p.add_argument('--hands', type=int, default=400); p.add_argument('--search-ms', type=int, default=40)
    p.add_argument('--alpha', type=float, default=0.5); p.add_argument('--seed', type=int, default=11)
    p = subs.add_parser('crossplay'); p.add_argument('--focal', required=True); p.add_argument('--field', required=True)
    p.add_argument('--hands', type=int, default=24000); p.add_argument('--seed', type=int, default=11)
    p = subs.add_parser('ablate-safety'); p.add_argument('--spots', type=int, default=24)
    p.add_argument('--iters', type=int, default=250); p.add_argument('--seed', type=int, default=11)
    p.add_argument('--target', default='distilled-v1')
    p = subs.add_parser('review'); p.add_argument('--name', required=True); p.add_argument('--request', required=True)
    p.add_argument('--search-ms', type=int, default=0)
    args = parser.parse_args()
    try:
        if args.cmd == 'build': result = build()
        elif args.cmd == 'train': result = train(args.name,args.profile,args.threads,args.players)
        elif args.cmd == 'evaluate': result = evaluate(args.name,args.hands,args.seeds)
        elif args.cmd == 'benchmark': result = benchmark_exploitability(args.name,args.br_hands,args.lbr_hands,args.aivat_hands,args.seed)
        elif args.cmd == 'train-value-net': result = train_value_net(args.name,args.samples,args.solve_iters,args.solve_ms,args.hidden,args.epochs,seed=args.seed)
        elif args.cmd == 'distill': result = distill_model(args.source,args.target,args.hands,args.search_ms,args.alpha,seed=args.seed)
        elif args.cmd == 'crossplay': result = crossplay(args.focal,args.field,args.hands,args.seed)
        elif args.cmd == 'ablate-safety': result = ablate_safety(args.spots,args.iters,args.seed,args.target)
        else: result = review(args.name,args.request,args.search_ms)
        print(json.dumps(result,indent=2,allow_nan=False))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
