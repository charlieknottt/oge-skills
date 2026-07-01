# scripts/checks/ — the believability layer

These scripts answer "is the graph believable?" (not just "is it well-formed?"). The full story,
in plain English, is in `guide/3-realism-checks.md`. This README is the map of the folder.

The idea in one line: an LLM built the graph, so we do not trust another LLM's opinion of it until
we have **tested that reviewer on known-bad edges**, and then we route only the hard leftovers to a
human.

## What each script does

| Script | Job |
|---|---|
| `mc_face_validity.py` | Play the graph forward thousands of times; check it against the behavior rules in `invariants.yaml`. Writes a `face_validity` report. |
| `build_invariant_author.py` | Build the AI job that writes the behavior rules from the scenario only (blind to the edges). |
| `validate_invariants.py` | Clean the authored rules (drop bad node refs, uncompilable rules, fake quotes) into `invariants.yaml`. |
| `plant_errors.py` | Make a copy of the graph with ~15 known mistakes + a record of them, for testing the reviewer. |
| `build_review_panel.py` | Build the AI review job (Opus, prompted to refute). Used twice: on the broken graph (to test) and on the real graph. |
| `score_calibration.py` | Compare the reviewer's flags to the known mistakes; report catch rate and false positives per error type (the "coverage map"). |
| `verify_quotes.py` | Check, word-for-word, that a quote the reviewer cites is really in the scenario. |
| `edge_leverage.py` | Measure how much each edge moves the outcome nodes (remove it, re-run). |
| `build_review_queue.py` | Rank the ~10-15 edges a human should actually look at (leverage × ungrounded × disagreement). |
| `reconcile.py` | For each failed behavior rule, decide: bad edge, missing edge, or wrong rule. Auto-apply only safe, proven, grounded fixes. |
| `build_dossier.py` | Merge everything into one `sme_dossier.md` for a short human sign-off. |
| `merge_dispositions.py` | Record the human's decisions back into the report. |
| `gate_face_validity.py` | Block finalize until every check is passing or waived with a reason. |
| `run_phase5b.py` | Orchestrator: runs all the automatic glue and stops where an AI job must be launched. |

## The flow (via run_phase5b.py)

The layer has three commands because AI review jobs cannot be launched by a script; a person or
agent launches them, then feeds the output back in.

```
prep      Runs the automatic pre-steps (leverage, planted errors) and writes three AI job files:
          the rule author, the reviewer-test panel, and the real-graph review panel.
          >>> launch those three jobs, save each output.

mid       Cleans the authored rules into invariants.yaml, runs the thousands-of-plays check,
          scores the reviewer test, and writes the reconciliation job.
          >>> launch the reconciliation job, save its output.

finalize  Applies the safe auto-fixes, ranks the human queue, and writes sme_dossier.md.
          >>> a human signs the dossier, then merge_dispositions.py closes the gate.
```

All paths are passed in explicitly, so this works on any game directory. Run
`python3 run_phase5b.py prep --help` for the exact arguments.
