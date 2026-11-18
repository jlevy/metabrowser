"""Filter-facing projection of the shared file-type registry.

Navigation filters and rollups need the registry expressed as flat group and
family tuples. This module derives those views from the one loaded registry so
there is no second catalog to keep in sync.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict

from metabrowser.color_oklch import DARK_THEME, LIGHT_THEME
from metabrowser.file_type_registry import (
    FILE_TYPE_FAMILY_KEY_PREFIX,
    FILE_TYPE_NO_EXTENSION_KEY,
    FILE_TYPE_REMAINING_KEY,
    load_file_type_registry,
    normalize_logical_extension,
)

_VALID_ID = re.compile(r"^[a-z][a-z0-9-]*$")
_FALLBACK_GROUP_ID = "other"


@dataclass(frozen=True, slots=True)
class FileTypeCategory:
    """A broad filter group plus members without a display family."""

    id: str
    label: str
    extra_values: tuple[str, ...]
    representative_family: str | None
    """The format that stands for the category, or ``None`` where no one format does
    (``_REPRESENTATIVE_FAMILIES``)."""
    icon: str
    """The category's icon, which leads its heading wherever the category is named: the
    registry group's shape, which is its representative format's icon. A heading draws it
    in the heading's gray, never in the format's colour, because it names the category,
    not a format (docs/design-system.md, "File-Type Category Icons")."""


@dataclass(frozen=True, slots=True)
class FileTypeFamily:
    """A readable semantic type, its canonical extension suffixes, and its hue."""

    id: str
    label: str
    category: str
    extensions: tuple[str, ...]
    hue: float


@dataclass(frozen=True, slots=True)
class FileTypeFamilyMatch:
    """The family and canonical member selected for one logical extension."""

    family: FileTypeFamily
    canonical_extension: str


class FilterTypePreset(TypedDict):
    id: str
    label: str
    values: tuple[str, ...]


_REGISTRY = load_file_type_registry()
_EXTRA_VALUES_BY_GROUP: dict[str, list[str]] = {group.id: [] for group in _REGISTRY.groups}
for _kind in _REGISTRY.kinds:
    if _kind.family_id is not None:
        continue
    _EXTRA_VALUES_BY_GROUP[_kind.group_id].extend(f".{value}" for value in _kind.extensions)
    _EXTRA_VALUES_BY_GROUP[_kind.group_id].extend(_kind.filenames)

# Each category's representative: the format that stands for it wherever the category is
# named, typically its most important one, and why. The category's icon is that format's
# icon, drawn in the heading's gray (docs/design-system.md, "File-Type Category Icons").
# The registry already holds that icon as the group's shape, which every family in the
# group takes unless it declares its own (the icon is the major type, the colour the
# subtype), so the choice is checked against it below rather than declared twice: a
# representative must be one of its group's families and take the group's shape. Which
# format represents a category is presentation, as the display order below is, so it
# lives here and not in the registry, whose groups and fingerprint are the File Rollup
# Format's. docs/design-system.md restates this table, and tests/test_category_icons.py
# holds the copy to it.
_REPRESENTATIVE_FAMILIES: dict[str, tuple[str | None, str]] = {
    "code": (
        "python",
        "Python leads the registry's Code families, and every Code family takes its shape.",
    ),
    "docs": (
        "markdown",
        "Markdown is what a repository's documentation is written in: READMEs and guides.",
    ),
    "data": (
        "json",
        "JSON is a repository's commonest data: configuration, manifests, and payloads; "
        "the tabular formats keep their own grid.",
    ),
    "archives": ("archives", "Archives has one family, which holds every archive format."),
    "media": (
        "images",
        "Images are the media a repository holds most: screenshots, diagrams, and icons.",
    ),
    "other": (
        None,
        "Other is mostly files the registry does not recognize, so the plain file shape "
        "stands for it; its one family, Log files, would misname the rest.",
    ),
}


def _category_icon(group_id: str, family_id: str | None) -> str:
    """The icon a category takes: its group's shape, once its representative is checked
    to be one of the group's families drawn in that shape."""

    group = _REGISTRY.group(group_id)
    if group is None:
        raise ValueError(f"representative named for an unknown group: {group_id!r}")
    if family_id is None:
        return group.icon
    family = _REGISTRY.family(family_id)
    if family is None or family.group_id != group_id:
        raise ValueError(
            f"the representative of {group_id!r} is not one of its families: {family_id!r}"
        )
    if (family.icon or group.icon) != group.icon:
        raise ValueError(
            f"the representative of {group_id!r}, {family_id!r}, declares its own icon "
            f"{family.icon!r}: a category's icon is its representative's, so the group's "
            f"shape must be that icon"
        )
    return group.icon


if set(_REPRESENTATIVE_FAMILIES) != {group.id for group in _REGISTRY.groups}:
    raise ValueError("every file type category names exactly one representative")

FILE_TYPE_CATEGORIES: tuple[FileTypeCategory, ...] = tuple(
    FileTypeCategory(
        id=group.id,
        label=group.label,
        extra_values=tuple(_EXTRA_VALUES_BY_GROUP[group.id]),
        representative_family=_REPRESENTATIVE_FAMILIES[group.id][0],
        icon=_category_icon(group.id, _REPRESENTATIVE_FAMILIES[group.id][0]),
    )
    for group in _REGISTRY.groups
)
FILE_TYPE_FAMILIES: tuple[FileTypeFamily, ...] = tuple(
    FileTypeFamily(
        id=family.id,
        label=family.label,
        category=family.group_id,
        extensions=family.extensions,
        hue=family.hue,
    )
    for family in _REGISTRY.families
)
_FAMILIES_BY_ID = {family.id: family for family in FILE_TYPE_FAMILIES}


def _normalize_extension(extension: str) -> str:
    return normalize_logical_extension(extension)


def validate_file_type_taxonomy(
    categories: tuple[FileTypeCategory, ...],
    families: tuple[FileTypeFamily, ...],
) -> None:
    """Reject a projection that could classify the same suffix ambiguously."""

    category_ids: set[str] = set()
    extra_values: dict[str, str] = {}
    for category in categories:
        if category.id in category_ids:
            raise ValueError(f"duplicate file type category id: {category.id!r}")
        if not _VALID_ID.fullmatch(category.id):
            raise ValueError(f"invalid file type category id: {category.id!r}")
        if not category.label.strip():
            raise ValueError(f"empty label for file type category: {category.id!r}")
        category_ids.add(category.id)
        for value in category.extra_values:
            normalized = value.strip().lower()
            if not normalized or normalized == "." or normalized != value:
                raise ValueError(f"file type category values must be normalized: {value!r}")
            prior_category = extra_values.get(normalized)
            if prior_category is not None:
                raise ValueError(
                    f"duplicate file type category value {normalized!r}: "
                    f"{prior_category!r} and {category.id!r}"
                )
            extra_values[normalized] = category.id

    family_ids: set[str] = set()
    family_extensions: dict[str, str] = {}
    for family in families:
        if family.id in family_ids:
            raise ValueError(f"duplicate file type family id: {family.id!r}")
        if not _VALID_ID.fullmatch(family.id):
            raise ValueError(f"invalid file type family id: {family.id!r}")
        if not family.label.strip():
            raise ValueError(f"empty label for file type family: {family.id!r}")
        if family.category not in category_ids:
            raise ValueError(
                f"unknown category {family.category!r} for file type family {family.id!r}"
            )
        if not family.extensions:
            raise ValueError(f"file type family has no extensions: {family.id!r}")
        family_ids.add(family.id)
        for extension in family.extensions:
            normalized = _normalize_extension(extension)
            if normalized != extension or not normalized.startswith(".") or normalized == ".":
                raise ValueError(f"file type family extensions must be normalized: {extension!r}")
            prior_family = family_extensions.get(normalized)
            if prior_family is not None:
                raise ValueError(
                    f"duplicate file type family extension {normalized!r}: "
                    f"{prior_family!r} and {family.id!r}"
                )
            extra_category = extra_values.get(normalized)
            if extra_category is not None:
                raise ValueError(
                    f"file type value {normalized!r} is both a family member and "
                    f"category-only value in {extra_category!r}"
                )
            family_extensions[normalized] = family.id


validate_file_type_taxonomy(FILE_TYPE_CATEGORIES, FILE_TYPE_FAMILIES)

# The order the app lists the display groups in for a reader: the type filter's Groups and
# its sections, Group by's File type groups, and File Overview. Documentation leads, ahead of
# Code; the rest keep the registry's order. This is
# presentation, kept apart from the registry on purpose: a group's `order` is part of the File
# Rollup Format's recommended definitions, which its fingerprint covers and its rollups and
# conformance fixtures follow ("The recommended order is Code, Documentation, ...",
# docs/project/architecture/file-rollup-format/file-rollup-format.md), so reordering there
# would be a new registry revision for every producer and consumer of the format.
_DISPLAY_LEADS = ("docs",)
FILE_TYPE_GROUP_DISPLAY_ORDER: tuple[str, ...] = (
    *_DISPLAY_LEADS,
    *(category.id for category in FILE_TYPE_CATEGORIES if category.id not in _DISPLAY_LEADS),
)
if set(_DISPLAY_LEADS) - {category.id for category in FILE_TYPE_CATEGORIES}:
    raise ValueError(f"display order names an unknown group: {_DISPLAY_LEADS!r}")
_DISPLAY_RANK = {group_id: rank for rank, group_id in enumerate(FILE_TYPE_GROUP_DISPLAY_ORDER)}


def family_for_extension(extension: str) -> FileTypeFamilyMatch | None:
    """Return the longest declared display-family suffix."""

    match = _REGISTRY.match("", _normalize_extension(extension))
    if match is None or match.kind.family_id is None or match.canonical_extension is None:
        return None
    family = _FAMILIES_BY_ID[match.kind.family_id]
    return FileTypeFamilyMatch(family=family, canonical_extension=match.canonical_extension)


def canonical_extension(extension: str) -> str:
    """Collapse a known logical extension to its canonical registry member."""

    normalized = _normalize_extension(extension)
    match = _REGISTRY.match("", normalized)
    return (
        match.canonical_extension
        if match is not None and match.canonical_extension is not None
        else normalized
    )


def category_for_file(name: str, extension: str) -> str:
    """Classify a file into its registry display group."""

    return _REGISTRY.classify(name, extension).group_id


def distribution_key_for_extension(extension: str) -> str:
    """Return the shared family palette key or an honest raw fallback."""

    normalized = _normalize_extension(extension)
    if normalized == FILE_TYPE_NO_EXTENSION_KEY:
        return FILE_TYPE_REMAINING_KEY
    match = family_for_extension(normalized)
    return f"{FILE_TYPE_FAMILY_KEY_PREFIX}{match.family.id}" if match else normalized


def _build_filter_type_presets() -> tuple[FilterTypePreset, ...]:
    """Build closed group presets; the open-ended Other group stays a section only."""

    return tuple(
        {
            "id": category.id,
            "label": category.label,
            "values": tuple(
                extension
                for family in FILE_TYPE_FAMILIES
                if family.category == category.id
                for extension in family.extensions
            )
            + category.extra_values,
        }
        for category in sorted(FILE_TYPE_CATEGORIES, key=lambda item: _DISPLAY_RANK[item.id])
        if category.id != _FALLBACK_GROUP_ID
        and (
            any(family.category == category.id for family in FILE_TYPE_FAMILIES)
            or category.extra_values
        )
    )


FILTER_TYPE_PRESETS = _build_filter_type_presets()


def serialize_file_type_registry() -> dict[str, object]:
    """Return the projected file-type definitions for the public browser SDK."""

    return _REGISTRY.projection()


def serialize_distribution_colors() -> list[dict[str, str]]:
    """Return each family's distribution key with its color on each theme.

    The registry declares a hue and the color that hue came from, and stops
    there, because both are tool-neutral and a theme's band is not. This is
    where the two meet, and it is deliberately here rather than in the browser
    for two reasons. sRGB cannot hold the target chroma at every hue, something
    has to pull it back, and a browser asked to paint an out-of-gamut
    ``oklch()`` clips it — moving hue by as much as nine degrees, which is more
    than the separation the palette is built on. And a family's place in the
    band is its rank among all the others, so it can only be worked out where
    the whole registry is in hand.

    Ordered by the registry, so a consumer with a key the registry does not
    know can index into the list rather than inventing a color.
    """

    colors: list[dict[str, str]] = []
    for family in _REGISTRY.families:
        position = _REGISTRY.tone_position(family.id)
        colors.append(
            {
                "key": family.distribution_key,
                "light": LIGHT_THEME.at(family.hue, position).css(),
                "dark": DARK_THEME.at(family.hue, position).css(),
            }
        )
    return colors


__all__ = [
    "FILE_TYPE_CATEGORIES",
    "FILE_TYPE_FAMILIES",
    "FILE_TYPE_FAMILY_KEY_PREFIX",
    "FILE_TYPE_GROUP_DISPLAY_ORDER",
    "FILE_TYPE_NO_EXTENSION_KEY",
    "FILE_TYPE_REMAINING_KEY",
    "FILTER_TYPE_PRESETS",
    "FileTypeCategory",
    "FileTypeFamily",
    "FileTypeFamilyMatch",
    "FilterTypePreset",
    "canonical_extension",
    "category_for_file",
    "distribution_key_for_extension",
    "family_for_extension",
    "serialize_distribution_colors",
    "serialize_file_type_registry",
    "validate_file_type_taxonomy",
]
