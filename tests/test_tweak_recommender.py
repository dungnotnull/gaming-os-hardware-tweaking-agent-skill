"""
test_tweak_recommender.py — Unit tests for TweakRecommender and TweakPlan.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from gaming_tweaks.system_profiler import (
    HardwareProfile, CPUProfile, GPUProfile, MemoryProfile,
    StorageProfile, DisplayProfile, PeripheralProfile, OSProfile,
)
from gaming_tweaks.tweak_recommender import (
    TweakRecommender, TweakRecommendation, TweakPlan, EVIDENCE_TIERS,
)
from gaming_tweaks.config_manager import ConfigProfile, ConfigManager, PRESET_PROFILES


def _create_test_hardware():
    return HardwareProfile(
        cpu=CPUProfile(model="Intel Core i9-13900K", vendor="Intel",
                       cores_physical=24, cores_logical=32,
                       base_clock_mhz=3000, supports_avx2=True),
        gpu=GPUProfile(model="NVIDIA GeForce RTX 4090", vendor="NVIDIA",
                       vram_mb=24576, supports_reflex=True,
                       supports_gsync=True, supports_freesync=False,
                       max_refresh_hz=240),
        memory=MemoryProfile(total_gb=32.0, speed_mhz=6000, type="DDR5",
                             channels=2, xmp_enabled=True),
        storage=StorageProfile(has_nvme=True, system_drive_type="NVMe SSD"),
        display=DisplayProfile(resolution="2560x1440", refresh_rate_hz=240,
                               supports_vrr=True, supports_gsync=True),
        peripherals=PeripheralProfile(mouse_polling_rate_hz=1000,
                                      keyboard_polling_rate_hz=1000),
        os=OSProfile(name="Windows", version="11", build="22631",
                     power_plan="Balanced", game_mode_enabled=True,
                     hags_enabled=True),
    )


class TestTweakRecommender:
    def test_creation(self):
        tr = TweakRecommender()
        assert tr is not None
        assert tr._knowledge_base is not None

    def test_analyze_competitive(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw, target_style="competitive", risk_tolerance="moderate")
        assert isinstance(plan, TweakPlan)
        assert len(plan.recommendations) > 0
        assert plan.risk_summary in ("Low", "Medium", "High", "Critical")

    def test_analyze_casual(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw, target_style="casual", risk_tolerance="low")
        assert isinstance(plan, TweakPlan)
        for r in plan.recommendations:
            assert r.risk in ("Low",)

    def test_analyze_aggressive(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw, target_style="competitive", risk_tolerance="aggressive")
        assert isinstance(plan, TweakPlan)
        assert any(r.risk in ("Medium", "High") for r in plan.recommendations)

    def test_all_recommendations_have_evidence(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw)
        for r in plan.recommendations:
            assert r.evidence_tier in EVIDENCE_TIERS
            assert r.evidence_source
            assert r.reasoning

    def test_to_config_profile(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw)
        config = plan.to_config_profile()
        assert isinstance(config, ConfigProfile)
        assert len(config.name) > 0

    def test_plan_summary(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw)
        summary = plan.summary()
        assert "TweakPlan" in summary
        assert "tweaks" in summary
        assert "risk" in summary

    def test_get_risky_recommendations(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw, risk_tolerance="aggressive")
        risky = plan.get_risky_recommendations()
        assert isinstance(risky, list)

    def test_get_by_evidence_tier(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw)
        tier1 = plan.get_by_evidence_tier(1)
        assert isinstance(tier1, list)

    def test_amd_gpu_skips_reflex(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        hw.gpu = GPUProfile(model="AMD Radeon RX 7900 XTX", vendor="AMD",
                            vram_mb=24576, supports_reflex=False)
        plan = tr.analyze(hw, risk_tolerance="aggressive")
        reflex_recs = [r for r in plan.recommendations if r.key == "nvidia_reflex"]
        assert len(reflex_recs) == 0

    def test_preset_profiles(self):
        tr = TweakRecommender()
        for name in ["minimal_latency", "balanced_gaming"]:
            profile = tr.recommend_preset(name)
            assert profile is not None
            assert profile.name == name

    def test_preset_unknown(self):
        tr = TweakRecommender()
        profile = tr.recommend_preset("nonexistent")
        assert profile is None

    def test_scenario_analysis_structure(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw)
        assert "best_case" in plan.scenario_analysis
        assert "base_case" in plan.scenario_analysis
        assert "worst_case" in plan.scenario_analysis
        for scenario, data in plan.scenario_analysis.items():
            assert "description" in data
            assert "stability" in data

    def test_evidence_sources_unique(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw)
        assert len(plan.evidence_sources) == len(set(plan.evidence_sources))

    def test_rollback_instructions_present(self):
        tr = TweakRecommender()
        hw = _create_test_hardware()
        plan = tr.analyze(hw)
        assert len(plan.rollback_instructions) > 0
        assert "revert" in plan.rollback_instructions.lower() or "rollback" in plan.rollback_instructions.lower()


class TestTweakRecommendation:
    def test_creation(self):
        r = TweakRecommendation(
            category="input_latency",
            key="test_key",
            current_value="old",
            recommended_value="new",
            impact="Significant",
            risk="Low",
            evidence_tier=1,
            evidence_source="Test Source",
            reasoning="Test reasoning",
        )
        assert r.category == "input_latency"
        assert r.reversible is True
        assert r.requires_reboot is False
