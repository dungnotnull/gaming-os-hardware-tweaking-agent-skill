# CONTEXT.md — gaming-os-hardware-tweaking Domain Model

> **Purpose:** Shared understanding of the Gaming System Optimization domain.
> This is the canonical glossary for this project. Every sub-skill, Python tool,
> and test uses these definitions.
>
> **Status:** Living document — updated as the domain model evolves.
> **Last Updated:** 2026-07-11

---

## Domain: Gaming System Optimization & Input Latency Tuning

### Bounded Context

This project operates within **one bounded context**: end-user gaming performance
optimization through OS and hardware configuration. It does NOT cover:
- Game engine optimization (render pipeline internals, asset streaming)
- Network latency (server-side tick rate, netcode)
- Hardware overclocking (voltage, thermal limits beyond spec)
- Cheating/exploit detection bypass

### Core Entities

| Entity | Definition | Properties |
|--------|-----------|------------|
| **HardwareProfile** | Snapshot of a system's gaming-relevant hardware and OS state | CPU, GPU, RAM, storage, display, peripherals, OS |
| **TweakPlan** | Prioritized set of configuration changes with evidence and risk | Recommendations, risk level, FPS/latency estimates, scenarios |
| **TweakRecommendation** | Single configuration change with impact/risk/evidence | Category, key, current→recommended value, evidence tier, source |
| **ConfigProfile** | Serializable snapshot of applied tweaks | Name, version, tweak map, metadata, parent lineage |
| **BenchmarkResult** | Structured performance measurement | FPS stats, frame times, latency, grades |
| **KnowledgeEntry** | Academic/professional reference in the knowledge base | Title, DOI/URL, tier, score, source |

### Value Objects

| Value | Definition |
|-------|-----------|
| **FrameTime** | Milliseconds per rendered frame (lower = better); inverse of FPS |
| **InputLatency** | End-to-end delay from input event to pixel response (ms) |
| **InputLatencyPipeline** | USB polling → CPU queue → render queue → GPU render → display scanout |
| **StabilityScore** | 0-100 measure of frame pacing consistency (100 = perfectly consistent) |
| **EvidenceTier** | 1-4 hierarchy: Tier 1 (meta-analysis/standard) → Tier 4 (blog/vendor) |
| **RiskLevel** | Low / Medium / High / Critical |
| **DegradationLevel** | 0-4: 0 (full data) → 4 (all sources failed) |

### Tweak Categories

```
input_latency       → Reflex, pre-rendered frames, vsync, polling rate
cpu_gpu_scheduling  → Game Mode, power plan, HAGS, core affinity, process priority
memory_storage      → XMP/DOCP, NVMe optimization, paging, shader cache
display             → VRR (G-Sync/FreeSync), BFI, refresh rate, FPS cap
network             → Nagle, buffer sizes, QoS (future)
power               → Core parking, C-states, PCIe power management
background_services → Game Bar, print spooler, Windows Update, startup items
driver_settings     → Shader cache, texture filtering, power management mode
```

---

## Key Processes

### Harness Execution Flow
```
User Query → [1] Requirements → [2] Evidence Collection → [3] Core Analysis
                                                              ↓
User ← [6] Quality Gate ← [5] Advisory Synthesis ← [4] Knowledge Query
```

### Knowledge Update Cycle
```
Weekly Cron → ArXiv + Semantic Scholar + CORE.ac.uk + RSS feeds
    → Parallel fetch with rate limiting
    → SHA256 dedup (DOI + URL + title)
    → Composite scoring (recency 0.35 + relevance 0.35 + citations 0.15 + authority 0.15)
    → Append top-N to SECOND-KNOWLEDGE-BRAIN.md Section 7
    → Update JSON audit log
```

### Benchmark Validation Pipeline
```
Raw frame times → FrameTimeStats (min/max/avg/median/p99/p999/std/stutters)
                → FPSStats (avg/min/max/1%low/0.1%low/stability)
                → LatencyStats (avg/min/max/p95/p99)
                → Composite Score (weighted: FPS 40% + stability 25% + consistency 15%
                                      + frame time 10% - stutters + latency 10%)
                → Grade (S/A/B/C/D/F)
```

---

## Invariants

1. **No claim without evidence.** Every recommendation cites a source with Tier label.
2. **Disclosure before conclusion.** Risk/limitation notice precedes the verdict.
3. **Source freshness.** Live sources preferred; knowledge base fallback flagged.
4. **Serializability.** All data structures support `to_dict`/`from_dict` roundtrip.
5. **Dedup by SHA256.** Knowledge entries deduplicated by DOI/URL/content hash.
6. **Rollback safety.** Config changes backed up before overwrite.
7. **Language respect.** Output language matches user's detected language.
8. **No fabrication.** Missing/unavailable data flagged as "DATA UNAVAILABLE", never invented.

---

## References

- `SECOND-KNOWLEDGE-BRAIN.md` — Living knowledge base
- `PROJECT-detail.md` — Technical architecture
- `skills/main.md` — Harness execution protocol
- `.commandcode/taste/` — Learned preferences
