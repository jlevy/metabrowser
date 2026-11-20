"""The Files tab's Group by model: which groups a tree splits into, in what order, and
what each one holds.

Grouping is a set of filters. Each group is a constraint that combines with the
navigation filter by intersection, so a group's tree is exactly the tree the filter
would show, restricted to that group's members:

- **File type** groups are the registry's display groups, each holding the files the
  registry classifies into it (``category_for_file``), name evidence included. Other
  holds the registry's own miscellaneous group and every file it does not recognize, so
  every file belongs to exactly one type group.
- **Age** groups are disjoint bands cut from the recency filter's windows: Live, then
  Past hour, Past day, Past week, and Past month, each holding only what the windows
  before it do not, and then Older for the rest. A band intersected with the recency
  filter keeps its lower edge and takes the nearer of the two upper edges; a band that
  ends up empty is not offered. A Git revision's files have the time of their last commit
  when Git can say it, and adds one group a folder never has: Undated, the files whose
  time is not known (a shallow boundary, a read cut by its budget, or one still running).

The order is the presentation order (``FILE_TYPE_GROUP_DISPLAY_ORDER``), Documentation
first, which the type filter shares. ``/api/tree?group_by=`` serves the groups that hold
at least one entry after the filter, with their counts, and ``/api/tree?group=`` serves
one group's tree; ``docs/project/architecture/arch-views-models-routes.md`` records both.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from metabrowser.file_type_filters import FILE_TYPE_CATEGORIES, FILE_TYPE_GROUP_DISPLAY_ORDER
from metabrowser.inventory_engine.contract import TreeGroupFilter
from metabrowser.settings import RECENT_WINDOW_SECONDS

GroupBy = Literal["type", "age"]
GROUP_BY_VALUES: tuple[GroupBy, ...] = ("type", "age")

# The recency filter's labels, which the age bands share (static/app.js,
# FILTER_RECENCY_OPTIONS, says the same words for the same windows).
_AGE_LABELS: dict[str, str] = {
    "live": "Live",
    "1h": "Past hour",
    "24h": "Past day",
    "7d": "Past week",
    "30d": "Past month",
}
OLDER_GROUP_ID = "older"
UNDATED_GROUP_ID = "undated"


@dataclass(frozen=True, slots=True)
class TreeGroup:
    """One group of a grouped tree, in the vocabulary ``group=<by>:<id>`` names."""

    by: GroupBy
    id: str
    label: str
    icon: str | None = None
    """A type group's representative icon (``FileTypeCategory.icon``), which its heading
    draws beside its name; an age group has none."""

    @property
    def key(self) -> str:
        return f"{self.by}:{self.id}"


@dataclass(frozen=True, slots=True)
class AgeBand:
    """An age group as mtime bounds: newer than ``within_seconds`` ago, when set, and
    not newer than ``older_than_seconds`` ago, when set."""

    within_seconds: float | None
    older_than_seconds: float | None

    @property
    def empty(self) -> bool:
        """Whether no mtime can be both newer than one bound and older than the other."""

        return (
            self.within_seconds is not None
            and self.older_than_seconds is not None
            and self.older_than_seconds >= self.within_seconds
        )


def _type_groups() -> tuple[TreeGroup, ...]:
    categories = {category.id: category for category in FILE_TYPE_CATEGORIES}
    return tuple(
        TreeGroup(
            by="type",
            id=group_id,
            label=categories[group_id].label,
            icon=categories[group_id].icon,
        )
        for group_id in FILE_TYPE_GROUP_DISPLAY_ORDER
    )


def _windows() -> tuple[tuple[str, float], ...]:
    """The bounded recency windows, shortest first."""

    bounded = [(key, float(seconds)) for key, seconds in RECENT_WINDOW_SECONDS.items() if seconds]
    return tuple(sorted(bounded, key=lambda item: item[1]))


def _age_groups() -> tuple[TreeGroup, ...]:
    return (
        *(TreeGroup(by="age", id=key, label=_AGE_LABELS[key]) for key, _seconds in _windows()),
        TreeGroup(by="age", id=OLDER_GROUP_ID, label="Older"),
    )


UNDATED_GROUP = TreeGroup(by="age", id=UNDATED_GROUP_ID, label="Undated")
_GROUPS: dict[GroupBy, tuple[TreeGroup, ...]] = {"type": _type_groups(), "age": _age_groups()}


def groups_for(by: GroupBy, *, undated: bool = False) -> tuple[TreeGroup, ...]:
    """Every group *by* can split a tree into, in display order. With *undated*, an age
    split ends in Undated, which a source whose files have no times of its own (a Git
    revision) needs and a folder never does."""

    if undated and by == "age":
        return (*_GROUPS[by], UNDATED_GROUP)
    return _GROUPS[by]


def parse_group_by(raw: str) -> GroupBy | None:
    """Read a ``group_by`` value; anything else means no grouping."""

    for value in GROUP_BY_VALUES:
        if raw == value:
            return value
    return None


def parse_group(raw: str) -> TreeGroup | None:
    """Read a ``group`` value, ``<by>:<id>``; anything else means no group."""

    by_raw, _, group_id = raw.partition(":")
    by = parse_group_by(by_raw)
    if by is None:
        return None
    if by == "age" and group_id == UNDATED_GROUP_ID:
        return UNDATED_GROUP
    return next((group for group in _GROUPS[by] if group.id == group_id), None)


def age_band(group: TreeGroup, recency_seconds: int) -> AgeBand:
    """The mtime bounds of an age *group* under a recency filter of *recency_seconds*
    (zero for none). They can leave nothing (`AgeBand.empty`): Past week under a Past
    hour filter.

    A band runs from the window before it, exclusive, to its own window, inclusive:
    Past hour holds what is newer than an hour and not newer than the Live window.
    """

    if group.by != "age" or group.id == UNDATED_GROUP_ID:
        raise ValueError(f"{group.key} is not an age band")
    windows = _windows()
    keys = [key for key, _seconds in windows]
    if group.id == OLDER_GROUP_ID:
        within: float | None = None
        older_than: float | None = windows[-1][1]
    else:
        at = keys.index(group.id)
        within = windows[at][1]
        older_than = windows[at - 1][1] if at > 0 else None
    if recency_seconds:
        within = float(recency_seconds) if within is None else min(within, recency_seconds)
    return AgeBand(within_seconds=within, older_than_seconds=older_than)


def inventory_group_filter(group: TreeGroup) -> TreeGroupFilter:
    """*group* as the inventory provider selects it in a grouped tree (`GroupedTreeQuery`):
    a type group by its id, and an age group as its band, which a recency window then cuts
    as the provider applies both."""

    if group.by == "type":
        return TreeGroupFilter(key=group.id, type_group=group.id)
    band = age_band(group, 0)
    return TreeGroupFilter(
        key=group.id,
        band_within_seconds=band.within_seconds,
        older_than_seconds=band.older_than_seconds,
    )


def group_row(group: TreeGroup, payload: Mapping[str, Any]) -> dict[str, Any]:
    """One group of a grouped answer: its name, its icon, what it holds, and its tree.

    A type group's icon is its category's representative icon, by name in the shared icon
    registry (static/icons.js); an age group's is None. The counts come from the group's
    filtered totals. A source that cannot count a group
    (a Git revision whose blob index is truncated) gives them as None, and a source that
    counts files but not bytes gives `size` as None.
    """

    filtered = payload.get("filtered") or {}
    return {
        "id": group.id,
        "label": group.label,
        "icon": group.icon,
        "files": filtered.get("files", 0),
        "size": filtered.get("size", 0),
        "entries": filtered.get("entries", 0),
        "tree": payload.get("tree", []),
    }


def groups_payload(
    group_by: str, groups: list[dict[str, Any]], envelope: Mapping[str, Any] | None
) -> dict[str, Any]:
    """`/api/tree?group_by=`: the groups that hold anything after the filter, in display
    order, each with its counts and its tree, under the envelope one group's tree carries.

    A group the filter leaves empty is not shown; one whose entries were not counted is
    shown when its tree holds anything.
    """

    source = envelope or {}
    return {
        "root": source.get("root"),
        "group_by": group_by,
        "groups": [
            group
            for group in groups
            if (group["entries"] > 0 if group["entries"] is not None else bool(group["tree"]))
        ],
        "tally_cache_status": source.get("tally_cache_status"),
        "tally_cache_max_files": source.get("tally_cache_max_files"),
    }


__all__ = [
    "GROUP_BY_VALUES",
    "OLDER_GROUP_ID",
    "UNDATED_GROUP",
    "UNDATED_GROUP_ID",
    "AgeBand",
    "GroupBy",
    "TreeGroup",
    "age_band",
    "group_row",
    "groups_for",
    "groups_payload",
    "inventory_group_filter",
    "parse_group",
    "parse_group_by",
]
