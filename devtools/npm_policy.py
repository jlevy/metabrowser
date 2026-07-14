"""Verify the standalone repository's package-resolution policy."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NPM_MIN_RELEASE_AGE_DAYS = "14"
NPM_TOOL_PINS = {
    "@biomejs/biome": "2.4.14",
    "typescript": "6.0.3",
}
FLOWMARK_VERSION = "0.3.1"


def npm_env() -> dict[str, str]:
    """Return an npm environment with the repository safety defaults."""
    env = os.environ.copy()
    env["NPM_CONFIG_IGNORE_SCRIPTS"] = "true"
    env["NPM_CONFIG_MIN_RELEASE_AGE"] = NPM_MIN_RELEASE_AGE_DAYS
    env["NPM_CONFIG_PACKAGE_LOCK"] = "true"
    env["NPM_CONFIG_SAVE_EXACT"] = "true"
    return env


def verify_repo_package_policy(root: Path = ROOT) -> None:
    """Raise when package or tool configuration bypasses repository policy."""
    npmrc = (root / ".npmrc").read_text(encoding="utf-8")
    required_npmrc = {
        "ignore-scripts=true",
        "min-release-age=14",
        "package-lock=true",
        "save-exact=true",
    }
    missing = sorted(line for line in required_npmrc if line not in npmrc.splitlines())
    if missing:
        raise RuntimeError(f".npmrc is missing required settings: {missing}")

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    if "kpress==0.1.0" not in dependencies:
        raise RuntimeError("MetaBrowser must require exact kpress==0.1.0")
    uv_toml = tomllib.loads((root / "uv.toml").read_text(encoding="utf-8"))
    if uv_toml.get("exclude-newer") != "14 days":
        raise RuntimeError("uv.toml must preserve the 14-day cool-off")
    expected_exceptions = {
        "flowmark-rs": "2026-05-31T00:00:00Z",
        "kpress": "2026-07-14T00:00:00Z",
    }
    if uv_toml.get("exclude-newer-package") != expected_exceptions:
        raise RuntimeError("uv.toml must contain only the audited package exceptions")

    lock_path = root / "uv.lock"
    if lock_path.exists():
        lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
        kpress = [package for package in lock.get("package", []) if package.get("name") == "kpress"]
        if len(kpress) != 1 or kpress[0].get("version") != "0.1.0":
            raise RuntimeError("uv.lock must contain exactly kpress==0.1.0")
        if kpress[0].get("source") != {"registry": "https://pypi.org/simple"}:
            raise RuntimeError("KPress must resolve from the PyPI registry")
        if lock.get("options", {}).get("exclude-newer-package") != expected_exceptions:
            raise RuntimeError("uv.lock contains an unreviewed package-age exception")

    publish_workflow = (root / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    if "types: [published]" not in publish_workflow or "workflow_dispatch" in publish_workflow:
        raise RuntimeError("publishing must be triggered only by a published GitHub release")

    tooling_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            root / "Makefile",
            root / ".github/workflows/ci.yml",
            root / ".github/workflows/publish.yml",
        ]
    )
    expected = [
        f"@biomejs/biome@{NPM_TOOL_PINS['@biomejs/biome']}",
        f"typescript@{NPM_TOOL_PINS['typescript']}",
        f"flowmark-rs@{FLOWMARK_VERSION}",
    ]
    missing_pins = [pin for pin in expected if pin not in tooling_text]
    if missing_pins:
        raise RuntimeError(f"tooling references are missing exact pins: {missing_pins}")
    if "@latest" in tooling_text:
        raise RuntimeError("tooling must not use @latest")

    package_json = root / "package.json"
    if package_json.exists():
        data = json.loads(package_json.read_text(encoding="utf-8"))
        for group in ("dependencies", "devDependencies", "optionalDependencies"):
            for package, spec in data.get(group, {}).items():
                if spec.startswith(("^", "~", ">", "<", "=", "*")):
                    raise RuntimeError(f"{package} must use an exact version, got {spec!r}")


def main() -> int:
    verify_repo_package_policy()
    print("Package policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
