"""Behavioral contracts for the shared semantic file type taxonomy."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from metabrowser import server
from metabrowser.file_type_filters import (
    FILE_TYPE_FAMILIES,
    FILTER_TYPE_PRESETS,
    FileTypeCategory,
    FileTypeFamily,
    canonical_extension,
    category_for_file,
    distribution_key_for_extension,
    family_for_extension,
    validate_file_type_taxonomy,
)
from metabrowser.settings import client_settings_dict


def test_required_families_use_longest_declared_suffixes() -> None:
    javascript = family_for_extension(".min.js")
    assert javascript is not None
    assert javascript.family.id == "javascript"
    assert javascript.canonical_extension == ".js"
    assert canonical_extension("d.ts") == ".ts"
    for extension, family_id in ((".yaml", "yaml"), (".yml", "yaml"), (".py", "python")):
        match = family_for_extension(extension)
        assert match is not None
        assert match.family.id == family_id
    assert category_for_file("bundle.min.js", ".min.js") == "code"
    assert distribution_key_for_extension(".min.js") == "family:javascript"


def test_unknown_and_ambiguous_extensions_remain_raw() -> None:
    assert family_for_extension(".m") is None
    assert category_for_file("module.m", ".m") == "code"
    assert canonical_extension(".m") == ".m"
    assert distribution_key_for_extension(".m") == ".m"
    assert family_for_extension(".unknown") is None
    assert category_for_file("asset.unknown", ".unknown") == "other"
    assert category_for_file("README", "") == "docs"
    assert distribution_key_for_extension("") == ""
    assert distribution_key_for_extension("(none)") == ""


def test_catalog_generates_presets_for_every_populated_group() -> None:
    presets = {preset["id"]: preset for preset in FILTER_TYPE_PRESETS}
    assert tuple(presets) == ("code", "docs", "data", "archives", "media")
    assert {".js", ".mjs", ".cjs", ".jsx", "makefile"} <= set(presets["code"]["values"])
    assert {".yaml", ".yml", ".db"} <= set(presets["data"]["values"])
    # A preset with no selectable values would render as a filter that does nothing.
    assert all(preset["values"] for preset in FILTER_TYPE_PRESETS)
    log_files = next(family for family in FILE_TYPE_FAMILIES if family.id == "log-files")
    assert log_files.category == "other"
    assert {".log", ".jsonl", ".ndjson"} <= set(log_files.extensions)


def test_projected_families_track_the_registry() -> None:
    from metabrowser.file_type_registry import load_file_type_registry

    assert [family.id for family in FILE_TYPE_FAMILIES] == [
        family.id for family in load_file_type_registry().families
    ]


def test_catalog_validation_rejects_duplicate_members() -> None:
    categories = (FileTypeCategory("code", "Code", ()),)
    families = (
        FileTypeFamily("first", "First", "code", (".x",)),
        FileTypeFamily("second", "Second", "code", (".x",)),
    )
    try:
        validate_file_type_taxonomy(categories, families)
    except ValueError as error:
        assert "duplicate file type family extension" in str(error)
    else:
        raise AssertionError("duplicate family members must be rejected")

    overlapping_categories = (
        FileTypeCategory("code", "Code", ()),
        FileTypeCategory("data", "Data", (".x",)),
    )
    try:
        validate_file_type_taxonomy(
            overlapping_categories,
            (FileTypeFamily("first", "First", "code", (".x",)),),
        )
    except ValueError as error:
        assert "both a family member and category-only value" in str(error)
    else:
        raise AssertionError("family and category-only members must not overlap")


def test_client_settings_publish_one_authoritative_registry() -> None:
    settings = client_settings_dict()
    assert "FILE_TYPE_TAXONOMY" not in settings
    registry = settings["FILE_TYPE_REGISTRY"]
    assert isinstance(registry, dict)
    assert registry["schema"] == "file-type-registry-v1"


def test_index_loads_the_taxonomy_before_the_plugin_sdk() -> None:
    response = asyncio.run(server.index(cast(Any, None)))
    html = bytes(response.body).decode()
    assert "/static/file_type_taxonomy.js?v=" in html
    assert html.index("/static/file_type_taxonomy.js") < html.index("/static/plugin_sdk.js")
