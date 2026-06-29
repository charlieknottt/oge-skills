---
name: oge-world-graph-builder
description: >-
  Build the OGE world graph from scenario documents. Use when setting up an OGE or wargame
  scenario and you need to turn scenario docs plus the fixed PMESII-P indicator framework into
  a validated causal world model: a lean runtime graph of stocks (nodes) and signed,
  time-delayed edges, a rich stock model, and a locked qualitative sidecar. Two modes: create
  (scenario docs in, graph out) and rework (existing graph plus a change request in, revised
  graph out). Generation is LLM-driven but gated by deterministic Python validators, adversarial
  review panels, and Game Manager approval, so nothing ships on model say-so alone. Triggers:
  "build the world graph", "generate stocks and edges", "set up the OGE scenario graph",
  "scenario to system graph".
---

# OGE World Graph Builder

Turns a scenario document (plus the fixed indicator framework) into an approved, validated
world graph. This is the Game Engine Agent's **world-creation** capability. It is **not** the
runtime physics engine: at game time Claude is the runtime reasoner and the graph this skill
produces is the **context document** that grounds it. So the load-bearing outputs are causal
structure and mechanism language, not precise numeric weights.

## When to use
- Standing up a new OGE/wargame scenario and you need the stock+edge world model (create mode).
- Revising an approved graph after a GM edit or a mid-game "we need a new stock" request
  (rework mode).

## When not to use
- Running the live game / updating state each round (that is the runtime engine, not this skill).
- Authoring the scenario prose itself, or White Cell inject decisions.

## What it produces
1. `world_graph.json` - the lean runtime graph (PRIMARY; GM approves this). Schema in
   `schemas/graph.schema.json`, examples in `examples/`.
2. `stocks.json` - the rich stock model behind each node (SECONDARY; feeds the sidecar).
3. `qualitative_sidecar.md` - locked baseline qualitative context (TERTIARY).
4. Audit trail - `validation_report.json` and `generation_log.md` (per-stock/edge rationale).
5. Optional preview - `<scenario>.html`, a self-contained, **playable** deterministic propagation
   demo (6 rounds x 6 ticks, auto-generated decisions + injects) for vetting the graph by eye.
   This is a showcase, not the runtime (at game time Claude is the physics).

See `reference/schema.md` for the full field spec.

## Inputs (directory contract)
The skill takes **one argument: the game directory**. Everything it reads/writes is under it,
so there are no local-path assumptions (this matters for remote Hermes runs).

```
games/<game_id>/
  inputs/
    scenario/        *.pdf|docx|md|txt   (required: the primary driver)
    supplementary/   *                   (optional: tech briefs, data)
    config.yaml                          (optional; see templates/config.example.yaml)
    existing_graph.json                  (rework mode only)
  outputs/
    world_graph.json  stocks.json  qualitative_sidecar.md
    validation_report.json  generation_log.md
    <scenario>.html                  (optional playable propagation preview)
```

The skill is scenario-agnostic: the package never contains a specific scenario. Scenario
material only ever arrives as per-game inputs. Defaults: node band 25-35, functional-swimlane
`category`, edge fan-out for >=25 nodes, MCP grounding off.

## Pipeline

```
Phase 0  Ingest & frame            scripts/parse_docs.py -> scenario frame
Phase 1  Stock proposal            per-dimension ensemble, 9 questions   (prompts/stock_proposal.md)
Phase 2  Stock red-team + GM gate  6 lenses + validators + APPROVE       (prompts/stock_redteam.md)
Phase 3  Qualitative sidecar       8 questions (parallel-capable)        (prompts/sidecar.md)
Phase 4  Edge generation           causal graph from stocks + sidecar    (prompts/edge_proposal.md)
Phase 5  Edge red-team + GM gate   6 lenses + validators + APPROVE       (prompts/edge_redteam.md)
         Rework loop re-enters at 1 (new stocks) or 4 (new edges)
```

- **Phase 0 Ingest.** Parse scenario + supplementary docs to clean text. Extract a structured
  scenario frame: title, central crisis, actors/teams, time horizon and rounds, named
  scarcities and threats, win/lose framing.
- **Phase 1 Stock proposal.** One subagent per PMESII-P dimension (and optionally per sector),
  in parallel, each answering the 9 questions for its slice. A consolidation subagent merges,
  dedupes, enforces the count band and per-dimension balance into one stock vector.
- **Phase 2 Stock red-team + GM gate.** Six adversarial lenses (redundancy, coverage,
  measurability, balance, engine-fit, count), each an independent subagent prompted to find
  problems. Synthesis applies findings; the deterministic validators run; then the GM approves,
  edits, adds, or removes. A GM cut/merge triggers an edge repair pass so the graph entering
  round one is always one the model reasoned over whole.
- **Phase 3 Qualitative sidecar.** Eight questions -> `qualitative_sidecar.md`. Runs in parallel
  with 1-2 (needs only the frame). Locked automatically at finalize. Holds ground-truth
  knowledge state (fog of war); inject routing stays with the White Cell.
- **Phase 4 Edge generation.** Fan out per node (incoming + outgoing) grounded in the sidecar's
  mechanisms, then consolidate (dedupe mirrors, resolve sign conflicts). Apply the taxonomy edge
  rules: levers get no in-edges, accumulators get a delayed activation out-edge, drifter harm is
  fast, prefer explicit negative feedback.
- **Phase 5 Edge red-team + GM gate.** Six lenses (causal-validity, sign-correctness,
  missing-edges, contradiction, mechanism-quality, propagation-sanity). Synthesis -> validators
  -> GM approval. On approval the world-state vector is finalized and the artifacts are written.

## Robustness layer
Generation is LLM-driven; the **guarantees** are deterministic. Nothing advances on model
say-so alone.
- `scripts/validate_graph.py` - hard schema validation (ids, enums, ranges, references, counts).
  Blocks advance on any error.
- `scripts/lint_taxonomy.py` - structural rules: levers with incoming edges (fail), isolated
  nodes (fail), accumulators with no funding/activation edge (warn), drifter long-lag harm (warn).
- `scripts/graph_stats.py` - metrics: sign/magnitude split, degree distribution, category and
  PMESII balance, feedback loops (SCCs), orphans, levers-with-incoming.
- Adversarial panels (Phase 2 and 5) + bounded retry loops (cap ~3; surface residuals to the GM
  rather than loop forever) + provenance logging for every stock and edge.

## How to run the scripts
```
python3 scripts/validate_graph.py outputs/world_graph.json --json outputs/validation_report.json
python3 scripts/lint_taxonomy.py  outputs/world_graph.json
python3 scripts/graph_stats.py    outputs/world_graph.json
python3 scripts/render_preview.py outputs/world_graph.json   # writes outputs/<scenario>.html
```
Both bundled examples are gold-standard: `validate_graph.py` passes clean (0 errors) on each;
`lint_taxonomy.py` is informational and intentionally flags the two known Gordian accumulators
and the three Taiwan levers-with-incoming as teaching cases. `render_preview.py` builds the
playable `index.html`: it maps `magnitude -> weight` and `dynamics -> rate params`, uses the
edge `lag` directly, auto-generates fake decisions/injects, and runs the deterministic
asymmetric-lag propagation so you can watch shocks spread and levers hold. Run
`bash scripts/bootstrap.sh` for a one-shot environment check + smoke test.

## Rework mode
Given the existing graph + a change request, re-enter at Phase 1 (stock delta) or Phase 4 (edge
delta), or run the "are current stocks sufficient?" check (a subagent + White Cell reasonableness
check decides whether a new decision needs a new stock, routes to GM approval). The full
validator always re-runs on the whole graph after any rework. Structural changes are logged with
the round number and are never retroactive.

## File map
```
SKILL.md                     this file (orchestration + when-to-use)
reference/
  taxonomy.md                the 4 dynamics (Level/Lever/Accumulator/Drifter) + edge rules
  update_guideline.md        the 0-100 ruler + decision->number tiers
  indicator_framework.md     PMESII-P dimensions + mechanical-type catalog
  quant_questions.md         the 9 stock questions (stock_type) + 4 admission tests
  qual_questions.md          the 8 sidecar questions
  schema.md                  node/edge/stock schema, prose + examples
schemas/
  graph.schema.json          JSON Schema for the lean runtime graph
  stocks.schema.json         JSON Schema for the rich stock model
scripts/
  parse_docs.py              scenario/supplementary -> clean text (PyPDF2 / python-docx)
  validate_graph.py          hard schema validation (no third-party deps)
  lint_taxonomy.py           structural / taxonomy rules
  graph_stats.py             metrics report
  render_preview.py          world_graph.json -> playable index.html (deterministic showcase)
  bootstrap.sh               env check + smoke test against the examples
prompts/
  stock_proposal.md stock_redteam.md sidecar.md edge_proposal.md edge_redteam.md
templates/
  config.example.yaml        per-game configuration
examples/
  gordian_knot_graph.json    gold-standard lean graph (26 nodes, 50 edges)
  taiwan_strait_graph.json   second scenario (33 nodes), proves scenario-agnostic
  gordian_knot_stocks.json   gold-standard rich model (60 stocks)
```

## Deployment (Hermes)
Skill package ships via git (clone/pull on the box); per-game inputs via rsync into
`games/<game_id>/inputs/`; secrets (model access, MCP config) live on the box, never in git.
The validator scripts are harness-agnostic and dependency-free, so they run identically locally,
in a Claude Code workflow, or on the Hermes VM. `scripts/bootstrap.sh` installs the optional
doc-parsing deps and smoke-tests the box against the bundled examples before any real game.
