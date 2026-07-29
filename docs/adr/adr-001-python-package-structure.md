# ADR-001: Use Python package with setuptools for CLI tools

**Status:** Accepted
**Date:** 2026-07-11

## Context

The project needed production-grade CLI tools alongside Claude Code skill files.
Options: standalone scripts, Python package, or Node.js package. The primary
audience is Python users (data scientists, engineers, power users).

## Decision

Package the project as a `src/gaming_tweaks/` Python package using setuptools
with entry points for CLI commands. Combine with `.md` skill files in `skills/`
for Claude Code integration.

## Options Considered

1. **Pure .md skills only** — No CLI, only Claude Code harness
   - Pro: Simple
   - Con: No standalone use, not reusable outside Claude
2. **Python package with CLI entry points** — Chosen
   - Pro: Reusable as library + CLI, installable via pip, testable
   - Con: More complexity in packaging/config
3. **Separate CLI repo** — CLI tools in a different repository
   - Pro: Separation of concerns
   - Con: Version sync overhead, split documentation

## Consequences

- Library users install via `pip install gaming-os-hardware-tweaking`
- CLI users get `gaming-tweaks-{profile,recommend,benchmark,update-kb}`
- Claude Code users use the `.md` skill files directly
- Tests cover both library API and tool logic
- Package metadata in `pyproject.toml` enables PyPI publishing
