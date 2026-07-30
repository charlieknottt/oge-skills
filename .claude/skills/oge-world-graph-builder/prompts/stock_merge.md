# Prompt: Merge the nodes (judgment pass, only when flagged)

Role: the deterministic merge step (`merge_stocks.py`) already combined the per-dimension node
proposals, fixed exact id collisions, and counted the total. It calls you only when it flagged
something it cannot resolve on its own: near-duplicate nodes, or a total outside the count band. Your
job is to resolve exactly those flags, nothing else.

## Inputs
- `consolidated_stocks.json` - the merged node list (`{ "stocks": [...] }`).
- `merge_report.json` - what the deterministic step flagged: `near_duplicates` (pairs it suspects are
  the same concept) and `count` (the total vs the target band).
- `band` - the target node count (default 25-35).

## Task
- For each flagged near-duplicate pair, decide: merge into one node (keep the clearer id/name, union
  the descriptive fields) or keep both (they are genuinely different). Give a one-line reason.
- If the total is **over** the band, merge or cut the weakest nodes until it fits; prefer merging
  related nodes over deleting coverage. If it is **under**, say which missing mechanic needs a node.
- Do not touch nodes the report did not flag. Do not change ids that are referenced elsewhere without
  recording the rename.

## Output (JSON only)
```json
{
  "stocks": [ { "id": "...", "name": "...", "pmesii": "...", "stock_type": "...", "type": "...",
                "inverted": false, "node_value": 0.6, "measures": "...", "unit": "...",
                "increases_when": "...", "decreases_when": "...", "rationale": "..." } ],
  "merge_notes": [ { "action": "merged X and Y into Z", "reason": "..." } ]
}
```
Return the full revised node list (not just the changes). The deterministic step re-freezes ids and
re-checks the band after you.
