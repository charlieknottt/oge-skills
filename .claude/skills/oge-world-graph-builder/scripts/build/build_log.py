#!/usr/bin/env python3
"""
build_log.py - assemble the generation log (deterministic).

A plain-language record of what the build produced: the node list with each node's rationale, the
edge list with each edge's mechanism, and any synthesis change logs appended. It is the paper trail
for a finished graph. No judgment, just rendering.

Inputs : --graph  world_graph.json (or a .runtime.json)
         --change-logs  comma-separated change-log JSON files (optional)
Output : generation_log.md

Usage:
    python3 build_log.py --graph world_graph.json \\
            --change-logs stock_change_log.json,edge_change_log.json --out generation_log.md
"""
import argparse
import json
import sys


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render(graph, change_logs):
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    lines = [f"# Generation log: {graph.get('scenario', '(scenario)')}", "",
             f"{len(nodes)} nodes, {len(edges)} edges.", "",
             "## Nodes", ""]
    for n in nodes:
        base = n.get("baseline", "")
        lines.append(f"- **{n.get('label', n.get('id'))}** (`{n.get('id')}`, {n.get('type')}, "
                     f"{n.get('pmesii', '')}, baseline {base}): {n.get('rationale', '')}")
    lines += ["", "## Edges", ""]
    for e in edges:
        strength = e.get("strength", "")
        lines.append(f"- `{e.get('id')}` {e.get('source')} --({e.get('sign')}{strength}, "
                     f"lag {e.get('lag')})--> {e.get('target')}: {e.get('mechanism', '')}")

    for cl in change_logs:
        changes = (cl.get("change_log") if isinstance(cl, dict) else cl) or []
        if changes:
            lines += ["", "## Review changes", ""]
            for c in changes:
                if isinstance(c, dict):
                    lines.append(f"- {c.get('change', '')} ({c.get('driven_by', '')})")
            break
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Assemble the generation log.")
    ap.add_argument("--graph", required=True)
    ap.add_argument("--change-logs", default=None, help="comma-separated change-log JSON paths")
    ap.add_argument("--out", default="generation_log.md")
    args = ap.parse_args()

    try:
        graph = _load(args.graph)
        cls = []
        if args.change_logs:
            for p in args.change_logs.split(","):
                p = p.strip()
                if p:
                    cls.append(_load(p))
    except FileNotFoundError as ex:
        print(f"ERROR: file not found: {ex.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as ex:
        print(f"ERROR: invalid JSON: {ex}", file=sys.stderr)
        return 2

    md = render(graph, cls)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"WROTE  {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
