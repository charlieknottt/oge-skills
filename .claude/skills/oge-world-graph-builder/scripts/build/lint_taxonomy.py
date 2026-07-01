#!/usr/bin/env python3
"""
lint_taxonomy.py - structural / taxonomy lint for an OGE world graph.

Implements the "6b. Structural / taxonomy lint" rules from the
world-graph-builder plan. Run this after validate_graph.py passes; it assumes
the graph is already schema-valid and checks the node-class rules from the
taxonomy (guide/1-how-the-model-works.md).

FAIL findings are hard taxonomy violations (block advance).
WARN findings are things a human should look at but do not block.

Exit code 0 = no FAIL findings (warnings allowed).
Exit code 1 = one or more FAIL findings.

Usage:
    python3 lint_taxonomy.py path/to/world_graph.json
    python3 lint_taxonomy.py graph.json --drifter-lag-warn 3 --json lint_report.json
"""
import argparse
import json
import sys


def lint(graph, drifter_lag_warn=3):
    """Return (fails, warns) lists of strings."""
    fails, warns = [], []
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []

    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict)}
    indeg = {nid: 0 for nid in by_id}
    outdeg = {nid: 0 for nid in by_id}
    out_edges = {nid: [] for nid in by_id}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in outdeg:
            outdeg[s] += 1
            out_edges[s].append(e)
        if t in indeg:
            indeg[t] += 1

    for nid, n in by_id.items():
        ntype = n.get("type")

        # Lever must have no incoming edges (all time logic is on its out-edges).
        if ntype == "Lever" and indeg.get(nid, 0) > 0:
            fails.append(f"Lever '{nid}' has {indeg[nid]} incoming edge(s); levers are set directly and take no inputs")

        # Isolated node (degree 0) is almost always a generation error.
        if indeg.get(nid, 0) == 0 and outdeg.get(nid, 0) == 0:
            fails.append(f"Node '{nid}' is isolated (degree 0)")

        # Accumulator should be funded (in-edge) and should activate something (out-edge).
        if ntype == "Accumulator":
            if indeg.get(nid, 0) == 0:
                warns.append(f"Accumulator '{nid}' has no funding in-edge (nothing drives its progress)")
            if outdeg.get(nid, 0) == 0:
                warns.append(f"Accumulator '{nid}' has no activation out-edge (its progress feeds nothing)")

        # Drifter harm should bite fast: long-lag out-edges are suspicious.
        if ntype == "Drifter":
            for e in out_edges.get(nid, []):
                lag = e.get("lag")
                if isinstance(lag, int) and lag > drifter_lag_warn:
                    warns.append(f"Drifter '{nid}' out-edge '{e.get('id')}' has lag {lag} (> {drifter_lag_warn}); drifter harm should land fast")

        # A non-lever, non-accumulator node with no incoming edges can only move by
        # direct decision, which is usually unintended for an outcome/level.
        if ntype in ("Level", "Drifter") and indeg.get(nid, 0) == 0:
            warns.append(f"{ntype} '{nid}' has no incoming edges; it can only change by direct decision")

    return fails, warns


def main():
    ap = argparse.ArgumentParser(description="Structural / taxonomy lint for an OGE world graph.")
    ap.add_argument("graph", help="path to world_graph.json")
    ap.add_argument("--drifter-lag-warn", type=int, default=3, help="warn on drifter out-edge lag above this (default 3)")
    ap.add_argument("--json", dest="json_out", default=None, help="write a JSON report to this path")
    args = ap.parse_args()

    try:
        with open(args.graph, "r", encoding="utf-8") as f:
            graph = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.graph}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as ex:
        print(f"ERROR: invalid JSON in {args.graph}: {ex}", file=sys.stderr)
        return 2

    fails, warns = lint(graph, args.drifter_lag_warn)
    ok = len(fails) == 0

    if args.json_out:
        report = {"graph": args.graph, "ok": ok, "fail_count": len(fails),
                  "warn_count": len(warns), "fails": fails, "warns": warns}
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  {args.graph} - {len(fails)} fail(s), {len(warns)} warning(s)")
    for x in fails:
        print(f"  FAIL  {x}")
    for x in warns:
        print(f"  WARN  {x}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
