#!/usr/bin/env python3
"""
Calibration harness, final step — join the blind panel's output back to the planted-error manifest and
compute, per error class: recall (catch rate), plus a false-positive rate on untouched control edges,
bootstrap confidence intervals, a catch-rate-vs-difficulty curve, and a coverage map (which classes
clear their pre-registered GO threshold). This is the number that licenses trusting the panel at all.

HONESTY: planted errors are, by construction, sharper than real ones, so recall here is an UPPER BOUND
on real-error detection. The scorecard states this. Classes below threshold (predictably strength/lag)
are declared "not covered by automated review — human required."

Inputs:
  --manifest  plant_manifest.json  (ground truth)
  --panel     the workflow output file (wrapper {result:{bundles:[...]}} or bare {bundles:[...]})
  --map       review_map_<tag>.json  (bundle -> edge_ids, for missing-edge attribution)
  --thresholds calibration thresholds JSON (optional; defaults below, documented in guide/3-realism-checks.md)
Writes calibration.json + prints the scorecard.
"""
import argparse
import json
import os
import random

# Pre-registered GO thresholds (recall floor, FPR ceiling) per class. Mirror of guide/3-realism-checks.md.
DEFAULT_THRESH = {
    "flipped_sign":         {"recall_min": 0.80, "fpr_max": 0.15},
    "fabricated_mechanism": {"recall_min": 0.60, "fpr_max": 0.20},
    "deleted_edge":         {"recall_min": 0.40, "fpr_max": 0.25},
    "strength_shift":      {"recall_min": 0.50, "fpr_max": 0.20},
    "wrong_lag":            {"recall_min": 0.50, "fpr_max": 0.20},
}
# which reviewer signals count as "catching" each class
FIX_FIELD = {"flipped_sign": "sign", "strength_shift": "strength", "wrong_lag": "lag",
             "fabricated_mechanism": "mechanism"}
ERR_CLASS = {"flipped_sign": "flipped_sign", "strength_shift": "wrong_strength",
             "wrong_lag": "wrong_lag", "fabricated_mechanism": "fabricated_mechanism"}


def unwrap(doc, key="bundles"):
    if isinstance(doc, dict):
        if key in doc:
            return doc
        if isinstance(doc.get("result"), dict) and key in doc["result"]:
            return doc["result"]
    return None


def load_panel(path):
    doc = json.load(open(path))
    got = unwrap(doc)
    if not got:
        raise SystemExit(f"no 'bundles' array found in {path}")
    verdict_by_edge, missing_pairs = {}, set()
    for b in got["bundles"]:
        rev = b.get("review") or {}
        for e in rev.get("edges", []) or []:
            verdict_by_edge[e["edge_id"]] = e
        for m in rev.get("missing_edges", []) or []:
            missing_pairs.add((m.get("source"), m.get("target")))
    return verdict_by_edge, missing_pairs


def caught(mut, verdict_by_edge, missing_pairs):
    klass = mut["error_class"]
    if klass == "deleted_edge":
        return (mut["source"], mut["target"]) in missing_pairs
    v = verdict_by_edge.get(mut["edge_id"])
    if not v or v.get("verdict") != "flag":
        return False
    # count as caught if the flagged class matches OR the proposed fix targets the right field
    if v.get("error_class") == ERR_CLASS.get(klass):
        return True
    fix = v.get("proposed_fix") or {}
    if fix.get("field") == FIX_FIELD.get(klass):
        return True
    # fabricated: also caught if provenance says existence/sign unsupported
    if klass == "fabricated_mechanism":
        prov = v.get("provenance", {})
        if any((prov.get(a, {}) or {}).get("grounding") == "unsupported" for a in ("existence", "sign")):
            return True
    return False


def boot_ci(hits, n, iters=2000, seed=1):
    if n == 0:
        return [None, None]
    rng = random.Random(seed)
    data = [1] * hits + [0] * (n - hits)
    means = []
    for _ in range(iters):
        s = sum(data[rng.randrange(n)] for _ in range(n))
        means.append(s / n)
    means.sort()
    return [round(means[int(0.05 * iters)], 3), round(means[int(0.95 * iters)], 3)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--panel", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--thresholds", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    thresh = json.load(open(args.thresholds)) if args.thresholds else DEFAULT_THRESH
    verdict_by_edge, missing_pairs = load_panel(args.panel)

    # per-class + per-difficulty recall
    by_class, by_diff = {}, {}
    for mut in manifest["mutations"]:
        k, d = mut["error_class"], mut["difficulty"]
        hit = caught(mut, verdict_by_edge, missing_pairs)
        by_class.setdefault(k, []).append(hit)
        by_diff.setdefault(d, []).append(hit)

    # false positives on controls: a control flagged is a false positive vs planted-error ground truth
    # (caveat: some may be REAL defects in the original graph — reported separately, not as pure error)
    controls = manifest["controls"]
    fp = [cid for cid in controls if (verdict_by_edge.get(cid, {}) or {}).get("verdict") == "flag"]
    fpr = round(len(fp) / len(controls), 3) if controls else 0.0

    classes = {}
    for k, hits in by_class.items():
        n = len(hits)
        r = sum(hits)
        recall = round(r / n, 3) if n else None
        th = thresh.get(k, {"recall_min": 0.5, "fpr_max": 0.2})
        ci = boot_ci(r, n)
        classes[k] = {"n": n, "recall": recall, "recall_ci90": ci,
                      "threshold_recall_min": th["recall_min"], "threshold_fpr_max": th["fpr_max"],
                      # trusted only if the CI LOWER BOUND clears the floor AND overall FPR under ceiling
                      "trusted": bool(ci[0] is not None and ci[0] >= th["recall_min"] and fpr <= th["fpr_max"])}
    difficulty_curve = {d: round(sum(h) / len(h), 3) for d, h in sorted(by_diff.items())}

    out = {
        "n_mutations": len(manifest["mutations"]), "n_controls": len(controls),
        "false_positive_rate": fpr, "false_positive_edges": fp,
        "per_class": classes, "difficulty_curve": difficulty_curve,
        "coverage_map": {k: ("trusted" if v["trusted"] else "NOT COVERED — human required")
                         for k, v in classes.items()},
        "note": ("Recall is measured on PLANTED errors, which are sharper than real ones; treat these "
                 "as an upper bound. FPR on controls may include real defects in the original graph."),
    }
    out_path = args.out or os.path.join(os.path.dirname(args.manifest), "calibration.json")
    json.dump(out, open(out_path, "w"), indent=2)

    print("=== CALIBRATION SCORECARD ===")
    print(f"{'class':22} {'n':>3} {'recall':>7} {'CI90':>14} {'thr':>5}  coverage")
    for k, v in classes.items():
        print(f"{k:22} {v['n']:>3} {str(v['recall']):>7} {str(v['recall_ci90']):>14} "
              f"{v['threshold_recall_min']:>5}  {'TRUSTED' if v['trusted'] else 'not covered'}")
    print(f"\nfalse-positive rate on {len(controls)} controls: {fpr}  (flagged: {fp[:6]}{'...' if len(fp)>6 else ''})")
    print(f"difficulty curve (recall by tier): {difficulty_curve}")
    print(f"\n{out['note']}\n-> {out_path}")


if __name__ == "__main__":
    main()
