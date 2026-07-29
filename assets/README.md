# /assets — Static Resources, Schemas & Diagrams

Machine-readable contracts and visual assets for the harness.

## Layout

```
assets/
├── schemas/                                    # JSON-Schema contracts
│   ├── skill_spec.schema.json
│   ├── tool_schema.schema.json
│   ├── hook_context.schema.json
│   ├── execution_plan.schema.json
│   ├── orchestration_result.schema.json
│   └── app_config.schema.json
└── diagrams/
    └── system_architecture.md                  # Mermaid architecture diagram
```

## Purpose

- **schemas/** — the canonical, machine-readable contract between the harness,
  external integrators, and LLM tool-discovery prompts. Importing systems
  (or LLMs) read these to know exact field names, types, enums, and ranges.
- **diagrams/** — human-readable architecture and data-flow diagrams.
