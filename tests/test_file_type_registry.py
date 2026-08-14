"""Registry v1 parsing, classification, and compatibility contracts."""

from __future__ import annotations

from importlib.resources import files
from textwrap import dedent

from metabrowser.file_type_registry import (
    ContentFamily,
    FileTypeRegistryError,
    load_file_type_registry,
    load_file_type_registry_from_text,
)
from metabrowser.fs_paths import derive_ext


def _minimal_registry() -> str:
    return dedent(
        """
        schema_version = 1
        registry_revision = 1
        max_extension_components = 2

        [[group]]
        id = "code"
        label = "Code"
        order = 10

        [[group]]
        id = "other"
        label = "Other"
        order = 20

        [[family]]
        id = "python"
        label = "Python"
        group = "code"
        order = 10

        [[kind]]
        id = "python"
        family = "python"
        content_family = "code"
        extensions = ["py"]
        filenames = []
        shebangs = []
        priority = 100
        """
    ).strip()


def _error_code(text: str) -> str:
    try:
        load_file_type_registry_from_text(text)
    except FileTypeRegistryError as error:
        return error.code
    raise AssertionError("invalid registry was accepted")


def test_packaged_registry_is_cached_ordered_and_self_describing() -> None:
    registry = load_file_type_registry()
    assert registry is load_file_type_registry()
    assert [group.id for group in registry.groups] == [
        "code",
        "docs",
        "data",
        "logs",
        "archives",
        "media",
        "other",
    ]
    assert len(registry.fingerprint) == 64
    assert files("metabrowser").joinpath("data/file-types.toml").is_file()
    projection = registry.projection()
    assert projection["schema"] == "file-type-registry-v1"
    assert projection["fingerprint"] == registry.fingerprint


def test_registry_classification_keeps_display_and_content_axes_independent() -> None:
    registry = load_file_type_registry()
    javascript = registry.classify("bundle.umd.min.js", ".min.js")
    assert (
        javascript.kind_id,
        javascript.family_id,
        javascript.group_id,
        javascript.canonical_extension,
    ) == ("javascript", "javascript", "code", ".js")

    json_lines = registry.classify("events.jsonl", ".jsonl")
    assert (json_lines.family_id, json_lines.group_id, json_lines.content_family) == (
        "log-files",
        "logs",
        ContentFamily.data,
    )
    svg = registry.classify("diagram.svg", ".svg")
    assert (svg.family_id, svg.group_id, svg.content_family) == (
        "images",
        "media",
        ContentFamily.markup,
    )
    readme = registry.classify("README", "")
    assert (readme.kind_id, readme.family_id, readme.group_id) == (
        "documentation-file",
        None,
        "docs",
    )


def test_logical_extension_uses_two_ascii_case_folded_components() -> None:
    assert derive_ext("bundle.js.map") == ".js.map"
    assert derive_ext("bundle.umd.min.js.map") == ".js.map"
    assert derive_ext("types.d.ts.map") == ".ts.map"
    assert derive_ext("Photo.JPEG") == ".jpeg"
    assert derive_ext(".eslintrc.json") == ".json"
    assert derive_ext(".gitignore") == ""


def test_normalized_fingerprint_ignores_toml_layout() -> None:
    compact = load_file_type_registry_from_text(_minimal_registry())
    spaced = load_file_type_registry_from_text(
        _minimal_registry().replace('label = "Code"', 'label   =   "Code"') + "\n"
    )
    assert compact.fingerprint == spaced.fingerprint


def test_registry_rejects_each_structural_validation_class() -> None:
    base = _minimal_registry()
    duplicate_kind = dedent(
        """

        [[kind]]
        id = "python-copy"
        content_family = "code"
        extensions = ["py"]
        filenames = []
        shebangs = []
        priority = 1
        """
    )
    empty_family = dedent(
        """

        [[family]]
        id = "empty"
        label = "Empty"
        group = "code"
        order = 30
        """
    )
    cases = (
        ("not = [valid", "invalid-toml"),
        (base.replace("schema_version = 1", "schema_version = 2"), "unsupported-schema-version"),
        (
            base.replace("max_extension_components = 2", "max_extension_components = 3"),
            "unsupported-extension-components",
        ),
        (base.replace("registry_revision = 1", "registry_revision = 0"), "invalid-field"),
        (base.replace('id = "code"', 'id = "code_name"', 1), "invalid-id"),
        (base.replace('id = "other"', 'id = "fallback"', 1), "missing-fallback"),
        (base.replace("order = 20", "order = 10", 1), "duplicate-order"),
        (base.replace('group = "code"', 'group = "missing"'), "unknown-group"),
        (base.replace('family = "python"', 'family = "missing"'), "unknown-family"),
        (
            base.replace('content_family = "code"', 'content_family = "mystery"'),
            "invalid-content-family",
        ),
        (base.replace('extensions = ["py"]', 'extensions = [".py"]'), "invalid-extension"),
        (base + duplicate_kind, "duplicate-evidence"),
        (base + empty_family, "empty-family"),
        (base.replace('extensions = ["py"]', "extensions = []"), "missing-evidence"),
    )
    assert [_error_code(text) for text, _expected in cases] == [
        expected for _text, expected in cases
    ]
