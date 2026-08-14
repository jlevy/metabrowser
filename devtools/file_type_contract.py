"""Generate, check, and export the versioned file-type compatibility packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from textwrap import dedent
from typing import cast

import jsonschema
from strif import atomic_output_file

from metabrowser.events import FsEntry
from metabrowser.file_type_registry import (
    FileTypeClassification,
    load_file_type_registry,
)
from metabrowser.inventory_rollup import RollupOptions, build_rollup, group_rollup_children

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPOSITORY_ROOT / "src" / "metabrowser" / "data"
CONTRACT_ROOT = DATA_ROOT / "file-types"
CONFORMANCE_PATH = CONTRACT_ROOT / "conformance-v1.json"
REGISTRY_PROJECTION_PATH = CONTRACT_ROOT / "registry-v1.json"
EMPTY_BREAKDOWN_PATH = CONTRACT_ROOT / "breakdown-empty-v1.json"
REGISTRY_SOURCE_PATH = DATA_ROOT / "file-types.toml"
SCHEMA_PATHS = (
    CONTRACT_ROOT / "registry-v1.schema.json",
    CONTRACT_ROOT / "breakdown-v1.schema.json",
    CONTRACT_ROOT / "conformance-v1.schema.json",
)
CONTRACT_DOC_PATHS = (
    REPOSITORY_ROOT / "docs" / "project" / "architecture" / "file-types" / "README.md",
    REPOSITORY_ROOT / "docs" / "project" / "architecture" / "file-types" / "registry-v1.md",
    REPOSITORY_ROOT / "docs" / "project" / "architecture" / "file-types" / "interchange-v1.md",
    REPOSITORY_ROOT / "docs" / "project" / "architecture" / "file-types" / "fdu-compatibility.md",
)
PACKET_MANIFEST_NAME = "manifest.json"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _classification_payload(classification: FileTypeClassification) -> dict[str, object]:
    return {
        "logical_extension": classification.logical_extension,
        "canonical_extension": classification.canonical_extension,
        "kind_id": classification.kind_id,
        "family_id": classification.family_id,
        "group_id": classification.group_id,
        "content_family": classification.content_family.value,
        "detection_source": classification.detection_source,
        "confidence": classification.confidence,
    }


def _empty_breakdown() -> dict[str, object]:
    registry = load_file_type_registry()
    metrics = {
        "all": {"files": 0, "bytes": 0},
        "unignored": {"files": 0, "bytes": 0},
    }
    return {
        "schema": "file-type-breakdown-v1",
        "registry": {
            "schema_version": registry.schema_version,
            "revision": registry.revision,
            "fingerprint": registry.fingerprint,
        },
        "metrics": metrics,
        "groups": [],
        "no_extension": {"metrics": metrics, "filenames": [], "others": None},
        "remaining_types": {"metrics": metrics, "extensions": [], "others": None},
    }


def _breakdown_for_facts(facts: list[dict[str, object]]) -> dict[str, object]:
    root = FsEntry.for_observed_dir(path="", parent="", name="root")
    entries = {"": root}
    for index, fact in enumerate(facts):
        basename = str(fact["basename"])
        apparent_bytes = fact["apparent_bytes"]
        ignored = fact["ignored"]
        if not isinstance(apparent_bytes, int) or not isinstance(ignored, bool):
            raise TypeError(
                "aggregate fixture facts must contain integer bytes and boolean ignored"
            )
        entry = FsEntry.for_observed_file(
            path=f"fixture/{index}/{basename}",
            parent="",
            name=basename,
            size=apparent_bytes,
            mtime_ns=1_700_000_000_000_000_000,
        )
        entries[entry.path] = replace(entry, gitignored=ignored)
    result = build_rollup(
        entries,
        group_rollup_children(entries),
        "",
        RollupOptions(
            depth=0,
            top=0,
            ext_top=0,
            max_nodes=1,
            type_top=20,
            filename_top=20,
            ext_rank="dual",
        ),
        ancestor_gitignored=False,
    )
    if result is None:
        raise RuntimeError("fixture rollup did not produce a root")
    return cast(dict[str, object], result["file_type_breakdown"])


def _aggregate_cases() -> list[dict[str, object]]:
    mixed_facts: list[dict[str, object]] = [
        {"basename": "events.jsonl", "apparent_bytes": 100, "ignored": False},
        {"basename": "notes.log", "apparent_bytes": 80, "ignored": True},
        {"basename": "photo.svg", "apparent_bytes": 60, "ignored": False},
        {"basename": "bundle.tar.gz", "apparent_bytes": 200, "ignored": False},
    ]
    mixed_facts.extend(
        {"basename": f"bare-{index}", "apparent_bytes": index, "ignored": index % 7 == 0}
        for index in range(23)
    )
    mixed_facts.extend(
        {
            "basename": f"unknown-{index}.x{index}",
            "apparent_bytes": 50 - index,
            "ignored": index % 5 == 0,
        }
        for index in range(23)
    )
    return [
        {"id": "empty-directory", "facts": [], "expected": _empty_breakdown()},
        {
            "id": "families-and-bounded-fallbacks",
            "facts": mixed_facts,
            "expected": _breakdown_for_facts(mixed_facts),
        },
    ]


def _minimal_registry() -> str:
    return dedent(
        """
        schema_version = 1
        registry_revision = 1
        max_extension_components = 2

        [[group]]
        id = "code"
        label = "Code"
        order = 10

        [[group]]
        id = "other"
        label = "Other"
        order = 20

        [[family]]
        id = "python"
        label = "Python"
        group = "code"
        order = 10

        [[kind]]
        id = "python"
        family = "python"
        content_family = "code"
        extensions = ["py"]
        filenames = []
        shebangs = []
        priority = 100
        """
    ).strip()


def _invalid_registry_cases() -> list[dict[str, str]]:
    base = _minimal_registry()
    duplicate_kind = dedent(
        """

        [[kind]]
        id = "python-copy"
        group = "code"
        content_family = "code"
        extensions = ["py"]
        filenames = []
        shebangs = []
        priority = 1
        """
    )
    empty_family = dedent(
        """

        [[family]]
        id = "empty"
        label = "Empty"
        group = "code"
        order = 30
        """
    )
    raw_cases = (
        ("invalid-toml", "not = [valid", "invalid-toml"),
        (
            "unsupported-schema",
            base.replace("schema_version = 1", "schema_version = 2"),
            "unsupported-schema-version",
        ),
        (
            "unsupported-components",
            base.replace("max_extension_components = 2", "max_extension_components = 3"),
            "unsupported-extension-components",
        ),
        (
            "invalid-field",
            base.replace("registry_revision = 1", "registry_revision = 0"),
            "invalid-field",
        ),
        ("invalid-id", base.replace('id = "code"', 'id = "code_name"', 1), "invalid-id"),
        (
            "missing-fallback",
            base.replace('id = "other"', 'id = "fallback"', 1),
            "missing-fallback",
        ),
        (
            "duplicate-order",
            base.replace("order = 20", "order = 10", 1),
            "duplicate-order",
        ),
        (
            "unknown-group",
            base.replace('group = "code"', 'group = "missing"'),
            "unknown-group",
        ),
        (
            "unknown-family",
            base.replace('family = "python"', 'family = "missing"'),
            "unknown-family",
        ),
        (
            "invalid-content-family",
            base.replace('content_family = "code"', 'content_family = "mystery"'),
            "invalid-content-family",
        ),
        (
            "invalid-extension",
            base.replace('extensions = ["py"]', 'extensions = [".py"]'),
            "invalid-extension",
        ),
        ("duplicate-evidence", base + duplicate_kind, "duplicate-evidence"),
        (
            "familyless-kind-without-group",
            base
            + dedent(
                """

                [[kind]]
                id = "standalone"
                content_family = "code"
                extensions = ["standalone"]
                filenames = []
                shebangs = []
                priority = 1
                """
            ),
            "invalid-field",
        ),
        (
            "family-group-mismatch",
            base.replace('family = "python"', 'family = "python"\ngroup = "other"'),
            "group-mismatch",
        ),
        ("empty-family", base + empty_family, "empty-family"),
        (
            "missing-evidence",
            base.replace('extensions = ["py"]', "extensions = []"),
            "missing-evidence",
        ),
    )
    return [
        {"id": case_id, "toml": toml, "error_code": error_code}
        for case_id, toml, error_code in raw_cases
    ]


def build_conformance() -> dict[str, object]:
    """Generate all declaration cases plus focused matching boundaries."""

    registry = load_file_type_registry()
    cases: list[dict[str, object]] = []
    for kind in registry.kinds:
        for extension in kind.extensions:
            logical_extension = f".{extension}"
            name = f"sample{logical_extension}"
            cases.append(
                {
                    "name": name,
                    "logical_extension": logical_extension,
                    "expected": _classification_payload(registry.classify(name, logical_extension)),
                }
            )
        for filename in kind.filenames:
            cases.append(
                {
                    "name": filename.upper(),
                    "logical_extension": None,
                    "expected": _classification_payload(registry.classify(filename, "")),
                }
            )
    for name, extension in (
        ("bundle.min.js", ".min.js"),
        ("types.d.ts", ".d.ts"),
        ("bundle.js.map", ".js.map"),
        ("archive.tar.gz", ".tar.gz"),
        ("PHOTO.JPEG", ".jpeg"),
        (".eslintrc.json", ".json"),
        (".gitignore", ""),
        ("unknown.zzz", ".zzz"),
    ):
        cases.append(
            {
                "name": name,
                "logical_extension": extension or None,
                "expected": _classification_payload(registry.classify(name, extension)),
            }
        )
    return {
        "schema": "file-type-conformance-v1",
        "registry": {
            "schema_version": registry.schema_version,
            "revision": registry.revision,
            "fingerprint": registry.fingerprint,
        },
        "metadata_cases": cases,
        "invalid_registry_cases": _invalid_registry_cases(),
        "aggregate_cases": _aggregate_cases(),
    }


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _generated_artifacts() -> dict[Path, bytes]:
    return {
        REGISTRY_PROJECTION_PATH: _json_bytes(load_file_type_registry().projection()),
        CONFORMANCE_PATH: _json_bytes(build_conformance()),
        EMPTY_BREAKDOWN_PATH: _json_bytes(_empty_breakdown()),
    }


def _validate_artifacts(artifacts: dict[Path, bytes]) -> None:
    registry_schema = json.loads(SCHEMA_PATHS[0].read_text(encoding="utf-8"))
    breakdown_schema = json.loads(SCHEMA_PATHS[1].read_text(encoding="utf-8"))
    conformance_schema = json.loads(SCHEMA_PATHS[2].read_text(encoding="utf-8"))
    jsonschema.validate(json.loads(artifacts[REGISTRY_PROJECTION_PATH]), registry_schema)
    conformance = json.loads(artifacts[CONFORMANCE_PATH])
    jsonschema.validate(conformance, conformance_schema)
    for case in conformance["aggregate_cases"]:
        jsonschema.validate(case["expected"], breakdown_schema)
    jsonschema.validate(json.loads(artifacts[EMPTY_BREAKDOWN_PATH]), breakdown_schema)


def check_artifacts() -> None:
    """Fail when checked compatibility artifacts drift from the registry."""

    artifacts = _generated_artifacts()
    _validate_artifacts(artifacts)
    stale = [
        path
        for path, expected in artifacts.items()
        if not path.is_file() or path.read_bytes() != expected
    ]
    if stale:
        paths = ", ".join(str(path.relative_to(REPOSITORY_ROOT)) for path in stale)
        raise RuntimeError(f"file-type contract artifacts are stale: {paths}")


def write_artifacts() -> None:
    """Atomically update generated compatibility artifacts."""

    artifacts = _generated_artifacts()
    _validate_artifacts(artifacts)
    for path, content in artifacts.items():
        with atomic_output_file(path, make_parents=True) as temporary:
            temporary.write_bytes(content)


def export_packet(destination: Path, source_revision: str) -> None:
    """Copy a self-contained reviewed packet to an explicit destination."""

    check_artifacts()
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise RuntimeError("file-type packet destination must be a real directory")
    destination.mkdir(parents=True, exist_ok=True)
    source_paths = (
        REGISTRY_SOURCE_PATH,
        REGISTRY_PROJECTION_PATH,
        CONFORMANCE_PATH,
        EMPTY_BREAKDOWN_PATH,
        *SCHEMA_PATHS,
    )
    packet_sources = [(source.name, source) for source in source_paths]
    packet_sources.extend((f"docs/{source.name}", source) for source in CONTRACT_DOC_PATHS)
    expected = {relative_path for relative_path, _source in packet_sources} | {PACKET_MANIFEST_NAME}
    _prune_packet_destination(destination, expected)
    manifest_files: list[dict[str, str]] = []
    for relative_path, source in sorted(packet_sources):
        content = source.read_bytes()
        target = destination / relative_path
        with atomic_output_file(target, make_parents=True) as temporary:
            temporary.write_bytes(content)
        manifest_files.append(
            {
                "path": relative_path,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    registry = load_file_type_registry()
    manifest = {
        "schema": "file-type-adoption-packet-v1",
        "source_revision": source_revision,
        "registry_schema_version": registry.schema_version,
        "registry_revision": registry.revision,
        "registry_fingerprint": registry.fingerprint,
        "files": manifest_files,
    }
    with atomic_output_file(destination / PACKET_MANIFEST_NAME, make_parents=True) as temporary:
        temporary.write_bytes(_json_bytes(manifest))
    _prune_packet_destination(destination, expected)
    verify_packet(destination)


def _safe_packet_path(raw_path: object) -> PurePosixPath:
    if not isinstance(raw_path, str) or not raw_path:
        raise RuntimeError("file-type packet manifest contains an invalid path")
    path = PurePosixPath(raw_path)
    windows_path = PureWindowsPath(raw_path)
    if (
        "\\" in raw_path
        or path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or path.as_posix() != raw_path
        or any(component in ("", ".", "..") for component in path.parts)
    ):
        raise RuntimeError(f"file-type packet manifest contains an unsafe path: {raw_path!r}")
    return path


def _packet_expected_directories(paths: set[str]) -> set[str]:
    directories: set[str] = set()
    for raw_path in paths:
        parent = PurePosixPath(raw_path).parent
        while parent != PurePosixPath("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _prune_packet_destination(destination: Path, expected_files: set[str]) -> None:
    expected_directories = _packet_expected_directories(expected_files)
    for path in sorted(destination.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        relative = path.relative_to(destination).as_posix()
        if path.is_symlink() or path.is_file():
            if relative not in expected_files:
                path.unlink()
        elif path.is_dir() and relative not in expected_directories:
            path.rmdir()


def verify_packet(destination: Path) -> None:
    """Verify manifest shape, safe paths, exact contents, and every file hash."""

    if destination.is_symlink() or not destination.is_dir():
        raise RuntimeError("file-type packet must be a real directory")
    for path in destination.rglob("*"):
        if path.is_symlink():
            relative = path.relative_to(destination).as_posix()
            raise RuntimeError(f"file-type packet contains a symbolic link: {relative!r}")
    manifest_path = destination / PACKET_MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise RuntimeError("file-type packet manifest is missing or invalid")
    try:
        raw_manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("file-type packet manifest is unreadable") from error
    if not isinstance(raw_manifest, dict):
        raise RuntimeError("file-type packet manifest must be an object")
    manifest = cast(dict[str, object], raw_manifest)
    if manifest.get("schema") != "file-type-adoption-packet-v1":
        raise RuntimeError("file-type packet manifest has an unsupported schema")
    if not isinstance(manifest.get("source_revision"), str) or not manifest["source_revision"]:
        raise RuntimeError("file-type packet manifest has an invalid source revision")
    if manifest.get("registry_schema_version") != 1:
        raise RuntimeError("file-type packet manifest has an unsupported registry schema")
    if (
        not isinstance(manifest.get("registry_revision"), int)
        or isinstance(manifest["registry_revision"], bool)
        or cast(int, manifest["registry_revision"]) < 1
    ):
        raise RuntimeError("file-type packet manifest has an invalid registry revision")
    fingerprint = manifest.get("registry_fingerprint")
    if not isinstance(fingerprint, str) or not _SHA256.fullmatch(fingerprint):
        raise RuntimeError("file-type packet manifest has an invalid registry fingerprint")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise RuntimeError("file-type packet manifest files must be an array")
    files = cast(list[object], raw_files)

    expected_files = {PACKET_MANIFEST_NAME}
    for raw_item in files:
        if not isinstance(raw_item, dict):
            raise RuntimeError("file-type packet manifest file entry is invalid")
        item = cast(dict[str, object], raw_item)
        if set(item) != {"path", "sha256"}:
            raise RuntimeError("file-type packet manifest file entry is invalid")
        relative = _safe_packet_path(item["path"])
        raw_path = relative.as_posix()
        digest = item["sha256"]
        if raw_path == PACKET_MANIFEST_NAME or raw_path in expected_files:
            raise RuntimeError(f"file-type packet manifest path is duplicated: {raw_path!r}")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise RuntimeError(f"file-type packet manifest hash is invalid: {raw_path!r}")
        target = destination.joinpath(*relative.parts)
        if not target.is_file() or target.is_symlink():
            raise RuntimeError(f"file-type packet file is missing or invalid: {raw_path!r}")
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"file-type packet hash mismatch: {raw_path!r}")
        expected_files.add(raw_path)

    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for path in destination.rglob("*"):
        relative = path.relative_to(destination).as_posix()
        if path.is_symlink():
            raise RuntimeError(f"file-type packet contains a symbolic link: {relative!r}")
        if path.is_file():
            actual_files.add(relative)
        elif path.is_dir():
            actual_directories.add(relative)
    if actual_files != expected_files:
        extras = sorted(actual_files - expected_files)
        missing = sorted(expected_files - actual_files)
        raise RuntimeError(f"file-type packet contents differ: extras={extras}, missing={missing}")
    expected_directories = _packet_expected_directories(expected_files)
    if actual_directories != expected_directories:
        extras = sorted(actual_directories - expected_directories)
        missing = sorted(expected_directories - actual_directories)
        raise RuntimeError(
            f"file-type packet directories differ: extras={extras}, missing={missing}"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="update checked generated artifacts")
    mode.add_argument("--export", type=Path, help="write an adoption packet to this directory")
    mode.add_argument("--verify", type=Path, help="verify an existing adoption packet")
    parser.add_argument(
        "--source-revision",
        help="reviewed Metabrowser Git revision recorded in an exported packet",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.export is not None:
        if not args.source_revision:
            raise SystemExit("--export requires --source-revision")
        export_packet(args.export, args.source_revision)
    elif args.verify is not None:
        if args.source_revision:
            raise SystemExit("--source-revision is only valid with --export")
        verify_packet(args.verify)
    elif args.write:
        write_artifacts()
    else:
        check_artifacts()


if __name__ == "__main__":
    main()
