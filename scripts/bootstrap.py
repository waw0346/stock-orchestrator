from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
MIN_PYTHON = (3, 8)


def requirement_names(path: Path) -> list[str]:
    names: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for separator in ("==", ">=", "<=", "~=", ">", "<"):
            if separator in line:
                line = line.split(separator, 1)[0]
                break
        names.append(line.strip())
    return names


def package_status(names: list[str]) -> list[dict[str, Any]]:
    status: list[dict[str, Any]] = []
    for name in names:
        try:
            version = importlib.metadata.version(name)
            status.append({"name": name, "installed": True, "version": version})
        except importlib.metadata.PackageNotFoundError:
            status.append({"name": name, "installed": False, "version": ""})
    return status


def venv_paths() -> dict[str, str]:
    scripts_dir = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin")
    executable = scripts_dir / ("python.exe" if sys.platform.startswith("win") else "python")
    return {
        "dir": str(ROOT / ".venv"),
        "scripts_dir": str(scripts_dir),
        "python": str(executable),
    }


def build_report() -> dict[str, Any]:
    requirements = requirement_names(REQUIREMENTS) if REQUIREMENTS.exists() else []
    packages = package_status(requirements)
    missing = [item["name"] for item in packages if not item["installed"]]
    return {
        "project_root": str(ROOT),
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "ok": sys.version_info >= MIN_PYTHON,
            "minimum": ".".join(str(part) for part in MIN_PYTHON),
        },
        "venv": venv_paths(),
        "requirements_file": str(REQUIREMENTS),
        "requirements_present": REQUIREMENTS.exists(),
        "packages": packages,
        "missing_packages": missing,
        "commands": {
            "create_venv": f"{sys.executable} -m venv .venv",
            "install": f"{sys.executable} -m pip install -r requirements.txt",
            "smoke": f"{sys.executable} tests/run_cross_platform_smoke.py",
        },
    }


def run_install() -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)], cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check or prepare a portable stock orchestrator Python environment.")
    parser.add_argument("--install", action="store_true", help="Install requirements into the active Python environment.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Only report checks and commands; do not install.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.install and not args.dry_run:
        run_install()

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Project root: {report['project_root']}")
        print(f"Python: {report['python']['version']} at {report['python']['executable']}")
        print(f"Requirements: {report['requirements_file']}")
        if report["missing_packages"]:
            print("Missing packages: " + ", ".join(report["missing_packages"]))
            print("Install: " + report["commands"]["install"])
        else:
            print("All requirements are installed in the active Python environment.")
        print("Smoke test: " + report["commands"]["smoke"])

    return 0 if report["python"]["ok"] and report["requirements_present"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
