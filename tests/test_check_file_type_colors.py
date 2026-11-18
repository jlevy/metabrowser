"""The palette check's allowance for a family that leaves GitHub's color.

A deviation may nudge a hue out of a collision and keep the color a reader
knows; leaving that color for another one is a separate decision, and the check
names the families that made it. These pin both directions: a family that
leaves without being named fails, and a named family that no longer leaves
fails too, so the list cannot go stale.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from devtools import check_file_type_colors as check
from metabrowser.file_type_registry import FileTypeFamily, load_file_type_registry


def _family(family_id: str) -> FileTypeFamily:
    family = load_file_type_registry().family(family_id)
    assert family is not None
    return family


def test_the_shipped_families_keep_the_upstream_rules() -> None:
    registry = load_file_type_registry()
    assert [
        problem for family in registry.families for problem in check._upstream_problems(family)
    ] == []
    known = {family.id for family in registry.families}
    assert check.LEAVES_GITHUBS_COLOR.issubset(known)


def test_typescript_leaves_githubs_color_only_because_it_is_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    typescript = _family("typescript")
    assert check._upstream_problems(typescript) == []

    monkeypatch.setattr(check, "LEAVES_GITHUBS_COLOR", frozenset[str]())
    [problem] = check._upstream_problems(typescript)
    assert "161.30 degrees" in problem.detail
    assert "LEAVES_GITHUBS_COLOR names" in problem.detail


def test_a_nudged_hue_keeps_githubs_color_and_may_not_be_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    swift = _family("swift")
    assert check._upstream_problems(swift) == []

    monkeypatch.setattr(check, "LEAVES_GITHUBS_COLOR", frozenset({"typescript", "swift"}))
    [problem] = check._upstream_problems(swift)
    assert "drop it from LEAVES_GITHUBS_COLOR" in problem.detail


def test_a_named_family_that_takes_githubs_hue_again_must_be_unnamed() -> None:
    """Reverting TypeScript to GitHub's blue, deviation and all, leaves the
    allowance pointing at nothing, and the check says so."""

    typescript = _family("typescript")
    reverted = replace(
        typescript, hue=253.30, deviation=None, lightness_rank=None, chroma_ratio=None
    )
    [problem] = check._upstream_problems(reverted)
    assert "declares no deviation" in problem.detail


def test_a_named_family_without_upstream_provenance_is_refused() -> None:
    """A named family has to name the color it leaves. Without ``linguist`` and
    ``linguist_color`` there is no hue to measure the departure from, and the
    allowance would hold whatever hue the family declared."""

    typescript = _family("typescript")
    stripped = replace(typescript, linguist=None, linguist_color=None)
    [problem] = check._upstream_problems(stripped)
    assert "names no upstream color" in problem.detail
