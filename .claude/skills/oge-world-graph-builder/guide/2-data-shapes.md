# 2. Data shapes (what the files look like)

The build produces one file that matters most, the **runtime file**, plus a few build-time files
behind it. This explains each field in plain language. The machine-checkable versions are in
`schemas/`; working examples are in `examples/`.

One vocabulary, used everywhere:

| Concept | Field | Scale |
|---|---|---|
| how hard an edge pushes | `strength` | 0-1 |
| which way it pushes | `sign` | `+` / `-` |
| a node's resting value | `baseline` | 0-1 |
| a node's live value in play | `current_value` | 0-1 |

## `<slug>.runtime.json` — the play-ready file

This is the single file the game and the graph-**update** skill read. It merges each node's
behavior, its stock detail, and its live value into one object, and seeds the runtime state. It is on
the 0-1 scale, with the engine constants stamped in. Schema: `schemas/runtime_graph.schema.json`.
The physics that reads it: `guide/4-the-engine.md`.

```json
{
  "scenario": "gordian_knot", "version": "1", "round": 0, "tick": 0,
  "engine": { "scale_min": 0, "scale_max": 1, "sat_a": 0.38, "speed": 0.7, "ticks_per_round": 6,
              "rates": { "Level": [0.12, 0.22], "Accumulator": [0.06, 0.13],
                         "Drifter": [0.10, 0.18], "Lever": [0.0, 0.0] } },
  "nodes": [
    { "id": "semi_supply", "label": "Semiconductor Supply", "category": "Supply",
      "type": "Level", "stock_type": "service-level", "pmesii": "Infrastructure",
      "inverted": false, "baseline": 0.6, "current_value": 0.6,
      "measures": "share of certified supply", "rationale": "the central scarcity" }
  ],
  "edges": [
    { "id": "e_tariff_semi_supply", "source": "tariff_level", "target": "semi_supply",
      "sign": "-", "strength": 0.6, "lag": 2, "lag_ticks_elapsed": 0,
      "mechanism": "Tariffs raise input costs, which crimps supply." }
  ]
}
```

**Each node has** (the engine reads only `type`, `inverted`, `baseline`, `current_value`; the rest is
descriptive):

| Field | Meaning |
|---|---|
| `id` | short unique name, lowercase with underscores; the one id space (a node is its own stock detail) |
| `label` | the human-readable name |
| `category` | a display grouping (Levers, Supply, Outcomes). A free label, not the PMESII-P dimension. |
| `type` | the behavior: `Level`, `Lever`, `Accumulator`, or `Drifter` (guide 1) |
| `stock_type` | the finer class the behavior is derived from (guide 1) |
| `pmesii` | which of the 7 dimensions it belongs to |
| `inverted` | `true` when a low value is the good state. Load-bearing in the engine (guide 4), not just a label. |
| `baseline` | its resting value on 0-1 |
| `current_value` | its live value on 0-1; seeded to `baseline` at package time; the only node field the update skill writes |
| `measures`, `unit`, `rationale`, `increases_when`, `decreases_when` | descriptive detail |

**Each edge has:**

| Field | Meaning |
|---|---|
| `id` | unique name starting with `e_` |
| `source` / `target` | the node doing the pushing / being pushed |
| `sign` | `+` (same direction) or `-` (opposite) |
| `strength` | how hard, a number 0-1 (see below); the direction is in `sign`, not here |
| `lag` | delay in ticks before the effect lands; 6 ticks = 1 round (0-1 immediate, 2-3 short, 6+ multi-round) |
| `lag_ticks_elapsed` | the runtime counter of ticks of history; seeded 0 |
| `mechanism` | one specific sentence saying why the source moves the target |

### Edge strength is a 0-1 number

Strength is a **discrete number between 0 and 1**, chosen when the graph is built. It is a gain, not a
value on the node scale. Use these bands as a guide, but pick a specific value (e.g. `0.6`), not a
band:

| Feel | Number |
|---|---|
| weak | about 0.2-0.4 |
| moderate | about 0.5-0.7 |
| strong | about 0.8-1.0 |

## The build-time files (behind the runtime file)

`world_graph.json` is the graph before runtime state is seeded (nodes + edges, same fields as above
minus `current_value` and `lag_ticks_elapsed`). `package_runtime.py` seeds those and stamps the
`engine` block to make the runtime file.

`stocks.json` is the detailed stock model that feeds the sidecar. It authors the resting value on a
**0-1** scale as `node_value`:

```json
{ "id": "semi_supply", "name": "Semiconductor Supply", "pmesii": "Infrastructure",
  "measures": "share of certified supply", "unit": "index 0-1", "node_value": 0.60,
  "increases_when": "domestic capacity comes online", "decreases_when": "a compromise is found",
  "rationale": "the central scarcity", "inverted": false, "stock_type": "service-level" }
```

### `node_value` and `baseline` are the same number

The stock model authors the resting value as `node_value`; the runtime file calls it `baseline`. Both
are on the 0-1 scale and hold the same number, so `build_nodes.py` copies one to the other. `node_value`
is the stock-model name; `baseline` is the name on the node in the graph and runtime files.

## `qualitative_sidecar.md` — the plain-text context

Prose, one section per sidecar question (guide 1). Written once, locked when the game starts. Holds
the ground-truth knowledge state (including secrets, since players never see it).

## The audit trail

- `stock_review.md`, `edge_review.md` — the two review sheets a human can accept or reject.
- `validation_report.json` — every automatic check and whether it passed.
- `generation_log.md` — the reason behind each node and edge.
