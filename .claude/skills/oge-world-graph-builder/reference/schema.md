# Output Schema (prose + examples)

The skill produces three content artifacts plus an audit trail. Machine schemas live in
`schemas/graph.schema.json` and `schemas/stocks.schema.json`; this file is the readable spec.

## 1. `world_graph.json` - the lean runtime graph (PRIMARY)

The runtime context document and the thing the GM approves. See
`examples/gordian_knot_graph.json` and `examples/taiwan_strait_graph.json`.

```json
{
  "scenario": "gordian_knot",
  "version": "1.0",
  "nodes": [
    { "id": "tariff_level", "label": "Tariff Level", "category": "Levers",
      "type": "Lever", "starting_value": 30, "inverted": false }
  ],
  "edges": [
    { "id": "e_tariff_price", "source": "tariff_level", "target": "price_stability",
      "sign": "-", "magnitude": "moderate", "lag": 2,
      "mechanism": "Tariffs on Chinese-origin components raise input costs, pressuring consumer prices." }
  ]
}
```

**Node fields**
- `id` - unique, snake_case, `^[a-z][a-z0-9_]*$`
- `label` - human-readable, non-empty
- `category` - functional swimlane grouping (scenario-specific, e.g. Levers / Supply /
  Compromise / Buildouts / Outcomes / Pool). May differ from the PMESII-P tag.
- `type` - one of `Level | Lever | Accumulator | Drifter` (engine node-class; see taxonomy.md)
- `starting_value` - number in [0,100] on the 0-100 ruler
- `inverted` - boolean; true when lower is the desirable state (threat/compromise nodes)

**Edge fields**
- `id` - unique, `e_` prefix
- `source`, `target` - existing node ids; `source != target`; no duplicate (source,target) pair
- `sign` - `+` or `-`
- `magnitude` - `weak | moderate | strong` (qualitative guidance, not a literal multiplier)
- `lag` - integer ticks >= 0 (6 ticks/round): immediate 0-1, short 2-3, multi-round 6+
- `mechanism` - one specific causal sentence (why source moves target). Generic filler is
  rejected by the edge red-team.

## 2. `stocks.json` - the rich stock model (SECONDARY)

The research-grade artifact with full metadata; source of truth behind each node and feed for
the sidecar. See `examples/gordian_knot_stocks.json`. Per-stock fields: `id`, `name`, `pmesii`
(fixed PMESII-P dimension), `measures`, `unit`, `baseline_normalized` (0-1), `inverted`,
`stock_type`, `sector`, `increases_when`,
`decreases_when`, `rationale`.

The lean `starting_value` (0-100) is `baseline_normalized` x 100. The lean `category`
(functional swimlane) is not the same field as `pmesii` (dimension); keep both.

## 3. `qualitative_sidecar.md` - locked qualitative context (TERTIARY)

Prose with headers answering the eight questions (see `qual_questions.md`). Generated once,
locked at launch. Holds ground-truth knowledge state (fog of war).

## 4. Audit trail (REQUIRED)

- `validation_report.json` - every deterministic check, pass/fail, with reasons
  (from `scripts/validate_graph.py --json` and `lint_taxonomy.py --json`).
- `generation_log.md` - per-stock and per-edge rationale, enough for the Adjudicator and GM
  to trace cause to effect.
