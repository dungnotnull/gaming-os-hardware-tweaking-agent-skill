"""
gaming_tweaks — OS & Hardware Tweaking for Gamers (Low Latency & High FPS)

A production-grade Python package for gaming system optimization,
input latency tuning, and FPS maximization through evidence-backed
OS and hardware configuration.
"""

__version__ = "1.1.0"
__author__ = "gaming-os-hardware-tweaking contributors"
__license__ = "MIT"

from gaming_tweaks.system_profiler import SystemProfiler, HardwareProfile
from gaming_tweaks.tweak_recommender import TweakRecommender, TweakPlan
from gaming_tweaks.config_manager import ConfigManager, ConfigProfile
from gaming_tweaks.benchmark_validator import BenchmarkValidator, BenchmarkResult
from gaming_tweaks.logging_setup import setup_logging, get_logger
# Phase 6 ??? flexible agent & skill architecture
from gaming_tweaks.config import AppConfig, load_config
from gaming_tweaks.hooks import HookRegistry, HookContext, HookType
from gaming_tweaks.tools import ToolRegistry, ToolSchema, Tool
from gaming_tweaks.registry import SkillRegistry, SkillSpec
from gaming_tweaks.router import Router, ExecutionPlan
from gaming_tweaks.orchestrator import Orchestrator, OrchestrationResult, OfflineAssemblyBackend, CallableLLMBackend

__all__ = [
    "SystemProfiler",
    "HardwareProfile",
    "TweakRecommender",
    "TweakPlan",
    "ConfigManager",
    "ConfigProfile",
    "BenchmarkValidator",
    "BenchmarkResult",
    "setup_logging",
    "get_logger",
    # Phase 6
    "AppConfig",
    "load_config",
    "HookRegistry",
    "HookContext",
    "HookType",
    "ToolRegistry",
    "ToolSchema",
    "Tool",
    "SkillRegistry",
    "SkillSpec",
    "Router",
    "ExecutionPlan",
    "Orchestrator",
    "OrchestrationResult",
    "OfflineAssemblyBackend",
    "CallableLLMBackend",
]
