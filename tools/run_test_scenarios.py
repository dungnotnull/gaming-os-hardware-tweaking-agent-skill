"""
run_test_scenarios.py â€” Skill 204: gaming-os-hardware-tweaking
Production-grade structural & content validator. Verifies the 8-File Contract,
sub-skill content, knowledge base, test scenarios, and quality-gate coverage.
Exit code 0 = all checks pass, non-zero = failures.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
GATES = ["U1","U2","U3","U4","U5","U6"] + [g["id"] for g in [{"id": "G1", "check": "Input latency config (Reflex/VRR/BFI/polling) stated", "fix": "State latency config"}, {"id": "G2", "check": "CPU/GPU scheduling tuned (Game Mode/power/background)", "fix": "Tune scheduling"}, {"id": "G3", "check": "Monitoring metrics defined (frame time, 1% lows, latency)", "fix": "Define monitoring"}, {"id": "G4", "check": "Stability-vs-gain tradeoffs noted", "fix": "Note stability tradeoffs"}]]
VERDICTS = ["Optimized & Stable", "Conditional (risky tweaks)", "Low-Performance Hardware", "Inconclusive"]

checks_passed = 0
checks_failed = 0
failures = []

def ok(label, detail=""):
    global checks_passed; checks_passed += 1

def fail(label, detail=""):
    global checks_failed; checks_failed += 1
    failures.append(f"{label}: {detail}")

def require(cond, label, detail=""):
    (ok if cond else fail)(label, detail)

def read(p):
    return Path(p).read_text(encoding="utf-8") if Path(p).exists() else ""

# ---- 1. File structure ----
REQUIRED = ["CLAUDE.md","PROJECT-detail.md","PROJECT-DEVELOPMENT-PHASE-TRACKING.md",
            "README.md","SECOND-KNOWLEDGE-BRAIN.md","skills/main.md",
            "tools/knowledge_updater.py","tools/test_knowledge_updater.py",
            "tools/run_test_scenarios.py","tests/test-scenarios.md","tests/TEST_RESULTS.md"]
for f in REQUIRED:
    require((ROOT/f).exists(), f"file present: {f}")

subs = sorted(SKILLS.glob("sub-*.md"))
require(len(subs) >= 5, f"at least 5 sub-skills", f"found {len(subs)}")
expected_subs = set(["sub-gather-requirements", "sub-evidence-collector", "sub-core-analysis", "sub-knowledge-updater", "sub-advisor"])
got_subs = {s.stem for s in subs}
require(got_subs == expected_subs, "sub-skill set", f"got {got_subs}")

# ---- 2. Frontmatter + sections ----
FM = re.compile(r"^---\s*\n(.*?\n)---", re.S)
for s in subs:
    txt = read(s)
    m = FM.search(txt)
    require(bool(m), f"{s.name}: frontmatter")
    if m:
        require("name:" in m.group(1) and "description:" in m.group(1), f"{s.name}: name+description")
    for sec in ["Role & Persona","Workflow","Output Format","Quality Gates"]:
        require(sec in txt, f"{s.name}: section {sec}")

main_txt = read(ROOT/"skills/main.md")
for sec in ["Role & Persona","Quality Gates","Graceful Degradation"]:
    require(sec in main_txt, f"main.md: section {sec}")
require("Harness Execution Protocol" in main_txt or "Workflow" in main_txt, "main.md: harness workflow heading")
require("Pre-Flight" in main_txt, "main.md: pre-flight language detection")
require("limitation" in main_txt.lower(), "main.md: limitation banner")

# ---- 3. Quality gate coverage ----
for g in GATES:
    require(g in main_txt, f"main.md: gate {g} present")
adv = read(ROOT/"skills/sub-advisor.md") if (ROOT/"skills/sub-advisor.md").exists() else ""
for v in VERDICTS:
    require(v in adv or v in main_txt, f"advisor/verdict {v} present")

# ---- 4. Knowledge base ----
brain = read(ROOT/"SECOND-KNOWLEDGE-BRAIN.md")
require("Tier 1" in brain and "Tier 4" in brain, "brain: evidence hierarchy tiers")
dois = re.findall(r"10\.\d{4,9}/[^\s|]+", brain)
require(len(dois) >= 2, f"brain: >=2 DOI-cited references", f"found {len(dois)}")
rows = len(re.findall(r"\|\s*\d{4}\s*\|", brain))
require(rows >= 3 or brain.count("### 2.") > 0, "brain: key-papers table present")
require(("### 1.1" in brain) or ("Foundational" in brain) or ("## 1. Core" in brain), "brain: core methods present")
require("## 4. Authoritative Data Sources" in brain, "brain: data sources section")
require("## 6. Self-Update Protocol" in brain, "brain: self-update protocol")

# ---- 5. test-scenarios ----
sc = read(ROOT/"tests/test-scenarios.md")
require(sc.count("Scenario") >= 5, "scenarios: >=5", f"found {sc.count(chr(83)+chr(99)+chr(101))}")
require("degraded" in sc.lower() or "missing" in sc.lower(), "scenarios: degraded case")
require("conflict" in sc.lower() or "compare" in sc.lower() or "comparison" in sc.lower(), "scenarios: comparison/conflict case")
for g in ["G1","G2","G3"]:
    require(g in sc, f"scenarios: gate {g} referenced")

# ---- 6. knowledge_updater.py ----
ku = read(ROOT/"tools/knowledge_updater.py")
require("KNOWLEDGE_CONFIG" in ku, "knowledge_updater: KNOWLEDGE_CONFIG")
require("sha256" in ku, "knowledge_updater: SHA256 dedup")
require("score_entry" in ku, "knowledge_updater: scoring")
require("--dry-run" in ku, "knowledge_updater: dry-run flag")

# ---- 6b. Phase 6 architecture (modular dirs, SKILL.md, modules) ----
require((ROOT/"SKILL.md").exists(), "Phase 6: SKILL.md")
require((ROOT/"config/default.json").exists(), "Phase 6: config/default.json")
require((ROOT/"config/test.json").exists(), "Phase 6: config/test.json")
require((ROOT/"config/development.json").exists(), "Phase 6: config/development.json")
require((ROOT/"config/README.md").exists(), "Phase 6: config/README.md")
require((ROOT/"scripts/setup_env.py").exists(), "Phase 6: scripts/setup_env.py")
require((ROOT/"scripts/seed_knowledge.py").exists(), "Phase 6: scripts/seed_knowledge.py")
require((ROOT/"scripts/ingest_knowledge.py").exists(), "Phase 6: scripts/ingest_knowledge.py")
require((ROOT/"scripts/validate_architecture.py").exists(), "Phase 6: scripts/validate_architecture.py")
require((ROOT/"references/prompts/system_base.md").exists(), "Phase 6: references/prompts/system_base.md")
require((ROOT/"references/domain/domain_knowledge.md").exists(), "Phase 6: references/domain/domain_knowledge.md")
require((ROOT/"assets/schemas/app_config.schema.json").exists(), "Phase 6: assets/schemas/app_config.schema.json")
require((ROOT/"assets/diagrams/system_architecture.md").exists(), "Phase 6: assets/diagrams/system_architecture.md")
for mod in ["config.py","hooks.py","tools.py","registry.py","router.py","orchestrator.py"]:
    require((ROOT/"src/gaming_tweaks"/mod).exists(), f"Phase 6: src/gaming_tweaks/{mod}")
skill_md = read(ROOT/"SKILL.md")
for token in ["Skill Registry","Router","Tool System","Hooks","Quality Gates","Configuration"]:
    require(token in skill_md, f"SKILL.md: {token}")
require((ROOT/"tests/test_agent_architecture.py").exists(), "Phase 6: tests/test_agent_architecture.py")
pdpt = read(ROOT/"PROJECT-DEVELOPMENT-PHASE-TRACKING.md")  # read early for Phase 6 check
require("Phase 6" in pdpt, "PDPT: Phase 6 present")

# ---- 7. PDPT + README + PROJECT-detail ----
pdpt = read(ROOT/"PROJECT-DEVELOPMENT-PHASE-TRACKING.md")
require("100%" in pdpt, "PDPT: 100% markers")
require("Phase 5" in pdpt, "PDPT: Phase 5")
readme = read(ROOT/"README.md")
require("Usage" in readme, "README: usage")
pd = read(ROOT/"PROJECT-detail.md")
require("Idea (Vietnamese)" in pd, "PROJECT-detail: Idea (Vietnamese)")
require("Harness Architecture" in pd, "PROJECT-detail: harness architecture")

# ---- report ----
total = checks_passed + checks_failed
print(f"[run_test_scenarios] {checks_passed}/{total} checks passed")
if failures:
    for f in failures:
        print("  - FAIL " + f)
    sys.exit(1)
print("[OK] all checks passed")
sys.exit(0)
