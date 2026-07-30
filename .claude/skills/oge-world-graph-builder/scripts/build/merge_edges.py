#!/usr/bin/env python3
"""
merge_edges.py - combine the edge proposals into one edge set (deterministic).

The "draw the edges" step can fan out (one agent per node or a single pass), so the same directed
edge can be proposed twice, and two agents can propose the same pair with opposite signs. This step
unions the proposals, gives every edge a stable id, drops self-loops, merges exact duplicates of the
same directed edge, and FLAGS sign conflicts for the edge synthesis step to resolve by re-reading the
mechanism. It never averages a sign or invents a resolution.

Note: A->B and B->A are two different directed edges (legitimate feedback), not a duplicate; both are
kept. A duplicate is the same (source, target) proposed more than once.

Inputs : a directory of proposal_*.json, each { "focus_node"?, "edges": [ {source,target,sign,strength,lag,mechanism} ] }
Outputs: consolidated_edges.json  { "edges": [...] }  (ids assigned, one per directed pair)
         merge_report.json         { count, sign_conflicts, merged_duplicates, needs_judgment }

Usage:
    python3 merge_edges.py --proposals-dir games/G/outputs/edges --out consolidated_edges.json \\
            --report merge_report.json
"""
import argparse
import glob
import json
import os
import re
import sys


def _strength(e):
    v = e.get("strength")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _edge_id(src, tgt, used):
    base = f"e_{src}_{tgt}"
    base = re.sub(r"[^a-z0-9_]", "", base.lower())
    eid, n = base, 2
    while eid in used:
        eid = f"{base}_{n}"
        n += 1
    used.add(eid)
    return eid


def merge(proposals):
    raw = []
    for p in proposals:
        for e in (p.get("edges") or []):
            if isinstance(e, dict):
                raw.append(dict(e))

    by_pair = {}          # (src,tgt) -> chosen edge
    sign_conflicts = []
    merged_dupes = []
    dropped_selfloops = 0

    for e in raw:
        src, tgt = e.get("source"), e.get("target")
        if not (isinstance(src, str) and isinstance(tgt, str)):
            continue
        if src == tgt:
            dropped_selfloops += 1
            continue
        key = (src, tgt)
        if key not in by_pair:
            by_pair[key] = e
        else:
            kept = by_pair[key]
            if kept.get("sign") != e.get("sign"):
                sign_conflicts.append({"pair": f"{src} -> {tgt}",
                                       "kept_sign": kept.get("sign"), "other_sign": e.get("sign"),
                                       "kept_mechanism": kept.get("mechanism"),
                                       "other_mechanism": e.get("mechanism")})
                # keep the stronger of the two so synthesis has the more-committed claim to judge
                if (_strength(e) or 0) > (_strength(kept) or 0):
                    by_pair[key] = e
            else:
                merged_dupes.append(f"{src} -> {tgt}")
                if (_strength(e) or 0) > (_strength(kept) or 0):
                    by_pair[key] = e  # same sign, keep the stronger claim

    used_ids = set()
    edges = []
    for (src, tgt), e in by_pair.items():
        out = dict(e)
        out["source"], out["target"] = src, tgt
        out["id"] = e.get("id") if isinstance(e.get("id"), str) and e["id"].startswith("e_") and e["id"] not in used_ids else _edge_id(src, tgt, used_ids)
        used_ids.add(out["id"])
        s = _strength(out)
        if s is not None:
            out["strength"] = s
        edges.append(out)

    report = {
        "count": len(edges),
        "dropped_selfloops": dropped_selfloops,
        "merged_duplicates": merged_dupes,
        "sign_conflicts": sign_conflicts,
        "needs_judgment": bool(sign_conflicts),
    }
    return {"edges": edges}, report


def _load_proposals(proposals_dir, panel):
    """Read edge proposals from a directory of proposal_*.json or a combined panel output
    ({ "results": [ { "result": {edges:[...]} } ] })."""
    if panel:
        with open(panel, "r", encoding="utf-8") as f:
            doc = json.load(f)
        results = doc.get("results") if isinstance(doc, dict) else doc
        return [r.get("result", r) for r in (results or []) if isinstance(r, dict)]
    paths = sorted(glob.glob(os.path.join(proposals_dir, "proposal_*.json")))
    if not paths:
        raise FileNotFoundError(f"no proposal_*.json in {proposals_dir}")
    out = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def main():
    ap = argparse.ArgumentParser(description="Combine edge proposals into one edge set.")
    ap.add_argument("--proposals-dir", default=None, help="directory of proposal_*.json files")
    ap.add_argument("--panel", default=None, help="combined panel output ({results:[{result:{edges}}]})")
    ap.add_argument("--out", default="consolidated_edges.json")
    ap.add_argument("--report", default="merge_report.json")
    args = ap.parse_args()

    if not (args.proposals_dir or args.panel):
        print("ERROR: pass --proposals-dir or --panel", file=sys.stderr)
        return 2
    try:
        proposals = _load_proposals(args.proposals_dir, args.panel)
    except (OSError, FileNotFoundError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2

    consolidated, report = merge(proposals)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    flag = "NEEDS JUDGMENT (sign conflicts)" if report["needs_judgment"] else "clean"
    print(f"MERGED  {len(proposals)} proposals -> {report['count']} edges, "
          f"{len(report['merged_duplicates'])} dup(s) merged, "
          f"{report['dropped_selfloops']} self-loop(s) dropped, "
          f"{len(report['sign_conflicts'])} sign conflict(s) -> {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
