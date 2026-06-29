# The Eight Qualitative Questions (sidecar)

The qualitative sidecar holds all world-state knowledge that cannot be a numeric stock. It is
generated once at setup, locked at launch, and never edited mid-game (mid-game qualitative
shifts go into the round log as White Cell injects). The agent answers eight structured
questions from the scenario document. These complement the stock-generation questions
(`quant_questions.md`): that set asks what *kinds of things* exist in the world, this set
asks what *qualitative knowledge* the runtime needs that numbers cannot hold.

| # | Question | -> produces |
|---|---|---|
| 1 | Who are the actors and what do they want? | actor profiles + objective functions |
| 2 | What can each actor realistically do, and what is off the table? | feasibility envelope |
| 3 | How does each actor decide and react under pressure? | behavioral / decision profile |
| 4 | What relationships and sentiments shape behavior? | relationship / sentiment map |
| 5 | How did the world get here, and what are the red lines? | backstory + escalation logic |
| 6 | How does this specific world actually work beneath the numbers? | world-mechanism notes |
| 7 | What is true at the start, and who knows it? | initial knowledge state (fog of war) |
| 8 | Who reports on this world, and what narratives compete? | narrative map + source biases |

## Who each question serves

- **Edge-mechanism generation (setup):** mainly #4 relationships, #5 history, #6 domain
  dynamics. These ground why one stock moves another.
- **Runtime reasoning (play):** mainly #1 objectives, #2 capabilities, #3 decision dynamics,
  #5 escalation logic, #7 knowledge state. These make each actor behave plausibly.
- **IEGS / information products:** mainly #7 knowledge state and #8 information environment.
  These decide what an actor could plausibly learn and how it would be framed.

## What the sidecar contains

- **Actor profiles & objectives** - who each team represents, what they want, what they fear,
  and what counts as winning or losing.
- **Capabilities & instruments** - the instruments, authority, and industrial/military
  base each actor can realistically bring, plus what is off the table.
- **Decision-making & internal dynamics** - decision speed, veto players, domestic audience
  costs, and risk/escalation tolerance per actor.
- **Relationships & alignments** - starting trust, alliances, rivalries, dependencies,
  directional where it matters.
- **History, precedent & red lines** - how the world got here, prior commitments, recent
  triggers, red lines, and off-ramps.
- **Domain dynamics & world mechanisms** - tipping points, second-order effects, what is fragile
  vs robust, how shocks propagate. The qualitative complement to the numeric edge graph.
- **Initial knowledge state** - what is true at game start and who knows, suspects, or is blind
  to each key fact.
- **Information environment & narratives** - competing framings, who pushes them, and the
  reliability/bias of the main information sources.

## Knowledge state is ground truth

Question 7 captures **knowledge state**: what is *true* at T0 and *who knows it*. This is
ground-truth world state, and fog of war is part of the world the runtime reasons over. Because
players never see the sidecar (just as they never see edges), secrets are safe to record here.

## Output

A single markdown document with headers, one per question, in order (`qualitative_sidecar.md`).
It is prose, not data. It can run in parallel with stock/edge generation because it needs only
the scenario frame. It is consumed by edge generation (mechanism grounding) and the runtime
adjudicator / IEGS. Locked automatically at finalize.
