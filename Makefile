.PHONY: install test lint typecheck validate clean build help

PYTHON := python
PIP := pip

help:
	@echo "gaming-os-hardware-tweaking — Development Makefile"
	@echo ""
	@echo "  install       Install in development mode with all extras"
	@echo "  test          Run full test suite"
	@echo "  test-quick    Run tests excluding system profiler"
	@echo "  lint          Run ruff linter"
	@echo "  lint-fix      Run ruff linter with auto-fix"
	@echo "  typecheck     Run mypy type checker"
	@echo "  validate      Run all project validation"
	@echo "  validate-all  Run validate_project + scenarios + knowledge tests"
	@echo "  security      Run bandit security scan"
	@echo "  build         Build distribution packages"
	@echo "  clean         Remove build artifacts and caches"
	@echo "  all           Run lint + typecheck + test + validate"

install:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

test-quick:
	$(PYTHON) -m pytest tests/test_benchmark_validator.py tests/test_config_manager.py tests/test_tweak_recommender.py tests/test_logging_setup.py -v --tb=short

lint:
	$(PYTHON) -m ruff check src/ tests/ tools/

lint-fix:
	$(PYTHON) -m ruff check --fix src/ tests/ tools/

typecheck:
	$(PYTHON) -m mypy src/ --ignore-missing-imports

validate:
	$(PYTHON) tools/validate_project.py

validate-all:
	$(PYTHON) tools/validate_project.py
	$(PYTHON) tools/run_test_scenarios.py
	$(PYTHON) tools/test_knowledge_updater.py

security:
	$(PYTHON) -m bandit -r src/ -c pyproject.toml -ll

build:
	$(PYTHON) -m build

clean:
	rmdir /s /q dist build *.egg-info 2>nul || true
	rmdir /s /q .pytest_cache 2>nul || true
	rmdir /s /q .mypy_cache 2>nul || true
	rmdir /s /q src\gaming_tweaks\__pycache__ 2>nul || true
	rmdir /s /q tests\__pycache__ 2>nul || true
	rmdir /s /q tools\__pycache__ 2>nul || true

all: lint typecheck test validate-all
	@echo "=== ALL CHECKS PASSED ==="
