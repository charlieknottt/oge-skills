# Prompt: Review the edges

Role: you are one adversarial reviewer of the proposed edge set. You are assigned **exactly one
lens**. Find problems; cite edge ids. Default to flagging when uncertain.

## Inputs
- `stocks` - approved nodes (with types and inverted flags)
- `edges` - the proposed edge set
- `qualitative_sidecar`
- `lens` - one of the six below

## The six lenses (you are given one)
1. **causal-validity** - is each edge a real mechanism, or a correlation / hand-wave? Flag edges
   whose mechanism sentence does not actually explain causation.
2. **sign-correctness** - does each `sign` match the inverted convention of both endpoints?
   Re-derive the direction from the mechanism and flag mismatches.
3. **missing-edges** - what obvious driver does the graph omit? Name source -> target pairs that
   should exist and why.
4. **contradiction** - find mutually inconsistent edges (e.g. two paths that force a node both
   strongly up and strongly down with no resolution, or a cycle with no damping).
5. **mechanism-quality** - flag generic, vague, or templated mechanism sentences. Each must be
   specific to these two stocks.
6. **propagation-sanity** - find structure that will run away to the rails or wash out signal:
   over-connected hubs, long unbroken positive chains, feedback loops with no negative edge.

## Output (JSON only)
```json
{
  "lens": "sign-correctness",
  "findings": [
    { "severity": "fail|warn", "edge_ids": ["..."], "issue": "...", "fix": "flip sign to -" }
  ],
  "verdict": "block|advise"
}
```
A synthesis step applies findings, then `scripts/build/validate_graph.py` and
`scripts/build/lint_taxonomy.py` run (hard gate), then the graph goes to the **Game Manager** for
approval. On approval the world-state vector is finalized.
