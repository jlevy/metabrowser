"""Which changed file GitHub's ``#diff-<hash>`` anchor names, read from the cache alone.

A pull request's Changes tab anchors each file as ``diff-`` and the SHA-256 of its path in
hexadecimal (``urls.py`` reads the anchor). The hash names a file only against the pull
request's list of changed files, so :func:`pull_file_for_anchor` hashes the paths of two
lists, in order, and takes the first that matches:

1. the list ``GET /api/plugin/github/pull-files`` answers from, when one is cached
   (``read_pull_files``), GitHub's or the local comparison's; then
2. the comparison of the cached record, listed in the store as the Changes tab lists it
   (``shared_pull_manifest``), which reads the manifest the record's fetch prepared, or
   lists it with Git when there is none.

Neither runs ``gh`` or fetches, so a URL resolves as well offline as on line, and an
anchor neither list holds is not an error: the URL opens the Changes tab itself, and
:class:`~metabrowser.cache.providers.PullRequestFile` says why. A path matches only when
the Changes tab has an address for it (``format_pull_href``), so what this returns always
opens.

The work is bounded by what each source already bounds: a cached list by
``MAX_PULL_FILES_BYTES``, a record by ``MAX_PULL_RECORD_BYTES``, and a comparison's
manifest by ``MAX_MANIFEST_FILES``, which a manifest past it says (``truncated``).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from metabrowser.builtin_plugins.github.pull_list import PullFileList, read_pull_files
from metabrowser.builtin_plugins.github.pull_manifest import shared_pull_manifest
from metabrowser.builtin_plugins.github.pull_record import PullRecord, read_pull_record
from metabrowser.cache.providers import PullRequestFile
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.git.process import GitError
from metabrowser.view_routes import format_pull_href

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.cache.urls import FileAnchor

log = logging.getLogger(__name__)


def path_digest(path: str) -> str | None:
    """GitHub's anchor hash of *path*, or ``None`` for a path that is not UTF-8."""

    try:
        return hashlib.sha256(path.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        return None


def _addressable(number: int, path: str) -> bool:
    try:
        format_pull_href(number, "files", path)
    except ValueError:
        return False
    return True


def _matching(number: int, digest: str, paths: Iterable[str]) -> str | None:
    return next(
        (path for path in paths if path_digest(path) == digest and _addressable(number, path)),
        None,
    )


def _cached_paths(listed: PullFileList | str) -> list[str]:
    return [row.path for row in listed.rows] if isinstance(listed, PullFileList) else []


async def _comparison_paths(
    published: PublishedSource, number: int, record: PullRecord | str
) -> tuple[list[str], bool] | None:
    """The paths of the record's comparison and whether its manifest was cut short.

    ``None`` when there is no record with a comparison, or the store cannot list it.
    """

    if not isinstance(record, PullRecord) or record.comparison is None:
        return None
    comparison = record.comparison
    try:
        listed = await shared_pull_manifest(
            published, number, comparison.base, comparison.head, retain_memory=False
        )
    except (DiffSourceError, GitError) as exc:
        log.debug("pull request %s's comparison could not be listed: %s", number, exc)
        return None
    paths: list[str] = []
    for change in listed.manifest.files:
        side = change.new if change.new is not None else change.old
        # A path Git could not spell in UTF-8 has its bytes in `path_b64` and a lossy
        # `path`, which is not the name GitHub hashed.
        if side is not None and side.path_b64 is None:
            paths.append(side.path)
    return paths, listed.manifest.truncated


async def pull_file_for_anchor(
    published: PublishedSource, number: int, anchor: FileAnchor
) -> PullRequestFile:
    """The changed file of pull request *number* whose path hashes to *anchor*'s digest."""

    listed = await asyncio.to_thread(read_pull_files, published.home, published.slug, number)
    found = _matching(number, anchor.digest, _cached_paths(listed))
    if found is not None:
        return PullRequestFile(found)
    record = await asyncio.to_thread(read_pull_record, published.home, published.slug, number)
    compared = await _comparison_paths(published, number, record)
    if compared is not None:
        paths, truncated = compared
        found = _matching(number, anchor.digest, paths)
        if found is not None:
            return PullRequestFile(found)
        if not truncated:
            return PullRequestFile(
                None,
                f"no file pull request {number} changes has the path the URL's anchor "
                "hashes (file_not_changed)",
            )
    if isinstance(listed, PullFileList):
        return PullRequestFile(
            None,
            f"no file in the cached list of pull request {number}'s changes has the path the "
            "URL's anchor hashes (file_not_listed)",
        )
    return PullRequestFile(
        None,
        f"pull request {number}'s changed files are not known offline: no list of them is "
        "cached, and no cached record names a comparison the store can list in full "
        "(files_unknown)",
    )


__all__ = ["path_digest", "pull_file_for_anchor"]
