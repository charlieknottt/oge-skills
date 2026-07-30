---
description: Build, validate, and package an OGE world graph from a scenario path
argument-hint: <path to a scenario file or directory>
---

You are running the **oge-world-graph-builder** skill end to end on the scenario at:

`$ARGUMENTS`

It runs as one command: a Python orchestrator (`run_build.py`) does all the deterministic glue and
stops at each judgment step, printing a Workflow to launch. You launch it, save its output where the
orchestrator says, and run the next step. Keep looping until the play-ready runtime file is packaged,
then report.

## 1. Load the skill
Read `.claude/skills/oge-world-graph-builder/SKILL.md` and the four guides in `guide/`
(`1-how-the-model-works.md`, `2-data-shapes.md`, `3-realism-checks.md`, `4-the-engine.md`). Skim
`examples/gordian_knot_runtime.json` for the target shape.

## 2. Set up the game directory
`$ARGUMENTS` is the scenario path (a single PDF/DOCX/MD/TXT or a directory of scenario +
supplementary docs). If it does not exist, stop and say so. Pick a snake_case `<slug>` from the
name, create `games/<slug>/inputs/`, and put the scenario file(s) there.

Let `SKILL=.claude/skills/oge-world-graph-builder` and `RB="python3 $SKILL/scripts/build/run_build.py"`.

## 3. Run the build loop
Run each step with `$RB <step> --game-dir games/<slug> --scenario <slug>`. After each run:

- **If it prints `>>> LAUNCH the Workflow above. Save its output to: <path>`**, then launch the
  Workflow it just wrote (`Workflow({scriptPath: "<the .js path it printed>"})`), take the return
  value, and write it verbatim to `<path>` (JSON steps write JSON; the sidecar writes markdown text).
  Then run the next step it named.
- **If it prints no LAUNCH line** (a deterministic step), just run the next step.

The order, and what each judgment step returns:

| step | you launch | save its output to |
|---|---|---|
| `ingest` | framing Workflow | `outputs/scenario_frame.json` |
| `propose-nodes` | per-dimension node panel | `outputs/stock_proposals.json` |
| `review-nodes` | sidecar + node red-team | `outputs/qualitative_sidecar.md` and `outputs/stock_redteam.json` |
| `synthesize-nodes` | apply-node-findings | `outputs/stocks_reviewed.json` |
| `build-nodes` | labels/swimlanes | `outputs/node_labels.json` |
| `propose-edges` | per-node edge panel | `outputs/edge_proposals.json` |
| `review-edges` | edge red-team | `outputs/edge_redteam.json` |
| `synthesize-edges` | apply-edge-findings | `outputs/edge_synthesis.json` |
| `finalize` | (nothing) | packages `outputs/<slug>.runtime.json` |

`review-nodes`, `propose-edges`, `review-edges`, and `finalize` also run deterministic glue
(merging, assembling, validating, packaging) before/after the launch. If `run_build.py` exits with an
error (e.g. validate/lint failed after assembly), read the report it names in `outputs/`, fix the
offending file, and re-run that step.

Run `$RB status --game-dir games/<slug>` any time to see which artifacts exist.

## 4. Report
When `finalize` prints `DONE`, summarize: node/edge counts, the runtime file path
(`games/<slug>/outputs/<slug>.runtime.json`), the two review sheets (`stock_review.md`,
`edge_review.md`) for the human to accept or reject, and the preview `outputs/<slug>.html`. Note that
the deep realism check (`scripts/checks/`) is a separate, optional follow-up and is not run here.
