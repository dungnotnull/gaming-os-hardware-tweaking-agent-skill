"""
benchmark_validator.py — Gaming performance benchmark validation and analysis.

Provides tools for collecting, analyzing, and validating gaming performance
benchmarks including FPS metrics, frame times, latency measurements,
and stability indicators across multiple test runs.
"""

import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gaming_tweaks.logging_setup import get_logger, OperationContext

logger = get_logger(__name__)


@dataclass
class FrameTimeStats:
    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0
    median_ms: float = 0.0
    p99_ms: float = 0.0
    p999_ms: float = 0.0
    std_dev_ms: float = 0.0
    samples: int = 0
    stutter_count: int = 0
    stutter_threshold_ms: float = 16.67


@dataclass
class FPSStats:
    avg_fps: float = 0.0
    min_fps: float = 0.0
    max_fps: float = 0.0
    p1_low_fps: float = 0.0
    p01_low_fps: float = 0.0
    std_dev_fps: float = 0.0
    stability_score: float = 0.0


@dataclass
class LatencyStats:
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    reflex_stats: bool = False
    measurement_method: str = "Unknown"


@dataclass
class BenchmarkResult:
    test_name: str
    test_date: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    fps: FPSStats = field(default_factory=FPSStats)
    frame_times: FrameTimeStats = field(default_factory=FrameTimeStats)
    latency: LatencyStats = field(default_factory=LatencyStats)
    gpu_temp_c: float = 0.0
    cpu_temp_c: float = 0.0
    gpu_usage_percent: float = 0.0
    cpu_usage_percent: float = 0.0
    ram_usage_gb: float = 0.0
    vram_usage_mb: float = 0.0
    score: float = 0.0
    grade: str = "N/A"
    notes: List[str] = field(default_factory=list)
    raw_frame_times: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "test_name": self.test_name,
            "test_date": self.test_date,
            "duration_seconds": self.duration_seconds,
            "fps": {
                "avg_fps": self.fps.avg_fps,
                "min_fps": self.fps.min_fps,
                "max_fps": self.fps.max_fps,
                "p1_low_fps": self.fps.p1_low_fps,
                "p01_low_fps": self.fps.p01_low_fps,
                "std_dev_fps": self.fps.std_dev_fps,
                "stability_score": self.fps.stability_score,
            },
            "frame_times": {
                "min_ms": self.frame_times.min_ms,
                "max_ms": self.frame_times.max_ms,
                "avg_ms": self.frame_times.avg_ms,
                "median_ms": self.frame_times.median_ms,
                "p99_ms": self.frame_times.p99_ms,
                "p999_ms": self.frame_times.p999_ms,
                "std_dev_ms": self.frame_times.std_dev_ms,
                "samples": self.frame_times.samples,
                "stutter_count": self.frame_times.stutter_count,
            },
            "latency": {
                "avg_ms": self.latency.avg_ms,
                "min_ms": self.latency.min_ms,
                "max_ms": self.latency.max_ms,
                "p95_ms": self.latency.p95_ms,
                "p99_ms": self.latency.p99_ms,
                "reflex_stats": self.latency.reflex_stats,
                "measurement_method": self.latency.measurement_method,
            },
            "gpu_temp_c": self.gpu_temp_c,
            "cpu_temp_c": self.cpu_temp_c,
            "gpu_usage_percent": self.gpu_usage_percent,
            "cpu_usage_percent": self.cpu_usage_percent,
            "ram_usage_gb": self.ram_usage_gb,
            "vram_usage_mb": self.vram_usage_mb,
            "score": self.score,
            "grade": self.grade,
            "notes": self.notes,
        }
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        return (
            f"{self.test_name}: FPS avg={self.fps.avg_fps:.1f} "
            f"(1% Low={self.fps.p1_low_fps:.1f}, 0.1% Low={self.fps.p01_low_fps:.1f}) | "
            f"Latency avg={self.latency.avg_ms:.1f}ms | "
            f"FT avg={self.frame_times.avg_ms:.1f}ms | "
            f"Grade: {self.grade} ({self.score:.0f})"
        )


class BenchmarkValidator:
    STUTTER_THRESHOLD_MS = 16.67
    DEFAULT_GRADE_THRESHOLDS = {
        "S": (90, float("inf")),
        "A": (80, 90),
        "B": (65, 80),
        "C": (50, 65),
        "D": (35, 50),
        "F": (0, 35),
    }

    def __init__(self, results_dir: Optional[Path] = None):
        self.results_dir = results_dir or Path.home() / ".gaming_tweaks" / "benchmarks"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def analyze_frame_times(self, frame_times_ms: List[float],
                            stutter_threshold: Optional[float] = None) -> FrameTimeStats:
        if not frame_times_ms:
            return FrameTimeStats()

        threshold = stutter_threshold or self.STUTTER_THRESHOLD_MS
        sorted_ft = sorted(frame_times_ms)
        n = len(sorted_ft)

        stats = FrameTimeStats(
            min_ms=min(frame_times_ms),
            max_ms=max(frame_times_ms),
            avg_ms=statistics.mean(frame_times_ms),
            median_ms=statistics.median(frame_times_ms),
            p99_ms=sorted_ft[int(n * 0.99)] if n > 1 else sorted_ft[0],
            p999_ms=sorted_ft[int(n * 0.999)] if n > 1 else sorted_ft[0],
            std_dev_ms=statistics.stdev(frame_times_ms) if n > 1 else 0.0,
            samples=n,
            stutter_count=sum(1 for ft in frame_times_ms if ft > threshold),
            stutter_threshold_ms=threshold,
        )

        logger.debug(
            "Frame time analysis: avg=%.2fms, std=%.2fms, stutters=%d/%d (%.1f%%)",
            stats.avg_ms, stats.std_dev_ms,
            stats.stutter_count, n,
            (stats.stutter_count / n * 100) if n > 0 else 0)
        return stats

    def analyze_fps(self, fps_values: List[float]) -> FPSStats:
        if not fps_values:
            return FPSStats()

        sorted_fps = sorted(fps_values)
        n = len(sorted_fps)

        stats = FPSStats(
            avg_fps=round(statistics.mean(fps_values), 2),
            min_fps=round(min(fps_values), 2),
            max_fps=round(max(fps_values), 2),
            p1_low_fps=round(sorted_fps[max(0, int(n * 0.01))], 2),
            p01_low_fps=round(sorted_fps[max(0, int(n * 0.001))], 2),
            std_dev_fps=round(statistics.stdev(fps_values) if n > 1 else 0.0, 2),
        )

        if stats.avg_fps > 0:
            stats.stability_score = round(
                (1.0 - min(stats.std_dev_fps / stats.avg_fps, 1.0)) * 100, 2)
        else:
            stats.stability_score = 0.0

        return stats

    def calculate_score(self, result: BenchmarkResult) -> float:
        score = 0.0
        max_possible = 100.0

        if result.fps.avg_fps > 0:
            fps_score = min(result.fps.avg_fps / 240.0 * 40.0, 40.0)
            score += fps_score

        if result.fps.stability_score > 0:
            stability_score = result.fps.stability_score / 100.0 * 25.0
            score += stability_score

        if result.fps.p1_low_fps > 0 and result.fps.avg_fps > 0:
            p1_ratio = result.fps.p1_low_fps / result.fps.avg_fps
            consistency_score = p1_ratio * 15.0
            score += consistency_score

        if result.frame_times.avg_ms > 0:
            ft_score = max(0, (1.0 - result.frame_times.avg_ms / 33.33) * 10.0)
            score += ft_score

        if result.frame_times.samples > 0:
            stutter_ratio = result.frame_times.stutter_count / result.frame_times.samples
            stutter_penalty = stutter_ratio * 100 * 0.5
            score -= stutter_penalty

        if result.latency.avg_ms > 0:
            latency_score = max(0, (1.0 - result.latency.avg_ms / 50.0) * 10.0)
            score += latency_score

        return max(0.0, min(score, max_possible))

    def assign_grade(self, score: float,
                     thresholds: Optional[Dict[str, Tuple[float, float]]] = None) -> str:
        t = thresholds or self.DEFAULT_GRADE_THRESHOLDS
        for grade, (low, high) in t.items():
            if low <= score < high:
                return grade
        return "N/A"

    def create_result(self, test_name: str, frame_times_ms: List[float],
                      fps_values: Optional[List[float]] = None,
                      latency_ms: Optional[List[float]] = None,
                      **metadata) -> BenchmarkResult:
        with OperationContext(logger, "BenchmarkValidator.create_result",
                             test=test_name, samples=len(frame_times_ms)):
            if not fps_values:
                fps_values = [1000.0 / ft for ft in frame_times_ms if ft > 0]

            ft_stats = self.analyze_frame_times(frame_times_ms)
            fps_stats = self.analyze_fps(fps_values)

            latency_stats = LatencyStats()
            if latency_ms:
                sl = sorted(latency_ms)
                n = len(sl)
                latency_stats = LatencyStats(
                    avg_ms=round(statistics.mean(latency_ms), 2),
                    min_ms=round(min(latency_ms), 2),
                    max_ms=round(max(latency_ms), 2),
                    p95_ms=round(sl[int(n * 0.95)], 2) if n > 1 else 0,
                    p99_ms=round(sl[int(n * 0.99)], 2) if n > 1 else 0,
                    measurement_method=metadata.get("measurement_method", "Calculated"),
                )

            result = BenchmarkResult(
                test_name=test_name,
                fps=fps_stats,
                frame_times=ft_stats,
                latency=latency_stats,
                raw_frame_times=frame_times_ms,
                metadata=metadata,
            )

            result.score = self.calculate_score(result)
            result.grade = self.assign_grade(result.score)

            logger.info("Benchmark result: %s", result.summary())
            return result

    def compare_results(self, baseline: BenchmarkResult,
                        tweaked: BenchmarkResult) -> Dict[str, Any]:
        if baseline.fps.avg_fps == 0:
            return {"error": "Baseline has zero FPS"}

        comparison = {
            "test_name": f"{tweaked.test_name} vs {baseline.test_name}",
            "fps": {
                "baseline_avg": baseline.fps.avg_fps,
                "tweaked_avg": tweaked.fps.avg_fps,
                "delta_fps": round(tweaked.fps.avg_fps - baseline.fps.avg_fps, 2),
                "delta_percent": round(
                    (tweaked.fps.avg_fps - baseline.fps.avg_fps) / baseline.fps.avg_fps * 100, 2),
                "p1_baseline": baseline.fps.p1_low_fps,
                "p1_tweaked": tweaked.fps.p1_low_fps,
                "p1_delta": round(tweaked.fps.p1_low_fps - baseline.fps.p1_low_fps, 2),
                "stability_baseline": baseline.fps.stability_score,
                "stability_tweaked": tweaked.fps.stability_score,
                "stability_delta": round(
                    tweaked.fps.stability_score - baseline.fps.stability_score, 2),
            },
            "frame_times": {
                "baseline_avg_ms": baseline.frame_times.avg_ms,
                "tweaked_avg_ms": tweaked.frame_times.avg_ms,
                "delta_ms": round(
                    tweaked.frame_times.avg_ms - baseline.frame_times.avg_ms, 2),
                "stutter_reduction": (
                    baseline.frame_times.stutter_count - tweaked.frame_times.stutter_count),
            },
            "score": {
                "baseline": baseline.score,
                "tweaked": tweaked.score,
                "delta": round(tweaked.score - baseline.score, 2),
            },
            "verdict": self._generate_verdict(baseline, tweaked),
        }

        if baseline.latency.avg_ms > 0 and tweaked.latency.avg_ms > 0:
            comparison["latency"] = {
                "baseline_avg_ms": baseline.latency.avg_ms,
                "tweaked_avg_ms": tweaked.latency.avg_ms,
                "delta_ms": round(
                    tweaked.latency.avg_ms - baseline.latency.avg_ms, 2),
                "delta_percent": round(
                    (tweaked.latency.avg_ms - baseline.latency.avg_ms) / baseline.latency.avg_ms * 100, 2),
            }

        return comparison

    def _generate_verdict(self, baseline: BenchmarkResult,
                          tweaked: BenchmarkResult) -> str:
        fps_gain = tweaked.fps.avg_fps - baseline.fps.avg_fps
        stability_delta = tweaked.fps.stability_score - baseline.fps.stability_score

        if fps_gain >= 5 and stability_delta >= 0:
            return "STRONG IMPROVEMENT: Significant FPS gain with maintained stability"
        elif fps_gain >= 2 and stability_delta >= -2:
            return "MODERATE IMPROVEMENT: Measurable FPS gain"
        elif fps_gain >= 0 and stability_delta >= -5:
            return "NEUTRAL: No significant change detected"
        elif stability_delta < -5:
            return "REGRESSION: Stability decreased — investigate tweaks causing variance"
        else:
            return "REGRESSION: Performance decreased — revert changes"

    def save_result(self, result: BenchmarkResult) -> Path:
        fpath = self.results_dir / (
            f"{result.test_name}_{datetime.now():%Y%m%d_%H%M%S}.json")
        fpath.write_text(result.to_json())
        logger.info("Benchmark saved: %s", fpath)
        return fpath

    def load_result(self, path: Path) -> Optional[BenchmarkResult]:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            result = BenchmarkResult(
                test_name=data["test_name"],
                test_date=data.get("test_date", ""),
                fps=FPSStats(**data["fps"]),
                frame_times=FrameTimeStats(**data["frame_times"]),
                latency=LatencyStats(**data["latency"]),
                gpu_temp_c=data.get("gpu_temp_c", 0),
                cpu_temp_c=data.get("cpu_temp_c", 0),
                gpu_usage_percent=data.get("gpu_usage_percent", 0),
                cpu_usage_percent=data.get("cpu_usage_percent", 0),
                ram_usage_gb=data.get("ram_usage_gb", 0),
                vram_usage_mb=data.get("vram_usage_mb", 0),
                score=data.get("score", 0),
                grade=data.get("grade", "N/A"),
                notes=data.get("notes", []),
                metadata=data.get("metadata", {}),
            )
            return result
        except Exception as e:
            logger.error("Failed to load benchmark %s: %s", path, e)
            return None
