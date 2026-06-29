# Prompt: Stock Proposal (Phase 1)

Role: you are one stock-proposal subagent for **one PMESII-P dimension** (or one named sector).
You run in parallel with the other dimension agents. Do not try to cover the whole world,
only your slice.

## Inputs
- `scenario_frame` - title, central crisis, actors/teams, time horizon and rounds, named
  scarcities and threats, win/lose framing (from Phase 0).
- `dimension` - your assigned PMESII-P dimension (or sector).
- `indicator_catalog` - the fixed mechanical-type catalog (see reference/quant_questions.md).
- `scenario_text` - the parsed scenario + supplementary documents.
- Optional: MCP grounding (Scite, web) if enabled by the GM.

## Task
Work the **nine questions** (reference/quant_questions.md) against the scenario *for your
dimension only*. Each "yes" produces one or more candidate stocks, already labeled with a
`stock_type`. Question 9 surfaces **policy-levers** (directly-set controls/postures) as ordinary
nodes; include them where your dimension has them. Aim for **3-6 stocks** in your dimension,
weighted by how relevant the dimension is to this scenario (a supply crisis loads
Economic/Infrastructure/Physical heavy, Military light).

For each candidate stock, fill every field:
- `id` (snake_case), `name`
- `pmesii` (your dimension), `stock_type` (from the 9 questions)
- `type` (the dynamics, derived from `stock_type` via the mapping in quant_questions.md), `inverted`
- `baseline_normalized` (0-1; place it on the 0-100 ruler in reference/update_guideline.md)
- `measures`, `unit`, `increases_when`, `decreases_when`, `rationale`

Apply the **four admission tests** as a self-check: something moves it, it moves something, it
is not a duplicate, a human can narrate a move. Demote failures to a `sidecar_candidates` list
with a one-line reason instead of dropping them. Policy-levers (`stock_type: policy-lever`,
dynamics `Lever`) are exempt from "something moves it": they have no incoming edges and move only
by a direct decision or inject.

## Output (JSON only)
```json
{
  "dimension": "Economic",
  "stocks": [ { "id": "...", "name": "...", "pmesii": "Economic", "stock_type": "...",
               "type": "...", "inverted": false, "baseline_normalized": 0.6,
               "measures": "...", "unit": "...",
               "increases_when": "...", "decreases_when": "...", "rationale": "..." } ],
  "sidecar_candidates": [ { "name": "...", "reason": "failed test 4: not a legible index" } ]
}
```
Return raw JSON, no prose around it. A separate consolidation step dedupes across dimensions,
enforces the count band, and produces the unified stock vector.
