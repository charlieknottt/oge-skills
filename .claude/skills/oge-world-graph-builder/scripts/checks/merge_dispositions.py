#!/usr/bin/env python3
"""
Close the gate loop. mc_face_validity emits checks with an empty dispositions[]; reconcile and the human
sign-off produce decisions elsewhere. This merges those decisions INTO the face_validity report's
dispositions[] so `gate_face_validity.py` can actually pass once everything is resolved. Without this
step the gate blocks forever even after the work is done.

Sources merged (later overrides earlier):
  --reconcile-disp  reconcile_dispositions.json  (auto-fixed checks -> decision "fixed")
  --signoff         human decisions {dispositions:[{id, decision: waived|fixed|accept, reason}]}

Writes the updated face_validity report in place (or --out) and prints the gate outcome.
"""
import argparse
import json
import subprocess
import sys
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("face_validity")
    ap.add_argument("--reconcile-disp")
    ap.add_argument("--signoff")
    ap.add_argument("--out")
    args = ap.parse_args()

    doc = json.load(open(args.face_validity))
    fv = doc.get("face_validity", doc)
    merged = {}

    if args.reconcile_disp and os.path.exists(args.reconcile_disp):
        for d in json.load(open(args.reconcile_disp)).get("dispositions", []):
            if d.get("decision") == "fixed":
                merged[d["id"]] = {"id": d["id"], "decision": "fixed",
                                   "reason": d.get("note", "auto-fixed by reconcile (rails 1-4)")}
    if args.signoff and os.path.exists(args.signoff):
        for d in json.load(open(args.signoff)).get("dispositions", []):
            merged[d["id"]] = {"id": d["id"], "decision": d.get("decision"),
                               "reason": d.get("reason", "")}

    fv["dispositions"] = list(merged.values())
    out = args.out or args.face_validity
    json.dump(doc if "face_validity" in doc else fv, open(out, "w"), indent=2)
    print(f"merged {len(merged)} disposition(s) into {out}")

    # run the gate and surface its verdict
    gate = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate_face_validity.py")
    r = subprocess.run([sys.executable, gate, out], capture_output=True, text=True)
    print(r.stdout.strip())
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
