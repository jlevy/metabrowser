"""Filter-facing projection of the shared file-type registry.

Navigation filters and rollups need the registry expressed as flat group and
family tuples. This module derives those views from the one loaded registry so
there is no second catalog to keep in sync.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict

from metabrowser.file_type_registry import (
    FILE_TYPE_FAMILY_KEY_PREFIX,
    FILE_TYPE_NO_EXTENSION_KEY,
    FILE_TYPE_REMAINING_KEY,
    load_file_type_registry,
    normalize_logical_extension,
)

type FileTypeCategoryId = str
type ClassifiedFileTypeCategoryId = str

_VALID_ID = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True, slots=True)
class FileTypeCategory:
    """A broad filter group plus members without a display family."""

    id: FileTypeCategoryId
    label: str
    extra_values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FileTypeFamily:
    """A readable semantic type and its canonical extension suffixes."""

    id: str
    label: str
    category: FileTypeCategoryId
    extensions: tuple[str, ...]


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

FILE_TYPE_CATEGORIES: tuple[FileTypeCategory, ...] = tuple(
    FileTypeCategory(
        id=group.id,
        label=group.label,
        extra_values=tuple(_EXTRA_VALUES_BY_GROUP[group.id]),
    )
    for group in _REGISTRY.groups
)
FILE_TYPE_FAMILIES: tuple[FileTypeFamily, ...] = tuple(
    FileTypeFamily(
        id=family.id,
        label=family.label,
        category=family.group_id,
        extensions=family.extensions,
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


def category_for_file(name: str, extension: str) -> ClassifiedFileTypeCategoryId:
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
        for category in FILE_TYPE_CATEGORIES
        if any(family.category == category.id for family in FILE_TYPE_FAMILIES)
        or category.extra_values
    )


FILTER_TYPE_PRESETS = _build_filter_type_presets()


def serialize_file_type_registry() -> dict[str, object]:
    """Return the projected file-type definitions for the public browser SDK."""

    return _REGISTRY.projection()


__all__ = [
    "FILE_TYPE_CATEGORIES",
    "FILE_TYPE_FAMILIES",
    "FILE_TYPE_FAMILY_KEY_PREFIX",
    "FILE_TYPE_NO_EXTENSION_KEY",
    "FILE_TYPE_REMAINING_KEY",
    "FILTER_TYPE_PRESETS",
    "ClassifiedFileTypeCategoryId",
    "FileTypeCategory",
    "FileTypeCategoryId",
    "FileTypeFamily",
    "FileTypeFamilyMatch",
    "FilterTypePreset",
    "canonical_extension",
    "category_for_file",
    "distribution_key_for_extension",
    "family_for_extension",
    "serialize_file_type_registry",
    "validate_file_type_taxonomy",
]
