# Contributing to gaming-os-hardware-tweaking

Thank you for your interest in contributing! This document outlines the process for contributing to this project.

## Development Setup

```bash
git clone https://github.com/example/gaming-os-hardware-tweaking.git
cd gaming-os-hardware-tweaking
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Project Structure

```
gaming-os-hardware-tweaking/
├── src/gaming_tweaks/     # Production package
│   ├── __init__.py
│   ├── system_profiler.py      # Hardware/OS detection
│   ├── tweak_recommender.py     # Recommendation engine
│   ├── config_manager.py        # Profile management
│   ├── benchmark_validator.py   # Performance validation
│   ├── logging_setup.py         # Logging infrastructure
│   └── cli.py                   # CLI entry points
├── skills/                # Claude Code skill definitions
├── tools/                 # Supporting Python tools
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_system_profiler.py -v

# Run with coverage
pytest tests/ --cov=src/gaming_tweaks --cov-report=html

# Run knowledge updater tests
python tools/test_knowledge_updater.py

# Run project validation
python tools/validate_project.py --verbose
```

## Code Quality

Before submitting a PR, please ensure:

```bash
# Lint
ruff check src/ tests/ tools/

# Type check
mypy src/

# Run tests
pytest tests/ -v

# Run project validation
python tools/validate_project.py
```

## Pull Request Process

1. Fork the repository and create a feature branch
2. Add tests for any new functionality
3. Ensure all existing tests pass
4. Update documentation if needed
5. Submit a PR with a clear description

## Commit Convention

We follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Test changes
- `refactor:` Code restructuring
- `chore:` Build/tooling changes

## Evidence Requirements

This project follows evidence-backed methodology:
- All recommendations must cite authoritative sources
- Use the 4-tier evidence hierarchy (Tier 1-4)
- Tier 1: Systematic reviews, meta-analyses, official standards
- Tier 2: Peer-reviewed academic papers
- Tier 3: Industry reports, professional guidelines
- Tier 4: News, blogs, vendor documentation

## Adding New Tweak Categories

1. Add category to `TWEAK_CATEGORIES` in `src/gaming_tweaks/config_manager.py`
2. Add knowledge entries in `TweakRecommender._knowledge_base`
3. Add recommendation evaluation logic in `TweakRecommender._evaluate_tweak`
4. Add tests in `tests/test_tweak_recommender.py`

## Creative Comments

**Ai, còn nhớ lần tôi tweak con PC đầu tiên, ép từng ms latency, canh từng frame time... Đây là skill dành cho những ai hiểu rằng 10ms cũng đủ thay đổi kết quả một round đấu.**

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
