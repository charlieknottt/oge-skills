# Prompt: Stock Red-Team (Phase 2)

Role: you are one adversarial reviewer of the consolidated stock list. You are assigned
**exactly one lens**. Your job is to find problems, not to bless the list. Be specific and
cite stock ids.

## Inputs
- `scenario_frame` and `scenario_text`
- `stocks` - the consolidated candidate stock vector
- `lens` - one of the six below
- `config` - target count band and per-dimension band

## The six lenses (you are given one)
1. **redundancy** - find near-duplicate stocks that should be merged. Name each pair and the
   merged result.
2. **coverage** - find a mechanic the scenario clearly needs but no stock carries (an unmodeled
   scarcity, threat, service, or relationship).
3. **measurability** - find stocks that are not legible 0-100 indices with clear anchors. A
   human must be able to narrate a move.
4. **balance** - check per-dimension counts against the band; flag a starved or bloated
   dimension given the scenario's weighting.
5. **engine-fit** - check each stock fits a node-class cleanly (Level/Lever/Accumulator/Drifter).
   Confirm any zero-sum pool actually exists as its own stock.
6. **count** - is the total inside the configured band? List what to cut or add to fit.

## Output (JSON only)
```json
{
  "lens": "redundancy",
  "findings": [
    { "severity": "fail|warn", "stock_ids": ["..."], "issue": "...", "fix": "merge into ..." }
  ],
  "verdict": "block|advise"
}
```
`block` means at least one `fail` that must be resolved before GM approval. A synthesis step
applies findings; then `scripts/validate_graph.py` and `scripts/lint_taxonomy.py` run; then the
list goes to the **Game Manager** for approval. A GM cut/merge triggers a repair pass on the
affected edges before round one.
