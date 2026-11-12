"""The compact File Overview legend's rule, case by case.

``build_file_type_legend`` decides which families File Overview names under its
population bars; the browser only formats what it returns. The route's answer
is pinned against a real folder in ``cli-api-file-type-legend.tryscript.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser.file_type_legend import (
    LEGEND_MINIMUM_SHARE_PERCENT,
    LEGEND_TYPE_LIMIT,
    build_file_type_legend,
)
from metabrowser.wire_models import FileTypeBreakdown, validate_file_type_legend

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_MODEL = ROOT / "src/metabrowser/builtin_plugins/folder/file-type-summary-model.js"
SESSION_FIXTURE = ROOT / "tests/dom/fixtures/file-overview-many-types-rollup.json"


def _metrics(
    files: int, size: int, unignored_files: int | None = None, unignored_size: int | None = None
) -> dict[str, dict[str, int]]:
    return {
        "all": {"files": files, "bytes": size},
        "unignored": {
            "files": files if unignored_files is None else unignored_files,
            "bytes": size if unignored_size is None else unignored_size,
        },
    }


def _breakdown(
    groups: dict[str, list[tuple[str, dict[str, dict[str, int]]]]],
    no_extension: dict[str, dict[str, int]] | None = None,
    remaining: dict[str, dict[str, int]] | None = None,
) -> FileTypeBreakdown:
    """A breakdown with these families, and the two special rollups, conserved."""

    no_extension = no_extension or _metrics(0, 0)
    remaining = remaining or _metrics(0, 0)
    parts = [m for families in groups.values() for _, m in families] + [no_extension, remaining]
    root = {
        population: {
            measure: sum(part[population][measure] for part in parts)
            for measure in ("files", "bytes")
        }
        for population in ("all", "unignored")
    }
    return cast(
        "FileTypeBreakdown",
        {
            "schema": "file-type-breakdown-v1",
            "registry": {"schema_version": 1, "revision": 1, "fingerprint": "test"},
            "metrics": root,
            "groups": [
                {
                    "id": group_id,
                    "families": [
                        {"id": family_id, "metrics": metrics, "extensions": []}
                        for family_id, metrics in families
                    ],
                }
                for group_id, families in groups.items()
            ],
            "no_extension": {"metrics": no_extension, "filenames": [], "others": None},
            "remaining_types": {"metrics": remaining, "extensions": [], "others": None},
        },
    )


def _named(legend: Any, measure: str = "files", population: str = "all") -> list[str]:
    return [entry["family"] for entry in legend[measure][population]["named"]]


# Eight families in four groups and the two special rollups, with Other types the
# largest bucket of all by files, a mostly ignored JSON tree, and a different
# order by bytes.
MANY = _breakdown(
    {
        "code": [
            ("typescript", _metrics(60, 200)),
            ("python", _metrics(33, 150)),
            ("javascript", _metrics(25, 120)),
            ("rust", _metrics(8, 5)),
        ],
        "docs": [("markdown", _metrics(150, 300))],
        "data": [("json", _metrics(240, 100, 40, 20)), ("yaml", _metrics(170, 50))],
        "other": [("log", _metrics(21, 25))],
    },
    no_extension=_metrics(40, 20),
    remaining=_metrics(253, 30),
)


def test_names_the_five_largest_families_across_groups_then_other() -> None:
    legend = build_file_type_legend(MANY)
    assert legend is not None
    view = legend["files"]["all"]
    assert view == {
        "total": 1000,
        "named": [
            {"family": "json", "value": 240},
            {"family": "yaml", "value": 170},
            {"family": "markdown", "value": 150},
            {"family": "typescript", "value": 60},
            {"family": "python", "value": 33},
        ],
        # JavaScript, Rust, and Log files, plus both special rollups.
        "other": 347,
    }


def test_never_names_no_extension_or_other_types() -> None:
    only_special = _breakdown(
        {"code": [("python", _metrics(1, 1))]},
        no_extension=_metrics(500, 500),
        remaining=_metrics(499, 499),
    )
    legend = build_file_type_legend(only_special)
    assert legend is not None
    # Python is 0.1% of the folder, under the floor; the special rollups are larger
    # and still not candidates.
    assert legend["files"]["all"] == {"total": 1000, "named": [], "other": 1000}


def test_follows_the_measure_and_the_population() -> None:
    legend = build_file_type_legend(MANY)
    assert _named(legend, "bytes", "all") == [
        "markdown",
        "typescript",
        "python",
        "javascript",
        "json",
    ]
    assert legend is not None
    assert legend["bytes"]["all"]["other"] == 130
    assert _named(legend, "files", "unignored") == [
        "yaml",
        "markdown",
        "typescript",
        "json",
        "python",
    ]
    assert legend["files"]["unignored"]["total"] == 800
    assert _named(legend, "bytes", "unignored")[-1] == "yaml"


@pytest.mark.parametrize(
    ("rust_files", "named"),
    [
        # Below the floor, exactly at it, and just above it, of 1,000 files.
        (9, False),
        (10, False),
        (11, True),
    ],
)
def test_names_a_family_only_above_the_share_floor(rust_files: int, named: bool) -> None:
    breakdown = _breakdown(
        {"code": [("python", _metrics(1000 - rust_files, 1)), ("rust", _metrics(rust_files, 1))]}
    )
    legend = build_file_type_legend(breakdown)
    assert ("rust" in _named(legend)) is named
    assert legend is not None
    view = legend["files"]["all"]
    assert view["other"] == (0 if named else rust_files)


def test_names_at_most_five_however_many_clear_the_floor() -> None:
    families = [(f"f{index}", _metrics(100, 100)) for index in range(8)]
    legend = build_file_type_legend(_breakdown({"code": families}))
    assert legend is not None
    view = legend["files"]["all"]
    assert len(view["named"]) == LEGEND_TYPE_LIMIT == 5
    assert view["other"] == 300


def test_breaks_ties_by_the_other_measure_then_the_family_id() -> None:
    breakdown = _breakdown(
        {
            "code": [
                ("b", _metrics(10, 5)),
                ("a", _metrics(10, 5)),
                ("c", _metrics(10, 9)),
            ]
        }
    )
    assert _named(build_file_type_legend(breakdown)) == ["c", "a", "b"]


def test_values_and_other_add_up_to_the_population_in_every_view() -> None:
    legend = build_file_type_legend(MANY)
    assert legend is not None
    for measure in ("files", "bytes"):
        for population in ("all", "unignored"):
            view = legend[measure][population]
            assert sum(e["value"] for e in view["named"]) + view["other"] == view["total"]
            assert view["total"] == MANY["metrics"][population][measure]


def test_names_everything_and_leaves_no_other_when_named_families_cover_it() -> None:
    legend = build_file_type_legend(_breakdown({"code": [("python", _metrics(10, 10))]}))
    assert legend is not None
    assert legend["files"]["all"] == {
        "total": 10,
        "named": [{"family": "python", "value": 10}],
        "other": 0,
    }


def test_an_empty_measure_names_nothing() -> None:
    legend = build_file_type_legend(_breakdown({"code": [("python", _metrics(10, 0))]}))
    assert legend is not None
    assert legend["bytes"]["all"] == {"total": 0, "named": [], "other": 0}


def test_no_breakdown_has_no_legend() -> None:
    assert build_file_type_legend(None) is None


def test_the_floor_is_the_one_the_breakdown_table_folds_at() -> None:
    """The legend never names a family the Details table folds into "N more"."""

    source = SUMMARY_MODEL.read_text(encoding="utf-8")
    match = re.search(r"^const MINIMUM_VISIBLE_SHARE = (\d+);$", source, re.MULTILINE)
    assert match, "MINIMUM_VISIBLE_SHARE not found in file-type-summary-model.js"
    assert int(match.group(1)) == LEGEND_MINIMUM_SHARE_PERCENT


def test_the_file_overview_session_fixture_carries_the_routes_legend() -> None:
    """The browserless session reads a rollup whose legend this rule produced."""

    rollup = json.loads(SESSION_FIXTURE.read_text(encoding="utf-8"))
    assert rollup["file_type_legend"] == build_file_type_legend(rollup["file_type_breakdown"])


def test_the_wire_validator_holds_an_envelope_to_the_rule() -> None:
    legend = build_file_type_legend(MANY)
    validate_file_type_legend(legend, MANY)
    tampered = json.loads(json.dumps(legend))
    tampered["files"]["all"]["other"] += 1
    with pytest.raises(AssertionError, match="does not follow from its breakdown"):
        validate_file_type_legend(tampered, MANY)
