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

Reads behavior_rules.json (written by validate_behavior_rules.py). The rule expressions were already
checked to be safe true/false tests, so they are evaluated here with no builtins.

Exit 0 = no high-confidence failure. Exit 1 = at least one high-confidence failure (rebuild needed).

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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build"))
from engine import Engine, sample_game


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
    qual = miss = 0
    for run in runs:
        n = len(run)
        for r in range(n):
            if ev(when_code, run[r]):
                qual += 1
                if not any(ev(then_code, run[j]) for j in range(r, min(n, r + within + 1))):
                    miss += 1
    if qual == 0:
        return None, "the trigger never occurred in play (rule not exercised)"
    rate = miss / qual
    return rate, f"the effect failed to follow in {miss}/{qual} trigger cases ({rate:.1%})"


def evaluate(rule, ids, runs):
    """Return a result dict for one rule."""
    rid, kind, conf = rule.get("id"), rule.get("kind"), rule.get("confidence")
    exprs = [rule.get("never")] if kind == "shouldnt_coexist" else [rule.get("when"), rule.get("then")]
    used = set().union(*[names_in(e) for e in exprs if e]) if any(exprs) else set()
    missing = used - ids
    base = {"id": rid, "kind": kind, "confidence": conf, "why": rule.get("why"),
            "involved_nodes": sorted(used & ids)}
    if missing:  # the rule was written against a node this graph does not have
        return {**base, "status": "skipped", "metric": None, "value": None, "limit": None,
                "evidence": "references a node not in this graph: " + ", ".join(sorted(missing))}
    if kind == "shouldnt_coexist":
        rate, ev_txt = run_shouldnt_coexist(compile(rule["never"], "<r>", "eval"), runs)
        ok = rate <= rule["max_rate"]
        return {**base, "status": "pass" if ok else "fail", "metric": "violation_rate",
                "value": round(rate, 4), "limit": rule["max_rate"], "evidence": ev_txt}
    within = int(rule["within_rounds"])
    rate, ev_txt = run_should_follow(compile(rule["when"], "<r>", "eval"),
                                     compile(rule["then"], "<r>", "eval"), within, runs)
    if rate is None:
        return {**base, "status": "not_exercised", "metric": "miss_rate", "value": None,
                "limit": rule["max_miss_rate"], "evidence": ev_txt}
    ok = rate <= rule["max_miss_rate"]
    return {**base, "status": "pass" if ok else "fail", "metric": "miss_rate",
            "value": round(rate, 4), "limit": rule["max_miss_rate"], "evidence": ev_txt}


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
    ids = {n["id"] for n in graph["nodes"]}
    rules = json.load(open(args.rules)).get("rules", [])
    eng = Engine(graph)
    rng = random.Random(args.seed)
    runs = [sample_game(eng, args.rounds, args.tpr, args.cap, args.teams, rng) for _ in range(args.runs)]

    results = [evaluate(r, ids, runs) for r in rules]
    fails = [r for r in results if r["status"] == "fail"]
    high = [r for r in fails if r["confidence"] == "high"]
    human = [r for r in fails if r["confidence"] in ("medium", "low")]
    not_ex = [r for r in results if r["status"] == "not_exercised"]
    skipped = [r for r in results if r["status"] == "skipped"]

    report = {
        "graph": args.graph, "runs": args.runs, "rounds": args.rounds, "n_rules": len(rules),
        "n_pass": sum(1 for r in results if r["status"] == "pass"),
        "n_fail": len(fails), "n_high_fail": len(high),
        "n_not_exercised": len(not_ex), "n_skipped": len(skipped),
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
    order = {"fail": 0, "not_exercised": 1, "skipped": 2, "pass": 3}
    for r in sorted(results, key=lambda x: order.get(x["status"], 9)):
        mark = {"pass": "  ok ", "fail": " FAIL", "not_exercised": " n/ex", "skipped": " skip"}[r["status"]]
        v = r.get("value")
        vtxt = f"{v:.1%}" if isinstance(v, float) else "-"
        print(f"{mark} [{str(r['confidence'] or '?'):6}] {str(r['id']):34} {r.get('metric') or '':14} "
              f"{vtxt:>6}  {r['evidence']}")
    print(f"\n{report['n_pass']} pass / {len(fails)} fail ({len(high)} high-confidence) "
          f"/ {len(not_ex)} not exercised / {len(skipped)} skipped")
    if high:
        print("\nREBUILD NEEDED (high-confidence failures) -- re-examine these nodes:")
        for b in report["rebuild_brief"]:
            print(f"  - {b['rule']}: {', '.join(b['reexamine_nodes'])}  ({b['evidence']})")
    if human:
        print("\nFor human review (medium/low-confidence failures):")
        for h in report["human_review"]:
            print(f"  - {h['rule']} [{h['confidence']}]: {h['evidence']}")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
