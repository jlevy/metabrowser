"""Validate built artifacts and a clean-wheel installation."""

from __future__ import annotations

import os
import subprocess
import tarfile
import zipfile
from pathlib import Path
from textwrap import dedent

from devtools.public_hygiene import find_hygiene_findings

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
REPOSITORY_ONLY_PARTS = {
    ".agents",
    ".claude",
    ".codex",
    ".github",
    ".tbd",
    ".venv",
    "dist",
    "node_modules",
}
REPOSITORY_ONLY_NAMES = {".copier-answers.yml", "AGENTS.md", "CLAUDE.md", "skills-lock.json"}
EXPECTED_LICENSE_METADATA = {
    "License-Expression: AGPL-3.0-or-later",
    "License-File: LICENSE",
    "License-File: NOTICE.md",
}
VSCODE_LICENSE_PATH = "metabrowser/static/vendor/licenses/vscode.txt"
KEYBOARD_STATIC_ASSETS = {
    "keyboard-help.js",
    "keyboard-shortcuts.js",
    "overlay-layer.js",
    "tree-keyboard-navigation.js",
}
ISOLATED_PYTHON_ENV_VARS = ("PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONPATH")

CONTRACT_SMOKE_SCRIPT = dedent(
    """
    import sys

    import metabrowser


    def _require(condition, message):
        if not condition:
            raise RuntimeError(message)


    _require(
        all(name not in sys.modules for name in ("frontmatter_format", "jsonschema", "softschema")),
        "importing metabrowser loaded heavyweight schema dependencies",
    )

    from metabrowser.cache.contracts import cache_contract_registry
    from metabrowser.plugin_loader.artifact_inventory import validate_installed_evidence

    contracts = validate_installed_evidence(cache_contract_registry())
    _require(contracts, "installed contract registry has no artifact contracts")
    _require(metabrowser.__version__, "installed distribution has no version")
    print(metabrowser.__version__)
    """
).strip()

WHEEL_SMOKE_SCRIPT = dedent(
    """
    from importlib.resources import files

    import metabrowser
    from metabrowser.file_type_registry import load_file_type_registry
    from metabrowser.kpress_adapter import render_kpress_view
    from metabrowser.plugin_loader.discovery import discover_plugins
    from metabrowser.cache.contracts import check_packaged_schemas


    def _require(condition, message):
        if not condition:
            raise RuntimeError(message)


    registry = load_file_type_registry()
    plugins = discover_plugins()
    names = {plugin.name for plugin in plugins.plugins}
    required = {
        "agent-log",
        "binary",
        "diff",
        "folder",
        "github",
        "html",
        "image",
        "markdown",
        "structured",
        "text",
        "unknown-jsonl",
    }
    rendered = render_kpress_view(
        source_text="# Wheel smoke\\n",
        source_path="smoke.md",
        kind="markdown",
        view="rendered",
        ext=".md",
        mtime_hash="wheel-smoke",
        size=14,
    )
    _require(metabrowser.__version__, "installed wheel has no version")
    _require(registry.family("javascript") is not None, "installed file-type registry is incomplete")
    package = files("metabrowser")
    required_assets = (
        "static/app.js",
        "static/document-width.js",
        "static/keyboard-help.js",
        "static/keyboard-shortcuts.js",
        "static/overlay-layer.js",
        "static/tree-keyboard-navigation.js",
        "static/view-composition.js",
        "builtin_plugins/folder/overview.js",
        "builtin_plugins/diff/diff-view.js",
        "builtin_plugins/image/index.js",
        "builtin_plugins/image/styles.css",
        "builtin_plugins/html/index.js",
        "builtin_plugins/html/styles.css",
        "builtin_plugins/html/detect.py",
        "builtin_plugins/markdown/dom-traversal.js",
        "builtin_plugins/markdown/markdown-worker.js",
        "builtin_plugins/markdown/markdown-worker-client.js",
        "builtin_plugins/markdown/markdown-worker-operations.js",
        "builtin_plugins/markdown/reconciliation-coordinator.js",
        "data/file-diff-format/file-diff.schema.json",
        "builtin_plugins/folder/file_type_summary.css",
    )
    missing_assets = [asset for asset in required_assets if not package.joinpath(asset).is_file()]
    _require(not missing_assets, f"installed wheel is missing assets: {missing_assets}")
    _require(required == names, f"installed plugin set differs: expected {sorted(required)}, found {sorted(names)}")
    _require(not plugins.errors, f"installed plugin discovery failed: {plugins.errors}")
    _require("Wheel smoke" in rendered["html"], "installed KPress renderer returned unexpected HTML")
    # The permissive config contract is outside the enforced registry the contract
    # smoke covers, so every packaged cache schema is compiled against its model here.
    schema_drift = check_packaged_schemas()
    _require(not schema_drift, f"installed cache schemas drifted from their models: {schema_drift}")
    print(metabrowser.__version__)
    """
).strip()


def _single_wheel() -> Path:
    wheels = sorted(DIST.glob("metabrowser-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one wheel in dist/, found {len(wheels)}")
    return wheels[0]


def _single_sdist() -> Path:
    sdists = sorted(DIST.glob("metabrowser-*.tar.gz"))
    if len(sdists) != 1:
        raise RuntimeError(f"expected one sdist in dist/, found {len(sdists)}")
    return sdists[0]


def _check_text_member(name: str, payload: bytes) -> None:
    if name.endswith("devtools/public_hygiene.py"):
        return
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return
    findings = find_hygiene_findings(name, text)
    if findings:
        raise RuntimeError(f"artifact hygiene failed: {findings[:10]}")


def _check_project_metadata(payload: bytes) -> None:
    metadata_lines = set(payload.decode("utf-8").splitlines())
    missing = sorted(EXPECTED_LICENSE_METADATA - metadata_lines)
    if missing:
        raise RuntimeError(f"wheel metadata is missing license declarations: {missing}")


def _inspect_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required_suffixes = {
            "metabrowser/__init__.py",
            "metabrowser/static/app.js",
            "metabrowser/static/charts.js",
            "metabrowser/static/contribution-registry.js",
            "metabrowser/static/document-width.js",
            "metabrowser/static/resource-context.js",
            "metabrowser/static/view-state.js",
            "metabrowser/static/source-append.js",
            # Vendored browser libraries: the offline-first page depends on
            # these shipping in the wheel (see static/vendor/manifest.json).
            "metabrowser/static/vendor/manifest.json",
            "metabrowser/static/vendor/highlight.min.js",
            "metabrowser/static/vendor/chart.umd.min.js",
            VSCODE_LICENSE_PATH,
            "metabrowser/builtin_plugins/markdown/manifest.toml",
            "metabrowser/builtin_plugins/markdown/dom-traversal.js",
            "metabrowser/builtin_plugins/markdown/markdown-worker.js",
            "metabrowser/builtin_plugins/markdown/markdown-worker-client.js",
            "metabrowser/builtin_plugins/markdown/markdown-worker-operations.js",
            "metabrowser/builtin_plugins/markdown/reconciliation-coordinator.js",
            "metabrowser/builtin_plugins/markdown/rendered.js",
            "metabrowser/builtin_plugins/folder/overview.js",
            "metabrowser/builtin_plugins/folder/file-type-summary.js",
            "metabrowser/builtin_plugins/folder/file_type_summary.css",
            "metabrowser/builtin_plugins/html/manifest.toml",
            "metabrowser/builtin_plugins/html/detect.py",
            "metabrowser/builtin_plugins/html/index.js",
            "metabrowser/builtin_plugins/html/styles.css",
            "metabrowser/data/file-rollup-format/empty-file-rollup.json",
            "metabrowser/data/file-rollup-format/file-rollup-conformance.json",
            "metabrowser/data/file-rollup-format/file-rollup-conformance.schema.json",
            "metabrowser/data/file-rollup-format/file-rollup.schema.json",
            "metabrowser/data/file-rollup-format/file-type-registry.schema.json",
            "metabrowser/data/file-rollup-format/recommended-file-types.json",
            "metabrowser/data/file-rollup-format/recommended-file-types.toml",
            "dist-info/licenses/LICENSE",
            "dist-info/licenses/NOTICE.md",
            *(f"metabrowser/static/{asset}" for asset in KEYBOARD_STATIC_ASSETS),
        }
        for suffix in required_suffixes:
            if not any(name.endswith(suffix) for name in names):
                raise RuntimeError(f"wheel is missing {suffix}")
        forbidden_parts = REPOSITORY_ONLY_PARTS | {"tests", "devtools"}
        leaked = [name for name in names if forbidden_parts.intersection(Path(name).parts)]
        if leaked:
            raise RuntimeError(f"wheel contains repository-only files: {leaked[:10]}")
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise RuntimeError(f"wheel must contain one METADATA file, found {metadata_names}")
        _check_project_metadata(archive.read(metadata_names[0]))
        for name in names:
            _check_text_member(name, archive.read(name))


def _inspect_sdist(sdist: Path) -> None:
    with tarfile.open(sdist, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        names = {member.name for member in members}
        required_suffixes = {
            "LICENSE",
            "NOTICE.md",
            "README.md",
            "docs/project/architecture/file-rollup-format/file-rollup-format.md",
            "docs/project/architecture/file-rollup-format/recommended-file-types.toml",
            "pyproject.toml",
            "skills/metabrowser/SKILL.md",
            "skills/metabrowser/agents/openai.yaml",
            "src/metabrowser/data/file-rollup-format/recommended-file-types.toml",
            "src/metabrowser/static/app.js",
            "src/metabrowser/builtin_plugins/markdown/dom-traversal.js",
            "src/metabrowser/builtin_plugins/markdown/markdown-worker.js",
            "src/metabrowser/builtin_plugins/markdown/markdown-worker-client.js",
            "src/metabrowser/builtin_plugins/markdown/markdown-worker-operations.js",
            "src/metabrowser/builtin_plugins/markdown/reconciliation-coordinator.js",
            *(f"src/metabrowser/static/{asset}" for asset in KEYBOARD_STATIC_ASSETS),
        }
        for suffix in required_suffixes:
            if not any(name.endswith(suffix) for name in names):
                raise RuntimeError(f"sdist is missing {suffix}")
        leaked = [
            name
            for name in names
            if REPOSITORY_ONLY_PARTS.intersection(Path(name).parts)
            or Path(name).name in REPOSITORY_ONLY_NAMES
        ]
        if leaked:
            raise RuntimeError(f"sdist contains repository-only files: {leaked[:10]}")
        for member in members:
            extracted = archive.extractfile(member)
            if extracted is not None:
                _check_text_member(member.name, extracted.read())


def _isolated_install_environment() -> dict[str, str]:
    env = os.environ.copy()
    for name in ISOLATED_PYTHON_ENV_VARS:
        env.pop(name, None)
    env.setdefault("UV_EXCLUDE_NEWER", "14 days")
    return env


def _run_installed_python_smoke(artifact: Path, script: str) -> str:
    python_command = [
        "uv",
        "--config-file",
        str(ROOT / "uv.toml"),
        "run",
        "--isolated",
        "--no-project",
        "--with",
        str(artifact),
        "python",
        "-I",
        "-c",
        script,
    ]
    try:
        result = subprocess.run(
            python_command,
            cwd=ROOT,
            env=_isolated_install_environment(),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr if isinstance(exc.stderr, str) and exc.stderr.strip() else exc.stdout
        if not isinstance(detail, str) or not detail.strip():
            detail = str(exc)
        raise RuntimeError(f"installed {artifact.name} smoke failed: {detail.strip()}") from exc
    return result.stdout.strip()


def _smoke_installed_contracts(artifact: Path) -> None:
    """Run every installed contract's packaged corpus evidence against one built artifact."""
    _run_installed_python_smoke(artifact, CONTRACT_SMOKE_SCRIPT)


def _smoke_install(wheel: Path) -> None:
    env = _isolated_install_environment()
    uv_command = ["uv", "--config-file", str(ROOT / "uv.toml")]
    expected_version = _run_installed_python_smoke(wheel, WHEEL_SMOKE_SCRIPT)

    for command in ("metab", "metabrowser"):
        cli_command = [
            *uv_command,
            "run",
            "--isolated",
            "--no-project",
            "--with",
            str(wheel),
            command,
        ]
        subprocess.run([*cli_command, "--help"], cwd=ROOT, env=env, check=True)

        version_result = subprocess.run(
            [*cli_command, "--version"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        expected_output = f"{command} {expected_version}"
        if version_result.stdout.strip() != expected_output:
            raise RuntimeError(
                f"unexpected {command} --version output: {version_result.stdout!r}; "
                f"expected {expected_output!r}"
            )

    doctor_command = [
        *uv_command,
        "run",
        "--isolated",
        "--no-project",
        "--with",
        str(wheel),
        "metab",
        "--doctor",
    ]
    subprocess.run(doctor_command, cwd=ROOT, env=env, check=True)

    api_check_command = [
        *uv_command,
        "run",
        "--isolated",
        "--no-project",
        "--with",
        str(wheel),
        "metab",
        str(ROOT / "tests" / "manual-fixtures"),
        "--check-api",
    ]
    subprocess.run(api_check_command, cwd=ROOT, env=env, check=True)


def main() -> int:
    wheel = _single_wheel()
    sdist = _single_sdist()
    _inspect_wheel(wheel)
    _inspect_sdist(sdist)
    _smoke_installed_contracts(wheel)
    _smoke_installed_contracts(sdist)
    _smoke_install(wheel)
    print(f"Distribution checks passed: {wheel.name}, {sdist.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
