"""
hooks.py — Lifecycle, state-sync, and event-emission hooks for the
gaming_tweaks agent orchestrator.

Hooks let external code react to orchestrator lifecycle events without
polluting the core execution loop. They are intentionally side-effectful by
design (logging, metrics, state persistence, event emission) and must be
fast and exception-safe — a failing hook never aborts a skill step.

Registry semantics
------------------
* Hooks are registered with a :class:`HookType`, a name, a priority
  (lower runs first; default 100) and a callable handler.
* ``emit`` runs all registered hooks for an event in priority order, passing
  a :class:`HookContext`. Exceptions are caught, logged, and recorded on the
  context as ``errors`` so the orchestrator can surface them.
* Built-in hooks (logging, metrics, state sync, event emission) are
  constructed via factory functions and can be added with one line.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

__all__ = [
    "HookType",
    "HookContext",
    "Hook",
    "HookError",
    "HookRegistry",
    "EventEmitter",
    "logging_hook",
    "metrics_hook",
    "state_sync_hook",
    "event_emission_hook",
    "default_registry",
]


class HookType(str, Enum):
    """Lifecycle events the orchestrator can emit hooks for."""

    ORCHESTRATION_START = "orchestration.start"
    ORCHESTRATION_END = "orchestration.end"
    PRE_STEP = "step.pre"
    POST_STEP = "step.post"
    STEP_ERROR = "step.error"
    PRE_GATE = "gate.pre"
    POST_GATE = "gate.post"
    GATE_FAIL = "gate.fail"
    PRE_TOOL = "tool.pre"
    POST_TOOL = "tool.post"
    TOOL_ERROR = "tool.error"
    SKILL_RESOLVE = "skill.resolve"
    DEGRADATION = "degradation"
    CONTEXT_OVERFLOW = "context.overflow"
    RETRY = "retry"


@dataclass
class HookContext:
    """Immutable-ish payload passed to every hook handler.

    Handlers are free to mutate ``state`` and ``metadata`` (thread-safe
    copy-on-write is the caller's responsibility) but should treat the other
    fields as read-only.
    """

    event: HookType
    timestamp: float = field(default_factory=time.time)
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    skill_name: str = ""
    step_index: Optional[int] = None
    step_total: Optional[int] = None
    gate_name: str = ""
    tool_name: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    error: Optional[BaseException] = None
    elapsed_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event"] = self.event.value
        if self.error is not None:
            d["error"] = f"{type(self.error).__name__}: {self.error}"
        return d


@dataclass
class Hook:
    """A registered hook: name, type, priority, and handler callable."""

    name: str
    event: HookType
    handler: Callable[[HookContext], None]
    priority: int = 100
    enabled: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.event, HookType):
            self.event = HookType(self.event)
        if self.priority < 0:
            raise ValueError("hook priority must be >= 0")
        if not callable(self.handler):
            raise TypeError("hook handler must be callable")


class HookError(RuntimeError):
    """Raised only when a hook is explicitly told to abort (rare)."""


HookHandler = Callable[[HookContext], None]


class HookRegistry:
    """Thread-safe registry of hooks keyed by event type."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._hooks: Dict[HookType, List[Hook]] = {}
        self._lock = threading.RLock()
        self._emit_count = 0
        self.logger = logger or logging.getLogger("gaming_tweaks.hooks")

    # -- registration ----------------------------------------------------

    def register(
        self,
        event: HookType,
        handler: HookHandler,
        name: str = "",
        priority: int = 100,
        description: str = "",
    ) -> Hook:
        hook = Hook(
            name=name or handler.__name__ or f"hook_{priority}",
            event=event,
            handler=handler,
            priority=priority,
            description=description,
        )
        with self._lock:
            self._hooks.setdefault(hook.event, []).append(hook)
            self._hooks[hook.event].sort(key=lambda h: (h.priority, h.name))
        return hook

    def unregister(self, hook: Hook) -> bool:
        with self._lock:
            bucket = self._hooks.get(hook.event, [])
            if hook in bucket:
                bucket.remove(hook)
                return True
            return False

    def unregister_by_name(self, name: str) -> int:
        removed = 0
        with self._lock:
            for bucket in self._hooks.values():
                before = len(bucket)
                bucket[:] = [h for h in bucket if h.name != name]
                removed += before - len(bucket)
        return removed

    def disable(self, name: str) -> int:
        with self._lock:
            count = 0
            for bucket in self._hooks.values():
                for h in bucket:
                    if h.name == name:
                        h.enabled = False
                        count += 1
            return count

    def enable(self, name: str) -> int:
        with self._lock:
            count = 0
            for bucket in self._hooks.values():
                for h in bucket:
                    if h.name == name:
                        h.enabled = True
                        count += 1
            return count

    def clear(self) -> None:
        with self._lock:
            self._hooks.clear()

    def hooks(self, event: Optional[HookType] = None) -> List[Hook]:
        with self._lock:
            if event is None:
                return [h for bucket in self._hooks.values() for h in bucket]
            return list(self._hooks.get(event, []))

    # -- emission --------------------------------------------------------

    def emit(self, context: HookContext) -> HookContext:
        self._emit_count += 1
        bucket = self.hooks(context.event)
        for hook in bucket:
            if not hook.enabled:
                continue
            try:
                hook.handler(context)
            except HookError:
                raise
            except Exception as exc:  # noqa: BLE001 - hooks must never abort
                context.errors.append(f"{hook.name}: {exc}")
                self.logger.debug(
                    "hook %s raised: %s", hook.name, exc, exc_info=True
                )
        return context

    @property
    def emit_count(self) -> int:
        return self._emit_count


# ---------------------------------------------------------------------------
# Event emitter — a tiny in-process pub/sub backed by the registry.
# ---------------------------------------------------------------------------


class EventEmitter:
    """Buffered event emitter for downstream consumers (UIs, telemetry)."""

    def __init__(self, max_buffer: int = 1000) -> None:
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=max_buffer)
        self._lock = threading.RLock()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def publish(self, context: HookContext) -> None:
        payload = context.to_dict()
        with self._lock:
            self._buffer.append(payload)
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(payload)
            except Exception:  # noqa: BLE001
                pass

    def events(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()


# ---------------------------------------------------------------------------
# Built-in hook factories.
# ---------------------------------------------------------------------------


def logging_hook(
    logger: Optional[logging.Logger] = None,
    level: int = logging.INFO,
) -> Callable[[HookContext], None]:
    """Emit a structured log line for every event."""
    log = logger or logging.getLogger("gaming_tweaks.hooks")

    def _hook(ctx: HookContext) -> None:
        msg = (
            f"hook.event={ctx.event.value} skill={ctx.skill_name} "
            f"step={ctx.step_index}/{ctx.step_total} elapsed={ctx.elapsed_seconds}"
        )
        if ctx.error is not None:
            log.error("%s error=%s", msg, ctx.error)
        else:
            log.log(level, "%s", msg)

    return _hook


def metrics_hook() -> Callable[[HookContext], None]:
    """Aggregate lightweight counters and timings into a shared metrics dict.

    The metrics dict is attached to the hook closure so callers can read it
    afterwards. Use ``metrics_hook.metrics`` to access it.
    """
    metrics: Dict[str, Any] = {
        "events_total": 0,
        "by_event": {},
        "skill_elapsed": {},
        "tool_invocations": {},
        "errors_total": 0,
    }

    def _hook(ctx: HookContext) -> None:
        metrics["events_total"] += 1
        bucket = metrics["by_event"].setdefault(ctx.event.value, 0)
        metrics["by_event"][ctx.event.value] = bucket + 1
        if ctx.error is not None or ctx.errors:
            metrics["errors_total"] += 1
        if ctx.elapsed_seconds is not None and ctx.skill_name:
            metrics["skill_elapsed"].setdefault(ctx.skill_name, []).append(
                ctx.elapsed_seconds
            )
        if ctx.tool_name:
            metrics["tool_invocations"].setdefault(ctx.tool_name, 0)
            metrics["tool_invocations"][ctx.tool_name] += 1

    _hook.metrics = metrics  # type: ignore[attr-defined]
    return _hook


def state_sync_hook(
    state: Dict[str, Any],
    persist_path: Optional[Path] = None,
) -> Callable[[HookContext], None]:
    """Mirror selected step outputs into a shared state dict; optionally persist."""

    def _hook(ctx: HookContext) -> None:
        if not ctx.outputs:
            return
        key = ctx.skill_name or ctx.event.value
        state[key] = dict(ctx.outputs)
        # Last-write-wins for run-level metadata.
        state.setdefault("__runs__", {})
        state["__runs__"][ctx.run_id] = {
            "event": ctx.event.value,
            "ts": ctx.timestamp,
            "skill": ctx.skill_name,
        }
        if persist_path is not None:
            try:
                persist_path.parent.mkdir(parents=True, exist_ok=True)
                persist_path.write_text(
                    json.dumps(state, default=str, indent=2),
                    encoding="utf-8",
                )
            except Exception:  # noqa: BLE001
                pass

    return _hook


def event_emission_hook(emitter: EventEmitter) -> Callable[[HookContext], None]:
    """Forward every context to an :class:`EventEmitter` for consumers."""

    def _hook(ctx: HookContext) -> None:
        emitter.publish(ctx)

    return _hook


# Module-level convenience registry pre-wired with a logging hook.
def default_registry(
    logger: Optional[logging.Logger] = None,
    include_metrics: bool = True,
) -> HookRegistry:
    reg = HookRegistry(logger=logger)
    reg.register(
        HookType.ORCHESTRATION_START, logging_hook(logger), name="startup_log"
    )
    reg.register(
        HookType.STEP_ERROR, logging_hook(logger, logging.ERROR),
        name="error_log", priority=10,
    )
    if include_metrics:
        reg.register(
            HookType.POST_STEP, metrics_hook(), name="post_step_metrics"
        )
    return reg
