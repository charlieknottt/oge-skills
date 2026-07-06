#!/usr/bin/env python3
"""
validate_behavior_rules.py - clean the authored behavior rules into behavior_rules.yaml.

A behavior rule says what a believable version of the world should never do, or should always do.
An author writes them from the scenario, blind to the graph's arrows; this script keeps only the
sound ones. No LLM, no network, standard library only.

For each rule it checks:
  - the kind is known (shouldnt_coexist or should_follow),
  - the required fields are present and in range,
  - every test uses only real node ids and parses as a plain true/false expression,
  - confidence is high/medium/low and there is a one-line 'why'.
Broken rules are dropped and reported, not shipped. Near-duplicates are merged.

Usage:
  python3 validate_behavior_rules.py --rules AUTHOR_OUTPUT.json --graph world_graph.json --out-dir OUTDIR
Writes OUTDIR/behavior_rules.yaml and OUTDIR/behavior_rules_report.json
"""
import argparse
import ast
import json
import os
import re
import sys

CONF = {"high", "medium", "low"}
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# A rule "test" must be a plain true/false expression: comparisons of node ids and numbers, combined
# with and/or/not. Nothing else. This is enforced on the parse tree, not just the names, because the
# check step later evaluates these in a no-builtins sandbox where `100/x` (x can be 0 on a rail), a
# call, a lambda, an attribute, or a walrus would crash or silently corrupt state.
_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp, ast.And, ast.Or,
    ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
    ast.Compare, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
    ast.Name, ast.Load, ast.Constant,
)


def _is_bool_test(node):
    """True if node is a comparison, or and/or/not built from comparisons -- a real true/false test,
    not a bare node value like `supply and frontline` (which evaluates to a number)."""
    if isinstance(node, ast.Compare):
        return True
    if isinstance(node, ast.BoolOp):
        return all(_is_bool_test(v) for v in node.values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_bool_test(node.operand)
    return False


def node_ids(doc):
    """Node ids from either a world_graph.json ('nodes') or a stocks.json ('stocks'). Phase 3b runs
    before the edges exist, so this usually points at stocks.json; both shapes use an 'id' per item."""
    items = doc.get("nodes") or doc.get("stocks") or []
    return {n["id"] for n in items if isinstance(n, dict) and "id" in n}


def unwrap(doc):
    """Accept {rules:[...]}, a raw [...], or an agent/workflow wrapper {result:{rules:[...]}}."""
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        if isinstance(doc.get("rules"), list):
            return doc["rules"]
        r = doc.get("result")
        if isinstance(r, dict) and isinstance(r.get("rules"), list):
            return r["rules"]
    return []


def expr_ok(expr, ids):
    if not isinstance(expr, str) or not expr.strip():
        return False, "empty"
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return False, f"does not parse ({e.msg})"
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return False, ("only node ids, numbers, comparisons and and/or/not are allowed "
                           f"(found {type(node).__name__})")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            return False, "only numeric thresholds are allowed"
        if isinstance(node, ast.Name):
            names.add(node.id)
    unknown = sorted(n for n in names if n not in ids)
    if unknown:
        return False, "unknown node id(s): " + ", ".join(unknown)
    if not names:
        return False, "references no node id"
    if not _is_bool_test(tree.body):
        return False, "must be a comparison, or and/or/not of comparisons"
    return True, ""


def check(rule, ids):
    problems = []
    if not (isinstance(rule.get("id"), str) and ID_RE.match(rule.get("id", ""))):
        problems.append("id must be snake_case")
    kind = rule.get("kind")
    if kind not in ("shouldnt_coexist", "should_follow"):
        problems.append(f"unknown kind '{kind}'")
        return problems  # nothing else is meaningful without a valid kind
    if kind == "shouldnt_coexist":
        ok, msg = expr_ok(rule.get("never"), ids)
        if not ok:
            problems.append("never: " + msg)
        mr = rule.get("max_rate")
        if not (isinstance(mr, (int, float)) and not isinstance(mr, bool) and 0 < mr <= 0.5):
            problems.append("max_rate must be a number in (0, 0.5]")
    else:  # should_follow
        for f in ("when", "then"):
            ok, msg = expr_ok(rule.get(f), ids)
            if not ok:
                problems.append(f"{f}: {msg}")
        wr = rule.get("within_rounds")
        if not (isinstance(wr, int) and not isinstance(wr, bool) and 1 <= wr <= 6):
            problems.append("within_rounds must be an integer 1-6")
        mm = rule.get("max_miss_rate")
        if not (isinstance(mm, (int, float)) and not isinstance(mm, bool) and 0 < mm <= 0.6):
            problems.append("max_miss_rate must be a number in (0, 0.6]")
    if rule.get("confidence") not in CONF:
        problems.append("confidence must be high/medium/low")
    if not (isinstance(rule.get("why"), str) and rule["why"].strip()):
        problems.append("why (one sentence) is required")
    return problems


def signature(rule):
    def norm(s):
        return re.sub(r"\s+", "", s or "")
    if rule.get("kind") == "shouldnt_coexist":
        return ("shouldnt_coexist", norm(rule.get("never")))
    return ("should_follow", norm(rule.get("when")), norm(rule.get("then")))


def to_yaml(rules):
    lines = ["# Behavior rules: what a believable version of this world should never do, or should",
             "# always do. Written from the scenario, blind to the graph's arrows. Checked against",
             "# simulated playthroughs (elsewhere). No effect on the live game.", "", "rules:"]
    for r in rules:
        lines.append(f"  - id: {r['id']}")
        lines.append(f"    kind: {r['kind']}")
        if r["kind"] == "shouldnt_coexist":
            lines.append(f"    never: {json.dumps(r['never'])}")
            lines.append(f"    max_rate: {r['max_rate']}")
        else:
            lines.append(f"    when: {json.dumps(r['when'])}")
            lines.append(f"    then: {json.dumps(r['then'])}")
            lines.append(f"    within_rounds: {int(r['within_rounds'])}")
            lines.append(f"    max_miss_rate: {r['max_miss_rate']}")
        lines.append(f"    confidence: {r['confidence']}")
        lines.append(f"    why: {json.dumps(r['why'])}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Clean authored behavior rules into behavior_rules.yaml.")
    ap.add_argument("--rules", required=True, help="the author's JSON output")
    ap.add_argument("--graph", required=True,
                    help="world_graph.json OR stocks.json -- either supplies the real node id list")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    ids = node_ids(graph)
    proposed = unwrap(json.load(open(args.rules)))

    kept, report, seen = [], [], set()
    for rule in proposed if isinstance(proposed, list) else []:
        if not isinstance(rule, dict):
            report.append({"id": None, "kind": None, "kept": False, "problems": ["not an object"]})
            continue
        problems = check(rule, ids)
        sig = signature(rule)
        dup = sig in seen
        seen.add(sig)
        keep = (not problems) and (not dup)
        report.append({"id": rule.get("id"), "kind": rule.get("kind"), "kept": keep,
                       "confidence": rule.get("confidence"),
                       "problems": problems + (["duplicate of an earlier rule"] if dup and not problems else [])})
        if keep:
            kept.append(rule)

    os.makedirs(args.out_dir, exist_ok=True)
    open(os.path.join(args.out_dir, "behavior_rules.yaml"), "w").write(to_yaml(kept))
    # behavior_rules.json is the machine copy the check step reads (no YAML dependency).
    json.dump({"rules": kept}, open(os.path.join(args.out_dir, "behavior_rules.json"), "w"), indent=2)
    json.dump({"proposed": len(proposed), "kept": len(kept), "rules": report},
              open(os.path.join(args.out_dir, "behavior_rules_report.json"), "w"), indent=2)

    by_conf = {c: sum(1 for r in kept if r.get("confidence") == c) for c in ("high", "medium", "low")}
    print(f"behavior rules: {len(proposed)} proposed -> {len(kept)} kept "
          f"(high {by_conf['high']}, medium {by_conf['medium']}, low {by_conf['low']})")
    for r in report:
        mark = "keep" if r["kept"] else "DROP"
        extra = "" if r["kept"] else "  -- " + "; ".join(r["problems"])
        print(f"  {mark}  {str(r['kind'] or '?'):16} {str(r['id'] or '(no id)'):34}{extra}")
    print(f"\nwrote {args.out_dir}/behavior_rules.yaml (+ behavior_rules_report.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
