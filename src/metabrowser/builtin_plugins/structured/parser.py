"""Parse + re-serialize JSON / YAML for the structured plugin.

The plugin's ``/api/plugin/structured/parsed`` handler delegates here.
We parse the file once, cache the ``(parsed, pretty_yaml)`` pair on a
small LRU keyed by ``(disk_path, mtime_hash)``, and ship the result
to the client which renders it as a virtualized YAML-styled tree.

Comments are dropped in v1 (lossy round-trip). The on-the-wire payload
flags ``comments_supported = False`` so v2 can flip the flag without a
renderer rewrite when ``ruamel.yaml`` round-trip-with-comments lands.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from metabrowser.gz_io import ArtifactDecompressionLimitError, ArtifactPath

LOG = logging.getLogger(__name__)


# Hard cap on parse size. Files above this short-circuit to the
# truncated branch and the Tree view falls back to Source. The cap
# is generous (8 MB matches metabrowser's existing
# _TEXT_PREVIEW_MAX_CHUNK_BYTES) but bounded so a 1 GB JSON dump
# doesn't OOM the server.
STRUCTURED_PARSE_MAX_BYTES = int(os.environ.get("STRUCTURED_PARSE_MAX_BYTES", str(8 * 1024 * 1024)))
# Cache entries are small (a parsed dict + a YAML string per file) so
# 64 is comfortable headroom for a typical session.
STRUCTURED_CACHE_SIZE = int(os.environ.get("STRUCTURED_CACHE_SIZE", "64"))


@dataclass(frozen=True)
class StructuredPayload:
    """The data we cache per (path, mtime_hash) and ship to the client.

    All fields are JSON-serializable; the handler wraps them in a
    JSON envelope with the file's path and ext.
    """

    parsed: Any
    pretty_yaml: str
    node_count: int
    max_depth: int
    parse_error: str | None
    truncated: bool


def _count_nodes_and_depth(value: Any, depth: int = 0) -> tuple[int, int]:
    """Walk the parsed tree once. Returns (node_count, max_depth).

    Node count = every container (dict, list) plus every leaf value.
    Depth = deepest nesting level reached (0 for a single primitive).
    """
    if isinstance(value, dict):
        if not value:
            return 1, depth
        total = 1
        max_d = depth
        for v in value.values():
            n, d = _count_nodes_and_depth(v, depth + 1)
            total += n
            if d > max_d:
                max_d = d
        return total, max_d
    if isinstance(value, list):
        if not value:
            return 1, depth
        total = 1
        max_d = depth
        for v in value:
            n, d = _count_nodes_and_depth(v, depth + 1)
            total += n
            if d > max_d:
                max_d = d
        return total, max_d
    # Leaf: primitive value.
    return 1, depth


def _serialize_to_yaml(value: Any) -> str:
    """Serialize a JSON-safe value to a YAML string matching the
    metabrowser YAML aesthetic (indent=2, no wrap, double-quoted
    strings, plain keys, single blank line between blocks).

    Prefers ``ruamel.yaml`` (round-trip-capable, unlocks v2 comment
    preservation); falls back to ``pyyaml`` if ruamel isn't installed
    in this environment. Either produces output that the renderer's
    line-classification works on.
    """
    try:
        from ruamel.yaml import (
            YAML,  # type: ignore[import-not-found]
        )
        from ruamel.yaml.compat import (
            StringIO,  # type: ignore[import-not-found]
        )

        yaml = YAML()
        yaml.indent(mapping=2, sequence=4, offset=2)
        yaml.width = 4096  # effectively no wrap
        yaml.default_flow_style = False
        yaml.allow_unicode = True
        # Match YamlViewer's QUOTE_DOUBLE preference for strings.
        yaml.default_style = None  # let ruamel pick per value; we post-process
        buf = StringIO()
        yaml.dump(value, buf)
        text = buf.getvalue()
    except ImportError:
        import yaml as pyyaml  # type: ignore[import-not-found]

        text = pyyaml.safe_dump(
            value,
            default_flow_style=False,
            indent=2,
            width=4096,
            allow_unicode=True,
            sort_keys=False,
        )

    return re.sub(r"\n{3,}", "\n\n", text)


def _parse_text(text: str, ext: str) -> Any:
    """Parse JSON or YAML text into a JSON-safe Python value.

    Raises whatever the underlying parser raises on malformed input.
    The caller turns that into a ``parse_error`` field rather than a
    5xx response.
    """
    if ext == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # JSONC dialect (tsconfig.json, .vscode/*.json, ...): comments
            # and trailing commas. Strict ``json`` stays the fast path for
            # normal JSON of any size; only files that fail it fall through
            # to ``json5``, and those are tiny config files, so json5's
            # pure-Python speed never touches the hot path.
            import json5  # type: ignore[import-not-found]

            return json5.loads(text)
    # .yaml / .yml — accept ``ruamel.yaml`` typ="safe" or pyyaml.safe_load.
    # Use the multi-document loader: generated files often concatenate YAML
    # documents with ``---`` separators (and frequently end with a trailing
    # ``---`` plus a comment, which parses as an empty document). A single-
    # document load raises on those, dropping the file to the plain-text
    # fallback instead of rendering the structured tree.
    try:
        from ruamel.yaml import (
            YAML,  # type: ignore[import-not-found]
        )

        yaml = YAML(typ="safe")
        docs = list(yaml.load_all(text))
    except ImportError:
        import yaml as pyyaml  # type: ignore[import-not-found]

        docs = list(pyyaml.safe_load_all(text))
    return _collapse_yaml_documents(docs)


def _collapse_yaml_documents(docs: list[Any]) -> Any:
    """Reduce a YAML document stream to a single tree-renderable value.

    A lone document renders as itself. A multi-document stream renders as a
    list, after dropping empty (``None``) documents — these are usually a
    trailing ``---`` followed only by comments. If exactly one real document
    remains it renders bare, not as a one-element list.
    """
    if len(docs) <= 1:
        return docs[0] if docs else None
    meaningful = [doc for doc in docs if doc is not None]
    if len(meaningful) == 1:
        return meaningful[0]
    return meaningful or None


def parse_structured(target: Path, ext: str, mtime_hash: str) -> StructuredPayload:
    """Parse, serialize, and cache. Use this as the public entry point.

    The cache is keyed by ``(disk_path, mtime_hash)``: when the file
    changes, the inventory's mtime_hash changes, and the next call
    rebuilds the payload. This piggybacks on the existing invalidation
    contract instead of inventing a new one.
    """
    return _parse_structured_cached(str(target), ext, mtime_hash)


@lru_cache(maxsize=STRUCTURED_CACHE_SIZE)
def _parse_structured_cached(
    target_str: str,
    ext: str,
    mtime_hash: str,
) -> StructuredPayload:
    target = Path(target_str)
    artifact = ArtifactPath(target)

    def truncated_payload() -> StructuredPayload:
        return StructuredPayload(
            parsed=None,
            pretty_yaml="",
            node_count=0,
            max_depth=0,
            parse_error=None,
            truncated=True,
        )

    try:
        # Compressed streams must reach the caller-specific bound before a
        # malformed trailer can obscure that they exceed it.
        if not artifact.is_compressed and artifact.logical_size > STRUCTURED_PARSE_MAX_BYTES:
            return truncated_payload()
        with artifact.open_text(max_output_bytes=STRUCTURED_PARSE_MAX_BYTES) as fh:
            text = fh.read()
        parsed = _parse_text(text, ext)
    except ArtifactDecompressionLimitError:
        return truncated_payload()
    except Exception as exc:
        return StructuredPayload(
            parsed=None,
            pretty_yaml="",
            node_count=0,
            max_depth=0,
            parse_error=f"{type(exc).__name__}: {exc}",
            truncated=False,
        )

    try:
        pretty_yaml = _serialize_to_yaml(parsed)
    except Exception as exc:
        # Parsing succeeded but serialization failed — uncommon (the
        # output is just structured data the YAML serializer should
        # handle), so log loudly and ship the parsed tree with an
        # empty pretty_yaml. The client still gets the tree view.
        LOG.warning("structured: failed to serialize %s to YAML: %s", target, exc, exc_info=True)
        pretty_yaml = ""

    node_count, max_depth = _count_nodes_and_depth(parsed)
    return StructuredPayload(
        parsed=parsed,
        pretty_yaml=pretty_yaml,
        node_count=node_count,
        max_depth=max_depth,
        parse_error=None,
        truncated=False,
    )
