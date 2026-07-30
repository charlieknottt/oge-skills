#!/usr/bin/env python3
"""
assemble_graph.py - combine nodes.json and the merged edges into one world_graph.json (deterministic).

This is the join before the hard gate: it puts the built nodes and the consolidated edges into a
single build-time graph, which validate_graph.py and lint_taxonomy.py then check. It does not seed
runtime state (that is package_runtime.py) and does no judgment.

Inputs : nodes.json               { "nodes": [...] }
         consolidated_edges.json  { "edges": [...] }
Output : world_graph.json         { scenario, version, nodes, edges }

Usage:
    python3 assemble_graph.py --nodes nodes.json --edges consolidated_edges.json \\
            --scenario gordian_knot --version 1 --out world_graph.json
"""
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser(description="Combine nodes and edges into one world_graph.json.")
    ap.add_argument("--nodes", required=True, help="nodes.json")
    ap.add_argument("--edges", required=True, help="consolidated_edges.json")
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--version", default=None)
    ap.add_argument("--drop-invalid", action="store_true",
                    help="drop edges with unknown endpoints, self-loops, or a Lever target (self-heal)")
    ap.add_argument("--out", default="world_graph.json")
    args = ap.parse_args()

    try:
        with open(args.nodes, "r", encoding="utf-8") as f:
            ndoc = json.load(f)
        with open(args.edges, "r", encoding="utf-8") as f:
            edoc = json.load(f)
    except FileNotFoundError as ex:
        print(f"ERROR: file not found: {ex.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as ex:
        print(f"ERROR: invalid JSON: {ex}", file=sys.stderr)
        return 2

    nodes = ndoc.get("nodes") if isinstance(ndoc, dict) else ndoc
    edges = edoc.get("edges") if isinstance(edoc, dict) else edoc
    if not isinstance(nodes, list) or not isinstance(edges, list):
        print("ERROR: nodes file needs a 'nodes' array and edges file needs an 'edges' array", file=sys.stderr)
        return 2

    if args.drop_invalid:
        node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
        levers = {n.get("id") for n in nodes if isinstance(n, dict) and n.get("type") == "Lever"}
        kept, dropped = [], 0
        for e in edges:
            s, t = e.get("source"), e.get("target")
            if s in node_ids and t in node_ids and t not in levers and s != t:
                kept.append(e)
            else:
                dropped += 1
        if dropped:
            print(f"  dropped {dropped} invalid edge(s) (unknown endpoint / self-loop / Lever target)")
        edges = kept

    graph = {}
    if args.scenario:
        graph["scenario"] = args.scenario
    if args.version:
        graph["version"] = args.version
    graph["nodes"] = nodes
    graph["edges"] = edges

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)
    print(f"ASSEMBLED  {args.out}  ({len(nodes)} nodes, {len(edges)} edges)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
