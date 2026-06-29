# Node Dynamics

How every **node** in the world graph moves on its own each tick, so the engine knows how to
update it. Distilled from `Stock_Taxonomy.md`. A node is a stock the world tracks, with edges
flowing in and out. This covers nodes only, not resources (the pools a decision spends from).

> **Dynamics vs. stock type.** This document defines the **dynamics**, one of exactly **4**:
> Level / Lever / Accumulator / Drifter. It answers "how does this node move on its own." It is
> **derived** from the node's `stock_type` (the thing actually chosen, one of 9, from the
> questions in `quant_questions.md`). Dynamics lives on the lean graph in the field named `type`
> (kept that way for the engine; read it as "dynamics"). Only the stock type is called a "type."

## The four dynamics

| Dynamics | Moves on its own by... | What moves it otherwise | Examples |
|---|---|---|---|
| **Level** (default) | goal-seeking the saturated sum of its incoming edges; mean-reverts to baseline only when it is an "activity" stock | a decision/inject pushes it directly | Safe Supply, Market Confidence, Prestige |
| **Lever** | nothing - it holds its value | a decision or inject targets it directly (it has **no incoming edges**, so nothing propagates into it) | Tariff Level, Export Controls, Cyber Posture |
| **Accumulator** | accruing funded effort toward a threshold, then activating a linked Level through a delayed edge | a decision funds the effort; a shock can destroy accrued progress | Domestic Buildout, Reshoring |
| **Drifter** | drifting on a fixed schedule regardless of play | a decision can slow or counter it, never stop it | Trade Friction, Media Pressure |

**Level is the default.** If a node does not clearly need one of the other three, it is a Level.

### Lever, precisely

A Lever is an ordinary node, not a special control surface. There is **no separate interface to
set its value**; it is updated through the **same decision/inject -> direct-effect path as every
other node**. What makes it a Lever is purely its autonomous behavior: it has none. It holds its
value and moves only when a decision or inject directly targets it. It takes **no incoming
edges** (a direct decision effect is not an edge), does not goal-seek, does not drift, and does
not revert. All of a lever's temporal character lives on its **outgoing** edges.

## Asymmetry per dynamics ("easy to destroy, hard to build")

This is not one global switch; each earns its asymmetry for its own reason.

- **Level** splits its rate: `alpha_up` (slow, building takes sustained input) vs `alpha_down`
  (faster, loss is abrupt). Set `alpha_down > alpha_up` for anything fragile.
- **Lever** has no internal time. All temporal character lives on its **outgoing** edges.
- **Accumulator** is slow-up by construction (rate-limited accrual) but **shockable down**
  (a direct negative shock with no rate limit destroys accrued progress in one tick).
- **Drifter** moves deterministically; the interesting timing is the **counter-action lag**
  (push-back takes effect with delay, so act early) and **fast-biting harm out-edges**.

## The asymmetric-lag rule (shared by all edges)

Lag on an edge is a transport delay: the target reads its source from `lag` ticks ago. The
fix for destruction is one rule: an edge reads the **worse of { source now, source `lag` ticks
ago }** (worse = the value that makes the target worse, sign-aware).

- Steady state: behaves like an ordinary lagged edge.
- Source just collapsed: harm lands **next tick**.
- Source just grew: benefit still waits out the **full lag**.

Construction is gated by lag; destruction is not. Floor: "next tick" is the soonest any
downstream node can move; `lag: 0` means "as fast as the engine allows" (one tick).

## Edge rules the builder must enforce (used by lint_taxonomy.py)

- **Levers get no incoming edges.** Put all their time logic on out-edges. (Hard fail.)
- **Accumulators** take funding/effort in-edges and emit a **delayed activation edge** into
  their linked Level. (Warn if missing either.)
- **Drifters'** harm out-edges carry short/zero lag. (Warn on long lag.)
- Prefer explicit **negative-feedback edges** where the world should self-correct, over
  relying on spontaneous reversion.
- No isolated nodes. (Hard fail.)

Dynamics is assigned once at scenario setup (derived from stock type) and never re-decided at
runtime.
