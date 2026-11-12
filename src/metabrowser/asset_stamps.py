"""Addresses that name their content, so a browser can keep an asset without asking.

A response a browser holds is used without a request only while it is fresh, and the
application's own scripts, stylesheets, and fonts are fresh forever at an address that
changes whenever they do. Three classes of asset get such an address:

- ``/static/<file>?v=<stamp>``: one file, stamped by ``strif.file_mtime_hash`` (its
  name, size, and modification time), the token ``_static_asset_url`` in ``server.py``
  writes. :class:`StampedStaticFiles` serves it.
- ``/plugin-static/<plugin>/@<digest>/<file>``: every file of one plugin's directory.
- ``/kpress-static/@<digest>/v<version>/<file>``: every file of the KPress package.

A whole tree takes one stamp, a :class:`TreeStamp`, in the path rather than in a query,
because a module's relative imports, a worker's ``new URL("./x.js", import.meta.url)``,
and a stylesheet's ``url(../fonts/…)`` resolve against the path. They inherit the stamp
with no import map and no build step.

The digest is of the tree's contents, so the same release has the same addresses on
every machine and after every restart, and a golden that shows one stays still. Python
files and ``__pycache__`` are left out: no browser asks for them, and a server-side edit
should not make every browser fetch the plugin's scripts again.

**When a tree is stamped.** In an installed release nothing under a package changes while
the process runs, so its stamp is taken once. A tree that can change underneath the
process -- an editable install, or an operator's plugin directory -- is *live*: each page
the server renders takes its stamp again, from one ``stat`` per file, and reads and
hashes the files only when a stat moved. A page rendered after an edit therefore names
the edited tree, the way a ``?v=`` stamp follows an edited file.

**When an answer is immutable.** Only when the address names the content the server has
now (``http_caching.stamped_asset_cache_control``). A page rendered before an edit still
asks with the old stamp; the bytes it gets are the new ones, so they are revalidated
rather than kept under an address that names the old. For a plugin the check is also per
file: the file must have the size and modification time it had when the stamp was taken.
KPress resolves its own files, so its check is that the bytes served are among those the
stamp was taken from.

The work is bounded: a tree past :data:`MAX_TREE_FILES` files or :data:`MAX_TREE_BYTES`
bytes is not stamped, and its assets keep unstamped addresses, which are revalidated.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.datastructures import QueryParams
from starlette.staticfiles import StaticFiles
from strif import file_mtime_hash

from metabrowser.http_caching import stamped_asset_cache_control

if TYPE_CHECKING:
    from starlette.responses import Response
    from starlette.types import Scope

LOG = logging.getLogger(__name__)

# The trees stamped today: 66 KPress files of 1.05 MB, and 45 files in the largest
# built-in plugin (github). Measured 2026-11-11, a loaded laptop: a stat walk of all
# eleven built-in plugins, 133 files, took 4.9 ms, and of KPress 1.2 ms, which is why a
# release stamps once and only a live tree walks per page.
MAX_TREE_FILES = 2000
MAX_TREE_BYTES = 64 * 1024 * 1024

_STAMP_SEGMENT = re.compile(r"@([0-9a-f]{16})/(.*)", re.DOTALL)


def split_stamp(path: str) -> tuple[str | None, str]:
    """``(digest, rest)`` for ``@<digest>/rest``, else ``(None, path)``."""
    matched = _STAMP_SEGMENT.fullmatch(path)
    if matched is None:
        return None, path
    return matched.group(1), matched.group(2)


def content_digest(body: bytes) -> str:
    """The digest a stamp records for one file's bytes."""
    return hashlib.blake2b(body, digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class TreeStamp:
    """One tree's stamp, and what it was taken from."""

    digest: str
    # Relative POSIX path -> (size, mtime_ns), the stat each file had when it was read.
    files: Mapping[str, tuple[int, int]]
    # The content digest of every file, for a reader that does not resolve the path itself.
    contents: frozenset[str]

    def holds(self, rel: str, stat: os.stat_result) -> bool:
        """Whether the file at *rel*, which now has *stat*, is the one this stamp read."""
        return self.files.get(rel) == (stat.st_size, stat.st_mtime_ns)

    def holds_content(self, body: bytes) -> bool:
        """Whether *body* is the content of one of the files this stamp read."""
        return content_digest(body) in self.contents


_Signature = tuple[tuple[str, int, int], ...]


def _skipped_dir(name: str) -> bool:
    return name == "__pycache__" or name.startswith(".")


def _skipped_file(name: str) -> bool:
    return name.startswith(".") or name.endswith((".py", ".pyc"))


def _signature(root: Path, max_files: int) -> _Signature | None:
    """Every stamped file under *root* with its size and time, sorted; None past the bound."""
    found: list[tuple[str, int, int]] = []
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if not _skipped_dir(name))
        for name in files:
            if _skipped_file(name):
                continue
            full = os.path.join(directory, name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            found.append((Path(full).relative_to(root).as_posix(), stat.st_size, stat.st_mtime_ns))
            if len(found) > max_files:
                return None
    found.sort()
    return tuple(found)


def _hash_tree(root: Path, signature: _Signature, max_bytes: int) -> TreeStamp | None:
    if sum(size for _rel, size, _mtime in signature) > max_bytes:
        return None
    tree = hashlib.blake2b(digest_size=8)
    files: dict[str, tuple[int, int]] = {}
    contents: set[str] = set()
    for rel, size, mtime_ns in signature:
        try:
            body = (root / rel).read_bytes()
        except OSError:
            # Gone between the walk and the read: no stamp this time, and the next page
            # walks again.
            return None
        digest = content_digest(body)
        tree.update(f"{rel}\0{digest}\n".encode("utf-8", errors="surrogatepass"))
        files[rel] = (size, mtime_ns)
        contents.add(digest)
    return TreeStamp(digest=tree.hexdigest(), files=files, contents=frozenset(contents))


class StampedTree:
    """One directory whose files are served under a content-keyed path segment."""

    def __init__(
        self,
        root: Path,
        *,
        live: bool,
        max_files: int = MAX_TREE_FILES,
        max_bytes: int = MAX_TREE_BYTES,
    ) -> None:
        self.root = root
        self.live = live
        self._max_files = max_files
        self._max_bytes = max_bytes
        self._lock = threading.Lock()
        self._taken = False
        self._signature: _Signature | None = None
        self._latest: TreeStamp | None = None
        self._warned = False

    @property
    def settled(self) -> bool:
        """Whether :meth:`stamp` would return without touching the disk."""
        return self._taken and not self.live

    def stamp(self) -> TreeStamp | None:
        """The stamp a page rendered now names, or None for a tree that cannot be stamped.

        Touches the disk on a live tree, so a request handler on the event loop calls it
        in a thread unless :attr:`settled` says it will not.
        """
        if self.settled:
            return self._latest
        with self._lock:
            if self.settled:
                return self._latest
            signature = _signature(self.root, self._max_files)
            if signature is None:
                self._latest = None
            elif self._latest is None or signature != self._signature:
                self._latest = _hash_tree(self.root, signature, self._max_bytes)
            self._signature = signature
            self._taken = True
            if self._latest is None and signature is not None and not self._warned:
                self._warned = True
                LOG.warning(
                    "metabrowser assets under %s are past the stamping bound; "
                    "they are served at unstamped addresses and revalidated",
                    self.root,
                )
            return self._latest

    def latest(self) -> TreeStamp | None:
        """The stamp the last page was given, without touching the disk.

        None before any page was rendered in this process: a page from an earlier one asks
        with a stamp this one never gave, and its answer is revalidated.
        """
        return self._latest


def static_file_stamp(path: Path) -> str | None:
    """The ``?v=`` token of one static file now, or None when it cannot be read."""
    try:
        return file_mtime_hash(path)
    except OSError:
        return None


class StampedStaticFiles(StaticFiles):
    """``/static``, immutable at the address that names a file's current stamp.

    The shell writes every static URL with ``?v=`` (``_static_asset_url`` in
    ``server.py``). A request whose stamp is the file's stamp now is answered
    ``immutable``; a missing or different one -- an older page, or a hand-written URL --
    is ``no-cache``, so it is revalidated rather than kept under the wrong address.
    """

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        requested = QueryParams(scope.get("query_string", b"")).get("v")
        current = requested is not None and requested == static_file_stamp(Path(full_path))
        # Set on the 304 too: a revalidation's answer refreshes the headers a browser holds.
        response.headers["cache-control"] = stamped_asset_cache_control(current=current)
        return response


__all__ = [
    "MAX_TREE_BYTES",
    "MAX_TREE_FILES",
    "StampedStaticFiles",
    "StampedTree",
    "TreeStamp",
    "content_digest",
    "split_stamp",
    "static_file_stamp",
]
