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

## Write 8-15 rules, of two kinds

**1) shouldnt_coexist** (write mostly these) — a combination of node values a believable world
would almost never show at the same time.
- `never`: a true/false test that should almost never be true.
  Example: `ukraine_sustainability < 15 and ukraine_frontline > 70`
- `max_rate`: how often it is allowed anyway, a small number like `0.02`.

Think: what pair of states would be obviously wrong to see together? A side out of supplies but
winning easily. A collapsed economy but a booming currency. A secret out in the open but trust
still high.

**2) should_follow** — when one thing happens, another should follow within a few rounds.
- `when`: a true/false trigger. Example: `chip_supply < 20`
- `then`: what should become true. Example: `sdv_capability < 40`
- `within_rounds`: a small integer, 1 to 4.
- `max_miss_rate`: how often it is allowed to not follow, like `0.25`.

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
    { "id": "supply_out_but_winning", "kind": "shouldnt_coexist",
      "never": "ally_supply < 15 and frontline_position > 70", "max_rate": 0.02,
      "confidence": "high", "why": "A side out of supplies cannot be advancing with ease." },
    { "id": "supply_cut_hits_capability", "kind": "should_follow",
      "when": "chip_supply < 20", "then": "program_capability < 40",
      "within_rounds": 2, "max_miss_rate": 0.25,
      "confidence": "medium", "why": "With no substitute, losing supply should degrade the program within a round or two." }
  ]
}
```
Fill only the fields for the kind you chose.
