//! Structured study/replay boundary. No OCR guesses, network calls or clicks.
use crate::abstraction::Abstraction;
use crate::bot::{Policy, SearchParams, SearchSession};
use crate::cards::{parse_card, Card};
use crate::cfr::{Blueprint, TrainConfig};
use crate::engine::{HandConfig, PlayerAction};
use crate::search::RangeTracker;
use crate::table::Table;
use rand::{SeedableRng, seq::SliceRandom, rngs::SmallRng};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub players: usize,
    pub button: usize,
    pub hero: usize,
    pub hole: [String; 2],
    pub board: Vec<String>,
    pub actions: Vec<Action>,
    /// Current pot and stacks must reconcile against the action history.
    pub expected_pot: u32,
    pub expected_stacks: Vec<u32>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Action {
    pub seat: usize,
    pub action: String,
    pub amount: Option<u32>,
}

fn parse_known(r: &Request) -> Result<(Vec<Card>, Vec<Card>), String> {
    if !(2..=6).contains(&r.players) || r.hero >= r.players || r.button >= r.players {
        return Err("Invalid player count, hero or button".into());
    }
    if ![0, 3, 4, 5].contains(&r.board.len()) || r.actions.len() > 200 {
        return Err("Invalid board length or excessive action history".into());
    }
    let hole: Vec<_> = r.hole.iter().map(|s| parse_card(s).ok_or("Invalid hole card".to_string())).collect::<Result<_, _>>()?;
    let board: Vec<_> = r.board.iter().map(|s| parse_card(s).ok_or("Invalid board card".to_string())).collect::<Result<_, _>>()?;
    let mut seen = [false; 52];
    for &c in hole.iter().chain(board.iter()) {
        if seen[c as usize] { return Err("Duplicate known cards".into()); }
        seen[c as usize] = true;
    }
    Ok((hole, board))
}

fn legal_action(table: &Table, event: &Action) -> Result<PlayerAction, String> {
    let h = &table.real;
    if h.is_terminal() || h.to_act() != event.seat {
        return Err("Action history has an incorrect actor or continues after hand end".into());
    }
    match event.action.as_str() {
        "fold" if !h.can_check() && event.amount.is_none() => Ok(PlayerAction::Fold),
        "check" if h.can_check() && event.amount.is_none() => Ok(PlayerAction::CheckCall),
        "call" if !h.can_check() && event.amount.is_none() => Ok(PlayerAction::CheckCall),
        "raise_to" => {
            let amount = event.amount.ok_or("raise_to requires a street-total amount")?;
            let (lo, hi) = h.raise_bounds().ok_or("Raising is not legal")?;
            if amount < lo || amount > hi { return Err("Raise amount outside legal bounds".into()); }
            Ok(PlayerAction::RaiseTo(amount))
        },
        _ => Err("Illegal action; use fold, check, call or raise_to".into()),
    }
}

fn rebuild(r: &Request, policy: &Policy) -> Result<(Table, RangeTracker), String> {
    let (hole, board) = parse_known(r)?;
    if r.players != policy.blueprint.num_players {
        return Err("Blueprint player count does not match request".into());
    }
    // This protocol deliberately supports the training default only: equal
    // 100bb starting stacks, 50/100 blinds, no rake or antes. Metadata is
    // verified by the Python entry point before loading the binary artifact.
    let cfg = HandConfig { num_players: r.players, ..HandConfig::default() };
    let mut slots = [None; 52];
    slots[2 * r.hero] = Some(hole[0]);
    slots[2 * r.hero + 1] = Some(hole[1]);
    for (i, &c) in board.iter().enumerate() { slots[2 * r.players + i] = Some(c); }
    let mut remaining: Vec<u8> = (0..52).filter(|c| !hole.contains(c) && !board.contains(c)).collect();
    remaining.shuffle(&mut SmallRng::seed_from_u64(71));
    let mut available = remaining.into_iter();
    let deck = std::array::from_fn(|i| slots[i].unwrap_or_else(|| available.next().unwrap()));
    let mut table = Table::new(&cfg, r.button, deck);
    let mut tracker = RangeTracker::new(r.players).with_widening();
    for event in &r.actions {
        let action = legal_action(&table, event)?;
        let old_len = table.real.board().len();
        let abstract_action = table.map_concrete(action, &policy.abs);
        tracker.observe(event.seat, abstract_action, &table.shadow, &table.hist, &policy.blueprint, &policy.abs);
        table.apply_concrete(action, &policy.abs);
        let public = table.real.board();
        if public.len() > board.len() {
            return Err("History requires board cards missing from request".into());
        }
        if public.len() > old_len { tracker.exclude(&public[old_len..]); }
    }
    if table.real.is_terminal() || table.real.to_act() != r.hero {
        return Err("Request is not an active decision for Hero".into());
    }
    if table.real.board() != board.as_slice() {
        return Err("Board does not match betting history".into());
    }
    let stacks: Vec<_> = (0..r.players).map(|p| table.real.stack(p)).collect();
    if table.real.pot() != r.expected_pot || stacks != r.expected_stacks {
        return Err("Pot or stacks do not reconcile with the complete action history".into());
    }
    Ok((table, tracker))
}

#[derive(Deserialize)]
#[serde(untagged)]
enum WorkerLine {
    Wrapped {
        request: Request,
        search_ms: Option<u64>,
        search_iters: Option<u64>,
    },
    Direct(Request),
}

pub fn load_review_policy(blueprint: &str, value_net: Option<&str>) -> Result<Policy, String> {
    let bp = Blueprint::load(blueprint).map_err(|e| e.to_string())?;
    let abs = Arc::new(Abstraction::with_centroids(bp.abs_cfg.clone(), bp.centroids.clone()));
    let net = match value_net {
        Some(p) => Some(Arc::new(crate::valuenet::ValueNet::load(p).map_err(|e| e.to_string())?)),
        None => None,
    };
    Ok(Policy::new(bp, abs).with_value_net(net))
}

pub fn evaluate_request(
    policy: &Policy,
    r: &Request,
    search_ms: u64,
    search_iters: u64,
) -> Result<Value, String> {
    if search_ms > 10_000 || search_iters == 0 || search_iters > 2_000_000 {
        return Err("Search budget outside supported bounds".into());
    }
    parse_known(r)?;
    let (table, tracker) = rebuild(r, policy)?;
    let mut rng = SmallRng::seed_from_u64(5);
    let bucket = policy.abs.bucket(table.shadow.hole(r.hero), table.shadow.board(), &mut rng);
    let menu = policy.abs.abstract_actions(&table.shadow);
    let covered = policy.blueprint.get(bucket, &table.hist)
        .map(|p| p.len() == menu.len() && p.iter().all(|v| v.is_finite() && *v >= 0.) && p.iter().sum::<f32>() > 0.)
        .unwrap_or(false);
    let has_value_net = policy.value_net.is_some();
    // Unseen states otherwise silently become 100% check/call upstream.
    if !covered && search_ms == 0 {
        return Ok(json!({"status":"uncovered", "actions":[], "blueprint_covered":false,
                         "value_net_loaded":has_value_net,
                         "strength":"unvalidated", "training_iterations":policy.blueprint.iterations}));
    }
    let (actions, probabilities) = if search_ms > 0 {
        let cfg = TrainConfig { hand: HandConfig { num_players:r.players, ..HandConfig::default() }, ..TrainConfig::default() };
        policy.search_dist(&table.real, &table.shadow, &table.hist,
            SearchParams { time_ms:search_ms, max_iters:search_iters, safe_resolve:true, ..SearchParams::default() },
            &cfg, Some(&tracker), Some(&mut SearchSession::new()), Some(&table.round), &mut rng)
    } else { policy.blueprint_dist(&table.shadow, &table.hist, &mut rng) };
    if probabilities.len() != actions.len() || probabilities.iter().any(|p| !p.is_finite() || *p < 0.)
        || (probabilities.iter().sum::<f64>() - 1.).abs() > 1e-5 {
        return Err("Engine returned an invalid distribution".into());
    }
    // Search can fall back to the blueprint, so an uncovered result is never
    // presented as validated just because a search budget was requested.
    let distribution: Vec<Value> = actions.iter().zip(probabilities.iter()).map(|(a,p)| {
        let concrete = match a {
            crate::abstraction::AbsAction::Bet(_) | crate::abstraction::AbsAction::AllIn
                if table.real.raise_bounds().is_none() => PlayerAction::CheckCall,
            _ => policy.abs.concrete(&table.real,*a),
        };
        match concrete {
            PlayerAction::Fold => json!({"action":"fold", "probability":p}),
            PlayerAction::CheckCall => json!({"action":if table.real.can_check(){"check"}else{"call"},"probability":p}),
            PlayerAction::RaiseTo(amount) => json!({"action":"raise_to","amount":amount,"probability":p}),
        }
    }).collect();
    Ok(json!({"status":if covered {"candidate"} else {"uncovered"},
              "actions":distribution, "blueprint_covered":covered,
              "value_net_loaded":has_value_net,
              "training_iterations":policy.blueprint.iterations,
              "search_requested_ms":search_ms, "strength":"unvalidated",
              "game":{"players":r.players,"starting_stack":10000,"small_blind":50,"big_blind":100,"rake":0},
              "pot":table.real.pot(),"to_call":table.real.to_call()}))
}

pub fn run(
    blueprint: &str,
    request: &str,
    search_ms: u64,
    search_iters: u64,
    value_net: Option<&str>,
) -> Result<Value, String> {
    if search_ms > 10_000 || search_iters == 0 || search_iters > 2_000_000 {
        return Err("Search budget outside supported bounds".into());
    }
    let bytes = std::fs::read(request).map_err(|e| e.to_string())?;
    if bytes.len() > 100_000 { return Err("Request too large".into()); }
    let r: Request = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    parse_known(&r)?;
    let policy = load_review_policy(blueprint, value_net)?;
    evaluate_request(&policy, &r, search_ms, search_iters)
}

pub fn serve(
    blueprint: &str,
    value_net: Option<&str>,
    default_search_ms: u64,
    default_search_iters: u64,
) -> Result<(), String> {
    use std::io::{BufRead, Write};
    let policy = load_review_policy(blueprint, value_net)?;
    let stdin = std::io::stdin();
    let mut stdout = std::io::stdout();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(e) => return Err(e.to_string()),
        };
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        if trimmed.len() > 100_000 {
            let _ = writeln!(stdout, "{}", json!({"status": "unavailable", "error": "Request too large"}));
            let _ = stdout.flush();
            continue;
        }
        let resp = match serde_json::from_str::<WorkerLine>(trimmed) {
            Ok(WorkerLine::Wrapped { request, search_ms, search_iters }) => {
                evaluate_request(
                    &policy,
                    &request,
                    search_ms.unwrap_or(default_search_ms),
                    search_iters.unwrap_or(default_search_iters),
                )
            }
            Ok(WorkerLine::Direct(request)) => {
                evaluate_request(&policy, &request, default_search_ms, default_search_iters)
            }
            Err(e) => Err(e.to_string()),
        };
        match resp {
            Ok(val) => {
                let _ = writeln!(stdout, "{}", val);
            }
            Err(err) => {
                let _ = writeln!(stdout, "{}", json!({"status": "unavailable", "error": err}));
            }
        }
        let _ = stdout.flush();
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn request() -> Request {
        serde_json::from_value(json!({"players":6,"button":0,"hero":3,"hole":["As","Kd"],
          "board":[],"actions":[],"expected_pot":150,
          "expected_stacks":[10000,9950,9900,10000,10000,10000]})).unwrap()
    }
    fn policy() -> Policy {
        let abs = Arc::new(Abstraction::new(crate::abstraction::AbsConfig::default()));
        Policy::new(crate::cfr::Trainer::new(abs.clone(),TrainConfig::default()).to_blueprint(),abs)
    }
    #[test] fn accepts_reconciled_start() { assert!(rebuild(&request(),&policy()).is_ok()); }
    #[test] fn rejects_wrong_pot() { let mut r=request();r.expected_pot=151;assert!(rebuild(&r,&policy()).is_err()); }
    #[test] fn rejects_duplicate_cards() { let mut r=request();r.hole[1]="As".into();assert!(parse_known(&r).is_err()); }
    #[test] fn rejects_wrong_actor() { let mut r=request();r.actions.push(Action{seat:4,action:"fold".into(),amount:None});assert!(rebuild(&r,&policy()).is_err()); }
    #[test] fn rejects_illegal_raise() { let mut r=request();r.actions.push(Action{seat:3,action:"raise_to".into(),amount:Some(101)});assert!(rebuild(&r,&policy()).is_err()); }
    #[test] fn worker_line_parses_both_wrapped_and_direct() {
        let direct: WorkerLine = serde_json::from_value(json!({
            "players":6,"button":0,"hero":3,"hole":["As","Kd"],
            "board":[],"actions":[],"expected_pot":150,
            "expected_stacks":[10000,9950,9900,10000,10000,10000]
        })).unwrap();
        assert!(matches!(direct, WorkerLine::Direct(_)));
        let wrapped: WorkerLine = serde_json::from_value(json!({
            "request": {"players":6,"button":0,"hero":3,"hole":["As","Kd"],
                        "board":[],"actions":[],"expected_pot":150,
                        "expected_stacks":[10000,9950,9900,10000,10000,10000]},
            "search_ms": 25,
            "search_iters": 5000
        })).unwrap();
        assert!(matches!(wrapped, WorkerLine::Wrapped { search_ms: Some(25), search_iters: Some(5000), .. }));
    }
    #[test] fn evaluate_request_reports_value_net_flag() {
        let pol = policy();
        let val = evaluate_request(&pol, &request(), 0, 1000).unwrap();
        assert_eq!(val["value_net_loaded"], json!(false));
    }
    #[test] fn accepts_reconciled_heads_up_request() {
        let abs = Arc::new(Abstraction::new(crate::abstraction::AbsConfig::default()));
        let cfg = TrainConfig { hand: HandConfig { num_players: 2, ..HandConfig::default() }, ..TrainConfig::default() };
        let pol = Policy::new(crate::cfr::Trainer::new(abs.clone(), cfg).to_blueprint(), abs);
        let hu_req: Request = serde_json::from_value(json!({
            "players": 2,
            "button": 0,
            "hero": 1,
            "hole": ["As", "Kd"],
            "board": ["Qh", "Jc", "2s"],
            "actions": [
                {"seat": 0, "action": "raise_to", "amount": 250},
                {"seat": 1, "action": "call", "amount": null}
            ],
            "expected_pot": 500,
            "expected_stacks": [9750, 9750]
        })).unwrap();
        assert!(rebuild(&hu_req, &pol).is_ok());
    }
}
