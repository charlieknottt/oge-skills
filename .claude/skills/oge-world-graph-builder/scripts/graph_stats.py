#!/usr/bin/env python3
"""
graph_stats.py - metrics report for an OGE world graph.

Implements "6c. Graph metrics report" from the world-graph-builder plan:
node/edge counts, edges by sign, in/out degree distribution, category balance,
PMESII-P balance (if rich stock data present),
feedback structure (strongly connected components / cycles), orphans, and
levers-with-incoming. Pure standard library.

Usage:
    python3 graph_stats.py path/to/world_graph.json
    python3 graph_stats.py graph.json --json graph_stats.json
"""
import argparse
import json
import sys
from collections import Counter, defaultdict


def _tarjan_scc(node_ids, adj):
    """Return list of strongly connected components (each a list of node ids).

    Recursive Tarjan. World graphs are small (tens of nodes), so recursion depth
    is never a concern; we raise the limit defensively anyway.
    """
    sys.setrecursionlimit(10000)
    index = {}
    low = {}
    on_stack = set()
    stack = []
    counter = [0]
    sccs = []

    def strongconnect(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in adj.get(v, []):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for root in node_ids:
        if root not in index:
            strongconnect(root)
    return sccs


def compute(graph):
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    by_id = {n.get("id"): n for n in nodes if isinstance(n, dict)}

    indeg = Counter()
    outdeg = Counter()
    adj = defaultdict(list)
    sign_counts = Counter()
    mag_counts = Counter()
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in by_id:
            outdeg[s] += 1
            if t in by_id:
                adj[s].append(t)
        if t in by_id:
            indeg[t] += 1
        sign_counts[e.get("sign")] += 1
        mag_counts[e.get("magnitude")] += 1

    type_counts = Counter(n.get("type") for n in nodes if isinstance(n, dict))
    cat_counts = Counter(n.get("category") for n in nodes if isinstance(n, dict))
    pmesii_counts = Counter(n.get("pmesii") for n in nodes if isinstance(n, dict) and n.get("pmesii"))

    sccs = _tarjan_scc(list(by_id.keys()), adj)
    feedback_sccs = [sorted(c) for c in sccs if len(c) > 1]
    nodes_in_cycles = sum(len(c) for c in feedback_sccs)

    orphans = [nid for nid in by_id if indeg[nid] == 0 and outdeg[nid] == 0]
    levers_with_incoming = [nid for nid, n in by_id.items()
                            if n.get("type") == "Lever" and indeg[nid] > 0]

    degsum = sum(indeg[n] + outdeg[n] for n in by_id)
    avg_deg = round(degsum / len(by_id), 2) if by_id else 0

    top_in = sorted(by_id, key=lambda n: indeg[n], reverse=True)[:5]
    top_out = sorted(by_id, key=lambda n: outdeg[n], reverse=True)[:5]

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "types": dict(type_counts),
        "categories": dict(cat_counts),
        "pmesii": dict(pmesii_counts) or None,
        "edges_by_sign": dict(sign_counts),
        "edges_by_magnitude": dict(mag_counts),
        "avg_total_degree": avg_deg,
        "top_in_degree": [(n, indeg[n]) for n in top_in],
        "top_out_degree": [(n, outdeg[n]) for n in top_out],
        "feedback_loop_count": len(feedback_sccs),
        "nodes_in_feedback_loops": nodes_in_cycles,
        "largest_feedback_components": [c for c in sorted(feedback_sccs, key=len, reverse=True)[:3]],
        "orphan_nodes": orphans,
        "levers_with_incoming": levers_with_incoming,
    }


def _print_table(title, counter):
    print(f"  {title}:")
    for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"    {str(k):<22} {v}")


def main():
    ap = argparse.ArgumentParser(description="Metrics report for an OGE world graph.")
    ap.add_argument("graph", help="path to world_graph.json")
    ap.add_argument("--json", dest="json_out", default=None, help="write the report as JSON to this path")
    args = ap.parse_args()

    try:
        with open(args.graph, "r", encoding="utf-8") as f:
            graph = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2

    r = compute(graph)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2)

    print(f"GRAPH STATS  {args.graph}")
    print(f"  nodes: {r['node_count']}   edges: {r['edge_count']}   avg total degree: {r['avg_total_degree']}")
    _print_table("node types", r["types"])
    _print_table("categories", r["categories"])
    if r["pmesii"]:
        _print_table("PMESII-P", r["pmesii"])
    _print_table("edges by sign", r["edges_by_sign"])
    _print_table("edges by magnitude", r["edges_by_magnitude"])
    print(f"  feedback loops (SCCs > 1 node): {r['feedback_loop_count']}  "
          f"({r['nodes_in_feedback_loops']} nodes involved)")
    if r["largest_feedback_components"]:
        for c in r["largest_feedback_components"]:
            print(f"    loop ({len(c)}): {', '.join(c)}")
    print(f"  top in-degree:  " + ", ".join(f"{n}({d})" for n, d in r["top_in_degree"]))
    print(f"  top out-degree: " + ", ".join(f"{n}({d})" for n, d in r["top_out_degree"]))
    if r["orphan_nodes"]:
        print(f"  ORPHANS: {', '.join(r['orphan_nodes'])}")
    if r["levers_with_incoming"]:
        print(f"  LEVERS WITH INCOMING (taxonomy violation): {', '.join(r['levers_with_incoming'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
