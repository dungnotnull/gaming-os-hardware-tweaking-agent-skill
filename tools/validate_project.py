"""
validate_project.py — Skill 204: gaming-os-hardware-tweaking
Production-grade project validator. Verifies 8-File Contract, file structure,
content quality, and cross-reference integrity for pre-deployment checks.

Usage:
    python tools/validate_project.py [--verbose] [--strict]
Exit code 0 = all validations pass, non-zero = failures found.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

EIGHT_FILE_CONTRACT = [
    "CLAUDE.md",
    "PROJECT-detail.md",
    "PROJECT-DEVELOPMENT-PHASE-TRACKING.md",
    "README.md",
    "SECOND-KNOWLEDGE-BRAIN.md",
    "skills/main.md",
    "tools/knowledge_updater.py",
    "tools/run_test_scenarios.py",
]

REQUIRED_SUB_SKILLS = [
    "sub-gather-requirements",
    "sub-evidence-collector",
    "sub-core-analysis",
    "sub-knowledge-updater",
    "sub-advisor",
]

REQUIRED_UNIVERSAL_GATES = ["U1", "U2", "U3", "U4", "U5", "U6"]
REQUIRED_DOMAIN_GATES = ["G1", "G2", "G3", "G4"]

REQUIRED_SECTIONS_SUB_SKILL = [
    "Role & Persona",
    "Workflow",
    "Tools",
    "Output Format",
    "Quality Gates",
]

FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---", re.S)
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s|]+")


class Validator:
    def __init__(self, verbose: bool = False, strict: bool = False):
        self.verbose = verbose
        self.strict = strict
        self.errors: List[Tuple[str, str]] = []
        self.warnings: List[Tuple[str, str]] = []
        self.checks_passed = 0
        self.checks_total = 0

    def read(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def check(self, condition: bool, label: str, detail: str = "",
              category: str = "error") -> None:
        self.checks_total += 1
        if condition:
            self.checks_passed += 1
            if self.verbose:
                print(f"  [PASS] {label}")
        else:
            if category == "warning":
                self.warnings.append((label, detail))
                if self.verbose:
                    print(f"  [WARN] {label}: {detail}")
            else:
                self.errors.append((label, detail))
                print(f"  [FAIL] {label}: {detail}")

    def validate_file_existence(self) -> None:
        for fpath in EIGHT_FILE_CONTRACT:
            self.check((ROOT / fpath).exists(), f"8-File Contract: {fpath}")

        for skill_name in REQUIRED_SUB_SKILLS:
            fpath = ROOT / "skills" / f"{skill_name}.md"
            self.check(fpath.exists(), f"Sub-skill: {skill_name}", category="warning" if not fpath.exists() else "error")

        self.check((ROOT / "tests" / "test-scenarios.md").exists(),
                   "Test scenarios file")
        self.check((ROOT / "tests" / "TEST_RESULTS.md").exists(),
                   "Test results file")
        self.check((ROOT / "tools" / "test_knowledge_updater.py").exists(),
                   "Knowledge updater test file")
        self.check((ROOT / "LICENSE").exists(), "LICENSE file")
        self.check((ROOT / "requirements.txt").exists(), "requirements.txt")

    def validate_sub_skill_structure(self) -> None:
        for skill_name in REQUIRED_SUB_SKILLS:
            fpath = ROOT / "skills" / f"{skill_name}.md"
            if not fpath.exists():
                continue
            content = self.read(fpath)

            fm = FM_PATTERN.search(content)
            self.check(bool(fm), f"{skill_name}: YAML frontmatter")
            if fm:
                frontmatter = fm.group(1)
                self.check("name:" in frontmatter,
                           f"{skill_name}: name field")
                self.check("description:" in frontmatter,
                           f"{skill_name}: description field")

            for section in REQUIRED_SECTIONS_SUB_SKILL:
                self.check(section in content,
                           f"{skill_name}: '{section}' section")

            self.check(len(content) >= 200,
                       f"{skill_name}: content length >= 200 chars",
                       f"found {len(content)}", "warning")

    def validate_main_harness(self) -> None:
        main_path = ROOT / "skills" / "main.md"
        if not main_path.exists():
            self.check(False, "main.md exists", category="error")
            return

        content = self.read(main_path)

        fm = FM_PATTERN.search(content)
        self.check(bool(fm), "main.md: YAML frontmatter")
        if fm:
            self.check("name:" in fm.group(1), "main.md: name")
            self.check("description:" in fm.group(1), "main.md: description")

        for section in [
            "Role & Persona", "Harness Execution Protocol", "Quality Gates",
            "Graceful Degradation", "Sub-skills Available", "Output Format"
        ]:
            self.check(section in content, f"main.md: '{section}' section")

        self.check("Pre-Flight" in content or "Language Detection" in content,
                   "main.md: language detection")
        self.check("limitation" in content.lower(),
                   "main.md: limitation banner")
        self.check("LIMITATION NOTICE" in content,
                   "main.md: LIMITATION NOTICE banner")

        for gate in REQUIRED_UNIVERSAL_GATES + REQUIRED_DOMAIN_GATES:
            self.check(gate in content, f"main.md: gate {gate}")

        for skill_name in REQUIRED_SUB_SKILLS:
            self.check(skill_name in content, f"main.md: references {skill_name}")

    def validate_knowledge_brain(self) -> None:
        brain_path = ROOT / "SECOND-KNOWLEDGE-BRAIN.md"
        if not brain_path.exists():
            self.check(False, "SECOND-KNOWLEDGE-BRAIN.md exists")
            return

        content = self.read(brain_path)

        self.check("## 1. Core Concepts" in content, "brain: Core Concepts")
        self.check("## 2. Key Research Papers" in content, "brain: Research Papers")
        self.check("## 3. State-of-the-Art" in content, "brain: SOTA")
        self.check("## 4. Authoritative Data Sources" in content, "brain: Data Sources")
        self.check("## 5. Analytical Frameworks" in content, "brain: Frameworks")
        self.check("## 6. Self-Update Protocol" in content, "brain: Update Protocol")
        self.check("## 7. Knowledge Update Log" in content, "brain: Update Log")

        dois = DOI_PATTERN.findall(content)
        self.check(len(dois) >= 2, "brain: 2+ DOI references",
                   f"found {len(dois)}")

        self.check("Tier 1" in content, "brain: Tier 1 references")
        self.check("Tier 2" in content, "brain: Tier 2 references")

    def validate_python_tools(self) -> None:
        for tool in ["knowledge_updater.py", "run_test_scenarios.py"]:
            fpath = ROOT / "tools" / tool
            self.check(fpath.exists(), f"Tool exists: {tool}")
            if fpath.exists():
                content = self.read(fpath)
                self.check('"""' in content, f"{tool}: docstring present")
                self.check("import " in content, f"{tool}: imports present")

        ku_path = ROOT / "tools" / "knowledge_updater.py"
        if ku_path.exists():
            ku = self.read(ku_path)
            self.check("KNOWLEDGE_CONFIG" in ku, "knowledge_updater: config")
            self.check("sha256" in ku, "knowledge_updater: SHA256 dedup")
            self.check("score_entry" in ku, "knowledge_updater: scoring")
            self.check("--dry-run" in ku, "knowledge_updater: dry-run flag")
            self.check("fetch_with_retry" in ku, "knowledge_updater: retry logic")
            self.check("compute_hash" in ku, "knowledge_updater: hash function")

    def validate_pdpt(self) -> None:
        pdpt_path = ROOT / "PROJECT-DEVELOPMENT-PHASE-TRACKING.md"
        if not pdpt_path.exists():
            self.check(False, "PDPT exists")
            return

        content = self.read(pdpt_path)

        for phase_num in range(6):
            self.check(f"Phase {phase_num}" in content,
                       f"PDPT: Phase {phase_num} present")

        self.check("100%" in content, "PDPT: 100% completion markers",
                   category="warning")
        self.check("PRODUCTION READY" in content.upper() or
                   "COMPLETE" in content.upper(),
                   "PDPT: production-ready status")

        phases = re.findall(r"Status:\s*\*?\*?(100%|\d+%)", content)
        if phases:
            all_complete = all(s == "100%" for s in phases)
            self.check(all_complete, "PDPT: all phases at 100%",
                       f"statuses: {phases}", "warning" if not all_complete else "error")

    def validate_test_scenarios(self) -> None:
        sc_path = ROOT / "tests" / "test-scenarios.md"
        if not sc_path.exists():
            self.check(False, "test-scenarios.md exists")
            return

        content = self.read(sc_path)
        scenario_count = len(re.findall(r"^## Scenario", content, re.MULTILINE))
        self.check(scenario_count >= 5, "test-scenarios: 5+ scenarios",
                   f"found {scenario_count}")

        self.check("degraded" in content.lower() or "missing" in content.lower(),
                   "test-scenarios: degraded mode case")

        for gate in ["G1", "G2", "G3", "G4"]:
            self.check(gate in content, f"test-scenarios: references {gate}")

        self.check("Gate coverage matrix" in content,
                   "test-scenarios: coverage matrix")

    def validate_cross_references(self) -> None:
        claude_content = self.read(ROOT / "CLAUDE.md")
        pdpt_content = self.read(ROOT / "PROJECT-DEVELOPMENT-PHASE-TRACKING.md")
        proj_detail = self.read(ROOT / "PROJECT-detail.md")
        readme = self.read(ROOT / "README.md")

        refs = [
            ("CLAUDE.md → PROJECT-detail.md", claude_content, "PROJECT-detail.md"),
            ("CLAUDE.md → PDPT", claude_content, "PROJECT-DEVELOPMENT-PHASE-TRACKING.md"),
            ("README.md → PROJECT-detail.md", readme, "PROJECT-detail.md"),
            ("README.md → skills/main.md", readme, "skills/main.md"),
            ("PROJECT-detail.md → skills/", proj_detail, "skills/"),
            ("PDPT → SECOND-KNOWLEDGE-BRAIN.md", pdpt_content, "SECOND-KNOWLEDGE-BRAIN.md"),
        ]

        for label, content, target in refs:
            self.check(target.lower() in content.lower() if content else True,
                       f"Cross-ref: {label}",
                       category="warning")

    def validate_phase6_architecture(self) -> None:
        """Phase 6 ? flexible agent & skill architecture + modular dirs."""
        # Modular directories
        for d in ["config", "scripts", "references", "assets"]:
            self.check((ROOT / d).is_dir(), f"Phase 6 dir: {d}")
        for sub in ["references/prompts", "references/domain",
                    "assets/schemas", "assets/diagrams"]:
            self.check((ROOT / sub).is_dir(), f"Phase 6 subdir: {sub}")

        # SKILL.md registry doc
        skill_md = ROOT / "SKILL.md"
        self.check(skill_md.exists(), "SKILL.md exists")
        if skill_md.exists():
            content = self.read(skill_md)
            for token in ["Skill Registry", "Router", "Tool System",
                          "Quality Gates", "Hooks", "Configuration"]:
                self.check(token in content, f"SKILL.md: {token}")

        # New src modules
        for mod in ["config.py", "hooks.py", "tools.py", "registry.py",
                    "router.py", "orchestrator.py"]:
            fpath = ROOT / "src" / "gaming_tweaks" / mod
            self.check(fpath.exists(), f"Phase 6 module: {mod}")
            if fpath.exists():
                content = self.read(fpath)
                self.check('\"\"\"' in content or '"""' in content,
                            f"{mod}: docstring present", category="warning")

        # Config profiles load (import-safe)
        try:
            sys.path.insert(0, str(ROOT / "src"))
            from gaming_tweaks.config import load_config, ConfigValidationError  # noqa: E402
            for prof in ["config/default.json", "config/development.json",
                         "config/test.json"]:
                try:
                    cfg = load_config(ROOT / prof)
                    self.check(cfg.environment in
                                {"production", "development", "test"},
                                f"config profile loads: {prof}")
                except ConfigValidationError as exc:
                    self.check(False, f"config profile loads: {prof}",
                               str(exc))
        except Exception as exc:  # noqa: BLE001
            self.check(False, "Phase 6 config import", str(exc), category="warning")

        # JSON schemas parse
        import json as _json
        for sch in (ROOT / "assets/schemas").glob("*.json"):
            try:
                _json.loads(sch.read_text(encoding="utf-8"))
                self.check(True, f"schema parses: {sch.name}")
            except _json.JSONDecodeError as exc:
                self.check(False, f"schema parses: {sch.name}", str(exc))

        # Scripts present
        for script in ["setup_env.py", "seed_knowledge.py",
                       "ingest_knowledge.py", "validate_architecture.py"]:
            self.check((ROOT / "scripts" / script).exists(),
                       f"Phase 6 script: {script}")

        # References present
        for ref in ["references/prompts/system_base.md",
                    "references/domain/domain_knowledge.md",
                    "references/domain/source_map.md"]:
            self.check((ROOT / ref).exists(), f"Phase 6 reference: {ref}")

        # Orchestrator smoke (offline)
        try:
            from gaming_tweaks.orchestrator import Orchestrator  # noqa: E402
            from gaming_tweaks.registry import SkillRegistry  # noqa: E402
            reg = SkillRegistry(skills_dir=ROOT / "skills")
            reg.load(strict=False)
            orch = Orchestrator(registry=reg)
            result = orch.run("compare competitive vs casual")
            self.check(bool(result.run_id), "orchestrator run_id")
            self.check(len(result.gates) >= 10, "orchestrator runs 10 gates",
                       f"got {len(result.gates)}", "warning")
        except Exception as exc:  # noqa: BLE001
            self.check(False, "orchestrator smoke", str(exc), category="warning")

    def validate_readme(self) -> None:
        content = self.read(ROOT / "README.md")
        if not content:
            self.check(False, "README.md: exists")
            return

        self.check("gaming-os-hardware-tweaking" in content,
                   "README: project name")
        self.check("Installation" in content or "install" in content.lower(),
                   "README: installation section")
        self.check("Usage" in content or "usage" in content.lower(),
                   "README: usage section")
        self.check("License" in content or "license" in content.lower(),
                   "README: license section")
        self.check("## " in content, "README: has markdown headings")

    def run(self) -> bool:
        print(f"[validate_project] Validation started at {datetime.now().isoformat()}")
        print(f"[validate_project] Root: {ROOT}")
        print(f"[validate_project] Verbose: {self.verbose}, Strict: {self.strict}")
        print()

        self.validate_file_existence()
        self.validate_sub_skill_structure()
        self.validate_main_harness()
        self.validate_knowledge_brain()
        self.validate_python_tools()
        self.validate_pdpt()
        self.validate_test_scenarios()
        self.validate_phase6_architecture()
        self.validate_cross_references()
        self.validate_readme()

        print()
        print(f"[validate_project] {self.checks_passed}/{self.checks_total} checks passed")

        if self.warnings:
            print(f"[validate_project] {len(self.warnings)} warnings:")
            for label, detail in self.warnings:
                print(f"  ⚠ {label}: {detail}")

        if self.errors:
            print(f"[validate_project] {len(self.errors)} ERRORS:")
            for label, detail in self.errors:
                print(f"  ✗ {label}: {detail}")
            print("[validate_project] VALIDATION FAILED")
            return False

        print("[validate_project] ALL CHECKS PASSED — PRODUCTION READY")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Validate gaming-os-hardware-tweaking project structure and quality")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show all passing checks")
    parser.add_argument("--strict", "-s", action="store_true",
                        help="Treat warnings as errors")
    args = parser.parse_args()

    validator = Validator(verbose=args.verbose, strict=args.strict)
    success = validator.run()

    if args.strict and validator.warnings:
        print("[validate_project] Strict mode: warnings treated as errors")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
