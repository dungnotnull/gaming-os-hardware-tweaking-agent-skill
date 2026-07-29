# ADR-002: 4-tier evidence hierarchy for recommendation quality

**Status:** Accepted
**Date:** 2026-07-11

## Context

Tweak recommendations need quality grading so users can distinguish between
well-established best practices and experimental suggestions. Without a tier
system, a vendor blog post carries the same weight as a peer-reviewed paper.

## Decision

Use a 4-tier evidence hierarchy with source-specific authority weights:

| Tier | Description | Examples | Weight |
|------|-------------|----------|--------|
| 1 | Systematic review / meta-analysis / official standard | NVIDIA Reflex SDK doc, VESA Adaptive-Sync spec | 0.9 |
| 2 | Peer-reviewed academic paper / RCT | MacKenzie & Ware (1993), CHI | 0.65 |
| 3 | Industry report / professional guideline | Microsoft WDDM docs, Blur Busters guides | 0.5 |
| 4 | News / blog / vendor material | Community benchmarks, RSS feeds | 0.2 |

The tier is displayed on every recommendation as `evidence_tier: 1-4` with the
source name. Recommendations without cited sources are blocked by quality gate U6.

## Options Considered

1. **No tier system** — All sources treated equally
   - Pro: Simpler
   - Con: Misleading — users can't distinguish quality
2. **3-tier (High/Medium/Low)** — Fewer gradations
   - Pro: Simpler
   - Con: Loses distinction between meta-analysis and single study
3. **4-tier with source authority weights** — Chosen
   - Pro: Research-grade precision, machine-usable weights
   - Con: Requires curation of tier assignments

## Consequences

- Every TweakRecommendation carries `evidence_tier` and `evidence_source`
- Source authority weights feed into knowledge updater composite scoring
- Quality gate U3 enforces tier annotation on all sources
- Knowledge entries in SECOND-KNOWLEDGE-BRAIN.md tagged with Tier labels
