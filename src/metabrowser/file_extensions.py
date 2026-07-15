"""Centralized file-extension settings for the browser.

Three independent sets, each scoped to one decision:

* :data:`BROWSER_TEXT_EXTS` — extensions the browser opens as text in
  the detail pane *regardless of file size*. Extensions outside this
  set still render as text when the file is small (under the inline
  fallback cap), but above that threshold they fall through to binary.
  Includes web formats, structured data, tabular, config, source
  code, logs, and process marker files.

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

# Extensions the browser opens as text in the detail pane regardless
# of size. Outside this set, files still render as text when smaller
# than the inline fallback cap (see ``proc_browser._INLINE_TEXT_FALLBACK_BYTES``);
# above that threshold they fall through to binary.
BROWSER_TEXT_EXTS: frozenset[str] = frozenset(
    {
        # Documents
        ".md",
        ".txt",
        ".rst",
        ".markdown",
        # Web / markup
        ".html",
        ".htm",
        ".xml",
        # Structured data
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        # Tabular
        ".csv",
        ".tsv",
        # Config
        ".cfg",
        ".ini",
        ".env",
        # Source code
        ".py",
        ".sh",
        ".bash",
        ".zsh",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".css",
        # Database
        ".sql",
        # Logs (separate from .jsonl which gets structured rendering)
        ".log",
        # Process marker files
        ".pid",
    }
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
