#!/usr/bin/env python3
"""
Attention router. Fuse the deterministic leverage, the panel's per-edge provenance/flags, the
calibration coverage map, and force-route signals (MC failure slices, network-dominated edges) into a
ranked human queue of the ~10-15 edges that most deserve scarce human attention. The point: an
ungrounded edge that moves nothing is low priority; an ungrounded MAGNITUDE on a high-leverage outcome
edge — exactly the attribute calibration proved the panel CAN'T check — is top priority.

priority ≈ leverage_norm × ungroundedness × review_uncertainty, with hard force-routes pinned on top.

Inputs:
  --leverage     edge_leverage.json
  --review       production panel output (workflow {result:{bundles:[{review:{edges:[...]}}]}}) on the REAL graph
  --calibration  calibration.json (coverage map: which attributes are trusted)
  --mechaudit    mechanism_audit.json (network_dominated_edges) [optional]
  --reconcile    reconcile_packets.json (slice edges get force-routed) [optional]
Writes human_review_queue.json + prints the top items.
"""
import argparse
import json
import os

GROUND_W = {"stated": 0.0, "implied": 0.25, "model-inferred": 0.7, "unsupported": 1.0}


def load_review(path):
    if not path or not os.path.exists(path):
        return {}
    doc = json.load(open(path))
    r = doc.get("result", doc)
    by_edge = {}
    for b in r.get("bundles", []):
        for e in (b.get("review") or {}).get("edges", []) or []:
            by_edge[e["edge_id"]] = e
    return by_edge


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leverage", required=True)
    ap.add_argument("--review")
    ap.add_argument("--calibration")
    ap.add_argument("--mechaudit")
    ap.add_argument("--reconcile")
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    lev = {e["edge_id"]: e for e in json.load(open(args.leverage))["edges"]}
    review = load_review(args.review)
    coverage = (json.load(open(args.calibration)).get("coverage_map", {})
                if args.calibration and os.path.exists(args.calibration) else {})
    netdom = set()
    if args.mechaudit and os.path.exists(args.mechaudit):
        for d in json.load(open(args.mechaudit)).get("network_dominated_edges", []):
            netdom.add((d.get("source"), d.get("target")))
    slice_edges = set()
    if args.reconcile and os.path.exists(args.reconcile):
        for p in json.load(open(args.reconcile)).get("packets", []):
            for e in p.get("slice", []):
                slice_edges.add(e["id"])

    # attributes the panel is NOT trusted to check → their ungroundedness matters more
    uncovered = {"magnitude": coverage.get("magnitude_shift") != "trusted",
                 "lag": coverage.get("wrong_lag") != "trusted"}

    rows = []
    for eid, L in lev.items():
        r = review.get(eid, {})
        prov = r.get("provenance", {})
        # ungroundedness weighted toward calibration-uncovered attributes
        ug, wsum = 0.0, 0.0
        for attr in ("existence", "sign", "magnitude", "lag"):
            g = (prov.get(attr, {}) or {}).get("grounding", "model-inferred")
            w = 2.0 if uncovered.get(attr) else 1.0
            ug += GROUND_W.get(g, 0.7) * w
            wsum += w
        ungrounded = ug / wsum if wsum else 0.7
        conf = {"low": 1.0, "medium": 0.6, "high": 0.3}.get(r.get("confidence", "medium"), 0.6)
        flagged = r.get("verdict") == "flag"
        base = L["leverage_norm"] * (0.5 + ungrounded) * (0.5 + 0.5 * conf)
        # Force-route only on a per-EDGE defect signal (a flag or a network-dominated edge). MC-slice
        # membership is NOT a force-route: the whole slice is already carried by its reconciliation
        # ticket (dossier §4), so pinning all ~16 slice edges here would double-count and crowd out the
        # high-leverage ungrounded edges this queue exists to surface. Slice membership is a soft +.
        force = flagged or (L["source"], L["target"]) in netdom
        in_slice = eid in slice_edges
        rows.append({
            "edge_id": eid, "source": L["source"], "target": L["target"],
            "leverage_norm": L["leverage_norm"], "ungrounded": round(ungrounded, 2),
            "flagged": flagged, "error_class": r.get("error_class"),
            "force_routed": force,
            "reasons": ([("flagged:" + str(r.get("error_class"))) if flagged else None,
                         "mc_slice" if in_slice else None,
                         "network_dominated" if (L["source"], L["target"]) in netdom else None]),
            "priority": round((1.0 if force else 0.0) + (0.15 if in_slice else 0.0) + base, 3),
            "question": _question(L, prov, uncovered, r),
        })
    rows.sort(key=lambda x: -x["priority"])
    for x in rows:
        x["reasons"] = [r for r in x["reasons"] if r]
    queue = rows[:args.top]
    json.dump({"queue": queue, "n_total_edges": len(rows)}, open(args.out, "w"), indent=2)
    print(f"human review queue — top {len(queue)} of {len(rows)} edges by priority")
    for x in queue:
        print(f"  {x['priority']:5.2f}  {x['edge_id']:26} lev={x['leverage_norm']:.2f} "
              f"ungr={x['ungrounded']:.2f} {'FLAG:'+str(x['error_class']) if x['flagged'] else ''} "
              f"{'['+','.join(x['reasons'])+']' if x['reasons'] else ''}")
    print(f"-> {args.out}")


def _question(L, prov, uncovered, r):
    if r.get("verdict") == "flag":
        return f"Panel flagged {r.get('error_class')}: {r.get('reasoning','')}. Confirm?"
    magg = (prov.get("magnitude", {}) or {}).get("grounding")
    if uncovered.get("magnitude") and magg in ("model-inferred", "unsupported", None) and L["leverage_norm"] > 0.5:
        return (f"'{L['source']} --{L['magnitude']}--> {L['target']}' is high-leverage and its magnitude "
                f"is not doc-grounded (panel can't verify magnitude). Is '{L['magnitude']}' right?")
    return "Spot-check: high-leverage edge; confirm sign/mechanism against the scenario."


if __name__ == "__main__":
    main()
