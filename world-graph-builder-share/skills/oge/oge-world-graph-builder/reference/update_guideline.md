# Stock Update Guideline

How the runtime LLM translates a player decision into a **direct** change on the graph.
The graph propagates everything downstream; the LLM never writes second-order effects.
Distilled from `Stock_Update_Guideline.md`. This is runtime guidance; the builder uses it to
size starting values and to keep node semantics legible, not to compute anything at build time.

**Core principle:** the LLM decides *where* and *how well*; the player's commitment decides
*how much*. Magnitude is anchored to committed resources, not to phrasing.

## 1. The 0-100 ruler

All stocks live on a fixed **0-100** index with concrete anchors so magnitude is stable
across rounds:

| Value | Meaning |
|---|---|
| 0 | collapse / nonexistent |
| 25 | struggling, below average |
| 50 | solid, average (default baseline) |
| 75 | strong, top-tier |
| 90 | elite |
| 100 | theoretical ceiling |

Inverted stocks (compromise, threat, friction) read the scale upside down: low is good.

## 2. Magnitude tiers (direct effect per round)

The LLM never emits a free float; it picks a **tier**:

| Tier | Name | Direct effect | Triggered by |
|---|---|---|---|
| T0 | Negligible | 0-1 | no real resource committed (a memo, a committee) |
| T1 | Minor | 2-4 | small share of effort |
| T2 | Moderate | 5-8 | meaningful commitment |
| T3 | Major | 9-14 | large, focused commitment |
| T4 | Transformational | 15-20 | all-in, defining bet (rare) |

Quantizing to five buckets is deliberate: you cannot smuggle magnitude through adjectives
when the output space is five options.

## 3. Decision -> number

```
direct_effect = TIER(commitment_share) x efficiency x sign
```

- **Tier** from the fraction of the team's round effort committed (sub-linear: doubling spend
  never doubles effect).
- **Efficiency** is the LLM's bounded judgment of fit-to-goal: Poor 0.6 / Standard 1.0 /
  Excellent 1.3. Bounded so it can never swing the result wildly.
- **Sign & target**: which node is *directly* touched, and the direction.

The LLM's whole job at runtime is: **target node + tier + efficiency + sign.** Everything
else is auditable arithmetic plus graph propagation.

## 4. Durability: direct vs earned

Any node can be a direct target, but directly-bought outcomes decay fast:

| Effect | Decay/round |
|---|---|
| Effect on a node the decision genuinely controls (a lever) | ~10% |
| Effect bought directly on an outcome (PR -> Prestige) | ~30% (a sugar high) |

This is why you do not forbid "buy the victory node": it fades unless backed by real
structural gains rippling through the graph.

## 5. Builder implications

- Pick **starting_value** on this ruler. Default solid stocks near 55-65, contested/at-risk
  stocks lower, threat/compromise stocks low (they are inverted: low = healthy).
- Make every node a **legible 0-100 index with clear anchors** so the runtime LLM can size
  tiers against it. A node nobody can narrate a move on fails admission.
- Magnitude/lag on edges is qualitative guidance for the runtime reasoner, not literal math.
