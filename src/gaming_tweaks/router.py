"""
router.py — Chain-of-thought intent router for the gaming_tweaks harness.

The router inspects a user query and decides which skill execution plan to
run. It is a rule-based, deterministic router (no LLM call required) that
emits explicit reasoning steps ("chain of thought") so callers can audit the
decision before execution.

Supported plans
---------------
* ``full_pipeline`` — the canonical 5-sub-skill + gate harness (default).
* ``requirements_only`` — only clarify inputs.
* ``evidence_only`` — only fetch data/evidence.
* ``analysis_only`` — only run core OS/hardware optimization.
* ``advisory_only`` — only synthesize a conclusion (assumes prior outputs).
* ``compare`` — two parallel analysis plans for comparison tasks.
* ``knowledge_lookup`` — query the knowledge brain only.
* ``profile_recommender`` — local-only fast path: profile + recommend tweaks.

The router returns an :class:`ExecutionPlan` with an ordered list of skill
names and a list of human-readable reasoning steps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from gaming_tweaks.registry import SkillRegistry

__all__ = [
    "Intent",
    "ExecutionPlan",
    "Router",
    "route",
]


class Intent(str):
    """String subclass holding one of the declared intent constants below."""

    FULL_PIPELINE = "full_pipeline"
    REQUIREMENTS_ONLY = "requirements_only"
    EVIDENCE_ONLY = "evidence_only"
    ANALYSIS_ONLY = "analysis_only"
    ADVISORY_ONLY = "advisory_only"
    COMPARE = "compare"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    PROFILE_RECOMMENDER = "profile_recommender"


# Keyword groups used by the rule-based classifier.
_KEYWORDS = {
    Intent.COMPARE: [
        "compare", "comparison", "vs", "versus", "difference between",
        "so sánh", "so sanh", "khác nhau",
    ],
    Intent.REQUIREMENTS_ONLY: [
        "clarify", "requirements", "what do you need", "inputs",
        "làm rõ", "yêu cầu", "đầu vào",
    ],
    Intent.EVIDENCE_ONLY: [
        "evidence", "sources", "data", "fetch", "research",
        "bằng chứng", "tài liệu", "nguồn",
    ],
    Intent.ANALYSIS_ONLY: [
        "analyze", "optimise", "optimize", "tweak", "latency", "fps",
        "tối ưu", "độ trễ", "fps", "tinh chỉnh",
    ],
    Intent.ADVISORY_ONLY: [
        "conclusion", "verdict", "recommend", "advise", "should i",
        "kết luận", "khuyến nghị", "khuyên",
    ],
    Intent.KNOWLEDGE_LOOKUP: [
        "knowledge", "papers", "research", "cite", "doi", "academic",
        "kiến thức", "bài báo", "học thuật",
    ],
    Intent.PROFILE_RECOMMENDER: [
        "profile", "recommend", "my system", "my pc", "benchmark",
        "hệ thống của tôi", "pc của tôi", "đề xuất",
    ],
}


@dataclass
class ExecutionPlan:
    """A router decision: intent, ordered skills, reasoning, and budget."""

    intent: str
    skills: List[str]
    reasoning: List[str] = field(default_factory=list)
    estimated_tokens: int = 0
    language: str = "en"
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "skills": list(self.skills),
            "reasoning": list(self.reasoning),
            "estimated_tokens": self.estimated_tokens,
            "language": self.language,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }


# Canonical full pipeline execution order.
_FULL_PIPELINE = [
    "sub-gather-requirements",
    "sub-evidence-collector",
    "sub-core-analysis",
    "sub-knowledge-updater",
    "sub-advisor",
]

_TOKEN_BUDGETS = {
    "sub-gather-requirements": 800,
    "sub-evidence-collector": 4000,
    "sub-core-analysis": 6000,
    "sub-knowledge-updater": 2500,
    "sub-advisor": 4000,
}


class Router:
    """Deterministic chain-of-thought router over a :class:`SkillRegistry`."""

    def __init__(self, registry: Optional[SkillRegistry] = None) -> None:
        self.registry = registry

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _detect_language(text: str) -> str:
        vi_chars = "àáảãạăâđèéêìíòóôơùúưý"
        if any(c in text.lower() for c in vi_chars):
            return "vi"
        return "en"

    @staticmethod
    def _score(text: str, keywords: List[str]) -> int:
        lower = text.lower()
        return sum(1 for kw in keywords if kw in lower)

    def _classify(self, text: str) -> tuple[str, float, list[str]]:
        """Return (intent, confidence, reasoning_steps)."""
        reasoning: list[str] = []
        scores = {intent: self._score(text, kws) for intent, kws in _KEYWORDS.items()}
        top_intent = max(scores, key=scores.get)  # type: ignore[arg-type]
        top_score = scores[top_intent]
        reasoning.append(
            f"Keyword scores: { {k: v for k, v in scores.items() if v > 0} }"
        )

        # Explicit comparison handling always wins over analysis_only when
        # two candidate objects are present.
        if scores[Intent.COMPARE] > 0 and "vs" in text.lower() or "so sánh" in text.lower():
            top_intent = Intent.COMPARE
            top_score = scores[Intent.COMPARE]
            reasoning.append("Comparison intent triggered by explicit 'vs/so sánh'.")

        if top_score == 0:
            reasoning.append(
                "No keyword match; falling back to full_pipeline (default)."
            )
            return Intent.FULL_PIPELINE, 0.5, reasoning

        # Disambiguate analysis_only vs profile_recommender when both match.
        if top_intent == Intent.ANALYSIS_ONLY and scores[Intent.PROFILE_RECOMMENDER] >= top_score:
            # If the user references their own system explicitly, prefer the
            # fast profile/recommend path.
            if any(p in text.lower() for p in ["my system", "my pc", "hệ thống của", "pc của"]):
                top_intent = Intent.PROFILE_RECOMMENDER
                reasoning.append("Profile/recommend path preferred (own-system reference).")

        confidence = min(1.0, 0.5 + 0.1 * top_score)
        reasoning.append(f"Selected intent '{top_intent}' with confidence {confidence:.2f}.")
        return top_intent, confidence, reasoning

    def _skills_for(self, intent: str) -> List[str]:
        if intent == Intent.FULL_PIPELINE:
            return list(_FULL_PIPELINE)
        if intent == Intent.REQUIREMENTS_ONLY:
            return ["sub-gather-requirements"]
        if intent == Intent.EVIDENCE_ONLY:
            return ["sub-evidence-collector"]
        if intent == Intent.ANALYSIS_ONLY:
            return ["sub-core-analysis"]
        if intent == Intent.ADVISORY_ONLY:
            return ["sub-advisor"]
        if intent == Intent.KNOWLEDGE_LOOKUP:
            return ["sub-knowledge-updater"]
        if intent == Intent.PROFILE_RECOMMENDER:
            return ["sub-gather-requirements", "sub-core-analysis", "sub-advisor"]
        if intent == Intent.COMPARE:
            # Two analysis passes; the orchestrator runs them with differing
            # preference labels via metadata.
            return [
                "sub-gather-requirements",
                "sub-evidence-collector",
                "sub-core-analysis",
                "sub-knowledge-updater",
                "sub-advisor",
            ]
        return list(_FULL_PIPELINE)

    def _validate_against_registry(self, skills: List[str]) -> List[str]:
        if self.registry is None:
            return skills
        available = set(self.registry.list_skills())
        valid = [s for s in skills if s in available]
        if len(valid) != len(skills):
            missing = set(skills) - available
            # Fall back to full pipeline if a declared skill is unavailable.
            return [s for s in _FULL_PIPELINE if s in available]
        return valid

    # -- public ----------------------------------------------------------

    def route(self, query: str) -> ExecutionPlan:
        """Produce an :class:`ExecutionPlan` for a user query."""
        reasoning: list[str] = []
        reasoning.append(f"Received query ({len(query)} chars).")
        language = self._detect_language(query)
        reasoning.append(f"Detected language: {language}.")
        intent, confidence, class_reasoning = self._classify(query)
        reasoning.extend(class_reasoning)
        skills = self._skills_for(intent)
        skills = self._validate_against_registry(skills)
        if not skills:
            reasoning.append("No valid skills available; plan is empty.")
        estimated = sum(_TOKEN_BUDGETS.get(s, 2000) for s in skills)
        reasoning.append(f"Plan: {skills} (estimated tokens ~{estimated}).")
        metadata: dict = {}
        if intent == Intent.COMPARE:
            metadata["compare_modes"] = ["competitive", "casual"]
            reasoning.append("Comparison plan: will run core analysis for each mode.")
        return ExecutionPlan(
            intent=intent,
            skills=skills,
            reasoning=reasoning,
            estimated_tokens=estimated,
            language=language,
            confidence=confidence,
            metadata=metadata,
        )


def route(query: str, registry: Optional[SkillRegistry] = None) -> ExecutionPlan:
    """Convenience wrapper around :class:`Router.route`."""
    return Router(registry=registry).route(query)
