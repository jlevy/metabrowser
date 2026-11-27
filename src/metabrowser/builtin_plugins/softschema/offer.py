"""Bounded discovery for the Table view of a served collection folder."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from functools import cache, lru_cache
from importlib.util import find_spec
from pathlib import Path, PureWindowsPath

from metabrowser.ignore_filter import IgnoreMode, make_ignore_filter

# On Patch the Conference and Universe, the median offer took 0.01 ms at
# the root and at most 0.22 ms in people/, over 20 reads with a warm filesystem.
# The entry cap bounds shallow traversal even when the folder holds no records.
_ENTRY_LIMIT = 40
_SNIFF_BYTES = 4096
# Resolving the sampled pointers in people/ took 14–26 ms on the same corpora,
# after importing the reader. Reuse that inference within the refresh window.
_POINTER_SAMPLE_LIMIT = 6
_POINTER_BYTES = 64 * 1024
_DATA_SUFFIXES = (".md", ".json", ".yaml", ".yml")
_SCHEMA_FOLDERS = ("_schemas", "schemas")


@cache
def _available() -> bool:
    return find_spec("softschema.collection") is not None


def _schema_folder(folder: Path) -> bool:
    return any(
        candidate.is_dir() and not candidate.is_symlink()
        for candidate in (folder / name for name in _SCHEMA_FOLDERS)
    )


def _read(path: Path, limit: int) -> bytes:
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        return stream.read(limit).removeprefix(b"\xef\xbb\xbf")


def _sniff(path: Path) -> bool:
    prefix = _read(path, _SNIFF_BYTES)
    if path.suffix == ".md":
        parts = prefix.splitlines()
        if not parts or parts[0].strip() != b"---":
            return False
        for line in parts[1:]:
            if line.strip() == b"---":
                return False
            if line.startswith((b"softschema:", b'"softschema":', b"'softschema':")):
                return True
        return False
    return b"softschema:" in prefix or b'"softschema"' in prefix


def _samples(folder: Path) -> Iterator[Path]:
    remaining = _ENTRY_LIMIT
    candidates = [folder]
    while candidates and remaining:
        candidate = candidates.pop(0)
        try:
            with os.scandir(candidate) as entries:
                for entry in entries:
                    remaining -= 1
                    if not entry.name.startswith(".") and not entry.is_symlink():
                        if candidate == folder and entry.is_dir(follow_symlinks=False):
                            candidates.append(Path(entry.path))
                        elif (
                            entry.name.endswith(_DATA_SUFFIXES)
                            and entry.is_file(follow_symlinks=False)
                            and _sniff(Path(entry.path))
                        ):
                            yield Path(entry.path)
                    if not remaining:
                        break
        except OSError:
            continue


def offers_collection(folder: Path) -> bool:
    """Offer the shared table where discovery finds a schema directory or an artifact."""
    if not _available():
        return False
    from .indexer import has_collection

    return (
        has_collection(folder) or _schema_folder(folder) or next(_samples(folder), None) is not None
    )


def _schema_pointer(path: Path, served_root: Path) -> Path | None:
    from softschema import parse_schema_metadata
    from softschema.validate import parse_frontmatter_text, parse_yaml_text

    try:
        content = _read(path, _POINTER_BYTES + 1)
        if len(content) > _POINTER_BYTES:
            return None
        text = content.decode()
        if path.suffix == ".md":
            _, document = parse_frontmatter_text(text, source=path.name)
        else:
            document = parse_yaml_text(text, source=path.name)
        metadata = (
            parse_schema_metadata(document.get("softschema"))
            if isinstance(document, dict)
            else None
        )
        ref = metadata.schema_ref if metadata is not None else None
        if not ref or Path(ref).is_absolute() or PureWindowsPath(ref).drive or "\\" in ref:
            return None
        target = Path(os.path.normpath(path.parent / ref))
        if (
            target.is_relative_to(served_root)
            and target.resolve(strict=True) == target
            and target.is_file()
        ):
            return target
    except (OSError, ValueError):
        return None
    return None


def collection_root(folder: Path, served_root: Path) -> Path:
    """Find the served ancestor that contains the folder and its sampled schemas."""
    return _sample_root(folder, served_root, int(time.monotonic() // 3))


@lru_cache(maxsize=128)
def _sample_root(folder: Path, served_root: Path, _refresh_window: int) -> Path:
    from itertools import islice

    ignored = make_ignore_filter(served_root, IgnoreMode.default)
    schemas = []
    for entry in islice(_samples(folder), _POINTER_SAMPLE_LIMIT):
        if ignored(entry.relative_to(served_root)):
            continue
        target = _schema_pointer(entry, served_root)
        if target is not None and not ignored(target.relative_to(served_root)):
            schemas.append(target.parent)
    if schemas:
        return Path(os.path.commonpath([folder, *schemas]))
    for candidate in (folder, *folder.parents):
        if not candidate.is_relative_to(served_root):
            break
        if _schema_folder(candidate) and not ignored(
            candidate.relative_to(served_root), is_dir=True
        ):
            return candidate
    return folder
