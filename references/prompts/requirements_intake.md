# Requirements Intake Prompt — Base Template

> Used by `sub-gather-requirements` to clarify the analysis object before any
> data is fetched. Keep clarifying questions to a maximum of two.

## Goal

Extract a structured requirements object from the raw user message.

## Required Fields

- `object` — the gaming system / game / hardware target of analysis.
- `scope` — what aspects matter (latency, FPS, stability, thermals, all).
- `timeframe` — when results are needed (now / this season / long-term).
- `available_inputs` — hardware profile, benchmark logs, screenshots, etc.
- `target_audience` — competitive gamer / casual / streamer / content creator.
- `language` — `en` or `vi`.
- `analysis_type` — `combined` (default), `latency`, `fps`, `stability`.

## Rules

1. Default `analysis_type` to `combined` and state the assumption.
2. Ask at most **two** clarifying questions if the `object` is unclear.
3. Normalize hardware identifiers (model names, driver versions).
4. Never fetch external data in this step.

## Output

```
REQUIREMENTS CONFIRMED:
- Object: ...
- Scope: ...
- Timeframe: ...
- Available inputs: ...
- Target audience: ...
- Language: en/vi
- Analysis type: combined
```
