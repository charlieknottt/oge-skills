# scripts/checks/ — the realism layer

This folder answers "is the graph believable?", not just "is it well-formed?".

Right now it holds the **behavior-rule** step: an author (an LLM, using
`prompts/author_behavior_rules.md`) writes rules for what this world should never do or should
always do, blind to the graph's arrows. `validate_behavior_rules.py` then checks those rules and
saves the sound ones to `behavior_rules.yaml`. No live-game effect.

The step that *checks* those rules against the simulation, and sends a bad graph back to be fixed,
is added next. The structural, LLM-free gate (nothing inert, nothing stuck, it settles) is separate
and lives in `scripts/build/behavior_gate.py`.
