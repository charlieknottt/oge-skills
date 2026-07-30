#!/usr/bin/env python3
"""
package_runtime.py - turn the build outputs into the single play-ready runtime file.

This is the last step of graph creation. It takes the reviewed world graph (nodes + edges) and,
optionally, the detailed stock model, and produces one merged, seeded artifact the live game reads
and the update skill mutates each round (schemas/runtime_graph.schema.json).

What it does:
  - merges each node's stock detail onto the node (one id space; stock_type, pmesii, measures, ...)
  - seeds runtime state: current_value = baseline, and lag_ticks_elapsed = 0 on every edge
  - stamps the header: round 0, tick 0, and the canonical engine constants (see guide/4-the-engine.md)

Before it writes anything it runs the hard checks that must hold for a valid runtime file, and
refuses to package (non-zero exit, no output written) if any fail:
  - node ids are unique
  - every edge source/target is a real node id
  - no Lever is the target of an edge (a Lever ignores incoming edges, so an edge into one is a bug)
  - if a stock model is given, its ids are a bijection with the node ids (the join is total)

Values are on the 0-1 scale. The stock model's node_value is the same 0-1 number as a node's baseline.

Usage:
    python3 package_runtime.py world_graph.json --out gordian.runtime.json
    python3 package_runtime.py world_graph.json --stocks stocks.json --scenario gordian_knot \\
            --version 1 --out gordian.runtime.json
"""
import argparse
import json
import sys

# The canonical engine constants, stamped into every runtime file. See guide/4-the-engine.md.
ENGINE_BLOCK = {
    "scale_min": 0,
    "scale_max": 1,
    "sat_a": 0.38,
    "speed": 0.7,
    "ticks_per_round": 6,
    "rates": {
        "Level": [0.12, 0.22],
        "Accumulator": [0.06, 0.13],
        "Drifter": [0.10, 0.18],
        "Lever": [0.0, 0.0],
    },
}

# stock-model fields that get folded onto the node it describes
STOCK_DETAIL_FIELDS = (
    "name", "pmesii", "stock_type", "measures", "unit",
    "rationale", "increases_when", "decreases_when", "sector",
)


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _baseline_of(rec):
    """Read a node's resting value on the 0-1 scale."""
    if _is_number(rec.get("baseline")):
        return float(rec["baseline"])
    if _is_number(rec.get("node_value")):
        return float(rec["node_value"])
    return None


def _strength_of(edge):
    """Read an edge's unsigned 0-1 gain."""
    if _is_number(edge.get("strength")):
        return float(edge["strength"])
    return None


def package(graph, stocks=None, scenario=None, version=None):
    """Return (runtime_dict, errors). If errors is non-empty, runtime_dict is None."""
    errors = []
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not nodes:
        errors.append("graph.nodes must be a non-empty array")
        nodes = nodes if isinstance(nodes, list) else []
    if not isinstance(edges, list):
        errors.append("graph.edges must be an array")
        edges = edges if isinstance(edges, list) else []

    # ---- stock detail, keyed by id (for the merge + the bijection check) ----
    stock_by_id = {}
    if stocks is not None:
        srecs = stocks.get("stocks") if isinstance(stocks, dict) else stocks
        if not isinstance(srecs, list):
            errors.append("stocks file must have a 'stocks' array")
            srecs = []
        for s in srecs:
            if isinstance(s, dict) and isinstance(s.get("id"), str):
                stock_by_id[s["id"]] = s

    # ---- build merged, seeded nodes ----
    node_ids = []
    seen = set()
    out_nodes = []
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"nodes[{i}] must be an object")
            continue
        nid = n.get("id")
        if not isinstance(nid, str):
            errors.append(f"nodes[{i}] missing string id")
            continue
        if nid in seen:
            errors.append(f"node '{nid}': duplicate node id")
        seen.add(nid)
        node_ids.append(nid)

        merged = dict(n)  # start from the graph node
        detail = stock_by_id.get(nid, {})
        for f in STOCK_DETAIL_FIELDS:            # fold stock detail on; node wins on conflict
            if f not in merged and f in detail:
                merged[f] = detail[f]

        base = _baseline_of(merged)
        if base is None:
            base = _baseline_of(detail)
        if base is None:
            errors.append(f"node '{nid}': no baseline/node_value found")
        else:
            base = max(0.0, min(1.0, base))
            merged["baseline"] = base
            merged["current_value"] = base       # seed live state at rest
        merged.pop("node_value", None)            # node_value is the stock-model name; the node carries baseline

        out_nodes.append(merged)

    node_id_set = set(node_ids)

    # ---- build seeded edges ----
    out_edges = []
    lever_ids = {n.get("id") for n in nodes if isinstance(n, dict) and n.get("type") == "Lever"}
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            errors.append(f"edges[{i}] must be an object")
            continue
        src, tgt = e.get("source"), e.get("target")
        if src not in node_id_set:
            errors.append(f"edge '{e.get('id', i)}': source '{src}' is not a node id")
        if tgt not in node_id_set:
            errors.append(f"edge '{e.get('id', i)}': target '{tgt}' is not a node id")
        if tgt in lever_ids:
            errors.append(f"edge '{e.get('id', i)}': target '{tgt}' is a Lever (levers take no incoming edges)")

        merged = dict(e)
        strength = _strength_of(merged)
        if strength is None:
            errors.append(f"edge '{e.get('id', i)}': no strength found")
        else:
            merged["strength"] = max(0.0, min(1.0, strength))
        merged["lag_ticks_elapsed"] = 0           # seed the lag counter
        out_edges.append(merged)

    # ---- id bijection between stock detail and nodes (the join must be total) ----
    if stocks is not None and stock_by_id:
        stock_ids = set(stock_by_id)
        missing_stock = node_id_set - stock_ids      # nodes with no stock detail
        extra_stock = stock_ids - node_id_set        # stock detail for no node
        if missing_stock:
            errors.append(f"id mismatch: {len(missing_stock)} node(s) have no matching stock: "
                          f"{sorted(missing_stock)[:5]}{' ...' if len(missing_stock) > 5 else ''}")
        if extra_stock:
            errors.append(f"id mismatch: {len(extra_stock)} stock(s) match no node: "
                          f"{sorted(extra_stock)[:5]}{' ...' if len(extra_stock) > 5 else ''}")

    if errors:
        return None, errors

    runtime = {
        "scenario": scenario or graph.get("scenario"),
        "version": version or graph.get("version"),
        "round": 0,
        "tick": 0,
        "engine": ENGINE_BLOCK,
        "nodes": out_nodes,
        "edges": out_edges,
    }
    runtime = {k: v for k, v in runtime.items() if v is not None}
    return runtime, []


def main():
    ap = argparse.ArgumentParser(description="Package the build outputs into the play-ready runtime file.")
    ap.add_argument("graph", help="path to the reviewed world_graph.json")
    ap.add_argument("--stocks", default=None, help="path to the detailed stock model (optional; enables the id bijection check)")
    ap.add_argument("--scenario", default=None, help="scenario slug for the header")
    ap.add_argument("--version", default=None, help="version string for the header")
    ap.add_argument("--out", default=None, help="output path (default: <graph without extension>.runtime.json)")
    args = ap.parse_args()

    def _load(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    try:
        graph = _load(args.graph)
        stocks = _load(args.stocks) if args.stocks else None
    except FileNotFoundError as ex:
        print(f"ERROR: file not found: {ex.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as ex:
        print(f"ERROR: invalid JSON: {ex}", file=sys.stderr)
        return 2

    runtime, errors = package(graph, stocks, args.scenario, args.version)

    if errors:
        print(f"BLOCKED  {args.graph} - cannot package ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        return 1

    out = args.out
    if not out:
        stem = args.graph.rsplit(".", 1)[0]
        out = f"{stem}.runtime.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(runtime, f, indent=2)

    print(f"PACKAGED  {out}  ({len(runtime['nodes'])} nodes, {len(runtime['edges'])} edges) - "
          f"current_value seeded, lag counters zeroed, round 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
