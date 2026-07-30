#!/usr/bin/env python3
"""
Attention routing, part 1 — how much does each edge actually move the OUTCOME nodes? An ungrounded
edge that changes nothing is low priority; an ungrounded edge that swings the outcome is where scarce
human attention must go. This computes a deterministic per-edge leverage score by ABLATION: remove the
edge, recompute the whole influence table (shock every node +0.25, measure outcome-node movement), and
score leverage as the total absolute change the removal causes. No LLM, no tokens.

Reuses the engine embedded in mc_face_validity.py (same physics as the preview).

Outcome nodes (what leverage is measured against) are resolved, in order: explicit --outcomes;
an invariants file's `config.outcome_nodes`; nodes whose `category` reads as "Outcomes"; else ALL
nodes (with a warning) so leverage still reflects total systemic influence rather than silently
scoring everything zero. No scenario-specific ids are baked in.

Usage:
  python3 edge_leverage.py GRAPH.json [--outcomes id1 id2 ...] [--invariants invariants.yaml]
                           [--shock 0.25] [--ticks 40] [--out edge_leverage.json]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mc_face_validity import Engine


def influence_table(graph, outcomes, shock, ticks):
    """For each node, shock +shock and record net end-state deviation of each outcome node."""
    eng = Engine(graph, rail_zone=0.0, rail_power=1.0)
    outs = [o for o in outcomes if o in eng.base]
    table = {}
    for nid in eng.ids:
        traj = eng.run({0: {nid: shock}}, ticks)
        end = traj[-1]
        table[nid] = {o: end[o] - eng.base[o] for o in outs}
    return table


def resolve_outcomes(graph, explicit, invariants_path):
    """Pick outcome nodes without baking in any scenario. Order: explicit > invariants
    config.outcome_nodes > nodes categorized as Outcomes > all nodes (warned fallback)."""
    ids = [n["id"] for n in graph["nodes"]]
    idset = set(ids)
    if explicit:
        picked = [o for o in explicit if o in idset]
        if picked:
            return picked, "explicit --outcomes"
        print(f"warning: none of --outcomes {explicit} exist in this graph; falling back", file=sys.stderr)
    if invariants_path and os.path.exists(invariants_path):
        try:
            from mc_face_validity import load_invariants
            _, cfg = load_invariants(invariants_path)
            on = cfg.get("outcome_nodes")
            if isinstance(on, str):
                on = [x.strip() for x in on.replace(",", " ").split()]
            picked = [o for o in (on or []) if o in idset]
            if picked:
                return picked, f"invariants config.outcome_nodes ({os.path.basename(invariants_path)})"
        except Exception:
            pass
    picked = [n["id"] for n in graph["nodes"] if "outcome" in str(n.get("category", "")).lower()]
    if picked:
        return picked, "nodes with category ~ 'Outcomes'"
    print("warning: no outcome nodes given or discoverable (no --outcomes, no invariants "
          "config.outcome_nodes, no 'Outcomes' category) — using ALL nodes so leverage reflects total "
          "systemic influence. Pass --outcomes for a sharper ranking.", file=sys.stderr)
    return ids, "ALL nodes (fallback)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graph")
    ap.add_argument("--outcomes", nargs="+", default=None,
                    help="outcome node ids; if omitted, resolved from --invariants / category / all nodes")
    ap.add_argument("--invariants", help="invariants.yaml to read config.outcome_nodes from")
    ap.add_argument("--shock", type=float, default=0.25)
    ap.add_argument("--ticks", type=int, default=40)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    outcomes, src = resolve_outcomes(graph, args.outcomes, args.invariants)
    print(f"leverage outcomes [{src}]: "
          + (", ".join(outcomes) if len(outcomes) <= 8 else f"{len(outcomes)} nodes"))
    base_tbl = influence_table(graph, outcomes, args.shock, args.ticks)

    scores = []
    for e in graph["edges"]:
        ablated = {"nodes": graph["nodes"],
                   "edges": [x for x in graph["edges"] if x["id"] != e["id"]]}
        tbl = influence_table(ablated, outcomes, args.shock, args.ticks)
        delta = 0.0
        for nid in base_tbl:
            for o in base_tbl[nid]:
                delta += abs(base_tbl[nid][o] - tbl.get(nid, {}).get(o, 0.0))
        scores.append({"edge_id": e["id"], "source": e["source"], "target": e["target"],
                       "sign": e["sign"], "strength": e.get("strength"),
                       "leverage": round(delta, 2)})

    scores.sort(key=lambda x: -x["leverage"])
    mx = scores[0]["leverage"] if scores and scores[0]["leverage"] > 0 else 1.0
    for s in scores:
        s["leverage_norm"] = round(s["leverage"] / mx, 3)

    out = args.out or (args.graph.rsplit(".", 1)[0] + ".edge_leverage.json")
    json.dump({"outcomes": outcomes, "outcome_source": src, "shock": args.shock, "edges": scores},
              open(out, "w"), indent=2)
    print(f"edge leverage over {len(outcomes)} outcome node(s) (higher = removal most changes outcome behavior)")
    for s in scores[:12]:
        print(f"  {s['leverage']:8.1f}  {s['leverage_norm']:.2f}  {s['edge_id']}  "
              f"({s['source']} --{s['sign']}{s['strength']}--> {s['target']})")
    print(f"... {len(scores)} edges -> {out}")


if __name__ == "__main__":
    main()
