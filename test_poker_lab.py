import json
import sys
from pathlib import Path

import pytest
import poker_lab


def test_eval_units_are_big_blinds_per_hundred():
    r = poker_lab.parse_eval('winrate: +123.4 mbb/hand (95% CI ±50.0) over 12000 hands in 1.0s')
    assert r['bb_per_100'] == pytest.approx(12.34)
    assert r['ci95_halfwidth'] == 5
    assert r['hands'] == 12000


@pytest.mark.parametrize('name',['../escape','/absolute','bad name','x'*65,''])
def test_run_names_cannot_escape_model_directory(name):
    with pytest.raises(ValueError): poker_lab.run_dir(name)


def test_failed_process_is_not_reported_success(tmp_path):
    log = tmp_path/'failed.log'
    with pytest.raises(RuntimeError,match='exited 3'):
        poker_lab.bounded_run([sys.executable,'-c','raise SystemExit(3)'], log)


def test_process_timeout_preserves_log(tmp_path):
    log = tmp_path/'timeout.log'
    with pytest.raises(RuntimeError,match='exceeded'):
        poker_lab.bounded_run([sys.executable,'-u','-c','import time; print("started"); time.sleep(10)'],
                              log, timeout=.5)
    assert 'started' in log.read_text()


def test_model_rejects_modified_blueprint(tmp_path,monkeypatch):
    monkeypatch.setattr(poker_lab,'RUNS',tmp_path)
    d=tmp_path/'candidate'; d.mkdir(); (d/'blueprint.bin').write_bytes(b'changed')
    (d/'manifest.json').write_text(json.dumps({'status':'trained','game':poker_lab.GAME,'blueprint_sha256':'old'}))
    with pytest.raises(ValueError,match='hash differs'): poker_lab.model('candidate')


def test_review_native_start_when_smoke_model_is_available(tmp_path):
    # Optional integration test; unit tests above work without Rust/models.
    if not (poker_lab.RUNS/'smoke-v1'/'manifest.json').exists():
        pytest.skip('Run python3 poker_lab.py train --name smoke-v1 first')
    req=tmp_path/'request.json'
    req.write_text(json.dumps({'players':6,'button':0,'hero':3,'hole':['As','Kd'],'board':[],
                             'actions':[],'expected_pot':150,'expected_stacks':[10000,9950,9900,10000,10000,10000]}))
    r=poker_lab.review('smoke-v1',req,0)
    assert r['status'] in ('candidate','uncovered')
    assert r['strength']=='unvalidated'
    if r['status']=='candidate':
        assert sum(x['probability'] for x in r['actions']) == pytest.approx(1)


def test_review_rejects_inconsistent_state_when_smoke_model_available(tmp_path):
    if not (poker_lab.RUNS/'smoke-v1'/'manifest.json').exists():
        pytest.skip('Smoke model unavailable')
    req=tmp_path/'request.json'
    req.write_text(json.dumps({'players':6,'button':0,'hero':3,'hole':['As','Kd'],'board':[],
                             'actions':[],'expected_pot':999,'expected_stacks':[10000,9950,9900,10000,10000,10000]}))
    r=poker_lab.review('smoke-v1',req,0)
    assert r['status']=='unavailable'
    assert 'reconcile' in r['error']


def test_parse_probe_extracts_br_and_lbr_metrics():
    br = poker_lab.parse_probe('BR probe wins +245.0 mbb/hand (95% CI ±32.5) over 1000 hands in 1.2s')
    assert br['bb_per_100'] == pytest.approx(24.5)
    assert br['ci95_halfwidth'] == pytest.approx(3.25)
    assert br['hands'] == 1000
    lbr = poker_lab.parse_probe('LBR wins -12.0 mbb/hand (95% CI ±18.0) over 4000 hands in 2.0s')
    assert lbr['bb_per_100'] == pytest.approx(-1.2)
    assert lbr['ci95_halfwidth'] == pytest.approx(1.8)
    assert lbr['hands'] == 4000


def test_parse_value_net_and_distill_outputs():
    td = poker_lab.parse_turn_data('wrote 300 samples to turn_data.bin in 4.2s')
    assert td == {'samples': 300, 'engine_seconds': 4.2}
    vn = poker_lab.parse_value_net('value net saved to value_net.bin (final val loss 0.01425, 3s)')
    assert vn['val_loss'] == pytest.approx(0.01425)
    ds = poker_lab.parse_distill(
        'collected 1420 searched decisions at 980 infosets in 12.3s\n'
        'updated 980 infosets (0 skipped on menu mismatch); distilled blueprint saved to out.bin (15956500 strategies)'
    )
    assert ds['searched_decisions'] == 1420
    assert ds['updated_infosets'] == 980
    assert ds['skipped_infosets'] == 0
    assert ds['total_strategies'] == 15956500


def test_synthesize_review_request_reconciles_across_streets():
    if not poker_lab.best_available_model():
        pytest.skip('No trained blueprint available')
    poker_lab.clear_native_subgame_cache()
    for cfg in (
        dict(hero_hand='AsKd', board='', pot_size=150, call_amount=100, spot={'kind': 'open', 'pos': 'UTG'}),
        dict(hero_hand='AhKh', board='QdJd2s', pot_size=300, call_amount=0, spot={'kind': 'open', 'pos': 'BTN'}),
        dict(hero_hand='AhKh', board='QdJd2s', pot_size=450, call_amount=150, spot={'kind': 'facing_open', 'pos': 'BB', 'vs': 'BTN'}),
        dict(hero_hand='AhKh', board='QdJd2s5c', pot_size=600, call_amount=200, spot={'kind': 'open', 'pos': 'BTN'}),
        dict(hero_hand='AhKh', board='QdJd2s5c9h', pot_size=800, call_amount=400, spot={'kind': 'open', 'pos': 'BTN'}),
    ):
        res = poker_lab.query_native_subgame(**cfg, search_ms=20)
        assert res['status'] in ('candidate', 'uncovered')
        assert sum(res['cfr_frequencies'].values()) == 100
        assert res.get('cached') is False
        cached_res = poker_lab.query_native_subgame(**cfg, search_ms=20)
        assert cached_res.get('cached') is True
        assert cached_res['cfr_frequencies'] == res['cfr_frequencies']


def test_parse_crossplay_and_ablate_safety():
    cp = poker_lab.parse_crossplay('focal winrate: +267.5 mbb/hand (95% CI ±1116.2) over 24000 hands')
    assert cp['bb_per_100'] == pytest.approx(26.75)
    assert cp['ci95_halfwidth'] == pytest.approx(111.62)
    assert cp['hands'] == 24000

    ablate_out = (
        'safety ablation: 24 random river spots, 250 CFR iters/solve...\n\n'
        'epsilon    unsafe mean   unsafe max   safe mean   safe max       pot\n'
        '0.25               3.0         85.6         1.5       21.0      2083\n'
        '0.5                4.8        117.9         1.6       15.0      2083\n'
        '1                  9.8        317.4         1.7       42.7      2083\n'
    )
    rows = poker_lab.parse_ablate_safety(ablate_out)
    assert len(rows) == 3
    assert rows[0]['epsilon'] == pytest.approx(0.25)
    assert rows[2]['unsafe_max_chips'] == pytest.approx(317.4)
    assert rows[2]['safe_mean_chips'] == pytest.approx(1.7)


def test_persistent_worker_and_value_net_and_preflop_queries():
    if not poker_lab.best_available_model():
        pytest.skip('No trained blueprint available')
    poker_lab.clear_native_subgame_cache()

    # 1. Preflop query with canonical hand ('AKs') and facing_3bet / facing_4bet spots
    for spot_cfg in (
        {'kind': 'open', 'pos': 'CO'},
        {'kind': 'facing_open', 'pos': 'BTN', 'vs': 'CO'},
        {'kind': 'facing_3bet', 'pos': 'CO', 'vs': 'BTN'},
        {'kind': 'facing_4bet', 'pos': 'BTN', 'vs': 'CO'},
    ):
        pre = poker_lab.query_native_preflop('AKs', spot=spot_cfg, use_cache=False)
        assert pre['status'] in ('candidate', 'uncovered')
        assert sum(pre['cfr_frequencies'].values()) == 100
        assert pre.get('worker_mode') is True

    # 2. Flop query with ReBeL value_net loaded via persistent worker
    obs_actions = [
        {'pos': 'CO', 'action': 'raise_to', 'amount_bb': 2.5},
        {'pos': 'BTN', 'action': 'call', 'amount_bb': 2.5},
    ]
    flop_res = poker_lab.query_native_subgame(
        hero_hand='AhKh',
        board='QdJd2s',
        pot_size=650,
        call_amount=0,
        spot={'kind': 'facing_open', 'pos': 'BTN', 'vs': 'CO'},
        in_position=True,
        search_ms=25,
        observed_actions=obs_actions,
        use_cache=False,
    )
    assert flop_res['status'] in ('candidate', 'uncovered')
    assert flop_res.get('worker_mode') is True
    assert flop_res.get('value_net_loaded') is True
    assert sum(flop_res['cfr_frequencies'].values()) == 100


def test_multi_street_postflop_history_reconciliation_and_vpip_and_hu_models():
    if not poker_lab.best_available_model():
        pytest.skip('No trained blueprint available')
    poker_lab.clear_native_subgame_cache()

    # 1. Multi-street postflop_history reconciliation on Turn and River
    post_hist = [
        {'street': 'flop', 'action': 'bet_call', 'amount_bb': 2.0},
        {'street': 'turn', 'action': 'bet_call', 'amount_bb': 4.0},
    ]
    river_res = poker_lab.query_native_subgame(
        hero_hand='AhKh',
        board='QdJd2s5c9h',
        pot_size=2200,
        call_amount=400,
        spot={'kind': 'facing_open', 'pos': 'BTN', 'vs': 'CO'},
        in_position=True,
        search_ms=20,
        postflop_history=post_hist,
        use_cache=False,
    )
    assert river_res['status'] in ('candidate', 'uncovered')
    assert sum(river_res['cfr_frequencies'].values()) == 100
    # Verify flop and turn raise_to+call actions were replayed into the engine request
    raise_actions = [a for a in river_res['request']['actions'] if a['action'] == 'raise_to']
    assert len(raise_actions) >= 4  # preflop open + flop bet + turn bet + river bet

    # 2. Automatic VPIP model routing (loose-passive caller >= 40% VPIP -> rnr-caller-v1)
    if (poker_lab.RUNS / 'rnr-caller-v1' / 'manifest.json').exists():
        assert poker_lab.select_model_for_opponent(opponent_vpip=48.0) == 'rnr-caller-v1'
        assert poker_lab.select_model_for_opponent(opponent_vpip=22.0) in ('distilled-v1', 'ochs-vr-v1')
        rnr_res = poker_lab.query_native_subgame(
            hero_hand='AhKh',
            board='QdJd2s',
            pot_size=500,
            call_amount=150,
            spot={'kind': 'open', 'pos': 'BTN'},
            opponent_vpip=50.0,
            search_ms=15,
            use_cache=False,
        )
        assert rnr_res['status'] in ('candidate', 'uncovered')
        assert rnr_res['model_name'] == 'rnr-caller-v1'
        assert sum(rnr_res['cfr_frequencies'].values()) == 100

    # 3. 2-Player Heads-Up blueprint (hu-v1) synthesis and querying
    if (poker_lab.RUNS / 'hu-v1' / 'manifest.json').exists():
        assert poker_lab.select_model_for_opponent(players=2) == 'hu-v1'
        hu_pre = poker_lab.query_native_preflop(
            'AKs',
            spot={'kind': 'open', 'pos': 'BTN', 'players': 2},
            players=2,
            use_cache=False,
        )
        assert hu_pre['status'] in ('candidate', 'uncovered')
        assert hu_pre['model_name'] == 'hu-v1'
        assert hu_pre['request']['players'] == 2
        assert sum(hu_pre['cfr_frequencies'].values()) == 100

        hu_flop = poker_lab.query_native_subgame(
            hero_hand='AhKh',
            board='QdJd2s',
            pot_size=500,
            call_amount=150,
            spot={'kind': 'open', 'pos': 'BTN'},
            players=2,
            search_ms=15,
            use_cache=False,
        )
        assert hu_flop['status'] in ('candidate', 'uncovered')
        assert hu_flop['model_name'] == 'hu-v1'
        assert hu_flop['request']['players'] == 2
        assert sum(hu_flop['cfr_frequencies'].values()) == 100


