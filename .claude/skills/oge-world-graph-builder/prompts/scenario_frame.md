# Prompt: Frame the scenario (step 2)

Role: you read the raw scenario text and pull out the structured frame the rest of the build needs.
This is the first judgment step. Everything after it (picking nodes, writing the background notes,
drawing edges) reads your output, so be accurate and do not invent facts the text does not support.

## Input
- `scenario_text` - the parsed scenario document plus any supplementary text (the output of the
  "read the scenario" step, which only concatenates the source files).

## Task
Answer these from the text. Where the text is silent, make the smallest reasonable inference and say
so in the field; do not fabricate specifics.

- **title** - a short name for the scenario.
- **central_crisis** - one or two sentences: what is actually going wrong.
- **actors** - every actor that matters, each marked `played` (a human team runs it) or not (a key
  actor no one plays). Give each a one-line role/goal.
- **teams** - the played teams and their mandate.
- **time_horizon** and **rounds** - how long the game models and how many rounds it runs.
- **scarcities** - the named things players compete over (supply, access, capital, attention).
- **threats** - the named things that get worse over time on their own.
- **win_conditions** / **lose_conditions** - what counts as winning or losing.

## Output (JSON only)
Return one object matching `schemas/frame.schema.json`, no prose around it:
```json
{
  "title": "...",
  "central_crisis": "...",
  "actors": [ { "name": "...", "role": "...", "played": true } ],
  "teams": [ { "name": "...", "mandate": "..." } ],
  "time_horizon": "...",
  "rounds": 6,
  "scarcities": ["..."],
  "threats": ["..."],
  "win_conditions": ["..."],
  "lose_conditions": ["..."]
}
```
Save it as `scenario_frame.json`. The build stops and re-asks if required keys are missing.
