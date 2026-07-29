# ADR-003: Multi-source academic crawl with composite scoring

**Status:** Accepted
**Date:** 2026-07-11

## Context

The SECOND-KNOWLEDGE-BRAIN needs continuous updates from academic and
professional sources. A single-source approach (e.g., only ArXiv) misses
peer-reviewed papers, industry reports, and community research.

## Decision

Implement a multi-source parallel crawl pipeline fetching from:
- **ArXiv** (cs.HC, cs.GR, cs.PF, cs.OS) — preprints
- **Semantic Scholar** — peer-reviewed papers with citation counts
- **CORE.ac.uk** — open access repository (optional, API key required)
- **RSS feeds** — Blur Busters, NVIDIA GeForce news

Scoring: composite 0-10 using weighted sum:
- Recency (0.35): Days since publication, linear decay over 730 days
- Keyword relevance (0.35): Fraction of config keywords matched in title+abstract+venue
- Citation count (0.15): Log-scaled, normalized to 1000 citations
- Source authority (0.15): Per-source weight from ADR-002 tiers

## Options Considered

1. **ArXiv only** — Single source
   - Pro: Simple, no API rate limits to manage
   - Con: Misses peer-reviewed papers, no citation data
2. **Manual curation** — Hand-picked entries
   - Pro: Highest quality control
   - Con: Doesn't scale, no automation
3. **Multi-source parallel crawl** — Chosen
   - Pro: Comprehensive coverage, citation-aware scoring
   - Con: Multiple API integrations, rate limiting complexity

## Consequences

- ThreadPoolExecutor for parallel fetching with per-thread sessions
- Rate limiting with jitter (configurable base delay)
- SHA256 dedup by DOI/URL and by title (separate hash sets)
- JSON audit log tracks every update run
- Cache with configurable TTL (default 24h)
- Cron schedule: weekly academic + daily news
