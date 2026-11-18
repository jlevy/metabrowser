"""The Group by model: which groups a tree splits into, their order, and the age bands.

The route that serves them is pinned end to end by
``tests/golden/cli-api-tree-groups.tryscript.md``; this pins the model's edges, which a
golden on a small fixture cannot reach: every band's bounds, and how a recency filter
cuts them.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from metabrowser.inventory_engine.contract import MAX_TREE_GROUPS, TreeGroupFilter
from metabrowser.settings import RECENT_WINDOW_SECONDS
from metabrowser.tree_groups import (
    GROUP_BY_VALUES,
    OLDER_GROUP_ID,
    AgeBand,
    age_band,
    groups_for,
    inventory_group_filter,
    parse_group,
    parse_group_by,
)

HOUR = 60 * 60
DAY = 24 * HOUR
LIVE = float(RECENT_WINDOW_SECONDS["live"] or 0)
STATIC = Path(__file__).parents[1] / "src/metabrowser/static"


def _recency_options() -> str:
    """static/app.js's FILTER_RECENCY_OPTIONS, Modified within's rows."""

    app = (STATIC / "app.js").read_text("utf-8")
    block = app[app.index("var FILTER_RECENCY_OPTIONS = [") :]
    return block[: block.index("];")]


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


def test_age_groups_say_the_recency_filter_s_words() -> None:
    """The age bands and Modified within name the same windows the same way; the shell
    states its labels in static/app.js (FILTER_RECENCY_OPTIONS), and this holds the two
    vocabularies to one."""

    pairs = re.findall(r'value: "([^"]+)",\s*label: "([^"]+)"', _recency_options())
    assert pairs, "FILTER_RECENCY_OPTIONS was not found"
    bands = [(group.id, group.label) for group in groups_for("age") if group.id != "older"]
    assert pairs == bands


def test_each_age_section_s_name_takes_its_band_s_age_ink() -> None:
    """By age, a section's name takes its band's age ink (static/styles.css, beside
    `.tree-section-label`; docs/design-system.md, "Grouping the Files Tree"). The section
    carries the route's group id, so the ink is paint; this holds the stylesheet's
    mapping, which names one ink per band and nothing else, to the two it must agree with.
    Modified within's row for each window wears the same tier (FILTER_RECENCY_OPTIONS in
    static/app.js), and each elapsed band lies inside the one tier of AGE_TIERS
    (static/formatters.js) whose ink it takes, so every file age in a section reads in its
    heading's ink. Live is the activity state, as Live's row is, not an elapsed tier."""

    css = (STATIC / "styles.css").read_text("utf-8")
    inks = dict(
        re.findall(
            r'\.tree-section\[data-tree-group="age:([^"]+)"\] \.tree-section-label \{\s*'
            r"color: var\(--file-age-([a-z]+)\);\s*\}",
            css,
        )
    )
    assert list(inks) == [group.id for group in groups_for("age")]

    menu = dict(
        re.findall(
            r'value: "([^"]+)"(?:(?!value: ).)*?ageClass: "age-([a-z]+)"',
            _recency_options(),
            re.DOTALL,
        )
    )
    assert menu == {key: tier for key, tier in inks.items() if key != OLDER_GROUP_ID}
    assert inks["live"] == "live"

    formatters = (STATIC / "formatters.js").read_text("utf-8")
    table = formatters[formatters.index("const AGE_TIERS") :]
    table = table[: table.index("]);")]
    # Each tier from the elapsed seconds it starts at, shortest first; under the shortest,
    # an age is "sec".
    tiers = sorted(
        (math.prod(int(factor) for factor in span.split("*")) / 1000, tier)
        for span, tier in re.findall(r'\["[a-z]+", ([\d *]+), "age-([a-z]+)"\]', table)
    )
    assert len(tiers) >= 5, f"AGE_TIERS was not found: {tiers}"

    def tier_at(seconds: float) -> str:
        return next((tier for start, tier in reversed(tiers) if seconds >= start), "sec")

    for group in groups_for("age"):
        if group.id == "live":
            continue
        band = age_band(group, 0)
        # The band holds the ages from its older edge, inclusive, to its newer, exclusive.
        low = band.older_than_seconds or 0.0
        high = band.within_seconds
        reached = {tier_at(low)} | {
            tier for start, tier in tiers if low < start and (high is None or start < high)
        }
        assert reached == {inks[group.id]}, f"{group.label} spans {reached}"


def test_each_group_reaches_the_provider_as_its_own_fields() -> None:
    """A grouped read names each group by the fields its filtered tree would set: a type
    group's id, and an age group's band before any recency window cuts it."""

    assert [inventory_group_filter(group) for group in groups_for("type")][:2] == [
        TreeGroupFilter(key="docs", type_group="docs"),
        TreeGroupFilter(key="code", type_group="code"),
    ]
    assert [inventory_group_filter(group) for group in groups_for("age")] == [
        TreeGroupFilter(key="live", band_within_seconds=90),
        TreeGroupFilter(key="1h", band_within_seconds=HOUR, older_than_seconds=90),
        TreeGroupFilter(key="24h", band_within_seconds=DAY, older_than_seconds=HOUR),
        TreeGroupFilter(key="7d", band_within_seconds=7 * DAY, older_than_seconds=DAY),
        TreeGroupFilter(key="30d", band_within_seconds=30 * DAY, older_than_seconds=7 * DAY),
        TreeGroupFilter(key="older", older_than_seconds=30 * DAY),
    ]


def test_every_grouping_fits_one_grouped_read() -> None:
    """`MAX_TREE_GROUPS` is set from what Group by sends, with headroom, and its cost
    measured there (inventory_engine/contract.py): every grouping fits it."""

    assert all(len(groups_for(by)) <= MAX_TREE_GROUPS for by in GROUP_BY_VALUES)
