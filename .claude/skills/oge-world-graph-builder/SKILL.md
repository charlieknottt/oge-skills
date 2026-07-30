---
name: oge-world-graph-builder
description: >-
  Build the OGE world graph from scenario documents. Use when setting up an OGE or wargame
  scenario and you need to turn scenario docs plus the fixed PMESII-P checklist into a
  cause-and-effect world model. It runs as one command that produces a single play-ready runtime
  file: a graph of nodes (stocks) and signed, time-delayed edges with each node's starting value
  seeded, ready for the game and for the separately-owned graph-update skill to read each round.
  The AI does the writing, but every step is gated by plain Python checks and adversarial review,
  so nothing ships on the model's word alone. Triggers: "build the world graph", "generate stocks
  and edges", "set up the OGE scenario graph", "scenario to system graph".
---

# OGE World Graph Builder

This skill turns a scenario document into a checked, play-ready **world graph**: a cause-and-effect
map the game runs on. It is the world-**creation** half of the system. A separately-owned
graph-**update** skill mutates the graph each round, and an agentic harness calls each at the right
time. This skill owns the shared file format and the physics both sides use.

New to this? Read the four guides in order:
- `guide/1-how-the-model-works.md` — nodes, edges, the 4 behaviors, the questions. Start here.
- `guide/2-data-shapes.md` — the exact fields in each file.
- `guide/3-realism-checks.md` — how we keep the graph honest (the deep realism check is a follow-up).
- `guide/4-the-engine.md` — the exact physics that runs the graph. This is the contract the update
  skill codes against.

## When to use
- Standing up a new OGE/wargame scenario and you need the play-ready world graph (create mode).
- Revising an approved graph after a Game Manager edit or a mid-game "we need a new node" request
  (rework mode).

## When not to use
- Running the live game or updating state each round (that is the update skill, plus the harness).
- Writing the scenario story itself, or making White Cell event decisions.

## What it produces
1. `<slug>.runtime.json` — **the play-ready file.** One merged artifact: every node carries its
   behavior, its stock detail, and its live `current_value` (seeded to its baseline); every edge
   carries sign, strength, lag, and a lag counter. On the 0-1 scale, with the engine constants
   stamped in. This is what the game and the update skill read. Schema:
   `schemas/runtime_graph.schema.json`; physics: `guide/4-the-engine.md`; examples in `examples/`.
2. `world_graph.json` — the build-time graph (nodes + edges, before runtime state is seeded).
3. `stocks.json` — the detailed model behind each node; feeds the sidecar.
4. `qualitative_sidecar.md` — the locked plain-text context (who the actors are, what they want).
5. `stock_review.md` and `edge_review.md` — the two review sheets a human can accept or reject.
6. Audit trail — `validation_report.json`, `generation_log.md`, and an optional `<slug>.html`
   playable preview.

## Inputs (the directory contract)
The skill takes **one argument: the game directory.** Everything it reads and writes lives under it,
so there are no hidden path assumptions (this matters for remote runs).

```
games/<game_id>/
  inputs/
    scenario/        *.pdf|docx|md|txt   (required: the main driver)
    supplementary/   *                   (optional: tech briefs, data)
    config.yaml                          (optional; see templates/config.example.yaml)
    existing_graph.json                  (rework mode only)
  outputs/
    <slug>.runtime.json                  (the play-ready file)
    world_graph.json  stocks.json  qualitative_sidecar.md
    stock_review.md   edge_review.md     (rejectable review sheets)
    validation_report.json  generation_log.md
    <slug>.html                          (optional playable preview)
    workflows/                           (the Workflow .js files the build emits)
```

The skill is scenario-agnostic: the package never contains a specific scenario. Scenario material
only ever arrives as per-game inputs. Defaults: 25-35 nodes, group nodes by function, external
grounding (MCP) off.

## The build pipeline (one command)

Trigger it with `/graph <scenario path>`. A Python orchestrator, `scripts/build/run_build.py`, runs
all the deterministic glue and stops at each judgment step, printing a Workflow to launch. The
driving agent launches it, saves the output where the orchestrator says, and runs the next step.
That loop is the whole build. (A script cannot launch an AI job in this harness, so the human/agent
launches each one; this mirrors the `run_phase5b.py` pattern.)

The steps, in plain names:

| Step | What happens | Kind |
|---|---|---|
| **Read the scenario** | `parse_docs.py` turns the docs into clean text | Python |
| **Frame the scenario** | pull out the title, crisis, actors, horizon, win/lose (`scenario_frame.md`) | agent |
| **Pick the nodes** | one agent per PMESII-P dimension works the 9 questions (`stock_proposal.md`) | agents |
| **Merge the nodes** | `merge_stocks.py` unions them, fixes id clashes, flags near-dups + count | Python |
| **Write the background notes** | the 8 questions into the sidecar (`sidecar.md`) | agent |
| **Review the nodes** | six lenses find problems (`stock_redteam.md`) | agents |
| **Apply node findings** | one pass applies the findings (`stock_synthesis.md`) | agent |
| **Build the nodes** | `build_nodes.py` sets each `baseline` and behavior; the agent adds labels/swimlanes (`node_build.md`) | Python + agent |
| **Draw the edges** | one agent per node proposes its edges (`edge_proposal.md`) | agents |
| **Merge the edges** | `merge_edges.py` dedups, flags sign conflicts; `assemble_graph.py` + validators (hard gate) | Python |
| **Review the edges** | six lenses find problems (`edge_redteam.md`) | agents |
| **Apply edge findings** | one pass applies findings + resolves sign conflicts (`edge_synthesis.md`) | agent |
| **Package the game-ready file** | re-validate, then `package_runtime.py` seeds state and writes `<slug>.runtime.json` | Python |

Human gates: the build runs autonomously and emits two **rejectable review sheets**
(`stock_review.md`, `edge_review.md`). A human can reject either afterward, which re-enters the build
at the matching propose step. Packaging is gated on the deterministic validators passing.

## What keeps it honest
The AI does the writing; the **guarantees** are plain Python. Nothing advances on the model's word.

- `scripts/build/validate_graph.py` — schema check (ids, values, ranges, references, counts). Blocks
  on any error. `--runtime` mode also checks the merged fields and that no Lever is an edge target.
- `scripts/build/lint_taxonomy.py` — wiring rules: a lever with an incoming arrow fails, an
  unconnected node fails, a mis-wired accumulator or a slow-biting threat warns.
- `scripts/build/package_runtime.py` — refuses to package unless node ids are unique, every edge
  endpoint is a real node, the stock detail joins one-to-one onto the nodes, and no Lever is a target.
- Adversarial review at "review the nodes" and "review the edges", a mandatory re-validate after each
  synthesis (bounded retries), and a logged reason for every node and edge.

## How to run the checks by hand
```
python3 scripts/build/validate_graph.py outputs/world_graph.json --json outputs/validation_report.json
python3 scripts/build/validate_graph.py outputs/<slug>.runtime.json --runtime
python3 scripts/build/lint_taxonomy.py   outputs/world_graph.json
python3 scripts/build/graph_stats.py     outputs/world_graph.json
python3 scripts/build/render_preview.py  outputs/world_graph.json   # writes outputs/<slug>.html
```
Both bundled runtime examples are gold-standard: they validate clean with `--runtime` and pass
`lint_taxonomy.py` with no failures. Run `bash scripts/build/bootstrap.sh` for an environment check
plus a smoke test.

## Rework mode
Given an existing graph plus a change request, re-enter at "pick the nodes" (node change) or "draw
the edges" (edge change). The full checks always re-run on the whole graph after any rework.
Structural changes are logged with the round number and are never applied retroactively.

## File map
```
SKILL.md                     this file (how the pipeline fits together)
guide/
  1-how-the-model-works.md   nodes, edges, the 4 behaviors, the questions, the scale
  2-data-shapes.md           the exact fields in each output file
  3-realism-checks.md        the mechanical checks + the (follow-up) believability layer
  4-the-engine.md            the exact physics; the contract the update skill codes against
schemas/
  runtime_graph.schema.json  the play-ready runtime file (the shared contract)
  graph.schema.json          the build-time graph (pre-seed)
  stocks.schema.json         the detailed stock model
  frame.schema.json          the scenario frame
scripts/
  build/                     the create pipeline (no third-party deps)
    run_build.py             the one-command orchestrator
    parse_docs.py            scenario/extra docs -> clean text
    build_panel.py           emit a fan-out Workflow (one agent per dimension/lens/node)
    build_agent_workflow.py  emit a one-agent Workflow (frame, merge, synthesis, labels, sidecar)
    merge_stocks.py          combine node proposals; fix id clashes; flag near-dups + count
    merge_edges.py           combine edge proposals; dedup; flag sign conflicts
    build_nodes.py           set baseline (= node_value x100) and behavior; the authority for both
    assemble_graph.py        nodes + edges -> world_graph.json
    validate_graph.py        schema check (build-time and --runtime)
    lint_taxonomy.py         wiring-rule check
    graph_stats.py           shape report
    build_review_artifact.py render the rejectable review sheets
    package_runtime.py       seed runtime state + hard id/lever checks -> <slug>.runtime.json
    build_log.py             the generation log
    render_preview.py        world_graph.json -> playable HTML demo
    bootstrap.sh             environment check + smoke test
  checks/                    the deep realism/believability layer (a follow-up; see checks/README.md + guide 3)
prompts/
  scenario_frame.md  stock_proposal.md  stock_merge.md   stock_redteam.md  stock_synthesis.md
  node_build.md      sidecar.md         edge_proposal.md edge_redteam.md   edge_synthesis.md
templates/
  config.example.yaml        per-game configuration
examples/
  gordian_knot_runtime.json  gold-standard play-ready file (26 nodes, 50 edges)
  taiwan_strait_runtime.json second scenario (33 nodes), proves it is scenario-agnostic
  *_graph.json / *_stocks.json  the build-time source files behind the runtime examples
```

## Deployment
The skill package ships via git; per-game inputs arrive by copying them into
`games/<game_id>/inputs/`; secrets stay on the machine. The Python has no third-party dependencies,
so it runs the same locally, in a workflow, or on the server.

## Status note
The create pipeline (the steps above), the shared runtime file format, and the engine spec are the
current deliverable, verified end to end. The **deep realism check** in `scripts/checks/` (the
calibration harness, provenance, reconcile, and dossier) is a scoped **follow-up** and remains beta:
it is wired but not yet validated on a fresh scenario, and it is not run by the one-command build.
When it lands, its human sign-off becomes a gate before packaging. See guide 3 for its design and
honest limits.
