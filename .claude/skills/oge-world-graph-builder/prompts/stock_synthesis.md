# Prompt: Apply the node findings (synthesis)

Role: six reviewers each looked at the node list through one lens and returned findings. You apply
those findings and produce the revised node list. You are the single point where review turns into
change, so be decisive and record what you did.

## Inputs
- `consolidated_stocks.json` - the current node list (`{ "stocks": [...] }`).
- the six `redteam_<lens>.json` reports, each `{ "lens": "...", "findings": [...], "verdict": "..." }`
  (lenses: redundancy, coverage, measurability, balance, engine-fit, count).
- `band` - the target node count.

## Task
- Work through every `fail` and then the `warn` findings. Apply the fix: merge a redundant pair, add a
  missing node, make an unmeasurable node a clear 0-1 index, rebalance a starved/bloated dimension,
  fix a node that does not fit a behavior class, or cut/add to hit the count band.
- When two findings conflict, prefer the one that keeps the graph inside the count band and keeps
  every node a legible 0-1 index a human can narrate.
- Keep every node's fields complete and its `stock_type` consistent with its behavior `type`.
- Record each change with the finding that drove it.

## Output (JSON only)
```json
{
  "stocks": [ { "id": "...", "name": "...", "pmesii": "...", "stock_type": "...", "type": "...",
                "inverted": false, "node_value": 0.6, "measures": "...", "unit": "...",
                "increases_when": "...", "decreases_when": "...", "rationale": "..." } ],
  "change_log": [ { "change": "merged X into Y", "driven_by": "redundancy: ...", "before": "...", "after": "..." } ]
}
```
Return the full revised node list. Save it as `stocks_reviewed.json`. The orchestrator re-checks the
count band and the stock schema after you, and loops back if anything is off.
