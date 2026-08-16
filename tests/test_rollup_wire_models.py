"""Validation contracts for rollup results and route envelopes."""

from __future__ import annotations

from typing import Any

import pytest

from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.wire_models import (
    validate_extension_tallies,
    validate_file_type_breakdown,
    validate_rollup_envelope,
    validate_rollup_result,
)


def _node() -> dict[str, object]:
    return {
        "name": "root",
        "path": "",
        "type": "dir",
        "state": "complete",
        "total_files": 3,
        "total_size": 12,
        "unignored_files": 2,
        "unignored_size": 7,
        "mtime": 1.0,
        "gitignored": False,
        "dominant_ext": ".py",
        "children": None,
    }


def _metrics(
    all_files: int, all_bytes: int, unignored_files: int, unignored_bytes: int
) -> dict[str, Any]:
    return {
        "all": {"files": all_files, "bytes": all_bytes},
        "unignored": {"files": unignored_files, "bytes": unignored_bytes},
    }


def _breakdown() -> dict[str, Any]:
    """Two Python files plus one ignored unknown extension, conserved to the root."""

    registry = load_file_type_registry()
    return {
        "schema": "file-type-breakdown-v1",
        "registry": {
            "schema_version": registry.schema_version,
            "revision": registry.revision,
            "fingerprint": registry.fingerprint,
        },
        "metrics": _metrics(3, 12, 2, 7),
        "groups": [
            {
                "id": "code",
                "families": [
                    {
                        "id": "python",
                        "metrics": _metrics(2, 7, 2, 7),
                        "extensions": [{"extension": ".py", "metrics": _metrics(2, 7, 2, 7)}],
                    }
                ],
            }
        ],
        "no_extension": {"metrics": _metrics(0, 0, 0, 0), "filenames": [], "others": None},
        "remaining_types": {
            "metrics": _metrics(1, 5, 0, 0),
            "extensions": [{"extension": ".unknown", "metrics": _metrics(1, 5, 0, 0)}],
            "others": None,
        },
    }


def test_extension_tallies_require_exact_unique_nonnegative_rows() -> None:
    validate_extension_tallies([[".py", 2, 7, 2, 7], ["", 1, 5, 0, 0]])

    invalid_rows = (
        [[".py", 1, 2, 1]],
        [[".py", 1, 2, 1, 2], [".py", 0, 0, 0, 0]],
        [["", 1, 2, 1, 2], [".py", 0, 0, 0, 0]],
        [[".py", -1, 2, 0, 0]],
        [[".py", 1, 2, 2, 0]],
        [[".py", 1, 2, 1, 3]],
    )
    for rows in invalid_rows:
        with pytest.raises(AssertionError):
            validate_extension_tallies(rows)


def test_rollup_result_requires_tallies_to_sum_to_root() -> None:
    result: dict[str, Any] = {
        "node": _node(),
        "ext_tallies": [[".py", 2, 7, 2, 7], ["", 1, 5, 0, 0]],
        "file_type_breakdown": _breakdown(),
    }
    validate_rollup_result(result)

    result["ext_tallies"] = [[".py", 2, 7, 2, 7]]
    with pytest.raises(AssertionError):
        validate_rollup_result(result)


def test_breakdown_requires_conserved_known_families() -> None:
    validate_file_type_breakdown(_breakdown(), _node())

    inflated = _breakdown()
    inflated["groups"][0]["families"][0]["metrics"] = _metrics(3, 7, 2, 7)
    with pytest.raises(AssertionError):
        validate_file_type_breakdown(inflated, _node())

    stale = _breakdown()
    stale["registry"]["fingerprint"] = "stale"
    with pytest.raises(AssertionError):
        validate_file_type_breakdown(stale, _node())


def test_rollup_envelope_accepts_honest_cold_state() -> None:
    validate_rollup_envelope(
        {
            "root": "/served",
            "path": "nested",
            "node": None,
            "ext_tallies": [],
            "file_type_breakdown": None,
            "index_status": "scanning",
            "indexed_files": 0,
            "max_files": 500_000,
            "truncated": False,
        }
    )

    with pytest.raises(AssertionError):
        validate_rollup_envelope(
            {
                "root": "/served",
                "path": "nested",
                "node": None,
                "ext_tallies": [[".py", 1, 1, 1, 1]],
                "file_type_breakdown": None,
                "index_status": "scanning",
                "indexed_files": 0,
                "max_files": 500_000,
                "truncated": False,
            }
        )
