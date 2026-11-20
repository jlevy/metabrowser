"""The pull requests a branch is the head of, for the ref chooser's rows.

The chooser (``static/source-ref-selector.js``) lists a repository's branches, and
``GET /api/source/refs`` asks :func:`metabrowser.cache.providers.ref_pulls_for` which pull
requests each is the head of, so a row can show its pull request beside the branch. This
module is what the GitHub provider answers with, from the repository's pull-request
catalog (:mod:`.pull_catalog`) and nothing else: it reads the cache and never asks
GitHub, so the chooser opens as fast as it does on a repository with no pull requests. A
catalog that has not arrived yet answers as such, and the chooser asks again while a job
fills it.

A pull request is listed under its head branch only when the branch is the repository's
own: one from a fork is not, since a fork's branch of the same name is another branch
(``head_repository`` is the fork's ``owner/name``). A branch that several pull requests
name, one from each of several attempts, lists the open ones first and then the newest
first, so the first is what a row shows.

The answer is built once for each revision of the catalog and kept: a chooser asks on
every keystroke of its filter. A revision is the catalog's ``epoch`` and ``revision``,
which every page a job writes moves.
"""

from __future__ import annotations

import asyncio
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from metabrowser.builtin_plugins.github.pull_catalog import HeadPull, catalog_heads
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.cache.providers import RefPull

# Revisions kept: the repositories one server shows in turn. A server serves one root, and
# tests serve several.
_MAX_KEPT: Final = 4
_OPEN: Final = ("open", "draft")


@dataclass(frozen=True, slots=True)
class _Entry:
    pull: RefPull
    folded: str


@dataclass(frozen=True, slots=True)
class _Heads:
    """The catalog's pull requests by head branch, at one revision."""

    revision: tuple[str, int] | None
    ready: bool
    complete: bool
    by_head: Mapping[str, tuple[_Entry, ...]]


_ABSENT: Final = _Heads(None, False, False, {})
_KEPT: OrderedDict[tuple[str, str], _Heads] = OrderedDict()
_LOCK: Final = threading.Lock()


def _build(repository: ListedRepository) -> _Heads:
    """The heads of *repository*'s catalog now: kept while its revision stays. Blocking."""

    key = (str(repository.home), repository.slug)
    with _LOCK:
        held = _KEPT.get(key)
    found = catalog_heads(repository, known=held.revision if held is not None else None)
    state = found.state
    if state is None:
        return _ABSENT
    if found.pulls is None:
        assert held is not None  # a known revision came from what is held
        return held
    grouped: dict[str, list[_Entry]] = {}
    for pull in found.pulls:
        grouped.setdefault(pull.head_ref, []).append(_entry(pull))
    heads = _Heads(
        (state.epoch, state.revision),
        True,
        state.done["all"] and not found.limited,
        {
            # Newest first as read, so open first keeps the newest of each.
            head: tuple(sorted(entries, key=lambda entry: entry.pull["state"] not in _OPEN))
            for head, entries in grouped.items()
        },
    )
    with _LOCK:
        _KEPT[key] = heads
        _KEPT.move_to_end(key)
        while len(_KEPT) > _MAX_KEPT:
            _KEPT.popitem(last=False)
    return heads


def _entry(pull: HeadPull) -> _Entry:
    return _Entry(
        RefPull(number=pull.number, title=pull.title, state=pull.state), pull.title.casefold()
    )


def _matcher(needle: str) -> Callable[[_Entry], bool] | None:
    """What decides whether a pull request matches *needle*, or ``None`` for no filter.

    ``#`` and digits match the numbers that start with them, as Quick Search's explicit
    number does, so ``#`` alone is every pull request; anything else matches a title that
    holds every one of its words, ignoring case. A bare number is a word, so it finds a
    title that says it.
    """

    text = needle.strip()
    if not text:
        return None
    digits = text[1:].strip() if text.startswith("#") else None
    if digits is not None and (digits == "" or (digits.isascii() and digits.isdecimal())):
        return lambda entry: str(entry.pull["number"]).startswith(digits)
    terms = tuple(dict.fromkeys(text.casefold().split()))
    return lambda entry: all(term in entry.folded for term in terms)


@dataclass(frozen=True, slots=True)
class GithubRefPulls:
    """:class:`~metabrowser.cache.providers.RefPulls` over one revision of the catalog."""

    _heads: _Heads
    refreshing: bool

    @property
    def token(self) -> str:
        revision = self._heads.revision
        named = f"{revision[0]}:{revision[1]}" if revision is not None else "absent"
        return f"{named}:{int(self.refreshing)}"

    @property
    def ready(self) -> bool:
        return self._heads.ready

    @property
    def complete(self) -> bool:
        return self._heads.complete

    def pulls(self, head: str, needle: str = "") -> tuple[RefPull, ...]:
        entries = self._heads.by_head.get(head, ())
        matches = _matcher(needle)
        if matches is not None:
            # False sorts first, and the sort is stable: the matches keep their order.
            entries = tuple(sorted(entries, key=lambda entry: not matches(entry)))
        return tuple(entry.pull for entry in entries)

    def matching(self, needle: str) -> frozenset[str]:
        matches = _matcher(needle)
        if matches is None:
            return frozenset()
        return frozenset(
            head
            for head, entries in self._heads.by_head.items()
            if any(matches(entry) for entry in entries)
        )


def ref_pulls_of(repository: ListedRepository, *, refreshing: bool = False) -> GithubRefPulls:
    """*repository*'s pull requests by head branch, as its cache holds them now. Blocking.

    *refreshing* is whether a job is filling the catalog, which the caller knows.
    """

    return GithubRefPulls(_build(repository), refreshing)


async def served_ref_pulls(app: Any) -> GithubRefPulls | None:
    """The served repository's pull requests by head branch, or ``None`` with no repository.

    A mirror's repository is what it mirrors, and a folder's is its checkout's ``origin``
    (:mod:`.checkout`). Reads the cache alone, off the event loop.
    """

    from metabrowser.builtin_plugins.github.checkout import ensure_resolved
    from metabrowser.builtin_plugins.github.pull_list_route import (
        catalog_job_key,
        served_repository,
    )
    from metabrowser.mirror_refresh import refresh_coordinator

    await ensure_resolved(app)
    repository = served_repository(app)
    if repository is None:
        return None
    coordinator = refresh_coordinator(app)
    refreshing = bool(
        coordinator is not None and coordinator.running(catalog_job_key(repository.source))
    )
    return await asyncio.to_thread(ref_pulls_of, repository, refreshing=refreshing)
