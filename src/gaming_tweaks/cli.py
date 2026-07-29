"""
cli.py — Command-line interface for gaming-os-hardware-tweaking.

Entry points for system profiling, tweak recommendations, benchmark
validation, and knowledge base updates.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gaming_tweaks.system_profiler import SystemProfiler, quick_profile
from gaming_tweaks.tweak_recommender import TweakRecommender
from gaming_tweaks.config_manager import ConfigManager, PRESET_PROFILES
from gaming_tweaks.benchmark_validator import BenchmarkValidator
from gaming_tweaks.logging_setup import setup_logging

logger = setup_logging("gaming_tweaks.cli")


def main_profile():
    parser = argparse.ArgumentParser(
        description="Profile gaming hardware and OS configuration")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-cache", action="store_true",
                        help="Skip cached profile, force refresh")
    parser.add_argument("--output", "-o", help="Save profile to file")
    args = parser.parse_args()

    profiler = SystemProfiler(use_cache=not args.no_cache)
    profile = profiler.profile(force_refresh=args.no_cache)

    if args.json:
        output = profile.to_json()
    else:
        output = format_profile_human(profile)

    print(output)

    if args.output:
        Path(args.output).write_text(
            profile.to_json() if args.output.endswith(".json") else output,
            encoding="utf-8")
        print(f"\nProfile saved to: {args.output}")


def format_profile_human(profile) -> str:
    p = profile
    lines = [
        "=" * 60,
        f"  GAMING HARDWARE PROFILE — {p.profile_date[:19]}",
        "=" * 60,
        "",
        "--- CPU ---",
        f"  Model:       {p.cpu.model}",
        f"  Vendor:      {p.cpu.vendor}",
        f"  Cores:       {p.cpu.cores_physical}P / {p.cpu.cores_logical}L",
        f"  Base Clock:  {p.cpu.base_clock_mhz:.0f} MHz",
        f"  L3 Cache:    {p.cpu.l3_cache_mb:.1f} MB",
        f"  AVX2:        {'Yes' if p.cpu.supports_avx2 else 'No'}",
        "",
        "--- GPU ---",
        f"  Model:       {p.gpu.model}",
        f"  Vendor:      {p.gpu.vendor}",
        f"  VRAM:        {p.gpu.vram_mb} MB",
        f"  Driver:      {p.gpu.driver_version}",
        f"  G-Sync:      {'Yes' if p.gpu.supports_gsync else 'No'}",
        f"  FreeSync:    {'Yes' if p.gpu.supports_freesync else 'No'}",
        f"  Reflex:      {'Yes' if p.gpu.supports_reflex else 'No'}",
        "",
        "--- Memory ---",
        f"  Total:       {p.memory.total_gb:.1f} GB",
        f"  Available:   {p.memory.available_gb:.1f} GB",
        f"  Type:        {p.memory.type}",
        f"  Speed:       {p.memory.speed_mhz} MHz",
        f"  Channels:    {p.memory.channels}",
        "",
        "--- Display ---",
        f"  Resolution:  {p.display.resolution}",
        f"  Refresh:     {p.display.refresh_rate_hz} Hz",
        f"  VRR:         {'Yes' if p.display.supports_vrr else 'No'}",
        "",
        "--- OS ---",
        f"  OS:          {p.os.name} {p.os.version}",
        f"  Build:       {p.os.build}",
        f"  Power Plan:  {p.os.power_plan}",
        f"  Game Mode:   {'Yes' if p.os.game_mode_enabled else 'No'}",
        f"  HAGS:        {'Yes' if p.os.hags_enabled else 'No'}",
        "",
        "--- Peripherals ---",
        f"  Mouse Rate:  {p.peripherals.mouse_polling_rate_hz} Hz",
        f"  Keyboard Rt: {p.peripherals.keyboard_polling_rate_hz} Hz",
        "",
        f"  Profile ID:  {p.profile_id}",
        "=" * 60,
    ]
    return "\n".join(lines)


def main_recommend():
    parser = argparse.ArgumentParser(
        description="Generate gaming optimization tweak recommendations")
    parser.add_argument("--style", "-s", default="competitive",
                        choices=["competitive", "casual", "balanced"],
                        help="Gaming style (default: competitive)")
    parser.add_argument("--risk", "-r", default="moderate",
                        choices=["low", "moderate", "high", "aggressive"],
                        help="Risk tolerance (default: moderate)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", "-o", help="Save config profile to file")
    parser.add_argument("--preset", "-p",
                        help="Use preset profile instead of analyzing")
    args = parser.parse_args()

    if args.preset:
        recommender = TweakRecommender()
        profile = recommender.recommend_preset(args.preset)
        if profile is None:
            print(f"ERROR: Unknown preset '{args.preset}'. Available: {list(PRESET_PROFILES.keys())}")
            sys.exit(1)

        if args.json:
            print(json.dumps(profile.to_dict(), indent=2))
        else:
            print(format_tweak_profile_human(profile))

        if args.output:
            Path(args.output).write_text(json.dumps(profile.to_dict(), indent=2))
            print(f"\nProfile saved to: {args.output}")
        return

    profiler = SystemProfiler()
    hardware = profiler.profile()

    recommender = TweakRecommender()
    plan = recommender.analyze(hardware, args.style, args.risk)

    if args.json:
        output = json.dumps({
            "plan_name": plan.name,
            "description": plan.description,
            "risk_summary": plan.risk_summary,
            "estimated_fps_gain": plan.estimated_fps_gain,
            "estimated_latency_reduction": plan.estimated_latency_reduction,
            "recommendations": [
                {
                    "category": r.category,
                    "key": r.key,
                    "current": r.current_value,
                    "recommended": r.recommended_value,
                    "impact": r.impact,
                    "risk": r.risk,
                    "evidence_tier": r.evidence_tier,
                    "evidence_source": r.evidence_source,
                    "reasoning": r.reasoning,
                }
                for r in plan.recommendations
            ],
            "scenarios": plan.scenario_analysis,
            "rollback": plan.rollback_instructions,
        }, indent=2)
    else:
        output = format_plan_human(plan, hardware)

    print(output)

    if args.output:
        config = plan.to_config_profile()
        Path(args.output).write_text(json.dumps(config.to_dict(), indent=2))
        print(f"\nTweak plan saved to: {args.output}")


def format_plan_human(plan, hardware) -> str:
    lines = [
        "=" * 70,
        f"  GAMING OPTIMIZATION PLAN — {plan.name}",
        "=" * 70,
        f"  Hardware: {hardware.cpu.model} + {hardware.gpu.model}",
        f"  Risk Level: {plan.risk_summary}",
        f"  Estimated FPS Gain: {plan.estimated_fps_gain}",
        f"  Estimated Latency Reduction: {plan.estimated_latency_reduction}",
        "",
        "--- RECOMMENDATIONS ---",
    ]

    for i, r in enumerate(plan.recommendations, 1):
        lines.append(f"  [{i}] {r.category}/{r.key}")
        lines.append(f"      Current: {r.current_value} → Recommended: {r.recommended_value}")
        lines.append(f"      Impact: {r.impact} | Risk: {r.risk} | Tier: {r.evidence_tier}")
        lines.append(f"      Source: {r.evidence_source}")
        lines.append(f"      Reason: {r.reasoning}")
        if r.requires_reboot:
            lines.append(f"      ⚠ Requires reboot")
        if r.prerequisites:
            lines.append(f"      Prerequisites: {'; '.join(r.prerequisites)}")
        lines.append("")

    lines.append("--- SCENARIOS ---")
    for scenario, data in plan.scenario_analysis.items():
        lines.append(f"  {scenario}: {data['description']}")
        lines.append(f"    FPS: {data['expected_fps_gain']} | Latency: {data['expected_latency_reduction']}")
        lines.append(f"    Stability: {data['stability']}")

    lines.append("")
    lines.append("--- ROLLBACK ---")
    lines.append(plan.rollback_instructions)
    lines.append("=" * 70)

    return "\n".join(lines)


def format_tweak_profile_human(profile) -> str:
    lines = [
        "=" * 60,
        f"  TWEAK PROFILE — {profile.name}",
        "=" * 60,
        f"  Description: {profile.description}",
        f"  Version: {profile.version}",
        "",
    ]
    for cat, tweaks in profile.tweaks.items():
        if tweaks:
            lines.append(f"  [{cat}]")
            for key, val in tweaks.items():
                lines.append(f"    {key}: {val}")
            lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def main_benchmark():
    parser = argparse.ArgumentParser(
        description="Validate gaming benchmark data")
    parser.add_argument("--input", "-i", help="Path to benchmark JSON file")
    parser.add_argument("--compare", "-c", help="Path to second benchmark for comparison")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    validator = BenchmarkValidator()

    if args.input:
        result = validator.load_result(Path(args.input))
        if result is None:
            print(f"ERROR: Could not load benchmark from {args.input}")
            sys.exit(1)
        print(result.summary())
        print(f"  Grade: {result.grade} (Score: {result.score:.1f})")

        if args.compare:
            result2 = validator.load_result(Path(args.compare))
            if result2 is None:
                print(f"ERROR: Could not load comparison benchmark from {args.compare}")
                sys.exit(1)
            comparison = validator.compare_results(result, result2)
            if args.json:
                print(json.dumps(comparison, indent=2))
            else:
                c = comparison
                print("\n--- COMPARISON ---")
                print(f"  FPS: {c['fps']['baseline_avg']:.1f} → {c['fps']['tweaked_avg']:.1f} "
                      f"({c['fps']['delta_percent']:+.1f}%)")
                print(f"  1% Lows: {c['fps']['p1_baseline']:.1f} → {c['fps']['p1_tweaked']:.1f}")
                print(f"  Stability: {c['fps']['stability_baseline']:.1f} → "
                      f"{c['fps']['stability_tweaked']:.1f} ({c['fps']['stability_delta']:+.1f})")
                print(f"  Frame Time: {c['frame_times']['baseline_avg_ms']:.2f}ms → "
                      f"{c['frame_times']['tweaked_avg_ms']:.2f}ms "
                      f"({c['frame_times']['delta_ms']:+.2f}ms)")
                print(f"  Stutters Reduced: {c['frame_times']['stutter_reduction']}")
                print(f"  Score: {c['score']['baseline']:.1f} → {c['score']['tweaked']:.1f} "
                      f"({c['score']['delta']:+.1f})")
                print(f"  Verdict: {c['verdict']}")
    else:
        print("No input provided. Use --input to provide a benchmark JSON file.")
        print("Example frame time data for analysis:")
        sample_ft = [8.33, 8.50, 9.00, 8.33, 16.67, 8.50, 8.33, 33.33, 8.50, 9.00]
        result = validator.create_result("sample_test", sample_ft)
        print(f"  {result.summary()}")


def main_update_kb():
    parser = argparse.ArgumentParser(
        description="Run knowledge base update pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing")
    parser.add_argument("--news-only", action="store_true",
                        help="Only fetch news/RSS, skip academic sources")
    args = parser.parse_args()

    tools_dir = Path(__file__).resolve().parent.parent.parent / "tools"
    updater = tools_dir / "knowledge_updater.py"

    if not updater.exists():
        print(f"ERROR: knowledge_updater.py not found at {updater}")
        sys.exit(1)

    import subprocess
    cmd = [sys.executable, str(updater)]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.news_only:
        cmd.append("--news-only")

    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"Update failed with code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main_profile()
