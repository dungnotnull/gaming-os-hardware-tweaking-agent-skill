# /references — Domain Knowledge & Prompt Base-Templates

Authoritative, citable domain knowledge and reusable prompt base-templates
used for RAG grounding of the agent harness.

## Layout

```
references/
├── prompts/                # Reusable prompt base-templates
│   ├── system_base.md          # System preamble (persona + evidence discipline).
│   ├── requirements_intake.md  # sub-gather-requirements template.
│   ├── evidence_collection.md  # sub-evidence-collector template.
│   ├── core_analysis.md        # sub-core-analysis template.
│   └── advisory_synthesis.md   # sub-advisor template.
└── domain/                 # Curated, citable domain knowledge
    ├── domain_knowledge.md     # Core concepts, decision rules, tradeoff matrix.
    └── source_map.md           # Authoritative + community source map with tiers.
```

## Evidence Tiers

- **Tier 1** — peer-reviewed academic (DOI-cited).
- **Tier 2** — authoritative vendor/standards docs.
- **Tier 3** — reputable community references.
- **Tier 4** — analyst judgment / community consensus.

The knowledge brain (`SECOND-KNOWLEDGE-BRAIN.md`) is auto-updated by the crawl
pipeline (`tools/knowledge_updater.py`); this directory holds the stable,
human-curated complement.
