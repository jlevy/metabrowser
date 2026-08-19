"""Validate built artifacts and a clean-wheel installation."""

from __future__ import annotations

import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

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
    "keyboard_help.js",
    "keyboard_shortcuts.js",
    "overlay_layer.js",
    "tree_keyboard_navigation.js",
}


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
            "metabrowser/static/contribution_registry.js",
            "metabrowser/static/resource_context.js",
            "metabrowser/static/view_state.js",
            "metabrowser/static/source_append.js",
            # Vendored browser libraries: the offline-first page depends on
            # these shipping in the wheel (see static/vendor/manifest.json).
            "metabrowser/static/vendor/manifest.json",
            "metabrowser/static/vendor/highlight.min.js",
            "metabrowser/static/vendor/chart.umd.min.js",
            VSCODE_LICENSE_PATH,
            "metabrowser/builtin_plugins/markdown/manifest.toml",
            "metabrowser/builtin_plugins/markdown/rendered.js",
            "metabrowser/builtin_plugins/folder/overview.js",
            "metabrowser/builtin_plugins/folder/file_type_summary.js",
            "metabrowser/builtin_plugins/folder/file_type_summary.css",
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


def _smoke_install(wheel: Path) -> None:
    env = os.environ.copy()
    env.setdefault("UV_EXCLUDE_NEWER", "14 days")
    uv_command = ["uv", "--config-file", str(ROOT / "uv.toml")]
    python_command = [
        *uv_command,
        "run",
        "--isolated",
        "--no-project",
        "--with",
        str(wheel),
        "python",
        "-c",
        (
            "from importlib.resources import files; "
            "import metabrowser; "
            "from metabrowser.file_type_registry import load_file_type_registry; "
            "from metabrowser.kpress_adapter import render_kpress_view; "
            "from metabrowser.plugin_loader.discovery import discover_plugins; "
            "registry = load_file_type_registry(); "
            "plugins = discover_plugins(); "
            "names = {plugin.name for plugin in plugins.plugins}; "
            "required = {'agent-log', 'binary', 'folder', 'markdown', 'structured', "
            "'text', 'unknown-jsonl'}; "
            "rendered = render_kpress_view(source_text='# Wheel smoke\\n', "
            "source_path='smoke.md', kind='markdown', view='rendered', ext='.md', "
            "mtime_hash='wheel-smoke', size=14); "
            "assert metabrowser.__version__; "
            "assert registry.family('javascript') is not None; "
            "static = files('metabrowser').joinpath('static'); "
            "assets = ('app.js', 'keyboard_help.js', 'keyboard_shortcuts.js', "
            "'overlay_layer.js', 'tree_keyboard_navigation.js'); "
            "assert all(static.joinpath(asset).is_file() for asset in assets); "
            "assert files('metabrowser').joinpath('builtin_plugins/folder/overview.js').is_file(); "
            "assert files('metabrowser').joinpath('builtin_plugins/folder/file_type_summary.css').is_file(); "
            "assert required == names; "
            "assert not plugins.errors; "
            "assert 'Wheel smoke' in rendered['html']; "
            "print(metabrowser.__version__)"
        ),
    ]
    python_result = subprocess.run(
        python_command,
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    expected_version = python_result.stdout.strip()

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
    _smoke_install(wheel)
    print(f"Distribution checks passed: {wheel.name}, {sdist.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
