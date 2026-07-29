"""
validate_architecture.py — Validate the Phase 6 agent/skill architecture.

Checks that the new modular directories exist with expected contents, that the
new src modules import and pass structural checks, that config profiles load,
that JSON schemas parse, and that the orchestrator can run end-to-end offline.

Usage:
    python scripts/validate_architecture.py [--verbose]
Exit 0 = pass, non-zero = fail.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class Report:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def check(self, cond: bool, label: str, detail: str = "") -> None:
        if cond:
            self.passed += 1
            if self.verbose:
                print(f"  [PASS] {label}")
        else:
            self.failed += 1
            self.errors.append(f"{label}: {detail}")
            print(f"  [FAIL] {label}: {detail}")

    def summary(self) -> int:
        print(f"\n[validate-arch] {self.passed} passed, {self.failed} failed")
        if self.errors:
            for e in self.errors:
                print(f"  - {e}")
        return 0 if self.failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    r = Report(verbose=args.verbose)

    # Directories
    for d in ["config", "scripts", "references", "assets", "skills"]:
        r.check((ROOT / d).is_dir(), f"dir exists: {d}")
    for d in ["references/prompts", "references/domain", "assets/schemas", "assets/diagrams"]:
        r.check((ROOT / d).is_dir(), f"subdir exists: {d}")

    # SKILL.md
    r.check((ROOT / "SKILL.md").exists(), "SKILL.md exists")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for token in ["Skill Registry", "Router", "Tool System", "Quality Gates", "Hooks"]:
        r.check(token in skill, f"SKILL.md mentions {token}")

    # Config profiles load
    from gaming_tweaks.config import load_config, ConfigValidationError
    for prof in ["config/default.json", "config/development.json", "config/test.json"]:
        try:
            cfg = load_config(ROOT / prof)
            r.check(cfg.environment in {"production", "development", "test"},
                    f"config loads: {prof}")
        except ConfigValidationError as exc:
            r.check(False, f"config loads: {prof}", str(exc))

    # JSON schemas parse
    for sch in (ROOT / "assets/schemas").glob("*.json"):
        try:
            json.loads(sch.read_text(encoding="utf-8"))
            r.check(True, f"schema parses: {sch.name}")
        except json.JSONDecodeError as exc:
            r.check(False, f"schema parses: {sch.name}", str(exc))

    # New modules import
    for mod in ["config", "hooks", "tools", "registry", "router", "orchestrator"]:
        try:
            __import__(f"gaming_tweaks.{mod}")
            r.check(True, f"import: gaming_tweaks.{mod}")
        except Exception as exc:  # noqa: BLE001
            r.check(False, f"import: gaming_tweaks.{mod}", str(exc))

    # Registry loads skills
    from gaming_tweaks.registry import SkillRegistry
    try:
        reg = SkillRegistry(skills_dir=ROOT / "skills")
        reg.load(strict=True)
        names = reg.list_skills()
        r.check(len(names) >= 5, "registry loads 5+ skills", f"got {len(names)}")
        r.check("sub-advisor" in names, "registry has sub-advisor")
    except Exception as exc:  # noqa: BLE001
        r.check(False, "registry loads", str(exc))

    # Tool registry has built-ins
    from gaming_tweaks.tools import default_registry
    try:
        tr = default_registry()
        names = tr.list_tools()
        r.check("profile_system" in names, "tools: profile_system")
        r.check("query_knowledge_brain" in names, "tools: query_knowledge_brain")
        r.check("detect_language" in names, "tools: detect_language")
    except Exception as exc:  # noqa: BLE001
        r.check(False, "tool registry", str(exc))

    # Router produces a plan
    from gaming_tweaks.router import Router
    try:
        plan = Router(reg).route("optimize latency for my system")
        r.check(len(plan.skills) >= 1, "router produces plan")
        r.check(plan.language in {"en", "vi"}, "router detects language")
        r.check(len(plan.reasoning) >= 1, "router emits reasoning")
    except Exception as exc:  # noqa: BLE001
        r.check(False, "router route", str(exc))

    # Orchestrator runs offline end-to-end
    from gaming_tweaks.orchestrator import Orchestrator
    try:
        o = Orchestrator(registry=reg)
        result = o.run("compare competitive vs casual latency tuning")
        r.check(result.run_id, "orchestrator returns run_id")
        r.check(len(result.steps) >= 1, "orchestrator executes steps",
                f"got {len(result.steps)}")
        r.check(len(result.gates) >= 10, "orchestrator runs 10 gates",
                f"got {len(result.gates)}")
        r.check(isinstance(result.token_usage, dict), "orchestrator reports tokens")
    except Exception as exc:  # noqa: BLE001
        r.check(False, "orchestrator run", str(exc))

    return r.summary()


if __name__ == "__main__":
    sys.exit(main())
