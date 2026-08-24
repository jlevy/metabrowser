"""Validity and equivalence guards for the installed-build comparator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devtools.compare_builds import (
    comparison_failures,
    comparison_payload,
    differences,
    missing_required_fields,
    normalise,
    resolve_tree,
    write_report,
)


def _equivalence(*, differences_found: int = 0) -> dict[str, Any]:
    return {
        channel: {
            "difference_count": differences_found,
            "differences": [],
            "missing_fields": {},
        }
        for channel in ("rows", "tallies")
    }


def test_relative_tree_is_resolved_before_the_server_changes_directory(
    tmp_path: Path, monkeypatch: Any
) -> None:
    tree = tmp_path / "corpus"
    tree.mkdir()
    monkeypatch.chdir(tmp_path)

    assert resolve_tree("corpus") == tree.resolve()


def test_normalise_preserves_list_order_and_nested_contract_fields() -> None:
    payload = {
        "tree": [{"path": "z"}, {"path": "a"}],
        "file_type_registry": {"schema_version": 3},
        "nested": {"duration_ms": 17, "version": "wire-v2"},
    }

    assert normalise(payload) == payload


def test_row_projection_ignores_only_the_separate_tally_channel() -> None:
    baseline = {
        "root": "/tree",
        "tree": [{"path": "a"}, {"path": "b"}],
        "summary": {"files": 2},
    }
    candidate = {
        "root": "/tree",
        "tree": [{"path": "a"}, {"path": "b"}],
        "summary": None,
    }

    assert comparison_payload("rows", baseline) == comparison_payload("rows", candidate)
    assert comparison_payload("tallies", baseline) != comparison_payload("tallies", candidate)


def test_tree_row_order_is_semantic() -> None:
    baseline = comparison_payload("rows", {"root": "/tree", "tree": [{"path": "a"}, {"path": "b"}]})
    candidate = comparison_payload(
        "rows", {"root": "/tree", "tree": [{"path": "b"}, {"path": "a"}]}
    )
    found: list[str] = []

    differences(normalise(baseline), normalise(candidate), "rows", found)

    assert found
    assert any("rows.tree[0].path" in item for item in found)


def test_required_fields_reject_two_equally_malformed_responses() -> None:
    assert missing_required_fields("rows", {}) == ["root", "tree"]
    assert missing_required_fields("tallies", []) == ["<object>"]


def test_comparison_is_valid_only_when_runs_corpus_and_answers_are_valid() -> None:
    report = {
        "corpus_unchanged": True,
        "equivalence": _equivalence(),
        "errors": [],
    }

    assert comparison_failures(report) == []


def test_comparison_reports_every_invalidating_condition() -> None:
    equivalence = _equivalence(differences_found=2)
    equivalence["rows"]["missing_fields"] = {"candidate": ["tree"]}
    report = {
        "corpus_unchanged": False,
        "equivalence": equivalence,
        "errors": ["never settled"],
    }

    failures = comparison_failures(report)

    assert "run failed: never settled" in failures
    assert "corpus changed during comparison" in failures
    assert any("rows response is missing required fields" in failure for failure in failures)
    assert "rows responses differ (2 found)" in failures
    assert "tallies responses differ (2 found)" in failures


def test_missing_equivalence_results_invalidate_the_comparison() -> None:
    failures = comparison_failures(
        {"corpus_unchanged": True, "equivalence": {"rows": _equivalence()["rows"]}, "errors": []}
    )

    assert failures == ["tallies equivalence result is missing"]


def test_report_is_written_as_machine_readable_json(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "comparison.json"
    report = {"valid": True, "timings": {"first_row": {"candidate": {"median": 1.2}}}}

    write_report(report, output)

    assert json.loads(output.read_text(encoding="utf-8")) == report
