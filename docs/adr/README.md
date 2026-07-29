# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for
gaming-os-hardware-tweaking. Each ADR documents a key architectural decision
with context, options considered, and rationale.

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](adr-001-python-package-structure.md) | Use Python package with setuptools for CLI tools | Accepted | 2026-07-11 |
| [002](adr-002-evidence-hierarchy.md) | 4-tier evidence hierarchy for recommendation quality | Accepted | 2026-07-11 |
| [003](adr-003-knowledge-pipeline.md) | Multi-source academic crawl with composite scoring | Accepted | 2026-07-11 |
| [004](adr-004-config-rollback.md) | Automatic backup before profile mutation | Accepted | 2026-07-11 |

## ADR Template

```markdown
# ADR-NNN: Title

**Status:** [Proposed | Accepted | Deprecated | Superseded]
**Date:** YYYY-MM-DD

## Context
[What problem are we solving?]

## Decision
[What did we decide?]

## Options Considered
1. [Option A] — [pros/cons]
2. [Option B] — [pros/cons]

## Consequences
[What are the outcomes — good and bad?]

## References
[Links to related documents/ADRs]
```
