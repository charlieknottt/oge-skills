#!/usr/bin/env python3
"""
run_build.py - the one-command graph build orchestrator.

A script cannot launch an AI job in this harness, so this driver runs all the DETERMINISTIC glue
automatically and STOPS at each judgment step, printing the Workflow to launch, the file to save its
output to, and the next command to run. The driving agent loops: run a step, launch what it prints,
save the output, run the next step. That loop IS the "one command" the user triggers with /graph.

Mirrors scripts/checks/run_phase5b.py. Every path is under <game-dir>/outputs, so it works on any
game directory. Run `status` any time to see which artifacts exist.

Step order (plain names):
  ingest -> propose-nodes -> review-nodes -> synthesize-nodes -> build-nodes
         -> propose-edges -> review-edges -> synthesize-edges -> finalize

Usage:
  python3 run_build.py ingest          --game-dir GAMES/g1 [--scenario slug]
  python3 run_build.py propose-nodes   --game-dir GAMES/g1
  ... (each step prints the next one) ...
  python3 run_build.py finalize        --game-dir GAMES/g1
  python3 run_build.py status          --game-dir GAMES/g1
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

DIMENSIONS = "Political,Military,Economic,Social,Information,Infrastructure,Physical"
STOCK_LENSES = "redundancy,coverage,measurability,balance,engine-fit,count"
EDGE_LENSES = "causal-validity,sign-correctness,missing-edges,contradiction,mechanism-quality,propagation-sanity"

# the file each judgment step's Workflow output must be saved to
SAVE_TARGETS = {
    "ingest": "scenario_frame.json",
    "propose-nodes": "stock_proposals.json",
    "review-nodes": "qualitative_sidecar.md + stock_redteam.json",
    "synthesize-nodes": "stocks_reviewed.json",
    "build-nodes": "node_labels.json",
    "propose-edges": "edge_proposals.json",
    "review-edges": "edge_redteam.json",
    "synthesize-edges": "edge_synthesis.json",
}
NEXT = {
    "ingest": "propose-nodes", "propose-nodes": "review-nodes", "review-nodes": "synthesize-nodes",
    "synthesize-nodes": "build-nodes", "build-nodes": "propose-edges", "propose-edges": "review-edges",
    "review-edges": "synthesize-edges", "synthesize-edges": "finalize",
}


def B(name):
    return os.path.join(HERE, name)


def PROMPT(name):
    return os.path.join(HERE, "..", "..", "prompts", name)


def SCHEMA(name):
    return os.path.join(HERE, "..", "..", "schemas", name)


def run(cmd, allow=(0,)):
    print("  $ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd])
    if r.returncode not in allow:
        raise SystemExit(f"step failed ({r.returncode}): {' '.join(str(c) for c in cmd)}")
    return r.returncode


class Ctx:
    def __init__(self, a):
        self.a = a
        self.od = os.path.join(a.game_dir, "outputs")
        self.wd = os.path.join(self.od, "workflows")
        os.makedirs(self.wd, exist_ok=True)
        self.slug = a.scenario or "graph"

    def o(self, name):
        return os.path.join(self.od, name)

    def w(self, name):
        return os.path.join(self.wd, name)


def _launch_msg(step, ctx, extra=""):
    print(f"\n>>> LAUNCH the Workflow above. Save its output to: {ctx.o('').rstrip(os.sep)}/"
          f"{SAVE_TARGETS[step]}")
    if extra:
        print(extra)
    print(f">>> Then run:  python3 {os.path.relpath(B('run_build.py'))} {NEXT[step]} "
          f"--game-dir {ctx.a.game_dir}")


# ---------------- steps ----------------
def ingest(ctx):
    a = ctx.a
    src = []
    for ext in ("pdf", "docx", "txt", "md"):
        src += glob.glob(os.path.join(a.game_dir, "inputs", "**", f"*.{ext}"), recursive=True)
    if not src:
        raise SystemExit(f"no scenario files under {a.game_dir}/inputs (pdf/docx/txt/md)")
    print("== INGEST: parse scenario documents ==")
    run([PY, B("parse_docs.py"), *sorted(src), "--out", ctx.o("scenario_text.txt")])
    if os.path.getsize(ctx.o("scenario_text.txt")) < 20:
        raise SystemExit("scenario_text.txt is empty; check inputs / install PyPDF2/python-docx")
    print("== INGEST: emit the framing Workflow ==")
    run([PY, B("build_agent_workflow.py"), "--prompt", PROMPT("scenario_frame.md"),
         "--input", f"scenario_text={ctx.o('scenario_text.txt')}",
         "--schema", SCHEMA("frame.schema.json"),
         "--name", "oge-frame", "--label", "frame", "--out", ctx.w("frame.js")])
    _launch_msg("ingest", ctx)


def propose_nodes(ctx):
    print("== PROPOSE NODES: emit the per-dimension proposal panel ==")
    run([PY, B("build_panel.py"), "--prompt", PROMPT("stock_proposal.md"),
         "--fan", DIMENSIONS, "--fan-label", "dimension",
         "--input", f"scenario_frame={ctx.o('scenario_frame.json')}",
         "--input", f"scenario_text={ctx.o('scenario_text.txt')}",
         "--name", "oge-propose-nodes", "--out", ctx.w("propose_nodes.js")])
    _launch_msg("propose-nodes", ctx)


def review_nodes(ctx):
    a = ctx.a
    print("== REVIEW NODES: merge the proposals ==")
    code = run([PY, B("merge_stocks.py"), "--panel", ctx.o("stock_proposals.json"),
                "--out", ctx.o("consolidated_stocks.json"), "--report", ctx.o("stock_merge_report.json"),
                "--min", str(a.min), "--max", str(a.max)])
    try:
        rep = json.load(open(ctx.o("stock_merge_report.json")))
        if rep.get("needs_judgment"):
            print("  note: merge flagged near-duplicates / count pressure; the red-team (redundancy, "
                  "count lenses) + synthesis will resolve these.")
    except OSError:
        pass
    print("== REVIEW NODES: emit the background-notes + red-team Workflows ==")
    run([PY, B("build_agent_workflow.py"), "--prompt", PROMPT("sidecar.md"),
         "--input", f"scenario_frame={ctx.o('scenario_frame.json')}",
         "--input", f"scenario_text={ctx.o('scenario_text.txt')}",
         "--name", "oge-sidecar", "--label", "sidecar", "--out", ctx.w("sidecar.js")])
    run([PY, B("build_panel.py"), "--prompt", PROMPT("stock_redteam.md"),
         "--fan", STOCK_LENSES, "--fan-label", "lens",
         "--input", f"consolidated_stocks={ctx.o('consolidated_stocks.json')}",
         "--input", f"scenario_frame={ctx.o('scenario_frame.json')}",
         "--input", f"scenario_text={ctx.o('scenario_text.txt')}",
         "--name", "oge-review-nodes", "--out", ctx.w("review_nodes.js")])
    _launch_msg("review-nodes", ctx,
                extra="    (save the sidecar Workflow text to qualitative_sidecar.md, "
                      "the red-team panel to stock_redteam.json)")


def synthesize_nodes(ctx):
    print("== SYNTHESIZE NODES: emit the apply-findings Workflow ==")
    run([PY, B("build_agent_workflow.py"), "--prompt", PROMPT("stock_synthesis.md"),
         "--input", f"consolidated_stocks={ctx.o('consolidated_stocks.json')}",
         "--input", f"stock_redteam={ctx.o('stock_redteam.json')}",
         "--name", "oge-synthesize-nodes", "--label", "synthesize", "--out", ctx.w("synthesize_nodes.js")])
    _launch_msg("synthesize-nodes", ctx)


def build_nodes_step(ctx):
    print("== BUILD NODES: emit the labels/swimlanes Workflow ==")
    run([PY, B("build_agent_workflow.py"), "--prompt", PROMPT("node_build.md"),
         "--input", f"stocks_reviewed={ctx.o('stocks_reviewed.json')}",
         "--name", "oge-build-nodes", "--label", "label", "--out", ctx.w("build_nodes.js")])
    _launch_msg("build-nodes", ctx)


def _extract_reviewed_stocks(ctx):
    """stocks_reviewed.json is {stocks, change_log}; write a clean stocks-only file for build_nodes."""
    doc = json.load(open(ctx.o("stocks_reviewed.json")))
    stocks = doc.get("stocks") if isinstance(doc, dict) else doc
    json.dump({"stocks": stocks}, open(ctx.o("_stocks_only.json"), "w"), indent=2)
    return ctx.o("_stocks_only.json")


def propose_edges(ctx):
    print("== BUILD NODES (deterministic): baseline + behavior + labels ==")
    stocks_only = _extract_reviewed_stocks(ctx)
    run([PY, B("build_nodes.py"), "--stocks", stocks_only, "--labels", ctx.o("node_labels.json"),
         "--out-nodes", ctx.o("nodes.json"), "--out-stocks", ctx.o("stocks.json")])
    run([PY, B("build_review_artifact.py"), "--kind", "stocks", "--artifact", ctx.o("nodes.json"),
         "--out", ctx.o("stock_review.md")])
    # fan file of node ids for the per-node edge proposal
    nodes = json.load(open(ctx.o("nodes.json")))["nodes"]
    json.dump([n["id"] for n in nodes], open(ctx.o("node_ids.json"), "w"))
    print("== PROPOSE EDGES: emit the per-node edge proposal panel ==")
    run([PY, B("build_panel.py"), "--prompt", PROMPT("edge_proposal.md"),
         "--fan-file", ctx.o("node_ids.json"), "--fan-label", "focus_node",
         "--input", f"nodes={ctx.o('nodes.json')}",
         "--input", f"qualitative_sidecar={ctx.o('qualitative_sidecar.md')}",
         "--name", "oge-propose-edges", "--out", ctx.w("propose_edges.js")])
    _launch_msg("propose-edges", ctx)


def review_edges(ctx):
    a = ctx.a
    print("== REVIEW EDGES: merge edges, assemble, validate (hard gate) ==")
    run([PY, B("merge_edges.py"), "--panel", ctx.o("edge_proposals.json"),
         "--out", ctx.o("consolidated_edges.json"), "--report", ctx.o("edge_merge_report.json")])
    run([PY, B("assemble_graph.py"), "--nodes", ctx.o("nodes.json"), "--edges", ctx.o("consolidated_edges.json"),
         "--scenario", ctx.slug, "--version", "1", "--drop-invalid", "--out", ctx.o("world_graph.json")])
    vcode = run([PY, B("validate_graph.py"), ctx.o("world_graph.json"), "--min", str(a.min), "--max", str(a.max),
                 "--json", ctx.o("validation_report.json")], allow=(0, 1))
    lcode = run([PY, B("lint_taxonomy.py"), ctx.o("world_graph.json"), "--json", ctx.o("lint_report.json")], allow=(0, 1))
    if vcode == 1 or lcode == 1:
        raise SystemExit("world_graph.json failed validate/lint after assembly; inspect the reports "
                         "in outputs/ and fix before continuing.")
    print("== REVIEW EDGES: emit the edge red-team panel ==")
    run([PY, B("build_panel.py"), "--prompt", PROMPT("edge_redteam.md"),
         "--fan", EDGE_LENSES, "--fan-label", "lens",
         "--input", f"nodes={ctx.o('nodes.json')}",
         "--input", f"world_graph={ctx.o('world_graph.json')}",
         "--input", f"qualitative_sidecar={ctx.o('qualitative_sidecar.md')}",
         "--name", "oge-review-edges", "--out", ctx.w("review_edges.js")])
    _launch_msg("review-edges", ctx)


def synthesize_edges(ctx):
    print("== SYNTHESIZE EDGES: emit the apply-findings Workflow ==")
    run([PY, B("build_agent_workflow.py"), "--prompt", PROMPT("edge_synthesis.md"),
         "--input", f"world_graph={ctx.o('world_graph.json')}",
         "--input", f"edge_redteam={ctx.o('edge_redteam.json')}",
         "--input", f"edge_merge_report={ctx.o('edge_merge_report.json')}",
         "--name", "oge-synthesize-edges", "--label", "synthesize", "--out", ctx.w("synthesize_edges.js")])
    _launch_msg("synthesize-edges", ctx)


def finalize(ctx):
    a = ctx.a
    print("== FINALIZE: apply edge findings, re-validate, package ==")
    doc = json.load(open(ctx.o("edge_synthesis.json")))
    edges = doc.get("edges") if isinstance(doc, dict) else doc
    json.dump({"edges": edges}, open(ctx.o("consolidated_edges.json"), "w"), indent=2)
    if isinstance(doc, dict) and doc.get("change_log"):
        json.dump({"change_log": doc["change_log"]}, open(ctx.o("edge_change_log.json"), "w"), indent=2)
    run([PY, B("assemble_graph.py"), "--nodes", ctx.o("nodes.json"), "--edges", ctx.o("consolidated_edges.json"),
         "--scenario", ctx.slug, "--version", "1", "--drop-invalid", "--out", ctx.o("world_graph.json")])
    vcode = run([PY, B("validate_graph.py"), ctx.o("world_graph.json"), "--min", str(a.min), "--max", str(a.max),
                 "--json", ctx.o("validation_report.json")], allow=(0, 1))
    lcode = run([PY, B("lint_taxonomy.py"), ctx.o("world_graph.json"), "--json", ctx.o("lint_report.json")], allow=(0, 1))
    if vcode == 1 or lcode == 1:
        raise SystemExit("world_graph.json failed validate/lint after edge synthesis; inspect the reports.")
    clog = ctx.o("edge_change_log.json")
    if os.path.exists(clog):
        run([PY, B("build_review_artifact.py"), "--kind", "edges", "--artifact", ctx.o("world_graph.json"),
             "--change-log", clog, "--out", ctx.o("edge_review.md")])
    else:
        run([PY, B("build_review_artifact.py"), "--kind", "edges", "--artifact", ctx.o("world_graph.json"),
             "--out", ctx.o("edge_review.md")])
    print("== FINALIZE: package the runtime file ==")
    run([PY, B("package_runtime.py"), ctx.o("world_graph.json"), "--stocks", ctx.o("stocks.json"),
         "--scenario", ctx.slug, "--version", "1", "--out", ctx.o(f"{ctx.slug}.runtime.json")])
    run([PY, B("validate_graph.py"), ctx.o(f"{ctx.slug}.runtime.json"), "--runtime",
         "--min", str(a.min), "--max", str(a.max)], allow=(0, 1))
    # a preview render (cosmetic; do not fail the build on it)
    try:
        run([PY, B("render_preview.py"), ctx.o("world_graph.json"), "--out", ctx.o(f"{ctx.slug}.html")], allow=(0, 1, 2))
    except SystemExit:
        print("  (preview render skipped)")
    run([PY, B("build_log.py"), "--graph", ctx.o(f"{ctx.slug}.runtime.json"),
         "--change-logs", clog if os.path.exists(clog) else "", "--out", ctx.o("generation_log.md")], allow=(0, 2))
    print(f"\nDONE. Play-ready runtime file: {ctx.o(ctx.slug + '.runtime.json')}")
    print("Review sheets: outputs/stock_review.md, outputs/edge_review.md. "
          "Reject either to re-enter at the matching propose step.")


def status(ctx):
    print(f"Build status for {ctx.a.game_dir}:")
    files = ["scenario_text.txt", "scenario_frame.json", "stock_proposals.json", "consolidated_stocks.json",
             "stock_redteam.json", "qualitative_sidecar.md", "stocks_reviewed.json", "node_labels.json",
             "nodes.json", "stocks.json", "edge_proposals.json", "consolidated_edges.json", "world_graph.json",
             "edge_redteam.json", "edge_synthesis.json", f"{ctx.slug}.runtime.json"]
    for f in files:
        mark = "OK " if os.path.exists(ctx.o(f)) else "-- "
        print(f"  [{mark}] {f}")


STEPS = {
    "ingest": ingest, "propose-nodes": propose_nodes, "review-nodes": review_nodes,
    "synthesize-nodes": synthesize_nodes, "build-nodes": build_nodes_step, "propose-edges": propose_edges,
    "review-edges": review_edges, "synthesize-edges": synthesize_edges, "finalize": finalize, "status": status,
}


def main():
    ap = argparse.ArgumentParser(description="One-command OGE graph build orchestrator.")
    ap.add_argument("step", choices=list(STEPS))
    ap.add_argument("--game-dir", required=True)
    ap.add_argument("--scenario", default=None, help="scenario slug (used for the runtime filename)")
    ap.add_argument("--min", type=int, default=25)
    ap.add_argument("--max", type=int, default=35)
    a = ap.parse_args()
    ctx = Ctx(a)
    STEPS[a.step](ctx)


if __name__ == "__main__":
    main()
