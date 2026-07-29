# CLAUDE.md — Skill 204: gaming-os-hardware-tweaking

## Skill Identity
- **Skill Name:** `gaming-os-hardware-tweaking`
- **Tagline:** OS & Hardware Tweaking for Gamers (Low Latency & High FPS) — Gaming System Optimization & Input Latency Tuning analysis & decision-support harness.
- **Current Phase:** Phase 5 — Integration & Polish (COMPLETE)
- **Folder:** `D:\972026\204-gaming-os-hardware-tweaking\`
- **Version:** 1.0.0 — PRODUCTION READY

---

## Problem This Skill Solves

This skill provides a structured, evidence-backed analytical workflow for
**Gaming System Optimization & Input Latency Tuning**. It gathers authoritative real-time and reference data, applies
recognized domain methods, cross-references academic research, and delivers
actionable outputs that are fully evidenced, risk/limitation-disclosed, and
traceable to authoritative sources — continuously self-improving through an
automated knowledge crawl pipeline.

---

## Harness Flow Summary

```
/gaming-os-hardware-tweaking invoked
│
├─ Step 1: sub-gather-requirements   → Clarify the object of analysis, constraints, timeframe, available inputs, target audience, and language before any data fetching.
├─ Step 2: sub-evidence-collector   → Fetch authoritative real-time and reference data for the object: current status/parameters, authoritative documents/standards, and recent developments from domain and academic sources.
├─ Step 3: sub-core-analysis   → Optimize OS and hardware configuration for gamers to maximize FPS and minimize input latency, with stability-vs-gain tradeoffs.
├─ Step 4: sub-knowledge-updater   → Query SECOND-KNOWLEDGE-BRAIN.md for authoritative academic and professional evidence; surface citations with tier labels and flag gaps for the crawl pipeline.
├─ Step 5: sub-advisor   → Synthesize all prior analysis into a risk-disclosed conclusion with a full evidence chain and recommended actions.
└─ Step 6: main (quality gate)       → verify evidence hierarchy, disclosure, output polish
```

---

## Sub-Skills

| `skills/sub-gather-requirements.md` | Clarify the object of analysis, constraints, timeframe, available inputs, target audience, and language before any data fetching. |
| `skills/sub-evidence-collector.md` | Fetch authoritative real-time and reference data for the object: current status/parameters, authoritative documents/standards, and recent developments from domain and academic sources. |
| `skills/sub-core-analysis.md` | Optimize OS and hardware configuration for gamers to maximize FPS and minimize input latency, with stability-vs-gain tradeoffs. |
| `skills/sub-knowledge-updater.md` | Query SECOND-KNOWLEDGE-BRAIN.md for authoritative academic and professional evidence; surface citations with tier labels and flag gaps for the crawl pipeline. |
| `skills/sub-advisor.md` | Synthesize all prior analysis into a risk-disclosed conclusion with a full evidence chain and recommended actions. |

---

## Tools Required

- **WebSearch** — live domain news, reports, standards updates
- **WebFetch** — scrape Gaming System Optimization & Input Latency Tuning authoritative sources
- **Read / Write** — read SECOND-KNOWLEDGE-BRAIN.md; append knowledge entries
- **Bash** — run `tools/knowledge_updater.py` for periodic crawl
- **Skill** — invoke sub-skills sequentially through the harness

---

## Knowledge Sources

### Domain Authoritative Sources
- NVIDIA Reflex & driver docs
- Microsoft Game Mode / WDDM docs
- Mouse/keyboard polling docs
- Display docs (VRR, BFI, refresh)
- Blur Busters (latency references)
- Game/DRM performance references
- CPU/GPU scheduling references

### Academic & Research Sources
- IEEE Transactions on Visualization & Computer Graphics
- ACM CHI (latency research)
- Computers in Human Behavior — Elsevier
- Entertainment Computing — Elsevier
- Performance Evaluation — Elsevier
- Journal of Network and Computer Applications

### Academic Crawl Targets
- Semantic Scholar / Google Scholar for "Gaming System Optimization & Input Latency Tuning" keyword clusters
- ArXiv categories: cs.HC, cs.GR, cs.PF, cs.OS
- CORE.ac.uk open access repository

---

## Supporting Python Tools

| File | Purpose |
|------|---------|
| `tools/knowledge_updater.py` | Crawl pipeline: fetches latest papers + news → appends to SECOND-KNOWLEDGE-BRAIN.md |
| `tools/test_knowledge_updater.py` | Unit tests for knowledge updater (13 checks) |
| `tools/run_test_scenarios.py` | Structural & content validator (84 checks) |
| `tools/validate_project.py` | Production-grade project validator (139 checks) |
| `src/gaming_tweaks/system_profiler.py` | Cross-platform hardware/OS detection |
| `src/gaming_tweaks/tweak_recommender.py` | Evidence-backed optimization engine |
| `src/gaming_tweaks/config_manager.py` | Profile management with backup/rollback |
| `src/gaming_tweaks/benchmark_validator.py` | Performance benchmark analysis |
| `src/gaming_tweaks/cli.py` | CLI entry points (profile, recommend, benchmark, update-kb) |

---

## Automated Knowledge Update Schedule

```cron
# Weekly academic update (Mondays 8:00 AM)
0 8 * * 1 python D:/972026/204-gaming-os-hardware-tweaking/tools/knowledge_updater.py >> logs/knowledge_update.log 2>&1

# Daily news update (Daily 7:00 AM)
0 7 * * * python D:/972026/204-gaming-os-hardware-tweaking/tools/knowledge_updater.py --news-only >> logs/knowledge_news.log 2>&1
```

Manual: `python tools/knowledge_updater.py --dry-run` | `--keywords "..."` | `--news-only` | `--academic-only`
CLI: `gaming-tweaks-update-kb --dry-run`

---

## Phase 6 — Flexible Agent & Skill Architecture

The harness was upgraded with a modular, production-grade agent & skill
architecture. New top-level directories:

| Dir | Purpose |
|-----|---------|
| `/config` | Type-safe configuration profiles (`gaming_tweaks.config`). |
| `/scripts` | Automation: setup, seeding, ingestion, architecture validation. |
| `/references` | Prompt base-templates + curated domain knowledge (RAG grounding). |
| `/assets` | JSON-Schema contracts + system architecture diagram. |

New `src/gaming_tweaks` agent modules:

| Module | Responsibility |
|--------|---------------|
| `config.py` | Type-safe `AppConfig` (defaults — file — env), validation, feature flags. |
| `hooks.py` | `HookRegistry` + 14 lifecycle events, built-in logging/metrics/state-sync/event hooks. |
| `tools.py` | `ToolRegistry` + 11 JSON-Schema-validated built-in tools, dynamic invocation. |
| `registry.py` | `SkillRegistry` — load / validate / resolve skills by name/tag/search. |
| `router.py` | Deterministic chain-of-thought `Router` (8 intents, language detection). |
| `orchestrator.py` | End-to-end `Orchestrator` (registry+router+hooks+tools+gates+state+token budget+graceful degradation). |
| `orchestrator_cli.py` | `gaming-tweaks-harness` CLI entry point. |

`SKILL.md` documents how skills are registered, resolved, executed, and
validated, with input/output JSON schemas (also published as machine-readable
contracts under `assets/schemas/`).

## Active Development Tasks

- [x] Phase 0: Architecture & source map (this file, PROJECT-detail.md, PDPT.md)
- [x] Phase 1: Core sub-skills (production-grade)
- [x] Phase 2: Main harness + quality gates + degradation
- [x] Phase 3: Knowledge pipeline + tests + cron
- [x] Phase 4: Testing & validation (all validators pass)
- [x] Phase 5: Integration & polish (PRODUCTION READY v1.0.0)
- [x] Phase 6: Flexible agent & skill architecture (PRODUCTION READY v1.1.0)

---

## References

- `PROJECT-detail.md` — full technical specification
- `PROJECT-DEVELOPMENT-PHASE-TRACKING.md` — build roadmap
- `SECOND-KNOWLEDGE-BRAIN.md` — self-improving knowledge base
- `D:\972026\SKILL-STANDARD.md` — library-wide standard
- Reference impl: `D:\vn-finance-analysis-hd-skill`
