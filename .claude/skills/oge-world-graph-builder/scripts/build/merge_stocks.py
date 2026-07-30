#!/usr/bin/env python3
"""
merge_stocks.py - combine the per-dimension node proposals into one list (deterministic).

The "pick the nodes" step runs one agent per PMESII dimension in parallel, each writing a
proposal_<dim>.json. This step unions them, resolves exact id collisions so ids are stable for the
rest of the build, flags likely near-duplicates and any count-band problem for the judgment pass
(stock_merge.md) to resolve, and writes the consolidated list.

It never silently drops a node. It only renames colliding ids and raises flags.

Inputs : a directory of proposal_*.json, each { "dimension", "stocks": [...], "sidecar_candidates": [...] }
Outputs: consolidated_stocks.json  { "stocks": [...] }
         merge_report.json          { count, band, in_band, id_collisions, near_duplicates, needs_judgment }

Usage:
    python3 merge_stocks.py --proposals-dir games/G/outputs/stocks --out consolidated_stocks.json \\
            --report merge_report.json --min 25 --max 35
"""
import argparse
import glob
import json
import os
import re
import sys


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def merge(proposals, min_nodes=25, max_nodes=35):
    stocks = []
    for p in proposals:
        for s in (p.get("stocks") or []):
            if isinstance(s, dict):
                stocks.append(dict(s))

    # ---- resolve exact id collisions (keep first, rename later ones, record it) ----
    seen_ids = {}
    id_collisions = []
    for s in stocks:
        sid = s.get("id")
        if not isinstance(sid, str):
            continue
        if sid in seen_ids:
            n = 2
            new = f"{sid}_{n}"
            while new in seen_ids:
                n += 1
                new = f"{sid}_{n}"
            id_collisions.append({"original": sid, "renamed_to": new,
                                  "name": s.get("name"), "note": "two proposals used the same id"})
            s["id"] = new
            seen_ids[new] = s
        else:
            seen_ids[sid] = s

    # ---- flag near-duplicates (same normalized name, or same measures) ----
    near = []
    by_name = {}
    for s in stocks:
        key = _norm(s.get("name")) or _norm(s.get("measures"))
        if not key:
            continue
        if key in by_name:
            near.append({"a": by_name[key], "b": s.get("id"),
                         "reason": f"same normalized name/measures: '{key}'"})
        else:
            by_name[key] = s.get("id")

    count = len(stocks)
    in_band = min_nodes <= count <= max_nodes
    needs_judgment = bool(near) or not in_band

    report = {
        "count": count,
        "band": [min_nodes, max_nodes],
        "in_band": in_band,
        "id_collisions": id_collisions,
        "near_duplicates": near,
        "needs_judgment": needs_judgment,
    }
    return {"stocks": stocks}, report


def _load_proposals(proposals_dir, panel):
    """Read proposals either from a directory of proposal_*.json or from a combined panel output
    ({ "results": [ { "result": {stocks:[...]} } ] })."""
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
    ap = argparse.ArgumentParser(description="Combine per-dimension node proposals into one list.")
    ap.add_argument("--proposals-dir", default=None, help="directory of proposal_*.json files")
    ap.add_argument("--panel", default=None, help="combined panel output ({results:[{result:{stocks}}]})")
    ap.add_argument("--out", default="consolidated_stocks.json", help="output node list path")
    ap.add_argument("--report", default="merge_report.json", help="output merge report path")
    ap.add_argument("--min", type=int, default=25)
    ap.add_argument("--max", type=int, default=35)
    args = ap.parse_args()

    if not (args.proposals_dir or args.panel):
        print("ERROR: pass --proposals-dir or --panel", file=sys.stderr)
        return 2
    try:
        proposals = _load_proposals(args.proposals_dir, args.panel)
    except (OSError, FileNotFoundError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2

    consolidated, report = merge(proposals, args.min, args.max)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    flag = "NEEDS JUDGMENT" if report["needs_judgment"] else "clean"
    print(f"MERGED  {len(proposals)} proposals -> {report['count']} nodes "
          f"(band {args.min}-{args.max}, {'in band' if report['in_band'] else 'OUT OF BAND'}), "
          f"{len(report['near_duplicates'])} near-dup flag(s), "
          f"{len(report['id_collisions'])} id collision(s) -> {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
