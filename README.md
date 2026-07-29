# gaming-os-hardware-tweaking

**OS & Hardware Tweaking for Gamers (Low Latency & High FPS)**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI version](https://img.shields.io/badge/pypi-v1.1.0-blue.svg)](https://pypi.org/project/gaming-os-hardware-tweaking/)

A production-grade, open-source Claude Code harness and Python toolkit for **Gaming System Optimization & Input Latency Tuning** — gathers real-time authoritative data, applies recognized domain methods, integrates academic research, and delivers evidence-backed, risk-disclosed outputs.

## Features

### 🤖 Claude Code Agent Harness
- Real-time data aggregation from authoritative Gaming System Optimization & Input Latency Tuning sources
- Systematic domain analysis methods with 5 specialized sub-skills
- Academic research integration with auto-updating knowledge base
- Risk/limitation-disclosed outputs with scenario coverage
- Self-improving knowledge pipeline (weekly academic + daily news crawl)
- Vietnamese/English dual-language support

### 🛠 Production Python Toolkit
- **System Profiler** — Cross-platform hardware detection (CPU, GPU, RAM, storage, display, peripherals, OS)
- **Tweak Recommender** — Evidence-backed optimization engine with 4-tier evidence hierarchy and risk assessment
- **Config Manager** — Profile management with validation, backup, diff, and rollback
- **Benchmark Validator** — Frame time analysis, FPS statistics, composite scoring (S-F grades), comparison
- **Knowledge Updater** — Parallel academic crawl (ArXiv, Semantic Scholar, CORE.ac.uk, RSS) with deduplication
- **CLI Tools** — `gaming-tweaks-profile`, `gaming-tweaks-recommend`, `gaming-tweaks-benchmark`, `gaming-tweaks-update-kb`
- **Structured Logging** — Rotating file handlers, JSON format, operation context tracking

## Installation

```bash
# From PyPI
pip install gaming-os-hardware-tweaking

# From source (development)
git clone https://github.com/example/gaming-os-hardware-tweaking.git
cd gaming-os-hardware-tweaking
pip install -e ".[dev]"

# Minimal install
pip install -r requirements.txt
```

Install skill files to `~/.claude/skills/` or use via project CLAUDE.md.

## Quick Start / Usage

### Command Line

```bash
# Profile your system
gaming-tweaks-profile

# Get tweak recommendations
gaming-tweaks-recommend --style competitive --risk moderate

# Validate benchmarks
gaming-tweaks-benchmark --input benchmark.json --compare baseline.json

# Update knowledge base
gaming-tweaks-update-kb --dry-run
```

### Python API

```python
from gaming_tweaks import SystemProfiler, TweakRecommender, BenchmarkValidator

# Profile hardware
profiler = SystemProfiler()
hardware = profiler.profile()
print(f"CPU: {hardware.cpu.model} | GPU: {hardware.gpu.model}")

# Get recommendations
recommender = TweakRecommender()
plan = recommender.analyze(hardware, target_style="competitive")
for r in plan.recommendations:
    print(f"  {r.key}: {r.current_value} → {r.recommended_value} [{r.impact}, {r.risk}]")

# Validate benchmarks
validator = BenchmarkValidator()
baseline = validator.create_result("baseline", frame_times_ms=[16.67]*100)
optimized = validator.create_result("optimized", frame_times_ms=[8.33]*100)
comparison = validator.compare_results(baseline, optimized)
print(f"Verdict: {comparison['verdict']}")
```

### Agent Harness (Phase 6)

```bash
# Run the harness offline (assembles prompts + gathers evidence; no LLM needed)
gaming-tweaks-harness "optimize latency for competitive play" --skills-dir skills

# Full machine-readable result
gaming-tweaks-harness "compare competitive vs casual" --json > result.json
```

### Claude Code

```bash
/gaming-os-hardware-tweaking Analyze my system for CS2 competitive play
```

## Architecture

```
USER INPUT
    │
    ▼
[main.md — gaming-os-hardware-tweaking]
    │
    ├─► sub-gather-requirements  → Structured requirements
    ├─► sub-evidence-collector   → Real-time data bundle
    ├─► sub-core-analysis        → OS/hardware optimization
    ├─► sub-knowledge-updater    → Academic evidence citations
    └─► sub-advisor              → Risk-disclosed conclusion
         │
         └─► [QUALITY GATES: U1-U6 + G1-G4]
```

See `PROJECT-detail.md` for the full architecture diagram.

## Quality Gates

Universal gates U1–U6 plus domain gates G1-G4 defined in `skills/main.md`.

| Gate | Check | Auto-Fix |
|------|-------|----------|
| U1 | ≥3 sources cited, ≥1 academic | Fetch missing |
| U2 | Disclosure before recommendation | Prepend standard |
| U3 | Evidence hierarchy stated | Annotate tiers |
| U4 | Language matches preference | Translate |
| U5 | Output uses template | Reformat |
| U6 | Claims traceable to source | Flag unsupported |
| G1 | Input latency config stated | State config |
| G2 | CPU/GPU scheduling tuned | Tune scheduling |
| G3 | Monitoring metrics defined | Define monitoring |
| G4 | Stability-vs-gain tradeoffs noted | Note tradeoffs |

## Data Sources

- NVIDIA Reflex & driver docs  
- Microsoft Game Mode / WDDM docs  
- Mouse/keyboard polling docs  
- Display docs (VRR, BFI, refresh)  
- Blur Busters (latency references)  
- Game/DRM performance references  
- CPU/GPU scheduling references  
- IEEE TVCG, ACM CHI, Elsevier journals  

## Testing

```bash
# Full test suite
pytest tests/ -v

# Knowledge updater
python tools/test_knowledge_updater.py

# Project validation
python tools/validate_project.py --verbose
```

## Knowledge Base

`SECOND-KNOWLEDGE-BRAIN.md` is auto-updated weekly via `tools/knowledge_updater.py`.

## Roadmap

- [x] Phase 0: Architecture  
- [x] Phase 1: Core sub-skills  
- [x] Phase 2: Main harness + gates  
- [x] Phase 3: Knowledge pipeline  
- [x] Phase 4: Testing  
- [x] Phase 5: Integration & polish — PRODUCTION READY v1.0.0  

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT — see [LICENSE](LICENSE).

## Citation

```bibtex
@software{gaming-os-hardware-tweaking,
  title = {gaming-os-hardware-tweaking: OS & Hardware Tweaking for Gamers (Low Latency & High FPS)},
  year = {2026},
  version = {1.1.0}
}
```
