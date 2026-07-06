# scripts/checks/ — the realism layer

This folder answers "is the graph believable?", not just "is it well-formed?".

It holds the **behavior-rule** step, in two parts:

1. **Author + validate.** An author (an LLM, `prompts/author_behavior_rules.md`) writes rules for
   what this world should never do or should always do, blind to the graph's arrows.
   `validate_behavior_rules.py` keeps the sound ones as `behavior_rules.json` (and a `.yaml` copy).
2. **Check.** `check_behavior_rules.py` runs those rules against the simulation (thousands of
   playthroughs) and counts how often each is broken. A high-confidence failure means the graph
   should go back to Phase 4 to be rebuilt (it names the nodes to re-examine); medium/low failures
   go to a short human list. No LLM: the pass/fail is a number.

No live-game effect. The structural, LLM-free gate (nothing inert, nothing stuck, it settles) is
separate, in `scripts/build/behavior_gate.py`.
