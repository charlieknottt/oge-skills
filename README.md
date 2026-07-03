# OGE World Graph Builder

A harness-agnostic skill that turns a wargame **scenario document** into a validated causal
**world graph**: a runtime graph of stocks (nodes) and signed, time-delayed edges, plus a rich
stock model and a locked qualitative sidecar. Generation is LLM-driven but gated by deterministic
Python checks, so nothing ships on model say-so alone.

At game time the runtime engine reads this graph and reasons over it; the graph is background
context, not a physics engine. So the load-bearing outputs are the **structure** (which node
affects which) and the **plain-English reason on each edge**, more than the exact numbers.

## What it is

This directory **is** the skill. Point any agent or harness at `SKILL.md` and follow the pipeline
(Phases 0–5). The deterministic checks in `scripts/build/` are plain Python (standard library
only), so they run the same locally, in a workflow, or on a server.

## Requirements

- **Python 3** — the checks (validate / lint / stats / render / parse) use only the standard library.
- Optional, only to parse PDF/DOCX inputs: `pip install PyPDF2 python-docx`
  (Markdown / TXT scenarios need nothing extra.)

One-time environment check + smoke test against the bundled examples:

```bash
bash scripts/build/bootstrap.sh
```

## The pipeline (full detail in `SKILL.md`)

Ingest the docs → propose nodes (red-team + approval) → write the sidecar → generate edges
(red-team + approval), with the Python checks gating each phase. The procedure, the questions, and
the per-phase prompts live in `SKILL.md`, `guide/`, and `prompts/`.

### Outputs (per scenario)

| File | What it is |
|---|---|
| `world_graph.json` | the lean runtime graph (PRIMARY — nodes + signed/lagged edges) |
| `stocks.json` | the rich stock model behind each node |
| `qualitative_sidecar.md` | locked qualitative context (actors, red lines, fog of war) |
| `validation_report.json` | deterministic validation result |
| `generation_log.md` | per-phase rationale + stock/edge red-team findings |
| `<slug>.html` | self-contained playable propagation preview |

## Deterministic tools (run standalone on any graph JSON, no API)

```bash
G=examples/gordian_knot_graph.json          # or your own world_graph.json

python3 scripts/build/validate_graph.py  $G   # hard schema gate (must be 0 errors)
python3 scripts/build/lint_taxonomy.py   $G   # structural / taxonomy rules
python3 scripts/build/graph_stats.py     $G   # metrics: balance, degree, feedback loops
python3 scripts/build/render_preview.py  $G   # writes a playable <name>.html next to the input
```

## Layout

```
SKILL.md            pipeline + when-to-use (start here)
guide/
  1-how-the-model-works.md   nodes, edges, the 4 behaviors, the 9 stock + 8 sidecar questions, the ruler
  2-data-shapes.md           the exact fields in each output file
schemas/            JSON Schemas for the graph and the stock model
scripts/build/      validate / lint / stats / render / parse / bootstrap (stdlib only)
prompts/            the per-phase generation prompts
examples/           gold-standard graphs + rich stock model (target shape + smoke-test fixtures)
templates/          per-game config example
```

Generated graphs are written under `world-graphs/<slug>/` (git-ignored). Start with `SKILL.md`.
