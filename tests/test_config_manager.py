"""
test_config_manager.py — Unit tests for ConfigManager and ConfigProfile.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from gaming_tweaks.config_manager import (
    ConfigManager, ConfigProfile, TWEAK_CATEGORIES, PRESET_PROFILES,
)


class TestConfigProfile:
    def test_creation(self):
        cp = ConfigProfile(name="test_profile", description="A test")
        assert cp.name == "test_profile"
        assert cp.description == "A test"
        assert cp.version == 1
        assert all(cat in cp.tweaks for cat in TWEAK_CATEGORIES)

    def test_set_and_get_tweak(self):
        cp = ConfigProfile(name="test")
        cp.set_tweak("input_latency", "nvidia_reflex", "On + Boost")
        assert cp.get_tweak("input_latency", "nvidia_reflex") == "On + Boost"
        assert cp.version > 1

    def test_get_tweak_default(self):
        cp = ConfigProfile(name="test")
        assert cp.get_tweak("input_latency", "nonexistent", "default") == "default"

    def test_to_dict_and_from_dict(self):
        cp = ConfigProfile(name="roundtrip", description="test RT")
        cp.set_tweak("input_latency", "key1", "val1")
        cp.set_tweak("display", "key2", "val2")
        d = cp.to_dict()
        cp2 = ConfigProfile.from_dict(d)
        assert cp2.name == cp.name
        assert cp2.get_tweak("input_latency", "key1") == "val1"
        assert cp2.get_tweak("display", "key2") == "val2"

    def test_validation_valid(self):
        cp = ConfigProfile(name="valid", description="test")
        cp.set_tweak("input_latency", "key", "value")
        issues = cp.validate()
        assert len(issues) == 0

    def test_validation_invalid_name(self):
        cp = ConfigProfile(name="!!!invalid!!!", description="test")
        issues = cp.validate()
        assert len(issues) > 0

    def test_diff_profiles(self):
        cp1 = ConfigProfile(name="a")
        cp1.set_tweak("input_latency", "k1", "v1")
        cp1.set_tweak("input_latency", "k2", "v2")

        cp2 = ConfigProfile(name="b")
        cp2.set_tweak("input_latency", "k1", "v1_changed")
        cp2.set_tweak("input_latency", "k3", "new_value")

        diff = cp1.diff(cp2)
        assert len(diff["added"]) >= 1
        assert len(diff["changed"]) >= 1

    def test_metadata(self):
        cp = ConfigProfile(name="test")
        cp.metadata["target_games"] = ["CS2", "Valorant"]
        cp.metadata["gpu_vendor"] = "NVIDIA"
        d = cp.to_dict()
        assert d["metadata"]["target_games"] == ["CS2", "Valorant"]


class TestConfigManager:
    def setup_method(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cm = ConfigManager(
            profiles_dir=Path(self.tmpdir.name) / "profiles",
            backups_dir=Path(self.tmpdir.name) / "backups",
        )

    def teardown_method(self):
        self.tmpdir.cleanup()

    def test_save_and_load(self):
        cp = ConfigProfile(name="test_save", description="test")
        cp.set_tweak("input_latency", "nvidia_reflex", "On")
        assert self.cm.save(cp) is True

        loaded = self.cm.get("test_save")
        assert loaded is not None
        assert loaded.get_tweak("input_latency", "nvidia_reflex") == "On"

    def test_list_profiles(self):
        cp1 = ConfigProfile(name="p1", description="desc1")
        cp2 = ConfigProfile(name="p2", description="desc2")
        self.cm.save(cp1)
        self.cm.save(cp2)
        profiles = self.cm.list_profiles()
        assert len(profiles) == 2
        assert profiles[0]["name"] in ("p1", "p2")

    def test_delete_profile(self):
        cp = ConfigProfile(name="to_delete", description="test")
        self.cm.save(cp)
        assert self.cm.delete("to_delete") is True
        assert self.cm.get("to_delete") is None

    def test_delete_nonexistent(self):
        assert self.cm.delete("nonexistent") is False

    def test_save_invalid_profile(self):
        cp = ConfigProfile(name="!!!invalid!!!", description="test")
        assert self.cm.save(cp) is False

    def test_backup_on_save(self):
        cp = ConfigProfile(name="backup_test", description="test")
        cp.set_tweak("input_latency", "k", "v1")
        self.cm.save(cp)

        cp.set_tweak("input_latency", "k", "v2")
        self.cm.save(cp)

        backups = list(self.cm.backups_dir.glob("backup_test_*.json"))
        assert len(backups) >= 1

    def test_rollback(self):
        cp = ConfigProfile(name="rollback_test", description="test")
        cp.set_tweak("input_latency", "k", "v1")
        self.cm.save(cp)

        cp.set_tweak("input_latency", "k", "v2")
        self.cm.save(cp)

        assert self.cm.rollback("rollback_test") is True
        loaded = self.cm.get("rollback_test")
        assert loaded.get_tweak("input_latency", "k") == "v1"

    def test_diff_profiles(self):
        cp1 = ConfigProfile(name="diff_a", description="test")
        cp1.set_tweak("input_latency", "k", "va")
        self.cm.save(cp1)

        cp2 = ConfigProfile(name="diff_b", description="test")
        cp2.set_tweak("input_latency", "k", "vb")
        cp2.set_tweak("input_latency", "k2", "new")
        self.cm.save(cp2)

        diff = self.cm.diff_profiles("diff_a", "diff_b")
        assert diff is not None
        assert len(diff["changed"]) >= 1
        assert len(diff["added"]) >= 1

    def test_diff_nonexistent(self):
        assert self.cm.diff_profiles("nonexistent_a", "nonexistent_b") is None


class TestPresetProfiles:
    def test_all_presets_have_valid_categories(self):
        for name, preset in PRESET_PROFILES.items():
            for cat in preset["tweaks"]:
                assert cat in TWEAK_CATEGORIES, f"Unknown category {cat} in preset {name}"

    def test_presets_serializable(self):
        for name, preset in PRESET_PROFILES.items():
            json_str = json.dumps(preset)
            assert len(json_str) > 0
