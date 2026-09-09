"""Navigation-filter input normalization before provider query construction."""

from __future__ import annotations

from metabrowser.tree_filter import TreeFilter, parse_recency, parse_size_floor, parse_types


def test_tree_filter_active_reports_only_constraining_selections() -> None:
    assert not TreeFilter().active
    assert TreeFilter(types=(".md",)).active
    assert TreeFilter(recency_seconds=60).active
    assert TreeFilter(min_size=1).active
    assert TreeFilter(include_ignored=False).active


def test_filter_query_values_normalize_or_degrade_to_unbounded() -> None:
    assert parse_types([" .MD, README ", ".md", "."]) == (".md", "readme")
    assert parse_size_floor("1024") == 1024
    assert parse_size_floor("nonsense") == 0
    assert parse_size_floor("-1") == 0
    assert parse_recency("1h") > 0
    assert parse_recency("unknown") == 0
