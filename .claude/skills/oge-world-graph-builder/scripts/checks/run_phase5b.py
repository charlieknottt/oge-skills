#!/usr/bin/env python3
"""
Phase 5b orchestrator — runs the realism-review layer in three phases, doing all the DETERMINISTIC glue
automatically and stopping at the points where an LLM Workflow must be launched (the harness requires an
agent to start those; a script cannot). Turns ~15 manual invocations into 3 phase commands.

  prep      deterministic pre-steps (edge leverage, mechanism audit, planted errors) + emit the three
            Workflow scripts: invariant author, calibration panel, production panel.
            >>> then launch those 3 Workflows, saving each output file.
  mid       validate authored invariants -> invariants.yaml; run Monte Carlo; score calibration; build
            the reconcile packets + workflow.
            >>> then launch the reconcile Workflow, saving its output.
  finalize  reconcile apply (rails 1-4, auto-apply trusted); build review queue; build dossier.
            >>> human signs the dossier; then merge_dispositions.py closes the gate.

Paths are passed explicitly so it works on any game dir.
Usage:
  python3 run_phase5b.py prep     --graph G --scenario S --stocks K --sidecar D --out-dir O
  python3 run_phase5b.py mid      --graph G --scenario S --out-dir O \
                                  --author-out F --calib-panel-out F
  python3 run_phase5b.py finalize --graph G --scenario S --out-dir O \
                                  --reconcile-out F --prod-panel-out F
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(cmd):
    print("  $ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd])
    if r.returncode not in (0, 1):  # 1 is an expected "findings present" code for several tools
        raise SystemExit(f"step failed ({r.returncode}): {cmd}")


def s(name):
    return os.path.join(HERE, name)


def prep(a):
    cal = os.path.join(a.out_dir, "calibration")
    inv = os.path.join(a.out_dir, "invariants")
    print("== PREP: deterministic pre-steps ==")
    run([PY, s("edge_leverage.py"), a.graph, "--out", os.path.join(a.out_dir, "edge_leverage.json")])
    run([PY, s("plant_errors.py"), a.graph, "--out-dir", cal, "--per-class", "3"])
    print("== PREP: emit Workflow scripts ==")
    run([PY, s("build_invariant_author.py"), "--scenario", a.scenario, "--stocks", a.stocks, "--out-dir", inv])
    run([PY, s("build_review_panel.py"), os.path.join(cal, "mutated_graph.json"),
         "--scenario", a.scenario, "--sidecar", a.sidecar, "--stocks", a.stocks,
         "--out-dir", cal, "--tag", "calib"])
    run([PY, s("build_review_panel.py"), a.graph, "--scenario", a.scenario, "--sidecar", a.sidecar,
         "--stocks", a.stocks, "--out-dir", a.out_dir, "--tag", "prod"])
    print("\n>>> NOW LAUNCH these 3 Workflows and save each output file, then run `mid`:")
    print(f"    1. {inv}/invariant_author_workflow.js       -> --author-out")
    print(f"    2. {cal}/review_panel_calib.js              -> --calib-panel-out")
    print(f"    3. {a.out_dir}/review_panel_prod.js         -> (used in finalize as --prod-panel-out)")


def mid(a):
    cal = os.path.join(a.out_dir, "calibration")
    inv = os.path.join(a.out_dir, "invariants")
    print("== MID: validate invariants -> invariants.yaml ==")
    run([PY, s("validate_invariants.py"), "--proposals", a.author_out, "--graph", a.graph,
         "--scenario", a.scenario, "--out-dir", inv])
    print("== MID: Monte Carlo against authored invariants ==")
    run([PY, s("mc_face_validity.py"), a.graph, "--invariants", os.path.join(inv, "invariants.yaml"),
         "--out", os.path.join(a.out_dir, "face_validity.json")])
    print("== MID: score calibration ==")
    run([PY, s("score_calibration.py"), "--manifest", os.path.join(cal, "plant_manifest.json"),
         "--panel", a.calib_panel_out, "--map", os.path.join(cal, "review_map_calib.json"),
         "--out", os.path.join(cal, "calibration.json")])
    print("== MID: build reconcile packets + workflow ==")
    run([PY, s("reconcile.py"), "build", a.graph, "--face-validity", os.path.join(a.out_dir, "face_validity.json"),
         "--invariants", os.path.join(inv, "invariants.yaml"), "--out-dir", os.path.join(a.out_dir, "reconcile")])
    print(f"\n>>> NOW LAUNCH {a.out_dir}/reconcile/reconcile_workflow.js, save output, then run `finalize`.")


def finalize(a):
    cal = os.path.join(a.out_dir, "calibration")
    inv = os.path.join(a.out_dir, "invariants")
    rec = os.path.join(a.out_dir, "reconcile")
    print("== FINALIZE: reconcile apply (rails 1-4) ==")
    run([PY, s("reconcile.py"), "apply", a.graph, "--adjudication", a.reconcile_out,
         "--calibration", os.path.join(cal, "calibration.json"), "--scenario", a.scenario,
         "--invariants", os.path.join(inv, "invariants.yaml"), "--out-dir", rec])
    print("== FINALIZE: build review queue ==")
    mech = a.mechaudit or ""
    cmd = [PY, s("build_review_queue.py"), "--leverage", os.path.join(a.out_dir, "edge_leverage.json"),
           "--review", a.prod_panel_out, "--calibration", os.path.join(cal, "calibration.json"),
           "--reconcile", os.path.join(rec, "reconcile_packets.json"),
           "--out", os.path.join(a.out_dir, "human_review_queue.json")]
    if mech:
        cmd += ["--mechaudit", mech]
    run(cmd)
    print("== FINALIZE: build dossier ==")
    run([PY, s("build_dossier.py"), "--calibration", os.path.join(cal, "calibration.json"),
         "--queue", os.path.join(a.out_dir, "human_review_queue.json"),
         "--reconcile-disp", os.path.join(rec, "reconcile_dispositions.json"),
         "--change-log", os.path.join(rec, "change_log.json"),
         "--face-validity", os.path.join(a.out_dir, "face_validity.json"), "--out-dir", a.out_dir])
    print(f"\n>>> Human signs {a.out_dir}/sme_dossier.md, then:")
    print(f"    python3 {s('merge_dispositions.py')} {a.out_dir}/face_validity.json "
          f"--reconcile-disp {rec}/reconcile_dispositions.json --signoff <human_signoff.json>")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="phase", required=True)
    for name in ("prep", "mid", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("--graph", required=True)
        p.add_argument("--scenario", required=True)
        p.add_argument("--out-dir", required=True)
        p.add_argument("--stocks")
        p.add_argument("--sidecar")
        p.add_argument("--author-out")
        p.add_argument("--calib-panel-out")
        p.add_argument("--prod-panel-out")
        p.add_argument("--reconcile-out")
        p.add_argument("--mechaudit")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    {"prep": prep, "mid": mid, "finalize": finalize}[a.phase](a)


if __name__ == "__main__":
    main()
