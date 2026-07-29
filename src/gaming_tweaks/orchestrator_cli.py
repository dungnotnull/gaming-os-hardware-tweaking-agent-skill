"""
orchestrator_cli.py â€” CLI entry point for the agent harness orchestrator.

Runs the gaming-os-hardware-tweaking harness over a user query and prints the
OrchestrationResult as JSON (or a compact summary). Wires the config profile,
skill registry, router, hooks, and tools together.

Usage:
    gaming-tweaks-harness "optimize latency for competitive play" \
        [--config config/default.json] [--json] [--language en|vi]
    gaming-tweaks-harness --query-file query.txt --json > result.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "src"


def _build_orchestrator(config_path: Optional[Path], registry_dir: Path):
    sys.path.insert(0, str(SRC))
    from gaming_tweaks.config import load_config
    from gaming_tweaks.registry import SkillRegistry
    from gaming_tweaks.orchestrator import Orchestrator

    cfg = load_config(config_path) if config_path else None
    reg = SkillRegistry(skills_dir=registry_dir)
    reg.load(strict=False)
    return Orchestrator(config=cfg, registry=reg), cfg


def main_harness(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gaming-tweaks-harness",
        description="Run the gaming-os-hardware-tweaking agent harness.",
    )
    parser.add_argument("query", nargs="?", default="",
                        help="user query (omit if --query-file is given)")
    parser.add_argument("--query-file", help="path to a file holding the query")
    parser.add_argument("--config", default="config/default.json",
                        help="config profile path")
    parser.add_argument("--skills-dir", default="skills",
                        help="skills directory")
    parser.add_argument("--json", action="store_true",
                        help="emit full OrchestrationResult as JSON")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="log reasoning trace to stderr")
    args = parser.parse_args(argv)

    if args.query_file:
        query = Path(args.query_file).read_text(encoding="utf-8").strip()
    else:
        query = args.query.strip()
    if not query:
        parser.error("a query (or --query-file) is required")

    config_path = Path(args.config)
    registry_dir = Path(args.skills_dir)
    if args.verbose:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    orch, _cfg = _build_orchestrator(
        config_path if config_path.exists() else None, registry_dir
    )
    result = orch.run(query)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(f"run_id: {result.run_id}")
        print(f"ok: {result.ok}")
        print(f"intent: {result.plan.intent} | language: {result.plan.language}")
        print(f"steps: {[s.skill_name for s in result.steps]}")
        print(f"degradation: {result.degradation_level}")
        print(f"tokens: {result.token_usage}")
        print("gates:")
        for g in result.gates:
            print(f"  {g.gate}: {'PASS' if g.passed else 'FAIL'} ({g.detail})")
        if result.errors:
            print("errors:")
            for e in result.errors:
                print(f"  - {e}")
        if args.verbose:
            print("trace:")
            for t in result.trace:
                print(f"  - {t}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main_harness())
