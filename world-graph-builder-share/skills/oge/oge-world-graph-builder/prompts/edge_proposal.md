# Prompt: Edge Proposal (Phase 4)

Role: you generate causal edges between the **approved** stocks. Stocks must already be approved
(you cannot evaluate an edge without both endpoint nodes). For thoroughness, you are assigned
one node and propose its plausible **incoming and outgoing** edges; a consolidation step merges
mirrored proposals and resolves sign conflicts. (For small graphs a single agent may author all
edges at once.)

## Inputs
- `stocks` - the approved stock vector (ids, types, inverted flags, meaning)
- `qualitative_sidecar` - actor profiles, relationships, mechanisms
- `focus_node` - the node you are wiring (incoming + outgoing), if running per-node
- `scenario_text`

## Task
Propose edges grounded in real mechanisms. Each edge needs:
- `source`, `target` (existing node ids; `source != target`)
- `sign` (`+` or `-`) - **match the inverted convention of both endpoints.** If a higher source
  makes a "lower-is-good" inverted target worse, the sign still encodes the value relationship,
  not the goodness. State the direction in the mechanism so the sign is checkable.
- `magnitude` (`weak | moderate | strong`)
- `lag` (integer ticks, 6/round): immediate 0-1, short 2-3, multi-round 6+
- `mechanism` - ONE specific causal sentence (why source moves target). No generic filler;
  "affects", "influences", "impacts" without a mechanism will be rejected by the red-team.

Apply the **taxonomy edge rules** (reference/taxonomy.md):
- **Levers get no incoming edges.** Put all their time logic on out-edges.
- **Accumulators** take funding/effort in-edges and emit a **delayed activation** out-edge into
  their linked Level (long lag, e.g. 6).
- **Drifters'** harm out-edges carry short/zero lag (threats bite fast).
- Add **negative-feedback** edges where the world should self-correct, rather than relying on
  spontaneous reversion. Keep propagation shallow and causal; avoid runaway chains.

## Output (JSON only)
```json
{
  "focus_node": "semi_supply",
  "edges": [
    { "id": "e_semi_supply_price", "source": "semi_supply", "target": "price_stability",
      "sign": "+", "magnitude": "moderate", "lag": 2,
      "mechanism": "Adequate semiconductor supply prevents shortage-driven price spikes." }
  ]
}
```
Give each edge a stable `e_` id derived from source+target. Return raw JSON only.
