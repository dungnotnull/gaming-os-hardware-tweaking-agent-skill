"""
setup_env.py — Local environment setup for gaming-os-hardware-tweaking.

Idempotent setup routine: validates Python version, creates runtime
directories (logs/), writes a default config profile if none exists, and
performs an import smoke test of the core package.

Usage:
    python scripts/setup_env.py [--config config/default.json] [--check-only]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
REQUIRED_DIRS = ["logs", "config", "references", "assets", "scripts", "skills", "tools", "tests"]
MIN_PY = (3, 9)


def check_python() -> bool:
    ok = sys.version_info >= MIN_PY
    print(f"[setup] python {sys.version.split()[0]} (>= {MIN_PY[0]}.{MIN_PY[1]}): {'OK' if ok else 'FAIL'}")
    return ok


def ensure_dirs() -> None:
    for d in REQUIRED_DIRS:
        path = ROOT / d
        path.mkdir(parents=True, exist_ok=True)
        print(f"[setup] dir ready: {d}/")


def ensure_default_config(profile: Path) -> bool:
    if profile.exists():
        print(f"[setup] config present: {profile.relative_to(ROOT)}")
        return True
    canonical = ROOT / "config" / "default.json"
    if canonical.exists() and canonical != profile:
        shutil.copy(canonical, profile)
        print(f"[setup] wrote config: {profile.relative_to(ROOT)} (from default.json)")
        return True
    print(f"[setup] config missing and no default to copy: {profile}")
    return False


def pip_install_optional() -> None:
    reqs = ROOT / "requirements.txt"
    if not reqs.exists():
        print("[setup] requirements.txt not found; skipping pip install")
        return
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(reqs), "--quiet"]
        )
        print("[setup] pip install -r requirements.txt: OK")
    except subprocess.CalledProcessError as exc:
        print(f"[setup] pip install failed (non-fatal): {exc}")


def smoke_imports() -> bool:
    sys.path.insert(0, str(SRC))
    failed = []
    for mod in ["config", "hooks", "tools", "registry", "router", "orchestrator",
                "system_profiler", "tweak_recommender", "config_manager",
                "benchmark_validator", "logging_setup"]:
        try:
            __import__(f"gaming_tweaks.{mod}")
            print(f"[setup] import OK: gaming_tweaks.{mod}")
        except Exception as exc:  # noqa: BLE001
            print(f"[setup] import FAIL: gaming_tweaks.{mod} -> {exc}")
            failed.append(mod)
    return not failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Local environment setup")
    parser.add_argument("--config", default="config/default.json",
                        help="config profile to ensure exists")
    parser.add_argument("--check-only", action="store_true",
                        help="validate without writing or installing")
    args = parser.parse_args()

    if not check_python():
        return 2
    if args.check_only:
        ensure_default_config(ROOT / args.config)
        return 0 if smoke_imports() else 1

    ensure_dirs()
    ensure_default_config(ROOT / args.config)
    pip_install_optional()
    ok = smoke_imports()
    print(f"[setup] setup {'COMPLETE' if ok else 'INCOMPLETE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
