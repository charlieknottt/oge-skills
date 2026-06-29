# The Nine Stock Questions (stock proposal)

The core of stock generation. The agent is **not** asked to invent indicators; it answers nine
specific questions about the scenario documents. Each question maps to exactly one `stock_type`.
This is what keeps generation repeatable: two runs of the same scenario surface near-identical
stocks.

## Stock type vs. dynamics (you only choose one)

Each node ends up with a `stock_type` and a `dynamics`, but these are **not two separate
decisions**. You choose the stock type from a question; the dynamics follows from it.

- **`stock_type`** (this document) - one of **9**, from the 9 questions below. The thing you
  actually choose. Answers *"what is this?"* Lives on the rich model (`stocks.json`).
- **dynamics** - one of **4**: `Level | Lever | Accumulator | Drifter`. Answers *"how does it
  move on its own each tick?"* It is **derived** from the stock type (table below), not chosen
  separately. It lives on the lean graph in the field named `type` (kept that way for the
  engine; read it as "dynamics"). Defined in `taxonomy.md`.

Only the stock type is ever called a "type." The 4-value dynamics is a different concept and is
computed, not picked, so there is nothing to confuse it with. (If you counted 4 dynamics and
wondered why this file has 9 questions: the 9 are stock types; they map down to the 4 dynamics.)

## The nine questions

| # | Question | -> stock_type | -> dynamics |
|---|---|---|---|
| 1 | What do players allocate that is scarce? | **zero-sum-pool** | Level |
| 2 | What escalates on a schedule regardless of player action? | **scheduled-threat** | Drifter |
| 3 | What do players spend that does not come back easily? | **spendable** | Level |
| 4 | What services do citizens/systems depend on that the crisis threatens? | **service-level** | Level |
| 5 | What is secret and racing to become public? | **clock** | Drifter |
| 6 | What slow build can players start now and feel only later? | **buildout** | Accumulator |
| 7 | Whose opinion of whom constrains action? | **trust-sentiment** | Level |
| 8 | What sits upstream of the things players think they are managing? | **upstream-access** | Level |
| 9 | What can an actor set or hold directly, that stays put until a decision or inject moves it? | **policy-lever** | Lever |

Question 9 is what surfaces **levers** as ordinary nodes (tariff level, export controls,
blockade intensity, cyber posture). They are not a special interface or an external input: they
are nodes generated like any other, updated through the same decision/inject path, and they
simply have no autonomous movement (see `taxonomy.md`). When a team/player config is supplied,
question 9 is answered from each team's action space; without one, it is inferred from the
scenario.

Two catch-all types exist for things the questions surface that do not fit cleanly: `capacity`
(a held ability/throughput) and `other` (last resort; flag for GM review).

## Numeric vs qualitative

The stock type settles the numeric question before it becomes an argument:

- **Numeric** (carry 0-100 values): `zero-sum-pool`, `scheduled-threat`, `clock`, `buildout`,
  `capacity`, `service-level`, `policy-lever` (a directly-set posture/intensity).
- **Qualitative-leaning** (still on the scale, but read as an index): `trust-sentiment`,
  `upstream-access`, `spendable`. Reserve hard numbers for finite/zero-sum/scheduled quantities;
  do not fabricate precision elsewhere.

## Mapping stock_type -> dynamics (derived by default)

The dynamics field is computed from the stock type. The default is deterministic; the
generator or GM may override in genuine edge cases (the engine accepts any of the 4), but the
default is what keeps generation consistent.

| stock_type | dynamics |
|---|---|
| policy-lever | Lever |
| buildout | Accumulator |
| scheduled-threat, clock | Drifter (or a White-Cell-driven inject) |
| zero-sum-pool, spendable, service-level, trust-sentiment, upstream-access, capacity, other | Level |

## The four admission tests (every candidate must pass)

1. **Something moves it** (it has at least one plausible driver / in-edge).
2. **It moves something** (it has at least one plausible effect / out-edge).
3. **It is not another stock in disguise** (no near-duplicates).
4. **A human can narrate a move** (it is a legible 0-100 index with clear anchors).

Failing a test demotes the candidate to the qualitative sidecar (it is not deleted, and can be
promoted later if play makes it load-bearing). **Policy-levers are the exception to test 1:**
they have no incoming edges and are moved only by a direct decision or inject, never by upstream
propagation.
