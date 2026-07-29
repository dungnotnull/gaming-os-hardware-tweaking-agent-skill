"""
test_benchmark_validator.py — Unit tests for BenchmarkValidator and related dataclasses.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from gaming_tweaks.benchmark_validator import (
    BenchmarkValidator,
    BenchmarkResult,
    FrameTimeStats,
    FPSStats,
    LatencyStats,
)


class TestFrameTimeStats:
    def test_defaults(self):
        fts = FrameTimeStats()
        assert fts.min_ms == 0.0
        assert fts.samples == 0

    def test_with_values(self):
        fts = FrameTimeStats(
            min_ms=4.0, max_ms=33.0, avg_ms=8.33, median_ms=8.0,
            p99_ms=16.0, p999_ms=30.0, std_dev_ms=2.5,
            samples=1000, stutter_count=5)
        assert fts.min_ms == 4.0
        assert fts.samples == 1000
        assert fts.stutter_count == 5


class TestFPSStats:
    def test_defaults(self):
        fps = FPSStats()
        assert fps.avg_fps == 0.0

    def test_with_values(self):
        fps = FPSStats(avg_fps=144.0, min_fps=100.0, max_fps=200.0,
                       p1_low_fps=95.0, p01_low_fps=85.0,
                       std_dev_fps=15.0, stability_score=85.0)
        assert fps.avg_fps == 144.0
        assert fps.stability_score == 85.0


class TestBenchmarkValidator:
    def setup_method(self):
        self.validator = BenchmarkValidator()

    def test_creation(self):
        assert self.validator is not None

    def test_analyze_frame_times_empty(self):
        stats = self.validator.analyze_frame_times([])
        assert stats.min_ms == 0.0
        assert stats.samples == 0

    def test_analyze_frame_times_normal(self):
        ft = [8.33, 8.33, 8.50, 8.33, 9.00, 8.33, 16.67, 8.50, 8.33, 8.33]
        stats = self.validator.analyze_frame_times(ft)
        assert stats.samples == 10
        assert stats.min_ms > 0
        assert stats.max_ms >= stats.min_ms
        assert stats.avg_ms > 0
        assert 0 <= stats.std_dev_ms < 100
        assert stats.stutter_count >= 0

    def test_analyze_frame_times_stutter_detection(self):
        ft = [8.33] * 100 + [50.0] * 10
        stats = self.validator.analyze_frame_times(ft)
        assert stats.stutter_count >= 10
        assert stats.p99_ms > 16.0

    def test_analyze_fps_empty(self):
        stats = self.validator.analyze_fps([])
        assert stats.avg_fps == 0.0

    def test_analyze_fps_normal(self):
        fps = [120.0, 118.0, 122.0, 119.0, 121.0, 60.0, 120.0, 120.0]
        stats = self.validator.analyze_fps(fps)
        assert stats.avg_fps > 0
        assert stats.min_fps > 0
        assert stats.max_fps >= stats.min_fps
        assert stats.p1_low_fps > 0
        assert 0 <= stats.stability_score <= 100

    def test_create_result(self):
        ft = [8.33] * 500 + [16.67] * 20 + [33.33] * 5
        result = self.validator.create_result("test_bench", ft)
        assert result.test_name == "test_bench"
        assert result.frame_times.samples == 525
        assert result.fps.avg_fps > 0
        assert result.score >= 0
        assert result.grade in ("S", "A", "B", "C", "D", "F", "N/A")

    def test_create_result_with_latency(self):
        ft = [8.33] * 100
        latency = [15.0, 16.0, 14.0, 18.0, 15.0]
        result = self.validator.create_result(
            "latency_test", ft, latency_ms=latency,
            measurement_method="LDAT")
        assert result.latency.avg_ms > 0
        assert result.latency.measurement_method == "LDAT"

    def test_calculate_score_high_performance(self):
        ft = [4.17] * 1000
        result = self.validator.create_result("high_perf", ft)
        assert result.score > 70
        assert result.grade in ("A", "S", "B")

    def test_calculate_score_low_performance(self):
        ft = [33.33] * 500
        result = self.validator.create_result("low_perf", ft)
        assert result.score < 50
        assert result.grade in ("D", "F", "C")

    def test_assign_grade(self):
        assert self.validator.assign_grade(95) == "S"
        assert self.validator.assign_grade(85) == "A"
        assert self.validator.assign_grade(72) == "B"
        assert self.validator.assign_grade(55) == "C"
        assert self.validator.assign_grade(40) == "D"
        assert self.validator.assign_grade(20) == "F"

    def test_compare_results_improvement(self):
        baseline_ft = [8.33] * 500 + [16.67] * 30
        baseline = self.validator.create_result("baseline", baseline_ft)

        tweaked_ft = [8.33] * 500 + [16.67] * 10
        tweaked = self.validator.create_result("tweaked", tweaked_ft)

        comparison = self.validator.compare_results(baseline, tweaked)
        assert "verdict" in comparison
        assert comparison["fps"]["delta_percent"] >= 0
        assert comparison["frame_times"]["delta_ms"] <= 0

    def test_compare_results_regression(self):
        baseline_ft = [8.33] * 500
        baseline = self.validator.create_result("baseline", baseline_ft)

        tweaked_ft = [8.33] * 300 + [33.33] * 200
        tweaked = self.validator.create_result("tweaked", tweaked_ft)

        comparison = self.validator.compare_results(baseline, tweaked)
        assert "REGRESSION" in comparison["verdict"].upper() or "decreased" in comparison["verdict"].lower() or comparison["fps"]["delta_percent"] <= 0

    def test_result_summary(self):
        ft = [8.33] * 100
        result = self.validator.create_result("summary_test", ft)
        summary = result.summary()
        assert "summary_test" in summary
        assert "FPS" in summary
        assert "Grade" in summary

    def test_result_to_dict(self):
        ft = [8.33] * 50
        result = self.validator.create_result("dict_test", ft)
        d = result.to_dict()
        assert d["test_name"] == "dict_test"
        assert "fps" in d
        assert d["fps"]["avg_fps"] > 0

    def test_result_to_json(self):
        ft = [8.33] * 50
        result = self.validator.create_result("json_test", ft)
        json_str = result.to_json()
        assert "json_test" in json_str

    def test_save_and_load_result(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = BenchmarkValidator(results_dir=Path(tmpdir))
            ft = [8.33] * 100
            result = validator.create_result("save_test", ft)
            path = validator.save_result(result)
            assert path.exists()

            loaded = validator.load_result(path)
            assert loaded is not None
            assert loaded.test_name == "save_test"
            assert loaded.fps.avg_fps > 0

    def test_load_result_nonexistent(self):
        validator = BenchmarkValidator()
        result = validator.load_result(Path("/nonexistent/path.json"))
        assert result is None
