"""Each file-type category's representative icon, held to the registry, the icon
registry, the grouped tree's answer, and the design system's table
(docs/design-system.md, "File-Type Category Icons").

A category's icon is the one its representative format draws, which is the registry
group's shape: `file_type_filters.py` refuses a representative that is not one of its
group's families or that declares an icon of its own. The design system restates the
table so a reader sees each choice and its reason without opening the code, and this
test is what lets it: a change to `_REPRESENTATIVE_FAMILIES` fails here until the table
says the same.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from metabrowser import file_type_filters
from metabrowser.file_type_filters import FILE_TYPE_CATEGORIES, FILE_TYPE_GROUP_DISPLAY_ORDER
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.tree_groups import group_row, groups_for

REPO_ROOT = Path(__file__).resolve().parents[1]
ICONS_JS = REPO_ROOT / "src/metabrowser/static/icons.js"
DESIGN_SYSTEM = REPO_ROOT / "docs/design-system.md"
SECTION = "### File-Type Category Icons"

_REGISTRY = load_file_type_registry()
_CATEGORIES = {category.id: category for category in FILE_TYPE_CATEGORIES}


def test_each_category_takes_its_representative_formats_icon() -> None:
    assert {
        category.id: (category.representative_family, category.icon)
        for category in FILE_TYPE_CATEGORIES
    } == {
        "code": ("python", "alignLeft"),
        "docs": ("markdown", "doc"),
        "data": ("json", "list"),
        "archives": ("archives", "copy"),
        "media": ("images", "monitor"),
        "other": (None, "file"),
    }
    for category in FILE_TYPE_CATEGORIES:
        group = _REGISTRY.group(category.id)
        assert group is not None, category
        # The category's icon is its group's shape ...
        assert category.icon == group.icon, category
        if category.representative_family is None:
            continue
        # ... which its representative is one of the families drawn in.
        family = _REGISTRY.family(category.representative_family)
        assert family is not None and family.group_id == category.id, category
        assert (family.icon or group.icon) == category.icon, (category, family)


@pytest.mark.parametrize(
    ("group_id", "family_id", "refusal"),
    [
        ("nope", None, "unknown group"),
        ("data", "python", "not one of its families"),
        # A tabular format draws the grid, its own shape, not Data's list.
        ("data", "delimited-text", "declares its own icon"),
        ("other", "log-files", "declares its own icon"),
    ],
)
def test_a_representative_that_would_misdraw_its_category_is_refused(
    group_id: str, family_id: str | None, refusal: str
) -> None:
    with pytest.raises(ValueError, match=refusal):
        file_type_filters._category_icon(group_id, family_id)


def test_every_category_icon_is_in_the_shared_icon_registry() -> None:
    # icons.js lists each icon as an entry of its ICONS object, four spaces in.
    names = set(re.findall(r"^ {4}([A-Za-z][A-Za-z0-9]*):", ICONS_JS.read_text("utf-8"), re.M))
    assert {category.icon for category in FILE_TYPE_CATEGORIES} <= names, names


def test_a_type_group_carries_its_category_icon_and_an_age_group_none() -> None:
    type_groups = groups_for("type")
    assert [group.icon for group in type_groups] == [
        _CATEGORIES[group.id].icon for group in type_groups
    ]
    assert all(group.icon is None for group in groups_for("age"))
    # The grouped tree's answer names the icon beside the label.
    docs = group_row(type_groups[0], {})
    assert list(docs)[:3] == ["id", "label", "icon"], docs
    assert docs["icon"] == "doc", docs
    assert group_row(groups_for("age")[0], {})["icon"] is None


def _design_system_table() -> list[list[str]]:
    text = DESIGN_SYSTEM.read_text("utf-8")
    start = text.index(f"\n{SECTION}\n")
    end = text.index("\n### ", start + 1)
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in text[start:end].splitlines()
        if line.startswith("| ")
    ]
    # The header row and its rule, then a row per category.
    assert rows[0] == ["Category", "Representative", "Icon", "Why"], rows[0]
    assert set("".join(rows[1])) <= set("-: "), rows[1]
    return rows[2:]


def test_the_design_system_table_is_the_codes() -> None:
    expected = []
    for group_id in FILE_TYPE_GROUP_DISPLAY_ORDER:
        category = _CATEGORIES[group_id]
        family = (
            _REGISTRY.family(category.representative_family)
            if category.representative_family
            else None
        )
        expected.append(
            [
                category.label,
                family.label if family else "None",
                f"`{category.icon}`",
                file_type_filters._REPRESENTATIVE_FAMILIES[group_id][1],
            ]
        )
    # The document's apostrophes are typographic, the code's straight.
    actual = [[cell.replace("’", "'") for cell in row] for row in _design_system_table()]
    assert actual == expected
