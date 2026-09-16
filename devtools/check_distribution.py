"""Validate built artifacts and a clean-wheel installation."""

from __future__ import annotations

import configparser
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
EXPECTED_CAPABILITY_ENTRY_POINTS = {
    "hosted-review": (
        "metabrowser.builtin_plugins.hosted_review.contracts:hosted_review_capabilities"
    ),
    "provider-resources": (
        "metabrowser.builtin_plugins.hosted_review.contracts:provider_resource_capabilities"
    ),
}
VSCODE_LICENSE_PATH = "metabrowser/static/vendor/licenses/vscode.txt"
KEYBOARD_STATIC_ASSETS = {
    "keyboard-help.js",
    "keyboard-shortcuts.js",
    "overlay-layer.js",
    "tree-keyboard-navigation.js",
}
HOSTED_REVIEW_SCHEMA_ASSETS = {
    "change-request-comment-v1.schema.yaml",
    "change-request-index-v1.schema.yaml",
    "change-request-v1.schema.yaml",
    "check-v1.schema.yaml",
    "commit-status-v1.schema.yaml",
    "hosted-repository-v1.schema.yaml",
    "provider-binding-v1.schema.yaml",
    "provider-sync-manifest-v1.schema.yaml",
    "provider-view-pointer-v1.schema.yaml",
    "repository-activity-v1.schema.yaml",
    "resource-set-v1.schema.yaml",
    "retrieval-v1.schema.yaml",
    "review-comment-v1.schema.yaml",
    "review-thread-v1.schema.yaml",
    "review-v1.schema.yaml",
    "tombstone-v1.schema.yaml",
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


def _check_capability_entry_points(payload: bytes) -> None:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(payload.decode("utf-8"))
    group = "metabrowser.capabilities.v1"
    if not parser.has_section(group):
        raise RuntimeError(f"wheel entry points are missing [{group}]")
    actual = dict(parser.items(group))
    if actual != EXPECTED_CAPABILITY_ENTRY_POINTS:
        raise RuntimeError(
            f"wheel capability entry points differ: {actual}; "
            f"expected {EXPECTED_CAPABILITY_ENTRY_POINTS}"
        )


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
            "metabrowser/builtin_plugins/hosted_review/__init__.py",
            "metabrowser/builtin_plugins/hosted_review/artifacts.py",
            "metabrowser/builtin_plugins/hosted_review/contracts.py",
            "metabrowser/builtin_plugins/hosted_review/hosted-review-model.js",
            "metabrowser/builtin_plugins/hosted_review/models.py",
            "metabrowser/builtin_plugins/hosted_review/resource_profiles.py",
            "metabrowser/plugin_loader/artifact_contracts.py",
            "metabrowser/plugin_loader/capability_discovery.py",
            "metabrowser/plugin_loader/capability_types.py",
            "metabrowser/provider_resources/profiles.py",
            "metabrowser/data/hosted-review-format/change-request-index-conformance.json",
            "metabrowser/data/hosted-review-format/change-request-conformance.json",
            "metabrowser/data/hosted-review-format/hosted-repository-conformance.json",
            "metabrowser/data/hosted-review-format/provider-storage-conformance.json",
            "metabrowser/data/hosted-review-format/repository-activity-conformance.json",
            "metabrowser/data/hosted-review-format/review-records-conformance.json",
            "metabrowser/data/file-rollup-format/empty-file-rollup.json",
            "metabrowser/data/file-rollup-format/file-rollup-conformance.json",
            "metabrowser/data/file-rollup-format/file-rollup-conformance.schema.json",
            "metabrowser/data/file-rollup-format/file-rollup.schema.json",
            "metabrowser/data/file-rollup-format/file-type-registry.schema.json",
            "metabrowser/data/file-rollup-format/recommended-file-types.json",
            "metabrowser/data/file-rollup-format/recommended-file-types.toml",
            "dist-info/licenses/LICENSE",
            "dist-info/licenses/NOTICE.md",
            *(
                f"metabrowser/data/hosted-review-format/schemas/{asset}"
                for asset in HOSTED_REVIEW_SCHEMA_ASSETS
            ),
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
        _check_capability_entry_points(archive.read(entry_point_names[0]))
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
            "src/metabrowser/builtin_plugins/hosted_review/artifacts.py",
            "src/metabrowser/builtin_plugins/hosted_review/contracts.py",
            "src/metabrowser/builtin_plugins/hosted_review/hosted-review-model.js",
            "src/metabrowser/builtin_plugins/hosted_review/models.py",
            "src/metabrowser/builtin_plugins/hosted_review/resource_profiles.py",
            "src/metabrowser/plugin_loader/artifact_contracts.py",
            "src/metabrowser/plugin_loader/capability_discovery.py",
            "src/metabrowser/plugin_loader/capability_types.py",
            "src/metabrowser/provider_resources/profiles.py",
            "src/metabrowser/data/hosted-review-format/change-request-index-conformance.json",
            "src/metabrowser/data/hosted-review-format/change-request-conformance.json",
            "src/metabrowser/data/hosted-review-format/hosted-repository-conformance.json",
            "src/metabrowser/data/hosted-review-format/provider-storage-conformance.json",
            "src/metabrowser/data/hosted-review-format/repository-activity-conformance.json",
            "src/metabrowser/data/hosted-review-format/review-records-conformance.json",
            *(
                f"src/metabrowser/data/hosted-review-format/schemas/{asset}"
                for asset in HOSTED_REVIEW_SCHEMA_ASSETS
            ),
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
            "from metabrowser.builtin_plugins.hosted_review.models import "
            "validate_authorization_context, validate_change_request, validate_change_request_comment, "
            "validate_change_request_index, validate_check, validate_commit_status, "
            "validate_hosted_repository, validate_hosted_review_bundle, "
            "validate_provider_binding, validate_provider_sync_manifest, "
            "validate_provider_view_pointer, validate_resource_set, "
            "validate_repository_activity, validate_retrieval, validate_review, "
            "validate_review_comment, validate_review_thread, validate_tombstone; "
            "from metabrowser.kpress_adapter import render_kpress_view; "
            "from metabrowser.plugin_loader.artifact_contracts import "
            "build_installed_registries, serialize_artifact, validate_artifact; "
            "from metabrowser.plugin_loader.discovery import discover_plugins; "
            "registry = load_file_type_registry(); "
            "plugins = discover_plugins(); "
            "capabilities = build_installed_registries(); "
            "names = {plugin.name for plugin in plugins.plugins}; "
            "required = {'agent-log', 'binary', 'diff', 'folder', 'image', 'markdown', "
            "'structured', 'text', 'unknown-jsonl'}; "
            "rendered = render_kpress_view(source_text='# Wheel smoke\\n', "
            "source_path='smoke.md', kind='markdown', view='rendered', ext='.md', "
            "mtime_hash='wheel-smoke', size=14); "
            "assert metabrowser.__version__; "
            "assert registry.family('javascript') is not None; "
            "static = files('metabrowser').joinpath('static'); "
            "assets = ('app.js', 'document-width.js', 'keyboard-help.js', 'keyboard-shortcuts.js', "
            "'overlay-layer.js', 'tree-keyboard-navigation.js', 'view-composition.js'); "
            "assert all(static.joinpath(asset).is_file() for asset in assets); "
            "assert files('metabrowser').joinpath('builtin_plugins/folder/overview.js').is_file(); "
            "assert files('metabrowser').joinpath('builtin_plugins/diff/diff-view.js').is_file(); "
            "assert files('metabrowser').joinpath('builtin_plugins/image/index.js').is_file(); "
            "assert files('metabrowser').joinpath('builtin_plugins/image/styles.css').is_file(); "
            "assert files('metabrowser').joinpath("
            "'builtin_plugins/markdown/dom-traversal.js').is_file(); "
            "assert files('metabrowser').joinpath("
            "'builtin_plugins/markdown/markdown-worker.js').is_file(); "
            "assert files('metabrowser').joinpath("
            "'builtin_plugins/markdown/markdown-worker-client.js').is_file(); "
            "assert files('metabrowser').joinpath("
            "'builtin_plugins/markdown/markdown-worker-operations.js').is_file(); "
            "assert files('metabrowser').joinpath("
            "'builtin_plugins/markdown/reconciliation-coordinator.js').is_file(); "
            "assert files('metabrowser').joinpath("
            "'data/file-diff-format/file-diff.schema.json').is_file(); "
            "import json; "
            "format_data = files('metabrowser').joinpath('data/hosted-review-format'); "
            "change_request = json.loads(format_data.joinpath("
            "'change-request-conformance.json').read_text(encoding='utf-8')); "
            "storage = json.loads(format_data.joinpath("
            "'provider-storage-conformance.json').read_text(encoding='utf-8'))"
            "['base_records']; "
            "repository = json.loads(format_data.joinpath("
            "'hosted-repository-conformance.json').read_text(encoding='utf-8'))"
            "['base_records']; "
            "index = json.loads(format_data.joinpath("
            "'change-request-index-conformance.json').read_text(encoding='utf-8'))"
            "['base_records']; "
            "review_records = json.loads(format_data.joinpath("
            "'review-records-conformance.json').read_text(encoding='utf-8'))"
            "['base_records']; "
            "activity = json.loads(format_data.joinpath("
            "'repository-activity-conformance.json').read_text(encoding='utf-8'))"
            "['base_document']; "
            "parsed_change_request = validate_change_request(change_request['base_document']); "
            "validate_authorization_context(storage['authorization_context']); "
            "validate_retrieval(storage['retrieval']); "
            "validate_resource_set(storage['resource_set']); "
            "validate_provider_sync_manifest(storage['provider_sync_manifest']); "
            "validate_provider_view_pointer(storage['provider_view_pointer']); "
            "validate_tombstone(storage['tombstone']); "
            "validate_provider_binding(repository['provider_binding']); "
            "parsed_repository = validate_hosted_repository(repository['hosted_repository']); "
            "validate_change_request_index(index['change_request_index']); "
            "validate_change_request_index(index['empty_change_request_index']); "
            "validate_resource_set(index['index_resource_set']); "
            "change_request_comments = (validate_change_request_comment("
            "review_records['change_request_comment']),); "
            "reviews = (validate_review(review_records['review']),); "
            "review_threads = tuple(validate_review_thread(review_records[name]) for name in "
            "('review_thread', 'review_thread_empty')); "
            "review_comments = tuple(validate_review_comment(review_records[name]) for name in "
            "('review_comment', 'review_comment_reply')); "
            "checks = tuple(validate_check(review_records[name]) for name in "
            "('check_suite', 'check_run')); "
            "commit_statuses = (validate_commit_status(review_records['commit_status']),); "
            "validate_hosted_review_bundle(change_request=parsed_change_request, "
            "change_request_comments=change_request_comments, reviews=reviews, "
            "review_threads=review_threads, review_comments=review_comments, checks=checks, "
            "commit_statuses=commit_statuses, review_comments_complete=True); "
            "validate_repository_activity(activity); "
            "assert files('metabrowser').joinpath("
            "'builtin_plugins/hosted_review/hosted-review-model.js').is_file(); "
            "assert files('metabrowser').joinpath('builtin_plugins/folder/file_type_summary.css').is_file(); "
            "assert required == names; "
            "assert not plugins.errors; "
            "assert len(capabilities.contracts) == 16; "
            "assert len(capabilities.resource_profiles) == 2; "
            "change_request_contract = next(contract_id for contract_id, installed in "
            "capabilities.contracts.items() if installed.spec.envelope == 'change_request'); "
            "change_request_payload = serialize_artifact(parsed_change_request, "
            "contract_id=change_request_contract, contracts=capabilities.contracts, "
            "body='# Wheel artifact smoke\\n'); "
            "assert validate_artifact(change_request_payload, "
            "expected_contract_id=change_request_contract, "
            "contracts=capabilities.contracts).body == '# Wheel artifact smoke\\n'; "
            "repository_contract = next(contract_id for contract_id, installed in "
            "capabilities.contracts.items() if installed.spec.envelope == 'hosted_repository'); "
            "repository_payload = serialize_artifact(parsed_repository, "
            "contract_id=repository_contract, contracts=capabilities.contracts); "
            "assert validate_artifact(repository_payload, "
            "expected_contract_id=repository_contract, "
            "contracts=capabilities.contracts).record == parsed_repository; "
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
