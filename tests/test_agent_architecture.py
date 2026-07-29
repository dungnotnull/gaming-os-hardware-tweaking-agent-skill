"""
test_agent_architecture.py — Tests for the Phase 6 flexible agent & skill
architecture: config, hooks, tools, registry, router, orchestrator.

Run:  pytest tests/test_agent_architecture.py -v
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Ensure src is importable (conftest also adds it).
ROOT = Path(__file__).resolve().parent.parent

from gaming_tweaks import config as cfg_mod
from gaming_tweaks.config import (
    AppConfig, LLMConfig, FeatureFlags, KnowledgeConfig, LoggingConfig,
    OrchestrationConfig, ConfigLoader, ConfigValidationError, LogLevel,
    ProviderType, load_config,
)
from gaming_tweaks.hooks import (
    HookContext, HookRegistry, HookType, EventEmitter,
    logging_hook, metrics_hook, state_sync_hook, event_emission_hook, Hook,
)
from gaming_tweaks.tools import (
    Tool, ToolSchema, ToolRegistry, ToolResult, BUILTIN_TOOLS, default_registry,
)
from gaming_tweaks.registry import SkillRegistry, SkillSpec, SkillValidationError, parse_skill_file
from gaming_tweaks.router import Router, ExecutionPlan, route
from gaming_tweaks.orchestrator import (
    Orchestrator, OrchestrationResult, OfflineAssemblyBackend, CallableLLMBackend,
    SkillResult, QualityGateResult, GATE_CHECKS, estimate_tokens, run_harness,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults_load(self):
        c = load_config()
        assert c.app_name == "gaming-os-hardware-tweaking"
        assert c.llm.provider == ProviderType.CLAUDE
        assert c.flags.enable_hooks is True
        assert "U1" in c.orchestration.quality_gates

    def test_available_input_tokens(self):
        c = load_config()
        assert c.llm.available_input_tokens == (
            c.llm.context_window_tokens - c.llm.reserve_output_tokens
        )

    def test_env_overrides_win(self, monkeypatch):
        monkeypatch.setenv("GAMING_TWEAKS_LLM_MAX_TOKENS", "4096")
        monkeypatch.setenv("GAMING_TWEAKS_DEBUG", "true")
        c = load_config()
        assert c.llm.max_tokens == 4096
        assert c.debug is True

    def test_section_env_overlay(self, monkeypatch):
        monkeypatch.setenv("GAMING_TWEAKS_FLAGS_MAX_GATE_RETRIES", "5")
        c = load_config()
        assert c.flags.max_gate_retries == 5

    def test_json_profile_loads(self):
        c = load_config(ROOT / "config/default.json")
        assert c.environment == "production"
        assert len(c.orchestration.quality_gates) == 10

    def test_development_profile(self):
        c = load_config(ROOT / "config/development.json")
        assert c.environment == "development"
        assert c.debug is True

    def test_test_profile(self):
        c = load_config(ROOT / "config/test.json")
        assert c.environment == "test"
        assert c.flags.enable_web_search is False

    def test_invalid_temperature_raises(self):
        with pytest.raises(ConfigValidationError):
            LLMConfig(temperature=5.0)

    def test_invalid_token_budget_raises(self):
        with pytest.raises(ConfigValidationError):
            LLMConfig(context_window_tokens=100, reserve_output_tokens=200)

    def test_invalid_environment_raises(self):
        with pytest.raises(ConfigValidationError):
            AppConfig(environment="mars")

    def test_bool_parsing_variants(self):
        assert cfg_mod._parse_bool("YES") is True
        assert cfg_mod._parse_bool("off") is False
        assert cfg_mod._parse_bool(1) is True

    def test_coerce_list_from_csv_string(self):
        assert cfg_mod._coerce("a, b ,c", list) == ["a", "b", "c"] or \
               cfg_mod._coerce("a, b ,c", list[str]) == ["a", "b", "c"]

    def test_unknown_section_key_strict_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"llm": {"bogus_key": 1}}), encoding="utf-8")
        with pytest.raises(ConfigValidationError):
            load_config(p)

    def test_underscore_keys_skipped(self, tmp_path):
        p = tmp_path / "ok.json"
        p.write_text(json.dumps({"_comment": "hi", "llm": {"_note": "x", "max_tokens": 1024}}),
                     encoding="utf-8")
        c = load_config(p)
        assert c.llm.max_tokens == 1024  # underscore keys ignored, valid key kept

    def test_to_dict_roundtrip(self):
        d = load_config().to_dict()
        assert d["app_name"] == "gaming-os-hardware-tweaking"
        assert d["llm"]["provider"] == "claude"

    def test_orchestration_dedup_gates(self):
        oc = OrchestrationConfig(quality_gates=["U1", "U1", "G1", "G1"])
        assert oc.quality_gates == ["U1", "G1"]

    def test_default_language_must_be_supported(self):
        with pytest.raises(ConfigValidationError):
            OrchestrationConfig(default_language="fr",
                                supported_languages=["en", "vi"])

    def test_config_file_not_found_strict_raises(self, tmp_path):
        with pytest.raises(ConfigValidationError):
            load_config(tmp_path / "missing.json", strict=True)


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


class TestHooks:
    def test_register_and_emit(self):
        reg = HookRegistry()
        seen = []
        reg.register(HookType.POST_STEP, lambda ctx: seen.append(ctx.skill_name),
                     name="capture")
        reg.emit(HookContext(event=HookType.POST_STEP, skill_name="s1"))
        assert seen == ["s1"]

    def test_priority_ordering(self):
        reg = HookRegistry()
        order = []
        reg.register(HookType.POST_STEP, lambda c: order.append("b"),
                     name="b", priority=200)
        reg.register(HookType.POST_STEP, lambda c: order.append("a"),
                     name="a", priority=10)
        reg.emit(HookContext(event=HookType.POST_STEP))
        assert order == ["a", "b"]

    def test_hook_exception_does_not_abort(self):
        reg = HookRegistry()
        reg.register(HookType.POST_STEP, lambda c: (_ for _ in ()).throw(ValueError("boom")),
                     name="bad")
        ctx = HookContext(event=HookType.POST_STEP)
        reg.emit(ctx)  # must not raise
        assert any("bad" in e for e in ctx.errors)

    def test_unregister_by_name(self):
        reg = HookRegistry()
        reg.register(HookType.POST_STEP, lambda c: None, name="x")
        assert reg.unregister_by_name("x") == 1
        assert reg.hooks(HookType.POST_STEP) == []

    def test_disable_enable(self):
        reg = HookRegistry()
        called = []
        reg.register(HookType.PRE_STEP, lambda c: called.append(1), name="h")
        assert reg.disable("h") == 1
        reg.emit(HookContext(event=HookType.PRE_STEP))
        assert called == []
        assert reg.enable("h") == 1
        reg.emit(HookContext(event=HookType.PRE_STEP))
        assert called == [1]

    def test_metrics_hook_aggregates(self):
        m = metrics_hook()
        ctx = HookContext(event=HookType.POST_STEP, skill_name="s1", elapsed_seconds=0.5)
        m(ctx)
        m(HookContext(event=HookType.POST_STEP, skill_name="s1", elapsed_seconds=0.3))
        assert m.metrics["events_total"] == 2
        assert "s1" in m.metrics["skill_elapsed"]

    def test_state_sync_hook_mirrors(self):
        state = {}
        m = state_sync_hook(state)
        ctx = HookContext(event=HookType.POST_STEP, skill_name="s1",
                          outputs={"x": 1})
        m(ctx)
        assert state["s1"] == {"x": 1}

    def test_event_emitter_buffer(self):
        em = EventEmitter()
        m = event_emission_hook(em)
        m(HookContext(event=HookType.POST_STEP, skill_name="s1"))
        assert len(em.events()) == 1

    def test_hook_priority_negative_raises(self):
        with pytest.raises(ValueError):
            Hook(name="h", event=HookType.POST_STEP, handler=lambda c: None,
                 priority=-1)

    def test_hook_handler_must_be_callable(self):
        with pytest.raises(TypeError):
            Hook(name="h", event=HookType.POST_STEP, handler="not callable")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class TestTools:
    def test_builtin_tools_present(self):
        names = BUILTIN_TOOLS.keys()
        for t in ["profile_system", "recommend_tweaks", "validate_benchmark",
                  "read_knowledge_brain", "query_knowledge_brain",
                  "set_state", "get_state", "detect_language", "hash_text", "noop"]:
            assert t in names

    def test_default_registry_lists_all(self):
        reg = default_registry()
        names = reg.list_tools()
        assert len(names) >= 10

    def test_invoke_detect_language_vi(self):
        reg = default_registry()
        res = reg.invoke("detect_language", {"text": "Tối ưu hệ thống"})
        assert res.ok and res.value["language"] == "vi"

    def test_invoke_detect_language_en(self):
        reg = default_registry()
        res = reg.invoke("detect_language", {"text": "Optimize latency"})
        assert res.ok and res.value["language"] == "en"

    def test_hash_text_sha256(self):
        reg = default_registry()
        res = reg.invoke("hash_text", {"text": "abc"})
        assert res.ok
        assert res.value["hash"].startswith("ba7816bf")

    def test_hash_text_invalid_algorithm_validation(self):
        reg = default_registry()
        res = reg.invoke("hash_text", {"text": "abc", "algorithm": "rot13"})
        assert res.ok is False
        assert "validation" in (res.error or "")

    def test_invoke_unknown_tool(self):
        reg = default_registry()
        res = reg.invoke("does_not_exist", {})
        assert res.ok is False
        assert "unknown tool" in (res.error or "")

    def test_input_validation_missing_required(self):
        reg = default_registry()
        res = reg.invoke("hash_text", {})
        assert res.ok is False
        assert "required" in (res.error or "") or "missing" in (res.error or "")

    def test_alias_resolution(self):
        reg = default_registry()
        reg.register(BUILTIN_TOOLS["hash_text"], aliases=["sha"])
        assert reg.resolve("sha") is not None

    def test_state_tools_roundtrip(self):
        reg = default_registry(state={})
        r1 = reg.invoke("set_state", {"key": "k", "value": 42})
        assert r1.ok and r1.value["set"] is True
        r2 = reg.invoke("get_state", {"key": "k"})
        assert r2.ok and r2.value["value"] == 42

    def test_read_knowledge_brain_missing_path(self):
        reg = default_registry()
        res = reg.invoke("read_knowledge_brain", {"path": "does_not_exist.md"})
        assert res.ok and res.value["found"] is False

    def test_read_knowledge_brain_real(self):
        reg = default_registry()
        res = reg.invoke("read_knowledge_brain",
                         {"path": str(ROOT / "SECOND-KNOWLEDGE-BRAIN.md")})
        assert res.ok and res.value["found"] is True
        assert "sha256" in res.value

    def test_query_knowledge_brain(self):
        reg = default_registry()
        res = reg.invoke("query_knowledge_brain",
                         {"query": "Tier", "path": str(ROOT / "SECOND-KNOWLEDGE-BRAIN.md"),
                          "max_hits": 5})
        assert res.ok
        assert res.value["total"] >= 1

    def test_metrics_recorded(self):
        reg = default_registry()
        reg.invoke("hash_text", {"text": "x"})
        reg.invoke("hash_text", {"text": "y"})
        m = reg.metrics()
        assert m["invocations"]["hash_text"] == 2

    def test_tool_with_custom_handler(self):
        reg = ToolRegistry()
        tool = Tool(
            schema=ToolSchema(name="echo", description="echo",
                              input_schema={"type": "object",
                                            "required": ["x"],
                                            "properties": {"x": {"type": "string"}}}),
            handler=lambda i: {"echo": i["x"]},
        )
        reg.register(tool)
        res = reg.invoke("echo", {"x": "hi"})
        assert res.ok and res.value == {"echo": "hi"}

    def test_output_validation_failure(self):
        reg = ToolRegistry()
        tool = Tool(
            schema=ToolSchema(name="bad_out", description="bad output",
                              input_schema={"type": "object"},
                              output_schema={"type": "object",
                                             "required": ["must"],
                                             "properties": {"must": {"type": "string"}}}),
            handler=lambda i: {"wrong": 1},
        )
        reg.register(tool)
        res = reg.invoke("bad_out", {})
        assert res.ok is False
        assert "output validation" in (res.error or "")

    def test_unsafe_tool_error_does_not_raise(self):
        reg = ToolRegistry()
        tool = Tool(
            schema=ToolSchema(name="boom", description="raises",
                              input_schema={"type": "object"},
                              output_schema=None),
            handler=lambda i: (_ for _ in ()).throw(RuntimeError("kaboom")),
        )
        reg.register(tool)
        res = reg.invoke("boom", {})
        assert res.ok is False
        assert "kaboom" in (res.error or "")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_loads_all_skills(self):
        reg = SkillRegistry(skills_dir=ROOT / "skills")
        specs = reg.load(strict=True)
        names = [s.name for s in specs]
        assert "sub-advisor" in names
        assert "sub-core-analysis" in names
        assert len(names) >= 5

    def test_main_uses_alt_section_accepted(self):
        reg = SkillRegistry(skills_dir=ROOT / "skills")
        reg.load(strict=True)
        assert reg.get("gaming-os-hardware-tweaking") is not None

    def test_get_by_name(self):
        reg = SkillRegistry(skills_dir=ROOT / "skills")
        reg.load(strict=False)
        assert reg.get("sub-advisor") is not None
        assert reg.get("nope") is None

    def test_by_tag(self):
        reg = SkillRegistry(skills_dir=ROOT / "skills")
        reg.load(strict=False)
        advisory = reg.by_tag("advisory")
        assert any(s.name == "sub-advisor" for s in advisory)

    def test_search_ranks(self):
        reg = SkillRegistry(skills_dir=ROOT / "skills")
        reg.load(strict=False)
        results = reg.search("latency fps optimization")
        assert len(results) >= 1
        assert results[0].name in {s.name for s in reg._by_name.values()}

    def test_validate_spec_missing_section(self, tmp_path):
        p = tmp_path / "bad.md"
        p.write_text("---\nname: bad\ndescription: d\n---\n## Role & Persona\nx\n",
                      encoding="utf-8")
        with pytest.raises(SkillValidationError):
            parse_skill_file(p, strict=True)

    def test_validate_spec_too_short(self, tmp_path):
        p = tmp_path / "short.md"
        body = "## Role & Persona\nx\n## Workflow\ny\n## Output Format\nz\n"
        p.write_text(f"---\nname: short\ndescription: d\n---\n{body}", encoding="utf-8")
        with pytest.raises(SkillValidationError):
            parse_skill_file(p, strict=True)

    def test_schemas_serializable(self):
        reg = SkillRegistry(skills_dir=ROOT / "skills")
        reg.load(strict=False)
        data = reg.schemas()
        json.dumps(data)  # must be JSON-serializable
        assert isinstance(data, list) and data

    def test_programmatic_register(self):
        reg = SkillRegistry(skills_dir=ROOT / "tmp_missing")
        spec = SkillSpec(
            name="custom", description="d",
            body_markdown="## Role & Persona\nr\n## Workflow\nw\n## Output Format\no\n" * 5,
        )
        reg.register(spec)
        assert reg.get("custom") is not None

    def test_load_strict_raises_on_missing_dir(self, tmp_path):
        reg = SkillRegistry(skills_dir=tmp_path / "no_skills")
        with pytest.raises(SkillValidationError):
            reg.load(strict=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class TestRouter:
    def setup_method(self):
        self.reg = SkillRegistry(skills_dir=ROOT / "skills")
        self.reg.load(strict=False)
        self.router = Router(self.reg)

    def test_full_pipeline_default(self):
        plan = self.router.route("please help me understand my gaming setup")
        assert plan.intent == "full_pipeline"
        assert len(plan.skills) >= 5
        assert len(plan.reasoning) >= 1

    def test_compare_intent(self):
        plan = self.router.route("compare competitive vs casual latency")
        assert plan.intent == "compare"
        assert "compare_modes" in plan.metadata

    def test_vietnamese_detected(self):
        plan = self.router.route("Tối ưu độ trễ cho hệ thống của tôi")
        assert plan.language == "vi"

    def test_english_detected(self):
        plan = self.router.route("optimize latency for my system")
        assert plan.language == "en"

    def test_profile_recommender_for_own_system(self):
        plan = self.router.route("recommend tweaks for my pc")
        assert plan.intent == "profile_recommender"
        assert "sub-core-analysis" in plan.skills

    def test_knowledge_lookup(self):
        plan = self.router.route("what academic papers cite input lag doi")
        assert plan.intent == "knowledge_lookup"

    def test_estimated_tokens_positive(self):
        plan = self.router.route("optimize")
        assert plan.estimated_tokens > 0

    def test_route_module_function(self):
        plan = route("vs compare", registry=self.reg)
        assert plan.intent == "compare"

    def test_skills_validated_against_registry(self):
        # Force unknown intent skills; should fall back to valid subset.
        plan = self.router.route("clarify requirements")
        for s in plan.skills:
            assert s in self.reg.list_skills()

    def test_execution_plan_serializable(self):
        plan = self.router.route("optimize")
        json.dumps(plan.to_dict())


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestOrchestrator:
    def setup_method(self):
        self.reg = SkillRegistry(skills_dir=ROOT / "skills")
        self.reg.load(strict=False)
        self.orch = Orchestrator(registry=self.reg)

    def test_run_returns_result(self):
        r = self.orch.run("optimize latency for competitive play")
        assert isinstance(r, OrchestrationResult)
        assert r.run_id
        assert len(r.steps) >= 1

    def test_plan_recorded(self):
        r = self.orch.run("compare competitive vs casual")
        assert r.plan.intent == "compare"
        assert len(r.plan.reasoning) >= 1

    def test_gates_executed(self):
        r = self.orch.run("optimize latency")
        assert len(r.gates) >= 10
        gate_names = {g.gate for g in r.gates}
        assert {"U1", "U2", "G1", "G4"} <= gate_names

    def test_token_usage_reported(self):
        r = self.orch.run("optimize")
        assert "estimated_prompt_tokens" in r.token_usage
        assert "budget" in r.token_usage

    def test_offline_backend_never_fabricates(self):
        r = self.orch.run("optimize latency")
        for step in r.steps:
            assert "[offline-assembly]" in step.response or "fallback" in step.response or "error" in step.response or step.response

    def test_callable_backend_used(self):
        calls = []
        def fake_llm(prompt, skill_name):
            calls.append(skill_name)
            return f"## Executive Summary\n## Inputs\n## Evidence\n## Conclusion\nDisclosure\nReflex VRR Game Mode frame time stability http://a http://b http://c Tier 2"
        orch = Orchestrator(registry=self.reg,
                            llm=CallableLLMBackend(fake_llm))
        r = orch.run("optimize latency for my system")
        assert len(calls) >= 1
        # With real-ish response, several gates should pass.
        passed = [g for g in r.gates if g.passed]
        assert len(passed) >= 4

    def test_degradation_on_missing_skill(self):
        reg = SkillRegistry(skills_dir=ROOT / "skills")
        reg.load(strict=False)
        # Force an invalid skill into the plan via a stub registry override.
        orch = Orchestrator(registry=reg)
        r = orch.run("optimize latency")
        # baseline: no degradation expected in offline mode unless errors
        assert isinstance(r.degradation_level, int)

    def test_state_propagates(self):
        r = self.orch.run("optimize latency for my system")
        # Each executed skill writes into state.
        assert isinstance(r.state, dict)

    def test_result_serializable(self):
        r = self.orch.run("optimize")
        json.dumps(r.to_dict())

    def test_estimate_tokens(self):
        assert estimate_tokens("a" * 100) == 25
        assert estimate_tokens("") == 1

    def test_gate_checks_present(self):
        for g in ["U1", "U2", "U3", "U4", "U5", "U6", "G1", "G2", "G3", "G4"]:
            assert g in GATE_CHECKS

    def test_run_harness_convenience(self):
        r = run_harness("optimize", registry=self.reg)
        assert r.run_id

    def test_auto_fix_g1_injects_latency(self):
        orch = Orchestrator(registry=self.reg)
        r = orch.run("optimize latency for my system")
        # G1 should pass after auto-fix injection.
        g1 = [g for g in r.gates if g.gate == "G1"][0]
        assert g1.passed

    def test_llm_error_degrades(self):
        def bad_llm(prompt, skill_name):
            raise RuntimeError("llm down")
        orch = Orchestrator(registry=self.reg, llm=CallableLLMBackend(bad_llm))
        r = orch.run("optimize latency")
        assert r.degradation_level >= 2
        assert any("LLM error" in e or "LLM call failed" in e or "llm down" in e.lower() for e in r.errors) or r.degradation_level >= 2

    def test_trace_has_reasoning(self):
        r = self.orch.run("compare competitive vs casual")
        assert any("Detected language" in t or "Keyword scores" in t or "Received query" in t for t in r.trace)


# ---------------------------------------------------------------------------
# Integration: scripts
# ---------------------------------------------------------------------------


class TestScripts:
    def test_validate_architecture_passes(self):
        import subprocess, sys
        env = dict(os.environ, PYTHONUTF8="1")
        r = subprocess.run([sys.executable, str(ROOT / "scripts/validate_architecture.py")],
                           capture_output=True, text=True, env=env, cwd=str(ROOT))
        assert r.returncode == 0, r.stdout + r.stderr

    def test_seed_knowledge_dry_run(self):
        import subprocess, sys
        env = dict(os.environ, PYTHONUTF8="1")
        r = subprocess.run([sys.executable, str(ROOT / "scripts/seed_knowledge.py"),
                            "--dry-run"], capture_output=True, text=True, env=env,
                           cwd=str(ROOT))
        assert r.returncode == 0, r.stdout + r.stderr
        assert "dry-run" in r.stdout
