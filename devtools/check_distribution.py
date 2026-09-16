"""Validate built artifacts and a clean-wheel installation."""

from __future__ import annotations

import configparser
import json
import os
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from collections.abc import Mapping
from pathlib import Path
from textwrap import dedent
from typing import cast, override

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
CAPABILITY_ENTRY_POINT_GROUP = "metabrowser.capabilities.v1"
ISOLATED_PYTHON_ENV_VARS = ("PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONPATH")
BROWSER_EVIDENCE_CHECK = ROOT / "devtools" / "artifact-contract-browser-check.mjs"
BROWSER_EVIDENCE_TIMEOUT_SECONDS = 30

CAPABILITY_SMOKE_SCRIPT = dedent(
    """
    import json
    import sys
    from pathlib import Path

    import metabrowser
    from metabrowser import ArtifactContractSpec, CapabilitySet, ConformanceCorpusSpec


    def _require(condition, message):
        if not condition:
            raise RuntimeError(message)


    _require(
        all(name not in sys.modules for name in ("frontmatter_format", "jsonschema", "softschema")),
        "public capability imports loaded heavyweight schema dependencies",
    )

    from metabrowser.plugin_loader.artifact_contracts import build_installed_registries
    from metabrowser.plugin_loader.artifact_inventory import validate_installed_evidence
    from metabrowser.plugin_loader.capability_discovery import discover_capability_sets

    evidence_root = Path(sys.argv[1])
    expected_provider_ids = frozenset(sys.argv[2:])
    _require(evidence_root.is_dir(), "caller-owned browser evidence directory is absent")
    _require(expected_provider_ids, "project metadata declared no capability providers")
    discovery = discover_capability_sets()
    actual_provider_ids = frozenset(provider.provider_id for provider in discovery.providers)
    _require(
        actual_provider_ids == expected_provider_ids,
        f"installed capability providers differ from project metadata: "
        f"expected {sorted(expected_provider_ids)}, found {sorted(actual_provider_ids)}",
    )
    _require(not discovery.errors, f"installed capability discovery failed: {discovery.errors}")
    capabilities = validate_installed_evidence(build_installed_registries(discovery))
    _require(capabilities.contracts, "installed capability registry has no artifact contracts")
    _require(
        capabilities.resource_profiles,
        "installed capability registry has no resource profiles",
    )
    expected_contract_count = sum(
        len(provider.capabilities.artifact_contracts) for provider in discovery.providers
    )
    expected_profile_count = sum(
        len(provider.capabilities.resource_profiles) for provider in discovery.providers
    )
    _require(
        len(capabilities.contracts) == expected_contract_count,
        "installed artifact-contract registry lost a provider declaration",
    )
    _require(
        len(capabilities.resource_profiles) == expected_profile_count,
        "installed resource-profile registry lost a provider declaration",
    )

    descriptors = []
    for contract_id, installed in sorted(capabilities.contracts.items()):
        spec = installed.spec
        if not spec.browser_consumed:
            continue
        parser = spec.browser_parser
        _require(parser is not None, f"browser-consumed contract {contract_id!r} has no parser")
        module_path = evidence_root / f"{parser.module_bytes_sha256}.mjs"
        corpus_path = evidence_root / f"{spec.corpus.payload_sha256}.json"
        for path, payload in (
            (module_path, parser.module_bytes),
            (corpus_path, spec.corpus.payload),
        ):
            if path.exists():
                _require(path.read_bytes() == payload, f"installed evidence collision at {path.name}")
            else:
                path.write_bytes(payload)
        corpus = json.loads(spec.corpus.payload)
        selectors = set(spec.corpus_record_selectors)
        selected_count = sum(
            (case.get("record") in selectors) if selectors else ("record" not in case)
            for case in corpus["cases"]
        )
        descriptors.append(
            {
                "contract_id": contract_id,
                "module_path": str(module_path),
                "export_name": parser.export_name,
                "corpus_path": str(corpus_path),
                "record_selectors": spec.corpus_record_selectors,
                "expected_case_count": selected_count,
            }
        )
    (evidence_root / "descriptors.json").write_text(
        json.dumps(descriptors, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
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
    print(metabrowser.__version__)
    """
).strip()


class _EntryPointConfigParser(configparser.ConfigParser):
    @override
    def optionxform(self, optionstr: str) -> str:
        return optionstr


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


def _parse_project_capability_entry_points(payload: bytes) -> dict[str, str]:
    try:
        document = cast(dict[str, object], tomllib.loads(payload.decode("utf-8")))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError("project capability entry points are malformed") from exc
    project_value = document.get("project")
    if not isinstance(project_value, dict):
        raise RuntimeError("project metadata is missing [project]")
    project = cast(dict[str, object], project_value)
    entry_points_value = project.get("entry-points")
    if not isinstance(entry_points_value, dict):
        raise RuntimeError("project metadata is missing [project.entry-points]")
    entry_points = cast(dict[str, object], entry_points_value)
    declarations_value = entry_points.get(CAPABILITY_ENTRY_POINT_GROUP)
    if not isinstance(declarations_value, dict) or not declarations_value:
        raise RuntimeError(
            f'project metadata is missing nonempty [project.entry-points."{CAPABILITY_ENTRY_POINT_GROUP}"]'
        )
    declarations = cast(dict[object, object], declarations_value)
    if any(
        not isinstance(name, str) or not name or not isinstance(target, str) or not target
        for name, target in declarations.items()
    ):
        raise RuntimeError("project capability entry points must map nonempty names to targets")
    return {
        cast(str, name): cast(str, target)
        for name, target in sorted(declarations.items(), key=lambda item: str(item[0]))
    }


def _project_capability_entry_points(
    pyproject: Path = ROOT / "pyproject.toml",
) -> dict[str, str]:
    return _parse_project_capability_entry_points(pyproject.read_bytes())


def _entry_point_difference(actual: Mapping[str, str], expected: Mapping[str, str]) -> str | None:
    missing = sorted(set(expected).difference(actual))
    unexpected = sorted(set(actual).difference(expected))
    changed = sorted(
        name for name in set(actual).intersection(expected) if actual[name] != expected[name]
    )
    differences: list[str] = []
    if missing:
        differences.append(f"missing {missing}")
    if unexpected:
        differences.append(f"unexpected {unexpected}")
    if changed:
        differences.append(f"changed targets {changed}")
    return "; ".join(differences) or None


def _check_capability_entry_points(payload: bytes, expected: Mapping[str, str]) -> None:
    parser = _EntryPointConfigParser(interpolation=None)
    try:
        parser.read_string(payload.decode("utf-8"))
    except (UnicodeDecodeError, configparser.Error) as exc:
        raise RuntimeError("wheel capability entry points are malformed") from exc
    if not parser.has_section(CAPABILITY_ENTRY_POINT_GROUP):
        raise RuntimeError(f"wheel entry points are missing [{CAPABILITY_ENTRY_POINT_GROUP}]")
    items = dict(parser.items(CAPABILITY_ENTRY_POINT_GROUP))
    if not items:
        raise RuntimeError(f"wheel entry points [{CAPABILITY_ENTRY_POINT_GROUP}] must not be empty")
    difference = _entry_point_difference(items, expected)
    if difference is not None:
        raise RuntimeError(
            f"wheel capability entry points differ from project metadata: {difference}"
        )


def _inspect_wheel(wheel: Path, expected_entry_points: Mapping[str, str]) -> None:
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
        entry_point_names = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        if len(entry_point_names) != 1:
            raise RuntimeError(
                f"wheel must contain one entry_points.txt file, found {entry_point_names}"
            )
        _check_capability_entry_points(archive.read(entry_point_names[0]), expected_entry_points)
        for name in names:
            _check_text_member(name, archive.read(name))


def _inspect_sdist(sdist: Path, expected_entry_points: Mapping[str, str]) -> None:
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
        pyproject_members = [
            member for member in members if member.name.endswith("/pyproject.toml")
        ]
        if len(pyproject_members) != 1:
            raise RuntimeError(
                f"sdist must contain one pyproject.toml file, found "
                f"{[member.name for member in pyproject_members]}"
            )
        extracted_pyproject = archive.extractfile(pyproject_members[0])
        if extracted_pyproject is None:
            raise RuntimeError("sdist pyproject.toml could not be read")
        sdist_entry_points = _parse_project_capability_entry_points(extracted_pyproject.read())
        difference = _entry_point_difference(sdist_entry_points, expected_entry_points)
        if difference is not None:
            raise RuntimeError(
                f"sdist capability entry points differ from project metadata: {difference}"
            )
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


def _run_installed_python_smoke(
    artifact: Path,
    script: str,
    *,
    arguments: tuple[str, ...] = (),
) -> str:
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
        *arguments,
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


def _browser_evidence_expected_output(descriptor_path: Path, evidence_root: Path) -> str:
    try:
        decoded = cast(object, json.loads(descriptor_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("installed browser evidence descriptor is unreadable") from exc
    if not isinstance(decoded, list):
        raise RuntimeError("installed browser evidence descriptor must be an array")
    descriptors = cast(list[object], decoded)
    case_count = 0
    evidence_root = evidence_root.resolve()
    for index, descriptor_value in enumerate(descriptors):
        if not isinstance(descriptor_value, dict):
            raise RuntimeError(f"installed browser evidence descriptor {index} is not an object")
        descriptor = cast(dict[object, object], descriptor_value)
        for field in ("module_path", "corpus_path"):
            value = descriptor.get(field)
            if not isinstance(value, str) or not value:
                raise RuntimeError(f"installed browser evidence descriptor {index} has no {field}")
            path = Path(value).resolve()
            if not path.is_relative_to(evidence_root) or not path.is_file():
                raise RuntimeError(
                    f"installed browser evidence descriptor {index} {field} escapes its handoff"
                )
        expected_case_count = descriptor.get("expected_case_count")
        if (
            isinstance(expected_case_count, bool)
            or not isinstance(expected_case_count, int)
            or expected_case_count < 0
        ):
            raise RuntimeError(
                f"installed browser evidence descriptor {index} has an invalid case count"
            )
        case_count += expected_case_count
    return f"artifact browser evidence OK ({len(descriptors)} parser(s), {case_count} cases)"


def _run_installed_browser_evidence(artifact: Path, evidence_root: Path) -> None:
    descriptor_path = evidence_root / "descriptors.json"
    expected_output = _browser_evidence_expected_output(descriptor_path, evidence_root)
    try:
        result = subprocess.run(
            [
                "node",
                "--experimental-vm-modules",
                "--no-warnings",
                str(BROWSER_EVIDENCE_CHECK),
                str(descriptor_path),
            ],
            cwd=ROOT,
            env=_isolated_install_environment(),
            check=False,
            capture_output=True,
            text=True,
            timeout=BROWSER_EVIDENCE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"installed {artifact.name} browser evidence requires Node.js") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"installed {artifact.name} browser evidence timed out") from exc
    except OSError as exc:
        raise RuntimeError(
            f"installed {artifact.name} browser evidence could not start: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if not detail:
            detail = f"browser harness exited {result.returncode} without diagnostics"
        raise RuntimeError(f"installed {artifact.name} browser evidence failed: {detail}")
    if result.stdout.strip() != expected_output or result.stderr.strip():
        raise RuntimeError(
            f"installed {artifact.name} browser evidence exited without its completion proof: "
            f"stdout={result.stdout.strip()!r}, stderr={result.stderr.strip()!r}"
        )


def _smoke_installed_capabilities(artifact: Path, expected_entry_points: Mapping[str, str]) -> None:
    with tempfile.TemporaryDirectory(prefix="metabrowser-installed-evidence-") as temp_dir:
        evidence_root = Path(temp_dir)
        _run_installed_python_smoke(
            artifact,
            CAPABILITY_SMOKE_SCRIPT,
            arguments=(str(evidence_root), *sorted(expected_entry_points)),
        )
        _run_installed_browser_evidence(artifact, evidence_root)


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
    expected_entry_points = _project_capability_entry_points()
    _inspect_wheel(wheel, expected_entry_points)
    _inspect_sdist(sdist, expected_entry_points)
    _smoke_installed_capabilities(wheel, expected_entry_points)
    _smoke_installed_capabilities(sdist, expected_entry_points)
    _smoke_install(wheel)
    print(f"Distribution checks passed: {wheel.name}, {sdist.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
