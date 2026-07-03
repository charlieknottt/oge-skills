# Prompt: Qualitative Sidecar (Phase 3)

Role: you generate the baseline qualitative context document. This holds everything about the
world that cannot be a numeric stock. It is generated once and **locked at launch** (mid-game
shifts become White Cell injects, never sidecar edits). You can run in parallel with stock and
edge generation because you need only the scenario frame, not the approved stocks.

## Inputs

- `scenario_frame` and `scenario_text`
- Optional: the approved stock list (for cross-reference only; do not block on it)

## Task

Answer the **eight questions** (guide/1-how-the-model-works.md) from the scenario. Each maps to one
section of the output. Ground every answer in the scenario text.

1. **Actors & objectives** - who each actor is (played and key unplayed), what they want, and
   what counts as winning or losing for them.
2. **Capabilities & instruments** - what each actor can realistically do given its
   instruments, authority, and industrial/military base, and what is off the table.
3. **Decision-making & internal dynamics** - how each actor decides under pressure: decision
   speed, veto players, domestic audience costs, and risk/escalation tolerance.
4. **Relationships & alignments** - starting trust, alliances, rivalries, and dependencies,
   directional where it matters (A's stance toward B can differ from B's toward A).
5. **History, precedent & red lines** - how the world reached this state, prior commitments,
   recent triggering events, red lines, and plausible off-ramps.
6. **Domain dynamics & world mechanisms** - how this specific world actually works: tipping
   points, second-order effects, what is fragile vs robust, and how a shock propagates.
7. **Initial knowledge state (fog of war)** - what is true at T0 and who knows, suspects, or is
   blind to each key fact, including the asymmetries.
8. **Information environment & narratives** - the competing framings, who pushes each, and the
   reliability/bias of the main information sources.

### Boundary on question 7 (important)

Question 7 captures **ground-truth knowledge state**: what is true and who knows it at game
start. Record only the epistemic starting state (truth + who knows what).

## Output (markdown only)

A single document, prose with headers, in this order:

```markdown
# Baseline Qualitative Context

## Actor Profiles & Objectives
## Capabilities & Instruments
## Decision-Making & Internal Dynamics
## Relationships & Alignments
## History, Precedent & Red Lines
## Domain Dynamics & World Mechanisms
## Initial Knowledge State
## Information Environment & Narratives
```

Ground every claim in the scenario text. Where the scenario is silent, say so briefly rather
than fabricating. This document feeds edge mechanism generation and the runtime IEGS/adjudicator;
players never see it, so the Initial Knowledge State section may hold secrets safely.
