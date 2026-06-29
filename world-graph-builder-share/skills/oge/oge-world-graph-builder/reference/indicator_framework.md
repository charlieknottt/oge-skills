# Indicator Framework

The fixed scaffolding that makes stock generation fill-in-the-blank rather than free
invention. Distilled from the Indicator Framework design doc. The **indicators are fixed and
never generated**; what the skill generates is **stocks** (concrete, scenario-specific values
under them).

## Key terms

- **Dimension** - a fixed top-level category: the P, M, E, S, I, I of PMESII plus Physical.
  Never changes between scenarios.
- **Sub-indicator / mechanical type** - an abstract kind of indicator, typed by what it does
  in the game (not its subject). Lives in the fixed catalog. Not a number.
- **Stock** - a concrete, scenario-specific node created from a mechanical type, e.g. "US
  battery cell output." Its value changes each round.
- **Edge** - a causal link between two stocks, generated from scenario docs + world knowledge.
  Engine-internal; players never see edges.

## The fixed layers

**Dimensions (PMESII-P):** Political, Military, Economic, Social, Information, Infrastructure,
Physical Environment. Every stock lives in exactly one.

**Stock-type catalog** (typed by game function, so it transfers across any scenario):
`zero-sum-pool`, `scheduled-threat`, `spendable`, `service-level`, `clock`, `buildout`,
`trust-sentiment`, `upstream-access`, `policy-lever`, plus `capacity` and `other`. The type
decides whether a stock is numeric (pools, ramps, clocks, levers) or qualitative (everything
else), and the node's **dynamics** (Level/Lever/Accumulator/Drifter) is derived from it. See
`quant_questions.md` for the nine questions that surface them.

The key design rule: **the catalog is typed by mechanical function, not domain content.**
A supply-chain game and a ransomware game share no subject matter, but both contain contested
pools, scheduled threats, spendables, and clocks.

## Counts and balance

- Bounded and reviewable: roughly **3-6 stocks per dimension, ~25-35 total** (the shipped
  examples are 26 and 33), scaled by how relevant each dimension is to the scenario. A supply
  crisis weights Economic/Infrastructure/Physical heavy and Military light.
- Every stock is validated by the Game Manager at setup.

## Decision-to-indicator mapping (runtime, five steps)

1. **Read** the decision/inject and its intent.
2. **Map** it to the specific stocks it directly hits (the landing points; cap ~7).
3. **Direct effect** applied to those stocks, logged with rationale *before* anything else moves.
4. **Propagate** through causal edges to dependent stocks, honoring delays.
5. **Next state** becomes current; the White Cell turns the relevant changes into injects.

Mapping free text to stocks is the most error-prone step, which is why each direct delta is
logged with its rationale before propagation.

## What this means for the builder

- Generate stocks by **answering the nine questions** against the scenario, not by inventing
  structure. Tag each with `pmesii`, `stock_type`, and the engine node `type`.
- Keep the set bounded and balanced across dimensions.
- Generate edges as a shallow, causal graph between stocks (see `schema.md` and the prompts).
