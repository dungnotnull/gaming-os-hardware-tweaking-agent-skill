"""
test_system_profiler.py — Unit tests for the SystemProfiler and associated dataclasses.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from gaming_tweaks.system_profiler import (
    SystemProfiler,
    HardwareProfile,
    CPUProfile,
    GPUProfile,
    MemoryProfile,
    StorageProfile,
    DisplayProfile,
    PeripheralProfile,
    OSProfile,
    quick_profile,
)


class TestHardwareProfile:
    def test_creation_defaults(self):
        hp = HardwareProfile()
        assert hp.cpu is not None
        assert hp.gpu is not None
        assert hp.memory is not None
        assert hp.storage is not None
        assert hp.display is not None
        assert hp.peripherals is not None
        assert hp.os is not None
        assert len(hp.profile_id) == 16

    def test_serialization(self):
        hp = HardwareProfile(
            cpu=CPUProfile(model="Test CPU", vendor="Intel", cores_physical=8, cores_logical=16),
            gpu=GPUProfile(model="RTX 4090", vendor="NVIDIA", vram_mb=24576),
            memory=MemoryProfile(total_gb=32.0, speed_mhz=3600, type="DDR4"),
        )
        d = hp.to_dict()
        assert d["cpu"]["model"] == "Test CPU"
        assert d["gpu"]["vram_mb"] == 24576
        assert d["memory"]["total_gb"] == 32.0

    def test_json_serialization(self):
        hp = HardwareProfile()
        json_str = hp.to_json()
        parsed = json.loads(json_str)
        assert "profile_id" in parsed
        assert "cpu" in parsed
        assert parsed["cpu"]["vendor"] == "Unknown"

    def test_profile_id_consistency(self):
        hp1 = HardwareProfile(
            cpu=CPUProfile(model="A"), gpu=GPUProfile(model="B"))
        hp2 = HardwareProfile(
            cpu=CPUProfile(model="A"), gpu=GPUProfile(model="B"))
        assert hp1.profile_id == hp2.profile_id

    def test_profile_id_difference(self):
        hp1 = HardwareProfile(
            cpu=CPUProfile(model="A"), gpu=GPUProfile(model="B"))
        hp2 = HardwareProfile(
            cpu=CPUProfile(model="C"), gpu=GPUProfile(model="B"))
        assert hp1.profile_id != hp2.profile_id


class TestCPUProfile:
    def test_defaults(self):
        cpu = CPUProfile()
        assert cpu.model == "Unknown"
        assert cpu.cores_physical == 0
        assert not cpu.supports_avx2


class TestGPUProfile:
    def test_defaults(self):
        gpu = GPUProfile()
        assert gpu.max_refresh_hz == 60
        assert not gpu.supports_reflex


class TestSystemProfiler:
    def test_creation(self):
        sp = SystemProfiler(use_cache=False)
        assert sp is not None
        assert sp.use_cache is False

    def test_profile_returns_hardware_profile(self):
        sp = SystemProfiler(use_cache=False)
        profile = sp.profile(force_refresh=True)
        assert isinstance(profile, HardwareProfile)
        assert profile.cpu.cores_logical > 0
        assert profile.os.name != "Unknown"

    def test_profile_cpu_basic(self):
        sp = SystemProfiler(use_cache=False)
        cpu = sp._profile_cpu()
        assert isinstance(cpu, CPUProfile)
        assert cpu.cores_logical > 0

    def test_profile_memory_basic(self):
        sp = SystemProfiler(use_cache=False)
        mem = sp._profile_memory()
        assert isinstance(mem, MemoryProfile)
        assert mem.total_gb >= 0

    def test_profile_os_basic(self):
        sp = SystemProfiler(use_cache=False)
        os_prof = sp._profile_os()
        assert isinstance(os_prof, OSProfile)
        assert os_prof.name in ("Windows", "Linux", "Darwin")

    def test_quick_profile(self):
        profile = quick_profile()
        assert isinstance(profile, HardwareProfile)
        assert profile.cpu.cores_logical > 0

    def test_cache_behavior(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            sp = SystemProfiler(use_cache=True, cache_dir=cache_dir)
            profile1 = sp.profile(force_refresh=True)
            profile2 = sp.profile(force_refresh=False)
            assert profile1.profile_date <= profile2.profile_date

    def test_dict_to_profile_roundtrip(self):
        hp = HardwareProfile(
            cpu=CPUProfile(model="Test CPU", vendor="AMD", cores_physical=6, cores_logical=12),
            gpu=GPUProfile(model="RX 7900", vendor="AMD", vram_mb=20480),
            memory=MemoryProfile(total_gb=16.0, speed_mhz=3200, type="DDR4"),
        )
        d = hp.to_dict()
        rebuilt = SystemProfiler._dict_to_profile(SystemProfiler, d)
        assert rebuilt.cpu.model == hp.cpu.model
        assert rebuilt.gpu.vendor == hp.gpu.vendor
        assert rebuilt.memory.total_gb == hp.memory.total_gb


class TestParseWmic:
    def test_parse_wmic_cpu_basic(self):
        sp = SystemProfiler(use_cache=False)
        cpu = CPUProfile()
        output = (
            "Name                                              NumberOfCores  "
            "NumberOfLogicalProcessors  MaxClockSpeed  L3CacheSize  Manufacturer\n"
            "Intel Core i9-13900K                              24             "
            "32                         3000           36864        GenuineIntel"
        )
        result = sp._parse_wmic_cpu(output, cpu)
        assert "Intel" in result.model
        assert result.cores_physical == 24
        assert result.cores_logical == 32
        assert result.base_clock_mhz == 3000.0
        assert "GenuineIntel" in result.vendor

    def test_parse_wmic_gpu_basic(self):
        sp = SystemProfiler(use_cache=False)
        gpu = GPUProfile()
        output = (
            "Name                                              AdapterRAM  "
            "DriverVersion  CurrentRefreshRate\n"
            "NVIDIA GeForce RTX 4080                           4294967296  "
            "31.0.15.3713   144"
        )
        result = sp._parse_wmic_gpu(output, gpu)
        assert "NVIDIA" in result.model
        assert result.vendor == "NVIDIA"

    def test_parse_wmic_cpu_empty(self):
        sp = SystemProfiler(use_cache=False)
        cpu = CPUProfile(model="Original")
        result = sp._parse_wmic_cpu("", cpu)
        assert result.model == "Original"
