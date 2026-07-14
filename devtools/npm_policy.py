"""Verify the standalone repository's package-resolution policy."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NPM_MIN_RELEASE_AGE_DAYS = "14"
NODE_VERSION = "24.18.0"
NODE_RANGE = ">=24.18.0 <25"
NPM_RANGE = ">=11.10.0 <12"
CHECKOUT_SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
SETUP_UV_SHA = "fac544c07dec837d0ccb6301d7b5580bf5edae39"
SETUP_NODE_SHA = "48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e"
UV_VERSION = "0.11.25"
UV_LINUX_CHECKSUM = "1db18b5e76fa645a7f3865773139bdec8e2d46adbdbb35e7410b34fa8015ccd2"
NPM_TOOL_PINS = {
    "@biomejs/biome": "2.4.14",
    "lefthook": "2.1.6",
    "typescript": "6.0.3",
}
FLOWMARK_VERSION = "0.3.1"


def verify_repo_package_policy(root: Path = ROOT) -> None:
    """Raise when package or tool configuration bypasses repository policy."""
    npmrc = (root / ".npmrc").read_text(encoding="utf-8")
    required_npmrc = {
        "ignore-scripts=true",
        f"min-release-age={NPM_MIN_RELEASE_AGE_DAYS}",
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

    package_json = root / "package.json"
    package_lock = root / "package-lock.json"
    if not package_json.is_file() or not package_lock.is_file():
        raise RuntimeError("the exact npm toolchain requires package.json and package-lock.json")

    package_data = json.loads(package_json.read_text(encoding="utf-8"))
    if package_data.get("private") is not True:
        raise RuntimeError("the npm development-tool package must remain private")
    if package_data.get("engines") != {"node": NODE_RANGE, "npm": NPM_RANGE}:
        raise RuntimeError("package.json must require the reviewed Node and npm ranges")
    if package_data.get("devDependencies") != NPM_TOOL_PINS:
        raise RuntimeError("package.json must contain only the reviewed exact npm tool pins")

    lock_data = json.loads(package_lock.read_text(encoding="utf-8"))
    lock_packages = lock_data.get("packages", {})
    if lock_packages.get("", {}).get("devDependencies") != NPM_TOOL_PINS:
        raise RuntimeError("package-lock.json root pins do not match package.json")
    if lock_packages.get("", {}).get("engines") != package_data["engines"]:
        raise RuntimeError("package-lock.json root engines do not match package.json")
    for package, version in NPM_TOOL_PINS.items():
        locked = lock_packages.get(f"node_modules/{package}", {})
        if locked.get("version") != version:
            raise RuntimeError(f"package-lock.json must contain exact {package}@{version}")
        if not str(locked.get("resolved", "")).startswith("https://registry.npmjs.org/"):
            raise RuntimeError(f"{package} must resolve from the npm registry")
        if not str(locked.get("integrity", "")).startswith("sha512-"):
            raise RuntimeError(f"{package} must have a sha512 lockfile integrity hash")
    for package_path, locked in lock_packages.items():
        if not package_path:
            continue
        if not str(locked.get("resolved", "")).startswith("https://registry.npmjs.org/"):
            raise RuntimeError(f"{package_path} must resolve from the npm registry")
        if not str(locked.get("integrity", "")).startswith("sha512-"):
            raise RuntimeError(f"{package_path} must have a sha512 lockfile integrity hash")

    tooling_paths = [
        root / "Makefile",
        root / ".github/workflows/ci.yml",
        root / ".github/workflows/publish.yml",
        root / "devtools/biome.py",
        root / "devtools/tsc_check.py",
    ]
    tooling_text = "\n".join(path.read_text(encoding="utf-8") for path in tooling_paths)
    if f"flowmark-rs@{FLOWMARK_VERSION}" not in tooling_text:
        raise RuntimeError("Flowmark tooling is missing its exact pin")
    if tooling_text.count("npx --no-install") < 1 or tooling_text.count("npx_no_install") < 2:
        raise RuntimeError("npm tools must run from the lock with npx --no-install")
    if "npx --yes" in tooling_text or '"--package"' in tooling_text:
        raise RuntimeError("npm tools must never fetch packages during lint or type checking")
    if "npm ci" not in tooling_text:
        raise RuntimeError("CI and local setup must install the committed npm lock")
    if "@latest" in tooling_text:
        raise RuntimeError("tooling must not use @latest")

    workflow_paths = sorted((root / ".github" / "workflows").glob("*.yml"))
    workflow_text = "\n".join(path.read_text(encoding="utf-8") for path in workflow_paths)
    action_uses = re.findall(r"^\s*uses:\s+[^@\s]+@([^\s#]+)", workflow_text, re.MULTILINE)
    mutable_actions = [ref for ref in action_uses if re.fullmatch(r"[0-9a-f]{40}", ref) is None]
    if mutable_actions:
        raise RuntimeError(f"GitHub Actions must use full commit SHAs: {mutable_actions}")
    required_workflow_pins = [
        f"actions/checkout@{CHECKOUT_SHA}",
        f"astral-sh/setup-uv@{SETUP_UV_SHA}",
        f"actions/setup-node@{SETUP_NODE_SHA}",
        f'version: "{UV_VERSION}"',
        f'checksum: "{UV_LINUX_CHECKSUM}"',
    ]
    missing_workflow_pins = [
        value for value in required_workflow_pins if value not in workflow_text
    ]
    if missing_workflow_pins:
        raise RuntimeError(f"workflows are missing reviewed pins: {missing_workflow_pins}")
    node_versions = set(
        re.findall(r'^\s*node-version:\s*["\']?([^\s"\']+)', workflow_text, re.MULTILINE)
    )
    if node_versions != {NODE_VERSION}:
        raise RuntimeError(f"workflows must use only Node {NODE_VERSION}, got {node_versions}")
    checkout_count = workflow_text.count(f"actions/checkout@{CHECKOUT_SHA}")
    if workflow_text.count("persist-credentials: false") != checkout_count:
        raise RuntimeError("every checkout must disable persisted credentials")
    if workflow_text.count("fetch-depth: 0") != checkout_count:
        raise RuntimeError("every checkout must fetch tags for dynamic versioning")
    required_publish_controls = [
        "environment: pypi",
        "ref: ${{ github.event.release.tag_name }}",
        "run: make verify",
        "npm audit --audit-level=moderate",
        "^v[0-9]+\\.[0-9]+\\.[0-9]+$",
        "metabrowser.__version__",
        "uv publish --trusted-publishing always",
    ]
    missing_publish_controls = [
        value for value in required_publish_controls if value not in publish_workflow
    ]
    if missing_publish_controls:
        raise RuntimeError(f"publish workflow is missing controls: {missing_publish_controls}")


def main() -> int:
    verify_repo_package_policy()
    print("Package policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
