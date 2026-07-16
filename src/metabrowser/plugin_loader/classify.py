"""Manifest-driven file-kind classifier.

At server startup, the discovery layer collects every loaded plugin's
``[[kind]]`` rules. ``build_classifier`` compiles them into a single
function that takes a ``FileContext`` and returns the winning kind id
(or None if nothing matched).

Rule evaluation order:

1. Higher ``priority`` wins. Built-in kinds use 0; domain plugins should
   use 100+.
2. Within the same priority, rules are evaluated in the order they were
   discovered (built-in plugins first, then entry-point plugins, then
   local plugins). Stable.

The ``FileContext`` is a thin wrapper around the file's path, extension,
adapter sniff (for JSONL), and a lazily-loaded YAML frontmatter dict.
The wrapper is shared with the imperative fallback detector chain in
``file_kinds.py``.
Declarative manifest rules are the supported plugin classification surface.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pathspec
import yaml

from metabrowser.file_kinds import FileContext
from metabrowser.gz_io import ArtifactPath
from metabrowser.paths_safe import _relativize
from metabrowser.plugin_loader.manifest import KindMatch, KindRule

LOG = logging.getLogger(__name__)


KindClassifier = Callable[[FileContext], "str | None"]


# Caps for content-based classification. These predicates run while inventory
# entries are being classified, so they must never turn a large artifact into
# an unbounded parse. JSON matching accepts only complete documents within its
# cap; YAML matching intentionally parses a small prefix.
_JSON_CLASSIFICATION_MAX_BYTES = 256 * 1024

# Cap for the bounded YAML prefix read used by `yaml_has_key` matching.
# 16 KiB comfortably covers any reasonable schema-versioned header (`spec:
# Foo/0.1`-style fields land in the first dozen lines) while keeping the
# classifier's per-file cost negligible even on multi-MB YAML files.
_YAML_PREFIX_BYTES = 16 * 1024


def _json_top_level(
    path: Path, byte_limit: int = _JSON_CLASSIFICATION_MAX_BYTES
) -> dict[str, Any] | None:
    """Return a small JSON document's top-level mapping.

    Content predicates are classification hints, not a reason to parse an
    arbitrarily large artifact. Read one byte beyond the declared cap so an
    oversized document is rejected even when its matching key appears near the
    beginning. ``ArtifactPath`` applies the same bound while decompressing.
    """
    try:
        with ArtifactPath(path).open_binary(max_output_bytes=byte_limit + 1) as source:
            payload = source.read(byte_limit + 1)
    except OSError:
        return None
    if len(payload) > byte_limit:
        return None
    try:
        parsed = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _yaml_top_level(path: Path, byte_limit: int = _YAML_PREFIX_BYTES) -> dict[str, Any] | None:
    """Parse the top of a YAML file and return its top-level mapping.

    Reads at most ``byte_limit`` bytes, then runs PyYAML's safe loader. If the
    prefix happens to truncate mid-document, PyYAML usually raises; we swallow
    the error and return None so the classifier falls through to lower-priority
    rules. Returns None when the file is unreadable, the parse fails, or the
    top-level value is not a mapping.
    """
    try:
        with ArtifactPath(path).open_binary(max_output_bytes=byte_limit) as f:
            prefix = f.read(byte_limit)
    except OSError:
        return None
    try:
        parsed = yaml.safe_load(prefix)
    except yaml.YAMLError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


# Compiled pathspec cache, keyed by the raw glob string. The classifier
# rules are immutable post-load, so the cache lives for the process lifetime
# and never grows past the count of distinct `path_glob` values declared by
# loaded plugins.
class _PathMatcher(Protocol):
    """Version-neutral subset of the PathSpec API used by the classifier."""

    def match_file(self, file: str) -> bool:
        """Return whether *file* matches the compiled specification."""
        ...


_PATH_GLOB_CACHE: dict[str, _PathMatcher] = {}


def _path_spec(glob: str) -> _PathMatcher:
    spec = _PATH_GLOB_CACHE.get(glob)
    if spec is None:
        spec = pathspec.PathSpec.from_lines("gitignore", [glob])
        _PATH_GLOB_CACHE[glob] = spec
    return spec


def _match_path_glob(path: Path, glob: str) -> bool:
    """Match *path* against a gitignore-style glob. Uses the served-root-relative
    path when one is available; otherwise the absolute path."""
    rel = _relativize(str(path))
    candidate = rel if rel is not None else str(path)
    return _path_spec(glob).match_file(candidate)


def collect_folder_markers(rules: list[CompiledKindRule]) -> set[str]:
    """Return the set of `folder_marker` basenames declared by any loaded plugin.

    Used by the tree renderer to badge folders whose direct children include a
    known marker file. Stays in sync with the classifier: every marker spelled
    here is also a `basename`-equivalent classifier match.
    """
    markers: set[str] = set()
    for compiled in rules:
        m = compiled.rule.match.folder_marker
        if m is not None:
            markers.add(m)
    return markers


@dataclass(frozen=True, slots=True)
class CompiledKindRule:
    """A KindRule paired with a stable sort key for deterministic eval order."""

    rule: KindRule
    plugin_name: str
    discovery_index: int

    @property
    def sort_key(self) -> tuple[int, int]:
        # Descending priority (higher first); ascending discovery index.
        return (-self.rule.priority, self.discovery_index)


def _match_one(rule: KindMatch, ctx: FileContext) -> bool:
    """Evaluate a single declarative match predicate against a FileContext."""
    artifact = ArtifactPath(ctx.path)
    logical_path = ctx.path.with_name(artifact.logical_name)
    if rule.ext is not None and ctx.ext != rule.ext:
        return False
    if rule.exts is not None and ctx.ext not in rule.exts:
        return False
    if rule.basename is not None and logical_path.name != rule.basename:
        return False
    # folder_marker is semantically identical to basename at file-classification
    # time; the difference is that it also feeds the tree-row badge
    # (see collect_folder_markers + tree.set_folder_markers).
    if rule.folder_marker is not None and logical_path.name != rule.folder_marker:
        return False
    if rule.path_glob is not None and not _match_path_glob(logical_path, rule.path_glob):
        return False
    if rule.adapter is not None and ctx.adapter != rule.adapter:
        return False
    if rule.frontmatter_has_key is not None:
        fm = ctx.frontmatter
        if fm is None or rule.frontmatter_has_key not in fm:
            return False
    if rule.frontmatter_schema_prefix is not None:
        fm = ctx.frontmatter
        if fm is None:
            return False
        schema = fm.get("schema")
        if not isinstance(schema, str) or not schema.startswith(rule.frontmatter_schema_prefix):
            return False
    if rule.json_has_key is not None or rule.json_value_prefix is not None:
        if ctx.ext != ".json":
            return False
        raw = ctx.json_top_level
        if not isinstance(raw, dict):
            return False
        if rule.json_has_key is not None and rule.json_has_key not in raw:
            return False
        if rule.json_value_prefix is not None:
            # Used in tandem with json_has_key: the value of that key must
            # be a string starting with the prefix. If json_has_key is None
            # but json_value_prefix is set, the manifest validator rejects
            # the rule, so we don't need to handle that case here.
            if rule.json_has_key is None:
                return False
            value = raw.get(rule.json_has_key)
            if not isinstance(value, str) or not value.startswith(rule.json_value_prefix):
                return False
    if rule.yaml_has_key is not None or rule.yaml_value_prefix is not None:
        if ctx.ext not in {".yaml", ".yml"}:
            return False
        parsed = ctx.yaml_top_level
        if parsed is None:
            return False
        if rule.yaml_has_key is not None and rule.yaml_has_key not in parsed:
            return False
        if rule.yaml_value_prefix is not None:
            # Manifest validator requires yaml_has_key when yaml_value_prefix
            # is set, so this branch is reachable only when both are set.
            if rule.yaml_has_key is None:
                return False
            value = parsed.get(rule.yaml_has_key)
            if not isinstance(value, str) or not value.startswith(rule.yaml_value_prefix):
                return False
    return True


def build_classifier(rules: list[CompiledKindRule]) -> KindClassifier:
    """Build a single classifier function from a sorted list of compiled rules.

    Rules should already be sorted by ``sort_key``; the function returned
    here just walks them in order.
    """
    sorted_rules = sorted(rules, key=lambda r: r.sort_key)

    def classify(ctx: FileContext) -> str | None:
        for compiled in sorted_rules:
            if _match_one(compiled.rule.match, ctx):
                return compiled.rule.id
        return None

    return classify
