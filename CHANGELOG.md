# Changelog

All notable changes to gaming-os-hardware-tweaking will be documented in this file.

## [1.1.0] — 2026-07-21

### Added — Phase 6: Flexible Agent & Skill Architecture
- **`SKILL.md`** — comprehensive skill registry documentation (registration,
  resolution, execution, validation, I/O JSON schemas, hooks, tools, gates).
- **`src/gaming_tweaks/config.py`** — type-safe `AppConfig` with defaults — JSON
  file — environment overlay, runtime validation, feature flags, LLM params,
  and knowledge/logging/orchestration sections.
- **`src/gaming_tweaks/hooks.py`** — `HookRegistry` with 14 lifecycle events,
  priority ordering, exception-safety, and built-in logging/metrics/state-sync/
  event-emission hooks plus an `EventEmitter`.
- **`src/gaming_tweaks/tools.py`** — `ToolRegistry` with JSON-Schema-validated
  tools (dependency-free validator), 11 built-in tools, dynamic invocation, and
  per-tool metrics.
- **`src/gaming_tweaks/registry.py`** — `SkillRegistry` that loads/validates/
  resolves skills by name, tag, or token-overlap search; infers schemas, tools,
  gates, and tags.
- **`src/gaming_tweaks/router.py`** — deterministic chain-of-thought `Router`
  (8 intents, language detection, reasoning trace, token-budget estimate).
- **`src/gaming_tweaks/orchestrator.py`** — end-to-end `Orchestrator` wiring the
  registry, router, hooks, tools, quality gates (U1—U6 + G1—G4 with auto-fix +
  retry), shared state, context-window tracking, graceful degradation (L0—L4),
  and pluggable LLM backends (`OfflineAssemblyBackend`, `CallableLLMBackend`).
- **`src/gaming_tweaks/orchestrator_cli.py`** — `gaming-tweaks-harness` CLI.
- **Modular directories**: `/config` (3 profiles + README), `/scripts`
  (setup, seed, ingest, validate-architecture + README), `/references`
  (5 prompt base-templates + 2 domain docs + README), `/assets` (6 JSON-Schema
  contracts + Mermaid architecture diagram + README).
- **`tests/test_agent_architecture.py`** — 82 tests covering config, hooks,
  tools, registry, router, orchestrator, and scripts.
- **`scripts/validate_architecture.py`** — 42-check Phase 6 architecture validator.
- Extended `tools/validate_project.py` (184 checks) and `tools/run_test_scenarios.py`
  (111 checks) to cover the new architecture.

### Changed
- Bumped version to 1.1.0 across `pyproject.toml`, `__init__.py`, `progression.json`.
- Public API now exports the Phase 6 agent architecture classes.
- `PROJECT-DEVELOPMENT-PHASE-TRACKING.md` documents Phase 6 (7 phases total).

### Fixed
- `gaming_tweaks.config` now skips `_`-prefixed comment/metadata keys in config
  files so profiles may carry human comments.

## [1.0.0] — 2026-07-11

 — 2026-07-11

### Added
- Complete 5-sub-skill harness architecture for gaming OS/hardware tweaking
- **System Profiler** (`src/gaming_tweaks/system_profiler.py`)
  - Cross-platform hardware detection (Windows + Linux)
  - CPU, GPU, RAM, storage, display, peripheral, and OS profiling
  - JSON serialization with profile caching (1-hour TTL)
- **Tweak Recommender** (`src/gaming_tweaks/tweak_recommender.py`)
  - Evidence-backed recommendations with 4-tier evidence hierarchy
  - Risk assessment (Low/Medium/High/Critical) with tolerance filters
  - Multi-scenario analysis (best/base/worst case)
  - Preset profiles: `minimal_latency` and `balanced_gaming`
  - FPS gain and latency reduction estimates
- **Config Manager** (`src/gaming_tweaks/config_manager.py`)
  - Profile CRUD with validation and rollback
  - Backup system with automatic cleanup
  - Profile diffing between configurations
  - 8 categorized tweak categories
- **Benchmark Validator** (`src/gaming_tweaks/benchmark_validator.py`)
  - Frame time analysis with percentile calculations
  - FPS statistics (avg, 1% lows, 0.1% lows, stability score)
  - Composite scoring with S-F grade assignment
  - Benchmark comparison with automated verdicts
- **Logging Setup** (`src/gaming_tweaks/logging_setup.py`)
  - Rotating file handlers with error separation
  - JSON and console format options
  - OperationContext for performance tracking
- **CLI Entry Points**: `gaming-tweaks-profile`, `gaming-tweaks-recommend`, `gaming-tweaks-benchmark`, `gaming-tweaks-update-kb`
- **Knowledge Updater** (enhanced from v0)
  - Parallel fetch from ArXiv, Semantic Scholar, CORE.ac.uk
  - Rate limiting with jitter
  - SHA256 deduplication with title dedup
  - Configurable scoring weights with source authority
  - JSON update log with audit trail
- **CI/CD Pipeline** (`.github/workflows/ci.yml`, `release.yml`)
  - Multi-platform testing (Ubuntu + Windows)
  - Python 3.9-3.12 matrix
  - Linting (ruff), typechecking (mypy), security (bandit)
  - PyPI publishing with GitHub releases
- **Comprehensive Test Suite** (16+ test classes)
  - Unit tests for all production modules
  - Knowledge updater validation (13 checks)
  - Project structure validation
  - Benchmark validator with round-trip tests
- **Open-source Documentation**
  - README with badges, installation, usage
  - CONTRIBUTING.md with development guide
  - CODE_OF_CONDUCT.md
  - LICENSE (MIT)
  - CHANGELOG.md (this file)
- **Project Infrastructure**
  - `pyproject.toml` with full metadata, classifiers, scripts
  - `progression.json` tracking all phases
  - Enhanced `requirements.txt` with platform-specific deps
  - Production `validate_project.py` with 70+ checks

### Changed
- Enhanced `knowledge_updater.py` with concurrent fetching, configurable scoring
- Expanded `SECOND-KNOWLEDGE-BRAIN.md` with 4+ DOI-cited references
- Updated `CLAUDE.md` with production-ready status for all phases
- Enhanced `test_knowledge_updater.py` with 13 test cases
- Improved all sub-skill markdown files with production-grade depth

### Fixed
- Cross-file reference consistency across all documentation
- Missing LICENSE file (now included)
- Missing `validate_project.py` (now implemented with 70+ checks)
- Missing `progression.json` (now tracking all phases)
