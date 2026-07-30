# The engine: how the graph moves during play

This is the exact rulebook for the physics that runs a world graph forward. The graph-creation skill
uses this engine to reality-check a graph before play. The graph-update skill runs the same engine
each round. This document is the shared contract: both sides implement exactly what is here.

The reference implementation is `scripts/checks/mc_face_validity.py` (the `Engine` class). If this
document and that code ever disagree, the code wins and this document is the bug. A second developer
should be able to reproduce that code from this text alone.

Everything is on the **0-1 scale** for node values. Edge `strength` is a 0-1 gain.

---

## The fixed constants

These are the same for every graph, and they are stamped into the `engine` block of every runtime
file so both skills read one source of truth.

| Constant | Value | What it does |
|---|---|---|
| scale | 0 to 1 | every node value and baseline lives here; nothing leaves this range |
| `SAT_A` | 0.38 | the soft ceiling on how hard one edge can push (the tanh saturation) |
| `SPEED` | 0.7 | global tempo multiplier applied to every node's move rate |
| ticks per round | 6 | one round is six ticks; `lag` is counted in ticks |

**Move rates (alpha), before the SPEED multiplier.** Each behavior type has a pair
`(alpha_up, alpha_down)`. Up is the rate when a node is rising toward its target; down is the rate
when it is falling. Down is faster than up in every row: things build slowly and collapse quickly.

| Behavior `type` | alpha_up (raw) | alpha_down (raw) | effective up (×0.7) | effective down (×0.7) |
|---|---|---|---|---|
| Level | 0.12 | 0.22 | 0.084 | 0.154 |
| Accumulator | 0.06 | 0.13 | 0.042 | 0.091 |
| Drifter | 0.10 | 0.18 | 0.070 | 0.126 |
| Lever | 0.0 | 0.0 | 0.0 | 0.0 |

A Lever's rate is zero, so propagation can never move it. It moves only by a direct change. (A node
whose `type` is unknown is treated as a Level.)

---

## The state each node carries

The engine tracks each node as a **deviation from its baseline**, not as an absolute value:

```
deviation = current_value - baseline
current_value = baseline + deviation      (always held in [0, 1])
```

A node sitting exactly at its baseline has deviation 0 and exerts no pull on anything. The runtime
file stores `current_value` (absolute); the engine converts to deviation internally.

The engine also keeps, for each node, a **history of its past deviations**, at least as far back as
the largest `lag` on any edge. This history is what `lag` reads from. (`lag_ticks_elapsed` on each
edge is the bookkeeping counter for how much history exists yet; see the lag section.)

---

## One edge's contribution (the squash + the worse-of rule)

For a single edge from `source` to `target`, define the signed gain:

```
w = strength * (+1 if sign is "+" else -1)      # strength is 0-1, so w is in [-1, +1]
```

Take two readings of the source's deviation: `now` (its current deviation) and `then` (its deviation
`lag` ticks ago). Squash each through the saturation, then combine with the **worse-of** rule:

```
c_now  = w * SAT_A * tanh(now  / SAT_A)
c_then = w * SAT_A * tanh(then / SAT_A)

contribution = min(c_now, c_then)   if the target is NOT inverted   (a high value is good)
contribution = max(c_now, c_then)   if the target IS inverted       (a low value is good)
```

Two things are happening here.

**The squash** (`SAT_A * tanh(x / SAT_A)`) is a soft ceiling. For small source deviations it is
nearly linear (slope ~1); for large ones it flattens toward `±SAT_A`. So one edge can contribute at
most about `strength * 0.38` to its target, no matter how extreme the source gets. This is what stops
any single edge from slamming a node to the rail in one tick.

**The worse-of rule** (`min` for a normal target, `max` for an inverted one) is the "easy to destroy,
hard to build" asymmetry, and it is also what makes `lag` bite. Worked through for a normal target
(min):
- A **positive** push (help) only lands once `then` has caught up, because until the lag has elapsed
  `then` sits at baseline (0) and `min(positive, 0) = 0`. So help is delayed by `lag`.
- A **negative** push (harm) lands immediately, because `min(negative, 0) = negative`. Harm does not
  wait for the lag.

For an inverted target the `max` mirrors this. **`inverted` is load-bearing right here** (it flips
`min` to `max`); it is not just a label for narration.

---

## The per-tick update (exact order)

Each tick, for every node:

**1. Sum the incoming contributions into a target.**
```
target_deviation[i] = sum over incoming edges of contribution      # from the rule above
active[i] = true if any incoming contribution has absolute value > 1e-6
```
The absolute equilibrium a node is being pulled toward is `baseline[i] + target_deviation[i]`.

**2. Move toward the target at the direction-appropriate rate.** Let `v = current deviation of i`.
```
if active[i]:
    alpha = alpha_up[i]   if target_deviation[i] >= v   else alpha_down[i]
    v_new = move(v, alpha * (target_deviation[i] - v), i)
else:
    v_new = clamp_to_range(v, i)     # HOLD: do not drift back to baseline
```
The node closes a fraction `alpha` of the gap to its target each tick, approaching exponentially and
never overshooting. **The up/down rate is chosen by net direction on the stored deviation** (is the
summed target above or below the current value), and `inverted` does **not** enter this choice, it
only entered the contribution rule above.

A node with **no active input holds its value** (only re-clamped to stay in range). It does not decay
back to baseline on its own. Baseline is the reference point for measuring deviation, not an
attractor.

**3. `move(v, delta, i)`** applies a change and keeps the node in range:
```
absolute = baseline[i] + v
absolute = clamp(absolute + delta, 0, 1)
return absolute - baseline[i]      # the new deviation
```

**4. Apply direct changes for the next tick.** Tick rules, White Cell events, and player decisions
are applied through `move()` in that priority order, after the convergence step, then clamped. (A
scheduled Clock decrement is one of these tick-rule direct changes; see the type-folding table.)

**5. Advance time.** Append the new deviation vector to history; increment the global tick; every
edge's `lag_ticks_elapsed` increases by 1.

---

## Lag and `lag_ticks_elapsed`

- **Edges always contribute.** `lag` does not switch an edge on or off. It only chooses which past
  reading of the source (`then`) goes into the worse-of rule.
- `then` is the source's deviation `lag` ticks ago. While the game has not yet run `lag` ticks
  (`lag_ticks_elapsed < lag`), that history does not exist, so `then` falls back to **baseline
  (deviation 0)**. Combined with the worse-of rule, this is what delays a positive push by `lag`.
- `lag_ticks_elapsed` starts at 0 at package time and **increments every tick**. It is **never reset**
  on a direct change. (Because it is never reset, it equals the number of ticks the game has run,
  which is why "`lag_ticks_elapsed >= lag`" is the same as "at least `lag` ticks of history exist.")

---

## The `inverted` convention

`inverted = true` means a **low** value is the good state (a threat, a compromise, a level of
friction). It enters the math in exactly one place: the worse-of rule, where it flips `min` to `max`.
It does not touch the alpha choice, the direct changes, or the clamp.

---

## The three extra behaviors fold onto the four

Some frameworks list seven behavior types. This engine has four. The extra three are handled by
authoring, not by a fifth branch of engine code:

| Extra behavior | Canonical `type` | `stock_type` | How it is handled |
|---|---|---|---|
| Clock | `Drifter` | `clock` | The scheduled per-round change is a **tick-rule direct change** applied in step 4, not special engine code. Drifter's fast rate carries its out-edges. |
| Zero-sum pool | `Level` | `zero-sum-pool` | Conservation is **not** a propagation rule. The offsetting debits are composed as extra **direct changes** by the GM / White Cell so the members sum to a constant; each member propagates as a Level. |
| Ratio | `Level` | `other` | Prefer a Level driven by edges from its numerator/denominator. If exact derived arithmetic is required, compute it as a **display-only overlay outside the engine** after the tick; it is not a propagating type. |

Lever is unchanged: rate `(0, 0)` means propagation never moves it, identical to "skip any edge whose
target is a Lever" (multiplying by zero is the same as skipping). A Lever must never be the target of
an edge in a valid runtime file.

---

## A small worked trace

Source `s`: baseline 0.2, pushed to current 0.6 by a decision, so its deviation is +0.4.
Edge `s -> t`: `sign +`, `strength 0.6`, `lag 5`. Target `t`: a Level, baseline 0.4, current 0.4
(deviation 0), not inverted. `SAT_A = 0.38`, effective alpha_up for a Level = 0.084.

At the first tick, the lag has not elapsed, so `then = 0`:
```
c_now  = 0.6 * 0.38 * tanh(0.4/0.38) = 0.228 * 0.783 =  0.179
c_then = 0.6 * 0.38 * tanh( 0/0.38) =  0
contribution = min(0.179, 0) = 0        # a positive push waits for the lag
```
So `t` does not move for the first 5 ticks. Once `s` has been held at deviation +0.4 for `lag` ticks,
`then` also reads +0.4, so `c_then = 0.179` and the contribution becomes `min(0.179, 0.179) = 0.179`.
Now `t` is being pulled toward deviation +0.179 (absolute 0.579), rising, at the slow build rate:
```
tick A:  v=0      -> v + 0.084*(0.179 - 0)     = 0.015    (current 0.415)
tick B:  v=0.015  -> v + 0.084*(0.179 - 0.015) = 0.029    (current 0.429)
...      closing 8.4% of the remaining gap each tick, approaching 0.579
```
If instead `t` were being pushed **down**, it would use the faster rate 0.154, so it would fall
toward its target roughly twice as fast as it rises. That asymmetry, plus the lag on the help, is the
whole "build slow, collapse fast, harm bites first" character of the model.

---

## What the update skill implements

The update skill reads the runtime file and steps it forward one tick at a time using exactly the
rules above. In summary, per tick:

1. Fields: node resting value is `baseline`, live value is `current_value`, both 0-1; an edge's
   `sign` and 0-1 `strength` give its signed gain `w`; `lag` and `lag_ticks_elapsed` drive the
   look-back.
2. Each edge's contribution is the **worse-of** the current and lagged squashed terms (`min` for a
   normal target, `max` for an inverted one), with `SAT_A = 0.38`.
3. Sum contributions into a target, then move each node a fraction of the gap using the **asymmetric**
   alpha table with the **net-direction rule** (up-rate when the summed target is at or above the
   current value, down-rate when below).
4. An edge whose lag has not elapsed does not skip; its lagged term falls back to baseline (the
   worse-of rule delays help automatically).
5. `lag_ticks_elapsed` increments every tick and is never reset on a direct change.
6. `inverted` is load-bearing (it flips the worse-of `min`/`max`).
7. A node with no active incoming contribution holds its value; it does not drift to baseline.
8. Apply direct changes (tick rules, White Cell, player decisions) after the move, then clamp to
   [0, 1].
