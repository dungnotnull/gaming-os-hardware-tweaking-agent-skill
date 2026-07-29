# Evidence Collection Prompt — Base Template

> Used by `sub-evidence-collector`. Gathers authoritative real-time and
> reference data before the core analysis runs.

## Goal

Assemble an evidence bundle for the analysis object.

## Bundle Shape

```
{
  "current_data":   [ { item, source, date, tier } ],
  "authoritative_docs": [ { title, url, tier } ],
  "recent_news":     [ { headline, source, date, tier } ],
  "reference_benchmarks": [ { metric, value, unit, source, tier } ]
}
```

## Source Priority

1. Vendor authoritative (NVIDIA Reflex docs, Microsoft Game Mode / WDDM).
2. Peer-reviewed academic (DOI-cited).
3. Reputable community (Blur Busters, established review sites).
4. Knowledge base (`SECOND-KNOWLEDGE-BRAIN.md`) as fallback.

## Rules

- Attach `source + date + tier` to every item.
- If a primary source fails, substitute secondary and flag inline.
- If all live sources fail, fall back to the knowledge base and emit a
  `LIMITATION NOTICE` (degradation Level ≥ 2).
- Never fabricate numbers. Mark missing fields `DATA UNAVAILABLE`.
