#!/usr/bin/env python3
"""
Calibration harness, step 1 — plant known errors into a world graph so we can later measure whether
the LLM review panel actually catches them. Without this, "the panel is skeptical, trust it" is
unfalsifiable and the whole review just launders one model agreeing with another.

Produces ONE mutated copy of the graph with ~K single-defect edges spread across error classes on a
DIFFICULTY LADDER, plus a ground-truth manifest and a control set (untouched edges) so a paired
false-positive rate can be computed. One mutated graph (not K graphs) keeps the panel to a single
blind pass. The panel later reviews all edges blind to which/how-many are planted.

Error classes:
  flipped_sign          + <-> -                              (also caught deterministically by mechanism_audit)
  magnitude_shift       jump to the opposite extreme (0.3<->0.9)  (calibration expects LOW catch — unfalsifiable from doc)
  wrong_lag             lag shifted across a band            (calibration expects LOW catch)
  fabricated_mechanism  mechanism replaced with plausible-but-false sentence, sign kept
  deleted_edge          a real edge removed (tests the missing-edge lens; recorded in manifest)

Difficulty is a heuristic proxy: high-magnitude edges are "obvious" when flipped, low ones "subtle".
This is honest-but-imperfect (see guide/3-realism-checks.md); the real doc-groundedness of each edge
comes from the provenance pass, which can refine difficulty later.

Usage:
  python3 plant_errors.py GRAPH.json --out-dir OUTDIR [--seed 7] [--per-class 3]
Writes OUTDIR/{mutated_graph.json, plant_manifest.json}.
"""
import argparse
import json
import os
import random

def _magnum(m):
    # read magnitude as a number, tolerating the legacy weak/moderate/strong strings
    if isinstance(m, (int, float)):
        return float(m)
    return {"weak": 0.35, "moderate": 0.6, "strong": 0.9}.get(m, 0.6)


FABRICATED = [
    "The two are linked through a coordination channel that synchronizes their levels over time",
    "A shared logistics dependency makes one track the other after a short delay",
    "Institutional feedback couples these so a rise in one is routinely offset in the other",
    "A common upstream driver causes them to move together across the campaign",
]


def difficulty_for(edge, klass):
    mag = _magnum(edge.get("magnitude", 0.6))
    if klass == "flipped_sign":
        return "obvious" if mag >= 0.75 else ("subtle" if mag < 0.45 else "medium")
    if klass == "fabricated_mechanism":
        return "medium"
    if klass == "deleted_edge":
        return "obvious" if mag >= 0.75 else "subtle"
    if klass == "magnitude_shift":
        return "subtle"      # unfalsifiable from a qualitative doc
    if klass == "wrong_lag":
        return "subtle"
    return "medium"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graph")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--per-class", type=int, default=3)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    graph = json.load(open(args.graph))
    edges = graph["edges"]
    os.makedirs(args.out_dir, exist_ok=True)

    # choose disjoint edges to mutate (one defect each); the rest are controls
    idx = list(range(len(edges)))
    rng.shuffle(idx)
    classes = ["flipped_sign", "magnitude_shift", "wrong_lag", "fabricated_mechanism", "deleted_edge"]
    picks, used = {}, set()
    for klass in classes:
        chosen = []
        for i in idx:
            if i in used:
                continue
            e = edges[i]
            chosen.append(i)
            used.add(i)
            if len(chosen) >= args.per_class:
                break
        picks[klass] = chosen

    mutated = json.loads(json.dumps(graph))  # deep copy
    medges = mutated["edges"]
    manifest = {"graph": os.path.abspath(args.graph), "seed": args.seed, "mutations": [], "controls": []}
    mid = 0
    delete_ids = set()

    for klass, indices in picks.items():
        for i in indices:
            e = medges[i]
            mid += 1
            m = {"mutation_id": f"m{mid:03d}", "error_class": klass, "edge_id": e["id"],
                 "source": e["source"], "target": e["target"], "difficulty": difficulty_for(e, klass)}
            if klass == "flipped_sign":
                m["from"] = {"sign": e["sign"]}
                e["sign"] = "-" if e["sign"] == "+" else "+"
                m["to"] = {"sign": e["sign"]}
            elif klass == "magnitude_shift":
                old = e.get("magnitude", 0.6)
                new = 0.9 if _magnum(old) < 0.55 else 0.3   # jump to the opposite extreme
                m["from"] = {"magnitude": old}
                e["magnitude"] = new
                m["to"] = {"magnitude": new}
            elif klass == "wrong_lag":
                old = int(e.get("lag", 1))
                new = 6 if old <= 2 else 1
                m["from"] = {"lag": old}
                e["lag"] = new
                m["to"] = {"lag": new}
            elif klass == "fabricated_mechanism":
                m["from"] = {"mechanism": e.get("mechanism", "")}
                e["mechanism"] = FABRICATED[mid % len(FABRICATED)]
                m["to"] = {"mechanism": e["mechanism"]}
            elif klass == "deleted_edge":
                m["from"] = {"present": True, "mechanism": e.get("mechanism", ""),
                             "sign": e.get("sign"), "magnitude": e.get("magnitude")}
                m["to"] = {"present": False}
                delete_ids.add(e["id"])
            manifest["mutations"].append(m)

    if delete_ids:
        mutated["edges"] = [e for e in medges if e["id"] not in delete_ids]
    manifest["controls"] = [e["id"] for e in mutated["edges"]
                            if e["id"] not in {m["edge_id"] for m in manifest["mutations"]}]

    json.dump(mutated, open(os.path.join(args.out_dir, "mutated_graph.json"), "w"), indent=1)
    json.dump(manifest, open(os.path.join(args.out_dir, "plant_manifest.json"), "w"), indent=2)

    by_class = {}
    for m in manifest["mutations"]:
        by_class.setdefault(m["error_class"], 0)
        by_class[m["error_class"]] += 1
    print(f"planted {len(manifest['mutations'])} mutations ({by_class}); "
          f"{len(manifest['controls'])} controls; deleted {len(delete_ids)} edges")
    print(f"wrote {args.out_dir}/mutated_graph.json + plant_manifest.json")


if __name__ == "__main__":
    main()
