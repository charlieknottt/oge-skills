#!/usr/bin/env python3
"""
validate_graph.py - hard schema validation for an OGE world graph.

Implements the "6a. Deterministic schema validation" rules from the
world-graph-builder plan. Pure standard library, no third-party deps, so it
runs anywhere Python 3.8+ is available.

Exit code 0 = no errors (graph may still have lint warnings; see lint_taxonomy.py).
Exit code 1 = one or more hard errors (block advance).

Usage:
    python3 validate_graph.py path/to/world_graph.json
    python3 validate_graph.py graph.json --min 25 --max 35
    python3 validate_graph.py graph.json --categories Levers,Supply,Economy
    python3 validate_graph.py graph.json --json validation_report.json
"""
import argparse
import json
import re
import sys

NODE_TYPES = {"Level", "Lever", "Accumulator", "Drifter"}
EDGE_SIGNS = {"+", "-"}
# edge magnitude is a number in [0, 1] (weak ~0.2-0.4, moderate ~0.5-0.7, strong ~0.8-1.0)
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

NODE_REQUIRED = ("id", "label", "category", "type", "starting_value", "inverted")
EDGE_REQUIRED = ("id", "source", "target", "sign", "magnitude", "lag", "mechanism")


def _is_bool(v):
    return isinstance(v, bool)


def _is_number(v):
    # bool is a subclass of int; reject it for numeric fields
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate(graph, min_nodes=25, max_nodes=35, categories=None, allow_parallel=False):
    """Return a list of error strings. Empty list == valid."""
    errors = []

    if not isinstance(graph, dict):
        return ["root: graph must be a JSON object"]

    nodes = graph.get("nodes")
    edges = graph.get("edges")

    if not isinstance(nodes, list) or not nodes:
        errors.append("root.nodes: must be a non-empty array")
        nodes = nodes if isinstance(nodes, list) else []
    if not isinstance(edges, list):
        errors.append("root.edges: must be an array")
        edges = edges if isinstance(edges, list) else []

    # ---- nodes ----
    node_ids = set()
    for i, n in enumerate(nodes):
        where = f"nodes[{i}]"
        if not isinstance(n, dict):
            errors.append(f"{where}: must be an object")
            continue
        for k in NODE_REQUIRED:
            if k not in n:
                errors.append(f"{where}: missing required field '{k}'")
        nid = n.get("id")
        if isinstance(nid, str):
            where = f"nodes[{i}] '{nid}'"
            if not ID_RE.match(nid):
                errors.append(f"{where}: id must match ^[a-z][a-z0-9_]*$ (snake_case)")
            if nid in node_ids:
                errors.append(f"{where}: duplicate node id")
            node_ids.add(nid)
        elif "id" in n:
            errors.append(f"{where}: id must be a string")
        if "label" in n and not (isinstance(n.get("label"), str) and n["label"].strip()):
            errors.append(f"{where}: label must be a non-empty string")
        cat = n.get("category")
        if "category" in n:
            if not (isinstance(cat, str) and cat.strip()):
                errors.append(f"{where}: category must be a non-empty string")
            elif categories and cat not in categories:
                errors.append(f"{where}: category '{cat}' not in allowed set {sorted(categories)}")
        if "type" in n and n.get("type") not in NODE_TYPES:
            errors.append(f"{where}: type '{n.get('type')}' must be one of {sorted(NODE_TYPES)}")
        sv = n.get("starting_value")
        if "starting_value" in n and not (_is_number(sv) and 0 <= sv <= 100):
            errors.append(f"{where}: starting_value must be a number in [0,100]")
        if "inverted" in n and not _is_bool(n.get("inverted")):
            errors.append(f"{where}: inverted must be a boolean")

    # ---- edges ----
    edge_ids = set()
    seen_pairs = set()
    for i, e in enumerate(edges):
        where = f"edges[{i}]"
        if not isinstance(e, dict):
            errors.append(f"{where}: must be an object")
            continue
        for k in EDGE_REQUIRED:
            if k not in e:
                errors.append(f"{where}: missing required field '{k}'")
        eid = e.get("id")
        if isinstance(eid, str):
            where = f"edges[{i}] '{eid}'"
            if not eid.startswith("e_"):
                errors.append(f"{where}: edge id must start with 'e_'")
            if eid in edge_ids:
                errors.append(f"{where}: duplicate edge id")
            edge_ids.add(eid)
        elif "id" in e:
            errors.append(f"{where}: id must be a string")
        src, tgt = e.get("source"), e.get("target")
        if isinstance(src, str) and src not in node_ids:
            errors.append(f"{where}: source '{src}' references a non-existent node")
        if isinstance(tgt, str) and tgt not in node_ids:
            errors.append(f"{where}: target '{tgt}' references a non-existent node")
        if isinstance(src, str) and isinstance(tgt, str):
            if src == tgt:
                errors.append(f"{where}: self-loop (source == target)")
            elif not allow_parallel:
                if (src, tgt) in seen_pairs:
                    errors.append(f"{where}: duplicate edge for pair ({src} -> {tgt})")
                seen_pairs.add((src, tgt))
        if "sign" in e and e.get("sign") not in EDGE_SIGNS:
            errors.append(f"{where}: sign '{e.get('sign')}' must be one of {sorted(EDGE_SIGNS)}")
        if "magnitude" in e:
            m = e.get("magnitude")
            if _is_bool(m) or not isinstance(m, (int, float)) or not (0 <= m <= 1):
                errors.append(f"{where}: magnitude must be a number in [0, 1] (got {m!r})")
        if "lag" in e and not (_is_int(e.get("lag")) and e["lag"] >= 0):
            errors.append(f"{where}: lag must be an integer >= 0")
        if "mechanism" in e and not (isinstance(e.get("mechanism"), str) and e["mechanism"].strip()):
            errors.append(f"{where}: mechanism must be a non-empty string")

    # ---- counts ----
    n_nodes = len(nodes)
    if not (min_nodes <= n_nodes <= max_nodes):
        errors.append(f"counts: node count {n_nodes} outside configured band [{min_nodes},{max_nodes}]")

    return errors


def main():
    ap = argparse.ArgumentParser(description="Hard schema validation for an OGE world graph.")
    ap.add_argument("graph", help="path to world_graph.json")
    ap.add_argument("--min", type=int, default=25, help="min node count (default 25)")
    ap.add_argument("--max", type=int, default=35, help="max node count (default 35)")
    ap.add_argument("--categories", default=None, help="comma-separated allowed category set (optional)")
    ap.add_argument("--allow-parallel", action="store_true", help="allow duplicate (source,target) edges")
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

    cats = set(c.strip() for c in args.categories.split(",")) if args.categories else None
    errors = validate(graph, args.min, args.max, cats, args.allow_parallel)

    n_nodes = len(graph.get("nodes", []) or [])
    n_edges = len(graph.get("edges", []) or [])
    ok = len(errors) == 0

    if args.json_out:
        report = {"graph": args.graph, "ok": ok, "node_count": n_nodes,
                  "edge_count": n_edges, "error_count": len(errors), "errors": errors}
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    if ok:
        print(f"PASS  {args.graph}  ({n_nodes} nodes, {n_edges} edges) - 0 errors")
    else:
        print(f"FAIL  {args.graph}  ({n_nodes} nodes, {n_edges} edges) - {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
