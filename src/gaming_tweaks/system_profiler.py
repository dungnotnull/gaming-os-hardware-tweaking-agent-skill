"""
system_profiler.py — Comprehensive hardware and OS profiling for gaming optimization.

Detects CPU, GPU, RAM, storage, display, and peripheral configurations.
Provides structured HardwareProfile objects with gaming-relevant metrics
including CPU core topology, GPU driver versions, memory timings, and
display capabilities (VRR support, refresh rate, resolution).
"""

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gaming_tweaks.logging_setup import get_logger, OperationContext

logger = get_logger(__name__)


@dataclass
class CPUProfile:
    model: str = "Unknown"
    vendor: str = "Unknown"
    cores_physical: int = 0
    cores_logical: int = 0
    base_clock_mhz: float = 0.0
    boost_clock_mhz: float = 0.0
    architecture: str = "Unknown"
    l3_cache_mb: float = 0.0
    tdp_watts: float = 0.0
    instruction_sets: List[str] = field(default_factory=list)
    supports_avx2: bool = False


@dataclass
class GPUProfile:
    model: str = "Unknown"
    vendor: str = "Unknown"
    vram_mb: int = 0
    driver_version: str = "Unknown"
    driver_date: str = "Unknown"
    supports_reflex: bool = False
    supports_dlss: bool = False
    supports_gsync: bool = False
    supports_freesync: bool = False
    max_refresh_hz: int = 60
    gpu_clock_mhz: float = 0.0
    mem_clock_mhz: float = 0.0


@dataclass
class MemoryProfile:
    total_gb: float = 0.0
    speed_mhz: int = 0
    type: str = "Unknown"
    channels: int = 1
    xmp_enabled: bool = False
    available_gb: float = 0.0
    usage_percent: float = 0.0


@dataclass
class StorageProfile:
    drives: List[Dict[str, Any]] = field(default_factory=list)
    has_nvme: bool = False
    system_drive_type: str = "Unknown"


@dataclass
class DisplayProfile:
    resolution: str = "Unknown"
    refresh_rate_hz: int = 60
    supports_vrr: bool = False
    supports_gsync: bool = False
    supports_freesync: bool = False
    supports_hdr: bool = False
    response_time_ms: float = 0.0
    connection_type: str = "Unknown"


@dataclass
class PeripheralProfile:
    mouse_polling_rate_hz: int = 125
    keyboard_polling_rate_hz: int = 125
    mouse_model: str = "Unknown"
    keyboard_model: str = "Unknown"
    controller_connected: bool = False


@dataclass
class OSProfile:
    name: str = "Unknown"
    version: str = "Unknown"
    build: str = "Unknown"
    architecture: str = "Unknown"
    kernel_version: str = "Unknown"
    power_plan: str = "Unknown"
    game_mode_enabled: bool = False
    hags_enabled: bool = False
    background_services_count: int = 0
    startup_items_count: int = 0


@dataclass
class HardwareProfile:
    cpu: CPUProfile = field(default_factory=CPUProfile)
    gpu: GPUProfile = field(default_factory=GPUProfile)
    memory: MemoryProfile = field(default_factory=MemoryProfile)
    storage: StorageProfile = field(default_factory=StorageProfile)
    display: DisplayProfile = field(default_factory=DisplayProfile)
    peripherals: PeripheralProfile = field(default_factory=PeripheralProfile)
    os: OSProfile = field(default_factory=OSProfile)
    profile_id: str = ""
    profile_date: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.profile_id:
            raw = json.dumps(asdict(self), sort_keys=True, default=str)
            self.profile_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if not self.profile_date:
            self.profile_date = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class SystemProfiler:
    def __init__(self, use_cache: bool = True, cache_dir: Optional[Path] = None):
        self.use_cache = use_cache
        self.cache_dir = cache_dir or Path(os.environ.get(
            "GAMING_TWEAKS_CACHE", str(Path.home() / ".gaming_tweaks" / "cache")))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self.cache_dir / "profile_cache.json"

    def profile(self, force_refresh: bool = False) -> HardwareProfile:
        with OperationContext(logger, "SystemProfiler.profile",
                             force_refresh=force_refresh):
            if not force_refresh and self.use_cache and self._cache_file.exists():
                try:
                    cached = json.loads(self._cache_file.read_text())
                    cache_age = (datetime.now() - datetime.fromisoformat(
                        cached.get("profile_date", "2000-01-01"))).total_seconds()
                    if cache_age < 3600:
                        logger.info("Using cached profile (age=%.0fs)", cache_age)
                        return self._dict_to_profile(cached)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning("Cache load failed: %s", e)

            profile = HardwareProfile(
                cpu=self._profile_cpu(),
                gpu=self._profile_gpu(),
                memory=self._profile_memory(),
                storage=self._profile_storage(),
                display=self._profile_display(),
                peripherals=self._profile_peripherals(),
                os=self._profile_os(),
            )
            profile.raw_data = {
                "platform": platform.platform(),
                "python_version": sys.version,
                "uname": list(platform.uname()),
            }
            profile.profile_date = datetime.now().isoformat()

            if self.use_cache:
                self._cache_file.write_text(profile.to_json())
                logger.info("Profile cached to %s", self._cache_file)

            return profile

    def _dict_to_profile(self, data: Dict[str, Any]) -> HardwareProfile:
        return HardwareProfile(
            cpu=CPUProfile(**data.get("cpu", {})),
            gpu=GPUProfile(**data.get("gpu", {})),
            memory=MemoryProfile(**data.get("memory", {})),
            storage=StorageProfile(**data.get("storage", {})),
            display=DisplayProfile(**data.get("display", {})),
            peripherals=PeripheralProfile(**data.get("peripherals", {})),
            os=OSProfile(**data.get("os", {})),
            profile_id=data.get("profile_id", ""),
            profile_date=data.get("profile_date", ""),
            raw_data=data.get("raw_data", {}),
        )

    def _profile_cpu(self) -> CPUProfile:
        cpu = CPUProfile()
        cpu.model = platform.processor() or "Unknown"

        if sys.platform == "win32":
            cpu = self._profile_cpu_windows(cpu)
        elif sys.platform == "linux":
            cpu = self._profile_cpu_linux(cpu)

        cpu.cores_logical = os.cpu_count() or 0
        cpu.cores_physical = cpu.cores_logical // 2 if cpu.cores_logical > 0 else 0

        if "Intel" in cpu.vendor or "GenuineIntel" in cpu.vendor:
            cpu.vendor = "Intel"
            cpu.supports_avx2 = True
        elif "AMD" in cpu.vendor or "AuthenticAMD" in cpu.vendor:
            cpu.vendor = "AMD"
            cpu.supports_avx2 = True

        return cpu

    def _profile_cpu_windows(self, cpu: CPUProfile) -> CPUProfile:
        try:
            import wmi
            c = wmi.WMI()
            for proc in c.Win32_Processor():
                cpu.model = proc.Name.strip() if proc.Name else cpu.model
                cpu.vendor = proc.Manufacturer or cpu.vendor
                cpu.cores_physical = proc.NumberOfCores or cpu.cores_physical
                cpu.cores_logical = proc.NumberOfLogicalProcessors or cpu.cores_logical
                cpu.base_clock_mhz = float(proc.MaxClockSpeed or 0)
                cpu.l3_cache_mb = float(proc.L3CacheSize or 0) / 1024.0
        except ImportError:
            logger.warning("wmi not available, using basic CPU detection")
            result = subprocess.run(
                ["wmic", "cpu", "get", "Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L3CacheSize,Manufacturer"],
                capture_output=True, text=True, timeout=10)
            cpu = self._parse_wmic_cpu(result.stdout, cpu)
        except Exception as e:
            logger.error("Windows CPU profiling failed: %s", e)

        return cpu

    def _parse_wmic_cpu(self, output: str, cpu: CPUProfile) -> CPUProfile:
        lines = [l for l in output.strip().split("\n") if l.strip()]
        if len(lines) < 2:
            return cpu
        header_line = lines[0]
        data_line = lines[1]
        cols = {}
        for col_name in ["Name", "NumberOfCores", "NumberOfLogicalProcessors",
                          "MaxClockSpeed", "L3CacheSize", "Manufacturer"]:
            pos = header_line.find(col_name)
            if pos >= 0:
                cols[col_name] = (pos, pos + len(col_name))
        for col_name, (start, end) in cols.items():
            next_cols = sorted(
                [s for n, (s, e) in cols.items() if s > start],
                key=lambda x: x)
            field_end = next_cols[0] if next_cols else len(data_line)
            value = data_line[start:field_end].strip()
            if not value:
                continue
            try:
                if "NumberOfCores" in col_name:
                    cpu.cores_physical = int(value)
                elif "NumberOfLogicalProcessors" in col_name:
                    cpu.cores_logical = int(value)
                elif "MaxClockSpeed" in col_name:
                    cpu.base_clock_mhz = float(value)
                elif "L3CacheSize" in col_name:
                    cpu.l3_cache_mb = float(value) / 1024.0
                elif "Manufacturer" in col_name:
                    cpu.vendor = value
                elif "Name" in col_name:
                    cpu.model = value
            except (ValueError, IndexError):
                continue
        return cpu

    def _profile_cpu_linux(self, cpu: CPUProfile) -> CPUProfile:
        try:
            cpuinfo = Path("/proc/cpuinfo").read_text()
            for line in cpuinfo.split("\n"):
                if "model name" in line:
                    cpu.model = line.split(":", 1)[1].strip()
                elif "vendor_id" in line:
                    cpu.vendor = line.split(":", 1)[1].strip()
                elif "cpu cores" in line:
                    cpu.cores_physical = int(line.split(":", 1)[1].strip())
                elif "cpu MHz" in line and cpu.base_clock_mhz == 0:
                    cpu.base_clock_mhz = float(line.split(":", 1)[1].strip())
                elif "cache size" in line:
                    match = re.search(r"(\d+)\s*KB", line.split(":", 1)[1])
                    if match:
                        cpu.l3_cache_mb = int(match.group(1)) / 1024.0
            if cpu.cores_physical == 0:
                cpu.cores_physical = cpu.cores_logical // 2
        except Exception as e:
            logger.error("Linux CPU profiling failed: %s", e)
        return cpu

    def _profile_gpu(self) -> GPUProfile:
        gpu = GPUProfile()

        if sys.platform == "win32":
            gpu = self._profile_gpu_windows(gpu)
        elif sys.platform == "linux":
            gpu = self._profile_gpu_linux(gpu)

        gpu.supports_reflex = "NVIDIA" in gpu.vendor.upper()
        gpu.supports_dlss = "NVIDIA" in gpu.vendor.upper() and gpu.vram_mb >= 4096
        gpu.supports_gsync = "NVIDIA" in gpu.vendor.upper()
        gpu.supports_freesync = "AMD" in gpu.vendor.upper()

        return gpu

    def _profile_gpu_windows(self, gpu: GPUProfile) -> GPUProfile:
        try:
            import wmi
            c = wmi.WMI()
            for vid in c.Win32_VideoController():
                if vid.Name:
                    gpu.model = vid.Name.strip()
                    gpu.vendor = "NVIDIA" if "nvidia" in vid.Name.lower() else (
                        "AMD" if "amd" in vid.Name.lower() or "radeon" in vid.Name.lower() else (
                            "Intel" if "intel" in vid.Name.lower() else gpu.vendor))
                    gpu.vram_mb = int(vid.AdapterRAM or 0) // (1024 * 1024)
                    gpu.driver_version = vid.DriverVersion or "Unknown"
                    gpu.max_refresh_hz = int(vid.CurrentRefreshRate or 60)
                    break
        except ImportError:
            logger.warning("wmi not available for GPU profile")
            result = subprocess.run(
                ["wmic", "path", "Win32_VideoController", "get",
                 "Name,AdapterRAM,DriverVersion,CurrentRefreshRate"],
                capture_output=True, text=True, timeout=10)
            gpu = self._parse_wmic_gpu(result.stdout, gpu)
        except Exception as e:
            logger.error("Windows GPU profiling failed: %s", e)

        return gpu

    def _parse_wmic_gpu(self, output: str, gpu: GPUProfile) -> GPUProfile:
        lines = [l for l in output.strip().split("\n") if l.strip()]
        if len(lines) < 2:
            return gpu
        header_line = lines[0]
        data_line = lines[1]
        cols = {}
        for col_name in ["Name", "AdapterRAM", "DriverVersion", "CurrentRefreshRate"]:
            pos = header_line.find(col_name)
            if pos >= 0:
                cols[col_name] = (pos, pos + len(col_name))
        for col_name, (start, end) in cols.items():
            next_cols = sorted(
                [s for n, (s, e) in cols.items() if s > start],
                key=lambda x: x)
            field_end = next_cols[0] if next_cols else len(data_line)
            value = data_line[start:field_end].strip()
            if not value or col_name != "Name":
                continue
            gpu.model = value
            gpu.vendor = "NVIDIA" if "nvidia" in value.lower() else (
                "AMD" if "amd" in value.lower() or "radeon" in value.lower() else gpu.vendor)
        return gpu

    def _profile_gpu_linux(self, gpu: GPUProfile) -> GPUProfile:
        try:
            result = subprocess.run(
                ["lspci", "-v"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.split("\n"):
                if "VGA" in line or "3D" in line:
                    gpu.model = line.split(":")[-1].strip()
                    gpu.vendor = "NVIDIA" if "nvidia" in line.lower() else (
                        "AMD" if "amd" in line.lower() or "radeon" in line.lower() else (
                            "Intel" if "intel" in line.lower() else gpu.vendor))
                    break
        except Exception:
            pass

        try:
            nvidia_smi = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10)
            if nvidia_smi.returncode == 0 and nvidia_smi.stdout.strip():
                parts = [p.strip() for p in nvidia_smi.stdout.strip().split(",")]
                if len(parts) >= 1:
                    gpu.model = parts[0]
                    gpu.vendor = "NVIDIA"
                if len(parts) >= 2:
                    mem_match = re.search(r"(\d+)", parts[1])
                    if mem_match:
                        gpu.vram_mb = int(mem_match.group(1))
                if len(parts) >= 3:
                    gpu.driver_version = parts[2]
        except Exception:
            pass

        return gpu

    def _profile_memory(self) -> MemoryProfile:
        mem = MemoryProfile()

        if sys.platform == "win32":
            mem = self._profile_memory_windows(mem)
        elif sys.platform == "linux":
            mem = self._profile_memory_linux(mem)

        try:
            import psutil
            vm = psutil.virtual_memory()
            mem.total_gb = round(vm.total / (1024 ** 3), 2)
            mem.available_gb = round(vm.available / (1024 ** 3), 2)
            mem.usage_percent = round(vm.percent, 2)
        except ImportError:
            logger.debug("psutil not available, skipping memory usage")

        return mem

    def _profile_memory_windows(self, mem: MemoryProfile) -> MemoryProfile:
        try:
            import wmi
            c = wmi.WMI()
            for chip in c.Win32_PhysicalMemory():
                mem.total_gb += float(chip.Capacity or 0) / (1024 ** 3)
                mem.speed_mhz = max(mem.speed_mhz, int(chip.Speed or 0))
                if "DDR5" in str(chip.SMBIOSMemoryType or ""):
                    mem.type = "DDR5"
                elif "DDR4" in str(chip.SMBIOSMemoryType or ""):
                    mem.type = "DDR4"
                elif "DDR3" in str(chip.SMBIOSMemoryType or ""):
                    mem.type = "DDR3"
            mem.channels = 2 if mem.total_gb > 0 else 1
        except ImportError:
            logger.warning("wmi not available for memory profile")
        except Exception as e:
            logger.error("Windows memory profiling failed: %s", e)

        return mem

    def _profile_memory_linux(self, mem: MemoryProfile) -> MemoryProfile:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        match = re.search(r"(\d+)", line)
                        if match:
                            mem.total_gb = round(int(match.group(1)) / (1024 ** 2), 2)
                        break

            dmidecode = subprocess.run(
                ["dmidecode", "-t", "memory"], capture_output=True, text=True, timeout=10)
            if dmidecode.returncode == 0:
                for line in dmidecode.stdout.split("\n"):
                    if "Speed:" in line and "Unknown" not in line:
                        match = re.search(r"(\d+)", line)
                        if match:
                            mem.speed_mhz = max(mem.speed_mhz, int(match.group(1)))
                    elif "Type:" in line and "DDR" in line:
                        mem.type = line.split(":")[1].strip()
        except Exception:
            pass

        mem.channels = 2 if mem.total_gb > 0 else 1
        return mem

    def _profile_storage(self) -> StorageProfile:
        storage = StorageProfile()
        drives = []

        try:
            import psutil
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drive_type = "SSD" if "nvme" in part.device.lower() else "HDD"
                    if "nvme" in part.device.lower():
                        storage.has_nvme = True
                    drives.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "total_gb": round(usage.total / (1024 ** 3), 2),
                        "used_gb": round(usage.used / (1024 ** 3), 2),
                        "free_gb": round(usage.free / (1024 ** 3), 2),
                        "type": drive_type,
                        "fstype": part.fstype,
                    })
                except PermissionError:
                    continue
        except ImportError:
            logger.debug("psutil not available for storage profile")

        storage.drives = drives
        storage.system_drive_type = "NVMe SSD" if storage.has_nvme else (
            "SSD" if any(d.get("type") == "SSD" for d in drives) else "HDD")
        return storage

    def _profile_display(self) -> DisplayProfile:
        display = DisplayProfile()

        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    ["wmic", "path", "Win32_VideoController", "get",
                     "CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate"],
                    capture_output=True, text=True, timeout=10)
                lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        display.resolution = f"{parts[0]}x{parts[1]}"
                    if len(parts) >= 3:
                        display.refresh_rate_hz = int(parts[2])
            except Exception as e:
                logger.error("Display profiling failed: %s", e)

        elif sys.platform == "linux":
            try:
                xrandr = subprocess.run(
                    ["xrandr"], capture_output=True, text=True, timeout=10)
                for line in xrandr.stdout.split("\n"):
                    if "*" in line:
                        match = re.search(r"(\d+x\d+).*?(\d+\.?\d*)\*?\+?", line)
                        if match:
                            display.resolution = match.group(1)
                            display.refresh_rate_hz = int(float(match.group(2)))
                            break
            except Exception:
                pass

        display.supports_vrr = display.refresh_rate_hz >= 120
        return display

    def _profile_peripherals(self) -> PeripheralProfile:
        periph = PeripheralProfile()

        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    ["wmic", "path", "Win32_PointingDevice", "get", "Name"],
                    capture_output=True, text=True, timeout=10)
                lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
                if len(lines) >= 2:
                    periph.mouse_model = lines[1]
                    if "gaming" in lines[1].lower() or "logitech" in lines[1].lower() or "razer" in lines[1].lower():
                        periph.mouse_polling_rate_hz = 1000
            except Exception:
                pass

        return periph

    def _profile_os(self) -> OSProfile:
        os_prof = OSProfile()
        os_prof.name = platform.system()
        os_prof.version = platform.release()
        os_prof.architecture = platform.machine()
        os_prof.kernel_version = platform.version()

        if sys.platform == "win32":
            os_prof.build = os.environ.get("OS_BUILD", platform.win32_ver()[1])
            try:
                power_result = subprocess.run(
                    ["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=5)
                for line in power_result.stdout.split("\n"):
                    if "High performance" in line:
                        os_prof.power_plan = "High Performance"
                    elif "Balanced" in line:
                        os_prof.power_plan = "Balanced"
                    elif "Power saver" in line:
                        os_prof.power_plan = "Power Saver"
                if not os_prof.power_plan:
                    os_prof.power_plan = "Unknown"

                game_mode = subprocess.run(
                    ["reg", "query",
                     r"HKCU\Software\Microsoft\GameBar",
                     "/v", "AllowAutoGameMode"],
                    capture_output=True, text=True, timeout=5)
                os_prof.game_mode_enabled = "0x1" in game_mode.stdout

                hags = subprocess.run(
                    ["reg", "query",
                     r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                     "/v", "HwSchMode"],
                    capture_output=True, text=True, timeout=5)
                os_prof.hags_enabled = "0x2" in hags.stdout
            except Exception as e:
                logger.debug("OS profiling details failed: %s", e)

        elif sys.platform == "linux":
            try:
                result = subprocess.run(
                    ["lsb_release", "-d"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    os_prof.build = result.stdout.split(":")[-1].strip()
            except Exception:
                pass

            try:
                with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as f:
                    governor = f.read().strip()
                    os_prof.power_plan = governor
            except Exception:
                os_prof.power_plan = "performance"

        return os_prof


def quick_profile() -> HardwareProfile:
    profiler = SystemProfiler(use_cache=False)
    return profiler.profile(force_refresh=True)
