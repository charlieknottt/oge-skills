#!/usr/bin/env python3
"""
build_review_artifact.py - render a human-readable review sheet (deterministic).

After the nodes are reviewed, and again after the edges are reviewed, the pipeline emits a markdown
sheet a human can skim and, if they disagree, reject (which re-enters the build at the propose step).
This is the "rejectable review artifact" from the autonomous-run design; it replaces a mid-run hard
pause. No judgment, just rendering.

Inputs : --kind stocks|edges
         --artifact FILE     (stocks: stocks_reviewed.json or nodes.json; edges: world_graph.json)
         --change-log FILE   (optional; the synthesis change_log for this step)
Output : a markdown review sheet.

Usage:
    python3 build_review_artifact.py --kind stocks --artifact stocks_reviewed.json \\
            --change-log stock_change_log.json --out stock_review.md
"""
import argparse
import json
import sys


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _rows_stocks(items):
    out = ["| id | type | pmesii | stock_type | inverted | measures |",
           "|---|---|---|---|---|---|"]
    for n in items:
        out.append("| {id} | {type} | {pmesii} | {stock_type} | {inv} | {measures} |".format(
            id=n.get("id", ""), type=n.get("type", ""), pmesii=n.get("pmesii", ""),
            stock_type=n.get("stock_type", ""), inv=n.get("inverted", ""),
            measures=str(n.get("measures", "")).replace("|", "/")[:80]))
    return out


def _rows_edges(items):
    out = ["| id | source | sign | strength | lag | target | mechanism |",
           "|---|---|---|---|---|---|---|"]
    for e in items:
        strength = e.get("strength", "")
        out.append("| {id} | {src} | {sign} | {st} | {lag} | {tgt} | {mech} |".format(
            id=e.get("id", ""), src=e.get("source", ""), sign=e.get("sign", ""),
            st=strength, lag=e.get("lag", ""), tgt=e.get("target", ""),
            mech=str(e.get("mechanism", "")).replace("|", "/")[:90]))
    return out


def render(kind, artifact, change_log):
    if kind == "stocks":
        items = artifact.get("stocks") or artifact.get("nodes") or []
        title = "Node review"
        rows = _rows_stocks(items)
    else:
        items = artifact.get("edges") or []
        title = "Edge review"
        rows = _rows_edges(items)

    lines = [f"# {title}", "",
             f"{len(items)} item(s). Skim this and reject if something is wrong; a rejection re-enters "
             f"the build at the propose step.", ""]
    lines += rows
    lines.append("")

    changes = (change_log.get("change_log") if isinstance(change_log, dict) else change_log) or []
    if changes:
        lines += ["## What review changed", ""]
        for c in changes:
            if isinstance(c, dict):
                lines.append(f"- **{c.get('change', '(change)')}** "
                             f"({c.get('driven_by', 'review')})")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Render a human-readable review sheet.")
    ap.add_argument("--kind", required=True, choices=["stocks", "edges"])
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--change-log", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        artifact = _load(args.artifact)
        change_log = _load(args.change_log) if args.change_log else {}
    except FileNotFoundError as ex:
        print(f"ERROR: file not found: {ex.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as ex:
        print(f"ERROR: invalid JSON: {ex}", file=sys.stderr)
        return 2

    md = render(args.kind, artifact, change_log)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"WROTE  {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
