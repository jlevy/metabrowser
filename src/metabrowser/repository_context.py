"""Bounded read-only GitHub identity for the currently served repository."""

from __future__ import annotations

import configparser
import os
import re
import stat
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlsplit

# Keep first-paint repository discovery bounded even for corrupt metadata.
MAX_GIT_POINTER_BYTES = 4 * 1024
MAX_GIT_CONFIG_BYTES = 1024 * 1024
MAX_PACKED_REFS_BYTES = 8 * 1024 * 1024
_FULL_REVISION_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_REPOSITORY_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class RepositoryContext(TypedDict):
    """Public-safe GitHub identity used to verify localizable repository URLs."""

    branch: str | None
    host: str
    name: str
    owner: str
    revision: str
    served_prefix: str


def discover_repository_context(served_root: Path) -> RepositoryContext | None:
    """Return verified GitHub identity without invoking Git or exposing local paths."""

    root = served_root.resolve()
    git_root = find_git_root(root)
    if git_root is None:
        return None
    git_dir = resolve_git_dir(git_root)
    if git_dir is None:
        return None
    common_dir = resolve_common_dir(git_dir)
    remote = _read_origin_remote(common_dir / "config")
    if remote is None:
        return None
    owner, name = remote
    head = _read_head(git_dir, common_dir)
    if head is None:
        return None
    branch, revision = head
    try:
        served_prefix = root.relative_to(git_root).as_posix()
    except ValueError:
        return None
    return RepositoryContext(
        branch=branch,
        host="github.com",
        name=name,
        owner=owner,
        revision=revision.lower(),
        served_prefix="" if served_prefix == "." else served_prefix,
    )


def find_git_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_git_dir(git_root: Path) -> Path | None:
    marker = git_root / ".git"
    if marker.is_dir():
        return marker.resolve()
    if not marker.is_file():
        return None
    pointer = read_bounded_text(marker, MAX_GIT_POINTER_BYTES)
    if pointer is None or not pointer.startswith("gitdir:"):
        return None
    raw_path = pointer.removeprefix("gitdir:").strip()
    if not raw_path or "\0" in raw_path:
        return None
    return (git_root / raw_path).resolve()


def resolve_common_dir(git_dir: Path) -> Path:
    pointer = read_bounded_text(git_dir / "commondir", MAX_GIT_POINTER_BYTES)
    if pointer is None:
        return git_dir
    raw_path = pointer.strip()
    return (git_dir / raw_path).resolve() if raw_path and "\0" not in raw_path else git_dir


def _read_origin_remote(config_path: Path) -> tuple[str, str] | None:
    source = read_bounded_text(config_path, MAX_GIT_CONFIG_BYTES)
    if source is None:
        return None
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read_string(source)
        remote = parser.get('remote "origin"', "url")
    except (configparser.Error, KeyError, ValueError):
        return None
    return _parse_github_remote(remote.strip())


def _parse_github_remote(remote: str) -> tuple[str, str] | None:
    scp_match = re.fullmatch(r"(?:[^@/:]+@)?github\.com:([^/]+)/(.+)", remote)
    if scp_match:
        owner, name = scp_match.groups()
    else:
        parsed = urlsplit(remote)
        if parsed.hostname is None or parsed.hostname.lower() != "github.com":
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2:
            return None
        owner, name = parts
    name = name.removesuffix(".git")
    if not _REPOSITORY_PART_RE.fullmatch(owner) or not _REPOSITORY_PART_RE.fullmatch(name):
        return None
    return owner, name


def _read_head(git_dir: Path, common_dir: Path) -> tuple[str | None, str] | None:
    source = read_bounded_text(git_dir / "HEAD", MAX_GIT_POINTER_BYTES)
    if source is None:
        return None
    value = source.strip()
    if _FULL_REVISION_RE.fullmatch(value):
        return None, value
    if not value.startswith("ref: refs/heads/"):
        return None
    reference = value.removeprefix("ref: ")
    branch = reference.removeprefix("refs/heads/")
    revision = _read_reference(git_dir, common_dir, reference)
    if revision is None:
        return None
    return branch, revision


def _read_reference(git_dir: Path, common_dir: Path, reference: str) -> str | None:
    for base in (git_dir, common_dir):
        value = read_bounded_text(base / reference, MAX_GIT_POINTER_BYTES)
        if value is not None and _FULL_REVISION_RE.fullmatch(value.strip()):
            return value.strip()
    packed = read_bounded_text(common_dir / "packed-refs", MAX_PACKED_REFS_BYTES)
    if packed is None:
        return None
    for line in packed.splitlines():
        if not line or line.startswith(("#", "^")):
            continue
        revision, separator, packed_reference = line.partition(" ")
        if separator and packed_reference == reference and _FULL_REVISION_RE.fullmatch(revision):
            return revision
    return None


def read_regular_file_head(path: Path, limit: int) -> bytes | None:
    """Up to *limit* bytes of a regular file, or ``None`` for anything else.

    A directory's ``.git`` is whatever was planted there, and a FIFO in the place of one
    of these files would block ``open`` until something wrote to it: a reviewer's replica
    with one as ``commondir`` blocked discovery until it was killed. So the file is opened
    without blocking and read only once it is known to be a regular file.
    """

    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    except (OSError, ValueError):
        return None
    try:
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return None
            return stream.read(limit)
    except OSError:
        return None


def read_bounded_text(path: Path, limit: int) -> str | None:
    """A regular file of at most *limit* bytes as text, or ``None``."""

    source = read_regular_file_head(path, limit + 1)
    if source is None or len(source) > limit:
        return None
    try:
        return source.decode("utf-8")
    except UnicodeError:
        return None
