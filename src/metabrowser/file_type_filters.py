"""Broad file-type presets shared by the server and browser."""

from __future__ import annotations

from typing import TypedDict


class FilterTypePreset(TypedDict):
    id: str
    label: str
    values: tuple[str, ...]


# A leading dot is an indexed logical extension. Any other token is a
# complete, case-insensitive filename. These are broad navigation aids rather
# than semantic classifiers: ambiguous extensions such as .m and .pl may cover
# more than one language. Keeping this vocabulary on the server lets aggregate
# tallies use exactly the same membership as the browser, including
# extensionless files such as README and LICENSE.
FILTER_TYPE_PRESETS: tuple[FilterTypePreset, ...] = (
    {
        "id": "docs",
        "label": "Docs",
        "values": (
            ".md",
            ".txt",
            ".rst",
            ".adoc",
            ".org",
            ".pdf",
            ".docx",
            ".doc",
            ".rtf",
            ".odt",
            ".epub",
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
    },
    {
        "id": "code",
        "label": "Code",
        "values": (
            ".py",
            ".pyi",
            ".ts",
            ".mts",
            ".cts",
            ".tsx",
            ".js",
            ".jsx",
            ".mjs",
            ".cjs",
            ".rs",
            ".go",
            ".java",
            ".kt",
            ".kts",
            ".swift",
            ".m",
            ".mm",
            ".c",
            ".h",
            ".cc",
            ".cpp",
            ".hpp",
            ".cs",
            ".rb",
            ".php",
            ".scala",
            ".clj",
            ".ex",
            ".exs",
            ".erl",
            ".hs",
            ".ml",
            ".lua",
            ".pl",
            ".r",
            ".jl",
            ".dart",
            ".vue",
            ".svelte",
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
            ".ps1",
            ".sql",
            ".css",
            ".scss",
            ".less",
            ".html",
            "makefile",
            "dockerfile",
            "justfile",
            "rakefile",
            "gemfile",
            "procfile",
        ),
    },
    {
        "id": "data",
        "label": "Data",
        "values": (
            ".json",
            ".jsonl",
            ".ndjson",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".properties",
            ".csv",
            ".tsv",
            ".psv",
            ".xml",
            ".parquet",
            ".arrow",
            ".avro",
            ".orc",
            ".feather",
            ".proto",
            ".graphql",
            ".sqlite",
            ".db",
        ),
    },
)


__all__ = ["FILTER_TYPE_PRESETS", "FilterTypePreset"]
