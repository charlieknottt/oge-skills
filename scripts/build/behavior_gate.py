#!/usr/bin/env python3
"""
behavior_gate.py - deterministic dynamic-behavior gate for an OGE world graph.

validate_graph.py / lint_taxonomy.py prove the graph is well-formed. This proves it
BEHAVES: it drives the graph with the same physics the runtime and the preview use
(engine.py) and confirms the graph does not go inert, pin to the rails, ring, or blow
up. No LLM, standard library only.

Checks:
  reachability    HARD  every non-lever/drifter node is reachable from a Lever or
                        Drifter (nothing inert, e.g. an unfunded Accumulator).
  boundedness     HARD  no NaN / out-of-[0,100] value across thousands of random plays.
  no_rail_pin     HARD  no node sits pinned at a 0/100 rail across more than
                        --rail-pin-max of random plays (signal loss).
  settles         HARD  after a single-lever impulse (no other input) the system
                        reaches a quasi-steady state (not still drifting at the end).
  no_oscillation  HARD  no node rings (repeated large direction reversals) under that
                        impulse -- the signature of a feedback loop with gain >= 1.
  frozen_in_play  WARN  a node that never moves under random play (usually redundant
                        with reachability; kept as a backstop).

Exit 0 = deployable; exit 1 = one or more HARD failures.

Usage:
  python3 behavior_gate.py world_graph.json
  python3 behavior_gate.py graph.json --runs 2000 --rounds 24 --impulse 25 --json report.json
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Engine

# random decision-stream generator (same tier distribution as the parked MC harness)
TIERS = {"T1": 3, "T2": 6, "T3": 11, "T4": 18}
TIER_KEYS, TIER_W = ["T1", "T2", "T3", "T4"], [4, 3, 2, 1]
EFF = [0.6, 1.0, 1.3]


def sample_game(eng, rounds, tpr, cap, teams, rng):
    """One random episode; returns per-round absolute-value states (length `rounds`)."""
    shocks = {}
    for r in range(rounds):
        b = shocks.setdefault(r * tpr, {})
        for _ in range(teams * cap):
            i = rng.choice(eng.ids)
            d = TIERS[rng.choices(TIER_KEYS, weights=TIER_W)[0]] * rng.choice(EFF) * rng.choice([-1, 1])
            b[i] = b.get(i, 0.0) + d
    traj = eng.run(shocks, rounds * tpr)
    return [traj[k * tpr] for k in range(1, rounds + 1)]


def _c(cid, status, evidence):
    return {"id": cid, "status": status, "evidence": evidence}


def reachability(graph):
    adj = {}
    for e in graph["edges"]:
        adj.setdefault(e["source"], []).append(e["target"])
    driven = [n["id"] for n in graph["nodes"] if n.get("type") in ("Lever", "Drifter")]
    seen, stack = set(driven), list(driven)
    while stack:
        for v in adj.get(stack.pop(), []):
            if v not in seen:
                seen.add(v)
                stack.append(v)
    inert = [n["id"] for n in graph["nodes"]
             if n.get("type") not in ("Lever", "Drifter") and n["id"] not in seen]
    ok = not inert
    return _c("reachability", "pass" if ok else "fail",
              "every node is driven by some lever/drifter path" if ok
              else f"{len(inert)} inert node(s) nothing in play can move: {', '.join(inert)}")


def random_play_checks(eng, games, rail_pin_hard, rail_pin_warn):
    ids = eng.ids
    oob = sum(1 for run in games for st in run for v in st.values()
              if v != v or v < -1e-6 or v > 100 + 1e-6)
    bounded = _c("boundedness", "pass" if oob == 0 else "fail",
                 "all values stayed in [0,100]" if oob == 0 else f"{oob} out-of-bounds/NaN values")
    # persistent rail pinning: fraction of node-rounds spent at a 0/100 rail (signal loss),
    # not a single transient touch. Hard-fail only if a node is stuck at a rail nearly always.
    rounds_total = sum(len(run) for run in games) or 1
    pin = {i: 0 for i in ids}
    for run in games:
        for st in run:
            for i in ids:
                if st[i] <= 1.0 or st[i] >= 99.0:
                    pin[i] += 1
    frac = {i: pin[i] / rounds_total for i in ids}
    hard = sorted(((i, frac[i]) for i in ids if frac[i] > rail_pin_hard), key=lambda x: -x[1])
    warns = sorted(((i, frac[i]) for i in ids if rail_pin_warn < frac[i] <= rail_pin_hard), key=lambda x: -x[1])
    if hard:
        rp = _c("no_rail_pin", "fail",
                "stuck at a rail most of the time: " + ", ".join(f"{i}={r:.0%}" for i, r in hard[:8]))
    elif warns:
        rp = _c("no_rail_pin", "warn",
                "often near a rail: " + ", ".join(f"{i}={r:.0%}" for i, r in warns[:8]))
    else:
        rp = _c("no_rail_pin", "pass", f"no node spends >{rail_pin_warn:.0%} of rounds pinned")
    moved = {i: False for i in ids}
    for run in games:
        for st in run:
            for i in ids:
                if abs(st[i] - eng.base[i]) > 5.0:
                    moved[i] = True
    frozen = [i for i in ids if not moved[i]]
    fz = _c("frozen_in_play", "pass" if not frozen else "warn",
            "every node moved under play" if not frozen else "never moved: " + ", ".join(frozen))
    return [bounded, rp, fz]


def impulse_checks(eng, amount, ticks, settle_eps, settle_tail, osc_delta, osc_max):
    levers = [i for i in eng.ids if eng.type[i] == "Lever"]
    if not levers:
        return [_c("settles", "warn", "no levers to impulse"),
                _c("no_oscillation", "warn", "no levers to impulse")]
    unsettled, ringing = [], []
    for lv in levers:
        traj = eng.run({0: {lv: amount}}, ticks)
        tail_move = max(abs(traj[t][i] - traj[t - 1][i])
                        for t in range(ticks - settle_tail + 1, ticks + 1) for i in eng.ids)
        if tail_move > settle_eps:
            unsettled.append((lv, tail_move))
        for i in eng.ids:
            deltas = [traj[t][i] - traj[t - 1][i] for t in range(1, ticks + 1)]
            sig = [1 if d > osc_delta else (-1 if d < -osc_delta else 0) for d in deltas]
            nz = [s for s in sig if s != 0]
            rev = sum(1 for a, b in zip(nz, nz[1:]) if a != b)
            if rev > osc_max:
                ringing.append((lv, i, rev))
    st = _c("settles", "pass" if not unsettled else "fail",
            "all single-lever impulses settle" if not unsettled
            else "still moving at end: " + ", ".join(f"{lv}(d{m:.1f})" for lv, m in unsettled[:6]))
    osc = _c("no_oscillation", "pass" if not ringing else "fail",
             "no ringing under impulse" if not ringing
             else "ringing: " + ", ".join(f"{i}@{lv}({r})" for lv, i, r in ringing[:6]))
    return [st, osc]


def main():
    ap = argparse.ArgumentParser(description="Deterministic dynamic-behavior gate for an OGE world graph.")
    ap.add_argument("graph")
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--rounds", type=int, default=24)
    ap.add_argument("--tpr", type=int, default=6)
    ap.add_argument("--teams", type=int, default=4)
    ap.add_argument("--cap", type=int, default=3)
    ap.add_argument("--impulse", type=float, default=25.0)
    ap.add_argument("--impulse-ticks", type=int, default=120)
    ap.add_argument("--rail-pin-hard", type=float, default=0.8)
    ap.add_argument("--rail-pin-warn", type=float, default=0.4)
    ap.add_argument("--settle-eps", type=float, default=1.5)
    ap.add_argument("--settle-tail", type=int, default=6)
    ap.add_argument("--osc-delta", type=float, default=0.3)
    ap.add_argument("--osc-max", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    eng = Engine(graph)
    rng = random.Random(args.seed)
    games = [sample_game(eng, args.rounds, args.tpr, args.cap, args.teams, rng) for _ in range(args.runs)]

    checks = [reachability(graph)]
    checks += random_play_checks(eng, games, args.rail_pin_hard, args.rail_pin_warn)
    checks += impulse_checks(eng, args.impulse, args.impulse_ticks,
                             args.settle_eps, args.settle_tail, args.osc_delta, args.osc_max)

    hard_fail = sum(1 for c in checks if c["status"] == "fail")
    warn = sum(1 for c in checks if c["status"] == "warn")
    ok = hard_fail == 0
    report = {"graph": args.graph, "deployable": ok, "n_fail": hard_fail, "n_warn": warn,
              "method": f"random-play n={args.runs}x{args.rounds}, "
                        f"impulse={args.impulse}x{args.impulse_ticks}t, seed={args.seed}",
              "checks": checks}
    if args.json_out:
        json.dump(report, open(args.json_out, "w"), indent=2)

    print(f"{'PASS' if ok else 'FAIL'}  {args.graph}  ({len(graph['nodes'])} nodes)  "
          f"{hard_fail} hard fail(s), {warn} warning(s)")
    for c in checks:
        mark = {"pass": "  ok ", "warn": " warn", "fail": " FAIL"}[c["status"]]
        print(f"{mark}  {c['id']:16} {c['evidence']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
