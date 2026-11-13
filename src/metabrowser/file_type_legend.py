"""The compact File Overview legend: a folder's largest file-type families.

File Overview shows this legend under the population bars, the way GitHub's
Languages box sits under its bar, and keeps the full breakdown table behind
Details. Which families it names is a data decision, so it is made here, on the
route, and reached through ``metab --api /api/rollup``; the browser only picks
the variant for its controls and formats it.

The rule:

- The candidates are the breakdown's file-type families, from every group.
  No extension and Other types are not candidates: they are the files no family
  claims, so they have no name to put in a legend and no color of their own.
- They rank by the measure, in the population, descending, with the other
  measure and then the family ID as tie-breaks.
- A family is named only above ``LEGEND_MINIMUM_SHARE_PERCENT`` of the
  population, the floor at which the browser's breakdown table folds a row into
  "N more", and at most ``LEGEND_TYPE_LIMIT`` are. So every named family is also
  a row that table shows unfolded.
- Whatever the named families leave of the population is ``other``, so the
  named values and ``other`` add up to ``total``.

Every measure and population is answered at once, because the browser switches
between Files and Bytes and between the whole folder and its unignored files
without asking again. That is four lists of at most five entries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from metabrowser.wire_models import (
        FileTypeBreakdown,
        FileTypeLegend,
        FileTypeLegendEntry,
        FileTypeLegendView,
        FileTypePopulationMetrics,
    )

LEGEND_SCHEMA: Literal["file-type-legend-v1"] = "file-type-legend-v1"

# A reading bound, not a cost bound: the legend is at most this many short items
# plus Other whatever the folder holds, so there is no cost to measure. Five is
# what GitHub's Languages box shows, and what the Overview was asked for.
LEGEND_TYPE_LIMIT = 5

# The share, in percent, a family must exceed to be named. It is the floor below
# which the browser's breakdown table folds a row into "N more"
# (MINIMUM_VISIBLE_SHARE in builtin_plugins/folder/file-type-summary-model.js),
# and tests/test_file_type_legend.py holds the two equal, so the legend never
# names a family that table folds away.
LEGEND_MINIMUM_SHARE_PERCENT = 1

type _Measure = Literal["files", "bytes"]
type _Population = Literal["all", "unignored"]


def _view(
    families: list[tuple[str, FileTypePopulationMetrics]],
    root: FileTypePopulationMetrics,
    measure: _Measure,
    population: _Population,
) -> FileTypeLegendView:
    other_measure: _Measure = "bytes" if measure == "files" else "files"
    total = root[population][measure]
    ranked = sorted(
        families,
        key=lambda family: (
            -family[1][population][measure],
            -family[1][population][other_measure],
            family[0],
        ),
    )
    # In integers, so a family at exactly the floor is never named by rounding:
    # value / total > minimum / 100.
    eligible: list[FileTypeLegendEntry] = [
        {"family": family_id, "value": metrics[population][measure]}
        for family_id, metrics in ranked
        if metrics[population][measure] * 100 > LEGEND_MINIMUM_SHARE_PERCENT * total
    ]
    named = eligible[:LEGEND_TYPE_LIMIT]
    return {
        "total": total,
        "named": named,
        "other": total - sum(entry["value"] for entry in named),
    }


def build_file_type_legend(breakdown: FileTypeBreakdown | None) -> FileTypeLegend | None:
    """The legend for one breakdown, or None when there is no breakdown yet."""

    if breakdown is None:
        return None
    families = [
        (family["id"], family["metrics"])
        for group in breakdown["groups"]
        for family in group["families"]
    ]
    root = breakdown["metrics"]
    return {
        "schema": LEGEND_SCHEMA,
        "limit": LEGEND_TYPE_LIMIT,
        "minimum_share_percent": LEGEND_MINIMUM_SHARE_PERCENT,
        "files": {
            "all": _view(families, root, "files", "all"),
            "unignored": _view(families, root, "files", "unignored"),
        },
        "bytes": {
            "all": _view(families, root, "bytes", "all"),
            "unignored": _view(families, root, "bytes", "unignored"),
        },
    }


__all__ = [
    "LEGEND_MINIMUM_SHARE_PERCENT",
    "LEGEND_SCHEMA",
    "LEGEND_TYPE_LIMIT",
    "build_file_type_legend",
]
