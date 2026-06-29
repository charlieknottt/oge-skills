---
description: Build, validate, and visualize an OGE world graph from a scenario path
argument-hint: <path to a scenario file or directory>
---

You are running the **oge-world-graph-builder** skill end to end on the scenario at:

`$ARGUMENTS`

Do the whole thing in one shot, then report. Use the skill's defaults: node band 25-35,
functional-swimlane categories, 9 stock questions, 8 sidecar questions, 6 rounds x 6 ticks, MCP off.

## 1. Load the skill
Read `.claude/skills/oge-world-graph-builder/SKILL.md` and the reference files in
`.claude/skills/oge-world-graph-builder/reference/` (`taxonomy.md`, `indicator_framework.md`,
`quant_questions.md`, `qual_questions.md`, `update_guideline.md`, `schema.md`). Follow that
pipeline and those schemas exactly. Skim `examples/gordian_knot_graph.json` for the target shape.

## 2. Resolve the scenario
`$ARGUMENTS` is the scenario path — a single doc (PDF/DOCX/MD/TXT) or a directory of scenario +
supplementary docs. If it does not exist, stop and say so. Pick a snake_case `<slug>` from the
filename/dir and create the output dir `world-graphs/<slug>/`.

## 3. Phase 0 — Ingest
Run `python3 .claude/skills/oge-world-graph-builder/scripts/parse_docs.py <doc> [<doc>...]` to get
clean text. Extract the scenario frame: central crisis, actors/teams, time horizon and rounds,
named scarcities and threats, win/lose framing.

## 4. Phases 1-2 — Stocks
Answer the **9 questions** across the 7 PMESII-P dimensions to produce ~25-35 stocks. Tag each:
`pmesii`, `stock_type` (1 of 9), engine `type` (the dynamics — Level/Lever/Accumulator/Drifter,
derived from `stock_type`; `policy-lever` → Lever), `inverted`, `starting_value` (0-100),
`measures`, `increases_when`, `decreases_when`, `rationale`. Self-red-team
(redundancy, coverage, measurability, balance, engine-fit, count). Write the rich
`world-graphs/<slug>/stocks.json` to `schemas/stocks.schema.json`.

## 5. Phase 3 — Sidecar
Answer the **8 qualitative questions**. Write `world-graphs/<slug>/qualitative_sidecar.md`.
Capture ground-truth knowledge state (fog of war).

## 6. Phases 4-5 — Edges
Generate causal edges: `sign` (+/-), `magnitude` (weak/moderate/strong), integer `lag` in ticks,
one specific `mechanism` sentence each. Enforce the taxonomy edge rules: **Levers take no incoming
edges**; Accumulators take a funding in-edge and emit a delayed activation out-edge; Drifters'
harm out-edges are fast (short lag); prefer explicit negative-feedback edges; no isolated nodes.
Self-red-team (causal-validity, sign-correctness, missing-edges, contradiction, mechanism-quality,
propagation-sanity). Write the lean `world-graphs/<slug>/world_graph.json` to
`schemas/graph.schema.json` (include a top-level `"scenario": "<slug>"`).

## 7. Validate (hard gate)
```
python3 .claude/skills/oge-world-graph-builder/scripts/validate_graph.py world-graphs/<slug>/world_graph.json --json world-graphs/<slug>/validation_report.json
python3 .claude/skills/oge-world-graph-builder/scripts/lint_taxonomy.py  world-graphs/<slug>/world_graph.json
python3 .claude/skills/oge-world-graph-builder/scripts/graph_stats.py    world-graphs/<slug>/world_graph.json
```
`validate_graph.py` MUST report 0 errors — if not, fix the graph and re-run until clean. Review
the lint findings (levers-with-incoming = fix; unfunded accumulators = fix or justify).

## 8. Render the playable preview
```
python3 .claude/skills/oge-world-graph-builder/scripts/render_preview.py world-graphs/<slug>/world_graph.json
```
This writes `world-graphs/<slug>/<slug>.html` (Gordian-style UI). Then `open` it.

## 9. Report
Summarize: node/edge counts, per-dimension balance (from graph_stats), the validator result
(0 errors), any lint findings and how you resolved them, and the paths to `world_graph.json`,
`stocks.json`, `qualitative_sidecar.md`, and `<slug>.html`.
