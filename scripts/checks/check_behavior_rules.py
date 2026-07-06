#!/usr/bin/env python3
"""
check_behavior_rules.py - run the behavior rules against the simulation (the step that makes them bite).

It plays the graph forward thousands of times with the same physics the runtime uses (engine.py) and
checks each rule against the playthroughs:
  - shouldnt_coexist: how often the forbidden combination actually shows up (a violation rate).
  - should_follow:    how often the expected effect fails to follow the trigger (a miss rate).
A rule broken more than its allowed rate FAILS. No LLM: the pass/fail is a number from the sim.

What a failure means, by the rule's confidence:
  - high        -> the graph is probably wrong; the caller should send it back to be rebuilt.
  - medium/low  -> put it on a short human list; a person decides.
A should_follow rule whose trigger never occurs is reported 'not exercised' (a note, not a fail).

Reads behavior_rules.json (written by validate_behavior_rules.py). Each rule expression is
re-validated here before it is evaluated, so a hand-edited or malformed rules file degrades to an
'invalid' note instead of crashing, and eval only ever sees a safe true/false test (no builtins).

Exit 0 = ran, no high-confidence failure. Exit 1 = a high-confidence failure (rebuild needed).
Exit 2 = no rules could be evaluated (all invalid or none triggered) -- fix the rules file.

Usage:
  python3 check_behavior_rules.py world_graph.json --rules behavior_rules.json
      [--runs 2000 --rounds 24 --tpr 6 --teams 4 --cap 3 --seed 7] [--out report.json]
"""
import argparse
import ast
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                                  # for validate_behavior_rules (sibling)
sys.path.insert(0, os.path.join(HERE, "..", "build"))    # for engine
from engine import Engine, sample_game
from validate_behavior_rules import expr_ok               # re-validate expressions before eval


def names_in(expr):
    return {n.id for n in ast.walk(ast.parse(expr, mode="eval")) if isinstance(n, ast.Name)}


def ev(code, state):
    return bool(eval(code, {"__builtins__": {}}, state))


def run_shouldnt_coexist(code, runs):
    total = viol = 0
    for run in runs:
        for st in run:
            total += 1
            if ev(code, st):
                viol += 1
    rate = viol / total if total else 0.0
    return rate, f"the forbidden combination held in {viol}/{total} rounds ({rate:.1%})"


def run_should_follow(when_code, then_code, within, runs):
    # Only count a trigger if the full observation window fits before the episode ends; otherwise a
    # late trigger whose effect would land after the last round is wrongly scored a miss. The window
    # includes the trigger round r itself (a state-consistency reading of "within N rounds").
    qual = miss = 0
    for run in runs:
        n = len(run)
        for r in range(n):
            if r + within >= n:
                break
            if ev(when_code, run[r]):
                qual += 1
                if not any(ev(then_code, run[j]) for j in range(r, r + within + 1)):
                    miss += 1
    if qual == 0:
        return None, "the trigger never occurred with a full window in play (rule not exercised)"
    rate = miss / qual
    return rate, f"the effect failed to follow in {miss}/{qual} trigger cases ({rate:.1%})"


def evaluate(rule, ids, runs):
    """Return a result dict for one rule. Never raises: a bad rule becomes an 'invalid' result."""
    if not isinstance(rule, dict):
        return {"id": None, "kind": None, "confidence": None, "why": None, "involved_nodes": [],
                "metric": None, "value": None, "limit": None, "status": "invalid",
                "evidence": "rule is not an object"}
    rid, kind, conf = rule.get("id"), rule.get("kind"), rule.get("confidence")
    base = {"id": rid, "kind": kind, "confidence": conf, "why": rule.get("why"), "involved_nodes": [],
            "metric": None, "value": None, "limit": None}
    if conf not in ("high", "medium", "low"):
        # confidence drives the action (rebuild vs human), so a bad value can't be trusted
        return {**base, "status": "invalid", "evidence": f"confidence must be high/medium/low (got {conf!r})"}
    if kind == "shouldnt_coexist":
        exprs = [rule.get("never")]
    elif kind == "should_follow":
        exprs = [rule.get("when"), rule.get("then")]
    else:
        return {**base, "status": "invalid", "evidence": f"unknown kind '{kind}'"}

    # Re-validate every expression against THIS graph before evaluating it. This is defense in depth:
    # the rules file may have been hand-edited, and eval must only ever see a safe true/false test of
    # real node ids (no division, calls, lambda, walrus, or unknown names).
    for e in exprs:
        ok, why = expr_ok(e, ids)
        if not ok:
            return {**base, "status": "invalid", "evidence": f"rule expression rejected: {why}"}
    base["involved_nodes"] = sorted(set().union(*[names_in(e) for e in exprs]) & ids)

    try:
        if kind == "shouldnt_coexist":
            limit = float(rule["max_rate"])
            rate, ev_txt = run_shouldnt_coexist(compile(rule["never"], "<r>", "eval"), runs)
            return {**base, "status": "pass" if rate <= limit else "fail", "metric": "violation_rate",
                    "value": round(rate, 4), "limit": limit, "evidence": ev_txt}
        within = int(rule["within_rounds"])
        limit = float(rule["max_miss_rate"])
        rate, ev_txt = run_should_follow(compile(rule["when"], "<r>", "eval"),
                                         compile(rule["then"], "<r>", "eval"), within, runs)
        if rate is None:
            return {**base, "status": "not_exercised", "metric": "miss_rate", "value": None,
                    "limit": limit, "evidence": ev_txt}
        return {**base, "status": "pass" if rate <= limit else "fail", "metric": "miss_rate",
                "value": round(rate, 4), "limit": limit, "evidence": ev_txt}
    except Exception as ex:  # a missing/garbage max_rate, within_rounds, etc. in a hand-edited file
        return {**base, "status": "invalid", "evidence": f"could not evaluate ({type(ex).__name__}: {ex})"}


def main():
    ap = argparse.ArgumentParser(description="Run the behavior rules against the simulation.")
    ap.add_argument("graph")
    ap.add_argument("--rules", required=True, help="behavior_rules.json from validate_behavior_rules.py")
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--rounds", type=int, default=24)
    ap.add_argument("--tpr", type=int, default=6)
    ap.add_argument("--teams", type=int, default=4)
    ap.add_argument("--cap", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    ids = {n["id"] for n in graph.get("nodes", []) if isinstance(n, dict) and "id" in n}
    rules = json.load(open(args.rules)).get("rules", [])
    eng = Engine(graph)
    rng = random.Random(args.seed)
    runs = [sample_game(eng, args.rounds, args.tpr, args.cap, args.teams, rng) for _ in range(args.runs)]

    results = [evaluate(r, ids, runs) for r in rules]
    fails = [r for r in results if r["status"] == "fail"]
    high = [r for r in fails if r["confidence"] == "high"]
    human = [r for r in fails if r["confidence"] in ("medium", "low")]
    not_ex = [r for r in results if r["status"] == "not_exercised"]
    invalid = [r for r in results if r["status"] == "invalid"]

    report = {
        "graph": args.graph, "runs": args.runs, "rounds": args.rounds, "n_rules": len(rules),
        "n_pass": sum(1 for r in results if r["status"] == "pass"),
        "n_fail": len(fails), "n_high_fail": len(high),
        "n_not_exercised": len(not_ex), "n_invalid": len(invalid),
        "rebuild_needed": bool(high),
        "rebuild_brief": [{"rule": r["id"], "why": r["why"], "evidence": r["evidence"],
                           "reexamine_nodes": r["involved_nodes"]} for r in high],
        "human_review": [{"rule": r["id"], "confidence": r["confidence"], "evidence": r["evidence"]}
                         for r in human],
        "results": results,
    }
    if args.out:
        json.dump(report, open(args.out, "w"), indent=2)

    print(f"behavior-rule check on {args.graph} -- {args.runs} playthroughs x {args.rounds} rounds")
    order = {"fail": 0, "not_exercised": 1, "invalid": 2, "pass": 3}
    mark = {"pass": "  ok ", "fail": " FAIL", "not_exercised": " n/ex", "invalid": " inv "}
    for r in sorted(results, key=lambda x: order.get(x["status"], 9)):
        v = r.get("value")
        vtxt = f"{v:.1%}" if isinstance(v, float) else "-"
        print(f"{mark.get(r['status'], ' ??? ')} [{str(r['confidence'] or '?'):6}] {str(r['id']):34} "
              f"{r.get('metric') or '':14} {vtxt:>6}  {r['evidence']}")
    print(f"\n{report['n_pass']} pass / {len(fails)} fail ({len(high)} high-confidence) "
          f"/ {len(not_ex)} not exercised / {len(invalid)} invalid")
    if high:
        print("\nREBUILD NEEDED (high-confidence failures) -- re-examine these nodes:")
        for b in report["rebuild_brief"]:
            print(f"  - {b['rule']}: {', '.join(b['reexamine_nodes'])}  ({b['evidence']})")
    if human:
        print("\nFor human review (medium/low-confidence failures):")
        for h in report["human_review"]:
            print(f"  - {h['rule']} [{h['confidence']}]: {h['evidence']}")
    if invalid:
        print("\nCould not evaluate (fix the rules file):")
        for r in invalid:
            print(f"  - {r['id']}: {r['evidence']}")
    if report["n_pass"] + report["n_fail"] == 0:
        print("\nWARNING: no rules were actually evaluated (all invalid, or none triggered) -- "
              "this check provided no protection. Fix the rules file / scenario.")
        return 2
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
