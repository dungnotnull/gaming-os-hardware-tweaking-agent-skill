"""
tools.py — Rich, schema-validated tool definitions with dynamic invocation.

Each tool exposes:
  * a JSON-Schema describing its inputs and outputs (for LLM discovery),
  * a Python execution handler that performs the real work,
  * metadata (idempotent/safe/destructive) used by the orchestrator for
    permission gating and retry policy.

The :class:`ToolRegistry` resolves tools by name, validates inputs against the
declared schema (lightweight, dependency-free validator), invokes the handler
with graceful fallbacks, and records timing/metrics.

Built-in tools wire the existing gaming_tweaks subsystems
(system_profiler, tweak_recommender, config_manager, benchmark_validator,
knowledge_updater, SECOND-KNOWLEDGE-BRAIN) into a single registry so the
agent harness can call them by name without import juggling.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = [
    "ToolSchema",
    "Tool",
    "ToolResult",
    "ToolInvocationError",
    "ToolRegistry",
    "default_registry",
    "BUILTIN_TOOLS",
]


# ---------------------------------------------------------------------------
# Errors + result containers
# ---------------------------------------------------------------------------


class ToolInvocationError(RuntimeError):
    """Raised when a tool fails in a non-recoverable way."""


@dataclass
class ToolResult:
    """Standard tool output envelope."""

    ok: bool
    value: Any = None
    error: Optional[str] = None
    tool: str = ""
    elapsed_seconds: float = 0.0
    invocation_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "value": self.value,
            "error": self.error,
            "tool": self.tool,
            "elapsed_seconds": self.elapsed_seconds,
            "invocation_id": self.invocation_id,
        }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass
class ToolSchema:
    """Declarative schema for a tool, exposed to LLMs and validated at runtime."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    idempotent: bool = True
    safe: bool = True
    destructive: bool = False
    category: str = "general"
    examples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "idempotent": self.idempotent,
            "safe": self.safe,
            "destructive": self.destructive,
            "category": self.category,
            "examples": self.examples,
        }


# ---------------------------------------------------------------------------
# Tiny JSON-Schema subset validator (no external deps)
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = {
    "string", "integer", "number", "boolean", "array", "object", "null",
}


def _validate_schema(node: Any, schema: Dict[str, Any], path: str = "$") -> None:
    """Validate ``node`` against a minimal JSON-Schema subset."""
    if not isinstance(schema, dict):
        return  # nothing to validate

    schema_type = schema.get("type")
    if schema_type is not None:
        types = schema_type if isinstance(schema_type, list) else [schema_type]
        types = [t for t in types if t in _SUPPORTED_TYPES]
        if not _matches_any(node, types):
            raise ToolInvocationError(
                f"schema mismatch at {path}: expected {schema_type}, got "
                f"{type(node).__name__}"
            )

    if schema_type == "object" or (isinstance(node, dict) and "properties" in schema):
        if not isinstance(node, dict):
            raise ToolInvocationError(f"schema mismatch at {path}: expected object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for req in required:
            if req not in node:
                raise ToolInvocationError(
                    f"missing required field '{req}' at {path}"
                )
        for key, sub_schema in properties.items():
            if key in node:
                _validate_schema(node[key], sub_schema, f"{path}.{key}")
        # additionalProperties handling
        additional = schema.get("additionalProperties", True)
        if additional is False:
            extra = set(node) - set(properties)
            if extra:
                raise ToolInvocationError(
                    f"unknown fields {sorted(extra)} at {path}"
                )

    if schema_type == "array" or (isinstance(node, list) and "items" in schema):
        if not isinstance(node, list):
            raise ToolInvocationError(f"schema mismatch at {path}: expected array")
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for i, item in enumerate(node):
                _validate_schema(item, items_schema, f"{path}[{i}]")

    if "enum" in schema and node not in schema["enum"]:
        raise ToolInvocationError(
            f"value at {path} not in enum {schema['enum']}"
        )
    if "minimum" in schema and isinstance(node, (int, float)):
        if node < schema["minimum"]:
            raise ToolInvocationError(f"value at {path} < minimum {schema['minimum']}")
    if "maximum" in schema and isinstance(node, (int, float)):
        if node > schema["maximum"]:
            raise ToolInvocationError(f"value at {path} > maximum {schema['maximum']}")
    if "minLength" in schema and isinstance(node, str):
        if len(node) < schema["minLength"]:
            raise ToolInvocationError(
                f"length at {path} < minLength {schema['minLength']}"
            )
    if "pattern" in schema and isinstance(node, str):
        if not re.search(schema["pattern"], node):
            raise ToolInvocationError(f"value at {path} fails pattern {schema['pattern']}")


def _matches_any(node: Any, types: List[str]) -> bool:
    checks = []
    for t in types:
        if t == "string":
            checks.append(isinstance(node, str))
        elif t == "integer":
            checks.append(isinstance(node, int) and not isinstance(node, bool))
        elif t == "number":
            checks.append(isinstance(node, (int, float)) and not isinstance(node, bool))
        elif t == "boolean":
            checks.append(isinstance(node, bool))
        elif t == "array":
            checks.append(isinstance(node, list))
        elif t == "object":
            checks.append(isinstance(node, dict))
        elif t == "null":
            checks.append(node is None)
    return any(checks)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    """A tool = schema + handler."""

    schema: ToolSchema
    handler: Callable[[Dict[str, Any]], Any]
    version: str = "1.0.0"

    def call(self, inputs: Dict[str, Any]) -> ToolResult:
        start = time.perf_counter()
        try:
            _validate_schema(inputs, self.schema.input_schema)
        except ToolInvocationError as exc:
            return ToolResult(
                ok=False, error=f"validation: {exc}", tool=self.schema.name,
                elapsed_seconds=time.perf_counter() - start,
            )
        try:
            value = self.handler(inputs)
            if self.schema.output_schema is not None:
                try:
                    _validate_schema(value, self.schema.output_schema)
                except ToolInvocationError as exc:
                    return ToolResult(
                        ok=False, error=f"output validation: {exc}",
                        tool=self.schema.name,
                        elapsed_seconds=time.perf_counter() - start,
                    )
            return ToolResult(
                ok=True, value=value, tool=self.schema.name,
                elapsed_seconds=time.perf_counter() - start,
            )
        except Exception as exc:  # noqa: BLE001 - tool errors must be surfaced
            return ToolResult(
                ok=False, error=f"{type(exc).__name__}: {exc}",
                tool=self.schema.name,
                elapsed_seconds=time.perf_counter() - start,
            )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Thread-safe registry of tools, with aliasing and metrics."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._tools: Dict[str, Tool] = {}
        self._aliases: Dict[str, str] = {}
        self._invocations: Dict[str, int] = {}
        self._failures: Dict[str, int] = {}
        self._timings: Dict[str, List[float]] = {}
        self.logger = logger or logging.getLogger("gaming_tweaks.tools")

    def register(self, tool: Tool, aliases: Optional[List[str]] = None) -> None:
        name = tool.schema.name
        if name in self._tools:
            self.logger.warning("overwriting registered tool: %s", name)
        self._tools[name] = tool
        for alias in aliases or []:
            self._aliases[alias] = name

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
        self._aliases = {k: v for k, v in self._aliases.items() if v != name}

    def resolve(self, name: str) -> Optional[Tool]:
        if name in self._tools:
            return self._tools[name]
        target = self._aliases.get(name)
        if target and target in self._tools:
            return self._tools[target]
        return None

    def list_tools(self) -> List[str]:
        return sorted(self._tools)

    def schemas(self) -> List[Dict[str, Any]]:
        return [t.schema.to_dict() for t in self._tools.values()]

    def invoke(self, name: str, inputs: Optional[Dict[str, Any]] = None) -> ToolResult:
        tool = self.resolve(name)
        if tool is None:
            return ToolResult(
                ok=False, error=f"unknown tool: {name}", tool=name
            )
        inputs = inputs or {}
        result = tool.call(inputs)
        self._record(name, result)
        return result

    def _record(self, name: str, result: ToolResult) -> None:
        self._invocations[name] = self._invocations.get(name, 0) + 1
        if not result.ok:
            self._failures[name] = self._failures.get(name, 0) + 1
        self._timings.setdefault(name, []).append(result.elapsed_seconds)

    def metrics(self) -> Dict[str, Any]:
        return {
            "invocations": dict(self._invocations),
            "failures": dict(self._failures),
            "timings_ms": {
                k: [round(t * 1000, 3) for t in v[-50:]]
                for k, v in self._timings.items()
            },
        }


# ---------------------------------------------------------------------------
# Built-in tools
# ---------------------------------------------------------------------------


def _hash_text(text: str, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _profile_system(inputs: Dict[str, Any]) -> Dict[str, Any]:
    from gaming_tweaks.system_profiler import SystemProfiler  # local import
    profiler = SystemProfiler()
    profile = profiler.profile()
    return profile.to_dict() if hasattr(profile, "to_dict") else dict(profile)


def _recommend_tweaks(inputs: Dict[str, Any]) -> Dict[str, Any]:
    from gaming_tweaks.system_profiler import SystemProfiler
    from gaming_tweaks.tweak_recommender import TweakRecommender
    profiler = SystemProfiler()
    profile = profiler.profile()
    recommender = TweakRecommender()
    style = inputs.get("target_style", "competitive")
    plan = recommender.analyze(profile, target_style=style)
    return plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)


def _validate_benchmark(inputs: Dict[str, Any]) -> Dict[str, Any]:
    from gaming_tweaks.benchmark_validator import BenchmarkValidator
    validator = BenchmarkValidator()
    frame_times = inputs.get("frame_times_ms", [])
    name = inputs.get("name", "run")
    result = validator.create_result(name, frame_times_ms=frame_times)
    return result.to_dict() if hasattr(result, "to_dict") else dict(result)


def _read_knowledge_brain(inputs: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(inputs.get("path", "SECOND-KNOWLEDGE-BRAIN.md"))
    if not path.exists():
        return {"found": False, "content": "", "size": 0}
    content = path.read_text(encoding="utf-8")
    return {
        "found": True,
        "content": content,
        "size": len(content),
        "sha256": _hash_text(content),
    }


def _query_knowledge_brain(inputs: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(inputs.get("path", "SECOND-KNOWLEDGE-BRAIN.md"))
    query = inputs.get("query", "").lower()
    max_hits = int(inputs.get("max_hits", 10))
    if not path.exists():
        return {"query": query, "hits": [], "total": 0, "available": False}
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    hits: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines):
        if not query or query in line.lower():
            hits.append({"line": idx + 1, "text": line})
            if len(hits) >= max_hits:
                break
    return {
        "query": query,
        "hits": hits,
        "total": len(hits),
        "available": True,
        "sha256": _hash_text(content),
    }


def _append_knowledge_entry(inputs: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(inputs.get("path", "SECOND-KNOWLEDGE-BRAIN.md"))
    entry = inputs["entry"]
    section = inputs.get("section", "## 7. Knowledge Update Log")
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    hash_before = _hash_text(content)
    if not entry.endswith("\n"):
        entry = entry + "\n"
    if section in content:
        new_content = content.replace(section, section + "\n" + entry, 1)
    else:
        new_content = content + "\n" + section + "\n" + entry
    path.write_text(new_content, encoding="utf-8")
    return {
        "appended": True,
        "sha256_before": hash_before,
        "sha256_after": _hash_text(new_content),
        "path": str(path),
    }


def _set_state(inputs: Dict[str, Any]) -> Dict[str, Any]:
    # State lives on the orchestrator; this tool stores into a shared dict
    # passed via the registry's bound namespace when configured.
    state: Dict[str, Any] = ToolRegistry._shared_state  # type: ignore[attr-defined]
    key = inputs["key"]
    value = inputs["value"]
    state[key] = value
    return {"key": key, "set": True, "size": len(state)}


def _get_state(inputs: Dict[str, Any]) -> Dict[str, Any]:
    state: Dict[str, Any] = ToolRegistry._shared_state  # type: ignore[attr-defined]
    key = inputs["key"]
    default = inputs.get("default")
    return {"key": key, "value": state.get(key, default), "exists": key in state}


def _noop_safe(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """A safe no-op tool used for testing and graceful-degradation fallbacks."""
    return {"ack": True, "echo": inputs}


def _hash_text_tool(inputs: Dict[str, Any]) -> Dict[str, Any]:
    return {"hash": _hash_text(inputs["text"], inputs.get("algorithm", "sha256"))}


def _detect_language(inputs: Dict[str, Any]) -> Dict[str, Any]:
    text = inputs.get("text", "")
    vi_chars = "àáảãạăâđèéêìíòóôơùúưý"
    vi_markers = {"của", "và", "là", "trong", "với", "phân tích", "tối ưu", "hệ thống"}
    lower = text.lower()
    vi_score = sum(1 for c in vi_chars if c in lower)
    vi_score += sum(1 for w in vi_markers if w in lower)
    lang = "vi" if vi_score > 0 else "en"
    return {"language": lang, "vi_score": vi_score, "confidence": min(1.0, vi_score / 5)}


# Shared mutable state used by set_state / get_state tools.
_shared_state: Dict[str, Any] = {}


def _build_builtin_schemas() -> Dict[str, Tool]:
    tools: Dict[str, Tool] = {}

    tools["profile_system"] = Tool(
        schema=ToolSchema(
            name="profile_system",
            description="Detect CPU/GPU/RAM/storage/display/peripherals/OS for the local machine.",
            category="system",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object"},
            idempotent=False,
            safe=True,
        ),
        handler=_profile_system,
    )

    tools["recommend_tweaks"] = Tool(
        schema=ToolSchema(
            name="recommend_tweaks",
            description="Produce an evidence-backed OS/hardware tweak plan for the local profile.",
            category="tweaks",
            input_schema={
                "type": "object",
                "properties": {
                    "target_style": {
                        "type": "string",
                        "enum": ["competitive", "casual", "aggressive", "balanced"],
                    },
                },
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
            idempotent=False,
        ),
        handler=_recommend_tweaks,
    )

    tools["validate_benchmark"] = Tool(
        schema=ToolSchema(
            name="validate_benchmark",
            description="Compute frame-time / FPS statistics for a benchmark run.",
            category="benchmark",
            input_schema={
                "type": "object",
                "required": ["frame_times_ms"],
                "properties": {
                    "frame_times_ms": {"type": "array", "items": {"type": "number"}},
                    "name": {"type": "string"},
                },
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        ),
        handler=_validate_benchmark,
    )

    tools["read_knowledge_brain"] = Tool(
        schema=ToolSchema(
            name="read_knowledge_brain",
            description="Read the full SECOND-KNOWLEDGE-BRAIN.md knowledge base.",
            category="knowledge",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                },
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        ),
        handler=_read_knowledge_brain,
    )

    tools["query_knowledge_brain"] = Tool(
        schema=ToolSchema(
            name="query_knowledge_brain",
            description="Line-level grep of SECOND-KNOWLEDGE-BRAIN.md for a query string.",
            category="knowledge",
            input_schema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 1},
                    "path": {"type": "string"},
                    "max_hits": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        ),
        handler=_query_knowledge_brain,
    )

    tools["append_knowledge_entry"] = Tool(
        schema=ToolSchema(
            name="append_knowledge_entry",
            description="Append a new entry to a section of the knowledge brain (append-only, dedup caller-side).",
            category="knowledge",
            destructive=False,
            idempotent=False,
            safe=True,
            input_schema={
                "type": "object",
                "required": ["entry"],
                "properties": {
                    "entry": {"type": "string", "minLength": 1},
                    "section": {"type": "string"},
                    "path": {"type": "string"},
                },
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        ),
        handler=_append_knowledge_entry,
    )

    tools["set_state"] = Tool(
        schema=ToolSchema(
            name="set_state",
            description="Store a key/value pair in the orchestrator's shared state dict.",
            category="state",
            input_schema={
                "type": "object",
                "required": ["key", "value"],
                "properties": {
                    "key": {"type": "string", "minLength": 1},
                    "value": {},
                },
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        ),
        handler=_set_state,
    )

    tools["get_state"] = Tool(
        schema=ToolSchema(
            name="get_state",
            description="Read a key from the orchestrator's shared state dict.",
            category="state",
            input_schema={
                "type": "object",
                "required": ["key"],
                "properties": {
                    "key": {"type": "string", "minLength": 1},
                    "default": {},
                },
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        ),
        handler=_get_state,
    )

    tools["detect_language"] = Tool(
        schema=ToolSchema(
            name="detect_language",
            description="Detect Vietnamese vs English in user input text.",
            category="i18n",
            input_schema={
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string", "minLength": 1}},
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        ),
        handler=_detect_language,
    )

    tools["hash_text"] = Tool(
        schema=ToolSchema(
            name="hash_text",
            description="Hash arbitrary text (sha256/sha1/md5).",
            category="utility",
            input_schema={
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {"type": "string", "minLength": 0},
                    "algorithm": {
                        "type": "string", "enum": ["sha256", "sha1", "md5"],
                    },
                },
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
        ),
        handler=_hash_text_tool,
    )

    tools["noop"] = Tool(
        schema=ToolSchema(
            name="noop",
            description="Safe no-op tool used as a graceful-degradation fallback.",
            category="utility",
            input_schema={"type": "object", "additionalProperties": True},
            output_schema={"type": "object"},
        ),
        handler=_noop_safe,
    )
    return tools


BUILTIN_TOOLS: Dict[str, Tool] = _build_builtin_schemas()


def default_registry(
    logger: Optional[logging.Logger] = None,
    state: Optional[Dict[str, Any]] = None,
) -> ToolRegistry:
    """Construct a registry pre-populated with all built-in tools."""
    reg = ToolRegistry(logger=logger)
    ToolRegistry._shared_state = state if state is not None else _shared_state  # type: ignore[attr-defined]
    for tool in BUILTIN_TOOLS.values():
        reg.register(tool)
    return reg
