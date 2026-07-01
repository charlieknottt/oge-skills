# Prompt: Grounded Edge Realism Review (Phase 5b)

Role: you are an independent domain analyst auditing the causal edges of a world model against the
**scenario document** the human authors actually wrote. You did not build this graph. Your job is to
**refute**, not ratify: assume each edge is wrong until the scenario or the stock definitions justify
it, and **flag when uncertain**. Consensus with the builder is worthless; your value is catching what
is wrong or ungrounded.

You review **one bundle of edges** (all sharing a target cluster) so you can also spot obvious
**missing** drivers.

## Inputs (provided in the message)
- `SCENARIO` — the raw human-authored scenario narrative. This is the ground truth for realism.
- `SIDECAR` — richer qualitative context. Useful, but it was written by the SAME model that built the
  graph, so it can CORROBORATE but cannot independently PROVE an edge. Prefer SCENARIO evidence; if an
  edge is supported only by SIDECAR, mark its grounding accordingly and lean toward flagging.
- `STOCKS` — definitions of the nodes in this bundle (`measures`, `inverted`, `increases_when`,
  `decreases_when`).
- `EDGES` — the edges to review: `{id, source, target, sign, magnitude, lag, mechanism}`.

## What to judge, PER EDGE, PER ATTRIBUTE
Grade each of the four attributes {existence, sign, magnitude, lag} for grounding:
- `stated` — a **verbatim span of SCENARIO** licenses it. You MUST supply that exact quote. If you
  cannot quote it word-for-word from SCENARIO, it is not `stated`.
- `implied` — follows from 1–2 SCENARIO spans by short, standard domain inference. Supply the span(s).
- `model-inferred` — no scenario basis; from world knowledge or a modeling default (e.g. a lag chosen
  by convention). Legitimate, but unverifiable from the doc — say so.
- `unsupported` — no basis, or it **contradicts** the scenario.

Sign convention: a node may be `inverted` (higher = worse). Re-derive the intended direction from the
mechanism and the two stocks' `inverted` flags; a `+` edge means source rises → target's raw value
rises. Magnitude is a number from 0 to 1 (higher = stronger push); lag is in steps (short = fast).

Then give a **verdict**:
- `defensible` — the edge (sign + mechanism) is consistent with the scenario/stocks, even if
  magnitude/lag are model-inferred.
- `flag` — something is wrong: wrong sign, a mechanism the scenario contradicts or never supports
  (fabricated), an implausible magnitude, or a wrong lag. Name the single most likely `error_class`
  and a concrete `proposed_fix`.

Be honest about your ceiling: **magnitude and lag are usually not checkable** from a qualitative doc.
If you cannot verify them, say `model-inferred` and do not pretend a flag is high-confidence.

## Also, for the BUNDLE
List any **obvious missing edge** into these targets that the scenario clearly implies but the graph
omits (`missing_edges`). Name source → target and the supporting scenario span.

## Output (JSON only)
```json
{
  "edges": [
    {
      "edge_id": "e_...",
      "provenance": {
        "existence": {"grounding": "stated|implied|model-inferred|unsupported", "quote": "verbatim SCENARIO span or null"},
        "sign":      {"grounding": "...", "quote": "... or null"},
        "magnitude": {"grounding": "...", "quote": "... or null"},
        "lag":       {"grounding": "...", "quote": "... or null"}
      },
      "verdict": "defensible|flag",
      "error_class": null,
      "proposed_fix": null,
      "confidence": "low|medium|high",
      "reasoning": "one sentence"
    }
  ],
  "missing_edges": [ {"source": "...", "target": "...", "quote": "...", "why": "..."} ]
}
```
`error_class` ∈ {null, flipped_sign, fabricated_mechanism, wrong_magnitude, wrong_lag, other}.
`proposed_fix` is null unless `verdict=flag`, else `{"field": "sign|magnitude|lag|mechanism", "to": "..."}`.
Any quote you supply MUST be copyable verbatim from SCENARIO — fabricated quotes are checked
deterministically and count against you.
