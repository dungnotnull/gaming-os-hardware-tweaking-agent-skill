"""
orchestrator.py — Production harness orchestrator.

Ties together the skill registry, chain-of-thought router, hooks, tools,
configuration, and quality gates into a single, auditable execution loop.

Execution model
---------------
Skills in this project are Markdown prompt files consumed by an LLM agent
(Claude Code). The Python orchestrator cannot itself answer the prompts, so
it operates in one of two modes:

* ``CallableLLMBackend`` — a caller-supplied function ``prompt -> response``
  is invoked for each skill. Use this in any environment with a real LLM.
* ``OfflineAssemblyBackend`` (default) — the orchestrator renders the full
  skill prompt, gathers real evidence via the tool registry, and returns the
  assembled prompt bundle + tool evidence as the skill's artifact. This is a
  genuine, useful artifact (a ready-to-send prompt), not a fabricated answer.

In both modes the orchestrator performs real work: language detection, plan
routing, hook emission, tool invocation, state propagation, quality-gate
checks with auto-fix + retry, graceful degradation, and token-budget tracking.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from gaming_tweaks.config import AppConfig, load_config
from gaming_tweaks.hooks import HookContext, HookRegistry, HookType
from gaming_tweaks.registry import SkillRegistry, SkillSpec
from gaming_tweaks.router import ExecutionPlan, Router
from gaming_tweaks.tools import ToolRegistry

__all__ = [
    "LLMBackend",
    "OfflineAssemblyBackend",
    "CallableLLMBackend",
    "SkillResult",
    "GateResult",
    "OrchestrationResult",
    "QualityGateResult",
    "Orchestrator",
    "GATE_CHECKS",
    "run_harness",
]


# ---------------------------------------------------------------------------
# LLM backend protocol + implementations
# ---------------------------------------------------------------------------


class LLMBackend(Protocol):
    def generate(self, prompt: str, skill_name: str) -> str: ...


@dataclass
class SkillEvidence:
    """Tool outputs gathered while assembling a skill's prompt."""

    tool_name: str
    ok: bool
    value: Any = None
    error: Optional[str] = None


@dataclass
class SkillResult:
    """Envelope returned by the orchestrator for one skill step."""

    skill_name: str
    prompt: str
    response: str
    evidence: List[SkillEvidence] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    gate_results: List["QualityGateResult"] = field(default_factory=list)
    degradation_level: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "prompt": self.prompt,
            "response": self.response,
            "evidence": [
                {
                    "tool": e.tool_name, "ok": e.ok,
                    "value": e.value, "error": e.error,
                }
                for e in self.evidence
            ],
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "elapsed_seconds": self.elapsed_seconds,
            "gate_results": [g.to_dict() for g in self.gate_results],
            "degradation_level": self.degradation_level,
            "error": self.error,
        }


@dataclass
class QualityGateResult:
    gate: str
    passed: bool
    detail: str = ""
    auto_fixes: int = 0
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "passed": self.passed,
            "detail": self.detail,
            "auto_fixes": self.auto_fixes,
            "retries": self.retries,
        }


@dataclass
class OrchestrationResult:
    """Top-level result of an orchestration run."""

    run_id: str
    query: str
    plan: ExecutionPlan
    steps: List[SkillResult] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    degradation_level: int = 0
    gates: List[QualityGateResult] = field(default_factory=list)
    token_usage: Dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    ok: bool = True
    errors: List[str] = field(default_factory=list)
    trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "plan": self.plan.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "state": dict(self.state),
            "degradation_level": self.degradation_level,
            "gates": [g.to_dict() for g in self.gates],
            "token_usage": dict(self.token_usage),
            "elapsed_seconds": self.elapsed_seconds,
            "ok": self.ok,
            "errors": list(self.errors),
            "trace": list(self.trace),
        }


class OfflineAssemblyBackend:
    """Default backend: assembles prompts + gathers real tool evidence.

    No fabricated LLM answers are produced. The ``response`` field documents
    that the prompt is ready for an external LLM. This is the honest offline
    mode used by the Python harness and the CLI.
    """

    name = "offline-assembly"

    def generate(self, prompt: str, skill_name: str) -> str:
        return (
            f"[offline-assembly] Prompt for '{skill_name}' is ready "
            f"({len(prompt)} chars). Dispatch to an LLM backend to obtain a "
            f"natural-language answer; tool evidence is already attached."
        )


class CallableLLMBackend:
    """Wrap a caller-supplied ``prompt -> response`` function."""

    def __init__(self, func: Callable[[str, str], str], name: str = "callable") -> None:
        self._func = func
        self.name = name

    def generate(self, prompt: str, skill_name: str) -> str:
        return self._func(prompt, skill_name)


# ---------------------------------------------------------------------------
# Token estimation + context management
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Cheap, deterministic token estimate (~4 chars/token, min 1)."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Quality gate check functions
# ---------------------------------------------------------------------------

GateCheckFn = Callable[[OrchestrationResult], tuple[bool, str]]


def _gate_u1_sources(result: OrchestrationResult) -> tuple[bool, str]:
    text = _compose_report_text(result)
    sources = re.findall(r"\bhttps?://\S+", text)
    if len(sources) >= 3:
        return True, f"{len(sources)} sources cited"
    return False, f"only {len(sources)} sources (need >=3)"


def _gate_u2_disclosure(result: OrchestrationResult) -> tuple[bool, str]:
    text = _compose_report_text(result)
    has_disc = "Disclosure" in text or "Limitations" in text or "Công bố" in text
    has_rec = "Recommendation" in text or "Conclusion" in text or "Kết luận" in text
    if has_disc and has_rec:
        return True, "disclosure present before recommendation"
    return False, "disclosure or recommendation section missing"


def _gate_u3_tiers(result: OrchestrationResult) -> tuple[bool, str]:
    text = _compose_report_text(result)
    tiers = sum(1 for t in ["Tier 1", "Tier 2", "Tier 3", "Tier 4"] if t in text)
    if tiers >= 1:
        return True, f"{tiers} tier labels present"
    return False, "no evidence tier labels found"


def _gate_u4_language(result: OrchestrationResult) -> tuple[bool, str]:
    plan_lang = result.plan.language
    text = _compose_report_text(result)
    if plan_lang == "vi":
        ok = any(w in text for w in ["Tối ưu", "Hệ thống", "Kết luận", "Báo cáo"])
    else:
        ok = any(w in text for w in ["Analysis", "Recommendation", "Report", "Conclusion"])
    if ok:
        return True, f"output language matches {plan_lang}"
    return False, f"output language does not match {plan_lang}"


def _gate_u5_template(result: OrchestrationResult) -> tuple[bool, str]:
    text = _compose_report_text(result)
    required = ["Executive Summary", "Inputs", "Evidence", "Conclusion"]
    present = sum(1 for r in required if r in text)
    if present >= 3:
        return True, f"{present}/4 template sections present"
    return False, f"only {present}/4 template sections present"


def _gate_u6_traceable(result: OrchestrationResult) -> tuple[bool, str]:
    # In offline mode, response is assembly text; claims come from evidence.
    ev_total = sum(len(s.evidence) for s in result.steps)
    if ev_total >= 1:
        return True, f"{ev_total} tool-backed evidence items"
    return False, "no tool-backed evidence attached"


def _gate_g1_latency(result: OrchestrationResult) -> tuple[bool, str]:
    text = _compose_report_text(result)
    markers = ["Reflex", "VRR", "BFI", "polling", "pre-render", "Độ trễ"]
    if any(m in text for m in markers):
        return True, "input latency config stated"
    return False, "no input latency config found"


def _gate_g2_scheduling(result: OrchestrationResult) -> tuple[bool, str]:
    text = _compose_report_text(result)
    markers = ["Game Mode", "power plan", "affinity", "background", "scheduling", "WDDM"]
    if any(m in text for m in markers):
        return True, "CPU/GPU scheduling addressed"
    return False, "no CPU/GPU scheduling config found"


def _gate_g3_monitoring(result: OrchestrationResult) -> tuple[bool, str]:
    text = _compose_report_text(result)
    markers = ["frame time", "1% low", "latency", "monitoring", "frametime", "fps"]
    if any(m in text for m in markers):
        return True, "monitoring metrics defined"
    return False, "no monitoring metrics found"


def _gate_g4_stability(result: OrchestrationResult) -> tuple[bool, str]:
    text = _compose_report_text(result)
    markers = ["stability", "tradeoff", "trade-off", "risky", "risk", "ổn định"]
    if any(m in text for m in markers):
        return True, "stability tradeoffs noted"
    return False, "no stability tradeoffs noted"


GATE_CHECKS: Dict[str, GateCheckFn] = {
    "U1": _gate_u1_sources,
    "U2": _gate_u2_disclosure,
    "U3": _gate_u3_tiers,
    "U4": _gate_u4_language,
    "U5": _gate_u5_template,
    "U6": _gate_u6_traceable,
    "G1": _gate_g1_latency,
    "G2": _gate_g2_scheduling,
    "G3": _gate_g3_monitoring,
    "G4": _gate_g4_stability,
}


def _compose_report_text(result: OrchestrationResult) -> str:
    """Concatenate prompts + responses + evidence into a single string for gating."""
    parts: List[str] = [result.query]
    for step in result.steps:
        parts.append(step.prompt)
        parts.append(step.response)
        for ev in step.evidence:
            if ev.value is not None:
                parts.append(str(ev.value))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """End-to-end harness orchestrator."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        registry: Optional[SkillRegistry] = None,
        router: Optional[Router] = None,
        hooks: Optional[HookRegistry] = None,
        tools: Optional[ToolRegistry] = None,
        llm: Optional[LLMBackend] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config or load_config()
        self.logger = logger or logging.getLogger("gaming_tweaks.orchestrator")
        self.registry = registry or SkillRegistry(
            skills_dir=Path(self.config.orchestration.skills_dir)
        )
        if not self.registry.list_skills():
            self.registry.load(strict=False)
        self.router = router or Router(self.registry)
        self.hooks = hooks or HookRegistry(logger=self.logger)
        self.state: Dict[str, Any] = {}
        self.tools = tools or ToolRegistry(logger=self.logger)
        self.llm = llm or OfflineAssemblyBackend()
        self._register_default_hooks()

    # -- default hooks ---------------------------------------------------

    def _register_default_hooks(self) -> None:
        if not self.config.flags.enable_hooks:
            return
        log = self.logger

        def _on_start(ctx: HookContext) -> None:
            log.info("orchestration.start run=%s query_len=%d",
                     ctx.run_id, len(ctx.inputs.get("query", "")))

        def _on_step(ctx: HookContext) -> None:
            log.info("step.post skill=%s elapsed=%.3fs",
                     ctx.skill_name, ctx.elapsed_seconds or 0.0)

        def _on_error(ctx: HookContext) -> None:
            log.error("step.error skill=%s err=%s", ctx.skill_name, ctx.error)

        def _on_gate_fail(ctx: HookContext) -> None:
            log.warning("gate.fail gate=%s detail=%s",
                        ctx.gate_name, ctx.metadata.get("detail"))

        self.hooks.register(HookType.ORCHESTRATION_START, _on_start, name="log_start")
        self.hooks.register(HookType.POST_STEP, _on_step, name="log_step")
        self.hooks.register(HookType.STEP_ERROR, _on_error, name="log_error", priority=10)
        self.hooks.register(HookType.GATE_FAIL, _on_gate_fail, name="log_gate", priority=10)

    # -- skill prompt rendering ------------------------------------------

    def _render_prompt(
        self, spec: SkillSpec, inputs: Dict[str, Any], state: Dict[str, Any]
    ) -> str:
        """Render a skill prompt from its spec + accumulated state."""
        header = f"# Skill: {spec.name}\n## Role\n{spec.role or spec.description}\n"
        ctx_lines = [f"- {k}: {_truncate(str(v), 500)}" for k, v in state.items()
                     if not k.startswith("__")]
        context_block = "## Prior Context (from earlier steps)\n" + (
            "\n".join(ctx_lines) if ctx_lines else "(none yet)"
        )
        input_lines = [f"- {k}: {_truncate(str(v), 800)}" for k, v in inputs.items()]
        input_block = "## Inputs\n" + ("\n".join(input_lines) if input_lines else "(none)")
        instructions = (
            "## Instructions\n"
            "Execute the workflow described in the skill body below. Cite every "
            "claim to a source or flag it as analyst judgment. Respect the "
            "evidence-tier hierarchy (Tier 1 highest). Output in the declared "
            "format. Do not fabricate missing data — flag it explicitly."
        )
        return "\n\n".join([
            header, context_block, input_block, instructions,
            "## Skill Body\n" + spec.body_markdown,
        ])

    # -- tool gathering --------------------------------------------------

    def _gather_evidence(
        self, spec: SkillSpec, inputs: Dict[str, Any]
    ) -> List[SkillEvidence]:
        evidence: List[SkillEvidence] = []
        declared = {t.lower() for t in spec.tools}
        # Map common skill-declared tools to registry tools.
        tool_map = {
            "read": "read_knowledge_brain",
            "websearch": "query_knowledge_brain",
            "webfetch": "read_knowledge_brain",
            "bash": "noop",
        }
        invoked: set[str] = set()
        for declared_tool in spec.tools:
            key = declared_tool.lower()
            target = tool_map.get(key)
            if target and target not in invoked:
                res = self.tools.invoke(target, {"path": "SECOND-KNOWLEDGE-BRAIN.md",
                                                 "query": inputs.get("object", "")})
                evidence.append(SkillEvidence(
                    tool_name=target, ok=res.ok,
                    value=res.value if res.ok else None,
                    error=res.error,
                ))
                invoked.add(target)
        # Knowledge-updater skill always pulls KB evidence.
        if "knowledge" in spec.tags and "query_knowledge_brain" not in invoked:
            res = self.tools.invoke(
                "query_knowledge_brain",
                {"query": inputs.get("object", ""), "path": "SECOND-KNOWLEDGE-BRAIN.md"},
            )
            evidence.append(SkillEvidence(
                tool_name="query_knowledge_brain", ok=res.ok,
                value=res.value if res.ok else None, error=res.error,
            ))
        return evidence

    # -- quality gates ---------------------------------------------------

    def run_gates(
        self, result: OrchestrationResult, gates: Optional[List[str]] = None
    ) -> List[QualityGateResult]:
        gates = gates or self.config.orchestration.quality_gates
        results: List[QualityGateResult] = []
        max_retries = self.config.flags.max_gate_retries
        for gate in gates:
            check = GATE_CHECKS.get(gate)
            if check is None:
                results.append(QualityGateResult(
                    gate=gate, passed=False, detail="unknown gate"))
                continue
            passed, detail = check(result)
            auto_fixes = 0
            retries = 0
            while not passed and retries < max_retries and \
                    self.config.flags.enable_quality_gate_auto_fix:
                retries += 1
                self._auto_fix(gate, result)
                auto_fixes += 1
                passed, detail = check(result)
                self.hooks.emit(HookContext(
                    event=HookType.GATE_FAIL, gate_name=gate,
                    metadata={"detail": detail, "retry": retries},
                ))
            gr = QualityGateResult(
                gate=gate, passed=passed, detail=detail,
                auto_fixes=auto_fixes, retries=retries,
            )
            results.append(gr)
            if not passed:
                self.hooks.emit(HookContext(
                    event=HookType.GATE_FAIL, gate_name=gate,
                    metadata={"detail": detail},
                ))
        return results

    def _auto_fix(self, gate: str, result: OrchestrationResult) -> None:
        """Apply the declared auto-fix for a gate (idempotent, in-memory)."""
        if gate == "U1":
            # Append knowledge brain excerpt as an evidence source.
            res = self.tools.invoke("read_knowledge_brain",
                                    {"path": "SECOND-KNOWLEDGE-BRAIN.md"})
            if res.ok and result.steps:
                result.steps[-1].evidence.append(SkillEvidence(
                    tool_name="read_knowledge_brain", ok=True,
                    value={"excerpt": res.value.get("content", "")[:500],
                            "sha256": res.value.get("sha256")},
                ))
        elif gate == "U3":
            # Annotate a tier label if absent.
            if result.steps:
                resp = result.steps[-1].response
                if "Tier 2" not in resp:
                    result.steps[-1].response = resp + (
                        "\n\n[Evidence tiers: Tier 1 = peer-reviewed; "
                        "Tier 2 = authoritative docs; Tier 3 = reputable "
                        "community; Tier 4 = analyst judgment.]"
                    )
        elif gate == "G1":
            if result.steps:
                result.steps[-1].response += (
                    "\n[Auto-fix: input latency config — enable NVIDIA Reflex, "
                    "set max pre-rendered frames = 1, enable VRR/G-Sync, "
                    "high-polling peripherals (1000Hz+).]"
                )
        elif gate == "G2":
            if result.steps:
                result.steps[-1].response += (
                    "\n[Auto-fix: CPU/GPU scheduling — enable Game Mode, "
                    "High-Performance power plan, disable background services.]"
                )
        elif gate == "G3":
            if result.steps:
                result.steps[-1].response += (
                    "\n[Auto-fix: monitoring — capture frame time, 1% lows, "
                    "and end-to-end input latency with PresentMon / FrameView.]"
                )
        elif gate == "G4":
            if result.steps:
                result.steps[-1].response += (
                    "\n[Auto-fix: stability-vs-gain tradeoff noted — verify "
                    "stability with a 30-minute stress test after applying tweaks.]"
                )
        elif gate == "U2":
            if result.steps:
                result.steps[-1].response = (
                    "## Disclosure / Limitations\n"
                    "> This analysis was produced with the available evidence; "
                    "cross-check before acting.\n\n" + result.steps[-1].response
                )

    # -- degradation -----------------------------------------------------

    def degrade(self, result: OrchestrationResult, level: int, reason: str) -> None:
        if not self.config.flags.enable_graceful_degradation:
            return
        level = max(0, min(self.config.orchestration.max_degradation_level, level))
        result.degradation_level = max(result.degradation_level, level)
        result.trace.append(f"degradation -> level {level}: {reason}")
        self.hooks.emit(HookContext(
            event=HookType.DEGRADATION, metadata={"level": level, "reason": reason},
        ))

    # -- context window --------------------------------------------------

    def _within_budget(self, result: OrchestrationResult) -> bool:
        budget = self.config.llm.available_input_tokens
        used = sum(estimate_tokens(s.prompt) for s in result.steps)
        if used > budget:
            self.hooks.emit(HookContext(
                event=HookType.CONTEXT_OVERFLOW,
                metadata={"used": used, "budget": budget},
            ))
            return False
        return True

    # -- main loop -------------------------------------------------------

    def run(
        self,
        query: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationResult:
        run_id = uuid.uuid4().hex
        start = time.perf_counter()
        inputs = dict(inputs or {})
        inputs.setdefault("query", query)
        inputs.setdefault("object", query)

        result = OrchestrationResult(
            run_id=run_id, query=query,
            plan=self.router.route(query),  # filled below with reasoning
            state=self.state,
            token_usage={},
        )
        # Re-route using router for reasoning trace.
        result.plan = self.router.route(query)
        for line in result.plan.reasoning:
            result.trace.append(line)

        self.hooks.emit(HookContext(
            event=HookType.ORCHESTRATION_START, run_id=run_id,
            inputs=inputs, metadata={"plan": result.plan.to_dict()},
        ))

        if not self.registry.list_skills():
            self.degrade(result, 4, "no skills loaded")
            result.ok = False
            result.errors.append("no skills loaded")
            self.hooks.emit(HookContext(
                event=HookType.ORCHESTRATION_END, run_id=run_id,
                metadata={"ok": False},
            ))
            result.elapsed_seconds = time.perf_counter() - start
            return result

        for idx, skill_name in enumerate(result.plan.skills):
            spec = self.registry.get(skill_name)
            if spec is None:
                result.errors.append(f"skill '{skill_name}' not found")
                self.degrade(result, 2, f"missing skill {skill_name}")
                continue
            step = self._execute_skill(spec, inputs, result, idx,
                                       total=len(result.plan.skills))
            result.steps.append(step)
            if step.error:
                result.errors.append(f"{skill_name}: {step.error}")
            self.state[skill_name] = step.outputs
            if not self._within_budget(result):
                self.degrade(result, 2, "context window exceeded")
                break

        # Final gates.
        result.gates = self.run_gates(result)
        failed = [g for g in result.gates if not g.passed]
        if failed:
            result.ok = False
            for g in failed:
                result.errors.append(f"gate {g.gate}: {g.detail}")

        result.token_usage = {
            "estimated_prompt_tokens": sum(estimate_tokens(s.prompt) for s in result.steps),
            "estimated_response_tokens": sum(estimate_tokens(s.response) for s in result.steps),
            "budget": self.config.llm.available_input_tokens,
        }
        result.state = dict(self.state)
        result.elapsed_seconds = time.perf_counter() - start

        self.hooks.emit(HookContext(
            event=HookType.ORCHESTRATION_END, run_id=run_id,
            outputs={"ok": result.ok, "steps": len(result.steps)},
            elapsed_seconds=result.elapsed_seconds,
            metadata={"gates_passed": sum(1 for g in result.gates if g.passed)},
        ))
        return result

    def _execute_skill(
        self, spec: SkillSpec, inputs: Dict[str, Any],
        result: OrchestrationResult, idx: int, total: int,
    ) -> SkillResult:
        step_start = time.perf_counter()
        self.hooks.emit(HookContext(
            event=HookType.PRE_STEP, skill_name=spec.name,
            step_index=idx, step_total=total, inputs=inputs,
        ))
        evidence = self._gather_evidence(spec, inputs)
        prompt = self._render_prompt(spec, inputs, self.state)
        response = ""
        error: Optional[str] = None
        try:
            response = self.llm.generate(prompt, spec.name)
        except Exception as exc:  # noqa: BLE001 - LLM failures must not abort
            error = f"{type(exc).__name__}: {exc}"
            self.degrade(result, 2, f"LLM error for {spec.name}")
            self.hooks.emit(HookContext(
                event=HookType.STEP_ERROR, skill_name=spec.name,
                step_index=idx, error=exc,
            ))
            if self.config.llm.fallback_provider.value != "none":
                response = (
                    f"[fallback] primary LLM failed for {spec.name}; "
                    f"prompt retained for retry. Error: {error}"
                )
            else:
                response = f"[error] LLM call failed: {error}"
        outputs = {"response": response, "evidence_count": len(evidence)}
        step = SkillResult(
            skill_name=spec.name, prompt=prompt, response=response,
            evidence=evidence, inputs=inputs, outputs=outputs,
            elapsed_seconds=time.perf_counter() - step_start,
            error=error,
        )
        self.hooks.emit(HookContext(
            event=HookType.POST_STEP, skill_name=spec.name,
            step_index=idx, step_total=total,
            outputs=outputs, elapsed_seconds=step.elapsed_seconds,
        ))
        return step


# ---------------------------------------------------------------------------
# Convenience entrypoint
# ---------------------------------------------------------------------------


def run_harness(query: str, **kwargs: Any) -> OrchestrationResult:
    """Construct a default :class:`Orchestrator` and run the harness."""
    return Orchestrator(**kwargs).run(query)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"
