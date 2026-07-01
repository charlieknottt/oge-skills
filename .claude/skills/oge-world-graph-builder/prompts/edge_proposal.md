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
- `sign` (`+` or `-`) - **watch the inverted nodes.** Some nodes are "lower is good" (threats,
  compromise). If a higher source makes such a target worse, the sign encodes the value
  relationship, not whether it is good news. State the direction in the mechanism so the sign is
  checkable.
- `magnitude` - a number from 0 to 1 (weak ~0.2-0.4, moderate ~0.5-0.7, strong ~0.8-1.0). Pick a
  specific value, not a band.
- `lag` (integer steps, 6 per round): immediate 0-1, short 2-3, multi-round 6+
- `mechanism` - ONE specific causal sentence (why source moves target). No generic filler;
  "affects", "influences", "impacts" without a mechanism will be rejected by the red-team.

Apply the **wiring rules** (guide/1-how-the-model-works.md):
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
      "sign": "+", "magnitude": 0.6, "lag": 2,
      "mechanism": "Adequate semiconductor supply prevents shortage-driven price spikes." }
  ]
}
```
Give each edge a stable `e_` id derived from source+target. Return raw JSON only.
