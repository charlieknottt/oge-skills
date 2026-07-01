#!/usr/bin/env python3
"""
The enforcer. mc_face_validity.py PRODUCES a face_validity block; this DECIDES whether the build may
ship. It reads that block plus any human/reconciliation dispositions and applies one policy:

  a check is RESOLVED iff  status == "pass"
                           OR it has a disposition of "waived" WITH a non-empty reason
                           OR it has a disposition of "fixed"  (a reconcile auto-apply or human edit)
  otherwise it is BLOCKING.

Exit 0 only if every check is resolved AND the block was actually generated (a missing block fails —
that closes the loop where skipping the checks would look like a pass). Prints what blocks and why.

Usage: python3 gate_face_validity.py FACE_VALIDITY.json
  (accepts either {"face_validity": {...}} or a bare face_validity object)
"""
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    args = ap.parse_args()
    doc = json.load(open(args.report))
    fv = doc.get("face_validity", doc)

    if not fv.get("generated"):
        print("FAIL: no face_validity block was generated (checks did not run) — cannot pass by omission")
        sys.exit(2)

    checks = fv.get("checks", [])
    disp = {d.get("id"): d for d in fv.get("dispositions", [])}
    blocking = []
    for c in checks:
        if c.get("status") == "pass":
            continue
        d = disp.get(c["id"], {})
        decision = d.get("decision") or d.get("human")
        if decision == "waived" and (d.get("reason") or "").strip():
            continue
        if decision in ("fixed", "accept"):
            continue
        blocking.append(c)

    n_waived = sum(1 for c in checks if c.get("status") != "pass" and c["id"] in disp)
    if blocking:
        print(f"BLOCKED: {len(blocking)} face-validity check(s) unresolved:")
        for c in blocking:
            print(f"  - {c['id']}: {c.get('status')} ({c.get('metric')}={c.get('value')}, "
                  f"need {c.get('threshold')})  [{c.get('evidence','')[:90]}]")
        print("\nResolve each by fixing the graph or recording a waiver{decision:'waived',reason:...} "
              "in dispositions[].")
        sys.exit(1)

    print(f"face-validity gate PASS — {len(checks)} checks "
          f"({sum(1 for c in checks if c.get('status')=='pass')} pass, {n_waived} waived/fixed)")
    sys.exit(0)


if __name__ == "__main__":
    main()
