# SKILL.md — Skill Registry & Harness Specification

> Authoritative documentation for how skills are registered, resolved,
> executed, validated, and exposed in the `gaming-os-hardware-tweaking`
> harness. This is the single source of truth that the Python
> `gaming_tweaks.registry`, `gaming_tweaks.router`, and
> `gaming_tweaks.orchestrator` modules implement.

**Version:** 2.0.0 (Phase 6 — Flexible Agent & Skill Architecture)
**Status:** Production-grade, open-source ready

---

## 1. Overview

A **skill** is a self-contained, Markdown-encoded agent capability. Each skill
declares a role, a workflow, the tools it uses, an output format, and quality
gates. The harness loads every `skills/*.md` file into a **skill registry**,
routes incoming user queries to an **execution plan** via a chain-of-thought
router, and orchestrates the plan with hooks, tools, and quality gates.

The architecture is intentionally **modular and pluggable**:

```
User Query
   │
   ▼
┌────────────────────────────────────────────────────────────────────┐
│  Router (chain-of-thought)  ──►  ExecutionPlan (intent + skills)     │
└────────────────────────────────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────────────────────────────┐
│  Orchestrator                                                        │
│   ├── SkillRegistry   ── resolve(name|tag|query)                     │
│   ├── ToolRegistry    ── invoke(tool, inputs)   [JSON-Schema gated]  │
│   ├── HookRegistry    ── emit(event, context)   [lifecycle events]  │
│   ├── QualityGates    ── check + auto-fix + retry                     │
│   ├── StateManager    ── shared dict across steps                    │
│   ├── LLMBackend      ── callable | offline-assembly                  │
│   └── TokenBudget     ── context-window tracking + overflow hooks     │
└────────────────────────────────────────────────────────────────────┘
   │
   ▼
OrchestrationResult (run_id, steps, state, gates, trace, token_usage)
```

---

## 2. Skill File Format

Every skill is a Markdown file with YAML frontmatter and structured sections.

```markdown
---
name: sub-core-analysis
description: Optimize OS and hardware configuration for gamers ...
---
## Role & Persona
## Workflow
## Tools
## Output Format
## Quality Gates
```

### 2.1 Frontmatter Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | yes | string | Skill identifier; must be unique. |
| `description` | yes | string | One-line summary used by the router for routing/scoring. |

### 2.2 Required Sections

| Section | Purpose |
|---------|---------|
| `## Role & Persona` | Who the skill acts as; persona context. |
| `## Workflow` (or `## Harness Execution Protocol` for `main.md`) | Ordered execution steps. |
| `## Tools` | Tools the skill may invoke (used to bind evidence). |
| `## Output Format` | Declared output template (drives gate U5). |
| `## Quality Gates` | Per-skill gate checklist (drives gate coverage). |

The registry validator (`SkillRegistry.validate_spec`) enforces these sections.
`main.md` may substitute `## Harness Execution Protocol` for `## Workflow`.

---

## 3. Skill Registration

Skills are registered through three supported paths:

### 3.1 File-based auto-discovery (default)

```python
from pathlib import Path
from gaming_tweaks.registry import SkillRegistry

registry = SkillRegistry(skills_dir=Path("skills"))
registry.load(strict=True)  # raises SkillValidationError on malformed skills
```

`load()` parses every `*.md` file under `skills/`, extracts frontmatter +
structured sections, infers `tags`, `tools`, `gates`, and minimal I/O schemas,
then registers each `SkillSpec` keyed by name and by tag.

### 3.2 Programmatic registration

```python
from gaming_tweaks.registry import SkillSpec, SkillRegistry

spec = SkillSpec(
    name="sub-my-skill",
    description="...",
    body_markdown="## Role & Persona\n...\n## Workflow\n...\n## Output Format\n...",
)
SkillRegistry().register(spec)
```

### 3.3 Validation rules

`SkillRegistry.validate_spec` enforces:
- non-empty `name` and `description`
- presence of `## Role & Persona`, `## Workflow` (or alt), `## Output Format`
- body length >= 120 chars
- unique names (later registrations overwrite with a logged warning)

Unknown frontmatter keys are tolerated (forward-compatible). Invalid skills
abort loading in `strict=True`; in `strict=False` they are skipped with a
warning.

---

## 4. Skill Resolution

The registry supports four resolution modes:

| Mode | Method | Use case |
|------|--------|----------|
| By name | `registry.get(name)` | Deterministic step execution. |
| By tag | `registry.by_tag(tag)` | Group queries ("knowledge", "advisory"). |
| By search | `registry.search(query)` | Token-overlap ranking for ad-hoc queries. |
| By router | `Router.route(query)` | Intent-based plan selection (see §6). |

Tags are inferred from name/description/body (`sub-skill`, `harness`,
`intake`, `evidence`, `analysis`, `knowledge`, `advisory`, `latency`, `fps`,
`tweaks`). Tags are stable and deterministic.

---

## 5. Tool System

Tools are schema-validated, dynamically invocable capabilities exposed to the
orchestrator (and discoverable by LLMs). See `assets/schemas/tool_schema.json`
for the canonical JSON-Schema describing a tool definition.

### 5.1 Tool definition

```python
Tool(
    schema=ToolSchema(
        name="query_knowledge_brain",
        description="Line-level grep of SECOND-KNOWLEDGE-BRAIN.md",
        category="knowledge",
        input_schema={"type": "object", "required": ["query"], ...},
        output_schema={"type": "object", ...},
        idempotent=True,
        safe=True,
        destructive=False,
    ),
    handler=callable_handler,
)
```

### 5.2 Built-in tools

| Tool | Category | Safe | Idempotent | Description |
|------|----------|------|-----------|-------------|
| `profile_system` | system | yes | no | Detect local CPU/GPU/RAM/storage/display/OS. |
| `recommend_tweaks` | tweaks | yes | no | Evidence-backed tweak plan for local profile. |
| `validate_benchmark` | benchmark | yes | yes | Frame-time / FPS statistics for a run. |
| `read_knowledge_brain` | knowledge | yes | yes | Read full SECOND-KNOWLEDGE-BRAIN.md. |
| `query_knowledge_brain` | knowledge | yes | yes | Grep knowledge brain for a query. |
| `append_knowledge_entry` | knowledge | yes | no | Append-only entry to the knowledge brain. |
| `set_state` / `get_state` | state | yes | no | Shared orchestrator state read/write. |
| `detect_language` | i18n | yes | yes | Vietnamese vs English detection. |
| `hash_text` | utility | yes | yes | sha256/sha1/md5 hashing. |
| `noop` | utility | yes | yes | Safe no-op fallback. |

### 5.3 Invocation contract

`ToolRegistry.invoke(name, inputs)` returns a `ToolResult`:

```json
{
  "ok": true,
  "value": { ... },
  "error": null,
  "tool": "query_knowledge_brain",
  "elapsed_seconds": 0.0023,
  "invocation_id": "<hex>"
}
```

Inputs are validated against `input_schema` before the handler runs; outputs
are validated against `output_schema` when declared. Validation failures are
returned as `ok=false` with a descriptive error — they never raise.

### 5.4 Extending

```python
from gaming_tweaks.tools import Tool, ToolSchema, ToolRegistry

def my_handler(inputs): return {"echo": inputs["x"]}
ToolRegistry().register(Tool(
    schema=ToolSchema(name="echo", description="echo x",
                      input_schema={"type":"object","required":["x"],
                                    "properties":{"x":{"type":"string"}}}),
    handler=my_handler,
))
```

---

## 6. Router (Chain-of-Thought Intent Classification)

The router (`gaming_tweaks.router.Router`) inspects a user query and returns an
`ExecutionPlan`. It is **deterministic and rule-based** — no LLM call required —
and emits explicit reasoning steps for auditability.

### 6.1 Intents

| Intent | Skills | Trigger keywords (en/vi) |
|--------|--------|--------------------------|
| `full_pipeline` | all 5 sub-skills | (default fallback) |
| `requirements_only` | `sub-gather-requirements` | clarify, requirements, yêu cầu |
| `evidence_only` | `sub-evidence-collector` | evidence, sources, bằng chứng |
| `analysis_only` | `sub-core-analysis` | optimize, tweak, latency, tối ưu |
| `advisory_only` | `sub-advisor` | conclusion, recommend, khuyến nghị |
| `knowledge_lookup` | `sub-knowledge-updater` | papers, doi, học thuật |
| `profile_recommender` | requirements+core+advisor | my system, pc của tôi |
| `compare` | full pipeline w/ modes | compare, vs, so sánh |

### 6.2 Output schema

```json
{
  "intent": "full_pipeline",
  "skills": ["sub-gather-requirements", "sub-evidence-collector", "sub-core-analysis", "sub-knowledge-updater", "sub-advisor"],
  "reasoning": ["Received query (N chars).", "Detected language: vi.", "..."],
  "estimated_tokens": 17300,
  "language": "vi",
  "confidence": 0.7,
  "metadata": {}
}
```

---

## 7. Hooks (Lifecycle Events)

Hooks let external code react to orchestrator events without modifying the
core loop. See `assets/schemas/hook_schema.json`.

### 7.1 Event types

| HookType | Emitted |
|----------|---------|
| `orchestration.start` / `orchestration.end` | Run begin/end. |
| `step.pre` / `step.post` | Before/after each skill. |
| `step.error` | Skill raised an exception. |
| `gate.pre` / `gate.post` / `gate.fail` | Quality-gate lifecycle. |
| `tool.pre` / `tool.post` / `tool.error` | Tool lifecycle. |
| `skill.resolve` | After skill resolution. |
| `degradation` | Graceful-degradation escalation. |
| `context.overflow` | Token budget exceeded. |
| `retry` | Retryable failure recovery. |

### 7.2 Hook context

Each hook receives a `HookContext` with `event`, `run_id`, `skill_name`,
`step_index`, `gate_name`, `tool_name`, `inputs`, `outputs`, `state`,
`error`, `elapsed_seconds`, `metadata`, and `errors`.

### 7.3 Built-in hooks

`logging_hook`, `metrics_hook`, `state_sync_hook`, `event_emission_hook` —
all exception-safe (a failing hook logs + records on context, never aborts).

---

## 8. Execution

`Orchestrator.run(query, inputs)` produces an `OrchestrationResult`:

```json
{
  "run_id": "<hex>",
  "query": "...",
  "plan": { "intent": "...", "skills": ["..."], "reasoning": ["..."] },
  "steps": [ SkillResult, ... ],
  "state": { "<skill_name>": { "response": "...", "evidence_count": N } },
  "degradation_level": 0,
  "gates": [ QualityGateResult, ... ],
  "token_usage": { "estimated_prompt_tokens": N, "budget": N },
  "elapsed_seconds": 1.23,
  "ok": true,
  "errors": [],
  "trace": ["..."]
}
```

### 8.1 LLM backends

| Backend | Behavior |
|---------|----------|
| `OfflineAssemblyBackend` (default) | Renders the prompt + gathers real tool evidence; `response` documents that the prompt is LLM-ready. **Never fabricates an answer.** |
| `CallableLLMBackend(func)` | Calls a real `prompt -> response` function for each skill. |

### 8.2 Context-window management

The orchestrator estimates tokens per step (`len//4`) and aborts further steps
with a `context.overflow` hook + degradation when the cumulative prompt tokens
exceed `config.llm.available_input_tokens`.

### 8.3 Graceful degradation

Levels 0–4 (0 = full data, 4 = all sources + KB fail). On any failure the
orchestrator emits a `degradation` hook, records the reason in `trace`, and
continues rather than crashing.

### 8.4 Error handling & retry

- LLM call failure → degrade + optional fallback-provider response.
- Gate failure → auto-fix (idempotent in-memory) up to `flags.max_gate_retries`.
- Missing skill → degrade to level 2 and continue.
- Tool validation failure → returned as `ToolResult(ok=false)` (never raises).

---

## 9. Quality Gates

Ten gates run after the plan completes. Each gate has a check function
(`GATE_CHECKS`), an auto-fix, and a 2-retry limit.

| Gate | Check | Auto-fix |
|------|-------|----------|
| U1 | ≥3 sources cited, ≥1 academic | Append KB excerpt as evidence. |
| U2 | Disclosure before recommendation | Prepend disclosure section. |
| U3 | Evidence tier labels present | Annotate tier legend. |
| U4 | Output language matches plan | (language detected upstream). |
| U5 | Output uses declared template | (template sections checked). |
| U6 | Claims traceable to source | Tool evidence counts. |
| G1 | Input latency config stated | Inject Reflex/VRR/BFI config. |
| G2 | CPU/GPU scheduling tuned | Inject Game Mode/power plan. |
| G3 | Monitoring metrics defined | Inject frame-time/1% low metrics. |
| G4 | Stability-vs-gain tradeoffs noted | Inject stability note. |

---

## 10. I/O JSON Schemas

Canonical machine-readable schemas live in `assets/schemas/`:

- `skill_spec.schema.json` — `SkillSpec` shape.
- `tool_schema.json` — `ToolSchema` shape.
- `hook_context.schema.json` — `HookContext` shape.
- `execution_plan.schema.json` — `ExecutionPlan` shape.
- `orchestration_result.schema.json` — `OrchestrationResult` shape.
- `app_config.schema.json` — `AppConfig` shape.

These schemas are the contract between the harness, external integrators, and
LLM tool-discovery prompts.

---

## 11. Configuration

All runtime knobs are managed by `gaming_tweaks.config.AppConfig`, loaded from
defaults → JSON/TOML file → environment variables (env wins). See
`config/default.json` for the canonical profile and `assets/schemas/app_config.schema.json`
for the schema.

Env var convention: `GAMING_TWEAKS_<SECTION>__<KEY>` (or `GAMING_TWEAKS_<TOP_KEY>`
for top-level fields), e.g. `GAMING_TWEAKS_LLM_MAX_TOKENS=4096`.

```python
from gaming_tweaks.config import load_config
cfg = load_config("config/default.json")
```

---

## 12. Extending the Harness

| Want to… | Do this |
|----------|---------|
| Add a new skill | Drop a `skills/sub-*.md` file; the registry auto-loads it. |
| Add a new tool | `registry.register(Tool(schema=..., handler=...))`. |
| Add a hook | `hooks.register(HookType.POST_STEP, handler, name="...")`. |
| Add a gate | Add to `GATE_CHECKS` + reference in `config.orchestration.quality_gates`. |
| Swap the LLM | Pass `llm=CallableLLMBackend(my_func)` to `Orchestrator`. |
| Change routing | Edit `gaming_tweaks.router._KEYWORDS` / `_skills_for`. |

---

## 13. References

- `PROJECT-detail.md` — full domain specification.
- `references/` — prompt base-templates and domain knowledge for RAG grounding.
- `assets/` — JSON schemas + system architecture diagram.
- `config/` — type-safe configuration profiles.
- `scripts/` — setup, seeding, ingestion, validation automation.
- `src/gaming_tweaks/` — Python implementation (`registry.py`, `router.py`,
  `hooks.py`, `tools.py`, `config.py`, `orchestrator.py`).
