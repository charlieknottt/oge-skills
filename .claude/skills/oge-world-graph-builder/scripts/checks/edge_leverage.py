#!/usr/bin/env python3
"""
Attention routing, part 1 — how much does each edge actually move the OUTCOME nodes? An ungrounded
edge that changes nothing is low priority; an ungrounded edge that swings the outcome is where scarce
human attention must go. This computes a deterministic per-edge leverage score by ABLATION: remove the
edge, recompute the whole influence table (shock every node +25, measure outcome-node movement), and
score leverage as the total absolute change the removal causes. No LLM, no tokens.

Reuses the engine embedded in mc_face_validity.py (same physics as the preview).

Usage:
  python3 edge_leverage.py GRAPH.json --outcomes ua_war_sustainability ru_war_sustainability frontline_position
                           [--shock 25] [--ticks 40] [--out edge_leverage.json]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graph")
    ap.add_argument("--outcomes", nargs="+",
                    default=["ua_war_sustainability", "ru_war_sustainability", "frontline_position"])
    ap.add_argument("--shock", type=float, default=25.0)
    ap.add_argument("--ticks", type=int, default=40)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    base_tbl = influence_table(graph, args.outcomes, args.shock, args.ticks)

    scores = []
    for e in graph["edges"]:
        ablated = {"nodes": graph["nodes"],
                   "edges": [x for x in graph["edges"] if x["id"] != e["id"]]}
        tbl = influence_table(ablated, args.outcomes, args.shock, args.ticks)
        delta = 0.0
        for nid in base_tbl:
            for o in base_tbl[nid]:
                delta += abs(base_tbl[nid][o] - tbl.get(nid, {}).get(o, 0.0))
        scores.append({"edge_id": e["id"], "source": e["source"], "target": e["target"],
                       "sign": e["sign"], "magnitude": e.get("magnitude"),
                       "leverage": round(delta, 2)})

    scores.sort(key=lambda x: -x["leverage"])
    mx = scores[0]["leverage"] if scores and scores[0]["leverage"] > 0 else 1.0
    for s in scores:
        s["leverage_norm"] = round(s["leverage"] / mx, 3)

    out = args.out or (args.graph.rsplit(".", 1)[0] + ".edge_leverage.json")
    json.dump({"outcomes": args.outcomes, "shock": args.shock, "edges": scores},
              open(out, "w"), indent=2)
    print(f"edge leverage over outcomes {args.outcomes} (higher = removal most changes outcome behavior)")
    for s in scores[:12]:
        print(f"  {s['leverage']:8.1f}  {s['leverage_norm']:.2f}  {s['edge_id']}  "
              f"({s['source']} --{s['sign']}{s['magnitude']}--> {s['target']})")
    print(f"... {len(scores)} edges -> {out}")


if __name__ == "__main__":
    main()
