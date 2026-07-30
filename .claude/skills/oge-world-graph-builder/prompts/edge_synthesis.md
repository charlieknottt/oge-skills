# Prompt: Apply the edge findings (synthesis)

Role: six reviewers each looked at the edge set through one lens, and the deterministic merge flagged
sign conflicts and mirror-duplicates. You apply all of it and produce the revised edge set. You are
the single point where edge review turns into change.

## Inputs
- `world_graph.json` - the current graph (`{ "nodes": [...], "edges": [...] }`).
- the six `redteam_<lens>.json` reports (lenses: causal-validity, sign-correctness, missing-edges,
  contradiction, mechanism-quality, propagation-sanity), each `{ "lens", "findings": [...], "verdict" }`.
- `merge_report.json` from the edge merge: `sign_conflicts` (same pair proposed with both signs) and
  `mirror_duplicates`.

## Task
- Work through every `fail` then `warn`. Fix causal hand-waves, add clearly missing drivers, resolve
  contradictions, tighten vague mechanism sentences, and break runaway structure (over-connected hubs,
  undamped positive loops).
- For each **sign conflict**, re-derive the sign from the mechanism and the two endpoints' `inverted`
  flags; pick one sign, do not average.
- **Hard rules you may not break:** never add an incoming edge to a `Lever` (levers take no inputs);
  never reference a node id that is not in `nodes`; keep edge ids unique with the `e_` prefix; keep
  `strength` a number in [0,1] and `lag` a non-negative integer.
- Record each change with the finding that drove it.

## Output (JSON only)
```json
{
  "edges": [ { "id": "e_...", "source": "...", "target": "...", "sign": "+", "strength": 0.6,
               "lag": 2, "mechanism": "..." } ],
  "change_log": [ { "change": "flipped sign of e_x", "driven_by": "sign-correctness: ...", "before": "-", "after": "+" } ]
}
```
Return the full revised edge set. The orchestrator re-runs `validate_graph.py` and `lint_taxonomy.py`
after you (bounded retries) and loops back if the graph is invalid or a Lever gained an input.
