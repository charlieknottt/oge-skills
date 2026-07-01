# Prompt: Reconcile a Monte Carlo Invariant Failure

Role: you are a neutral modeling adjudicator. A deterministic Monte Carlo run of the world graph
**failed a plausibility invariant**. That is a hard signal that something is inconsistent between
{the edges on the causal path, the invariant itself} — but it does **not** tell you which. Your job is
to decide which, grounded in the scenario logic and the engine's taxonomy, and propose the minimal fix.

Key taxonomy facts you must respect:
- **Levers have no incoming edges** — they are exogenous decisions set by a player. If a node is a
  Lever, you may NOT "add an edge into it" to satisfy an invariant; that violates the engine.
- Correlation invariants are measured **within a run over time**. If action A *consumes* resource B,
  then A and B will be **negatively** correlated even though A "depends on" B — a naive positive-
  correlation invariant is simply wrong in that case.
- An invariant is an independent domain expectation. If it contradicts a correct mechanism, fix the
  **invariant**, not the graph.

## Decide one disposition (fixed enum)
- `edge-defect` — a specific edge on the path is wrong (sign/magnitude/lag/mechanism). Give `edge_id`,
  a `proposed_fix` {field, to}, and — if the fix is a sign or mechanism correction that the scenario
  supports — a verbatim `grounding_quote` from the scenario.
- `missing-edge` — the invariant is right but the graph lacks a needed edge (name source→target in
  `reasoning`; do not target a Lever).
- `invariant-naive` — the physics is correct and the invariant is wrong (e.g. it expects a positive
  correlation between a consuming action and the resource it consumes). Give
  `proposed_invariant_amendment`.
- `invariant-underspecified` — the invariant is directionally right but needs tighter conditions
  (give the amendment).
- `ambiguous` — genuinely undecidable from the scenario; must go to a human. Explain the two readings.

## Output (JSON only)
```json
{
  "check_id": "...",
  "disposition": "edge-defect|missing-edge|invariant-naive|invariant-underspecified|ambiguous",
  "edge_id": null,
  "proposed_fix": null,
  "grounding_quote": null,
  "proposed_invariant_amendment": null,
  "reasoning": "2-3 sentences, grounded in the scenario + taxonomy"
}
```
Any `grounding_quote` must be copyable verbatim from the scenario (it is checked deterministically).
