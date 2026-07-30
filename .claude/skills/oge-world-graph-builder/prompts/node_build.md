# Prompt: Build the nodes (labels + swimlanes only)

Role: the deterministic step (`build_nodes.py`) turns the reviewed node list into graph nodes: it
computes each node's `baseline` from its `node_value`, sets its behavior `type` from its `stock_type`,
and carries `id`/`inverted` across. It leaves two judgment calls to you: each node's display **label**
and its functional **category** (swimlane). You do only those two.

## Inputs
- `stocks_reviewed.json` - the approved node list. Each node already has `id`, `name`, `stock_type`,
  `type`, `pmesii`, `node_value`, `inverted`, and the descriptive fields.
- Optional `config.categories` - a fixed set of allowed swimlane names. If present, use only these.

## Task
- **label**: a short, readable display name for each node (Title Case, no jargon).
- **category**: the functional swimlane the node belongs to (e.g. Levers, Supply, Compromise,
  Services, Outcomes, Trust). This groups nodes by role in the scenario, and is NOT the same as the
  PMESII dimension. Keep the set small (roughly 4-8 swimlanes). If `config.categories` is given, pick
  from it.

You may **not** change ids, values, `type`, `inverted`, `stock_type`, or any descriptive field. Those
are set. If you think one is wrong, note it in `flags`, do not edit it.

## Output (JSON only)
```json
{
  "nodes": [ { "id": "semi_supply", "label": "Semiconductor Supply", "category": "Supply" } ],
  "flags": [ { "id": "...", "note": "type looks wrong: ..." } ]
}
```
Return one entry per node, keyed by `id`. `build_nodes.py` merges your `label`/`category` onto the
deterministic fields to produce `nodes.json`.
