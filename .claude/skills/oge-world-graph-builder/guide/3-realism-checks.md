# 3. Checking the graph (does it hold together, and is it believable?)

There are two very different questions to ask about a finished graph:

1. **Does it hold together?** Are the ids valid, the levers wired right, the values in range, no
   node left dangling? These are mechanical and a computer can answer them with certainty.
2. **Is it believable?** Does the graph match how this part of the world actually works? This is a
   judgment about the real world, and no amount of internal consistency can settle it.

The skill handles (1) with plain Python checks, and (2) with a carefully-built review layer. Both
live in `scripts/`: the mechanical checks in `scripts/build/`, the believability checks in
`scripts/checks/`.

## Part A: the mechanical checks (certain)

These run at build time and block progress on any hard error. No AI involved.

- **`build/validate_graph.py`** — checks the file against the schema: valid ids, allowed values,
  numbers in range, edges point to real nodes, no duplicates, sensible counts.
- **`build/lint_taxonomy.py`** — checks the wiring rules from guide 1: a lever with an incoming
  arrow fails, an unconnected node fails, an accumulator with no funding or payoff arrow warns.
- **`build/graph_stats.py`** — reports the shape: how many of each behavior, the balance across
  dimensions, feedback loops, the busiest nodes.

If these pass, the graph is well-formed. That is necessary but it says nothing about realism.

## Part B: the believability checks (judgment)

Here is the hard problem. The graph was **built by an LLM**. If we now ask another LLM "does this
look right?", it will usually say yes, because it shares the same instincts as the model that
built it. That is not a real check, it is one model agreeing with itself.

So the whole design of this layer is built to break that agreement and, more importantly, to
**prove** it was broken. The order of trust is:

**certain machine checks > a reviewer we have tested and proven > a raw LLM opinion.**

We never treat "the reviewer agreed" as evidence. The only useful signals are **disagreement** and
**things the reviewer cannot ground in the scenario document.**

The reason we cannot just hand the whole graph to a human expert: a real scenario has ~70-80 edges,
and reviewing every one is too much to hold in your head. Experts will give us a scenario document;
they will not audit 78 causal arrows. So the job of this layer is to shrink that 78-edge audit down
to a short, ranked list a human can actually sign off on.

The steps below run on the near-final graph.

### Step 1: run the model thousands of times and watch how it behaves

**`checks/mc_face_validity.py`** plays the graph forward thousands of times with random decisions,
and checks whether the behavior obeys a set of **behavior rules** we wrote from the scenario. It
catches problems you cannot see in a static graph, like "this stock collapses but nothing downstream
ever reacts."

The behavior rules live in **`invariants.yaml`** (the file keeps that name in code). There are three
kinds:

- **coupling** (preferred): "when A happens, B should follow within a few rounds." This matches how
  scenarios actually state cause and effect.
- **pointwise**: "this combination should almost never happen" (e.g. a side's sustainability near
  zero while its front line is healthy).
- **correlation**: "these two should move together." Use this sparingly. There is a common trap: an
  action that **spends** a resource is negatively linked to it within a game, even though it
  "depends on" it. Do not assert that an activity and the resource it burns move together.

Where do these rules come from? See "Writing the behavior rules" below. Without an `invariants.yaml`
the script still runs general checks (values pinned at the ceiling/floor, dead nodes, out-of-range
values) but cannot check scenario-specific cause and effect.

### Step 2: test the reviewer before trusting it (calibration)

Before we believe a single thing the AI reviewer says, we measure what it actually catches.

**`checks/plant_errors.py`** makes a copy of the graph with about 15 deliberate, known mistakes in
it (a flipped sign, a made-up mechanism, a deleted edge, a shifted strength, a wrong lag), plus a
record of exactly what was broken. It also leaves most edges untouched as **controls**.

**`checks/build_review_panel.py`** builds a review job (an Opus panel, prompted to *refute* rather
than approve) that reviews the broken graph **blind**, not knowing which edges were tampered with or
how many.

**`checks/score_calibration.py`** compares what the panel flagged against what was actually broken,
and reports, per error type:

- **recall**: what fraction of the planted errors of this type it caught,
- **false-positive rate**: how often it flagged an untouched control edge,
- confidence intervals, and how the catch rate falls off as errors get subtler.

The result is a **coverage map**. The reviewer is trusted **only** for error types it proved it can
catch. The pre-set pass marks (fixed before we look at results, so they cannot be rationalized after
the fact) are:

| Error type | Must catch at least | Controls flagged at most | Note |
|---|---|---|---|
| flipped sign | 80% | 15% | sign is derivable from the mechanism; also cross-checked by machine |
| fabricated mechanism | 60% | 20% | needs noticing the scenario does not support the story |
| deleted edge | 40% | 25% | spotting something absent is intrinsically hard |
| strength shift | 50% | 20% | **expected to fail** — strength is not stated in the scenario |
| wrong lag | 50% | 20% | **expected to fail** — lag is not stated in the scenario |

Error types that fail (we expect strength and lag to fail) are marked **"not covered — human
required"** and are never fixed automatically.

**The honesty ceiling, printed on every scorecard:** planted errors are sharper than real ones, so
the measured catch rate is an **upper bound**, not an estimate. This layer bounds what the reviewer
*can* catch from above; it never certifies the graph is correct.

### Step 3: ground each edge and rank what a human should see

The same panel now reviews the **real** graph. For each edge it labels where each part of the claim
comes from:

- **stated**: a direct quote from the scenario supports it (the quote is checked word-for-word by
  `checks/verify_quotes.py`; a made-up quote is auto-rejected).
- **implied**: it follows from the scenario by a short, standard inference.
- **model-inferred**: no scenario basis, just world knowledge or a modeling default. Legitimate, but
  unverifiable from the document.
- **unsupported**: no basis, or it contradicts the scenario.

Then **`checks/edge_leverage.py`** measures how much each edge actually moves the outcome nodes (by
removing it and re-running), and **`checks/build_review_queue.py`** combines *leverage × how
ungrounded it is × how much reviewers disagreed* into a ranked list of about 10-15 edges the human
should actually look at. A high-leverage edge whose strength is only model-inferred floats to the
top, because that is exactly the kind of important-but-unverifiable choice a human must make.

### Step 4: reconcile the failed behavior rules

For every behavior rule that failed in Step 1, **`checks/reconcile.py`** works out the chain of
edges between the rule's nodes and asks an adjudicator: is this a bad edge, a missing edge, or is
the **rule itself** wrong? (Remember the spending trap: sometimes the graph is right and the rule
was naive.) It returns one of a fixed set of answers: edge-defect, missing-edge, invariant-naive,
invariant-underspecified, or ambiguous.

A proposed fix is **applied automatically only if all four of these hold**:

1. the error type **passed calibration** (Step 2),
2. the fix is backed by a **verified scenario quote**,
3. a **machine cross-check agrees** (e.g. the sign matches the mechanism), and
4. **re-running Step 1 introduces no new failure.**

Anything about strength, lag, a missing edge, or a "the rule was wrong" call always goes to a
human, never auto-applied. Every automatic fix is written to `change_log.json` (with before/after
and the evidence) and is fully reversible.

### Step 5: one short human sign-off, then the gate

**`checks/build_dossier.py`** merges everything (the calibration scorecard, the auto-fixes, the
ranked human queue, the reconciliation tickets) into one `sme_dossier.md`. It is roughly 30 items
and about 1.5 hours of review, instead of auditing 78 edges. If the reviewer **failed** calibration,
the top banner says so: "reviewer unreliable, audit manually," not a green light.

After the human signs off, **`checks/merge_dispositions.py`** records their decisions and
**`checks/gate_face_validity.py`** blocks the build from finalizing until every check is either
passing or explicitly waived with a reason.

## Writing the behavior rules (before Step 1)

The behavior rules in `invariants.yaml` are not written by hand and they are not derived from the
graph. If you wrote them from the graph, the model would just be checking itself again.

Instead, **`checks/build_invariant_author.py`** asks an author to write the rules from the
**scenario document only**, without seeing the edges. That way each rule is an independent
expectation the scenario commits to. Every rule must quote the scenario. Then
**`checks/validate_invariants.py`** drops any rule that references a node that does not exist, will
not compile, or carries a quote that is not actually in the scenario, and writes the clean
`invariants.yaml`.

This is what makes the believability checks exist automatically for a new scenario, instead of
someone hand-writing them each time.

## Running it end to end

**`checks/run_phase5b.py`** ties the deterministic glue together into three commands (`prep`, `mid`,
`finalize`). It runs everything a script can run on its own and stops at the points where an AI
review job has to be launched (a script cannot launch those; a person or agent does). See the
README in `scripts/checks/`.

## Honest limits (state these on the dossier, do not hide them)

- Frontier models share training. Using a different, stronger model to review decorrelates the blind
  spots partly, never fully. Shared assumptions ("sanctions work," "aid is decisive") are exactly
  what a contrarian human expert exists to challenge and a panel of LLMs will not.
- Grounding reaches **existence and sign**. **Magnitude and lag cannot be verified** from a
  qualitative scenario. The system can prove it cannot check them; it cannot fill them in.
- Detecting a **missing** edge is the weakest and most blind-spot-prone case.
- The calibration catch rate is an **upper bound**; real detection is lower by an unknown amount.
- This layer **reduces and routes** the human's work. It does not remove the human from the
  high-stakes strength and lag calls, or from owning the residual risk.
