"""
config_manager.py — Configuration management for gaming OS/hardware tweaks.

Manages tweak profiles, system settings snapshots, restore points,
and profile comparison. Supports JSON-based profile storage with
validation, diffing, and rollback capabilities.
"""

import json
import re
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from gaming_tweaks.logging_setup import get_logger, OperationContext

logger = get_logger(__name__)

DEFAULT_PROFILES_DIR = Path.home() / ".gaming_tweaks" / "profiles"
DEFAULT_BACKUPS_DIR = Path.home() / ".gaming_tweaks" / "backups"

TWEAK_CATEGORIES = [
    "input_latency",
    "cpu_gpu_scheduling",
    "memory_storage",
    "display",
    "network",
    "power",
    "background_services",
    "driver_settings",
]

CATEGORY_DESCRIPTIONS = {
    "input_latency": "Input latency reduction (Reflex, pre-rendered frames, polling)",
    "cpu_gpu_scheduling": "CPU/GPU scheduling (Game Mode, power plan, affinity)",
    "memory_storage": "Memory & storage optimization (XMP, NVMe, paging)",
    "display": "Display settings (VRR, BFI, refresh rate, resolution)",
    "network": "Network optimization (Nagle, buffer, QoS)",
    "power": "Power management (High Performance, core parking)",
    "background_services": "Background services & startup management",
    "driver_settings": "GPU driver settings (shader cache, texture filtering)",
}


class ConfigProfile:
    def __init__(self, name: str, description: str = "",
                 parent_profile: Optional[str] = None):
        self.name = name
        self.description = description
        self.parent_profile = parent_profile
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.version = 1
        self.tweaks: Dict[str, Dict[str, Any]] = {}
        self.metadata: Dict[str, Any] = {
            "hardware_profile_id": None,
            "os": None,
            "gpu_vendor": None,
            "target_games": [],
            "tags": [],
        }

        for cat in TWEAK_CATEGORIES:
            self.tweaks[cat] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parent_profile": self.parent_profile,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "tweaks": self.tweaks,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigProfile":
        profile = cls(
            name=data["name"],
            description=data.get("description", ""),
            parent_profile=data.get("parent_profile"),
        )
        profile.created_at = data.get("created_at", datetime.now().isoformat())
        profile.updated_at = data.get("updated_at", profile.created_at)
        profile.version = data.get("version", 1)
        profile.tweaks = data.get("tweaks", {})
        profile.metadata = data.get("metadata", profile.metadata)

        for cat in TWEAK_CATEGORIES:
            if cat not in profile.tweaks:
                profile.tweaks[cat] = {}
        return profile

    def get_tweak(self, category: str, key: str, default: Any = None) -> Any:
        return self.tweaks.get(category, {}).get(key, default)

    def set_tweak(self, category: str, key: str, value: Any) -> None:
        if category not in TWEAK_CATEGORIES:
            logger.warning("Unknown category: %s", category)
        self.tweaks.setdefault(category, {})[key] = value
        self.updated_at = datetime.now().isoformat()
        self.version += 1

    def diff(self, other: "ConfigProfile") -> Dict[str, List[Dict[str, Any]]]:
        diffs: Dict[str, List[Dict[str, Any]]] = {"added": [], "removed": [], "changed": []}

        for cat in TWEAK_CATEGORIES:
            my_tweaks = self.tweaks.get(cat, {})
            other_tweaks = other.tweaks.get(cat, {})

            for key, val in other_tweaks.items():
                if key not in my_tweaks:
                    diffs["added"].append({"category": cat, "key": key, "value": val})

            for key in my_tweaks:
                if key not in other_tweaks:
                    diffs["removed"].append({"category": cat, "key": key,
                                             "old_value": my_tweaks[key]})

            for key in set(my_tweaks) & set(other_tweaks):
                if my_tweaks[key] != other_tweaks[key]:
                    diffs["changed"].append({
                        "category": cat,
                        "key": key,
                        "old_value": my_tweaks[key],
                        "new_value": other_tweaks[key],
                    })

        return diffs

    def validate(self) -> List[str]:
        issues = []

        if not re.match(r"^[\w\-\s]{1,128}$", self.name):
            issues.append(f"Invalid profile name: {self.name}")

        if len(self.description) > 1024:
            issues.append("Description exceeds 1024 characters")

        for cat, values in self.tweaks.items():
            if cat not in TWEAK_CATEGORIES:
                issues.append(f"Unknown category: {cat}")
            for key, val in values.items():
                if not isinstance(key, str) or len(key) > 256:
                    issues.append(f"Invalid key in {cat}: {key}")
                if isinstance(val, (dict, list)):
                    try:
                        json.dumps(val)
                    except (TypeError, ValueError):
                        issues.append(f"Non-serializable value in {cat}.{key}")

        return issues


class ConfigManager:
    def __init__(self, profiles_dir: Optional[Path] = None,
                 backups_dir: Optional[Path] = None):
        self.profiles_dir = profiles_dir or DEFAULT_PROFILES_DIR
        self.backups_dir = backups_dir or DEFAULT_BACKUPS_DIR
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, ConfigProfile] = {}
        self._loaded = False

    @property
    def profiles(self) -> Dict[str, ConfigProfile]:
        if not self._loaded:
            self.load_all()
        return self._profiles

    def load_all(self) -> None:
        with OperationContext(logger, "ConfigManager.load_all"):
            self._profiles = {}
            for fpath in self.profiles_dir.glob("*.json"):
                try:
                    data = json.loads(fpath.read_text())
                    profile = ConfigProfile.from_dict(data)
                    self._profiles[profile.name] = profile
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning("Failed to load profile %s: %s", fpath.name, e)
            self._loaded = True
            logger.info("Loaded %d profiles", len(self._profiles))

    def get(self, name: str) -> Optional[ConfigProfile]:
        if name in self.profiles:
            return self.profiles[name]
        fpath = self.profiles_dir / f"{name}.json"
        if fpath.exists():
            try:
                data = json.loads(fpath.read_text())
                profile = ConfigProfile.from_dict(data)
                self._profiles[name] = profile
                return profile
            except Exception as e:
                logger.error("Failed to load profile %s: %s", name, e)
        return None

    def save(self, profile: ConfigProfile) -> bool:
        with OperationContext(logger, "ConfigManager.save", profile=profile.name):
            issues = profile.validate()
            if issues:
                logger.error("Validation failed for %s: %s", profile.name, issues)
                return False

            profile.updated_at = datetime.now().isoformat()

            fpath = self.profiles_dir / f"{profile.name}.json"
            if fpath.exists():
                backup_path = self.backups_dir / (
                    f"{profile.name}_{datetime.now():%Y%m%d_%H%M%S}.json")
                shutil.copy2(fpath, backup_path)
                logger.debug("Backed up to %s", backup_path)

                self._cleanup_old_backups(profile.name, max_backups=10)

            fpath.write_text(json.dumps(profile.to_dict(), indent=2))
            self._profiles[profile.name] = profile
            logger.info("Saved profile: %s (v%d)", profile.name, profile.version)
            return True

    def delete(self, name: str) -> bool:
        fpath = self.profiles_dir / f"{name}.json"
        if fpath.exists():
            backup_path = self.backups_dir / (
                f"{name}_DELETED_{datetime.now():%Y%m%d_%H%M%S}.json")
            shutil.copy2(fpath, backup_path)
            fpath.unlink()
            self._profiles.pop(name, None)
            logger.info("Deleted profile: %s", name)
            return True
        return False

    def list_profiles(self) -> List[Dict[str, Any]]:
        result = []
        for name, profile in self.profiles.items():
            result.append({
                "name": name,
                "description": profile.description,
                "version": profile.version,
                "updated_at": profile.updated_at,
                "tweak_count": sum(len(v) for v in profile.tweaks.values()),
                "tags": profile.metadata.get("tags", []),
            })
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    def diff_profiles(self, name_a: str, name_b: str) -> Optional[Dict[str, Any]]:
        profile_a = self.get(name_a)
        profile_b = self.get(name_b)
        if not profile_a or not profile_b:
            logger.error("Cannot diff: one or both profiles not found")
            return None

        return profile_a.diff(profile_b)

    def rollback(self, name: str, backup_timestamp: Optional[str] = None) -> bool:
        if backup_timestamp:
            backup_path = self.backups_dir / f"{name}_{backup_timestamp}.json"
            if not backup_path.exists():
                logger.error("Backup not found: %s", backup_path)
                return False
            data = json.loads(backup_path.read_text())
            profile = ConfigProfile.from_dict(data)
            return self.save(profile)
        else:
            backups = sorted(
                self.backups_dir.glob(f"{name}_*.json"),
                key=lambda p: p.stat().st_mtime, reverse=True)
            for backup in backups:
                if "_DELETED_" in backup.name:
                    continue
                data = json.loads(backup.read_text())
                profile = ConfigProfile.from_dict(data)
                return self.save(profile)
            return False

    def _cleanup_old_backups(self, name: str, max_backups: int = 10) -> None:
        backups = sorted(
            self.backups_dir.glob(f"{name}_*.json"),
            key=lambda p: p.stat().st_mtime)
        while len(backups) > max_backups:
            backups[0].unlink()
            backups.pop(0)


PRESET_PROFILES = {
    "minimal_latency": {
        "description": "Minimal input latency — aggressive tweaks for competitive gaming",
        "tweaks": {
            "input_latency": {
                "nvidia_reflex": "On + Boost",
                "max_pre_rendered_frames": 1,
                "vsync": "Off",
                "mouse_polling_rate": 1000,
                "keyboard_polling_rate": 1000,
            },
            "cpu_gpu_scheduling": {
                "game_mode": True,
                "power_plan": "High Performance",
                "hardware_accelerated_gpu_scheduling": True,
                "disable_fullscreen_optimizations": True,
                "process_priority": "High",
            },
            "memory_storage": {
                "xmp_profile": "Enabled",
                "page_file_size": "System managed",
                "prefetch": "Disabled",
                "superfetch": "Disabled",
            },
            "display": {
                "vrr": "G-Sync",
                "refresh_rate": None,
                "bfi_enabled": False,
                "resizable_bar": True,
                "low_latency_mode": "Ultra",
            },
            "background_services": {
                "disable_xbox_game_bar": True,
                "disable_print_spooler": True,
                "disable_bluetooth_gaming": True,
                "disable_windows_update_active_hours": True,
            },
            "driver_settings": {
                "shader_cache_size": "Unlimited",
                "texture_filtering_quality": "High Performance",
                "power_management_mode": "Prefer Maximum Performance",
                "threaded_optimization": "On",
            },
        },
    },
    "balanced_gaming": {
        "description": "Balanced gaming optimization with stability focus",
        "tweaks": {
            "input_latency": {
                "nvidia_reflex": "On",
                "max_pre_rendered_frames": 1,
                "vsync": "G-Sync Compatible",
                "mouse_polling_rate": 1000,
            },
            "cpu_gpu_scheduling": {
                "game_mode": True,
                "power_plan": "High Performance",
                "hardware_accelerated_gpu_scheduling": True,
                "process_priority": "Normal",
            },
            "memory_storage": {
                "xmp_profile": "Enabled",
                "page_file_size": "System managed",
            },
            "display": {
                "vrr": "G-Sync",
                "refresh_rate": None,
                "bfi_enabled": False,
            },
            "background_services": {
                "disable_xbox_game_bar": False,
            },
            "driver_settings": {
                "shader_cache_size": "Default",
                "power_management_mode": "Optimal Power",
            },
        },
    },
}
