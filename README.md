# OGE Skills

Claude Code skills for building **OGE / wargame** scenarios.

Currently one skill:

### `oge-world-graph-builder`

Turn a scenario document into a validated causal **world graph**: a runtime graph of stocks
(nodes) and signed, time-delayed edges, plus a rich stock model and a locked qualitative
sidecar. Generation is LLM-driven but gated by deterministic Python validators, so nothing
ships on model say-so alone.

## Layout

```
.claude/
  commands/graph.md                  the /graph slash command (one-shot driver)
  skills/
    oge-world-graph-builder/         the skill (single source of truth)
      SKILL.md            pipeline + when-to-use
      reference/          the fixed framework (taxonomy, 9 stock questions,
                          8 sidecar questions, 0–100 ruler, schema spec)
      schemas/            JSON Schemas for the graph and the stock model
      scripts/            validate / lint / stats / render / parse / bootstrap (stdlib only)
      prompts/            the per-phase generation prompts
      examples/           gold-standard graphs (target shape + smoke-test fixtures)
      templates/          per-game config example
```

Generated graphs are written to `world-graphs/<slug>/` (git-ignored).

## Requirements

- **Python 3** — the validators, linter, stats, and renderer use only the standard library.
- Optional, only to parse PDF/DOCX inputs: `pip install PyPDF2 python-docx`
  (Markdown / TXT scenarios need nothing extra.)

Optional one-time check + smoke test against the bundled examples:

```bash
bash .claude/skills/oge-world-graph-builder/scripts/bootstrap.sh
```

## Build a graph (Claude Code)

Open this repo in Claude Code and point `/graph` at any scenario doc:

```
/graph path/to/your_scenario.pdf
```

It runs the whole pipeline in one shot (ingest → stocks → sidecar → edges → validate →
render) and writes the outputs to `world-graphs/<slug>/`. Defaults: 25–35 nodes,
functional-swimlane categories, 9 stock questions, 8 sidecar questions, a 6-round × 6-tick
playable preview, MCP grounding off. Plain language works too: *"build the world graph for
path/to/your_scenario.pdf"*.

### Outputs (per scenario, under `world-graphs/<slug>/`)

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
SK=.claude/skills/oge-world-graph-builder/scripts
G=.claude/skills/oge-world-graph-builder/examples/gordian_knot_graph.json   # or your own world_graph.json

python3 $SK/validate_graph.py  $G   # hard schema gate (must be 0 errors)
python3 $SK/lint_taxonomy.py   $G   # structural / taxonomy rules
python3 $SK/graph_stats.py     $G   # metrics: balance, degree, feedback loops
python3 $SK/render_preview.py  $G   # writes a playable <name>.html next to the input
```

Start with `.claude/skills/oge-world-graph-builder/SKILL.md`.
