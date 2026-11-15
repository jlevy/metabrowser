"""The Group by model: which groups a tree splits into, their order, and the age bands.

The route that serves them is pinned end to end by
``tests/golden/cli-api-tree-groups.tryscript.md``; this pins the model's edges, which a
golden on a small fixture cannot reach: every band's bounds, and how a recency filter
cuts them.
"""

from __future__ import annotations

import pytest

from metabrowser.settings import RECENT_WINDOW_SECONDS
from metabrowser.tree_groups import AgeBand, age_band, groups_for, parse_group, parse_group_by

HOUR = 60 * 60
DAY = 24 * HOUR
LIVE = float(RECENT_WINDOW_SECONDS["live"] or 0)


def test_type_groups_list_documentation_first_and_other_last() -> None:
    assert [group.id for group in groups_for("type")] == [
        "docs",
        "code",
        "data",
        "archives",
        "media",
        "other",
    ]
    assert groups_for("type")[0].label == "Documentation"


def test_age_groups_are_the_recency_windows_then_older() -> None:
    assert [(group.id, group.label) for group in groups_for("age")] == [
        ("live", "Live"),
        ("1h", "Past hour"),
        ("24h", "Past day"),
        ("7d", "Past week"),
        ("30d", "Past month"),
        ("older", "Older"),
    ]


@pytest.mark.parametrize(
    ("group_id", "band"),
    [
        ("live", AgeBand(within_seconds=LIVE, older_than_seconds=None)),
        ("1h", AgeBand(within_seconds=HOUR, older_than_seconds=LIVE)),
        ("24h", AgeBand(within_seconds=DAY, older_than_seconds=HOUR)),
        ("7d", AgeBand(within_seconds=7 * DAY, older_than_seconds=DAY)),
        ("30d", AgeBand(within_seconds=30 * DAY, older_than_seconds=7 * DAY)),
        ("older", AgeBand(within_seconds=None, older_than_seconds=30 * DAY)),
    ],
)
def test_each_band_holds_only_what_the_windows_before_it_do_not(
    group_id: str, band: AgeBand
) -> None:
    group = parse_group(f"age:{group_id}")
    assert group is not None
    assert age_band(group, 0) == band
    assert not band.empty


def test_a_recency_filter_keeps_the_near_edge_and_empties_the_bands_past_it() -> None:
    def band(group_id: str, recency: int) -> AgeBand:
        group = parse_group(f"age:{group_id}")
        assert group is not None
        return age_band(group, recency)

    # Past day under a Past day filter is the whole band.
    assert band("24h", DAY) == AgeBand(within_seconds=DAY, older_than_seconds=HOUR)
    # Past day under a Past hour filter: nothing is both newer than an hour and older.
    assert band("24h", HOUR).empty
    # Older under any window is empty; Live under any window is Live.
    assert band("older", 30 * DAY).empty
    assert band("live", HOUR) == AgeBand(within_seconds=LIVE, older_than_seconds=None)


def test_unknown_groupings_mean_none() -> None:
    assert parse_group_by("size") is None
    assert parse_group_by("") is None
    assert parse_group("type:nope") is None
    assert parse_group("color:docs") is None
    assert parse_group("docs") is None
    group = parse_group("type:docs")
    assert group is not None
    assert group.key == "type:docs"
