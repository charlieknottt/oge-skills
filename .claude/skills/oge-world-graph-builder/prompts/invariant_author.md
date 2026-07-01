# Prompt: Blind Invariant Author (Phase 3b)

Role: you write the **plausibility invariants** the Monte Carlo will test the world graph's *behavior*
against. You are working **blind to the graph's edges** on purpose: your job is to state, independently,
what the **scenario document** claims *should* happen — so that when the graph violates one of your
rules, that is a real signal, not a paraphrase of the graph agreeing with itself. If you were shown the
edges you would just restate them; you are not.

## Inputs
- `SCENARIO` — the human-authored scenario narrative. This is your ONLY source of expectations.
- `NODES` — the list of stocks you may reference by exact `id`: `{id, name, measures, inverted}`.
  You need these ids to write valid rules; you are NOT given the causal edges between them.

## What to produce
~10-18 invariants, each an **independent domain expectation the scenario commits to**, expressed over
the node ids. Three kinds:

- **coupling** (preferred) — a cause→effect the scenario states: "when A happens, B should follow within
  a few rounds." Fields: `when` (expr), `then` (expr), `within_rounds` (2-4), `max_violation_rate`.
  Example intent: the scenario says when Western support stalls, Ukraine gives ground → when the supply
  stock is low, the front should worsen for Ukraine within a few rounds.
- **pointwise** — a state that should (almost) never occur: `rule` (a boolean expr that should hold each
  round), `max_violation_rate` (e.g. 0.05). Example: a side's sustainability near zero should not
  coexist with a healthy front.
- **correlation** — ONLY when the scenario explicitly states two things move together. Fields: `a`, `b`,
  `expect` (e.g. ">= 0.2"). **Beware the consumption trap:** an action that *spends* a resource is
  negatively correlated with it within a run even though it "depends on" it. Do not assert a positive
  correlation between an activity and the resource it consumes. When unsure, prefer a `coupling` that
  encodes the scenario's cause→effect instead of a contemporaneous correlation.

Expressions use node ids as variables and their absolute 0-100 value that round, e.g.
`ua_war_sustainability < 15`, `frontline_position > 60`. Remember `inverted` nodes read high = worse.

## Grounding (required)
Every invariant MUST carry a **verbatim `quote`** copied from SCENARIO that licenses it (checked
deterministically — a non-matching quote is rejected). If you cannot quote the scenario for an
expectation, do not write that invariant. Also give a one-line `rationale`.

Focus your budget on the scenario's **outcome/consequence** claims (who wins, what breaks what), not on
mechanical minutiae. Prefer a few well-grounded, decisive expectations over many weak ones.

## Output (JSON only)
```json
{
  "invariants": [
    {
      "id": "short_snake_case",
      "kind": "coupling|pointwise|correlation",
      "when": null, "then": null, "within_rounds": null,
      "rule": null,
      "a": null, "b": null, "expect": null,
      "max_violation_rate": 0.2,
      "quote": "verbatim SCENARIO span",
      "rationale": "one line"
    }
  ]
}
```
Fill only the fields for the chosen `kind`; leave the others null.
