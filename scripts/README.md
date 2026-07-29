# /scripts — Automation, Seeding, Ingestion & Validation

Production-grade automation routines for the gaming-os-hardware-tweaking
harness. All scripts are idempotent and safe to re-run.

## Scripts

| Script | Purpose |
|--------|---------|
| `setup_env.py` | Validate Python, create runtime dirs, ensure config, install deps, smoke-test imports. |
| `seed_knowledge.py` | Idempotently seed SECOND-KNOWLEDGE-BRAIN.md with curated baseline entries (SHA-256 dedup). |
| `ingest_knowledge.py` | One-shot ingest of an external knowledge dump into the brain with keyword scoring. |
| `validate_architecture.py` | Validate the Phase 6 agent/skill architecture end-to-end (dirs, config, schemas, registry, router, orchestrator). |

## Usage

```bash
python scripts/setup_env.py --check-only
python scripts/seed_knowledge.py --dry-run
python scripts/ingest_knowledge.py --input refs/dump.md --keywords "latency,reflex,vrr" --dry-run
python scripts/validate_architecture.py --verbose
```

## Notes

- No Git operations are performed.
- No model training or model pulling is performed.
- All scripts write UTF-8 (no BOM) and append-only to the knowledge brain.
