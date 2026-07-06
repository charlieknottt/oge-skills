---
name: oge-world-graph-builder
description: >-
  Build the OGE world graph from scenario documents. Use when setting up an OGE or wargame
  scenario and you need to turn scenario docs plus the fixed PMESII-P checklist into a
  cause-and-effect world model: a graph of nodes (stocks) and signed, time-delayed edges, a
  detailed stock model, and a locked plain-text sidecar. Two modes: create (scenario docs in,
  graph out) and rework (existing graph plus a change request in, revised graph out). The AI does
  the writing, but every step is gated by plain Python checks, adversarial review, and Game
  Manager approval, so nothing ships on the model's word alone. Triggers: "build the world graph",
  "generate stocks and edges", "set up the OGE scenario graph", "scenario to system graph".
---

# OGE World Graph Builder

This skill turns a scenario document into an approved, checked **world graph**: a cause-and-effect
map the game uses as background context. It is the world-**creation** step. It does not run the
game. At game time, Claude reads this graph and reasons over it; the graph is the context, not a
physics engine. So the outputs that matter most are the **structure** (which node affects which)
and the **plain-English reason on each edge**, more than the exact numbers.

New to this? Read the two guides in order:
- `guide/1-how-the-model-works.md` — nodes, edges, the 4 behaviors, the questions. Start here.
- `guide/2-data-shapes.md` — the exact fields in each file.

## When to use
- Standing up a new OGE/wargame scenario and you need the node + edge world model (create mode).
- Revising an approved graph after a Game Manager edit or a mid-game "we need a new node" request
  (rework mode).

## When not to use
- Running the live game or updating state each round (that is the runtime engine, a separate skill).
- Writing the scenario story itself, or making White Cell event decisions.

## What it produces
1. `world_graph.json` — the main graph the Game Manager approves. (Fields in guide 2, schema in
   `schemas/graph.schema.json`, examples in `examples/`.)
2. `stocks.json` — the detailed model behind each node; feeds the sidecar.
3. `qualitative_sidecar.md` — the locked plain-text context (who the actors are, what they want).
4. `behavior_rules.yaml` — the realism rules for this world: what a believable version should never
   do or should always do, checked against the simulation.
5. Audit trail — `validation_report.json` and `generation_log.md` (the reason behind each choice).
6. Optional — `<scenario>.html`, a self-contained **playable** demo of the graph propagating, for
   eyeballing it. This is a showcase, not the runtime.

## Inputs (the directory contract)
The skill takes **one argument: the game directory.** Everything it reads and writes lives under
it, so there are no hidden path assumptions (this matters for remote runs).

```
games/<game_id>/
  inputs/
    scenario/        *.pdf|docx|md|txt   (required: the main driver)
    supplementary/   *                   (optional: tech briefs, data)
    config.yaml                          (optional; see templates/config.example.yaml)
    existing_graph.json                  (rework mode only)
  outputs/
    world_graph.json  stocks.json  qualitative_sidecar.md  behavior_rules.yaml
    validation_report.json  generation_log.md
    <scenario>.html                  (optional playable preview)
```

The skill is scenario-agnostic: the package never contains a specific scenario. Scenario material
only ever arrives as per-game inputs. Defaults: 25-35 nodes, group nodes by function, more edges
allowed above 25 nodes, external grounding (MCP) off.

## The build pipeline

```
Phase 0   Read the docs           scripts/build/parse_docs.py -> a clean scenario summary
Phase 1   Propose nodes           one agent per dimension, the 9 questions   (prompts/stock_proposal.md)
Phase 2   Stress-test + approve   6 reviewers + Python checks + GM approval  (prompts/stock_redteam.md)
Phase 3   Write the sidecar       the 8 questions                           (prompts/sidecar.md)
Phase 3b  Write behavior rules    from the scenario, blind to the arrows    (prompts/author_behavior_rules.md)
Phase 4   Generate edges          the causal graph from nodes + sidecar     (prompts/edge_proposal.md)
Phase 5   Stress-test + approve   6 reviewers + Python checks + GM approval  (prompts/edge_redteam.md)
          Rework re-enters at Phase 1 (new nodes) or Phase 4 (new edges)
```

- **Phase 0 — Read the docs.** Parse the scenario and any extra docs into clean text, and pull out
  a summary: title, the central crisis, the actors/teams, the time horizon and rounds, the named
  scarcities and threats, and how you win or lose.
- **Phase 1 — Propose nodes.** One agent per PMESII-P dimension works the 9 questions
  (guide 1) for its slice, in parallel. A merge step removes duplicates and enforces the count.
- **Phase 2 — Stress-test the nodes, then approve.** Six reviewers each look for one kind of
  problem (duplicates, gaps, un-measurable nodes, imbalance, engine-fit, count). Their findings are
  applied, the Python checks run, then the Game Manager approves, edits, adds, or cuts. A GM cut
  triggers an edge-repair pass so the graph entering round one is one the model reasoned over whole.
- **Phase 3 — Write the sidecar.** Answer the 8 questions into `qualitative_sidecar.md`. Runs in
  parallel with Phases 1-2 (it needs only the summary). Locked when the game starts.
- **Phase 3b — Write behavior rules.** Using the scenario and the node list only (not the arrows),
  write rules for what a believable version of this world should never do or should always do;
  `scripts/checks/validate_behavior_rules.py` cleans them into `behavior_rules.yaml`. Two kinds,
  "shouldn't happen together" and "should follow within a few rounds", each with a confidence. The
  step that runs these rules against the simulation and sends a failing graph back to be fixed is
  being added next (see the Status note).
- **Phase 4 — Generate edges.** Wire the nodes into a causal graph grounded in the sidecar's
  mechanisms, then merge (remove mirror-image duplicates, resolve sign conflicts). Apply the wiring
  rules from guide 1 (levers get no incoming arrows, accumulators pay off on a delay, threats bite
  fast, prefer balancing feedback).
- **Phase 5 — Stress-test the edges, then approve.** Six reviewers (real mechanism vs hand-wave,
  correct sign, missing edges, contradictions, vague reasons, runaway structure). Apply findings,
  run the Python checks (schema, wiring, shape, and the dynamic behavior gate), then GM approval. On
  approval the starting state is finalized.

## What keeps it honest
The AI does the writing; the **guarantees** are plain Python. Nothing advances on the model's word.

- `scripts/build/validate_graph.py` — schema check (ids, values, ranges, references, counts). Blocks
  on any error.
- `scripts/build/lint_taxonomy.py` — wiring rules: a lever with an incoming arrow fails, an
  unconnected node fails, a mis-wired accumulator or a slow-biting threat warns.
- `scripts/build/graph_stats.py` — the shape report: sign/strength split, degree, balance, loops.
- `scripts/build/behavior_gate.py` — dynamic gate: drives the graph with the runtime physics
  (`engine.py`) and blocks on inert nodes, rail-pinning, ringing, or blow-ups. Exit 1 = not deployable.
- Adversarial review at Phases 2 and 5, bounded retries (about 3, then surface leftovers to the GM),
  and a logged reason for every node and edge.

## How to run the checks
```
python3 scripts/build/validate_graph.py outputs/world_graph.json --json outputs/validation_report.json
python3 scripts/build/lint_taxonomy.py   outputs/world_graph.json
python3 scripts/build/graph_stats.py     outputs/world_graph.json
python3 scripts/build/behavior_gate.py   outputs/world_graph.json   # dynamic gate: exit 1 = not deployable
python3 scripts/build/render_preview.py  outputs/world_graph.json   # writes outputs/<scenario>.html
```
Both bundled examples are gold-standard: `validate_graph.py` passes clean on each; `lint_taxonomy.py`
is informational and intentionally flags the known Gordian accumulators and Taiwan levers as teaching
cases. Run `bash scripts/build/bootstrap.sh` for a one-shot environment check plus smoke test.

## Rework mode
Given an existing graph plus a change request, re-enter at Phase 1 (node change) or Phase 4 (edge
change), or run the "are the current nodes enough?" check (an agent plus a White Cell reasonableness
check decides whether a new decision needs a new node, then routes to GM approval). The full checks
always re-run on the whole graph after any rework. Structural changes are logged with the round
number and are never applied retroactively.

## File map
```
SKILL.md                     this file (how the pipeline fits together)
guide/
  1-how-the-model-works.md   nodes, edges, the 4 behaviors, the questions, the scale
  2-data-shapes.md           the exact fields in each output file
schemas/
  graph.schema.json          machine schema for world_graph.json
  stocks.schema.json         machine schema for stocks.json
scripts/
  build/                     create-time checks
    parse_docs.py            scenario/extra docs -> clean text
    validate_graph.py        schema check (no third-party deps)
    lint_taxonomy.py         wiring-rule check
    graph_stats.py           shape report
    engine.py                shared propagation physics (imported by the gate + the preview)
    behavior_gate.py         dynamic gate: reachability, rail-pinning, settling
    render_preview.py        world_graph.json -> playable HTML demo
    bootstrap.sh             environment check + smoke test on the examples
  checks/                    realism layer (see checks/README.md)
    validate_behavior_rules.py  clean authored behavior rules -> behavior_rules.yaml
prompts/
  stock_proposal.md  stock_redteam.md  sidecar.md  author_behavior_rules.md
  edge_proposal.md   edge_redteam.md
templates/
  config.example.yaml        per-game configuration
examples/
  gordian_knot_graph.json    gold-standard graph (26 nodes, 50 edges)
  taiwan_strait_graph.json   second scenario (33 nodes), proves it is scenario-agnostic
  gordian_knot_stocks.json   gold-standard detailed model (60 stocks)
```

## Deployment
The skill package ships via git; per-game inputs arrive by copying them into
`games/<game_id>/inputs/`; secrets (model access, MCP config) stay on the machine, never in git.
The Python checks have no third-party dependencies, so they run the same locally, in a workflow, or
on the server. `scripts/build/bootstrap.sh` installs the optional doc-parsing libraries and
smoke-tests the box against the bundled examples before any real game.

## Status note
The build pipeline (Phases 0-5) and the mechanical checks (including the dynamic behavior gate) are
solid and proven on two scenarios (Gordian Knot and Taiwan Strait).

Phase 3b writes and validates `behavior_rules.yaml` (author + `validate_behavior_rules.py`), proven
on the Taiwan nodes. The step that runs those rules against the simulation and sends a failing graph
back to be fixed is the next piece being added; until then `behavior_rules.yaml` is produced but not
yet enforced.
