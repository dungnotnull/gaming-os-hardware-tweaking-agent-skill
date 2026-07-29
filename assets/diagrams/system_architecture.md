# System Architecture Diagram

> Render with any Mermaid viewer (GitHub, mermaid.live, VS Code Mermaid plugin).

```mermaid
flowchart TD
    U[User Query] --> ROUTER
    ROUTER[Router — Chain-of-Thought Intent Classifier]
    ROUTER -->|ExecutionPlan| ORC
    ORC[Orchestrator]
    ORC -->|resolve| REG[SkillRegistry]
    REG --> SK1[skills/sub-gather-requirements.md]
    REG --> SK2[skills/sub-evidence-collector.md]
    REG --> SK3[skills/sub-core-analysis.md]
    REG --> SK4[skills/sub-knowledge-updater.md]
    REG --> SK5[skills/sub-advisor.md]
    REG --> SKM[skills/main.md]
    ORC -->|invoke| TOOLS[ToolRegistry]
    TOOLS --> T1[profile_system]
    TOOLS --> T2[recommend_tweaks]
    TOOLS --> T3[validate_benchmark]
    TOOLS --> T4[read/query_knowledge_brain]
    TOOLS --> T5[set/get_state]
    TOOLS --> T6[detect_language]
    ORC -->|emit| HOOKS[HookRegistry]
    HOOKS --> H1[logging]
    HOOKS --> H2[metrics]
    HOOKS --> H3[state_sync]
    HOOKS --> H4[event_emission]
    ORC -->|render+dispatch| LLM[LLMBackend — callable / offline-assembly]
    ORC -->|check+autofix| GATES[Quality Gates U1-U6, G1-G4]
    ORC -->|track| BUDGET[Token Budget / Context Window]
    ORC -->|fallback| DEG[Graceful Degradation L0-L4]
    GATES --> RESULT[OrchestrationResult]
    DEG --> RESULT
    BUDGET --> RESULT
    RESULT --> KB[SECOND-KNOWLEDGE-BRAIN.md]
    RESULT --> LOGS[logs/ structured]
    CFG[AppConfig defaults + file + env] --> ORC
    CFG --> TOOLS
    CFG --> GATES
    REF[references/ prompts + domain] -.-> LLM
    ASSETS[assets/schemas JSON-Schema] -.-> TOOLS
    ASSETS -.-> REG
    SCRIPTS[scripts/ setup + seeding] -.-> KB
```

## Module Map

| Layer | Module | Responsibility |
|-------|--------|---------------|
| Config | `gaming_tweaks.config` | Type-safe AppConfig (defaults + file + env). |
| Registry | `gaming_tweaks.registry` | Load / validate / resolve skills. |
| Router | `gaming_tweaks.router` | Chain-of-thought intent → ExecutionPlan. |
| Tools | `gaming_tweaks.tools` | JSON-Schema-gated tool registry. |
| Hooks | `gaming_tweaks.hooks` | Lifecycle / state-sync / event emission. |
| Orchestrator | `gaming_tweaks.orchestrator` | End-to-end execution loop. |
| Knowledge | `tools/knowledge_updater.py` | Academic + RSS crawl pipeline. |
| Domain pkg | `src/gaming_tweaks/*` | system_profiler, tweak_recommender, config_manager, benchmark_validator, cli. |
