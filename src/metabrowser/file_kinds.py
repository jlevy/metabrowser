"""File-kind classification + view registry for the browser preview pane.

The preview pane decides which renderer to show by mapping a file's kind
to an ordered list of views. Kinds are inferred by a small detector
chain — the first detector that returns a string wins. The chain is
mutable: plugins can extend it via :func:`register_file_kind_detector`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from frontmatter_format import FmFormatError, FmStyle, fmf_read_frontmatter, from_yaml_string
from ruamel.yaml.error import YAMLError

from metabrowser.gz_io import ArtifactPath

# VIEW_REGISTRY carries the built-in kinds owned by metabrowser core.
# Third-party plugins contribute additional kinds and views through their
# manifests without extending this registry.
VIEW_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "agent-log": [
        {"id": "log", "label": "Log", "default": True},
        {"id": "charts", "label": "Charts"},
        {"id": "raw", "label": "Raw JSON"},
    ],
    "unknown-jsonl": [
        {"id": "log", "label": "Log"},
        {"id": "raw", "label": "Raw JSON"},
    ],
    "markdown": [
        {
            "id": "rendered",
            "label": "Document",
            "default": True,
            "printable": True,
            "print_profile": "document",
            "render_runtime": "kpress",
        },
        {
            "id": "source",
            "label": "Source",
            "printable": True,
            "print_profile": "source",
            "render_runtime": "client",
        },
    ],
    "text": [
        {
            "id": "source",
            "label": "Source",
            "default": True,
            "printable": True,
            "print_profile": "source",
            "render_runtime": "client",
        },
    ],
    "binary": [],
}


def _read_gzip_markdown_frontmatter(path: Path) -> dict[str, Any] | None:
    """Parse YAML frontmatter from a gzip-transparent Markdown stream."""
    try:
        with ArtifactPath(path).open_text(errors="strict") as source:
            first_line = source.readline()
            if not first_line or first_line.rstrip() != FmStyle.yaml.start:
                return None

            metadata_lines: list[str] = []
            for line in source:
                if line.rstrip() == FmStyle.yaml.end:
                    metadata_text = "".join(metadata_lines)
                    if not metadata_text:
                        return None
                    try:
                        parsed = from_yaml_string(metadata_text)
                    except YAMLError as exc:
                        raise FmFormatError(
                            f"Error parsing YAML metadata: `{path}`: {exc}"
                        ) from exc
                    if not isinstance(parsed, dict):
                        raise FmFormatError(
                            f"Expected YAML metadata to be a dict, got {type(parsed)}: `{path}`"
                        )
                    return parsed
                metadata_lines.append(line)
    except UnicodeDecodeError:
        return None

    raise FmFormatError(
        f"Delimiter `{FmStyle.yaml.end}` for end of frontmatter not found: `{path}`"
    )


class FileContext:
    """Everything a detector may need to classify a file.

    The ``frontmatter`` property returns the parsed YAML dict (or ``None``
    when the file has no frontmatter). Malformed YAML — a leading ``---``
    fence with a parse error — sets ``frontmatter_parse_error`` to the
    reason while leaving ``frontmatter`` as ``None`` so detectors that
    require a key match still fail to claim the file. Callers (notably
    ``api_file``) can read ``frontmatter_parse_error`` and surface it
    as a visible error rather than silently treating the file as a
    plain markdown document.
    """

    __slots__ = (
        "_frontmatter_cache",
        "_frontmatter_loaded",
        "_frontmatter_parse_error",
        "_yaml_top_level_cache",
        "_yaml_top_level_loaded",
        "adapter",
        "ext",
        "path",
    )

    def __init__(self, path: Path, ext: str, adapter: str | None = None) -> None:
        self.path = path
        self.ext = ext
        self.adapter = adapter
        self._frontmatter_cache: dict[str, Any] | None = None
        self._frontmatter_loaded = False
        self._frontmatter_parse_error: str | None = None
        self._yaml_top_level_cache: dict[str, Any] | None = None
        self._yaml_top_level_loaded = False

    @property
    def frontmatter(self) -> dict[str, Any] | None:
        """Lazily-loaded YAML frontmatter (None if absent or unparsable)."""
        if not self._frontmatter_loaded:
            self._frontmatter_loaded = True
            try:
                artifact = ArtifactPath(self.path)
                if self.ext == ".md" and artifact.is_gzip:
                    raw = _read_gzip_markdown_frontmatter(self.path)
                else:
                    raw = fmf_read_frontmatter(self.path)
            except (OSError, ValueError) as exc:
                # OSError on unreadable file — leave parse_error unset
                # (we'll get a separate error elsewhere); record YAML
                # parse failures so callers can surface them.
                if not isinstance(exc, OSError):
                    self._frontmatter_parse_error = str(exc)
                raw = None
            self._frontmatter_cache = raw if isinstance(raw, dict) else None
        return self._frontmatter_cache

    @property
    def frontmatter_parse_error(self) -> str | None:
        """Reason the frontmatter couldn't be parsed, or ``None`` if it
        parsed cleanly or was simply absent. Reading this property
        triggers the lazy parse if it hasn't happened yet.
        """
        # Touch the lazy property so the parse runs on first read.
        _ = self.frontmatter
        return self._frontmatter_parse_error

    @property
    def yaml_top_level(self) -> dict[str, Any] | None:
        """Lazily-loaded top-level mapping from the first 16 KiB of a `.yaml`
        / `.yml` file, used by the classifier's ``yaml_has_key`` /
        ``yaml_value_prefix`` matchers. Cached per FileContext so multiple
        rules consulting the same file don't trigger multiple bounded reads
        + PyYAML parses. Returns None when the file is unreadable, the
        prefix doesn't parse, or the top-level value is not a mapping.
        """
        if not self._yaml_top_level_loaded:
            self._yaml_top_level_loaded = True
            # Import locally so the classifier can call this without
            # forcing a pyyaml import on the hot path of agent-log or
            # markdown classification.
            from metabrowser.plugin_loader.classify import (
                _yaml_top_level,
            )

            self._yaml_top_level_cache = _yaml_top_level(self.path)
        return self._yaml_top_level_cache


FileKindDetector = Callable[[FileContext], "str | None"]


def _detect_jsonl(ctx: FileContext) -> str | None:
    """Return the built-in kind for a JSONL file.

    Plugin classifiers run before this fallback and may claim additional
    adapters. Unknown streams remain browsable as generic JSONL.
    """
    if ctx.ext != ".jsonl":
        return None
    if ctx.adapter in ("claude", "gemini", "pi"):
        return "agent-log"
    return "unknown-jsonl"


def _detect_markdown(ctx: FileContext) -> str | None:
    return "markdown" if ctx.ext == ".md" else None


FILE_KIND_DETECTORS: list[FileKindDetector] = [
    _detect_jsonl,
    _detect_markdown,
]


def register_file_kind_detector(detector: FileKindDetector) -> None:
    """Register an additional file-kind detector. Detectors are consulted in
    insertion order; earlier entries win."""
    FILE_KIND_DETECTORS.append(detector)


def classify_file_kind(
    path: Path,
    ext: str,
    adapter: str | None = None,
) -> str:
    """Classify a file by running each detector in order; fall back to text."""
    ctx = FileContext(path, ext, adapter)
    for detector in FILE_KIND_DETECTORS:
        kind = detector(ctx)
        if kind is not None:
            return kind
    return "text"


def classify_by_ext(ext: str, adapter: str | None = None) -> str:
    """Legacy extension-only classifier for call sites without a path handy.
    Used by the charts endpoint for .jsonl files where adapter has been sniffed
    from the first log lines. Prefer classify_file_kind(path, ext, adapter)
    for everything else."""
    if ext == ".jsonl":
        return _detect_jsonl(FileContext(Path(), ext, adapter)) or "unknown-jsonl"
    if ext == ".md":
        return "markdown"
    return "text"
