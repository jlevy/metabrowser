"""Centralized file-extension settings for the browser.

The syntax registry and three independent sets are each scoped to one decision:

* :data:`SYNTAX_LANGUAGE_BY_EXTENSION` — logical extensions backed by a
  grammar in the vendored Highlight.js registry. The server injects this
  mapping into the browser so routing and rendering cannot drift.

* :data:`SYNTAX_LANGUAGE_BY_BASENAME` — extensionless source names backed by
  those same grammars.

* :data:`BROWSER_TEXT_EXTS` — extensions the browser opens as text in
  the detail pane *regardless of file size*. Extensions outside this
  set still render as text when bounded content sniffing identifies
  text. Includes every syntax-known extension by construction.

* :data:`BROWSER_IMAGE_EXTS` — extensions the browser renders as
  images via ``<img>``.

* :data:`BROWSER_TRACKABLE_EXTS` — extensions the activity tracker
  watches for live writes. Kept tight because every entry costs one
  ``stat()`` per poll on the candidate-discovery walk; only formats
  an active process commonly appends to at runtime belong here. Notably
  excludes compressed artifacts (write-once-sealed) and source code (not produced
  at runtime).

Any supported extension remains browsable through gzip or zlib compression.
The browser's ``ArtifactPath`` layer provides transparent bounded reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

# Logical extension to a language in the exact vendored Highlight.js common
# registry. Keep aliases here rather than in individual renderers; settings.py
# injects one serialized copy into every browser surface.
SYNTAX_LANGUAGE_BY_EXTENSION: Final[Mapping[str, str]] = MappingProxyType(
    {
        ".bash": "bash",
        ".c": "c",
        ".cc": "cpp",
        ".cfg": "ini",
        ".cjs": "javascript",
        ".conf": "ini",
        ".cpp": "cpp",
        ".cs": "csharp",
        ".css": "css",
        ".cts": "typescript",
        ".cxx": "cpp",
        ".diff": "diff",
        ".gemspec": "ruby",
        ".geojson": "json",
        ".go": "go",
        ".gql": "graphql",
        ".graphql": "graphql",
        ".h": "c",
        ".hh": "cpp",
        ".hpp": "cpp",
        ".htm": "xml",
        ".html": "xml",
        ".hxx": "cpp",
        ".ini": "ini",
        ".java": "java",
        ".js": "javascript",
        ".json": "json",
        ".jsonl": "json",
        ".jsx": "javascript",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".less": "less",
        ".lua": "lua",
        ".m": "objectivec",
        ".markdown": "markdown",
        ".md": "markdown",
        ".mjs": "javascript",
        ".mk": "makefile",
        ".mm": "objectivec",
        ".mts": "typescript",
        ".ndjson": "json",
        ".patch": "diff",
        ".php": "php",
        ".phtml": "php-template",
        ".pl": "perl",
        ".pm": "perl",
        ".properties": "ini",
        ".py": "python",
        ".pyi": "python",
        ".pyw": "python",
        ".r": "r",
        ".rb": "ruby",
        ".rs": "rust",
        ".scss": "scss",
        ".sh": "bash",
        ".sql": "sql",
        ".swift": "swift",
        ".toml": "toml",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".vb": "vbnet",
        ".wat": "wasm",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".zsh": "bash",
    }
)

SYNTAX_LANGUAGE_BY_BASENAME: Final[Mapping[str, str]] = MappingProxyType(
    {
        "gemfile": "ruby",
        "makefile": "makefile",
        "rakefile": "ruby",
    }
)


def syntax_language_for_path(path_or_name: str, ext: str = "") -> str:
    """Resolve a logical path through the shipped syntax registry."""
    basename = path_or_name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for compression_suffix in (".gz", ".zlib"):
        if basename.endswith(compression_suffix):
            basename = basename[: -len(compression_suffix)]
            break
    logical_ext = ext.lower()
    if not logical_ext:
        dot = basename.rfind(".")
        logical_ext = basename[dot:] if dot > 0 else ""
    return SYNTAX_LANGUAGE_BY_BASENAME.get(basename, "") or SYNTAX_LANGUAGE_BY_EXTENSION.get(
        logical_ext, ""
    )


# Extensions the browser opens as text in the detail pane regardless of size.
# Files outside this set still render as text when bounded content sniffing
# identifies them as text.
BROWSER_TEXT_EXTS: frozenset[str] = frozenset(
    {
        # Documents without a syntax grammar
        ".txt",
        ".rst",
        # Tabular
        ".csv",
        ".tsv",
        # Configuration without a matching shipped grammar
        ".env",
        # Plain logs (.jsonl gets structured rendering)
        ".log",
        # Process marker files
        ".pid",
    }
    | set(SYNTAX_LANGUAGE_BY_EXTENSION)
)

# Extensions the browser renders as images via ``<img>``.
BROWSER_IMAGE_EXTS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".bmp",
        ".ico",
        ".avif",
        ".apng",
    }
)

# Extensions the activity tracker watches for live writes. Keep tight:
# every entry costs a stat() per poll on the candidate discovery walk,
# and only formats active processes commonly append to belong here. Compression
# suffixes are deliberately excluded because compressed artifacts are sealed.
BROWSER_TRACKABLE_EXTS: frozenset[str] = frozenset(
    {
        ".jsonl",
        ".yaml",
        ".yml",
        ".pid",
        ".json",
        ".md",
        ".csv",
    }
)
