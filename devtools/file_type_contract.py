"""Generate, check, and export the versioned file-type compatibility packet."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
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
    destination.mkdir(parents=True, exist_ok=True)
    source_paths = (
        REGISTRY_SOURCE_PATH,
        REGISTRY_PROJECTION_PATH,
        CONFORMANCE_PATH,
        EMPTY_BREAKDOWN_PATH,
        *SCHEMA_PATHS,
    )
    for source in source_paths:
        target = destination / source.name
        with atomic_output_file(target, make_parents=True) as temporary:
            temporary.write_bytes(source.read_bytes())
    docs_destination = destination / "docs"
    for source in CONTRACT_DOC_PATHS:
        target = docs_destination / source.name
        with atomic_output_file(target, make_parents=True) as temporary:
            temporary.write_bytes(source.read_bytes())
    registry = load_file_type_registry()
    manifest = {
        "schema": "file-type-adoption-packet-v1",
        "source_revision": source_revision,
        "registry_schema_version": registry.schema_version,
        "registry_revision": registry.revision,
        "registry_fingerprint": registry.fingerprint,
        "files": sorted(
            [source.name for source in source_paths]
            + [f"docs/{source.name}" for source in CONTRACT_DOC_PATHS]
        ),
    }
    with atomic_output_file(destination / "manifest.json", make_parents=True) as temporary:
        temporary.write_bytes(_json_bytes(manifest))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="update checked generated artifacts")
    mode.add_argument("--export", type=Path, help="write an adoption packet to this directory")
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
    elif args.write:
        write_artifacts()
    else:
        check_artifacts()


if __name__ == "__main__":
    main()
