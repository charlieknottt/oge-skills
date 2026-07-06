# Prompt: write behavior rules for a world graph (blind to the arrows)

You read a scenario and the list of things it tracks (the nodes). You write rules about what a
believable version of this world should **never** do, or should **always** do.

You do **not** see how the nodes are wired together. That is on purpose: your rules are an
independent check on the graph, not a copy of it. Write what *should* be true, from the scenario
and from how this kind of world actually works.

## What you are given
- **SCENARIO** — the situation text. Your source for how this world works, plus general knowledge.
- **NODES** — for each node: its `id`, a plain name, and whether high is bad. Values run 0-100.
  Refer to nodes by their exact `id`.

## Write 8-15 rules, of two kinds. Prefer the first.

**1) should_follow (prefer this — write most of these)** — when one thing happens, another should
follow within a few rounds. Most "impossible states" are really a cause and effect: the reason a side
can't be winning while its supplies are gone is that losing supplies *makes* the front collapse. So
write the cause→effect, not the coincidence.
- `when`: a true/false trigger. Example: `chip_supply < 20`
- `then`: what should become true. Example: `program_capability < 40`
- `within_rounds`: a small integer, 1 to 4.
- `max_miss_rate`: how often it is allowed to not follow, like `0.25`.

**2) shouldnt_coexist (only for genuine tensions)** — two states that can't both be true at once,
where neither one simply *causes* the other. Use this for tradeoffs the players push on from both
sides at the same time, e.g. you can't have both maximum operational independence and maximum
alignment with a partner. Do NOT use it for a plain cause→effect — write that as `should_follow`,
because a "two extremes at once" combo is harder to test and can pass just because that corner never
came up in play.
- `never`: a true/false test that should almost never be true.
  Example: `operational_independence > 75 and partner_alignment > 75`
- `max_rate`: how often it is allowed anyway, a small number like `0.02`.

## Every rule also has
- `confidence`: `high`, `medium`, or `low` — how sure you are this must hold in any believable
  version of this world.
- `why`: one plain sentence, from the scenario or from how this kind of world works.

## How to write the tests
Plain true/false expressions using node ids, numbers, comparisons (`<`, `>`, `<=`, `>=`, `==`),
and `and` / `or` / `not`. Remember which nodes are "high is bad" and read them accordingly.

## Rules for you
- Use only the exact node ids you were given.
- Prefer a few high-confidence rules that would be clearly wrong if broken, over many weak ones.
- Do not describe how the graph is wired. You do not know that.

## Output: JSON only
```json
{
  "rules": [
    { "id": "supply_cut_hits_capability", "kind": "should_follow",
      "when": "chip_supply < 20", "then": "program_capability < 40",
      "within_rounds": 2, "max_miss_rate": 0.25,
      "confidence": "high", "why": "With no substitute, losing supply should degrade the program within a round or two." },
    { "id": "independence_vs_alignment", "kind": "shouldnt_coexist",
      "never": "operational_independence > 75 and partner_alignment > 75", "max_rate": 0.02,
      "confidence": "medium", "why": "Full independence and full alignment with the partner are a genuine tradeoff; both cannot peak at once." }
  ]
}
```
Fill only the fields for the kind you chose.
