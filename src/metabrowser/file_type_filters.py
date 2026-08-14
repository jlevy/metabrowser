"""Semantic file type taxonomy shared by the server and browser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, TypedDict

type FileTypeCategoryId = Literal["docs", "code", "data"]
type ClassifiedFileTypeCategoryId = Literal["docs", "code", "data", "other"]

FILE_TYPE_NO_EXTENSION_KEY = "(none)"
FILE_TYPE_REMAINING_KEY = ""
FILE_TYPE_FAMILY_KEY_PREFIX = "family:"

_VALID_ID = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True, slots=True)
class FileTypeCategory:
    """A broad filter category plus members that have no semantic family."""

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


# Exact filenames and ambiguous extensions remain category-only. They retain
# useful broad filtering without acquiring a misleading semantic family name.
FILE_TYPE_CATEGORIES: tuple[FileTypeCategory, ...] = (
    FileTypeCategory(
        id="docs",
        label="Docs",
        extra_values=(
            "readme",
            "license",
            "licence",
            "copying",
            "notice",
            "changelog",
            "authors",
            "contributors",
            "contributing",
            "codeowners",
        ),
    ),
    FileTypeCategory(
        id="code",
        label="Code",
        extra_values=(
            ".m",
            ".mm",
            ".ml",
            ".pl",
            ".r",
            "makefile",
            "dockerfile",
            "justfile",
            "rakefile",
            "gemfile",
            "procfile",
        ),
    ),
    FileTypeCategory(
        id="data",
        label="Data",
        extra_values=(".cfg", ".conf", ".properties", ".db"),
    ),
)


# Families are deliberately curated rather than exhaustive. Singleton entries
# are included only where the readable name materially improves the UI.
FILE_TYPE_FAMILIES: tuple[FileTypeFamily, ...] = (
    FileTypeFamily("markdown", "Markdown", "docs", (".md",)),
    FileTypeFamily("plain-text", "Plain text", "docs", (".txt",)),
    FileTypeFamily("restructured-text", "reStructuredText", "docs", (".rst",)),
    FileTypeFamily("asciidoc", "AsciiDoc", "docs", (".adoc",)),
    FileTypeFamily("org", "Org", "docs", (".org",)),
    FileTypeFamily("pdf", "PDF", "docs", (".pdf",)),
    FileTypeFamily("word", "Word", "docs", (".doc", ".docx")),
    FileTypeFamily("rich-text", "Rich Text", "docs", (".rtf",)),
    FileTypeFamily("open-document", "OpenDocument", "docs", (".odt",)),
    FileTypeFamily("epub", "EPUB", "docs", (".epub",)),
    FileTypeFamily("python", "Python", "code", (".py", ".pyi")),
    FileTypeFamily("javascript", "JavaScript", "code", (".js", ".mjs", ".cjs", ".jsx")),
    FileTypeFamily("typescript", "TypeScript", "code", (".ts", ".mts", ".cts", ".tsx")),
    FileTypeFamily("css", "CSS", "code", (".css", ".scss", ".less")),
    FileTypeFamily("html", "HTML", "code", (".html",)),
    FileTypeFamily("rust", "Rust", "code", (".rs",)),
    FileTypeFamily("go", "Go", "code", (".go",)),
    FileTypeFamily("java", "Java", "code", (".java",)),
    FileTypeFamily("kotlin", "Kotlin", "code", (".kt", ".kts")),
    FileTypeFamily("swift", "Swift", "code", (".swift",)),
    FileTypeFamily("c-cpp", "C/C++", "code", (".c", ".h", ".cc", ".cpp", ".hpp")),
    FileTypeFamily("csharp", "C#", "code", (".cs",)),
    FileTypeFamily("ruby", "Ruby", "code", (".rb",)),
    FileTypeFamily("php", "PHP", "code", (".php",)),
    FileTypeFamily("scala", "Scala", "code", (".scala",)),
    FileTypeFamily("clojure", "Clojure", "code", (".clj",)),
    FileTypeFamily("elixir", "Elixir", "code", (".ex", ".exs")),
    FileTypeFamily("erlang", "Erlang", "code", (".erl",)),
    FileTypeFamily("haskell", "Haskell", "code", (".hs",)),
    FileTypeFamily("lua", "Lua", "code", (".lua",)),
    FileTypeFamily("julia", "Julia", "code", (".jl",)),
    FileTypeFamily("dart", "Dart", "code", (".dart",)),
    FileTypeFamily("vue", "Vue", "code", (".vue",)),
    FileTypeFamily("svelte", "Svelte", "code", (".svelte",)),
    FileTypeFamily("shell", "Shell", "code", (".sh", ".bash", ".zsh", ".fish")),
    FileTypeFamily("powershell", "PowerShell", "code", (".ps1",)),
    FileTypeFamily("sql", "SQL", "code", (".sql",)),
    FileTypeFamily("json", "JSON", "data", (".json", ".jsonl", ".ndjson")),
    FileTypeFamily("yaml", "YAML", "data", (".yaml", ".yml")),
    FileTypeFamily("toml", "TOML", "data", (".toml",)),
    FileTypeFamily("ini", "INI", "data", (".ini",)),
    FileTypeFamily("delimited-text", "Delimited text", "data", (".csv", ".tsv", ".psv")),
    FileTypeFamily("xml", "XML", "data", (".xml",)),
    FileTypeFamily("parquet", "Parquet", "data", (".parquet",)),
    FileTypeFamily("arrow", "Arrow", "data", (".arrow", ".feather")),
    FileTypeFamily("avro", "Avro", "data", (".avro",)),
    FileTypeFamily("orc", "ORC", "data", (".orc",)),
    FileTypeFamily("protocol-buffers", "Protocol Buffers", "data", (".proto",)),
    FileTypeFamily("graphql", "GraphQL", "data", (".graphql",)),
    FileTypeFamily("sqlite", "SQLite", "data", (".sqlite",)),
)


def _extension_matches(extension: str, suffix: str) -> bool:
    return extension == suffix or extension.endswith(suffix)


def _normalize_extension(extension: str) -> str:
    normalized = extension.strip().lower()
    if not normalized or normalized == FILE_TYPE_REMAINING_KEY:
        return FILE_TYPE_REMAINING_KEY
    if normalized == FILE_TYPE_NO_EXTENSION_KEY:
        return FILE_TYPE_NO_EXTENSION_KEY
    return normalized if normalized.startswith(".") else f".{normalized}"


def validate_file_type_taxonomy(
    categories: tuple[FileTypeCategory, ...],
    families: tuple[FileTypeFamily, ...],
) -> None:
    """Reject declarations that could classify the same suffix ambiguously."""

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

_FAMILY_SUFFIXES: tuple[tuple[str, FileTypeFamily], ...] = tuple(
    sorted(
        ((extension, family) for family in FILE_TYPE_FAMILIES for extension in family.extensions),
        key=lambda item: (-len(item[0]), item[0], item[1].id),
    )
)
_CATEGORY_SUFFIXES: tuple[tuple[str, FileTypeCategoryId], ...] = tuple(
    sorted(
        (
            (value, category.id)
            for category in FILE_TYPE_CATEGORIES
            for value in category.extra_values
            if value.startswith(".")
        ),
        key=lambda item: (-len(item[0]), item[0], item[1]),
    )
)
_CATEGORY_FILENAMES: dict[str, FileTypeCategoryId] = {
    value: category.id
    for category in FILE_TYPE_CATEGORIES
    for value in category.extra_values
    if not value.startswith(".")
}


def family_for_extension(extension: str) -> FileTypeFamilyMatch | None:
    """Return the longest declared family suffix for a logical extension."""

    normalized = _normalize_extension(extension)
    if not normalized.startswith("."):
        return None
    for suffix, family in _FAMILY_SUFFIXES:
        if _extension_matches(normalized, suffix):
            return FileTypeFamilyMatch(family=family, canonical_extension=suffix)
    return None


def canonical_extension(extension: str) -> str:
    """Collapse a known logical extension to its canonical family member."""

    normalized = _normalize_extension(extension)
    match = family_for_extension(normalized)
    return match.canonical_extension if match is not None else normalized


def category_for_file(name: str, extension: str) -> ClassifiedFileTypeCategoryId:
    """Classify a file by family, then category-only suffixes and filenames."""

    match = family_for_extension(extension)
    if match is not None:
        return match.family.category
    normalized_extension = _normalize_extension(extension)
    if normalized_extension.startswith("."):
        for suffix, category_id in _CATEGORY_SUFFIXES:
            if _extension_matches(normalized_extension, suffix):
                return category_id
    basename = name.replace("\\", "/").rsplit("/", maxsplit=1)[-1].lower()
    return _CATEGORY_FILENAMES.get(basename, "other")


def distribution_key_for_extension(extension: str) -> str:
    """Return the shared family palette key or an honest raw fallback."""

    normalized = _normalize_extension(extension)
    match = family_for_extension(normalized)
    if match is not None:
        return f"{FILE_TYPE_FAMILY_KEY_PREFIX}{match.family.id}"
    return normalized


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
    )


FILTER_TYPE_PRESETS = _build_filter_type_presets()


def serialize_file_type_taxonomy() -> dict[str, object]:
    """Return the immutable declarations as a JSON-safe browser setting."""

    return {
        "categories": tuple(
            {
                "id": category.id,
                "label": category.label,
                "extra_values": category.extra_values,
            }
            for category in FILE_TYPE_CATEGORIES
        ),
        "families": tuple(
            {
                "id": family.id,
                "label": family.label,
                "category": family.category,
                "extensions": family.extensions,
            }
            for family in FILE_TYPE_FAMILIES
        ),
    }


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
    "serialize_file_type_taxonomy",
    "validate_file_type_taxonomy",
]
