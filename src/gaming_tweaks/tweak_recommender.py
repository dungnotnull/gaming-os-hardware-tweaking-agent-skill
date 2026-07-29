"""
tweak_recommender.py — Evidence-backed tweak recommendation engine for gaming performance.

Analyzes hardware profiles and generates prioritized tweak recommendations
with stability-vs-gain tradeoffs, risk assessments, and evidence citations.
Applies domain knowledge from SECOND-KNOWLEDGE-BRAIN.md and authoritative sources.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from gaming_tweaks.system_profiler import HardwareProfile
from gaming_tweaks.config_manager import ConfigProfile, ConfigManager, PRESET_PROFILES, TWEAK_CATEGORIES
from gaming_tweaks.logging_setup import get_logger, OperationContext

logger = get_logger(__name__)

EVIDENCE_TIERS = {
    1: "Systematic review / meta-analysis / official standard",
    2: "Peer-reviewed academic paper / RCT",
    3: "Industry report / professional association guideline",
    4: "News / blog / vendor material",
}

RISK_LEVELS = ["Low", "Medium", "High", "Critical"]
IMPACT_LEVELS = ["Minimal", "Moderate", "Significant", "Transformative"]


@dataclass
class TweakRecommendation:
    category: str
    key: str
    current_value: Any
    recommended_value: Any
    impact: str
    risk: str
    evidence_tier: int
    evidence_source: str
    reasoning: str
    reversible: bool = True
    requires_reboot: bool = False
    prerequisites: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)


@dataclass
class TweakPlan:
    name: str
    description: str
    hardware_profile_id: str
    recommendations: List[TweakRecommendation] = field(default_factory=list)
    risk_summary: str = "Low"
    estimated_fps_gain: str = "0-5%"
    estimated_latency_reduction: str = "0-10ms"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    evidence_sources: List[str] = field(default_factory=list)
    rollback_instructions: str = ""
    scenario_analysis: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_config_profile(self) -> ConfigProfile:
        profile = ConfigProfile(
            name=self.name,
            description=self.description,
        )
        for rec in self.recommendations:
            profile.set_tweak(rec.category, rec.key, rec.recommended_value)
        return profile

    def get_risky_recommendations(self) -> List[TweakRecommendation]:
        return [r for r in self.recommendations if r.risk in ("High", "Critical")]

    def get_by_evidence_tier(self, tier: int) -> List[TweakRecommendation]:
        return [r for r in self.recommendations if r.evidence_tier == tier]

    def summary(self) -> str:
        counts = {}
        for r in self.recommendations:
            counts[r.category] = counts.get(r.category, 0) + 1
        parts = [f"{cat}: {cnt}" for cat, cnt in counts.items()]
        return (
            f"TweakPlan({self.name}): {len(self.recommendations)} tweaks, "
            f"risk={self.risk_summary}, fps_gain={self.estimated_fps_gain}, "
            f"latency_reduction={self.estimated_latency_reduction} | {', '.join(parts)}"
        )


class TweakRecommender:
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        self._knowledge_base: Dict[str, List[Dict[str, Any]]] = {
            "input_latency": [
                {
                    "key": "nvidia_reflex",
                    "values": {
                        "nvidia": {"Off": 0, "On": 1, "On + Boost": 2},
                        "amd": {"Disabled": 0, "Enabled": 1},
                    },
                    "impact": "Transformative",
                    "evidence_tier": 1,
                    "source": "NVIDIA Reflex SDK Documentation",
                    "reasoning": "Reduces render queue latency by keeping CPU/GPU in sync. On+Boost prevents GPU clock from dropping.",
                },
                {
                    "key": "max_pre_rendered_frames",
                    "values": {"default": 3, "recommended": 1},
                    "impact": "Significant",
                    "evidence_tier": 2,
                    "source": "MacKenzie & Ware (1993), CHI — Latency in interactive systems",
                    "reasoning": "Lower value = fewer frames queued = less latency. 1 frame is optimal for gaming.",
                },
                {
                    "key": "mouse_polling_rate",
                    "values": {"default": 125, "500": 500, "1000": 1000, "2000": 2000, "4000": 4000, "8000": 8000},
                    "impact": "Significant",
                    "evidence_tier": 1,
                    "source": "Battle(non)sense — Mouse Latency Testing",
                    "reasoning": "1000Hz reduces average input delay by ~8ms vs 125Hz. >2000Hz offers diminishing returns.",
                },
            ],
            "cpu_gpu_scheduling": [
                {
                    "key": "game_mode",
                    "values": {"disabled": False, "enabled": True},
                    "impact": "Moderate",
                    "evidence_tier": 2,
                    "source": "Microsoft Game Mode Documentation / WDDM",
                    "reasoning": "Prioritizes game process scheduling. Reduces CPU contention from background tasks.",
                },
                {
                    "key": "power_plan",
                    "values": {"balanced": "Balanced", "high_performance": "High Performance", "ultimate": "Ultimate Performance"},
                    "impact": "Significant",
                    "evidence_tier": 2,
                    "source": "Microsoft Power Management Documentation",
                    "reasoning": "High Performance prevents core parking and keeps CPU at maximum frequency.",
                },
                {
                    "key": "hardware_accelerated_gpu_scheduling",
                    "values": {"off": False, "on": True},
                    "impact": "Moderate",
                    "evidence_tier": 2,
                    "source": "Microsoft WDDM 2.7 Documentation",
                    "reasoning": "Reduces GPU scheduling overhead. Marginally improves frame pacing.",
                },
            ],
            "memory_storage": [
                {
                    "key": "xmp_profile",
                    "values": {"disabled": False, "enabled": True},
                    "impact": "Significant",
                    "evidence_tier": 2,
                    "source": "Intel XMP Specification / JEDEC DDR Standards",
                    "reasoning": "Running RAM at rated speed improves CPU-bound game performance by 5-15%.",
                },
                {
                    "key": "nvidia_shader_cache",
                    "values": {"off": "Off", "on": "On", "unlimited": "Unlimited"},
                    "impact": "Moderate",
                    "evidence_tier": 3,
                    "source": "NVIDIA Driver Documentation",
                    "reasoning": "Unlimited shader cache reduces shader compilation stutters in-game.",
                },
            ],
            "display": [
                {
                    "key": "vrr_mode",
                    "values": {"off": "Off", "gsync": "G-Sync", "freesync": "FreeSync"},
                    "impact": "Transformative",
                    "evidence_tier": 1,
                    "source": "NVIDIA G-Sync Documentation / VESA Adaptive-Sync Spec",
                    "reasoning": "Eliminates screen tearing without vsync latency penalty. Critical for smooth gameplay.",
                },
                {
                    "key": "vsync",
                    "values": {"off": "Off", "on": "On", "gsync_compatible": "G-Sync Compatible", "fast": "Fast Sync"},
                    "impact": "Significant",
                    "evidence_tier": 2,
                    "source": "Blur Busters — G-SYNC 101: Optimal Settings",
                    "reasoning": "With VRR, enable vsync in driver + cap fps 3 below refresh for tear-free low-latency.",
                },
                {
                    "key": "fps_cap",
                    "values": {"unlimited": 0},
                    "impact": "Significant",
                    "evidence_tier": 2,
                    "source": "Blur Busters — G-SYNC 101 / Frame Pacing Research",
                    "reasoning": "Capping 3fps below refresh minimizes vsync backpressure latency.",
                },
            ],
            "background_services": [
                {
                    "key": "disable_xbox_game_bar",
                    "values": {"enabled": False, "disabled": True},
                    "impact": "Moderate",
                    "evidence_tier": 3,
                    "source": "Microsoft / Gaming community benchmarks",
                    "reasoning": "Game Bar Game DVR can cause periodic micro-stutters. Disabling removes overhead.",
                },
                {
                    "key": "disable_fullscreen_optimizations",
                    "values": {"enabled": False, "disabled": True},
                    "impact": "Moderate",
                    "evidence_tier": 3,
                    "source": "Microsoft Windows Developer Documentation",
                    "reasoning": "Fullscreen optimizations can add input lag in exclusive fullscreen games.",
                },
            ],
            "driver_settings": [
                {
                    "key": "power_management_mode",
                    "values": {"optimal": "Optimal Power", "adaptive": "Adaptive", "max_performance": "Prefer Maximum Performance"},
                    "impact": "Significant",
                    "evidence_tier": 2,
                    "source": "NVIDIA Driver Documentation",
                    "reasoning": "Prefer Max Performance prevents GPU clock from dropping during low-load moments.",
                },
                {
                    "key": "texture_filtering_quality",
                    "values": {"quality": "Quality", "high_quality": "High Quality", "performance": "High Performance"},
                    "impact": "Minimal",
                    "evidence_tier": 3,
                    "source": "NVIDIA Driver Tuning Guide",
                    "reasoning": "Minimal visual difference for competitive gaming. Slight perf gain.",
                },
            ],
        }

    def analyze(self, hardware: HardwareProfile, target_style: str = "competitive",
                risk_tolerance: str = "moderate") -> TweakPlan:
        with OperationContext(logger, "TweakRecommender.analyze",
                             style=target_style, risk=risk_tolerance):
            plan = TweakPlan(
                name=f"Tweak_{target_style}_{hardware.profile_id[:8]}",
                description=f"Gaming tweak plan for {hardware.cpu.model} + {hardware.gpu.model} ({target_style})",
                hardware_profile_id=hardware.profile_id,
            )

            risk_levels = {"low": 0, "moderate": 1, "high": 2, "aggressive": 3}
            allowed_risk = risk_levels.get(risk_tolerance.lower(), 1)

            for category, knowledge_entries in self._knowledge_base.items():
                for entry in knowledge_entries:
                    rec = self._evaluate_tweak(hardware, category, entry, target_style)
                    if rec is None:
                        continue

                    risk_num = risk_levels.get(rec.risk.lower(), 1)
                    if risk_num > allowed_risk:
                        rec.reasoning += " [SKIPPED: exceeds risk tolerance]"
                        continue

                    plan.recommendations.append(rec)

            plan.recommendations.sort(
                key=lambda r: (EVIDENCE_TIERS[r.evidence_tier],
                               {"Transformative": 4, "Significant": 3,
                                "Moderate": 2, "Minimal": 1}.get(r.impact, 0)),
                reverse=True)

            plan.risk_summary = self._calculate_risk_summary(plan.recommendations)
            plan.estimated_fps_gain = self._estimate_fps_gain(plan.recommendations, hardware)
            plan.estimated_latency_reduction = self._estimate_latency_reduction(plan.recommendations)
            plan.scenario_analysis = self._build_scenarios(plan.recommendations, hardware)
            plan.rollback_instructions = (
                "1. Revert NVIDIA Control Panel settings to defaults.\n"
                "2. Re-enable Game Bar (Settings > Gaming > Game Bar).\n"
                "3. Restore power plan to Balanced.\n"
                "4. Re-enable HAGS (Settings > Display > Graphics > Default settings).\n"
                "5. Remove in-game FPS cap.\n"
                "6. Restart PC."
            )
            plan.evidence_sources = list(set(
                r.evidence_source for r in plan.recommendations))

            logger.info("Generated plan: %s", plan.summary())
            return plan

    def _evaluate_tweak(self, hardware: HardwareProfile, category: str,
                        entry: Dict[str, Any],
                        target_style: str) -> Optional[TweakRecommendation]:
        key = entry["key"]

        if key == "nvidia_reflex":
            if hardware.gpu.vendor.upper() != "NVIDIA":
                return None
            return TweakRecommendation(
                category=category,
                key=key,
                current_value="Unknown",
                recommended_value="On + Boost" if target_style == "competitive" else "On",
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "max_pre_rendered_frames":
            return TweakRecommendation(
                category=category,
                key=key,
                current_value=entry["values"]["default"],
                recommended_value=entry["values"]["recommended"],
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "mouse_polling_rate":
            current = hardware.peripherals.mouse_polling_rate_hz
            recommended = min(1000 if target_style == "competitive" else 500, 1000)
            return TweakRecommendation(
                category=category,
                key=key,
                current_value=current,
                recommended_value=recommended,
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "game_mode":
            return TweakRecommendation(
                category=category,
                key=key,
                current_value=hardware.os.game_mode_enabled,
                recommended_value=True,
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "power_plan":
            current = hardware.os.power_plan
            recommended = "High Performance" if target_style else "High Performance"
            return TweakRecommendation(
                category=category,
                key=key,
                current_value=current,
                recommended_value=recommended,
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "hardware_accelerated_gpu_scheduling":
            return TweakRecommendation(
                category=category,
                key=key,
                current_value=hardware.os.hags_enabled,
                recommended_value=True,
                impact=entry["impact"],
                risk="Medium",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
                requires_reboot=True,
            )

        elif key == "xmp_profile":
            return TweakRecommendation(
                category=category,
                key=key,
                current_value=hardware.memory.xmp_enabled,
                recommended_value=True,
                impact=entry["impact"],
                risk="Medium",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
                requires_reboot=True,
                prerequisites=["Enter BIOS/UEFI", "Locate XMP/DOCP setting"],
            )

        elif key == "nvidia_shader_cache":
            if hardware.gpu.vendor.upper() != "NVIDIA":
                return None
            return TweakRecommendation(
                category=category,
                key=key,
                current_value="Default",
                recommended_value=entry["values"]["unlimited"],
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "vrr_mode":
            if hardware.display.supports_vrr or hardware.gpu.supports_gsync:
                vrr_type = "G-Sync" if hardware.gpu.supports_gsync else "FreeSync"
                return TweakRecommendation(
                    category=category,
                    key=key,
                    current_value="Unknown",
                    recommended_value=vrr_type,
                    impact=entry["impact"],
                    risk="Low",
                    evidence_tier=entry["evidence_tier"],
                    evidence_source=entry["source"],
                    reasoning=entry["reasoning"],
                )
            return None

        elif key == "vsync":
            vrr_enabled = hardware.gpu.supports_gsync or hardware.gpu.supports_freesync
            return TweakRecommendation(
                category=category,
                key=key,
                current_value="Unknown",
                recommended_value="G-Sync Compatible" if vrr_enabled else "Off",
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "fps_cap":
            cap = hardware.display.refresh_rate_hz - 3 if hardware.display.refresh_rate_hz > 60 else 0
            return TweakRecommendation(
                category=category,
                key=key,
                current_value="Unlimited",
                recommended_value=f"fps_max {cap}" if cap > 0 else "Unlimited",
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "disable_xbox_game_bar":
            return TweakRecommendation(
                category=category,
                key=key,
                current_value=not hardware.os.game_mode_enabled,
                recommended_value=True,
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "disable_fullscreen_optimizations":
            return TweakRecommendation(
                category=category,
                key=key,
                current_value=False,
                recommended_value=True if target_style == "competitive" else False,
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "power_management_mode":
            if hardware.gpu.vendor.upper() != "NVIDIA":
                return None
            return TweakRecommendation(
                category=category,
                key=key,
                current_value="Optimal Power",
                recommended_value=entry["values"]["max_performance"],
                impact=entry["impact"],
                risk="Medium",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        elif key == "texture_filtering_quality":
            return TweakRecommendation(
                category=category,
                key=key,
                current_value="Quality",
                recommended_value=entry["values"]["performance"],
                impact=entry["impact"],
                risk="Low",
                evidence_tier=entry["evidence_tier"],
                evidence_source=entry["source"],
                reasoning=entry["reasoning"],
            )

        return None

    def _calculate_risk_summary(self, recommendations: List[TweakRecommendation]) -> str:
        risk_scores = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
        if not recommendations:
            return "Low"
        max_risk = max(risk_scores.get(r.risk, 1) for r in recommendations)
        if max_risk >= 4:
            return "Critical"
        elif max_risk >= 3:
            return "High"
        elif max_risk >= 2:
            return "Medium"
        return "Low"

    def _estimate_fps_gain(self, recommendations: List[TweakRecommendation],
                           hardware: HardwareProfile) -> str:
        impact_scores = {"Minimal": 1, "Moderate": 5, "Significant": 10, "Transformative": 15}
        total = sum(impact_scores.get(r.impact, 0) for r in recommendations)
        if total >= 30:
            return "10-20%"
        elif total >= 20:
            return "5-15%"
        elif total >= 10:
            return "3-10%"
        return "0-5%"

    def _estimate_latency_reduction(self, recommendations: List[TweakRecommendation]) -> str:
        latency_keys = {"nvidia_reflex", "max_pre_rendered_frames", "mouse_polling_rate",
                        "vsync", "fps_cap", "vrr_mode"}
        latency_recs = [r for r in recommendations if r.key in latency_keys]
        if len(latency_recs) >= 4:
            return "10-30ms"
        elif len(latency_recs) >= 2:
            return "5-15ms"
        elif len(latency_recs) >= 1:
            return "2-8ms"
        return "0-5ms"

    def _build_scenarios(self, recommendations: List[TweakRecommendation],
                         hardware: HardwareProfile) -> Dict[str, Dict[str, Any]]:
        return {
            "best_case": {
                "description": "All tweaks applied successfully, optimal hardware response",
                "expected_fps_gain": self._estimate_fps_gain(recommendations, hardware),
                "expected_latency_reduction": self._estimate_latency_reduction(recommendations),
                "stability": "Stable if hardware supports all tweaks",
            },
            "base_case": {
                "description": "Core tweaks applied, conservative values where risky",
                "expected_fps_gain": f"{max(0, int(self._estimate_fps_gain(recommendations, hardware).split('-')[0].strip('%')) // 2)}-{max(1, int(self._estimate_fps_gain(recommendations, hardware).split('-')[1].strip('%')) // 2)}%",
                "expected_latency_reduction": self._estimate_latency_reduction(recommendations),
                "stability": "Expected stable with standard hardware",
            },
            "worst_case": {
                "description": "System instability from aggressive tweaks, disabled after reboot",
                "expected_fps_gain": "0% (reverted)",
                "expected_latency_reduction": "No improvement (reverted)",
                "stability": "Unstable — rollback required",
            },
        }

    def recommend_preset(self, preset_name: str) -> Optional[ConfigProfile]:
        if preset_name not in PRESET_PROFILES:
            logger.error("Unknown preset: %s", preset_name)
            return None

        preset = PRESET_PROFILES[preset_name]
        profile = ConfigProfile(
            name=preset_name,
            description=preset["description"],
        )
        for cat, tweaks in preset["tweaks"].items():
            for key, val in tweaks.items():
                profile.set_tweak(cat, key, val)
        return profile
