# /config — Type-Safe Configuration

Type-safe configuration profiles for the harness, loaded by
`gaming_tweaks.config.ConfigLoader`.

## Files

| File | Purpose |
|------|---------|
| `default.json` | Production profile (canonical defaults). |
| `development.json` | Development profile (verbose, lower budgets). |
| `test.json` | Test profile (deterministic, no I/O). |

## Precedence

Defaults (dataclass defaults) → JSON file → environment variables (highest).

Env var convention: `GAMING_TWEAKS_<SECTION>__<KEY>` (sections: `llm`,
`flags`, `knowledge`, `logging`, `orchestration`) and `GAMING_TWEAKS_<TOP>`
for top-level fields (`environment`, `debug`, `version`, …).

## Schema

See `assets/schemas/app_config.schema.json` for the canonical JSON-Schema.

## Usage

```python
from gaming_tweaks.config import load_config
cfg = load_config("config/default.json")          # production
cfg = load_config("config/test.json")             # tests
cfg = load_config()                                # defaults + env only
```
