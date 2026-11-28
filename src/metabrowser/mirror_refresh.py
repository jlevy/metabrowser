"""Keep the served mirror fresh in the background, and switch its pin.

A server serving a repository mirror answers every page from the mirror and never makes
a request wait on the network. Network work runs as background jobs that a request
starts or joins and then returns: the :class:`RefreshCoordinator` on the application
state keeps one job per key (a store key, or for a pull request's record the store key
and its number) so concurrent requests join the running one, and a semaphore bounds how
many run at once. A :class:`CompanionRefresh` is data a provider serves beside the
mirror, refreshed with it under its own key, and a :class:`PullRequestSet` gives one for
any pull request of the repository.
A job outlives the request that started it, and its failures become typed outcomes
rather than exceptions. A graceful shutdown cancels whatever is still running through the
application lifespan, which kills each job's Git; a Ctrl-C exits at once instead, after
:func:`metabrowser.git.process.stop_process_groups` has killed them. A server that
is killed outright cannot do either, and its Git keeps the store's fetch lock until it
exits, so nothing else writes or cleans the store under it.

:class:`MirrorSession` ties the served mirror to that coordinator and to the source
session. It answers what ``GET /api/source/status`` reports about freshness from
memory -- the tip of the pinned ref as last observed, the last fetch time and outcome,
whether a refresh is running -- so the status route runs no Git and reads no store. The
observations are taken again when a job finishes and when the pin changes, one at a
time, so a pin switch during a refresh cannot leave the other ref's tip behind. A pin on
a branch, a tag, or a pull request's head follows its ref: when an observation finds that
a fetch moved it, the server serves the new tip, and a commit opened by its ID stays. When a
refresh finds another process refreshing the store, a served mirror follows that one
and observes the store again once it ends. Switching the pin resolves a selection in
the mirror, opens the new subject, and replaces the served one under a new generation.

The two halves are two classes. :class:`StoreSession` is the store's: its fetch, its
turn, its probe, its idle timer, and its last outcome, which read no served subject.
:class:`MirrorSession` adds the pin served from the store. A folder's server keeps a
store beside its checkout (``checkout_store.py``) with a session that owns only the
revisions read from that store, so while the working tree is served it is the store's
half alone.

A mirror is fetched as often as it usefully can be, since a fetch into Metabrowser's own
store is safe to repeat and spends no rate limit. A visible page on one of the origin's
branches makes its own ask every :data:`STORE_PROBE_S` (:meth:`MirrorSession.page_ask`):
the server asks the origin where that branch is with one ``ls-remote``, outside the store
turn and the network slots, and fetches at once when it moved; the whole mirror is
fetched once it is older than the freshness window. With no page visible, a server
fetches every :data:`STORE_IDLE_REFRESH_S` (:meth:`MirrorSession.run_idle_refresh`), as
background work that gives way at the store to any job a reader waits on. A probe or a
fetch that failed is tried again only a window, or an idle interval, later.

A server opens any pull request of its repository, and attends to one: the one its URL
named, replaced whenever a pin switch serves another's head. That one counts toward the
mirror's staleness and is refreshed with it, because a page of code on a pull request's
head depends on the refresh that finds a newer head. Any other is refreshed only when a
request asks, as its own job.

This module holds no cache or Git code of its own. The CLI hands the server a
:class:`ServedMirror` implementation (``cache/served_mirror.py``) through
:func:`serve_mirror`, so a server that serves a folder never imports the cache.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections import deque
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator, Sequence
from collections.abc import Set as AbstractSet
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, Protocol, TypedDict

from metabrowser import event_log
from metabrowser.git.process import GIT_ACQUISITION_TIMEOUT_S
from metabrowser.paths_safe import register_root_callback
from metabrowser.repository_context import RepositoryContext
from metabrowser.source import (
    SourceSession,
    as_git_revision_subject,
    get_source_session,
    replace_owned_subject,
)

if TYPE_CHECKING:
    # Annotations only. Every server owns a refresh coordinator, so this module loads
    # when a folder is served too, and the revision tree source is not a folder's cost.
    from metabrowser.git.tree_source import GitRevisionSubject

log = logging.getLogger(__name__)

# How old the last fetch may be before a served mirror counts as stale: the server
# starts one refresh when it opens a stale mirror, and the browser asks for one when
# a stale page becomes visible. A refresh with nothing new is one ls-remote and one
# fetch that transfers no objects: 135-170 ms over file:// for a three-commit origin
# and for this repository (210 refs), measured on macOS with Git 2.50.1 on 2026-09-23.
# HTTPS adds its round trips and is measured with the transport in step 5 of the
# thin-mirror plan. A minute keeps a reader who moves between pages of one session
# from paying that on every open, while one who comes back later still sees a push
# from minutes ago without asking.
FRESHNESS_WINDOW_S: Final = 60.0
# Background network jobs running at once in one server, across every key. Fetches into
# the store run one at a time (:class:`StoreTurn`), so two lets a list's refresh proceed
# beside one without letting a burst of requests open unbounded connections to one host.
MAX_CONCURRENT_REFRESHES: Final = 2
# Pull requests whose refresh may be queued or running at once. Past it a request is
# refused and starts nothing, since the numbers are request text; the attended one may run
# one over. Each job takes its turn at the store alone, so they run one after another.
# Measured 2026-11-02 on eight pull requests of pallets/click, each read cold and again
# conditionally, with gh 2.98.0 and Git 2.50.1 at a load average of 10: 4.7 to 7.0 s, median
# 5.2 s, which is eight gh processes and one fetch, and a 304 takes as long as a 200. Eight
# take at most 56 s at the slowest, so the last still starts inside the freshness window of
# the request that asked for it. That wait is theirs alone: the mirror's fetch and the
# attended pull request's go ahead of them (:data:`MAX_FIRST_IN_A_ROW`), and a job that is
# only waiting holds no network slot, so a list's refresh does not wait for them at all.
MAX_PULL_JOBS: Final = 8
# Jobs that may go ahead of a waiting pull request in a row at the store. Two is one each of
# the only jobs that go first, the mirror's and the attended pull request's, which a stale
# page asks for together. So those wait for at most the job running, one other that goes
# first, and one that does not: 21 s by the times above, not the queue's 56 s. And nothing
# else waits for ever, however often those two are asked for again.
MAX_FIRST_IN_A_ROW: Final = 2
# How often a served mirror checks whether another process's refresh has ended, and for
# how long at most: that process's own fetch deadline. A check tries a lock file, so it
# is cheap; a second keeps the page's label a second behind the other process at worst.
ELSEWHERE_POLL_S: Final = 1.0
ELSEWHERE_WAIT_S: Final = GIT_ACQUISITION_TIMEOUT_S

# How often a visible page of a mirror served on one of its origin's branches asks
# whether that branch moved there: one ``ls-remote`` of the branch
# (:meth:`ServedMirror.origin_tip`), and the fetch at once when it did, so a push shows
# within seconds, where the freshness window and the page's poll made it up to 90 s. A
# probe takes no turn at the store and no network slot, since it writes nothing and ends
# in a second or two.
#
# Measured 2026-11-22 against github.com over HTTPS with Git 2.56.1, at a load average
# of 275 to 300, five runs each of ``ls-remote`` of the default branch: 0.79 to 1.65 s
# for pallets/click and 0.99 to 1.50 s for bluesky-social/social-app, whose whole
# advertisement is 12,068 refs; 0.06 to 0.07 s of CPU, 13 MB at the peak, and 57 bytes of
# answer. A refresh is two round trips where a probe is one, ``ls-remote --symref`` (0.76
# to 1.44 s) and then the fetch, which with nothing new took 0.67 to 0.93 s into a store of
# click (75 refs) and 1.06 to 1.36 s into one of social-app (2,994 refs), 0.08 s of CPU and
# 17 MB; and a refresh takes the store's turn and its fetch lock and rewrites its record,
# which a probe does not. On the stores of two real mirrors the same day, at a load
# average of 330, the fetch alone took 1.7 to 5.3 s and 0.2 to 0.6 s of CPU (the cadence
# plan, "Metabrowser's Own Stores").
#
# Five seconds is three times the slowest probe, so probes do not run into their own
# latency, and it is the interval a visible pull request is probed at (``ATTENDED_PROBE_S``
# in ``builtin_plugins/github/served_pull.py``), so a push and a pull request's change show
# equally soon. It is 720 probes an hour for a visible mirror, about 50 s of CPU. An idle
# machine was not to hand; the wall times above include the load.
#
# An origin can also not answer at all: in the same run one ``ls-remote`` of
# torvalds/linux had printed nothing after 386 s, when it was killed, and ``curl`` got no
# answer from that repository's endpoint in 15 s. So a probe runs under the first-request
# deadline (``REMOTE_PROBE_TIMEOUT_S``), and a failed one holds the next for a window.
#
# What these measurements do not cover, which the update-cadence plan keeps open as "Both
# measured again on an idle machine"
# (``docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md``): an idle
# machine; a ``file://`` origin; and a private repository, whose probe runs the provider's
# credential helper each time.
STORE_PROBE_S: Final = 5.0
# The shortest gap the server keeps between two probes of the served branch, however
# many pages ask. Below STORE_PROBE_S, so an ask that arrives a little early, as timers
# make them, still probes instead of waiting for the next one, as ``PROBE_FLOOR_S`` does
# for a pull request (``builtin_plugins/github/served_pull.py``).
STORE_PROBE_FLOOR_S: Final = 4.0
# How long the request that started a probe waits for it. Past this it answers
# ``not_due`` and the probe ends on its own, under the first-request deadline, starting
# the fetch itself if the branch moved. Three seconds is about twice the slowest probe
# measured above (1.65 s), so the request that started a probe nearly always carries its
# answer, and it is as long as a pull request's probe is waited for (``PROBE_WAIT_S``).
STORE_PROBE_WAIT_S: Final = 3.0
# How old the last fetch of a served mirror may grow while its server runs with no page
# visible. The owner's rule (2026-11-22): a store Metabrowser keeps is fetched as often as
# it usefully can be, since a fetch into it is atomic, removes no commit, and spends no
# rate limit, so the cost is process time and network alone. A visible page keeps the
# mirror inside FRESHNESS_WINDOW_S by asking; this is for the server behind a hidden tab
# or a closed window, so a page opened later starts at most this old and its first ask
# catches up.
#
# A refresh with nothing new is the two round trips measured at STORE_PROBE_S: 1.4 to 2.8 s
# and about 0.15 s of CPU against github.com, and up to 5.3 s and 0.6 s of CPU for the
# fetch on a large real store. Every five minutes that is twelve an hour for each served
# mirror: at most 8 s of CPU and about a minute of network in the hour, with no reader
# waiting on any of it, and nothing at all when the last fetch, by any process, is newer.
# The cost would allow a shorter interval; five minutes is the "every few minutes" the
# owner asked for, and the fetch a returning page's first ask starts takes a second or two.
STORE_IDLE_REFRESH_S: Final = 300.0

type StartedOrJoined = Literal["started", "joined"]
# How a visible page's own ask was answered (:meth:`MirrorSession.page_ask`): the fetch
# was ``started`` or ``joined``, a probe found the served branch where the mirror has it
# (``probed``), or nothing was due (``not_due``).
type PageAsk = Literal["started", "joined", "probed", "not_due"]
# How a request for a pull request's refresh was answered; ``"too_many"`` started nothing,
# because :data:`MAX_PULL_JOBS` were queued or running.
type PullJobStart = Literal["started", "joined", "too_many"]
# Why a pull request's refresh was asked for, which is what its job reads
# (:meth:`CompanionRefresh.refresh`). Each start or join of the job names one, and the job
# reads what all of them need, whoever started it:
#
# - ``"due"``: whatever of the record and its status is due when the job's turn comes, and
#   nothing when neither still is. The source's own refresh asks this when the data served
#   beside the mirror is stale, as a page's own commit fetch and a prefetch do.
# - ``"page"``: a visible page's automatic ask, which found a read due: as ``"due"``, and
#   the record too when its full read is (``FULL_REFRESH_S`` in
#   ``builtin_plugins/github/served_pull.py``).
# - ``"record"``: the record and its status after it, whatever is due, since the asker
#   needs what only that read brings: a reader's own action, a reader's retry of a commit
#   fetch, a commit the mirror lacks, a link into the pull request, or a comparison.
type RefreshAsk = Literal["due", "page", "record"]
# How a request for the source's refresh was answered: ``"too_many"`` started nothing, when
# only the attended pull request was stale and the queue had no room for its job.
type RefreshStart = Literal["started", "joined", "too_many"]
# How a request for the fetch a missing commit waits for was answered: the mirror's
# fetch was started or joined, or the mirror is ``"fresh"`` and none was asked for.
type CommitFetch = Literal["started", "joined", "fresh"]


@dataclass(frozen=True, slots=True)
class CommitFetchAnswer:
    """How a request for the fetch a missing commit waits for was answered.

    ``refresh`` is the mirror's fetch. ``pull_refresh`` is the attended pull request's
    refresh, the only one that brings a newer head of it, as
    :meth:`MirrorSession.request_pull_refresh` answered it, or ``None`` when none was asked
    for: no pull request is attended, or its record was fresh and the request was no retry.
    """

    refresh: CommitFetch
    pull_refresh: PullJobStart | None


class SelectionError(Exception):
    """A pin selection could not be served. ``str()`` names no path."""

    code: ClassVar[str] = "invalid_selection"
    http_status: ClassVar[int] = 400


class InvalidSelectionError(SelectionError):
    """The selection is not a ref name or commit ID Metabrowser will look up."""


class SelectionNotFoundError(SelectionError):
    """No branch, tag, or commit in the mirror matches the selection."""

    code = "selection_not_found"
    http_status = 404


class SelectionNotACommitError(SelectionError):
    """The selection names a tag or object in the mirror that is not a commit, such as a tag of a tree.

    No fetch can change what an existing name points at, so this is answered at once.
    """

    code = "not_a_commit"
    http_status = 409


class AmbiguousSelectionError(SelectionError):
    """An abbreviated commit ID matches more than one commit in the mirror."""

    code = "ambiguous_selection"
    http_status = 409


class SelectionRefMovedError(SelectionError):
    """The ref a switch by commit ID names as ``under`` is not at that commit.

    View on branch and Browse code name a pull request's head commit under its
    ``refs/pull/<n>/head``. A page drawn before the pull request moved on names an earlier
    head, which served under no ref, or another's, would open a bare commit the page called
    the pull request's head; so nothing is switched, and the page says the head moved.
    """

    code = "ref_moved"
    http_status = 409


class SelectionFetchFailedError(SelectionError):
    """The fetch a missing selection waited for did not run to the end.

    ``outcome`` is that refresh's typed outcome. Asking again starts another fetch.
    """

    code = "selection_fetch_failed"
    http_status = 502

    def __init__(self, outcome: str) -> None:
        super().__init__(
            f"the mirror could not fetch from its origin ({outcome}); ask again to try again"
        )
        self.outcome = outcome


class SelectionPendingError(SelectionError):
    """The mirror does not have the selection yet; one background fetch will say.

    ``refresh`` is ``"started"`` or ``"joined"``. Asking again after that fetch ends
    answers the switch, or :class:`SelectionNotFoundError`.
    """

    code = "selection_pending"
    http_status = 202

    def __init__(self, refresh: StartedOrJoined) -> None:
        super().__init__("the mirror is fetching from its origin; ask again when it finishes")
        self.refresh: StartedOrJoined = refresh


# ``remote`` is a checkout's remote-tracking branches; a mirror, which holds its origin's
# branches as its own, has none.
type RefKind = Literal["branch", "tag", "remote"]


class OriginProbeError(Exception):
    """The origin could not be asked where a branch is; nothing was learned or changed."""


@dataclass(frozen=True, slots=True)
class MirrorRef:
    """One branch or tag a mirror or a checkout holds, and the commit it names.

    ``name`` is the name a reader knows it by, ``ref`` the full ref a pin request names
    it with, and ``default`` marks the origin's default branch in a mirror or the
    checked-out branch in a checkout. ``notable`` gives a branch listing priority
    independently of that marker. ``committed_at`` is the commit's committer date in
    epoch seconds, ``None`` when Git printed none.
    """

    name: str
    ref: str
    commit: str
    default: bool = False
    committed_at: float | None = None
    # Only on a row of a checkout's list of its origin's branches, read from the store
    # Metabrowser keeps of that origin: where the checkout's own remote-tracking branch
    # is, when that is not ``commit`` (``_with_origin`` in ``checkout_revisions.py``).
    checkout: CheckoutOwnRef | None = None
    notable: bool = False


@dataclass(frozen=True, slots=True)
class CheckoutOwnRef:
    """Where a checkout's own remote-tracking branch is, beside its origin's branch.

    ``commit`` and ``committed_at`` are that ref's, as :class:`MirrorRef` has them, and
    both ``None`` when the checkout has no such ref: a branch the reader never fetched.
    ``GET /api/source/refs`` sends it under the same name, the TypedDict
    ``CheckoutOwnRef`` in ``source_routes.py``.
    """

    commit: str | None
    committed_at: float | None


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """How one refresh ended: a typed outcome code and when.

    ``swept`` names refs the store itself deleted before the fetch, because the checkout
    an overlay borrows from no longer holds their objects; the origin was not asked about
    them, so a served one is unobserved rather than gone from the origin.
    """

    outcome: str
    at: str
    swept: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecordedFreshness:
    """What the mirror's own record says about its last fetch and operation.

    ``record_stamp`` identifies the record file as read -- its inode and nanosecond
    modification time, both new on every atomic rewrite -- so a caller can tell a
    rewrite apart from a record written earlier in the same second; ``None`` when the
    mirror cannot say. ``shallow`` is whether the store has a shallow boundary, which for
    an overlay moves with the checkout.
    """

    last_fetch_at: str | None
    last_operation: str | None
    last_outcome: str | None
    last_outcome_at: str | None
    record_stamp: tuple[int, int] | None = None
    shallow: bool = False


@dataclass(frozen=True, slots=True)
class MirrorDisplay:
    """What a page shows of the mirror it is served from. Display text, never an input.

    ``name`` is the repository's name as a checkout of it would be called, and
    ``origin`` the address it mirrors, as given. ``location`` is where the mirror is
    kept: the bare Git repository the pages are read from. It is the one place a served
    page names a path in the cache; see :class:`metabrowser.source_routes.SourceStatus`.
    Both ``origin``, when it is a ``file://`` address, and ``location`` have the home
    directory as ``~`` when they are under it. All three are safe to print: a control
    or invisible character the origin put in its address is already replaced.
    ``borrows`` is the checkout an overlay borrows objects from, under the same exception,
    and ``None`` for a mirror that holds all its own objects.
    """

    name: str
    origin: str
    location: str
    borrows: str | None = None


class ServedMirror(Protocol):
    """The repository mirror a server serves, as this module needs it."""

    @property
    def key(self) -> str:
        """The single-flight key of this mirror's refresh: its store key."""
        ...

    @property
    def display(self) -> MirrorDisplay:
        """The mirror's name, origin, and location, as a page shows them."""
        ...

    async def open_selection(
        self, *, ref: str | None, oid: str | None, keep_refs: tuple[str, ...] = ()
    ) -> GitRevisionSubject:
        """Resolve a selection in the mirror and open it, or raise :class:`SelectionError`.

        A commit named by *oid* that is the tip of one of *keep_refs* is opened under
        the first such ref rather than under none.
        """
        ...

    async def refresh(self) -> RefreshResult:
        """Fetch from the origin. Returns a typed outcome for every failure it can name."""
        ...

    async def origin_tip(self, ref: str) -> str | None:
        """Ask the origin, fetching nothing, which commit the branch behind *ref* names.

        *ref* is the mirror's own ref for one of the origin's branches
        (:func:`probes_origin`). ``None`` is an origin that no longer has the branch.
        Writes nothing and takes no lock. Raises :class:`OriginProbeError` when the origin
        did not answer.
        """
        ...

    async def recorded_freshness(self) -> RecordedFreshness:
        """Read the mirror's record of its last fetch, off the event loop."""
        ...

    async def ref_tip(self, ref: str) -> str | None:
        """The commit *ref* names in the mirror now, or ``None`` when it is gone."""
        ...

    async def ref_tips(self, refs: Sequence[str]) -> dict[str, str]:
        """The commit each of *refs* names in the mirror now, in one read; a ref that is
        gone is left out."""
        ...

    async def default_ref(self) -> str | None:
        """The store's record of the origin's default branch, as its full ref, or ``None``."""
        ...

    async def list_refs(self, kind: RefKind, *, default_ref: str | None) -> tuple[MirrorRef, ...]:
        """Every branch, or every tag, the mirror holds that names a commit.

        *default_ref*, :meth:`default_ref` as the caller read it, is marked and lists
        with the other notable branches. Each group reads newest first, then by name.
        """
        ...

    async def refresh_running_elsewhere(self) -> bool:
        """Whether a refresh of this mirror is running now, in any process."""
        ...

    def repository_context(self, *, revision: str, branch: str | None) -> RepositoryContext | None:
        """What lets rendered links into this mirror's hosted repository open locally.

        Supplied by a provider for a repository it hosts; ``None`` otherwise.
        """
        ...


class CompanionRefresh(Protocol):
    """Data served beside the mirror that a provider keeps fresh: a pull request's record.

    It is refreshed with the mirror, under its own key in the same coordinator, and
    counts toward the mirror's staleness, so the rules that keep a served page fresh
    keep it fresh too. :meth:`refresh` names every failure as an outcome it keeps.
    """

    @property
    def key(self) -> str:
        """The single-flight key of its refresh, distinct from the mirror's."""
        ...

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        """Whether it is older than *window_s* at *now*, from memory alone."""
        ...

    async def refresh(self, asks: AbstractSet[RefreshAsk]) -> None:
        """Fetch what *asks* need; failures become outcomes rather than exceptions.

        *asks* are why its job was started or joined (:data:`RefreshAsk`), as the job's
        coordinator keeps them (:meth:`RefreshCoordinator.asks`): a live view, so an ask
        that joins while it runs is there when it looks again.
        """
        ...


class PullRequestSet(Protocol):
    """Every pull request of the served repository, as a provider keeps them fresh.

    The numbers are request text, so what it keeps in memory is bounded, and the rest is
    read from disk when asked for. Both methods that may read do so off the event loop.
    """

    def key(self, number: int) -> str:
        """The single-flight key of pull request *number*'s refresh, with no read."""
        ...

    async def companion(self, number: int) -> CompanionRefresh:
        """Pull request *number*'s refresh, kept or read from disk."""
        ...

    async def attend(self, number: int) -> CompanionRefresh:
        """That refresh, kept whatever the bound drops until another number is attended."""
        ...


class LastOutcome(TypedDict):
    operation: str
    outcome: str
    at: str


class StoreFields(TypedDict):
    """What a store's session says of the store alone (:meth:`StoreSession.store_fields`)."""

    last_fetch_at: str | None
    last_outcome: LastOutcome | None
    refreshing: bool
    refresh_quiet: bool


type SelectionState = Literal["pending", "found", "not_found", "fetch_failed", "superseded"]


@dataclass(frozen=True, slots=True)
class OpenedSelection:
    """A URL selection opened in the mirror, and the ``/view/`` address it opens at."""

    subject: GitRevisionSubject
    view_href: str


class FreshnessFields(TypedDict):
    """The freshness half of ``/api/source/status``.

    ``refreshable`` says whether the refresh and pin routes act on this server's
    subject. ``follows`` says whether the pin moves with its ref (:func:`follows_moves`):
    true for a branch, a tag, or a pull request's head, whose new tip the server serves
    itself once a fetch moves it. ``latest`` is the commit the pinned ref names in the mirror as last observed:
    equal to the pin when nothing moved, different when a refresh moved a ref the pin
    does not follow, or one it could not follow yet, and ``None`` otherwise.
    ``ref_on_origin`` tells those apart: ``False`` when the origin no longer had the ref
    at the last fetch, ``None`` when there is no ref or it has not been observed. ``pull_request`` is the attended pull request: the one the
    URL named, or whose head a pin switch last served. ``selection_state`` follows a URL
    selection the mirror did not have when serving began: ``pending`` until a fetch for it ends,
    then ``found`` (and served) or ``not_found``, or ``fetch_failed`` when that fetch
    did not run, which the next refresh retries; ``superseded`` once a pin switch
    serves something else. ``None`` when there was none. ``selection_href`` is where a
    ``found`` selection opens, with its line anchor, so a page opened while it was
    pending can go there. ``probe_every_s`` is how often a visible page of this pin makes
    its own ask (:meth:`MirrorSession.page_ask`): :data:`STORE_PROBE_S` while the pin is
    one of the origin's branches, which the server probes there, and ``None`` otherwise.
    ``refresh_quiet`` says that all that is refreshing is a fetch of the mirror no reader
    asked for, the idle one or a visible page's once a window, so a page shows and
    announces nothing for it; a reader's request that joins such a fetch ends that.
    """

    refreshable: bool
    follows: bool
    latest: str | None
    ref_on_origin: bool | None
    last_fetch_at: str | None
    last_outcome: LastOutcome | None
    refreshing: bool
    refresh_quiet: bool
    stale: bool
    probe_every_s: float | None
    pull_request: int | None
    selection_state: SelectionState | None
    selection_href: str | None


UNSERVED_FRESHNESS: Final[FreshnessFields] = {
    "refreshable": False,
    "follows": False,
    "latest": None,
    "ref_on_origin": None,
    "last_fetch_at": None,
    "last_outcome": None,
    "refreshing": False,
    "refresh_quiet": False,
    "stale": False,
    "probe_every_s": None,
    "pull_request": None,
    "selection_state": None,
    "selection_href": None,
}

# Selections a pin request found missing, remembered until the fetch they started
# ends, so the next request for one answers found or not found rather than pending
# again. Bounded because the selections are request text.
MAX_REMEMBERED_MISSES: Final = 64

type SelectionOpener = Callable[[], Awaitable[OpenedSelection | None]]


# A pull request's head as a pin names it, which makes that pull request the attended one.
_PULL_HEAD: Final = re.compile(r"refs/pull/([1-9][0-9]{0,9})/head")


def pull_head_number(ref: str | None) -> int | None:
    """The pull request whose head *ref* is, ``refs/pull/<n>/head``, or ``None`` for any other."""

    head = _PULL_HEAD.fullmatch(ref or "")
    return int(head.group(1)) if head is not None else None


# The refs a served pin follows when a fetch moves them: the origin's branches and its
# tags, where a mirror keeps them (``MIRROR_REFS`` in ``cache/resolve.py``, which this
# module does not import), and a pull request's head, ``refs/pull/<n>/head``, which that
# pull request's refresh fetches. A reader who opened a branch reads that branch, and one
# who opened a pull request reads its head, so the server serves the new tip itself
# (:meth:`MirrorSession.observe`) and the page goes with it. The owner decided the pull
# request's case on 2026-11-22 (mb-6a6w): its refresh is probed every few seconds while a
# page is visible, so a new head offered behind a button was offered seconds after every
# push of a review. A commit opened by its ID stays: it is served under no ref, or named
# by one whose tip it is, and a pin asked for by ID alone is never moved
# (``MirrorSession._by_id``).
_FOLLOWED_REF_PREFIXES: Final = ("refs/remotes/origin/", "refs/tags/")


def follows_moves(ref: str | None, prefixes: tuple[str, ...] | None = None) -> bool:
    """Whether a pin served under *ref* moves when that ref does.

    By default a mirror's: one of the origin's branches or tags, or a pull request's
    head, each of which a fetch moves. *prefixes* are the namespaces that follow where
    the pin is read from something else: a checkout names its own
    (``FOLLOWED_CHECKOUT_REFS`` in ``checkout_revisions.py``), which the reader's commit
    or fetch moves.
    """

    if ref is None:
        return False
    if prefixes is not None:
        return ref.startswith(prefixes)
    return ref.startswith(_FOLLOWED_REF_PREFIXES) or pull_head_number(ref) is not None


async def follow_served_ref(
    subject: GitRevisionSubject,
    tip: tuple[str, str | None] | None,
    *,
    follows: Callable[[str | None], bool],
    open_tip: Callable[[str], Awaitable[GitRevisionSubject]],
    on_open: Callable[[GitRevisionSubject], None] | None = None,
) -> GitRevisionSubject | None:
    """Serve the ref *subject* is served under at its new tip; the revision now served, or ``None``.

    *tip* is the ref and its commit as last observed where the subject is read from, a
    mirror's store or a checkout. A pin whose ref follows (*follows*) and was observed at
    another commit is replaced by the one *open_tip* opens for the ref, under a new
    generation. ``None`` when nothing moved, when the pin does not follow, and when the tip
    could not be opened: the pin then stays, and status reports the tip as ``latest``,
    where the page asks for the switch itself.

    The caller holds the lock every change of what is served is made under, as a switch
    does: a reader's switch that ran meanwhile is the pin now, and this follows only the
    pin it is given.

    *on_open* is told the new revision once it is opened and before it is attached, as a
    switch records what it serves before attaching it: a caller that answers for its own
    revisions by identity, as a checkout's does (``CheckoutRevisions.serves``), then
    answers for it from the moment a request can find it served.
    """

    if (
        not follows(subject.ref)
        or tip is None
        or tip[0] != subject.ref
        or tip[1] is None
        or tip[1] == subject.commit_oid
    ):
        return None
    ref = tip[0]
    try:
        moved = await open_tip(ref)
    except Exception:
        log.warning("could not follow the served ref to its new tip", exc_info=True)
        return None
    if moved.ref != ref or moved.commit_oid == subject.commit_oid:
        await moved.aclose()
        return None
    if on_open is not None:
        on_open(moved)
    await replace_owned_subject(moved)
    log.info("followed %s to %s", ref, moved.commit_oid)
    return moved


def probes_origin(ref: str | None) -> bool:
    """Whether a pin served under *ref* is probed at the origin between fetches.

    Only one of the origin's branches: a tag is not expected to move, a commit opened by
    its ID cannot, and a pull request's head is the provider's to watch.
    """

    return ref is not None and ref.startswith(PROBED_REF_PREFIX)


# The mirror's refs for its origin's branches: what the status advertises as probed, and
# what :meth:`ServedMirror.origin_tip` accepts and strips to name the branch at the
# origin, so the two cannot disagree. ``tests/test_source_refresh.py`` holds it to the
# prefix the cache fetches branches under.
PROBED_REF_PREFIX: Final = "refs/remotes/origin/"
# Refresh outcomes that say nothing against trying again at once: the fetch ran, another
# process's is running, or this one was stopped before the origin answered.
_UNHELD_OUTCOMES: Final = frozenset(
    {"succeeded", "default_branch_unknown", "refreshing_elsewhere", "cancelled"}
)

# Outcomes after which the store holds what the origin had: the fetch ran.
_FETCHED_OUTCOMES: Final = frozenset({"succeeded", "default_branch_unknown"})


@dataclass(slots=True)
class _Miss:
    """A selection the mirror did not have, and how things stood when it was found missing.

    A later count of refreshes ended means a refresh ended since, and a later count of
    fetches ran that one fetched. ``pull_jobs`` are the keys of the pull-request jobs asked
    for on its account, which may bring it; a job is waited for whichever pull request is
    attended by the time it ends. ``pull_job_refused`` is set while the last ask for the
    attended one's job found the queue full, so that job has not run.
    """

    refreshes_ended: int
    fetches_ran: int
    pull_jobs: set[str] = field(default_factory=set[str])
    pull_job_refused: bool = False


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _utc_timestamp() -> str:
    return _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return None


def followed_outcome(
    recorded: RecordedFreshness,
    *,
    baseline: RecordedFreshness | None,
    since: str,
    ended: bool,
) -> str:
    """The outcome of another process's refresh that this one waited for.

    *baseline* is the record as read just before this process tried the store and found
    it busy, at *since*. Only a record rewritten after that can be the other refresh's:
    one that was killed or cancelled writes none, and the record then still says what
    an earlier operation did. The record's file stamp tells a rewrite apart even within
    the same second; without stamps, only a record from a later second counts.
    Otherwise, or when the wait ran out before the other refresh ended, the answer is
    ``failed``, which says nothing about the origin: a selection waiting on it stays
    waiting for the next refresh.
    """

    if not ended or recorded.last_outcome is None:
        return "failed"
    stamp = recorded.record_stamp
    before = baseline.record_stamp if baseline is not None else None
    if stamp is not None and before is not None:
        rewritten = stamp != before
    else:
        at = recorded.last_outcome_at
        rewritten = at is not None and at > since
    return recorded.last_outcome if rewritten else "failed"


def _never() -> bool:
    return False


def _monotonic() -> float:
    """The clock the probe and idle intervals are kept on; a test replaces it."""

    return time.monotonic()


# How a probe of the served branch ended: the origin has it where the mirror does, it
# moved and the fetch was started (``moved``) or one that began meanwhile was joined, the
# origin did not answer, or the answer was not acted on (the pin changed meanwhile, or
# that tip's fetch was already tried).
type ProbeEnd = Literal["unchanged", "moved", "joined", "failed", "held"]
# The least the idle refresh sleeps between checks, so a record whose last fetch reads
# as due, and stays so, costs one read of a small file a second and not a busy loop.
IDLE_CHECK_FLOOR_S: Final = 1.0


@dataclass(eq=False, slots=True)
class _TurnWaiter:
    goes_first: Callable[[], bool]
    turn: asyncio.Future[None]
    background: Callable[[], bool] = _never
    preempt: Callable[[], object] | None = None
    acquisition: bool = False


class StoreTurn:
    """Whose turn it is to fetch into the store: one job at a time, the most awaited first.

    The mirror's refresh and each pull request's fetch into the store under its fetch lock.
    Within one server they take turns here first, so none finds another holding it and
    reports a refresh running elsewhere.

    The queue can hold :data:`MAX_PULL_JOBS` pull requests a reader asked for, and a page of
    served code waits on the mirror's fetch and the attended pull request's, so those go
    first. *goes_first* is asked each time a turn is given, not when a job queues, because
    the attended pull request can change while its job waits. Those that go first wait in
    the order they asked, so neither starves the other, and after
    :data:`MAX_FIRST_IN_A_ROW` of them in a row ahead of a waiting job, the oldest other job
    goes, so they starve nothing. One that went when nothing else waited is not counted.

    A background job, one whose *background* is true when a turn is given, is optional
    work a reader is not waiting for: it goes only when no other job waits, it is never
    counted against :data:`MAX_FIRST_IN_A_ROW`, and when any other job starts waiting
    while it holds the turn, its *preempt* is called, which cancels it. So a reader's job
    waits at the store for the background job to unwind, never for it to finish. A
    background job promoted to a reader's (*background* false from then on) is neither,
    and whoever promotes one that is waiting says so (:meth:`promoted`), since it arrived
    as background and stopped nothing then.
    """

    def __init__(self) -> None:
        self._waiting: list[_TurnWaiter] = []
        self._taken = False
        self._holder: _TurnWaiter | None = None
        self._first_in_a_row = 0
        self._reading_acquisition_metadata = False

    @property
    def acquiring(self) -> bool:
        """Whether the current holder is making the checkout's first Git store."""
        return self._holder is not None and self._holder.acquisition

    @contextlib.contextmanager
    def read_during_acquisition(self) -> Generator[bool]:
        """Lend the acquisition's turn to one selected read that uses no Git store.

        If Git finishes first, the next turn waits for this read. That keeps provider
        reads serialized and prevents a store attachment from invalidating its preview.
        """
        if not self.acquiring or self._reading_acquisition_metadata:
            yield False
            return
        self._reading_acquisition_metadata = True
        try:
            yield True
        finally:
            self._reading_acquisition_metadata = False
            if not self._taken:
                self._give()

    @asynccontextmanager
    async def __call__(
        self,
        goes_first: Callable[[], bool],
        *,
        background: Callable[[], bool] = _never,
        preempt: Callable[[], object] | None = None,
        acquisition: bool = False,
    ) -> AsyncGenerator[None]:
        """Hold the turn for the block, once it comes."""

        waiter = _TurnWaiter(
            goes_first, asyncio.get_running_loop().create_future(), background, preempt, acquisition
        )
        self._waiting.append(waiter)
        if not self._taken:
            self._give()
        elif not background():
            holder = self._holder
            if holder is not None and holder.preempt is not None and holder.background():
                holder.preempt()
        try:
            await waiter.turn
        except asyncio.CancelledError:
            if waiter in self._waiting:
                self._waiting.remove(waiter)
            else:
                # Its turn came just as it was cancelled, so it is this job's to pass on.
                self._pass()
            raise
        try:
            yield
        finally:
            self._pass()

    def promoted(self) -> None:
        """A waiting job stopped being background: stop a background job that holds the turn.

        The check a job's arrival runs is run again, because a job a reader's request
        joined arrived as background and stopped nothing then. Without it the reader's job
        would wait for the background one to finish, not to unwind.
        """

        holder = self._holder
        if holder is None or holder.preempt is None or not holder.background():
            return
        if any(not waiter.turn.done() and not waiter.background() for waiter in self._waiting):
            holder.preempt()

    def _pass(self) -> None:
        self._taken = False
        self._holder = None
        self._give()

    def _give(self) -> None:
        if self._reading_acquisition_metadata:
            return
        # One that was cancelled and has not run yet is still listed.
        waiting = [waiter for waiter in self._waiting if not waiter.turn.done()]
        foreground = [waiter for waiter in waiting if not waiter.background()]
        first = next((waiter for waiter in foreground if waiter.goes_first()), None)
        other = next((waiter for waiter in foreground if not waiter.goes_first()), None)
        first_is_due = other is None or self._first_in_a_row < MAX_FIRST_IN_A_ROW
        chosen = first if first is not None and first_is_due else other
        if chosen is not None:
            # Only a first that went ahead of a waiting job counts. One that went ahead of
            # nothing kept nobody waiting, and counting it would give the next contention to
            # the other.
            went_ahead = chosen is first and other is not None
            self._first_in_a_row = self._first_in_a_row + 1 if went_ahead else 0
        elif waiting:
            # Only background jobs wait; they leave the count as it was.
            chosen = waiting[0]
        else:
            return
        self._waiting.remove(chosen)
        self._taken = True
        self._holder = chosen
        chosen.turn.set_result(None)


class NetworkSlots:
    """Record waits for a shared provider slot, with bounded priority at handoff."""

    def __init__(self, value: int = 1) -> None:
        if value < 0:
            raise ValueError("the refresh concurrency limit must be nonnegative")
        self._value = value
        self._ordinary: deque[asyncio.Future[None]] = deque()
        self._selected: deque[asyncio.Future[None]] = deque()
        self._selected_ahead = 0

    def locked(self) -> bool:
        return self._value == 0

    async def acquire(self, *, selected: bool = False) -> Literal[True]:
        asked = time.perf_counter()
        await self._take(selected=selected)
        # The request report totals time queued on both automatic and explicit jobs.
        waiting = event_log.current()
        waited_ms = (time.perf_counter() - asked) * 1000
        before = waiting.attrs.get("queued_ms")
        total = (before if isinstance(before, int | float) else 0.0) + waited_ms
        waiting.set(queued_ms=round(total, 1))
        return True

    async def _take(self, *, selected: bool) -> None:
        if not self.locked():
            self._value -= 1
            return
        granted = asyncio.get_running_loop().create_future()
        waiting = self._selected if selected else self._ordinary
        waiting.append(granted)
        try:
            await granted
        except asyncio.CancelledError:
            if granted.cancelled():
                # A concurrent release can have skipped this cancelled waiter already.
                with contextlib.suppress(ValueError):
                    waiting.remove(granted)
            else:
                # Cancellation after a handoff returns the reserved slot.
                self.release()
            raise

    def release(self) -> None:
        for waiting in (self._selected, self._ordinary):
            while waiting and waiting[0].cancelled():
                waiting.popleft()
        preferred = bool(self._selected) and (
            not self._ordinary or self._selected_ahead < MAX_FIRST_IN_A_ROW
        )
        waiting = self._selected if preferred else self._ordinary
        self._selected_ahead = self._selected_ahead + 1 if preferred and self._ordinary else 0
        if waiting:
            waiting.popleft().set_result(None)
        else:
            self._value += 1

    async def __aenter__(self) -> None:
        await self.acquire()

    async def __aexit__(self, *exc: object) -> None:
        self.release()


class RefreshCoordinator:
    """Background jobs keyed by what they refresh, run at most *limit* at a time.

    A job belongs to the coordinator, not to the request that started it: the request
    returns as soon as the job is scheduled. A second start for a key whose job is
    still running joins it. A job's own failure is logged here and never reaches a
    request; callers that need an outcome record it inside the job. Why a pull request's
    job was started or joined (:data:`RefreshAsk`) is kept here with it (:meth:`asks`),
    for exactly as long as the job runs, so what it reads follows from every ask it has
    and from no ask of an earlier job or of a start that was refused.
    """

    def __init__(self, *, limit: int = MAX_CONCURRENT_REFRESHES) -> None:
        self._semaphore = NetworkSlots(limit)
        self._jobs: dict[str, asyncio.Task[None]] = {}
        self._closed = False
        # The keys of jobs a request joined after they were told to stop, each to be
        # started again once it has unwound (:meth:`start_again_when_stopped`).
        self._restarts: set[str] = set()
        # Why each running job was started or joined (:meth:`asked`), bounded by the jobs.
        self._asks: dict[str, set[RefreshAsk]] = {}

    @property
    def closed(self) -> bool:
        """Whether :meth:`aclose` has run, after which :meth:`start` starts nothing."""

        return self._closed

    def running(self, key: str) -> bool:
        job = self._jobs.get(key)
        return job is not None and not job.done()

    def job(self, key: str) -> asyncio.Task[None] | None:
        """The live job for *key*, for a caller that waits for it without owning it."""

        job = self._jobs.get(key)
        return job if job is not None and not job.done() else None

    def start(
        self, key: str, work: Callable[[], Awaitable[None]], *, network: bool = True
    ) -> StartedOrJoined:
        """Start *work* for *key*, or join the job already running for it.

        A *network* job waits for one of the limited slots. Any other does not: one that
        only watches local state, such as following another process's refresh; one that
        waits for its turn at the store first and then takes a :meth:`slot` itself, since
        a job that is only waiting must not keep the network from one that isn't; or one
        whose caller bounds its own, as a provider's short conditional read that must not
        queue behind a fetch does. The event log records each job's ``network``.
        """

        if self.running(key):
            return "joined"
        if self._closed:
            raise RuntimeError("the refresh coordinator is closed")
        # The job's span in the event log, wrapped here so its parent is the request
        # that asked for it; its start is on record from its first step, even if it
        # never ends.
        job = asyncio.create_task(
            event_log.job(
                self._run(work, network=network),
                event_log.job_name(work),
                attrs={"key": key, "network": network},
            ),
            name=f"metabrowser-refresh:{key[:24]}",
        )
        self._jobs[key] = job

        def forget(done: asyncio.Task[None]) -> None:
            if self._jobs.get(key) is done:
                del self._jobs[key]
                # The asks that joined a job told to stop are its restart's.
                if key not in self._restarts:
                    self._asks.pop(key, None)

        job.add_done_callback(forget)
        return "started"

    def asked(self, key: str, ask: RefreshAsk) -> None:
        """Note that *key*'s job, running now, was started or joined for *ask*.

        A caller notes only a start or join; nothing is noted for a job that is not
        running, so no ask outlives the job it was for and none waits for a later one.
        """

        if self.running(key):
            self._asks.setdefault(key, set()).add(ask)

    def asks(self, key: str) -> AbstractSet[RefreshAsk]:
        """Why *key*'s job was started or joined so far (:meth:`asked`), for its work to read.

        A live view: an ask that joins after the work first looks is there when it looks
        again. The asks last as long as the job, and through its restart once it was told
        to stop (:meth:`start_again_when_stopped`).
        """

        asks = self._asks.get(key)
        if asks is None:
            asks = set[RefreshAsk]()
            if self.running(key):
                self._asks[key] = asks
        return asks

    async def _run(self, work: Callable[[], Awaitable[None]], *, network: bool) -> None:
        # The slot records how long the job waited for it (NetworkSlots).
        async with self._semaphore if network else contextlib.nullcontext():
            try:
                await work()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("a background refresh failed")
                event_log.current().end("failed", error=event_log.describe_error(exc))

    def cancel(self, key: str) -> asyncio.Task[None] | None:
        """Signal a live keyed job and return it to a caller that needs to drain it."""
        job = self._jobs.get(key)
        if job is None or job.done():
            return None
        if not job.cancelling():
            job.cancel()
        return job

    def start_again_when_stopped(self, key: str, start: Callable[[], object]) -> bool:
        """Whether *key*'s job was told to stop; if it was, *start* is called once it has unwound.

        A background job is stopped with ``Task.cancel()``, which is delivered a loop step
        after it is asked for, and unwinding can take longer, since it kills the job's Git.
        A request that joins the job meanwhile is answered ``joined``, so the work it
        joined must still be done: *start* starts it again as the request's own. It is
        called once for the key, however many requests join, and after this coordinator's
        own callback, added when the job started, has forgotten the job. A request handled
        since the job ended may have started the work already, and *start* then joins it.
        At shutdown, which stops every job, nothing is started.

        The task is asked, not a flag the job keeps: a job's cancel handler can clear its
        flag before the task is done.
        """

        job = self.job(key)
        if job is None or not job.cancelling():
            return False
        if key in self._restarts:
            return True
        self._restarts.add(key)

        def restart(_stopped: asyncio.Task[None]) -> None:
            self._restarts.discard(key)
            if not self._closed:
                start()
            if not self.running(key):
                self._asks.pop(key, None)

        job.add_done_callback(restart)
        return True

    def restarting(self, key: str) -> bool:
        """Whether *key*'s stopped job is to be started again once it has unwound, for what
        the job keeps for its restart (:meth:`start_again_when_stopped`)."""

        return key in self._restarts and not self._closed

    def slot(self) -> NetworkSlots:
        """One of the limited slots, for a job started with ``network=False`` to hold.

        Each wait for it is on the record of the span that waited (:class:`NetworkSlots`).
        """

        return self._semaphore

    @asynccontextmanager
    async def selected_slot(self) -> AsyncGenerator[None]:
        """Give one selected checkout read the next available provider slot when due."""

        await self._semaphore.acquire(selected=True)
        try:
            yield
        finally:
            self._semaphore.release()

    async def drain(self, *, timeout_s: float) -> None:
        """Wait until no job is left, at most *timeout_s* in all, for a one-shot command.

        A job may start another before it ends: a list's look at the mirror starts the
        status scan, a refresh that found another process refreshing follows it, and a
        stopped job that a request joined is started again once it has unwound. Waiting only
        for the jobs running when the drain began would leave those to the close that
        follows it, which cancels them. So each round waits for every job then running, and
        the next looks again, until the coordinator holds no job at all. A job that has
        ended is held until its done callbacks have run, the first of which forgets it, so a
        job one of them starts, as a restart does, is on the books before the drain can
        find none. Every round counts against the one deadline, so a chain of jobs that
        never ends costs the command no more than one job that never ends would.
        """

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while self._jobs:
            left = deadline - loop.time()
            if left <= 0:
                return
            live = [job for job in self._jobs.values() if not job.done()]
            if live:
                await asyncio.wait(live, timeout=left)
            else:
                # Only ended jobs whose done callbacks are still to run: let them run.
                await asyncio.sleep(0)

    async def aclose(self) -> None:
        """Cancel every running job and wait for each to finish unwinding."""

        self._closed = True
        jobs = list(self._jobs.values())
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        self._jobs.clear()
        self._asks.clear()


class StoreSession:
    """One store this server keeps fresh: its fetch, its turn, its probe, and its record.

    The half of a served mirror that belongs to the store and not to what is served from
    it: the single refresh job and whose turn it is at the store (:class:`StoreTurn`),
    the probe of one of the origin's branches and the rules that hold it, the idle timer,
    and the last outcome with the store's own record of its last fetch. It reads no
    served subject, so a server can keep a store that serves nothing, as a folder's does
    beside its checkout while the working tree is served.

    :class:`MirrorSession` adds what is served from the store, through the hooks here:
    :meth:`_observe_pin`, :meth:`_probed_branch`, :meth:`_observed_tip`,
    :meth:`_fetch_asked`, :meth:`_after_fetch`, and :meth:`_beside_refreshing`.

    *store_turn* is the turn this store's fetches take, when something else in the server
    fetches into the same store and made it first; without one the session makes its own.
    """

    def __init__(
        self,
        mirror: ServedMirror,
        coordinator: RefreshCoordinator,
        *,
        window_s: float = FRESHNESS_WINDOW_S,
        follow_elsewhere: bool = False,
        store_turn: StoreTurn | None = None,
    ) -> None:
        self.mirror = mirror
        self._coordinator = coordinator
        self._window_s = window_s
        self._follow_elsewhere = follow_elsewhere
        self._recorded = RecordedFreshness(None, None, None, None)
        self._last_result: RefreshResult | None = None
        # The record as last observed when that result was set, to break a tie.
        self._recorded_with_result: RecordedFreshness | None = None
        self._last_success_at: str | None = None
        # Refs an overlay's sweep deleted and no fetch has named since. Absent from the
        # store by its own hand, not the origin's, so the status says nothing about them
        # until a fetch brings one back, which a pull request's own fetch does.
        self._swept: set[str] = set()
        self._store_turn = store_turn if store_turn is not None else StoreTurn()
        # Probes of the served branch at its origin (:meth:`page_ask`), on the monotonic
        # clock: the one running, when one last started, when one last failed, and the
        # origin's tip the last probe started a fetch for, and when.
        self._probe_task: asyncio.Task[ProbeEnd] | None = None
        self._probe_attempt: float | None = None
        self._probe_failed: float | None = None
        self._probe_fetched: tuple[str | None, float] | None = None
        # When a fetch of the mirror last ended, and when one last failed.
        self._fetch_ended: float | None = None
        self._fetch_failed: float | None = None
        # Whether the fetch running is the idle one (:meth:`run_idle_refresh`), which no
        # reader waits for until a request joins it.
        self._idle_fetch = False
        # The earliest the idle fetch may start again after a reader's job stopped one.
        self._idle_not_before: float | None = None
        # Whether a reader's request, not only a page's ask, waits for the restart of an
        # idle fetch it joined after the fetch was told to stop (:meth:`_join_running`).
        self._restart_loud = False
        # Whether the fetch running is one no reader asked for, the idle one or a visible
        # page's once a window, which status reports as ``refresh_quiet``.
        self._quiet_fetch = False

    # ── What a served pin adds ──────────────────────────────────

    async def _observe_pin(self) -> None:
        """Read again what is served from the store; a store that serves nothing reads nothing."""

    def _probed_branch(self) -> str | None:
        """The served ref that is one of the origin's branches and has been observed, or ``None``."""

        return None

    def _observed_tip(self) -> tuple[str, str | None] | None:
        """The served ref and the commit it names in the store, as last observed."""

        return None

    def _fetch_asked(self, *, companion_stale: bool) -> None:
        """A fetch of the store was started or joined on a request's account."""

    async def _after_fetch(self, outcome: str) -> None:
        """A refresh ended with *outcome*, this process's or one it followed."""

    def _beside_refreshing(self) -> bool:
        """Whether data served beside the store is refreshing, which is never quiet."""

        return False

    # ── Observation ─────────────────────────────────────────────

    async def observe(self) -> None:
        """Read the store's record again, and what is served from it (:meth:`_observe_pin`)."""

        self._recorded = await self.mirror.recorded_freshness()
        await self._observe_pin()

    def shallow(self) -> bool:
        """Whether the store had a shallow boundary when it was last observed."""

        return self._recorded.shallow

    def last_fetch_at(self) -> str | None:
        recorded = self._recorded.last_fetch_at
        if self._last_success_at is None:
            return recorded
        if recorded is None:
            return self._last_success_at
        return max(recorded, self._last_success_at)

    def is_stale(self, now: datetime | None = None) -> bool:
        """Whether the store is older than the freshness window."""

        return self._mirror_stale(now or _now_utc())

    def store_fields(self) -> StoreFields:
        """What status reports of the store alone, whatever is served: from memory."""

        return {
            "last_fetch_at": self.last_fetch_at(),
            "last_outcome": self._last_outcome(),
            "refreshing": self.refreshing(),
            "refresh_quiet": self._refresh_quiet(),
        }

    def _mirror_stale(self, now: datetime) -> bool:
        fetched = self.last_fetch_at()
        moment = _parse_timestamp(fetched) if fetched is not None else None
        if moment is None:
            return True
        return (now - moment).total_seconds() > self._window_s

    def _refresh_quiet(self) -> bool:
        """Whether all that is refreshing is a fetch of the mirror that no reader asked for.

        The follow of another process's fetch that such a fetch started is as quiet as it
        was. No quiet fetch starts while a follow runs, and a reader's request during one
        ends the quiet (:meth:`_join_running`) and starts its own job.
        """

        return self._quiet_fetch and self.refreshing() and not self._beside_refreshing()

    def refreshing(self) -> bool:
        """Whether this server is refreshing, or following another process's refresh."""

        return self._coordinator.running(self.mirror.key) or self._coordinator.running(
            self._elsewhere_key
        )

    @property
    def _elsewhere_key(self) -> str:
        return f"{self.mirror.key}:elsewhere"

    def _last_outcome(self) -> LastOutcome | None:
        """The newer of this process's last refresh and the store's recorded operation.

        Another process's refresh writes the record after this one reported that it was
        refreshing elsewhere, and a record this process wrote is no newer than its own
        result, so the later timestamp wins. Timestamps have one-second resolution, so a
        tie goes to the record only when it changed after the result was set: a record
        from before it, such as the acquisition a moment earlier, does not hide it.
        """

        recorded = self._recorded
        from_record: LastOutcome | None = None
        if (
            recorded.last_operation is not None
            and recorded.last_outcome is not None
            and recorded.last_outcome_at is not None
        ):
            from_record = {
                "operation": recorded.last_operation,
                "outcome": recorded.last_outcome,
                "at": recorded.last_outcome_at,
            }
        result = self._last_result
        if result is None:
            return from_record
        if from_record is not None and (
            from_record["at"] > result.at
            or (from_record["at"] == result.at and recorded != self._recorded_with_result)
        ):
            return from_record
        return {"operation": "refresh", "outcome": result.outcome, "at": result.at}

    def _set_result(self, result: RefreshResult) -> None:
        self._last_result = result
        self._recorded_with_result = self._recorded

    def _join_running(self, *, quiet: bool) -> None:
        """Make the mirror's fetch that is running, if one is, a request's own.

        A reader's request (*quiet* false) ends its quiet. An idle fetch stops being
        background work, and the store turn is told (:meth:`StoreTurn.promoted`), so
        background work holding the turn is stopped for it. An idle fetch that was already
        told to stop cannot be kept: cancellation is delivered a loop step after it is
        asked for, so the fetch is started again, as the request's, once the stopped one
        has unwound (:meth:`RefreshCoordinator.start_again_when_stopped`), and nothing is
        recorded as cancelled.
        """

        if not quiet:
            self._quiet_fetch = False
        # Asked before the idle flag, which the cancel handler in :meth:`_refresh_job`
        # clears before the task is done. Only the idle fetch is ever told to stop, short
        # of shutdown, where the restart starts nothing.
        if self._coordinator.start_again_when_stopped(self.mirror.key, self._restart_stopped_idle):
            if not quiet:
                self._restart_loud = True
            return
        if not self._idle_fetch:
            return
        # A reader's request, or a page's: an idle fetch it joins is waited for from now.
        self._idle_fetch = False
        self._store_turn.promoted()

    def _restart_stopped_idle(self) -> None:
        # Nothing here touches the quiet: a reader's request that waits for this restart
        # ended it as it joined, and a page's ask that starts the fetch first, in the loop
        # step between the stopped job's end and this, starts it as no quiet one
        # (:meth:`_refresh_mirror`). The idle timer starts nothing in that step either,
        # since the stopped fetch holds it a window (:meth:`_refresh_job`).
        self._restart_loud = False
        self._coordinator.start(self.mirror.key, self._refresh_job, network=False)

    def _refresh_mirror(self, *, companion_stale: bool, quiet: bool = False) -> StartedOrJoined:
        """Start or join the mirror's fetch; *quiet* is a fetch no reader asked for."""

        self._join_running(quiet=quiet)
        started = self._coordinator.start(self.mirror.key, self._refresh_job, network=False)
        if started == "started":
            # Not quiet while a reader's request waits for the restart of a stopped idle
            # fetch: a page's ask handled first starts the fetch that request then joins.
            self._quiet_fetch = quiet and not self._restart_loud
        self._fetch_asked(companion_stale=companion_stale)
        return started

    # ── A visible page's own asks ───────────────────────────────

    def _fetch_held(self, at: float) -> bool:
        """Whether a fetch failed within a freshness window of *at*, so none is retried."""

        return self._fetch_failed is not None and at - self._fetch_failed <= self._window_s

    def _probe_running(self) -> bool:
        return self._probe_task is not None and not self._probe_task.done()

    def _probe_ref(self, at: float) -> str | None:
        """The served branch, when a probe of it may start at *at*, else ``None``.

        Not for a pin that is not one of the origin's branches, nor before its tip in the
        mirror is observed; not while a refresh or another probe runs; not within a
        freshness window of a failed fetch or a failed probe, so an origin that is gone,
        or a machine that is offline, is asked once a window and not every few seconds;
        and not within :data:`STORE_PROBE_FLOOR_S` of the last probe, however many pages
        ask.
        """

        ref = self._probed_branch()
        if ref is None:
            return None
        if self.refreshing() or self._probe_running() or self._fetch_held(at):
            return None
        if self._probe_failed is not None and at - self._probe_failed <= self._window_s:
            return None
        if self._probe_attempt is not None and at - self._probe_attempt < STORE_PROBE_FLOOR_S:
            return None
        return ref

    async def page_ask(self) -> PageAsk:
        """Answer a visible page's own ask: fetch a stale mirror, or probe the served branch.

        A page sends it while it is visible, every ``probe_every_s`` of its status, so
        nothing here runs for a hidden page. The whole mirror is fetched when its last
        fetch is older than the freshness window, unless a fetch failed within one.
        Otherwise the served branch is probed at its origin when :meth:`_probe_ref` allows,
        and the fetch starts at once if it moved there. The data served beside the mirror
        is not this ask's: its own page keeps it.

        Waits for the probe at most :data:`STORE_PROBE_WAIT_S`, then answers ``not_due``
        and leaves it to end on its own; cancelling the wait never cancels the probe.
        The fetch a moved branch starts is the page's to show as a refresh; the one a stale
        mirror starts is quiet (``refresh_quiet``).
        """

        at = _monotonic()
        if self.refreshing():
            if self._coordinator.running(self.mirror.key):
                # A visible page waits on it now, so it gives way to nothing; it stays quiet.
                self._join_running(quiet=True)
            return "joined"
        if self._mirror_stale(_now_utc()) and not self._fetch_held(at):
            # Nobody asked for this one, so status reports it as quiet.
            return self._refresh_mirror(companion_stale=False, quiet=True)
        ref = self._probe_ref(at)
        if ref is None:
            return "not_due"
        task = self._probe_task = asyncio.ensure_future(self._probe(ref, at))
        try:
            end = await asyncio.wait_for(asyncio.shield(task), STORE_PROBE_WAIT_S)
        except TimeoutError:
            return "not_due"
        if end == "unchanged":
            return "probed"
        if end == "moved":
            return "started"
        return "joined" if end == "joined" else "not_due"

    async def _probe(self, ref: str, at: float) -> ProbeEnd:
        """Ask the origin where *ref*'s branch is, and fetch at once if not where the mirror has it.

        Outside the store turn and the network slots: it writes nothing and a probe queued
        behind a fetch would defeat its purpose. A tip a probe already started a fetch for
        starts no second one within a freshness window once that fetch ran to the end, so
        an origin whose fetch does not bring what its ``ls-remote`` names cannot make every
        probe a fetch. A fetch that did not run, or one that was only joined, holds nothing.
        """

        self._probe_attempt = at
        try:
            tip = await self.mirror.origin_tip(ref)
        except Exception:
            # Nothing waits on a probe but the page's freshness, so any failure only holds
            # the next one for a window.
            log.debug("could not probe %s at the origin", ref, exc_info=True)
            # From when it failed, not when it began: one that ran to its deadline would
            # otherwise use up half the hold before it was set.
            self._probe_failed = _monotonic()
            return "failed"
        self._probe_failed = None
        held = self._observed_tip()
        if held is None or held[0] != ref:
            # The pin moved to another ref while the origin was asked.
            return "held"
        if tip == held[1]:
            return "unchanged"
        ended = _monotonic()
        asked = self._probe_fetched
        if (asked is not None and asked[0] == tip and ended - asked[1] <= self._window_s) or (
            self._fetch_held(ended)
        ):
            return "held"
        log.info("the origin moved %s; fetching", ref)
        try:
            started = self._refresh_mirror(companion_stale=False)
        except RuntimeError:
            # The server is shutting down and starts no more jobs.
            return "held"
        if started == "joined":
            # A fetch that began while the origin was asked may have read it before the
            # push, so it says nothing about this tip: the next probe may fetch for it.
            return "joined"
        # Held only while that fetch runs and after it brought what the origin had
        # (:meth:`_refresh_job` forgets it otherwise).
        self._probe_fetched = (tip, ended)
        return "moved"

    async def stop_probe(self) -> None:
        """Cancel a probe still running, which kills its Git, and wait for it to unwind."""

        task = self._probe_task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    # ── The idle refresh ────────────────────────────────────────

    def _idle_due_in(self, at: float) -> float:
        """Seconds from *at* until the idle fetch is due; zero or less when it is.

        Due once the last fetch, this process's or another's as the store's record has it,
        is older than :data:`STORE_IDLE_REFRESH_S`, and no fetch of this process ended
        within that long either, so one that failed is tried again only then. An idle
        fetch a reader's job stopped is tried again a freshness window later.
        """

        waits = [0.0]
        fetched = self.last_fetch_at()
        moment = _parse_timestamp(fetched) if fetched is not None else None
        if moment is not None:
            waits.append(STORE_IDLE_REFRESH_S - (_now_utc() - moment).total_seconds())
        if self._fetch_ended is not None:
            waits.append(STORE_IDLE_REFRESH_S - (at - self._fetch_ended))
        if self._idle_not_before is not None:
            waits.append(self._idle_not_before - at)
        return max(waits)

    async def run_idle_refresh(self) -> None:
        """Keep the served mirror at most :data:`STORE_IDLE_REFRESH_S` old; runs until cancelled.

        The one timer a server runs for a mirror no page is looking at. A visible page's
        asks keep the mirror newer than this, so the timer finds nothing due while one is
        open. When the fetch is due, the store's record is read again first, so another
        process's fetch is followed, and the served branch with it, rather than repeated.
        """

        while True:
            await asyncio.sleep(max(self._idle_due_in(_monotonic()), IDLE_CHECK_FLOOR_S))
            try:
                if self.refreshing():
                    continue
                await self.observe()
                if self._idle_due_in(_monotonic()) <= 0 and not self.refreshing():
                    self.request_idle_refresh()
            except Exception:
                log.warning("the idle refresh could not check the served mirror", exc_info=True)
                # As after a fetch that failed: nothing again until the interval has passed.
                self._fetch_ended = _monotonic()

    def request_idle_refresh(self) -> StartedOrJoined:
        """Start the fetch no reader waits for, or join the one running.

        Background work at the store (:class:`StoreTurn`): it goes only when no other job
        waits, takes no network slot, and is cancelled when a reader's job starts waiting,
        so nothing a reader asked for waits for it to finish. A reader's request that
        joins it makes it the reader's from then on.
        """

        if self._coordinator.running(self.mirror.key):
            return "joined"
        self._idle_fetch = True
        self._quiet_fetch = True
        return self._coordinator.start(self.mirror.key, self._refresh_job, network=False)

    def background_store_turn(
        self, preempt: Callable[[], object]
    ) -> contextlib.AbstractAsyncContextManager[None]:
        """The store's turn for background work outside a pull request's job, the
        prefetch's fetch of many heads: it goes when no other job waits, and *preempt* is
        called when one starts waiting (:class:`StoreTurn`)."""

        return self._store_turn(lambda: False, background=lambda: True, preempt=preempt)

    async def _refresh_job(self) -> None:
        baseline: RecordedFreshness | None = None
        span = event_log.current()

        def idle() -> bool:
            return self._idle_fetch

        try:
            # The idle fetch is background work: it goes when nothing else waits at the
            # store, holds no network slot, and is cancelled when a reader's job starts
            # waiting. A reader's or a page's fetch goes first, as a page of code waits on it.
            async with (
                self._store_turn(
                    lambda: not idle(),
                    background=idle,
                    preempt=partial(self._coordinator.cancel, self.mirror.key),
                ),
                contextlib.nullcontext() if idle() else self._coordinator.slot(),
            ):
                # The record just before this attempt, to tell whether another process's
                # refresh this one may follow rewrote it. Read here so the job has its place
                # in the queue from the moment it was asked for, and the record is not one
                # from before a long wait.
                if self._follow_elsewhere:
                    baseline = await self._read_baseline()
                started = _monotonic()
                try:
                    result = await self.mirror.refresh()
                finally:
                    span.set(refresh_duration_ms=round((_monotonic() - started) * 1000))
        except asyncio.CancelledError:
            cancelled = RefreshResult("cancelled", _utc_timestamp())
            span.set(refresh_outcome=cancelled.outcome, refresh_finished_at=cancelled.at)
            self._probe_fetched = None
            if idle():
                # Stopped to let a reader's job go, or by shutdown: nobody asked for it, so
                # status reports no refresh of theirs as cancelled. A request that joined
                # it since it was told to stop has its fetch started again
                # (:meth:`_join_running`).
                self._idle_fetch = False
                self._idle_not_before = _monotonic() + self._window_s
            else:
                self._fetch_ended = _monotonic()
                self._set_result(cancelled)
            raise
        except Exception as exc:
            log.exception("refreshing the served mirror failed")
            result = RefreshResult("failed", _utc_timestamp())
            span.set(error=event_log.describe_error(exc))
        span.set(refresh_outcome=result.outcome, refresh_finished_at=result.at)
        if result.outcome not in _UNHELD_OUTCOMES:
            span.note_failure(result.outcome)
        self._idle_fetch = False
        self._fetch_ended = _monotonic()
        self._fetch_failed = None if result.outcome in _UNHELD_OUTCOMES else self._fetch_ended
        if result.outcome not in _FETCHED_OUTCOMES:
            # The fetch a probe started did not run, so it holds no probe of that tip.
            self._probe_fetched = None
        self._swept.update(result.swept)
        self._set_result(result)
        if result.outcome in _FETCHED_OUTCOMES:
            self._last_success_at = result.at
        # Another process's refresh is the fetch a waiting selection needs; follow it.
        following = result.outcome == "refreshing_elsewhere" and self._follow_elsewhere
        if not following:
            await self._after_fetch(result.outcome)
        try:
            await self.observe()
        except Exception:
            # The fetch already ended; only the report of it is behind.
            log.warning("could not observe the mirror after a refresh", exc_info=True)
        if following:
            self._coordinator.start(
                self._elsewhere_key, partial(self._follow, result, baseline), network=False
            )

    async def _read_baseline(self) -> RecordedFreshness | None:
        try:
            return await self.mirror.recorded_freshness()
        except Exception:
            log.debug("could not read the mirror's record before a refresh", exc_info=True)
            return None

    async def _follow(self, busy: RefreshResult, baseline: RecordedFreshness | None) -> None:
        """Wait for another process's refresh to end, then observe the store again.

        Without this, a server that found the store busy would report the old tip and
        fetch time until its own next refresh. Once the other refresh has ended, *busy*
        is no longer true, so it stops being this process's last outcome; the record
        then reports what the other refresh wrote, or what was there before when it
        wrote nothing.
        """

        waited = 0.0
        ended = False
        while waited < ELSEWHERE_WAIT_S:
            await asyncio.sleep(ELSEWHERE_POLL_S)
            waited += ELSEWHERE_POLL_S
            if not await self.mirror.refresh_running_elsewhere():
                ended = True
                break
        try:
            await self.observe()
        except Exception:
            log.warning("could not observe the mirror after another refresh", exc_info=True)
        await self._after_fetch(
            followed_outcome(self._recorded, baseline=baseline, since=busy.at, ended=ended)
        )
        if ended and self._last_result is busy:
            self._last_result = None


class MirrorSession(StoreSession):
    """The served mirror: a :class:`StoreSession` and the pin served from its store.

    *owns* says which served revisions are this store's. A mirror's server serves nothing
    else, so every revision is. A folder's server also serves its working tree and its
    checkout's own revisions, which this session then leaves alone: it follows, probes,
    and reports only a revision read from its own store.
    """

    def __init__(
        self,
        mirror: ServedMirror,
        coordinator: RefreshCoordinator,
        *,
        window_s: float = FRESHNESS_WINDOW_S,
        follow_elsewhere: bool = False,
        pending_selection: SelectionOpener | None = None,
        fetch_on_miss: bool = False,
        pull_requests: PullRequestSet | None = None,
        store_turn: StoreTurn | None = None,
        owns: Callable[[GitRevisionSubject], bool] | None = None,
    ) -> None:
        super().__init__(
            mirror,
            coordinator,
            window_s=window_s,
            follow_elsewhere=follow_elsewhere,
            store_turn=store_turn,
        )
        self._owns = owns
        self.pull_requests = pull_requests
        # The attended pull request and its refresh; see :meth:`attend`.
        self._pull_request: int | None = None
        self.companion: CompanionRefresh | None = None
        self._fetch_on_miss = fetch_on_miss
        self._pending_selection = pending_selection
        self._selection_state: SelectionState | None = (
            "pending" if pending_selection is not None else None
        )
        self._selection_href: str | None = None
        # Fetches that ran to the end, and the outcome of the last refresh that ended.
        self._fetches_ran = 0
        self._last_fetch_outcome = "succeeded"
        # Refresh jobs that have ended, and for each missing selection the count when it
        # was found missing: a later count means a fetch ran since.
        self._refreshes_ended = 0
        self._misses: dict[tuple[str | None, str | None], _Miss] = {}
        self._tip: tuple[str, str | None] | None = None
        # The ref last served, kept while a commit pinned by ID is served under none.
        self._last_ref: str | None = None
        # Whether the served pin was asked for by commit ID alone. The mirror may name it
        # by a ref whose tip it is, a ref kept from before or a pull request's head, for
        # the selector, but the reader opened a commit, so it does not follow that ref
        # (:meth:`_follows`) and attends no pull request. A request that names the ref, by
        # name or as ``under``, follows it. The owner decided this (mb-cww9).
        self._by_id = False
        # The pull request head last observed for, on a record another process published
        # (:meth:`observe_pull_head`), so each such record starts one observation.
        self._head_observed: tuple[int, str] | None = None
        self._pin_lock = asyncio.Lock()
        # The keys of the pull-request jobs started, some of which may have ended.
        self._pull_jobs: set[str] = set()
        # The keys of background pull-request jobs not yet promoted; each removes its own.
        self._background_pulls: set[str] = set()

    def pin_switch(self) -> asyncio.Lock:
        """The lock every change of the served pin is made under, this session's own
        switch and its follow of a moved branch alike.

        A folder's server also switches between its checkout's revisions and its
        working tree. It holds this while it does, so a follow that was opening a
        branch's new tip cannot attach it over what the reader just chose.
        """

        return self._pin_lock

    def owns(self, subject: GitRevisionSubject) -> bool:
        """Whether *subject* is a revision read from this session's store."""

        return self._owns is None or self._owns(subject)

    def served(self) -> GitRevisionSubject | None:
        """The revision served from this session's store now, or ``None``."""

        subject = _served_revision()
        if subject is None or not self.owns(subject):
            return None
        return subject

    # ── The attended pull request ───────────────────────────────

    async def attend(self, number: int) -> None:
        """Make pull request *number* the one this session attends to.

        Its refresh is what :meth:`is_stale`, :meth:`request_refresh`,
        :meth:`request_commit_fetch`, and a pin the mirror lacks use, and status and
        :meth:`_refs_to_keep` report its number.
        """

        companion = self.companion
        if self.pull_requests is not None:
            companion = await self.pull_requests.attend(number)
        # Both at once, after the read: nothing sees one's number with another's staleness.
        self._pull_request, self.companion = number, companion

    # ── Observation ─────────────────────────────────────────────

    async def _observe_pin(self) -> None:
        """Read the pinned ref's tip again, and follow the ref.

        A pin on a branch, a tag, or a pull request's head (:func:`follows_moves`) whose
        ref a fetch moved, by a push or a force-push, is replaced by the ref's new tip
        under a new generation, so the server never serves a ref behind where the mirror
        has it. Any other pin stays, and status reports the ref's new tip as ``latest``.
        """

        await self._observe_tip()
        await self._follow_ref()

    def _probed_branch(self) -> str | None:
        subject = self.served()
        if subject is None or not probes_origin(subject.ref):
            return None
        ref = subject.ref
        assert ref is not None
        # Not before its tip in the mirror is observed.
        return ref if self._tip is not None and self._tip[0] == ref else None

    def _observed_tip(self) -> tuple[str, str | None] | None:
        return self._tip

    def _fetch_asked(self, *, companion_stale: bool) -> None:
        if self._pending_selection is not None:
            self._selection_state = "pending"
        if companion_stale:
            self.request_companion_refresh("due")

    def _beside_refreshing(self) -> bool:
        return self.companion_refreshing()

    def _follows(self, subject: GitRevisionSubject) -> bool:
        """Whether the served pin moves with its ref: a ref that follows, asked for by name."""

        return follows_moves(subject.ref) and not self._by_id

    def observe_pull_head(self, number: int, head: str) -> None:
        """A record read from disk names *head* for pull request *number*; follow it.

        This server's own pull job observes the mirror when it ends. A record another
        process published was fetched into the same store by that process, and nothing
        here observed it, so a pin on that pull request's head stayed on the earlier one
        until this server's next job of any kind. One observation is started for each
        such head, off the request that read the record; it finds the ref where the other
        process left it and follows. A pin that does not follow, or is at *head*, asks
        for nothing.
        """

        subject = self.served()
        if (
            subject is None
            or subject.ref != f"refs/pull/{number}/head"
            or subject.commit_oid == head
            or not self._follows(subject)
            or self._head_observed == (number, head)
            or self.pull_refreshing(number)
        ):
            return
        self._head_observed = (number, head)
        try:
            self._coordinator.start(f"{self.mirror.key}:observe", self.observe, network=False)
        except RuntimeError:
            log.debug("not observing an adopted head: the server is closing")

    async def _follow_ref(self) -> None:
        # Under the pin lock, as a switch is: a reader's switch that ran meanwhile is the
        # pin now, and this follows only the pin it finds.
        async with self._pin_lock:
            subject = self.served()
            # A pin asked for by its ID alone never moves, whatever ref names it.
            if subject is None or not self._follows(subject):
                return
            moved = await follow_served_ref(
                subject,
                self._tip,
                follows=follows_moves,
                open_tip=lambda ref: self.mirror.open_selection(ref=ref, oid=None),
            )
            if moved is None:
                return
            assert moved.ref is not None
            self._tip = (moved.ref, moved.commit_oid)
            if self._selection_state == "found":
                # The URL's address was served on the commit before; a page that follows
                # stays where its reader is rather than going back to it.
                self._selection_state = "superseded"

    async def _observe_tip(self) -> None:
        # One observation or switch at a time: a refresh that ends while a switch is
        # resolving observes the new pin's ref after it, never the old one over it.
        async with self._pin_lock:
            subject = self.served()
            if subject is None or subject.ref is None:
                self._tip = None
                return
            tip = await self.mirror.ref_tip(subject.ref)
            if tip is not None:
                self._swept.discard(subject.ref)
            # A ref the store swept is unobserved, never reported as gone from the origin.
            self._tip = None if tip is None and subject.ref in self._swept else (subject.ref, tip)

    def is_stale(self, now: datetime | None = None) -> bool:
        """Whether the mirror, or the data served beside it, is older than the window."""

        moment_now = now or _now_utc()
        return self._companion_stale(moment_now) or self._mirror_stale(moment_now)

    def _companion_stale(self, now: datetime) -> bool:
        return self.companion is not None and self.companion.is_stale(now, window_s=self._window_s)

    def freshness_fields(self, subject: GitRevisionSubject) -> FreshnessFields:
        """The freshness half of the status envelope, from memory alone."""

        latest: str | None = None
        on_origin: bool | None = None
        if self._tip is not None and subject.ref is not None and self._tip[0] == subject.ref:
            latest = self._tip[1]
            on_origin = latest is not None
        return {
            "refreshable": True,
            "follows": self._follows(subject),
            "latest": latest,
            "ref_on_origin": on_origin,
            "last_fetch_at": self.last_fetch_at(),
            "last_outcome": self._last_outcome(),
            "refreshing": self.refreshing() or self.companion_refreshing(),
            "refresh_quiet": self._refresh_quiet(),
            "stale": self.is_stale(),
            "probe_every_s": STORE_PROBE_S if probes_origin(subject.ref) else None,
            "pull_request": self._pull_request,
            "selection_state": self._selection_state,
            "selection_href": self._selection_href if self._selection_state == "found" else None,
        }

    def unpinned_fields(self) -> FreshnessFields:
        """The freshness half of the status envelope while nothing of this store is served.

        A folder's page on its working tree, or on one of its checkout's own revisions:
        the store of its origin is refreshable and has a last fetch, and no pin follows
        or is probed.
        """

        return {
            "refreshable": True,
            "follows": False,
            "latest": None,
            "ref_on_origin": None,
            "last_fetch_at": self.last_fetch_at(),
            "last_outcome": self._last_outcome(),
            "refreshing": self.refreshing(),
            "refresh_quiet": self._refresh_quiet(),
            "stale": self._mirror_stale(_now_utc()),
            "probe_every_s": None,
            "pull_request": None,
            "selection_state": None,
            "selection_href": None,
        }

    # ── Refresh ─────────────────────────────────────────────────

    def request_refresh(self, *, for_selection: bool = False) -> RefreshStart:
        """Start a background refresh of the mirror, or join the one running.

        A URL selection still waiting, as after a fetch that failed, waits for this one.
        The data served beside the mirror is refreshed as its own job when it is stale,
        and in a server, when only it is stale, only it is refreshed, which a full queue
        can refuse (``"too_many"``). *for_selection* is the fetch a pin the mirror lacks
        waits for: the mirror's alone.
        """

        now = _now_utc()
        companion_stale = not for_selection and self._companion_stale(now)
        # Only a server skips a fresh mirror; a one-shot command asked for its refresh.
        skip_mirror = self._fetch_on_miss and self._pending_selection is None
        if companion_stale and skip_mirror and not self._mirror_stale(now):
            return self.request_companion_refresh("due") or "joined"
        return self._refresh_mirror(companion_stale=companion_stale)

    def request_commit_fetch(self, *, retry: bool) -> CommitFetchAnswer:
        """Ask for the fetch a commit the mirror lacks waits for.

        It is the fetch a pin by commit ID waits for: the mirror's own, of branches and
        tags, whatever the state of the data served beside it, and that data's refresh
        as well, since a pull request's head arrives only through it. A fetch of the
        mirror that is already running is joined.

        A page asks for this by itself when it opens a commit's address, and a link in
        served content can send a reader to any address, so that request fetches only
        what is older than :data:`FRESHNESS_WINDOW_S`: ``"fresh"`` says the mirror was
        fetched inside the window and no fetch of it was started. *retry* is a reader's
        own click, and always fetches, the pull request's record among it. The answer says
        how the pull request's refresh was answered too, since a full queue can refuse it
        while the mirror is fetched.
        """

        now = _now_utc()
        pull_refresh: PullJobStart | None = None
        if retry or self._companion_stale(now):
            pull_refresh = self.request_companion_refresh("record" if retry else "due")
        if retry or self._mirror_stale(now) or self._coordinator.running(self.mirror.key):
            return CommitFetchAnswer(self._refresh_mirror(companion_stale=False), pull_refresh)
        return CommitFetchAnswer("fresh", pull_refresh)

    def request_companion_refresh(self, ask: RefreshAsk) -> PullJobStart | None:
        """Start or join the attended pull request's refresh for *ask*, if there is one."""

        if self.companion is None or self._pull_request is None:
            return None
        return self.request_pull_refresh(self._pull_request, ask)

    def companion_refreshing(self) -> bool:
        return self.companion is not None and self._coordinator.running(self.companion.key)

    def request_pull_refresh(
        self, number: int, ask: RefreshAsk, *, background: bool = False
    ) -> PullJobStart:
        """Start or join the refresh of pull request *number* for *ask*, whichever it is.

        *ask* is why (:data:`RefreshAsk`), which the job is told whoever started it
        (:meth:`RefreshCoordinator.asked`); a start refused ``too_many`` notes none.

        One that is not running starts only while fewer than :data:`MAX_PULL_JOBS` are
        queued or running; the mirror's own fetch and a list's do not count. The attended
        one may run one over, so a queue of other pull requests does not leave a page of
        code on a pull request's head behind its refresh. It is one over and not one per
        attended switch: while a job of an earlier attended number holds that place, the
        new number is refused like any other until a job ends.

        A *background* job, a prefetch's, counts toward neither bound, takes no network
        slot, and gives way at the store turn (:class:`StoreTurn`). A reader's request that
        joins one promotes it: from then on it is the reader's, and counts. One that joins
        after the job was told to stop has its job started again once that one has unwound
        (:meth:`RefreshCoordinator.start_again_when_stopped`), so ``joined`` is never an
        answer for work that is then dropped.
        """

        pulls = self.pull_requests
        assert pulls is not None
        key = pulls.key(number)
        if background:
            if self._coordinator.running(key):
                answer: PullJobStart = "joined"
            else:
                self._background_pulls.add(key)
                answer = self._coordinator.start(
                    key, partial(self._pull_job, number), network=False
                )
        else:
            answer = self._readers_pull(number, key, ask, bounded=True)
        if answer != "too_many":
            self._coordinator.asked(key, ask)
        return answer

    def _readers_pull(
        self, number: int, key: str, ask: RefreshAsk, *, bounded: bool
    ) -> PullJobStart:
        """A reader's start of pull request *number*'s job, or their join of the one running.

        A job joined counts among the reader's jobs from then on, in the place it takes now.
        Only a background job is told to stop, short of shutdown, and one that was cannot
        be kept: this runs again, not *bounded*, once it has unwound, and starts the
        reader's job or joins one started since.
        """

        if self._coordinator.running(key):
            self._pull_jobs.add(key)
            restart = partial(self._readers_pull, number, key, ask, bounded=False)
            if self._coordinator.start_again_when_stopped(key, restart):
                return "joined"
            if key in self._background_pulls:
                self._background_pulls.discard(key)
                self._store_turn.promoted()
            return "joined"
        if bounded:
            self._pull_jobs = {job for job in self._pull_jobs if self._coordinator.running(job)}
            bound = MAX_PULL_JOBS + 1 if number == self._pull_request else MAX_PULL_JOBS
            if len(self._pull_jobs) >= bound:
                return "too_many"
        self._pull_jobs.add(key)
        return self._coordinator.start(key, partial(self._pull_job, number), network=False)

    def pull_refreshing(self, number: int) -> bool:
        """Whether the refresh of pull request *number* is running, with no read."""

        pulls = self.pull_requests
        return pulls is not None and self._coordinator.running(pulls.key(number))

    async def _pull_job(self, number: int) -> None:
        pulls = self.pull_requests
        assert pulls is not None
        key = pulls.key(number)

        def background() -> bool:
            return key in self._background_pulls

        try:
            # A background job takes no network slot; one promoted while it waited takes one
            # as any reader's does, since the slot is asked for once the turn has come.
            async with (
                self._store_turn(
                    lambda: number == self._pull_request,
                    background=background,
                    preempt=partial(self._coordinator.cancel, key),
                ),
                contextlib.nullcontext() if background() else self._coordinator.slot(),
            ):
                # Asked for here, not when the job was started: a job waiting its turn
                # holds nothing the set's bound could drop.
                companion = await pulls.companion(number)
                await companion.refresh(self._coordinator.asks(key))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("refreshing the data served beside the mirror failed")
        finally:
            self._background_pulls.discard(key)
        try:
            # Its fetch moves the pull request's head, which a pin served under it follows.
            await self.observe()
        except Exception:
            log.warning("could not observe the mirror after a refresh", exc_info=True)

    async def _after_fetch(self, outcome: str) -> None:
        """Serve a waiting URL selection if the fetch brought it, and count the fetch.

        A fetch that did not run (*outcome* is not a fetched one) says nothing about the
        selection, so it stays waiting as ``fetch_failed`` for the next refresh.
        """

        ran = outcome in _FETCHED_OUTCOMES
        try:
            if ran:
                await self._open_pending_selection()
            elif self._pending_selection is not None:
                self._selection_state = "fetch_failed"
        except Exception:
            self._selection_state = "not_found"
            log.warning("could not open the requested selection after a refresh", exc_info=True)
        finally:
            self._fetches_ran += int(ran)
            self._last_fetch_outcome = outcome
            self._refreshes_ended += 1

    async def _open_pending_selection(self) -> None:
        """After the fetch a URL selection waited for: serve it, or say it is not there.

        The opener is taken under the pin lock, so a pin switch that ran while the fetch
        did, and cleared it, is never undone here.
        """

        async with self._pin_lock:
            opener, self._pending_selection = self._pending_selection, None
            if opener is None:
                return
            opened = await opener()
            if opened is None:
                self._selection_state = "not_found"
                return
            subject = opened.subject
            await replace_owned_subject(subject)
            self._tip = (subject.ref, subject.commit_oid) if subject.ref is not None else None
            self._by_id = False
            self._selection_state = "found"
            self._selection_href = opened.view_href

    def start_pending_selection(self) -> None:
        """Fetch once for a URL selection the mirror did not have when serving began."""

        if self._pending_selection is not None:
            self.request_refresh()

    # ── Pin switching ───────────────────────────────────────────

    async def switch_pin(
        self, *, ref: str | None, oid: str | None, under: str | None = None
    ) -> tuple[bool, SourceSession]:
        """Serve the commit a selection names; ``False`` when it is already served.

        *under* is a ref that a commit named by *oid* is served under, ahead of
        :meth:`_refs_to_keep`: View on branch names the pull request's head, so of two
        pull requests that share a head, each opens as itself. When *under* is not at that
        commit, nothing is switched and :class:`SelectionRefMovedError` is raised.
        Raises :class:`SelectionError` for a selection the mirror cannot serve. In a
        server that fetches on demand, one the mirror does not have starts one
        background fetch and raises :class:`SelectionPendingError`; asked again after
        that fetch ends, it is served or :class:`SelectionNotFoundError`. A one-shot
        command reads the mirror as it is and answers not found at once. Switches are
        serialized, so two concurrent requests end with one of them served.
        """

        async with self._pin_lock:
            kept = self._refs_to_keep()
            if under is not None:
                kept = tuple(dict.fromkeys((under, *kept)))
            try:
                subject = await self.mirror.open_selection(ref=ref, oid=oid, keep_refs=kept)
            except SelectionNotFoundError as exc:
                if not self._fetch_on_miss:
                    raise
                raise self._missing((ref, oid), exc) from None
            self._misses.pop((ref, oid), None)
            if under is not None and subject.ref != under:
                await subject.aclose()
                raise SelectionRefMovedError(f"{under} is no longer at that commit")
            if self._selection_state is not None:
                # The reader chose a pin, even the one served: a URL selection still
                # waiting must not replace it when its fetch ends, and a found one no
                # longer describes what the reader asked for.
                self._pending_selection = None
                self._selection_state = "superseded"
            # A commit asked for by its ID stays put, whatever ref the mirror names it by.
            by_id = oid is not None and under is None
            current = self.served()
            if (
                current is not None
                and current.commit_oid == subject.commit_oid
                and current.ref == subject.ref
            ):
                await subject.aclose()
                if self._by_id and not by_id:
                    # The commit served by its ID, asked for now by the ref it is the tip
                    # of: the same pin, which follows that ref from here.
                    self._by_id = False
                    await self._attend_named(subject.ref)
                return False, get_source_session()
            session = await replace_owned_subject(subject)
            if subject.ref is not None:
                # The ref was just resolved in the mirror, so the pin is its tip.
                self._tip = (subject.ref, subject.commit_oid)
            else:
                self._tip = None
            self._by_id = by_id
            if not by_id:
                await self._attend_named(subject.ref)
            return True, session

    async def _attend_named(self, ref: str | None) -> None:
        """Attend the pull request whose head a request named, as *ref*, if it is one.

        Only a request that names the head attends it: a commit asked for by its ID that
        happens to head a pull request the reader never opened attends nothing, so
        nothing probes that pull request for them.
        """

        number = pull_head_number(ref)
        if number is not None:
            await self.attend(number)

    def _refs_to_keep(self) -> tuple[str, ...]:
        """The refs a commit pinned by ID is opened under when it is their tip.

        View file on a commit's diff switches by commit ID, to the commit and back: without
        this the way back would leave the server on no ref, the selector reading
        "Commit: …" where it read the branch or the pull request, and freshness no
        longer saying when the ref moves on. The pin is still the commit asked for by its
        ID, so it does not follow the ref (:attr:`_by_id`); the row offers the ref's new
        tip instead. The ref last served comes first, then the attended pull request's
        head, GitHub's own ref for it.
        """

        current = self.served()
        if current is not None and current.ref is not None:
            self._last_ref = current.ref
        pull_head = (
            f"refs/pull/{self._pull_request}/head" if self._pull_request is not None else None
        )
        return tuple(dict.fromkeys(ref for ref in (self._last_ref, pull_head) if ref is not None))

    def _missing(
        self, key: tuple[str | None, str | None], not_found: SelectionNotFoundError
    ) -> SelectionError:
        """Pending while the fetch for *key* is still to run or running, then not found."""

        seen = self._misses.get(key)
        if (
            seen is not None
            and not seen.pull_job_refused
            and seen.refreshes_ended < self._refreshes_ended
            and not self.refreshing()
            and not any(self._coordinator.running(job) for job in seen.pull_jobs)
        ):
            del self._misses[key]
            # Not found only if a fetch ran to the end since the miss, not merely ended.
            if self._fetches_ran == seen.fetches_ran:
                return SelectionFetchFailedError(self._last_fetch_outcome)
            return not_found
        if seen is None:
            if len(self._misses) >= MAX_REMEMBERED_MISSES:
                self._misses.pop(next(iter(self._misses)))
            seen = self._misses[key] = _Miss(self._refreshes_ended, self._fetches_ran)
        # While the pull request's job is refused, a fetch of the mirror that ran since the
        # miss has brought all a fetch of it can, so only that job is asked for again.
        mirror_done = seen.pull_job_refused and seen.fetches_ran < self._fetches_ran
        started = "joined" if mirror_done else self._refresh_mirror(companion_stale=False)
        # A commit the mirror lacks may be a newer one of the attended pull request, which
        # only that refresh fetches; a branch or tag never is. Another number may be attended
        # by the time its job ends, so the miss remembers the job. One a full queue refused
        # has not run, so the miss waits for an ask that finds it room.
        if key[1] is not None and self.companion is not None:
            asked = self.request_companion_refresh("record")
            seen.pull_job_refused = asked == "too_many"
            if not seen.pull_job_refused:
                seen.pull_jobs.add(self.companion.key)
            if mirror_done and asked == "started":
                started = "started"
        return SelectionPendingError(started)


def _served_revision() -> GitRevisionSubject | None:
    return as_git_revision_subject(get_source_session().subject)


# ── Configuration and lifespan ──────────────────────────────────


@dataclass(frozen=True, slots=True)
class _ServedMirrorConfig:
    mirror: ServedMirror
    serving: bool
    pull_request: int | None
    pending_selection: SelectionOpener | None
    pull_requests: PullRequestSet | None


_served_mirror: _ServedMirrorConfig | None = None


def serve_mirror(
    mirror: ServedMirror | None,
    *,
    serving: bool = False,
    pull_request: int | None = None,
    pending_selection: SelectionOpener | None = None,
    pull_requests: PullRequestSet | None = None,
) -> None:
    """Tell the next application lifespan which mirror it serves, or that it serves none.

    *serving* is serve mode: the lifespan starts one background refresh when it opens a
    mirror whose last fetch is older than :data:`FRESHNESS_WINDOW_S`, a refresh that
    finds another process refreshing follows it until it ends, and a pin request for a
    ref or commit the mirror lacks fetches once. One-shot ``--show`` and ``--api`` pass
    none of it, so they never start work the command did not ask for, and a one-shot
    refresh ends when its own attempt does. *pull_request* is the number the URL named,
    which the session attends to first. *pending_selection* opens a URL selection the mirror did not have yet: in serve mode
    the lifespan starts one refresh for it, a one-shot command waits for the refresh it
    asks for, and the pin switches to it if that fetch brings it.
    *pull_requests* is what a provider keeps for the repository's pull requests, any of
    which a request can open.
    """

    global _served_mirror
    _served_mirror = (
        None
        if mirror is None
        else _ServedMirrorConfig(mirror, serving, pull_request, pending_selection, pull_requests)
    )


def _forget_served_mirror() -> None:
    # Choosing a filesystem root is choosing to serve it.
    serve_mirror(None)


register_root_callback(_forget_served_mirror)


def mirror_session(app: Any) -> MirrorSession | None:
    """The served mirror session on *app*, when the served subject has one."""

    session = getattr(app.state, "source_mirror", None)
    return session if isinstance(session, MirrorSession) else None


def refresh_coordinator(app: Any) -> RefreshCoordinator | None:
    coordinator = getattr(app.state, "refresh_jobs", None)
    return coordinator if isinstance(coordinator, RefreshCoordinator) else None


@asynccontextmanager
async def lifespan_refresh(app: Any) -> AsyncGenerator[None]:
    """Own the refresh coordinator and, when a mirror is served, its session.

    Entered after the served subject is attached. A failure to observe the mirror's
    freshness is logged and leaves it unknown; it never fails startup. At exit every
    background job is cancelled and awaited.
    """

    coordinator = RefreshCoordinator()
    app.state.refresh_jobs = coordinator
    app.state.source_mirror = None
    config = _served_mirror
    idle: asyncio.Task[None] | None = None
    try:
        if config is not None and _served_revision() is not None:
            session = MirrorSession(
                config.mirror,
                coordinator,
                follow_elsewhere=config.serving,
                pending_selection=config.pending_selection,
                fetch_on_miss=config.serving,
                pull_requests=config.pull_requests,
            )
            if config.pull_request is not None:
                await session.attend(config.pull_request)
            try:
                await session.observe()
            except Exception:
                log.warning("could not read the served mirror's freshness", exc_info=True)
            app.state.source_mirror = session
            # A one-shot command fetches for a waiting selection only when it asks for a
            # refresh; a server fetches for it at once.
            if config.pending_selection is not None and config.serving:
                session.start_pending_selection()
            elif config.serving and session.is_stale():
                session.request_refresh()
            if config.serving:
                # A one-shot command fetches only what it asks for; a server keeps its
                # mirror from growing old while no page is visible.
                idle = asyncio.create_task(
                    session.run_idle_refresh(), name="metabrowser-idle-refresh"
                )
        yield
    finally:
        served = mirror_session(app)
        app.state.source_mirror = None
        if idle is not None:
            idle.cancel()
            await asyncio.gather(idle, return_exceptions=True)
        if served is not None:
            await served.stop_probe()
        await coordinator.aclose()


async def drain_refreshes(app: Any, *, timeout_s: float) -> None:
    """Let a one-shot command finish the work its own request started, and every job that
    work starts in turn, within *timeout_s* in all (:meth:`RefreshCoordinator.drain`)."""

    coordinator = refresh_coordinator(app)
    if coordinator is not None:
        await coordinator.drain(timeout_s=timeout_s)


__all__ = [
    "FRESHNESS_WINDOW_S",
    "MAX_CONCURRENT_REFRESHES",
    "MAX_FIRST_IN_A_ROW",
    "MAX_PULL_JOBS",
    "STORE_IDLE_REFRESH_S",
    "STORE_PROBE_FLOOR_S",
    "STORE_PROBE_S",
    "STORE_PROBE_WAIT_S",
    "UNSERVED_FRESHNESS",
    "AmbiguousSelectionError",
    "CheckoutOwnRef",
    "CommitFetch",
    "CommitFetchAnswer",
    "CompanionRefresh",
    "FreshnessFields",
    "InvalidSelectionError",
    "LastOutcome",
    "MirrorDisplay",
    "MirrorRef",
    "MirrorSession",
    "NetworkSlots",
    "OpenedSelection",
    "OriginProbeError",
    "PROBED_REF_PREFIX",
    "PageAsk",
    "PullJobStart",
    "PullRequestSet",
    "RecordedFreshness",
    "RefKind",
    "RefreshAsk",
    "RefreshCoordinator",
    "RefreshResult",
    "RefreshStart",
    "SelectionError",
    "SelectionFetchFailedError",
    "SelectionNotACommitError",
    "SelectionNotFoundError",
    "SelectionPendingError",
    "SelectionRefMovedError",
    "SelectionState",
    "ServedMirror",
    "StoreFields",
    "StoreSession",
    "StoreTurn",
    "drain_refreshes",
    "follow_served_ref",
    "followed_outcome",
    "follows_moves",
    "lifespan_refresh",
    "mirror_session",
    "probes_origin",
    "pull_head_number",
    "refresh_coordinator",
    "serve_mirror",
]
