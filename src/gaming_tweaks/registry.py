"""
registry.py — Skill registry: load, validate, resolve, and list skills.

A skill is a Markdown file (frontmatter + structured sections) under
``skills/``. This module parses each skill file into a :class:`SkillSpec`,
validates its structure against the project's skill standard, and exposes a
:class:`SkillRegistry` for resolution by name, tag, or routing key.

The registry is the single source of truth used by the router/orchestrator.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "SkillSpec",
    "SkillValidationError",
    "SkillRegistry",
    "parse_skill_file",
]


class SkillValidationError(ValueError):
    """Raised when a skill file fails structural validation."""


FM_PATTERN = re.compile(r"^---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)$", re.S)
KEY_VALUE = re.compile(r"^(\w[\w-]*)\s*:\s*(.*)$")


@dataclass
class SkillSpec:
    """In-memory representation of a skill file."""

    name: str
    description: str = ""
    path: str = ""
    role: str = ""
    tools: List[str] = field(default_factory=list)
    gates: List[str] = field(default_factory=list)
    inputs_schema: Dict[str, Any] = field(default_factory=dict)
    outputs_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    category: str = "domain"
    version: str = "1.0.0"
    body_markdown: str = ""
    raw_frontmatter: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "role": self.role,
            "tools": self.tools,
            "gates": self.gates,
            "inputs_schema": self.inputs_schema,
            "outputs_schema": self.outputs_schema,
            "tags": self.tags,
            "category": self.category,
            "version": self.version,
        }


def _parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    m = FM_PATTERN.match(text)
    if not m:
        return {}, text
    fm_text = m.group("fm")
    body = m.group("body")
    fm: Dict[str, str] = {}
    for line in fm_text.splitlines():
        kv = KEY_VALUE.match(line)
        if kv:
            fm[kv.group(1)] = kv.group(2).strip().strip("\"'")
    return fm, body


def _extract_role(body: str) -> str:
    m = re.search(r"## Role & Persona\s*\n+(.*?)(?:\n##|\Z)", body, re.S)
    if not m:
        return ""
    # Take the first non-empty paragraph.
    para = m.group(1).strip().splitlines()
    return " ".join(p.strip() for p in para if p.strip())[:600]


def _extract_tools(body: str) -> List[str]:
    m = re.search(r"## Tools\s*\n+(.*?)(?:\n##|\Z)", body, re.S)
    if not m:
        return []
    block = m.group(1)
    tools: List[str] = []
    for line in block.splitlines():
        line = line.strip(" -*")
        if not line:
            continue
        # Capture names like WebSearch, Read, Skill("..."), Bash
        for match in re.findall(r'(?:`)?([A-Za-z_][\w-]+)(?:`)?', line):
            if match.lower() in {"and", "or", "for", "with", "the"}:
                continue
            if match not in tools:
                tools.append(match)
    return tools


def _extract_gates(body: str) -> List[str]:
    found: List[str] = []
    for g in re.findall(r"\b([UG]\d+)\b", body):
        if g not in found:
            found.append(g)
    return found


def _infer_tags(name: str, description: str, body: str) -> List[str]:
    tags: List[str] = []
    name_l = name.lower()
    if name_l.startswith("sub-"):
        tags.append("sub-skill")
    if name_l == "main" or "harness" in body.lower():
        tags.append("harness")
    desc_l = (description + " " + body).lower()
    keyword_tags = {
        "requirements": "intake",
        "evidence": "evidence",
        "analysis": "analysis",
        "knowledge": "knowledge",
        "advisor": "advisory",
        "synthesis": "advisory",
        "latency": "latency",
        "fps": "fps",
        "tweak": "tweaks",
    }
    for kw, tag in keyword_tags.items():
        if kw in desc_l and tag not in tags:
            tags.append(tag)
    return tags


def _infer_schemas(spec: SkillSpec, body: str) -> SkillSpec:
    """Infer minimal JSON schemas from declared inputs/outputs sections."""
    inputs: Dict[str, Any] = {}
    outputs: Dict[str, Any] = {}
    # Look for "Outputs:" / "Outputs" / "Output Format" declarations.
    out_match = re.search(
        r"Outputs?:?\s*(?:Structured )?(.*?)(?:\n##|\Z)", body, re.S
    )
    if out_match:
        out_text = out_match.group(1)
        for field_name in re.findall(
            r"\{?(\w+)\}?", out_text.split("}")[0] if "{" in out_text else out_text
        ):
            if field_name and field_name not in {"object", "str", "int", "of"}:
                outputs[field_name] = {"type": "string"}
    if not outputs:
        outputs = {"type": "object", "additionalProperties": True}
    if not inputs:
        inputs = {"type": "object", "additionalProperties": True}
    spec.inputs_schema = inputs
    spec.outputs_schema = outputs
    return spec


def parse_skill_file(path: Path, strict: bool = True) -> SkillSpec:
    """Parse a skill markdown file into a :class:`SkillSpec`."""
    if not path.exists():
        raise SkillValidationError(f"skill file not found: {path}")
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    if not fm:
        if strict:
            raise SkillValidationError(f"skill {path} missing frontmatter")
    name = fm.get("name", path.stem)
    description = fm.get("description", "")
    spec = SkillSpec(
        name=name,
        description=description,
        path=str(path),
        body_markdown=body,
        raw_frontmatter=fm,
    )
    spec.role = _extract_role(body)
    spec.tools = _extract_tools(body)
    spec.gates = _extract_gates(body)
    spec.tags = _infer_tags(name, description, body)
    spec = _infer_schemas(spec, body)
    if strict:
        SkillRegistry.validate_spec(spec)
    return spec


class SkillRegistry:
    """Registry that loads and resolves skills from a directory."""

    REQUIRED_SECTIONS = ["Role & Persona", "Workflow", "Output Format"]
    MAIN_ALT_SECTIONS = {"Workflow": {"Harness Execution Protocol"}}

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.skills_dir = skills_dir or Path("skills")
        self._by_name: Dict[str, SkillSpec] = {}
        self._by_tag: Dict[str, List[str]] = {}
        self.logger = logger or logging.getLogger("gaming_tweaks.registry")

    # -- loading ---------------------------------------------------------

    def load(self, strict: bool = True) -> List[SkillSpec]:
        """Load all ``*.md`` skills from ``skills_dir``."""
        self._by_name.clear()
        self._by_tag.clear()
        if not self.skills_dir.exists():
            if strict:
                raise SkillValidationError(
                    f"skills_dir not found: {self.skills_dir}"
                )
            return []
        loaded: List[SkillSpec] = []
        for path in sorted(self.skills_dir.glob("*.md")):
            try:
                spec = parse_skill_file(path, strict=strict)
                if strict:
                    self.validate_spec(spec)
                self._register(spec)
                loaded.append(spec)
            except SkillValidationError as exc:
                if strict:
                    raise
                self.logger.warning("skipping invalid skill %s: %s", path, exc)
        return loaded

    def register(self, spec: SkillSpec) -> None:
        """Register an already-built spec (no file parsing)."""
        self.validate_spec(spec)
        self._register(spec)

    def _register(self, spec: SkillSpec) -> None:
        self._by_name[spec.name] = spec
        for tag in spec.tags:
            self._by_tag.setdefault(tag, []).append(spec.name)

    # -- resolution ------------------------------------------------------

    def get(self, name: str) -> Optional[SkillSpec]:
        return self._by_name.get(name)

    def by_tag(self, tag: str) -> List[SkillSpec]:
        return [self._by_name[n] for n in self._by_tag.get(tag, []) if n in self._by_name]

    def list_skills(self) -> List[str]:
        return sorted(self._by_name)

    def schemas(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._by_name.values()]

    def search(self, query: str) -> List[SkillSpec]:
        """Token-overlap search across name/description/tags."""
        q = set(query.lower().split())
        if not q:
            return []
        scored: List[tuple[int, SkillSpec]] = []
        for spec in self._by_name.values():
            haystack = " ".join(
                [spec.name, spec.description, " ".join(spec.tags), spec.role]
            ).lower()
            score = sum(1 for tok in q if tok in haystack)
            if score > 0:
                scored.append((score, spec))
        scored.sort(key=lambda t: (-t[0], t[1].name))
        return [s for _, s in scored]

    # -- validation ------------------------------------------------------

    @staticmethod
    def validate_spec(spec: SkillSpec) -> None:
        if not spec.name:
            raise SkillValidationError("skill name is required")
        if not spec.description:
            raise SkillValidationError(f"skill '{spec.name}' missing description")
        body = spec.body_markdown
        for section in SkillRegistry.REQUIRED_SECTIONS:
            alts = SkillRegistry.MAIN_ALT_SECTIONS.get(section, set())
            if section not in body and not any(a in body for a in alts):
                raise SkillValidationError(
                    f"skill '{spec.name}' missing required section: {section}"
                )
        if len(body) < 120:
            raise SkillValidationError(
                f"skill '{spec.name}' body too short ({len(body)} chars)"
            )
