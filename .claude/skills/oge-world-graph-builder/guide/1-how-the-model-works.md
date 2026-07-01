# 1. How the world model works

This is the plain-English explanation of what the skill builds and why. Read this first.
(The exact JSON fields are in `2-data-shapes.md`. The checks that keep it honest are in
`3-realism-checks.md`.)

## The big picture

A "world graph" is a simple cause-and-effect map of a scenario. It has two parts:

- **Nodes** (we also call them "stocks") are the things in the world you can track on a
  0-100 scale: supply levels, market confidence, military readiness, a threat that is building.
- **Edges** are arrows between nodes that say "when this goes up, that goes up (or down), by
  about this much, after about this long."

That is the whole idea. Players never see the graph. It is a background model that helps the
game stay consistent: when a player does something, the change ripples through the arrows so the
world reacts in a believable, repeatable way.

Two important scoping facts:

1. This skill **builds** the graph before the game. It does not run the game. At game time,
   Claude reads the graph as context and reasons over it.
2. Because the graph is context (not a physics simulator), the parts that matter most are the
   **structure** (which node affects which) and the **plain-English reason** on each edge, more
   than the exact numbers.

## The 7 dimensions (PMESII-P)

Every node belongs to exactly one of seven fixed dimensions. They never change between
scenarios, which is what makes different games comparable.

| Dimension | Covers |
|---|---|
| **Political** | governments, alliances, legitimacy, domestic politics |
| **Military** | forces, readiness, posture |
| **Economic** | markets, trade, prices, industry |
| **Social** | public opinion, trust, cohesion |
| **Information** | narratives, media, what is known vs secret |
| **Infrastructure** | supply chains, grids, networks, logistics |
| **Physical** | terrain, geography, physical environment |

The dimensions are a checklist for coverage. They do not by themselves say how a node behaves.

## How nodes get created: the 9 questions

The skill does not invent nodes freely. It answers **nine fixed questions** about the scenario.
Each "yes" produces one or more nodes, and each question tags the node with a **stock type**.
This is what makes two runs of the same scenario produce nearly the same nodes.

| # | Question | Stock type | How it behaves |
|---|---|---|---|
| 1 | What is scarce that players fight over? | zero-sum-pool | Level |
| 2 | What gets worse on a schedule no matter what players do? | scheduled-threat | Drifter |
| 3 | What do players spend that does not come back easily? | spendable | Level |
| 4 | What service do people depend on that the crisis threatens? | service-level | Level |
| 5 | What secret is racing to become public? | clock | Drifter |
| 6 | What slow build can players start now and feel only later? | buildout | Accumulator |
| 7 | Whose opinion of whom limits what can be done? | trust-sentiment | Level |
| 8 | What sits upstream of the things players think they control? | upstream-access | Level |
| 9 | What can an actor set directly and hold until they change it? | policy-lever | Lever |

Two catch-all types exist for things that do not fit cleanly: **capacity** (a held ability) and
**other** (last resort, flag for the Game Manager to review).

Question 9 is important: it is how the levers (a tariff level, an export-control setting, a
blockade intensity) show up. They are ordinary nodes that just happen to have no arrows coming
into them, because only a direct decision moves them.

### The 0-100 scale

Every node sits on the same 0-100 scale so values mean the same thing across the game:

| Value | Meaning |
|---|---|
| 0 | collapse / nonexistent |
| 25 | struggling, below average |
| 50 | solid, average (default) |
| 75 | strong, top-tier |
| 90 | elite |
| 100 | theoretical ceiling |

Some nodes are **inverted**, meaning a low value is the good state (a threat, a compromise, a
level of friction). For those, read the scale upside down: low is healthy.

When you build the graph you pick each node's **starting value** on this scale. Default healthy
things to 55-65, contested/at-risk things lower, and threats low (because they are inverted, so
low means "not much threat yet").

## How a node moves on its own: the 4 behaviors

Every node has one of four behaviors. This is the single most important design choice per node.
The behavior is not picked separately, it is decided by the stock type above.

| Behavior | What it does on its own | What else moves it | Examples |
|---|---|---|---|
| **Level** (default) | drifts toward the sum of its incoming arrows | a decision pushes it directly | safe supply, market confidence, prestige |
| **Lever** | nothing, it holds its value | only a direct decision or event | tariff level, export controls, cyber posture |
| **Accumulator** | builds up funded effort, then pays off later through a delayed arrow | funding speeds it; a shock can wipe out the progress | domestic buildout, reshoring |
| **Drifter** | moves on a fixed schedule regardless of play | a decision can slow it, never stop it | a rising threat, mounting media pressure |

If a node does not clearly need one of the other three, it is a **Level**. That is the default.

**A note on Levers.** A lever is just a normal node with no incoming arrows. There is no special
control panel for it. It changes only when a player decides to change it, and all of its
"timing" lives on the arrows going *out* of it.

### "Easy to destroy, hard to build"

The model deliberately makes bad things happen faster than good things, because that is how the
real world usually works:

- **Levels** build slowly but drop fast.
- **Accumulators** take time to pay off but a shock can destroy the accrued progress in one step.
- **Drifters** move on schedule; the interesting timing is that pushing back on them takes a
  while to bite, so act early.

There is one shared rule that produces this: an arrow reads the **worse** of {where the source is
now, where it was `lag` steps ago}. So when something collapses, the damage lands next step; when
something grows, the benefit still waits out the full delay.

## How nodes connect: edges and the wiring rules

An edge is one arrow from a source node to a target node. It carries:

- a **sign** (`+` means they move the same way, `-` means opposite),
- a **magnitude** (a 0-1 number for how strong the push is),
- a **lag** (how many steps until the effect lands; 6 steps = 1 round),
- a one-sentence **reason** (the actual mechanism, e.g. "tariffs raise input costs, so prices rise").

When wiring edges, follow these rules (the linter checks them):

- **Levers get no incoming arrows.** All their timing lives on their outgoing arrows. (Hard rule.)
- **Accumulators** take funding/effort arrows in, and send one **delayed** payoff arrow into the
  Level they feed. (Warned if missing.)
- **Drifters** send their harm out with little or no delay (threats bite fast). (Warned if slow.)
- Prefer explicit **balancing arrows** (negative feedback) so the world self-corrects, instead of
  relying on nodes drifting back on their own.
- **No node is left unconnected.** (Hard rule.)
- Keep chains short and causal. Avoid long unbroken "everything boosts everything" chains that run
  away to the ceiling.

## The sidecar: the 8 questions numbers cannot answer

Not everything about a world is a number. The **sidecar** is a plain-text document that holds the
qualitative context: who the actors are, what they want, how they decide, what is secret. It is
written once at setup and locked when the game starts. Players never see it, so secrets are safe
there.

| # | Question | Produces |
|---|---|---|
| 1 | Who are the actors and what do they want? | actor profiles and goals |
| 2 | What can each actor realistically do, and what is off the table? | what is possible |
| 3 | How does each actor decide under pressure? | decision style |
| 4 | What relationships and feelings shape behavior? | who trusts/distrusts whom |
| 5 | How did the world get here, and what are the red lines? | backstory and escalation |
| 6 | How does this world actually work beneath the numbers? | domain mechanisms |
| 7 | What is true at the start, and who knows it? | the starting knowledge state (fog of war) |
| 8 | Who reports on this world, and whose story competes? | the information environment |

The sidecar does two jobs: it grounds the **reasons** on the edges during the build, and at game
time it helps each actor behave plausibly.

## One runtime note (not a build step)

At game time, a player's decision becomes a number in a controlled way, so nobody can smuggle a
big effect through dramatic wording. The runtime picks one of five effect sizes based on how much
the player actually committed:

| Tier | Size (per round) | When |
|---|---|---|
| Negligible | 0-1 | no real resources committed |
| Minor | 2-4 | a small share of effort |
| Moderate | 5-8 | a meaningful commitment |
| Major | 9-14 | a large, focused commitment |
| Transformational | 15-20 | an all-in, defining bet (rare) |

This matters for the builder only in one way: make every node a clear 0-100 index that a person
can narrate a move on, so the runtime can size these effects against it. (This "effect size" is a
runtime idea and is separate from an edge's 0-1 magnitude.)
