"""
config.py Ă¢â‚¬â€ Type-safe configuration management for gaming_tweaks.

Provides layered, validated configuration handling:
  1. Built-in defaults (lowest precedence)
  2. A JSON/TOML config file (e.g. config/*.json)
  3. Environment variables (highest precedence)

All configuration sections are dataclasses with explicit types, runtime
validation, and a single canonical :class:`AppConfig` aggregate. Feature flags,
LLM parameters, knowledge pipeline tuning, logging, and agent orchestration
settings are all handled here so the rest of the codebase imports a single
source of truth.

Design notes
------------
* No third-party config library is required; we rely on ``dataclasses`` and
  the standard library only, keeping the install footprint minimal.
* Unknown keys in config files are rejected in strict mode (default) so that
  typos surface immediately rather than silently being ignored.
* Environment variables are prefixed with ``GAMING_TWEAKS_`` and use
  double-underscore nesting, e.g. ``GAMING_TWEAKS_LLM__MAX_TOKENS``.
* Boolean env vars accept: 1/0, true/false, yes/no, on/off (case-insensitive).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, Union, get_type_hints

__all__ = [
    "LogLevel",
    "ProviderType",
    "AppConfig",
    "LLMConfig",
    "FeatureFlags",
    "KnowledgeConfig",
    "LoggingConfig",
    "OrchestrationConfig",
    "ConfigLoader",
    "ConfigValidationError",
    "load_config",
    "DEFAULT_CONFIG_PATH",
]

DEFAULT_CONFIG_PATH = Path("config/default.json")


class LogLevel(str, Enum):
    """Standard logging levels, exposed as a typed enum."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ProviderType(str, Enum):
    """Supported LLM provider identifiers."""

    CLAUDE = "claude"
    OPENAI = "openai"
    LOCAL = "local"
    NONE = "none"  # offline / harness-only execution


class ConfigValidationError(ValueError):
    """Raised when configuration values fail validation."""


# ---------------------------------------------------------------------------
# Section dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    """LLM parameters used by the orchestrator and any LLM-backed tools."""

    provider: ProviderType = ProviderType.CLAUDE
    model: str = "claude-sonnet-4-5"
    max_tokens: int = 8192
    temperature: float = 0.2
    top_p: float = 0.95
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_backoff_seconds: float = 1.5
    fallback_provider: ProviderType = ProviderType.NONE
    fallback_model: str = ""
    context_window_tokens: int = 200_000
    reserve_output_tokens: int = 2048
    system_prompt_path: str = "references/prompts/system_base.md"

    def __post_init__(self) -> None:
        if not isinstance(self.provider, ProviderType):
            self.provider = ProviderType(self.provider)
        if not isinstance(self.fallback_provider, ProviderType):
            self.fallback_provider = ProviderType(self.fallback_provider)
        if self.max_tokens <= 0:
            raise ConfigValidationError("llm.max_tokens must be > 0")
        if not (0.0 <= self.temperature <= 2.0):
            raise ConfigValidationError("llm.temperature must be in [0.0, 2.0]")
        if not (0.0 < self.top_p <= 1.0):
            raise ConfigValidationError("llm.top_p must be in (0.0, 1.0]")
        if self.max_retries < 0:
            raise ConfigValidationError("llm.max_retries must be >= 0")
        if self.retry_backoff_seconds < 0:
            raise ConfigValidationError("llm.retry_backoff_seconds must be >= 0")
        if self.context_window_tokens <= 0:
            raise ConfigValidationError("llm.context_window_tokens must be > 0")
        if self.reserve_output_tokens < 0:
            raise ConfigValidationError("llm.reserve_output_tokens must be >= 0")
        if self.reserve_output_tokens >= self.context_window_tokens:
            raise ConfigValidationError(
                "llm.reserve_output_tokens must be < context_window_tokens"
            )
        if self.timeout_seconds <= 0:
            raise ConfigValidationError("llm.timeout_seconds must be > 0")

    @property
    def available_input_tokens(self) -> int:
        """Tokens available for prompt input after reserving output budget."""
        return max(0, self.context_window_tokens - self.reserve_output_tokens)


@dataclass
class FeatureFlags:
    """System-wide feature flags for progressive rollout and toggles."""

    enable_web_search: bool = True
    enable_web_fetch: bool = True
    enable_knowledge_crawl: bool = True
    enable_bilingual_output: bool = True
    enable_chain_of_thought_router: bool = True
    enable_hooks: bool = True
    enable_tool_metrics: bool = True
    enable_state_sync: bool = True
    enable_quality_gate_auto_fix: bool = True
    enable_graceful_degradation: bool = True
    strict_evidence_tiers: bool = True
    enforce_disclosure_before_conclusion: bool = True
    max_router_retries: int = 2
    max_gate_retries: int = 2

    def __post_init__(self) -> None:
        if self.max_router_retries < 0:
            raise ConfigValidationError("flags.max_router_retries must be >= 0")
        if self.max_gate_retries < 0:
            raise ConfigValidationError("flags.max_gate_retries must be >= 0")


@dataclass
class KnowledgeConfig:
    """Knowledge pipeline tuning parameters (crawl + dedup + scoring)."""

    brain_path: str = "SECOND-KNOWLEDGE-BRAIN.md"
    sources: List[str] = field(
        default_factory=lambda: [
            "arxiv",
            "semantic_scholar",
            "core_ac_uk",
            "rss",
        ]
    )
    max_results_per_source: int = 25
    request_timeout_seconds: int = 30
    rate_limit_rps: float = 1.0
    rate_limit_jitter_seconds: float = 0.5
    parallel_workers: int = 4
    min_score_threshold: float = 0.15
    dedup_hash_algorithm: str = "sha256"
    max_gap_fill_queries: int = 2
    academic_only: bool = False
    news_only: bool = False
    dry_run: bool = False

    def __post_init__(self) -> None:
        if self.max_results_per_source <= 0:
            raise ConfigValidationError(
                "knowledge.max_results_per_source must be > 0"
            )
        if self.request_timeout_seconds <= 0:
            raise ConfigValidationError("knowledge.request_timeout_seconds must be > 0")
        if self.rate_limit_rps <= 0:
            raise ConfigValidationError("knowledge.rate_limit_rps must be > 0")
        if self.parallel_workers <= 0:
            raise ConfigValidationError("knowledge.parallel_workers must be > 0")
        if self.min_score_threshold < 0 or self.min_score_threshold > 1.0:
            raise ConfigValidationError(
                "knowledge.min_score_threshold must be in [0.0, 1.0]"
            )
        if self.dedup_hash_algorithm not in {"sha256", "sha1", "md5"}:
            raise ConfigValidationError(
                "knowledge.dedup_hash_algorithm must be sha256|sha1|md5"
            )
        if self.max_gap_fill_queries < 0:
            raise ConfigValidationError(
                "knowledge.max_gap_fill_queries must be >= 0"
            )


@dataclass
class LoggingConfig:
    """Structured logging configuration."""

    level: LogLevel = LogLevel.INFO
    log_dir: str = "logs"
    enable_file: bool = True
    enable_console: bool = True
    json_format: bool = False
    max_file_size_mb: int = 10
    backup_count: int = 5
    capture_warnings: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.level, LogLevel):
            self.level = LogLevel(self.level)
        if self.max_file_size_mb <= 0:
            raise ConfigValidationError("logging.max_file_size_mb must be > 0")
        if self.backup_count < 0:
            raise ConfigValidationError("logging.backup_count must be >= 0")


@dataclass
class OrchestrationConfig:
    """Agent / skill orchestration parameters."""

    skills_dir: str = "skills"
    default_language: str = "en"
    supported_languages: List[str] = field(
        default_factory=lambda: ["en", "vi"]
    )
    execution_order: List[str] = field(
        default_factory=lambda: [
            "sub-gather-requirements",
            "sub-evidence-collector",
            "sub-core-analysis",
            "sub-knowledge-updater",
            "sub-advisor",
        ]
    )
    quality_gates: List[str] = field(
        default_factory=lambda: ["U1", "U2", "U3", "U4", "U5", "U6",
                                  "G1", "G2", "G3", "G4"]
    )
    context_token_budget: int = 200_000
    preserve_history_between_steps: bool = True
    max_degradation_level: int = 4

    def __post_init__(self) -> None:
        if self.default_language not in self.supported_languages:
            raise ConfigValidationError(
                "orchestration.default_language must be in supported_languages"
            )
        if self.context_token_budget <= 0:
            raise ConfigValidationError(
                "orchestration.context_token_budget must be > 0"
            )
        if not (0 <= self.max_degradation_level <= 4):
            raise ConfigValidationError(
                "orchestration.max_degradation_level must be in [0, 4]"
            )
        if not self.execution_order:
            raise ConfigValidationError(
                "orchestration.execution_order must be non-empty"
            )
        # De-duplicate quality gates while preserving order.
        seen: set[str] = set()
        deduped: List[str] = []
        for g in self.quality_gates:
            if g not in seen:
                seen.add(g)
                deduped.append(g)
        self.quality_gates = deduped


@dataclass
class AppConfig:
    """Top-level application configuration aggregate."""

    app_name: str = "gaming-os-hardware-tweaking"
    version: str = "1.1.0"
    environment: str = "production"
    debug: bool = False
    llm: LLMConfig = field(default_factory=LLMConfig)
    flags: FeatureFlags = field(default_factory=FeatureFlags)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    orchestration: OrchestrationConfig = field(default_factory=OrchestrationConfig)

    def __post_init__(self) -> None:
        if self.environment not in {"production", "staging", "development", "test"}:
            raise ConfigValidationError(
                "environment must be one of production|staging|development|test"
            )

    def to_dict(self) -> Dict[str, Any]:
        def _conv(obj: Any) -> Any:
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, dict):
                return {k: _conv(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_conv(v) for v in obj]
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _conv(v) for k, v in asdict(obj).items()}
            return obj
        return _conv(asdict(self))


# ---------------------------------------------------------------------------
# Mapping between dataclass fields and (env var, file key)
# ---------------------------------------------------------------------------

_SECTION_TYPES: Dict[str, Type[Any]] = {
    "llm": LLMConfig,
    "flags": FeatureFlags,
    "knowledge": KnowledgeConfig,
    "logging": LoggingConfig,
    "orchestration": OrchestrationConfig,
}


def _coerce(value: Any, target_type: Any) -> Any:
    """Coerce a raw value (str from env, or native from JSON) to target type."""
    origin = getattr(target_type, "__origin__", None)
    args = getattr(target_type, "__args__", ())

    # Enum member: accept value or member.
    if isinstance(target_type, type) and issubclass(target_type, Enum):
        if isinstance(value, target_type):
            return value
        return target_type(value)

    # Optional[X] -> Union[X, None]
    if origin is Union and type(None) in args and len(args) == 2:
        if value is None:
            return None
        inner = args[0]
        return _coerce(value, inner)

    # list[X]
    if origin in (list, List):
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        if not isinstance(value, (list, tuple)):
            raise ConfigValidationError(f"expected list, got {type(value)!r}")
        elem_type = args[0] if args else str
        return [_coerce(v, elem_type) for v in value]

    # dict / Mapping
    if origin in (dict, Dict, Mapping):
        if not isinstance(value, dict):
            raise ConfigValidationError(f"expected dict, got {type(value)!r}")
        return dict(value)

    # Plain primitives.
    if target_type is bool:
        return _parse_bool(value)
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    if target_type is str:
        return str(value)
    # Fallback: return as-is.
    return value


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off", ""}:
            return False
    raise ConfigValidationError(f"cannot parse bool from {value!r}")


def _build_section(
    section_cls: Type[Any], raw: Mapping[str, Any], env_prefix: str
) -> Any:
    """Build a single section dataclass from file + env overlay."""
    merged: Dict[str, Any] = {}
    hints = get_type_hints(section_cls)
    # Start with defaults already present in the no-arg dataclass factory.
    defaults = section_cls()
    for f in fields(section_cls):
        merged[f.name] = getattr(defaults, f.name)

    # Overlay file values.
    for key, val in raw.items():
        if key.startswith("_"):
            continue
        if key not in hints:
            raise ConfigValidationError(
                f"unknown config key '{key}' for section {section_cls.__name__}"
            )
        merged[key] = _coerce(val, hints[key])

    # Overlay env values (env wins).
    for key in hints:
        env_name = f"{env_prefix}_{key}".upper()
        if env_name in os.environ:
            merged[key] = _coerce(os.environ[env_name], hints[key])
    return section_cls(**merged)


def _env_overlay_top(config: AppConfig) -> AppConfig:
    """Apply top-level AppConfig env vars (non-section fields)."""
    hints = get_type_hints(AppConfig)
    for f in fields(AppConfig):
        if f.name in _SECTION_TYPES:
            continue
        env_name = f"GAMING_TWEAKS_{f.name}".upper()
        if env_name in os.environ:
            coerced = _coerce(os.environ[env_name], hints[f.name])
            setattr(config, f.name, coerced)
    return config


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ConfigLoader:
    """Load and validate :class:`AppConfig` from defaults + file + env."""

    ENV_PREFIX = "GAMING_TWEAKS"

    def __init__(self, strict: bool = True) -> None:
        self.strict = strict

    def load(
        self,
        path: Optional[Path | str] = None,
        env_overlay: Optional[Mapping[str, str]] = None,
    ) -> AppConfig:
        file_data: Dict[str, Any] = {}
        resolved_path = Path(path) if path else None
        if resolved_path is not None:
            if not resolved_path.exists():
                if self.strict:
                    raise ConfigValidationError(
                        f"config file not found: {resolved_path}"
                    )
            else:
                file_data = self._read_file(resolved_path)

        # Allow caller-supplied env mapping (mostly for tests).
        if env_overlay is not None:
            for k, v in env_overlay.items():
                os.environ[str(k)] = str(v)

        try:
            sections: Dict[str, Any] = {}
            for section_name, section_cls in _SECTION_TYPES.items():
                raw = file_data.get(section_name, {})
                if not isinstance(raw, dict):
                    raise ConfigValidationError(
                        f"section '{section_name}' must be a mapping"
                    )
                env_prefix = f"{self.ENV_PREFIX}_{section_name}".upper().replace(
                    ".", "_"
                )
                sections[section_name] = _build_section(section_cls, raw, env_prefix)

            top_raw = {
                k: v for k, v in file_data.items() if k not in _SECTION_TYPES and not k.startswith("_")
            }
            top_kwargs: Dict[str, Any] = {}
            top_hints = get_type_hints(AppConfig)
            top_defaults = AppConfig()
            for f in fields(AppConfig):
                if f.name in _SECTION_TYPES:
                    continue
                top_kwargs[f.name] = getattr(top_defaults, f.name)
            for key, val in top_raw.items():
                if key not in top_hints:
                    if self.strict:
                        raise ConfigValidationError(
                            f"unknown top-level config key '{key}'"
                        )
                    continue
                top_kwargs[key] = _coerce(val, top_hints[key])
            config = AppConfig(**top_kwargs, **sections)
            config = _env_overlay_top(config)
            return config
        except ConfigValidationError:
            raise
        except (TypeError, ValueError) as exc:
            raise ConfigValidationError(str(exc)) from exc

    def _read_file(self, path: Path) -> Dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        if suffix in (".toml",):
            try:
                import tomllib  # Python 3.11+
                with path.open("rb") as fh:
                    return tomllib.load(fh)
            except ImportError as exc:  # pragma: no cover
                raise ConfigValidationError(
                    "TOML config requires Python 3.11+ (tomllib)"
                ) from exc
        if suffix == ".yaml" or suffix == ".yml":
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                raise ConfigValidationError(
                    "YAML config requires PyYAML installed"
                ) from exc
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raise ConfigValidationError(f"unsupported config file type: {suffix}")


def load_config(
    path: Optional[Path | str] = None, strict: bool = True
) -> AppConfig:
    """Convenience helper: load config from path (or defaults only) + env."""
    return ConfigLoader(strict=strict).load(path=path)
