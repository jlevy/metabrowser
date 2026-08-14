"""Shared file-type schemas, corpus, and adoption-packet behavior."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from devtools.file_type_contract import (
    CONFORMANCE_PATH,
    check_artifacts,
    export_packet,
    verify_packet,
)
from metabrowser.file_type_registry import (
    FileTypeRegistryError,
    load_file_type_registry,
    load_file_type_registry_from_text,
)


def test_checked_contract_artifacts_match_the_registry() -> None:
    check_artifacts()


def test_conformance_corpus_matches_python_classification() -> None:
    corpus = json.loads(CONFORMANCE_PATH.read_text(encoding="utf-8"))
    registry = load_file_type_registry()
    for case in corpus["metadata_cases"]:
        classification = registry.classify(case["name"], case["logical_extension"] or "")
        assert {
            "logical_extension": classification.logical_extension,
            "canonical_extension": classification.canonical_extension,
            "kind_id": classification.kind_id,
            "family_id": classification.family_id,
            "group_id": classification.group_id,
            "content_family": classification.content_family.value,
            "detection_source": classification.detection_source,
            "confidence": classification.confidence,
        } == case["expected"]
    for case in corpus["invalid_registry_cases"]:
        try:
            load_file_type_registry_from_text(case["toml"])
        except FileTypeRegistryError as error:
            assert error.code == case["error_code"]
        else:
            raise AssertionError(f"invalid registry case was accepted: {case['id']}")


def test_export_packet_is_self_contained_and_revision_pinned(tmp_path: Path) -> None:
    destination = tmp_path / "file-rollup-format"
    (destination / "stale").mkdir(parents=True)
    (destination / "stale" / "orphan.txt").write_text("old", encoding="utf-8")
    export_packet(destination, "abc123")
    verify_packet(destination)
    assert not (destination / "stale").exists()

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_revision"] == "abc123"
    assert manifest["registry_fingerprint"] == load_file_type_registry().fingerprint
    manifest_files = manifest["files"]
    actual_paths = {
        str(path.relative_to(destination))
        for path in destination.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    assert {item["path"] for item in manifest_files} == actual_paths
    assert {
        "recommended-file-types.toml",
        "recommended-file-types.json",
        "file-type-registry.schema.json",
        "file-rollup.schema.json",
        "file-rollup-conformance.schema.json",
        "file-rollup-conformance.json",
        "empty-file-rollup.json",
        "docs/file-rollup-format.md",
    } <= actual_paths
    assert not any(
        path.endswith(("registry-v1.json", "conformance-v1.json")) for path in actual_paths
    )
    for item in manifest_files:
        assert set(item) == {"path", "sha256"}
        assert (
            item["sha256"] == hashlib.sha256((destination / item["path"]).read_bytes()).hexdigest()
        )
    assert not any(
        "metabrowser.file_type" in path.read_text(encoding="utf-8")
        for path in destination.rglob("*.md")
    )


def test_verify_packet_rejects_tampering_and_unmanifested_content(tmp_path: Path) -> None:
    destination = tmp_path / "file-rollup-format"
    export_packet(destination, "abc123")
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    tracked = destination / manifest["files"][0]["path"]
    original = tracked.read_bytes()
    tracked.write_bytes(original + b"tampered")
    try:
        verify_packet(destination)
    except RuntimeError as error:
        assert "hash mismatch" in str(error)
    else:
        raise AssertionError("packet verification accepted a modified file")

    tracked.write_bytes(original)
    (destination / "orphan.txt").write_text("unexpected", encoding="utf-8")
    try:
        verify_packet(destination)
    except RuntimeError as error:
        assert "contents differ" in str(error)
    else:
        raise AssertionError("packet verification accepted an unmanifested file")
