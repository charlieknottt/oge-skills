#!/usr/bin/env python3
"""
build_nodes.py - turn the reviewed node list into graph nodes (deterministic).

This is the single authority for two things a human/LLM must not fiddle with:
  - the resting value:  baseline = node_value   (both on the 0-1 scale)
  - the behavior:       type is derived from stock_type by the fixed table below

It carries id / inverted / pmesii / the descriptive fields straight across, and merges the LLM's
label + category (from node_build.md) onto each node. If the label/category are missing it falls back
to the node's name / pmesii.

Inputs : stocks_reviewed.json  { "stocks": [...] }   (each stock: id, name, stock_type, pmesii,
                                                       node_value, inverted, measures, ...)
         node_build.json       { "nodes": [ {id, label, category} ] }   (optional; LLM labels/swimlanes)
Outputs: nodes.json            { "nodes": [...] }    (graph nodes, baseline + type set)
         stocks.json           { "stocks": [...] }   (the finalized descriptive model deliverable)

Usage:
    python3 build_nodes.py --stocks stocks_reviewed.json --labels node_build.json \\
            --out-nodes nodes.json --out-stocks stocks.json
"""
import argparse
import json
import sys

# The mapping from the finer stock_type to the 4 engine behaviors (see guide/1-how-the-model-works.md).
STOCK_TYPE_TO_BEHAVIOR = {
    "zero-sum-pool": "Level",
    "spendable": "Level",
    "service-level": "Level",
    "trust-sentiment": "Level",
    "upstream-access": "Level",
    "capacity": "Level",
    "other": "Level",
    "scheduled-threat": "Drifter",
    "clock": "Drifter",
    "buildout": "Accumulator",
    "policy-lever": "Lever",
}

DETAIL_FIELDS = ("name", "measures", "unit", "rationale", "increases_when", "decreases_when", "sector")


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _baseline_from(stock):
    """Resting value on the 0-1 scale, from node_value (or an existing baseline)."""
    for k in ("node_value", "baseline"):
        v = _num(stock.get(k))
        if v is not None:
            return round(max(0.0, min(1.0, v)), 4)
    return None


def build(stocks, labels):
    """Return (nodes_doc, stocks_doc, errors)."""
    errors = []
    label_by_id = {}
    for n in (labels.get("nodes") if isinstance(labels, dict) else []) or []:
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            label_by_id[n["id"]] = n

    nodes = []
    for i, s in enumerate(stocks):
        if not isinstance(s, dict):
            errors.append(f"stocks[{i}] must be an object")
            continue
        sid = s.get("id")
        if not isinstance(sid, str):
            errors.append(f"stocks[{i}] missing string id")
            continue
        stype = s.get("stock_type")
        behavior = STOCK_TYPE_TO_BEHAVIOR.get(stype)
        if behavior is None:
            errors.append(f"node '{sid}': unknown stock_type {stype!r}")
            behavior = "Level"
        baseline = _baseline_from(s)
        if baseline is None:
            errors.append(f"node '{sid}': no node_value/baseline to set the resting value")
            baseline = 0.5
        lab = label_by_id.get(sid, {})

        node = {
            "id": sid,
            "label": lab.get("label") or s.get("name") or sid,
            "category": lab.get("category") or s.get("sector") or s.get("pmesii") or "Uncategorized",
            "type": behavior,
            "stock_type": stype,
            "pmesii": s.get("pmesii"),
            "inverted": bool(s.get("inverted", False)),
            "baseline": baseline,
        }
        for f in DETAIL_FIELDS:
            if f in s and f != "name":
                node[f] = s[f]
        # sanity: the deterministic invariant this script exists to guarantee
        nv = _num(s.get("node_value"))
        if nv is not None and node["baseline"] != round(max(0.0, min(1.0, nv)), 4):
            errors.append(f"node '{sid}': baseline desync (internal error)")
        nodes.append(node)

    return {"nodes": nodes}, {"stocks": [s for s in stocks if isinstance(s, dict)]}, errors


def main():
    ap = argparse.ArgumentParser(description="Turn the reviewed node list into graph nodes.")
    ap.add_argument("--stocks", required=True, help="stocks_reviewed.json")
    ap.add_argument("--labels", default=None, help="node_build.json (LLM labels/categories; optional)")
    ap.add_argument("--out-nodes", default="nodes.json")
    ap.add_argument("--out-stocks", default="stocks.json")
    args = ap.parse_args()

    try:
        with open(args.stocks, "r", encoding="utf-8") as f:
            sdoc = json.load(f)
        labels = {}
        if args.labels:
            with open(args.labels, "r", encoding="utf-8") as f:
                labels = json.load(f)
    except FileNotFoundError as ex:
        print(f"ERROR: file not found: {ex.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as ex:
        print(f"ERROR: invalid JSON: {ex}", file=sys.stderr)
        return 2

    stocks = sdoc.get("stocks") if isinstance(sdoc, dict) else sdoc
    if not isinstance(stocks, list):
        print("ERROR: stocks file must have a 'stocks' array", file=sys.stderr)
        return 2

    nodes_doc, stocks_doc, errors = build(stocks, labels)
    if errors:
        print(f"FAIL  build_nodes - {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    with open(args.out_nodes, "w", encoding="utf-8") as f:
        json.dump(nodes_doc, f, indent=2)
    with open(args.out_stocks, "w", encoding="utf-8") as f:
        json.dump(stocks_doc, f, indent=2)
    print(f"BUILT  {len(nodes_doc['nodes'])} nodes -> {args.out_nodes}  (baseline + behavior type set)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
