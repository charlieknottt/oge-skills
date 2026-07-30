#!/usr/bin/env python3
"""
Assemble the single low-load human sign-off packet. Pure Python, no tokens. Merges the calibration
scorecard (the trust banner), any auto-applied changes, the ranked human review queue, the MC
reconciliation tickets, and the deterministic-gate outputs into `sme_dossier.md` (read this) and
`sme_dossier.json` (whose dispositions[] the gate consumes).

The human reads ONE page: what the reviewer is trusted for, what got auto-fixed, the ~10-15 edges that
need a human eye, the naive/ambiguous invariant calls, and the residual-risk statement — instead of
78 edges × 4 attributes.

Inputs (all optional except --out-dir; missing pieces are noted, not fatal):
  --calibration calibration.json  --queue human_review_queue.json
  --reconcile-disp reconcile_dispositions.json  --change-log change_log.json
  --face-validity world_graph.face_validity.json
"""
import argparse
import json
import os


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration")
    ap.add_argument("--queue")
    ap.add_argument("--reconcile-disp")
    ap.add_argument("--change-log")
    ap.add_argument("--face-validity")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    calib = load(args.calibration) if args.calibration else None
    queue = load(args.queue) if args.queue else None
    rdisp = load(args.reconcile_disp) if args.reconcile_disp else None
    clog = load(args.change_log) if args.change_log else None
    fv = load(args.face_validity) if args.face_validity else None
    fvb = (fv or {}).get("face_validity", fv) if fv else None

    L = []
    L.append("# SME Realism Review — Sign-off Dossier\n")
    L.append("*One-page human gate. The automated layers narrowed 78 edges × 4 attributes down to the "
             "items below. Sign each: accept / fix / waive-with-reason.*\n")

    # 1. Trust banner
    L.append("## 1. Reviewer trust (calibration)")
    if not calib:
        L.append("- **No calibration run found — the panel's verdicts are UNTRUSTED. Treat this as "
                 "vibes, not review.**\n")
    else:
        cov = calib.get("coverage_map", {})
        trusted = [k for k, v in cov.items() if v == "trusted"]
        L.append(f"- False-positive rate on controls: **{calib.get('false_positive_rate')}**  ·  "
                 f"difficulty curve: {calib.get('difficulty_curve')}")
        L.append(f"- **Trusted for:** {', '.join(trusted) if trusted else 'NOTHING — panel unreliable, manual audit required'}")
        for k, v in cov.items():
            pc = calib.get("per_class", {}).get(k, {})
            L.append(f"  - `{k}`: recall {pc.get('recall')} (CI {pc.get('recall_ci90')}) → **{v}**")
        L.append(f"- *{calib.get('note','')}*\n")

    # 2. Auto-applied changes
    L.append("## 2. Auto-applied fixes (reversible; review)")
    changes = (clog or {}).get("change_log", []) if clog else []
    if not changes:
        L.append("- none\n")
    else:
        for c in changes:
            L.append(f"- `{c['edge_id']}` {c['field']}: `{c['from']}` → `{c['to']}`  "
                     f"({c.get('basis', 'rails 1-4 passed')}; quote: \"{(c.get('grounding_quote') or '')[:80]}\")")
        L.append("")

    # 3. Human review queue
    L.append("## 3. Edges needing a human eye (ranked)")
    q = (queue or {}).get("queue", []) if queue else []
    if not q:
        L.append("- (queue not built)\n")
    else:
        for x in q:
            tags = (" [" + ",".join(x["reasons"]) + "]") if x.get("reasons") else ""
            L.append(f"- **{x['edge_id']}** ({x['source']}→{x['target']}, lev {x['leverage_norm']}, "
                     f"ungrounded {x['ungrounded']}){tags}\n    - {x['question']}\n    - [ ] accept  [ ] fix  [ ] waive: ____")
        L.append("")

    # 4. Reconciliation tickets
    L.append("## 4. Monte Carlo reconciliation tickets")
    tix = (rdisp or {}).get("dispositions", []) if rdisp else []
    if not tix:
        L.append("- (none / not run)\n")
    else:
        for d in tix:
            status = "AUTO-FIXED" if d.get("auto_applied") else "**HUMAN**"
            L.append(f"- `{d['id']}` → {d['disposition']} ({status})\n    - {d.get('reasoning','')}\n    - {d.get('note','')}")
            if d.get("proposed_invariant_amendment"):
                L.append(f"    - proposed invariant amendment: {d['proposed_invariant_amendment']}")
            if not d.get("auto_applied"):
                L.append("    - [ ] accept  [ ] fix graph  [ ] amend invariant  [ ] waive: ____")
        L.append("")

    # 5. Residual risk
    L.append("## 5. Residual risk (sign to accept)")
    L.append("- **Magnitude and lag are not automatically assured** — unfalsifiable from a qualitative "
             "scenario; the high-leverage ones are in the queue above for your judgment.")
    L.append("- **Omitted edges** are the weakest detection class; the panel may miss a driver the "
             "scenario implies.")
    L.append("- Calibration recall is an **upper bound** (planted errors are sharper than real ones); "
             "true recall is lower by an unknown margin.")
    L.append("- The reviewer is an LLM and shares training with the builder; it will not challenge "
             "shared priors a contrarian human SME would.")
    L.append("- [ ] I accept the residual risk for the items not auto-assured above.\n")

    # dispositions[] for the gate (auto-fixed items pre-filled; MC checks referenced)
    dispositions = []
    for d in tix:
        dispositions.append({"id": d["id"], "source": "reconcile",
                             "decision": "fixed" if d.get("auto_applied") else None,
                             "reason": d.get("note")})

    md = "\n".join(L)
    open(os.path.join(args.out_dir, "sme_dossier.md"), "w").write(md)
    json.dump({"dispositions": dispositions,
               "human_items": len(q) + len([d for d in tix if not d.get("auto_applied")]) + 2,
               "auto_fixes": len(changes)},
              open(os.path.join(args.out_dir, "sme_dossier.json"), "w"), indent=2)
    human_items = len(q) + len([d for d in tix if not d.get("auto_applied")]) + 2
    print(f"wrote {args.out_dir}/sme_dossier.md")
    print(f"human load: ~{human_items} items (1 scorecard + {len(q)} edges + "
          f"{len([d for d in tix if not d.get('auto_applied')])} tickets + residual-risk) vs 312 opaque judgments")
    print(f"auto-fixes: {len(changes)}")


if __name__ == "__main__":
    main()
