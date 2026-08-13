"""Validation contracts for rollup results and route envelopes."""

from __future__ import annotations

import pytest

from metabrowser.wire_models import (
    validate_extension_tallies,
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
    result = {
        "node": _node(),
        "ext_tallies": [[".py", 2, 7, 2, 7], ["", 1, 5, 0, 0]],
    }
    validate_rollup_result(result)

    result["ext_tallies"] = [[".py", 2, 7, 2, 7]]
    with pytest.raises(AssertionError):
        validate_rollup_result(result)


def test_rollup_envelope_accepts_honest_cold_state() -> None:
    validate_rollup_envelope(
        {
            "root": "/served",
            "path": "nested",
            "node": None,
            "ext_tallies": [],
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
                "index_status": "scanning",
                "indexed_files": 0,
                "max_files": 500_000,
                "truncated": False,
            }
        )
