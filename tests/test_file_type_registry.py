"""Recommended file-type parsing, classification, and compatibility contracts."""

from __future__ import annotations

from importlib.resources import files
from textwrap import dedent

from metabrowser.color_oklch import band_positions
from metabrowser.file_type_registry import (
    FILE_TYPE_REGISTRY_SCHEMA_VERSION,
    ContentFamily,
    FileTypeRegistryError,
    load_file_type_registry,
    load_file_type_registry_from_text,
)
from metabrowser.fs_paths import derive_ext


def _minimal_registry() -> str:
    return dedent(
        f"""
        schema_version = {FILE_TYPE_REGISTRY_SCHEMA_VERSION}
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
        linguist = "Python"
        linguist_color = "#3572a5"
        hue = 246.50

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
        "archives",
        "media",
        "other",
    ]
    assert len(registry.fingerprint) == 64
    assert (
        files("metabrowser")
        .joinpath("data/file-rollup-format/recommended-file-types.toml")
        .is_file()
    )
    projection = registry.projection()
    assert projection["schema"] == "file-type-registry-v3"
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
        "other",
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
        group = "code"
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
        hue = 12.5
        """
    )
    cases = (
        ("not = [valid", "invalid-toml"),
        (
            base.replace(
                f"schema_version = {FILE_TYPE_REGISTRY_SCHEMA_VERSION}",
                f"schema_version = {FILE_TYPE_REGISTRY_SCHEMA_VERSION + 1}",
            ),
            "unsupported-schema-version",
        ),
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
        (
            base
            + dedent(
                """

                [[kind]]
                id = "standalone"
                content_family = "code"
                extensions = ["standalone"]
                filenames = []
                shebangs = []
                priority = 1
                """
            ),
            "invalid-field",
        ),
        (base.replace('family = "python"', 'family = "python"\ngroup = "other"'), "group-mismatch"),
        (base + empty_family, "empty-family"),
        (base.replace("hue = 246.50", "hue = 361.0"), "invalid-hue"),
        (base.replace("hue = 246.50", 'hue = "246.50"'), "invalid-field"),
        (base.replace('linguist_color = "#3572a5"\n', ""), "invalid-linguist"),
        (
            base.replace("hue = 246.50", "hue = 246.50\nlightness_rank = -0.5"),
            "undeclared-deviation",
        ),
        (
            base.replace("hue = 246.50", 'hue = 246.50\ndeviation = "   "'),
            "invalid-field",
        ),
        (base.replace('extensions = ["py"]', "extensions = []"), "missing-evidence"),
    )
    assert [_error_code(text) for text, _expected in cases] == [
        expected for _text, expected in cases
    ]


def test_a_declared_deviation_overrides_the_rank_upstream_would_give() -> None:
    """The one way out of the band, and it only opens for a family that says
    why in prose.

    A deviation replaces the lightness rank and nothing else: the chroma the
    upstream colour earned stays, because leaving the band is about where a
    family sits, not about giving up its provenance.
    """

    text = _minimal_registry().replace(
        "hue = 246.50",
        'hue = 300.0\nlightness_rank = -0.5\ndeviation = "Collided with a better-known family."',
    )
    registry = load_file_type_registry_from_text(text)
    family = registry.family("python")
    assert family is not None
    assert family.deviation == "Collided with a better-known family."
    assert family.lightness_rank == -0.5

    derived = band_positions([family.linguist_color])[0]
    position = registry.tone_position("python")
    assert position.lightness_rank == -0.5
    assert position.chroma_ratio == derived.chroma_ratio

    # Provenance survives the deviation, so the hue's origin stays auditable.
    assert family.linguist == "Python"
    assert family.linguist_color == "#3572a5"

    families = registry.projection()["families"]
    assert isinstance(families, tuple)
    projected = next(
        entry for entry in families if isinstance(entry, dict) and entry.get("id") == "python"
    )
    assert projected["deviation"] == "Collided with a better-known family."
    assert projected["lightness_rank"] == -0.5


def test_a_family_that_does_not_deviate_carries_no_reason() -> None:
    registry = load_file_type_registry_from_text(_minimal_registry())
    family = registry.family("python")
    assert family is not None
    assert family.deviation is None
    assert family.lightness_rank is None
    assert 0.0 <= registry.tone_position("python").lightness_rank <= 1.0
