# 2. Data shapes (what the files look like)

The skill writes a few files. This explains each field in plain language. The machine-checkable
versions are `schemas/graph.schema.json` and `schemas/stocks.schema.json`; working examples are in
`examples/`.

## `world_graph.json` — the main file

This is the graph the game uses and the Game Manager approves. It has a list of `nodes` and a list
of `edges`.

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
      "sign": "-", "magnitude": 0.6, "lag": 2,
      "mechanism": "Tariffs on Chinese components raise input costs, which pushes consumer prices up." }
  ]
}
```

**Each node has:**

| Field | Meaning |
|---|---|
| `id` | short unique name, lowercase with underscores (e.g. `tariff_level`) |
| `label` | the human-readable name |
| `category` | a grouping for display (e.g. Levers, Supply, Outcomes). This is a free label, not the PMESII-P dimension. |
| `type` | the behavior: `Level`, `Lever`, `Accumulator`, or `Drifter` (see guide 1) |
| `starting_value` | where it starts on the 0-100 scale |
| `inverted` | `true` when a low value is the good state (a threat or compromise node) |

**Each edge has:**

| Field | Meaning |
|---|---|
| `id` | unique name starting with `e_` |
| `source` | the node doing the pushing |
| `target` | the node being pushed |
| `sign` | `+` (same direction) or `-` (opposite) |
| `magnitude` | strength, a number from 0 to 1 (see below) |
| `lag` | delay in steps before the effect lands; 6 steps = 1 round (0-1 immediate, 2-3 short, 6+ multi-round) |
| `mechanism` | one specific sentence saying why the source moves the target. Vague filler ("affects", "impacts") gets rejected in review. |

### Edge magnitude is a 0-1 number

Magnitude is a **discrete number between 0 and 1**, chosen when the graph is built. Use these
bands as a guide:

| Feel | Number |
|---|---|
| weak | about 0.2-0.4 |
| moderate | about 0.5-0.7 |
| strong | about 0.8-1.0 |

Pick a specific value (e.g. `0.6`), not a band. The number is used directly as the weight of the
source's push on the target. (This replaced the old `weak`/`moderate`/`strong` labels so the
graph-creation and graph-update skills share one format.)

## `stocks.json` — the detailed model behind each node

This is the fuller model with all the research metadata. It feeds the sidecar. Each node in
`world_graph.json` has a matching stock here.

```json
{
  "id": "safe_supply", "name": "Safe Semiconductor Supply", "pmesii": "Infrastructure",
  "measures": "share of certified, uncompromised chips in the supply", "unit": "index 0-1",
  "node_value": 0.42,
  "increases_when": "domestic capacity comes online; trusted allies expand output",
  "decreases_when": "a compromise is discovered; an ally cuts exports",
  "rationale": "the central scarcity the whole scenario turns on",
  "inverted": false, "stock_type": "upstream-access", "sector": "Semiconductors"
}
```

| Field | Meaning |
|---|---|
| `id`, `name` | the same id as the graph node, plus a longer name |
| `pmesii` | which of the 7 dimensions it belongs to |
| `measures`, `unit` | what it concretely measures, and its unit |
| `node_value` | the starting value on the **0-1** scale |
| `increases_when`, `decreases_when` | plain descriptions of what moves it up and down |
| `rationale` | why this node exists |
| `inverted` | same meaning as on the graph node |
| `stock_type` | one of the 9 stock types (guide 1); the node's behavior is derived from this |
| `sector` | optional free-text grouping |

### Two scales, on purpose

- The **stock** file uses `node_value` on a **0-1** scale.
- The **graph** file uses `starting_value` on a **0-100** scale.
- They are the same number: `starting_value = node_value × 100`.

The stock file uses `node_value` because that is the field name the graph-**update** skill uses,
so the two skills read each other's stocks without translation. The extra fields the creation side
needs (`inverted`, `stock_type`) are just ignored by the update side.

## `qualitative_sidecar.md` — the plain-text context

Prose, one section per sidecar question (guide 1). Written once, locked when the game starts.
Holds the ground-truth knowledge state (including secrets, since players never see it).

## The audit trail

Two files that let the Game Manager trace every choice:

- `validation_report.json` — every automatic check and whether it passed, with reasons.
- `generation_log.md` — the reason behind each node and edge.
