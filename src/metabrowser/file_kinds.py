"""File-kind classification + view registry for the browser preview pane.

The preview pane decides which renderer to show by mapping a file's kind
to an ordered list of views. The manifest classifier
(``plugin_loader/classify.py``) runs first; the small detector chain here
is the fallback, and the first detector that returns a string wins.
Manifest ``[[kind]]`` rules are the plugin classification surface:
:func:`register_file_kind_detector` is not part of the plugin API. See
``docs/project/architecture/arch-plugin-system.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from frontmatter_format import FmFormatError, FmStyle, fmf_split_frontmatter

from metabrowser.content_sniff import ContentClass, sniff_artifact
from metabrowser.frontmatter_yaml import (
    FRONTMATTER_MAX_BYTES,
    FrontmatterError,
    load_frontmatter_yaml,
    unclosed_frontmatter_error,
)
from metabrowser.gz_io import (
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
)

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
    # Directories: core assigns the kind (api_file's is_dir branch);
    # the built-in `folder` plugin manifest contributes the views.
    "folder": [],
}


def _frontmatter_mapping(metadata_text: str) -> dict[str, Any]:
    parsed = load_frontmatter_yaml(metadata_text)
    if not isinstance(parsed, dict):
        raise FrontmatterError(f"Expected YAML metadata to be a dict, got {type(parsed)}")
    return cast("dict[str, Any]", parsed)


def _read_plain_frontmatter(path: Path) -> dict[str, Any] | None:
    """Parse the frontmatter at the head of an uncompressed file, in any fmf style.

    Reads at most FRONTMATTER_MAX_BYTES, so an opening fence that is never closed
    costs one bounded read. Bytes that are not UTF-8 inside the frontmatter mean the
    file has none, as ``fmf_read_frontmatter`` treats a binary file; outside it, in
    the body, they do not matter.
    """

    with path.open("rb") as source:
        head = source.read(FRONTMATTER_MAX_BYTES + 1)
    complete = len(head) <= FRONTMATTER_MAX_BYTES
    text = head[:FRONTMATTER_MAX_BYTES].decode("utf-8", "surrogateescape")
    try:
        metadata_text, _, _ = fmf_split_frontmatter(text, strict=True)
    except FmFormatError as exc:
        if complete:
            raise
        raise unclosed_frontmatter_error() from exc
    if not metadata_text:
        return None
    try:
        metadata_text.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return _frontmatter_mapping(metadata_text)


def _read_compressed_markdown_frontmatter(path: Path) -> dict[str, Any] | None:
    """Parse YAML frontmatter from a bounded compressed Markdown stream.

    The decode stops at FRONTMATTER_MAX_BYTES. Reaching it after the opening fence
    means the fence is not closed within the bound; reaching it on the first line means
    the file has no front matter; and a decode past its CPU-time budget keeps its own
    meaning, an unreadable file.
    """
    in_fence = False
    try:
        with ArtifactPath(path).open_text(
            errors="strict", max_output_bytes=FRONTMATTER_MAX_BYTES
        ) as source:
            first_line = source.readline()
            if not first_line or first_line.rstrip() != FmStyle.yaml.start:
                return None
            in_fence = True

            metadata_lines: list[str] = []
            for line in source:
                if line.rstrip() == FmStyle.yaml.end:
                    metadata_text = "".join(metadata_lines)
                    if not metadata_text:
                        return None
                    return _frontmatter_mapping(metadata_text)
                metadata_lines.append(line)
    except UnicodeDecodeError:
        return None
    except ArtifactDecompressionTimeoutError:
        raise
    except ArtifactDecompressionLimitError as exc:
        if not in_fence:
            return None
        raise unclosed_frontmatter_error() from exc

    raise FmFormatError(f"Delimiter `{FmStyle.yaml.end}` for end of frontmatter not found")


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
        "_content_class_cache",
        "_frontmatter_cache",
        "_frontmatter_loaded",
        "_frontmatter_parse_error",
        "_json_top_level_cache",
        "_json_top_level_loaded",
        "_yaml_top_level_cache",
        "_yaml_top_level_loaded",
        "adapter",
        "ext",
        "path",
    )

    def __init__(
        self,
        path: Path,
        ext: str,
        adapter: str | None = None,
        content_class: ContentClass | None = None,
    ) -> None:
        self.path = path
        self.ext = ext
        self.adapter = adapter
        # Pre-supplied by a caller that already knows — today only tests and
        # call sites without a real path on disk. A crawl that sniffs during
        # inventory would populate it the same way, which is the point of
        # taking it here rather than reading unconditionally.
        self._content_class_cache: ContentClass | None = content_class
        self._frontmatter_cache: dict[str, Any] | None = None
        self._frontmatter_loaded = False
        self._frontmatter_parse_error: str | None = None
        self._json_top_level_cache: dict[str, Any] | None = None
        self._json_top_level_loaded = False
        self._yaml_top_level_cache: dict[str, Any] | None = None
        self._yaml_top_level_loaded = False

    @property
    def content_class(self) -> ContentClass:
        """Lazily-sniffed :class:`ContentClass` for this file.

        Peer of :attr:`json_top_level` and :attr:`yaml_top_level`: a bounded
        read that happens only when something asks, and is cached so repeated
        questions cost one read. Nothing on the ordinary path asks — extension
        typing answers first — so this stays unread for almost every file the
        browser opens.
        """
        if self._content_class_cache is None:
            self._content_class_cache = sniff_artifact(self.path)
        return self._content_class_cache

    @property
    def frontmatter(self) -> dict[str, Any] | None:
        """Lazily-loaded YAML frontmatter (None if absent or unparsable)."""
        if not self._frontmatter_loaded:
            self._frontmatter_loaded = True
            try:
                artifact = ArtifactPath(self.path)
                if self.ext == ".md" and artifact.is_compressed:
                    raw = _read_compressed_markdown_frontmatter(self.path)
                else:
                    raw = _read_plain_frontmatter(self.path)
            except (OSError, ValueError) as exc:
                # OSError on unreadable file — leave parse_error unset
                # (we'll get a separate error elsewhere); record YAML
                # parse failures and refused frontmatter (FrontmatterError)
                # so callers can surface them.
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
    def json_top_level(self) -> dict[str, Any] | None:
        """Lazily load a bounded, complete top-level JSON mapping."""
        if not self._json_top_level_loaded:
            self._json_top_level_loaded = True
            from metabrowser.plugin_loader.classify import _json_top_level

            self._json_top_level_cache = _json_top_level(self.path)
        return self._json_top_level_cache

    @property
    def yaml_top_level(self) -> dict[str, Any] | None:
        """Lazily-loaded top-level mapping from a bounded prefix
        (``classify._YAML_PREFIX_BYTES``) of a `.yaml` / `.yml` file, used by
        the classifier's ``yaml_has_key`` /
        ``yaml_value_prefix`` matchers. Cached per FileContext so multiple
        rules consulting the same file don't trigger multiple bounded reads
        + parses. Returns None when the file is unreadable, the
        prefix doesn't parse, or the top-level value is not a mapping.
        """
        if not self._yaml_top_level_loaded:
            self._yaml_top_level_loaded = True
            # Import locally: the classifier module imports this one.
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
    """Fallback classifier for call sites with no file on disk, such as Git
    blobs (``git/content_routes.py``), after the manifest rules found no
    kind. Prefer classify_file_kind(path, ext, adapter) when a path exists."""
    if ext == ".jsonl":
        return _detect_jsonl(FileContext(Path(), ext, adapter)) or "unknown-jsonl"
    if ext == ".md":
        return "markdown"
    return "text"
