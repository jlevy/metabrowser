"""The envelope the pull routes answer, built from the cache and memory alone.

It never runs gh or Git and never waits on the network, so a page opens as fast offline
as online. Every request names its pull request by number, and a server answers for any
number of its repository, so it is the same in a one-shot command and a server. It
reports one of:

- ``absent``: nothing to show, with a ``reason``: this server serves no GitHub repository
  (``not_github``), or no usable record is cached (``not_cached``, ``schema_mismatch``,
  ``unreadable``);
- ``pending``: no record yet, and a refresh is running;
- ``current``: a record fetched within the refresh coordinator's freshness window;
- ``stale``: an older record, still shown.

``refreshing`` says whether the pull request's refresh job is running, and
``last_refresh`` how its last one ended. ``pin`` is the commit the server serves and
``pin_ref`` the ref it was resolved from; the record's ``pull.head.sha`` and
``comparison_route`` name the head the record was read at. ``image_route`` serves an image
of that comparison's head that its rendered Markdown shows, completed with ``path``
(:func:`image_route`). ``rendered_route`` answers the rendered
Markdown redline of one changed file of that comparison; a page completes it with ``file``
(:func:`rendered_route`). They differ when the pin is
another pull request or a branch, when the URL selected a commit inside the pull request,
and when a refresh found a newer head than the pin, which status reports as ``latest``
for the page to offer rather than switching under a reader.

A read never starts a fetch. Only ``POST pull-refresh`` does, and :func:`start_refresh`
holds what it starts to the rule: a request that is not a reader's own action refreshes
only a pull request with a record, and only when that record is stale and not tried within
the window. A visible cold page can request the selected fetch with a separate POST.
Idle checkout comparison preparation instead names a fresh record revision, only where a
store is already attached, and a reader's Changes request promotes that job.

Which pull requests a server has is :func:`pull_host`'s to say, and nothing else here
knows whether it is a mirror or a checkout. A checkout with no attached store answers a
record with no comparison, ``no_store``, whoever wrote it. A server with a store answers
a record written that way as ``stale``. A comparison refresh request may attach a store
to a checkout's pull records.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import threading
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Final, Literal, NotRequired, TypedDict
from urllib.parse import urlencode

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.checkout import (
    checkout_job_key,
    checkout_pulls,
    checkout_store_turn,
    comparison_preparing,
    served_checkout,
    start_pull_refresh,
)
from metabrowser.builtin_plugins.github.pull_catalog import catalog_member
from metabrowser.builtin_plugins.github.pull_core_cache import read_cached_core
from metabrowser.builtin_plugins.github.pull_cores import CoreAdmission, CoreWindow, preparation_key
from metabrowser.builtin_plugins.github.pull_freshness import (
    RecordFreshness,
    VerifiedBy,
    record_freshness,
)
from metabrowser.builtin_plugins.github.pull_labels import (
    LabelEntry,
    labels_for,
    labels_job_key,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_list_probe import checked_at
from metabrowser.builtin_plugins.github.pull_list_route import catalog_job_key
from metabrowser.builtin_plugins.github.pull_readiness import DisplayState, lifecycle, readiness
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    RecordAbsence,
    read_pull_record,
)
from metabrowser.builtin_plugins.github.pull_status import PullStatus
from metabrowser.builtin_plugins.github.pull_status_store import (
    CheckProbes,
    KeptStatus,
    kept_status,
)
from metabrowser.builtin_plugins.github.served_pull import (
    ATTENDED_PROBE_S,
    PullCorePreview,
    PullRefreshOutcome,
    ServedPull,
    ServedPulls,
    cached_comparison_record,
    probe_inputs,
    written_without_store,
)
from metabrowser.builtin_plugins.github.served_pull import record_revision as _record_revision
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER, source_pull_record
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.git.wire import is_full_revision
from metabrowser.http_caching import BUILD_TAG, build_scoped_etag, store_tag
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    PullJobStart,
    RefreshCoordinator,
    mirror_session,
    refresh_coordinator,
)
from metabrowser.source import RepositorySubject
from metabrowser.view_routes import parse_pull_number

PULL_ROUTE: Final = "/api/plugin/github/pull"
_REFRESH_FIELDS: Final = frozenset(
    {"number", "retry", "comparison", "recovery", "wait_core", "prepare_comparison", "held"}
)
NUMBER_REQUIRED: Final = '"number" is a pull-request number'

type PullState = Literal["absent", "pending", "current", "stale"]
type PullAbsence = Literal["not_github"] | RecordAbsence
type PullRefreshStart = PullJobStart | Literal["not_due", "not_cached"]


class PullRequestError(Exception):
    """A request the pull routes refuse. ``str()`` says why, and names only the request."""


class PullEnvelope(TypedDict):
    """What ``GET /api/plugin/github/pull`` returns."""

    state: PullState
    reason: PullAbsence | None
    source: str | None
    number: int
    pin: str | None
    pin_ref: str | None
    fetched_at: str | None
    verified_at: str | None
    verified_by: VerifiedBy | None
    head_moved: bool
    checks_pending: bool
    record_revision: str | None
    fresh_for_s: float
    # How often a visible page asks while it shows a record: the server then probes it
    # (:data:`~.served_pull.ATTENDED_PROBE_S`) or reads it in full when that is due, and
    # answers ``not_due`` otherwise. ``None`` with no record to probe.
    probe_every_s: float | None
    refreshing: bool
    preparing_comparison: NotRequired[Literal[True]]
    # The server has no Git store to compare in, as a checkout has none until a reader's
    # Changes asks for one, so no read brings a comparison until then: the page holds no
    # placeholder for one (mb-30dz).
    no_store: NotRequired[Literal[True]]
    last_refresh: PullRefreshOutcome | None
    comparison_route: str | None
    image_route: str | None
    rendered_route: str | None
    # The size the comparison pushes, for the page's size line (:mod:`.pull_size`).
    size_route: str | None
    record: dict[str, Any] | None
    core_preview: PullCorePreview | None
    # The repository's label set's entries for the labels the record or core names without
    # a color (:func:`.pull_labels.labels_for`), and whether the set's job runs while the
    # set does not hold one of those labels, so a page reads again soon.
    repository_labels: list[LabelEntry]
    labels_pending: bool
    # The pull request's operational status as last read (:class:`~.pull_status.PullStatus`),
    # by the page or by the Pulls tab's scan, its head's checks (:class:`~.pull_status.PullChecks`),
    # and the verdict on it (:func:`~.pull_readiness.readiness`), beside the record and never
    # in it: they change with a check, and the record does not. Each names the head it
    # describes, and ``readiness`` judges ``status`` only when that is the head of the record
    # or core shown; it is ``None`` for a closed or merged pull request, and with nothing
    # shown. ``checks`` is the list ``status`` counts, of the head shown, and ``None`` until
    # the page has read one (:func:`shown_checks`): a scan's status of a new head, or of
    # checks that moved, counts no list.
    # ``status_unavailable`` is why the last read of the status failed, when it did; what
    # an earlier read kept is still answered.
    status: dict[str, Any] | None
    readiness: dict[str, Any] | None
    checks: dict[str, Any] | None
    status_unavailable: str | None


def display_state(pull: Mapping[str, object]) -> DisplayState:
    """The state badge of *pull*, a record's or core's ``pull`` as the wire has it.

    Merged and draft come before open and closed, as GitHub's badge shows them.
    """

    return lifecycle(
        closed=pull.get("state") == "closed",
        draft=bool(pull.get("draft")),
        merged=bool(pull.get("merged")),
    )


def _shown_head(shown: object) -> str | None:
    """The head commit of *shown*, the ``pull`` the envelope shows, or ``None``."""

    if not isinstance(shown, dict):
        return None
    head = shown.get("head")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    sha = head.get("sha") if isinstance(head, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return sha if isinstance(sha, str) else None


def shown_checks(shown: object, kept: KeptStatus) -> dict[str, Any] | None:
    """The checks the envelope carries beside *shown*, as the wire has them, or ``None``.

    Only the list the kept status counts (:attr:`~.pull_status_store.KeptStatus.listed_checks`),
    and only of the head shown: checks of another head, or ones a newer status no longer
    sums to, are never served, and ``None`` says the head shown has no list yet.
    """

    checks = kept.listed_checks
    if checks is None or checks.head != _shown_head(shown):
        return None
    return checks.model_dump(mode="json")


def judged_readiness(shown: object, status: PullStatus | None) -> dict[str, Any] | None:
    """The verdict on *shown*, the ``pull`` the envelope shows, with *status*, as the wire has it.

    ``None`` with no pull request shown, or a closed or merged one.
    """

    sha = _shown_head(shown)
    if not isinstance(shown, dict) or sha is None:
        return None
    pull: dict[str, object] = shown  # pyright: ignore[reportUnknownVariableType]
    url = pull.get("html_url")
    verdict = readiness(
        state=display_state(pull),
        head=sha,
        status=status,
        html_url=url if isinstance(url, str) else None,
    )
    return None if verdict is None else verdict.model_dump(mode="json")


def _parse_stamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def pull_state(
    record: PullRecord | RecordAbsence,
    *,
    now: datetime,
    refreshing: bool = False,
    has_store: bool = True,
    freshness: RecordFreshness | None = None,
) -> tuple[PullState, RecordAbsence | None]:
    """The state a cached record (or its absence) is in at *now*.

    A record written with no store, by a checkout's server, is stale whatever its age on a
    server that *has_store*, which can give it its Files changed. Otherwise the catalog's
    *freshness* verdict decides when it has one (:mod:`.pull_freshness`), and the
    refresh coordinator's window when it has none. A ``checks`` verdict is a current
    record whose status alone is due, which the record does not hold.
    """

    if not isinstance(record, PullRecord):
        return ("pending", None) if refreshing else ("absent", record)
    if has_store and written_without_store(record):
        return "stale", None
    if freshness is not None and freshness.verdict != "unverified":
        return ("stale" if freshness.verdict == "changed" else "current"), None
    age = now - _parse_stamp(record.fetched_at)
    return ("current" if age <= timedelta(seconds=FRESHNESS_WINDOW_S) else "stale"), None


def _without_store(dumped: dict[str, Any]) -> dict[str, Any]:
    """A record as a server with no store has it: no comparison, ``no_store``.

    A checkout's server may read a record a mirror wrote, with a comparison of commits in
    that mirror's store. It has no store of its own, and it never reads the checkout's, so
    it offers no Files changed for it. A new dictionary: *dumped* is the parsed cache's.
    """

    unavailable = {**dumped.get("unavailable", {}), "comparison": "no_store"}
    return {**dumped, "comparison": None, "unavailable": unavailable}


IMAGE_ROUTE: Final = "/api/plugin/github/pull-image"
RENDERED_ROUTE: Final = "/api/plugin/github/pull-rendered-diff"
SIZE_ROUTE: Final = "/api/plugin/github/pull-size"


def image_route(number: int, base: str, head: str, *, store: str) -> str:
    """The route of the images a comparison's rendered Markdown shows, the one spelling.

    The rendered diff appends ``path``, an image's Git path at the head in its wire form
    (:mod:`.pull_rendered_diff`).
    """

    query = urlencode({"number": number, "left": base, "right": head, "store": store})
    return f"{IMAGE_ROUTE}?{query}"


def rendered_route(number: int, base: str, head: str, *, store: str) -> str:
    """The rendered Markdown redline route of one comparison.

    A page appends ``file``, the manifest ID of one changed Markdown file, and
    ``prefetch=1`` on a request it sends before the reader asks, which also starts the
    projection process.
    """

    query = urlencode({"number": number, "left": base, "right": head, "store": store})
    return f"{RENDERED_ROUTE}?{query}"


def size_route(number: int, base: str, head: str, *, store: str) -> str:
    """The route of the size a comparison pushes, measured against its merge base."""

    query = urlencode({"number": number, "left": base, "right": head, "store": store})
    return f"{SIZE_ROUTE}?{query}"


def comparison_route(record: PullRecord, *, store: str) -> str | None:
    """The diff plugin's comparison of the record's pinned endpoints, or ``None``."""

    comparison = record.comparison
    if comparison is None:
        return None
    return (
        f"/api/plugin/github/pull-comparison?number={record.number}"
        f"&left={comparison.base}&right={comparison.head}&base_policy=merge_base"
        f"&build={BUILD_TAG}&store={store}"
    )


@dataclass(frozen=True, slots=True)
class _Parsed:
    stamp: tuple[int, int, int]
    record: PullRecord
    dumped: dict[str, Any]
    revision: str


# Records parsed for this route, keyed by home, slug, and number, each kept with the
# inode, modification time, and size it was read at. A browser polls the route, and a
# record is rewritten only by atomic replacement, which changes the inode, so an
# unchanged file is answered without reading or parsing it again.
_PARSED: dict[tuple[str, str, int], _Parsed] = {}
_PARSED_LOCK: Final = threading.Lock()
MAX_PARSED_RECORDS: Final = 16


def _file_stamp(home: Path, slug: str, number: int) -> tuple[int, int, int] | None:
    try:
        status = os.lstat(home / source_pull_record(slug, number))
    except OSError:
        return None
    if not stat.S_ISREG(status.st_mode):
        return None
    return status.st_ino, status.st_mtime_ns, status.st_size


def cached_pull_record(
    home: Path, slug: str, number: int
) -> tuple[PullRecord | RecordAbsence, dict[str, Any] | None, str | None]:
    """One parsed record, its JSON and content revision, reused while the file is unchanged."""

    key = (str(home), slug, number)
    stamp = _file_stamp(home, slug, number)
    with _PARSED_LOCK:
        hit = _PARSED.get(key)
    if hit is not None and stamp is not None and hit.stamp == stamp:
        return hit.record, hit.dumped, hit.revision
    record = read_pull_record(home, slug, number)
    if not isinstance(record, PullRecord):
        return record, None, None
    dumped = record.model_dump(mode="json")
    revision = _record_revision(dumped)
    # JSON numbers above JavaScript's safe integer range still need exact part IDs.
    for kind in ("issue_comments", "reviews"):
        for item in dumped[kind]:
            if abs(item["id"]) > (1 << 53) - 1:
                item["timeline_id"] = str(item["id"])
    if stamp is not None:
        with _PARSED_LOCK:
            if key not in _PARSED and len(_PARSED) >= MAX_PARSED_RECORDS:
                _PARSED.pop(next(iter(_PARSED)))
            _PARSED[key] = _Parsed(stamp, record, dumped, revision)
    return record, dumped, revision


@dataclass(frozen=True, slots=True)
class PullHost:
    """What the pull routes need of a server that has pull requests, and no more.

    ``pulls`` is the repository's set, ``running`` says whether a number's refresh is
    running, and ``start`` starts or joins it. ``start_background`` starts a prefetch's
    refresh, which gives way to a reader's (:mod:`.pull_prefetch`), and ``job_key`` names a
    number's job in the coordinator.
    """

    pulls: ServedPulls
    running: Callable[[int], bool]
    start: Callable[[int], PullJobStart]
    start_comparison: Callable[[int], PullJobStart] | None = None
    coordinator: RefreshCoordinator | None = None
    prepare: Callable[[int, str], PullRefreshStart] | None = None
    preparing: Callable[[int], bool] | None = None
    start_background: Callable[[int], PullRefreshStart] | None = None
    job_key: Callable[[int], str] | None = None
    # The store's turn for the prefetch's own fetch, held as background work; its argument
    # is called when a reader's job starts waiting for the turn.
    store_turn: Callable[[Callable[[], object]], AbstractAsyncContextManager[None]] | None = None
    # On a mirror: told the head a record read from disk names, so a pin on that pull
    # request's head follows one another process fetched (:func:`follow_adopted_head`).
    observe_head: Callable[[int, str], None] | None = None


def pull_host(app: Any) -> PullHost | None:
    """This server's pull requests, or ``None``.

    On a mirror, those the provider keeps. On a folder, those of a served checkout's
    repository (:mod:`.checkout`), whose jobs run on the server's refresh coordinator.
    """

    session = mirror_session(app)
    if session is None:
        checkout = served_checkout(app)
        coordinator = refresh_coordinator(app)
        if checkout is None or coordinator is None:
            return None
        pulls = checkout_pulls(checkout)
        return PullHost(
            pulls,
            lambda number: coordinator.running(checkout_job_key(checkout, number)),
            partial(start_pull_refresh, coordinator, checkout),
            partial(start_pull_refresh, coordinator, checkout, comparison=True),
            coordinator,
            lambda number, revision: start_pull_refresh(
                coordinator, checkout, number, comparison=True, eager_revision=revision
            ),
            partial(comparison_preparing, coordinator, checkout),
            partial(start_pull_refresh, coordinator, checkout, background=True),
            partial(checkout_job_key, checkout),
            partial(checkout_store_turn, checkout),
        )
    served = session.pull_requests
    if not isinstance(served, ServedPulls):
        return None
    return PullHost(
        served,
        session.pull_refreshing,
        session.request_pull_refresh,
        coordinator=refresh_coordinator(app),
        start_background=partial(session.request_pull_refresh, background=True),
        job_key=served.key,
        store_turn=session.background_store_turn,
        observe_head=session.observe_pull_head,
    )


@dataclass(frozen=True, slots=True)
class PullView:
    """What the envelope needs from memory, read on the event loop that owns it.

    The refresh job changes these on the loop, so a handler reads them there, before it
    reads the record in a thread, and the answer describes one moment. ``kept`` is the
    number's state when the set holds it; otherwise its last refresh is read from disk.
    """

    number: int
    host: PullHost | None
    pin: str | None
    pin_ref: str | None
    refreshing: bool
    kept: ServedPull | None
    core_preview: PullCorePreview | None = None
    core_window: CoreWindow | None = None
    core_admission: CoreAdmission | None = None
    preparing_comparison: bool = False
    catalog_scanning: bool = False
    # When a list probe last found the catalog unchanged (:mod:`.pull_list_probe`).
    catalog_checked_at: str | None = None
    labels_running: bool = False


def catalog_scanning(host: PullHost | None) -> bool:
    """Whether the repository's catalog job is running, with no read."""

    return (
        host is not None
        and host.coordinator is not None
        and host.coordinator.running(catalog_job_key(host.pulls.source))
    )


def catalog_checked_at(host: PullHost | None) -> str | None:
    """When a list probe last found the repository's catalog unchanged, with no read."""

    return None if host is None else checked_at(host.coordinator, host.pulls.source)


def pull_view(host: PullHost | None, subject: RepositorySubject, number: int) -> PullView:
    """Pull request *number*'s in-memory state. Reads nothing, so a read adds nothing."""

    revision = subject if isinstance(subject, GitRevisionSubject) else None
    kept = None if host is None else host.pulls.held(number)
    refreshing = host is not None and host.running(number)
    live = kept.core_preview if kept is not None and refreshing else None
    adopted = kept.display_core if kept is not None and refreshing and live is None else None
    window = host.pulls.core_window if host is not None and not refreshing else None
    prepared = window.preview(number) if window is not None else None
    admission = window.admission if prepared is not None and window is not None else None
    if adopted is not None:
        live, admission = adopted
    return PullView(
        number=number,
        host=host,
        pin=None if revision is None else revision.commit_oid,
        pin_ref=None if revision is None else revision.ref,
        refreshing=refreshing,
        kept=kept,
        core_preview=live or prepared,
        core_window=window if prepared is not None else None,
        core_admission=admission,
        preparing_comparison=host is not None
        and host.preparing is not None
        and host.preparing(number),
        catalog_scanning=catalog_scanning(host),
        catalog_checked_at=catalog_checked_at(host),
        labels_running=host is not None
        and host.coordinator is not None
        and host.coordinator.running(labels_job_key(host.pulls.source)),
    )


def pull_envelope(view: PullView) -> PullEnvelope:
    """The envelope for one pull request. Blocking and bounded; run it off the loop."""

    return pull_answer(view)[0]


def pull_answer(view: PullView) -> tuple[PullEnvelope, RecordFreshness | None]:
    """The envelope, and the catalog's verdict on its record for the held state to adopt.

    Blocking and bounded; run it off the loop. Besides the record it reads the catalog's
    checkpoint and one row (:func:`~.pull_catalog.catalog_member`), and the kept status
    (:func:`~.pull_status_store.kept_status`).
    """

    host = view.host
    if host is None:
        none = PullEnvelope(
            state="absent",
            reason="not_github",
            source=None,
            number=view.number,
            pin=view.pin,
            pin_ref=view.pin_ref,
            fetched_at=None,
            verified_at=None,
            verified_by=None,
            head_moved=False,
            checks_pending=False,
            record_revision=None,
            fresh_for_s=FRESHNESS_WINDOW_S,
            probe_every_s=None,
            refreshing=False,
            last_refresh=None,
            comparison_route=None,
            image_route=None,
            rendered_route=None,
            size_route=None,
            record=None,
            core_preview=None,
            repository_labels=[],
            labels_pending=False,
            status=None,
            readiness=None,
            checks=None,
            status_unavailable=None,
        )
        return none, None
    served = host.pulls
    record, dumped, revision = cached_pull_record(served.home, served.slug, view.number)
    has_store = served.git_dir is not None
    # Through the module, so records and their age share one clock seam.
    now = pulls.utc_now()
    operational = kept_status(served.home, served.slug, view.number)
    freshness = (
        record_freshness(
            record,
            *catalog_member(served.home, served.slug, view.number),
            status=operational.status,
            now=now,
            scanning=view.catalog_scanning,
            checked_at=view.catalog_checked_at,
        )
        if isinstance(record, PullRecord)
        else None
    )
    state, absence = pull_state(
        record, now=now, refreshing=view.refreshing, has_store=has_store, freshness=freshness
    )
    verified_at = freshness.verified_at if freshness is not None else None
    verified_by: VerifiedBy | None = freshness.verified_by if freshness is not None else None
    probed = probed_at(view, record, now=now, has_store=has_store, freshness=freshness)
    if probed is not None:
        state = "current"
        if verified_at is None or probed > verified_at:
            verified_at, verified_by = probed, "probe"
    if not has_store and isinstance(record, PullRecord) and dumped is not None:
        dumped = _without_store(dumped)
        record = record.model_copy(update={"comparison": None})
    route = images = rendered = sized = None
    if isinstance(record, PullRecord) and served.git_dir is not None:
        store = store_tag(served.git_dir)
        route = comparison_route(record, store=store)
        if record.comparison is not None:
            ends = (record.number, record.comparison.base, record.comparison.head)
            images = image_route(*ends, store=store)
            rendered = rendered_route(*ends, store=store)
            sized = size_route(*ends, store=store)
    preview = view.core_preview
    if view.core_admission is not None and not view.core_admission.catalog_matches(view.number):
        preview = None
    if preview is None and not isinstance(record, PullRecord):
        preview = read_cached_core(
            served.home,
            served.slug,
            view.number,
            reader=served.observed_reader,
            reader_identity=served.core_catalog_identity,
        )
    shown = (
        dumped.get("pull")
        if isinstance(record, PullRecord) and dumped is not None
        else preview["pull"]
        if preview is not None
        else None
    )
    labels: object = shown.get("labels") if isinstance(shown, dict) else None
    listed: list[object] = labels if isinstance(labels, list) else []  # pyright: ignore[reportUnknownVariableType]
    lookup = labels_for(served.home, served.slug, served.source, listed)
    envelope = PullEnvelope(
        state=state,
        reason=absence,
        source=served.source,
        number=view.number,
        pin=view.pin,
        pin_ref=view.pin_ref,
        fetched_at=record.fetched_at if isinstance(record, PullRecord) else None,
        verified_at=verified_at,
        verified_by=verified_by,
        head_moved=freshness is not None and freshness.head_moved,
        checks_pending=freshness is not None and freshness.checks_pending,
        record_revision=revision,
        fresh_for_s=FRESHNESS_WINDOW_S,
        probe_every_s=ATTENDED_PROBE_S if isinstance(record, PullRecord) else None,
        refreshing=view.refreshing,
        last_refresh=(
            view.kept.outcome() if view.kept is not None else served.last_refresh(view.number)
        ),
        comparison_route=route,
        image_route=images,
        rendered_route=rendered,
        size_route=sized,
        record=dumped if isinstance(record, PullRecord) else None,
        core_preview=preview if not isinstance(record, PullRecord) else None,
        repository_labels=lookup.entries,
        labels_pending=view.labels_running and bool(lookup.missing),
        status=(None if operational.status is None else operational.status.model_dump(mode="json")),
        readiness=judged_readiness(shown, operational.status),
        checks=shown_checks(shown, operational),
        status_unavailable=operational.unavailable,
    )
    if view.preparing_comparison:
        envelope["preparing_comparison"] = True
    if not has_store:
        envelope["no_store"] = True
    return envelope, freshness


def probed_at(
    view: PullView,
    record: PullRecord | RecordAbsence,
    *,
    now: datetime,
    has_store: bool,
    freshness: RecordFreshness | None,
) -> str | None:
    """When a probe last found *record* unchanged, if that makes it current at *now*.

    That is a probe of this very record within a freshness window, of a record read in full
    within :data:`~.served_pull.FULL_REFRESH_S` (:meth:`.ServedPull.full_read_overdue`),
    which the catalog does not say GitHub changed since and which needs no store this
    server has. Otherwise ``None``, and the record's state is the catalog's or the
    clock's (:func:`pull_state`).

    Below the background floor (:meth:`.ServedPull.below_floor`) the overdue full read
    waits, and the probe goes on vouching: it is all that reads the record then, and a
    page asks every ``probe_every_s`` only for a record it is told is current, so one
    marked stale would be probed once a window and a change found that much later.
    """

    kept = view.kept
    if (
        kept is None
        or not isinstance(record, PullRecord)
        or kept.fetched_at != record.fetched_at
        or not kept.probe_vouches(now)
        or (kept.full_read_overdue(now) and not kept.below_floor(now))
        or (freshness is not None and freshness.verdict == "changed")
        or (has_store and written_without_store(record))
    ):
        return None
    return kept.probed_at


def record_and_freshness(
    served: ServedPulls, number: int, *, scanning: bool = False, checked_at: str | None = None
) -> tuple[PullRecord | None, RecordFreshness | None]:
    """The cached record of *number* and the catalog's verdict on it. Blocking and bounded.

    *scanning* is :func:`catalog_scanning` and *checked_at* :func:`catalog_checked_at`,
    read on the event loop before the call. The verdict reads the kept status's row too.
    """

    record, freshness, _status, _probes = held_record(
        served, number, scanning=scanning, checked_at=checked_at
    )
    return record, freshness


def held_record(
    served: ServedPulls, number: int, *, scanning: bool = False, checked_at: str | None = None
) -> tuple[PullRecord | None, RecordFreshness | None, PullStatus | None, CheckProbes | None]:
    """:func:`record_and_freshness`, and what a probe of the record compares with.

    That is the kept status of *number* and what the last probe of its head's checks saw
    (:func:`~.served_pull.probe_inputs`). Blocking and bounded: the record, a catalog row
    and the status's, and one small file.
    """

    record, _dumped, _revision = cached_pull_record(served.home, served.slug, number)
    if not isinstance(record, PullRecord):
        return None, None, None, None
    member = catalog_member(served.home, served.slug, number)
    status, probes = probe_inputs(served.published, number)
    freshness = record_freshness(
        record,
        *member,
        status=status,
        now=pulls.utc_now(),
        scanning=scanning,
        checked_at=checked_at,
    )
    return record, freshness, status, probes


def note_full_record(view: PullView) -> None:
    window = view.core_window
    if (
        view.host is not None
        and window is not None
        and view.host.pulls.core_window is window
        and window.previews is not None
    ):
        window.previews.pop(view.number, None)


def follow_adopted_head(view: PullView, envelope: PullEnvelope) -> None:
    """Tell the server the head *envelope*'s record names, when its pin is not at it.

    A pin served under this pull request's head follows the head. This server's own
    refresh sees to that when it ends; a record another process published reaches this
    one only here, where the route read it (A7 of review A on #745). Reads nothing.
    """

    host, record = view.host, envelope["record"]
    if host is None or host.observe_head is None or record is None or view.refreshing:
        return
    head = record["pull"]["head"]["sha"]
    if (
        view.pin_ref == f"refs/pull/{view.number}/head"
        and isinstance(head, str)
        and head != view.pin
    ):
        host.observe_head(view.number, head)


def core_preview_current(view: PullView, preview: PullCorePreview | None) -> bool:
    """Reject an observation revoked while the envelope was built off the loop."""
    if preview is None:
        return True
    if view.host is None:
        return False
    if preview is not view.core_preview:
        # Disk validation runs separately off the loop; this path has no mutable
        # prepared-window ownership to inspect.
        return True
    if view.core_window is not None:
        return (
            view.host.pulls.core_window is view.core_window
            and not view.host.running(view.number)
            and view.core_window.preview(view.number) is preview
        )
    kept = view.kept
    if kept is None or not view.host.running(view.number):
        return False
    if kept.core_preview is not None:
        return kept.core_preview is preview
    adopted = kept.display_core
    return adopted is not None and adopted[0] is preview and adopted[1] is view.core_admission


def cached_core_preview_current(view: PullView, preview: PullCorePreview) -> bool:
    """Revalidate only a disk-sourced preview; called off the owning event loop."""
    if view.host is None:
        return False
    cached = read_cached_core(
        view.host.pulls.home,
        view.host.pulls.slug,
        view.number,
        reader=view.host.pulls.observed_reader,
        reader_identity=view.host.pulls.core_catalog_identity,
    )
    return cached is not None and cached == preview


def record_stamp(view: PullView) -> tuple[int, int, int] | None:
    """The record file's inode, modification time in nanoseconds, and size."""

    if view.host is None:
        return None
    return _file_stamp(view.host.pulls.home, view.host.pulls.slug, view.number)


def envelope_etag(envelope: PullEnvelope, stamp: tuple[int, int, int] | None) -> str:
    """An entity tag for *envelope* that never serializes the record.

    Every field but the record and the verdict's time is in it, and so is *stamp*, the
    record file's :func:`record_stamp`: a record is replaced atomically, which changes its
    inode, so two records written within the same second of ``fetched_at`` still differ.
    Read the stamp before the envelope; a record replaced in between then gets a tag the
    next request no longer matches, and is sent again rather than taken as unchanged.

    ``verified_at`` and ``verified_by`` move with every catalog scan, once a window, and
    change nothing else a page shows, so they are left out: a ``304`` carries them in
    :data:`VERIFIED_HEADER` instead (:func:`verified_header`). What the verdict changes,
    ``state``, ``head_moved``, and ``checks_pending``, stays in.

    The status, its verdict, and the checks are in it whole, so a read that moves the
    status's head or ``observed_at`` changes the tag. The checks are at most
    ``MAX_CHECK_ITEMS``: 400 checks as this repository's CI names them took about 110 KB
    and about 1 ms to hash here, 20 to 35 a tenth of that (measured 2026-11-26).
    """

    fields: dict[str, Any] = {
        name: value
        for name, value in envelope.items()
        if name not in {"record", "core_preview", "verified_at", "verified_by"}
    }
    preview = envelope["core_preview"]
    fields["core_preview"] = (
        None if preview is None else (preview["revision"], preview["observed_at"])
    )
    fields["record_stamp"] = list(stamp) if stamp is not None else None
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"pull-{digest[:32]}")


# The verdict's time and how it was reached, ``<verified_by> <verified_at>``, on a ``200`` and
# a ``304`` alike, so a page answered ``304`` after a scan still shows when it was checked.
# `` scanning`` follows a catalog verdict while the catalog's next scan runs, so the page
# reads again soon and sees a change that scan publishes in a fast poll, not a slow one. A
# catalog vouches for at most a window and :data:`~.pull_freshness.SCAN_GRACE_S`, so the
# fast polls stop with the scan or by then. The tag leaves it out.
VERIFIED_HEADER: Final = "x-metabrowser-verified"


def verified_header(envelope: PullEnvelope, *, scanning: bool = False) -> dict[str, str]:
    """The :data:`VERIFIED_HEADER` of *envelope*, or none when it has no record."""

    by, at = envelope["verified_by"], envelope["verified_at"]
    if by is None or at is None:
        return {}
    flag = " scanning" if scanning and by == "catalog" else ""
    return {VERIFIED_HEADER: f"{by} {at}{flag}"}


def requested_number(params: Mapping[str, str]) -> int:
    """The number a ``GET`` names, or :class:`PullRequestError`. It is required."""

    number = parse_pull_number(params.get("number", ""))
    if number is None:
        raise PullRequestError(NUMBER_REQUIRED)
    return number


@dataclass(frozen=True, slots=True)
class RefreshRequest:
    """What a ``POST`` asks for.

    *retry* is a reader's own action, or the one comparison request a page on Changes
    sends by itself for a record without a store. *held* is the ``record_revision`` of
    the record the asker already has, which the answer then leaves out
    (:func:`refresh_answer_pull`).
    """

    number: int
    retry: bool
    comparison: bool = False
    recovery: tuple[str, str] | None = None
    wait_core: bool = False
    prepare_comparison: str | None = None
    held: str | None = None


def refresh_request(body: Mapping[str, object]) -> RefreshRequest:
    """What a ``POST`` body names, or :class:`PullRequestError`."""

    if set(body) - _REFRESH_FIELDS:
        raise PullRequestError(
            'a refresh request names only "number", "retry", "comparison", "recovery", '
            '"wait_core", "prepare_comparison", and "held"'
        )
    number = body.get("number")
    if (
        not isinstance(number, int)
        or isinstance(number, bool)
        or not 1 <= number <= MAX_PULL_REQUEST_NUMBER
    ):
        raise PullRequestError(NUMBER_REQUIRED)
    retry = body.get("retry", False)
    if not isinstance(retry, bool):
        raise PullRequestError('"retry" is true or false')
    comparison = body.get("comparison", False)
    if not isinstance(comparison, bool) or (comparison and not retry):
        raise PullRequestError('"comparison" is true or false and requires "retry": true')
    recovery = body.get("recovery")
    pair: tuple[str, str] | None = None
    if recovery is not None:
        if (
            comparison
            or not retry
            or not isinstance(recovery, dict)
            or set(recovery) != {"base", "head"}
        ):
            raise PullRequestError(
                '"recovery" names a displayed base and head and requires "retry": true'
            )
        base, head = recovery.get("base"), recovery.get("head")
        if (
            not isinstance(base, str)
            or not isinstance(head, str)
            or not is_full_revision(base)
            or not is_full_revision(head)
        ):
            raise PullRequestError('"recovery" requires two full commit IDs')
        pair = (base, head)
    wait_core = body.get("wait_core", False)
    if not isinstance(wait_core, bool) or (
        wait_core and (not retry or comparison or pair is not None)
    ):
        raise PullRequestError('"wait_core" is true or false and requires only "retry": true')
    preparation = None
    if "prepare_comparison" in body:
        revision = body["prepare_comparison"]
        if (
            not isinstance(revision, str)
            or len(revision) != 64
            or not is_full_revision(revision)
            or retry
            or comparison
            or pair is not None
            or wait_core
        ):
            raise PullRequestError('"prepare_comparison" is a record revision and stands alone')
        preparation = revision
    held = None
    if "held" in body:
        held = body["held"]
        if (
            not isinstance(held, str)
            or len(held) != 64
            or not is_full_revision(held)
            or preparation is not None
        ):
            raise PullRequestError('"held" is a record revision, and not for "prepare_comparison"')
    return RefreshRequest(number, retry, comparison, pair, wait_core, preparation, held)


def refresh_answer_pull(envelope: PullEnvelope, held: str | None) -> dict[str, Any]:
    """The ``pull`` a refresh answers: *envelope*, without a record the asker holds.

    When *held* is the envelope's ``record_revision``, the answer names ``record_held``
    in place of ``record``, and the asker keeps the record it has: every other field is
    sent, so the verdict, the state, and the job's outcome still arrive. Otherwise it is
    the whole envelope, as for an asker that names no *held*.

    A visible page asks every ``probe_every_s``, and nearly every answer carries a record
    it already shows. Measured 2026-11-23 on the two largest records in a local cache,
    as the median of 200 renders of the answer in ``JSONResponse``, which serializes on
    the event loop, three runs at a load average near 380:

    - a 344 KiB record: 351,924 bytes and 1.70 to 1.72 ms whole, 733 bytes and 0.006 ms
      held, so 4.2 MB a minute for one visible page became 9 KB;
    - a 290 KiB record: 296,962 bytes and 1.31 ms whole, 733 bytes and 0.006 ms held.

    The revision is the record's as cached, before a server without a store drops its
    comparison (``no_store``), so the asker also compares ``no_store`` with its own
    envelope's and reads the route again when either differs.
    """

    answer: dict[str, Any] = dict(envelope)
    if held is not None and envelope["record"] is not None and envelope["record_revision"] == held:
        del answer["record"]
        answer["record_held"] = True
    return answer


async def start_refresh(host: PullHost, ask: RefreshRequest) -> PullRefreshStart:
    if ask.prepare_comparison is not None:
        served = host.pulls

        def foreground_waiting() -> bool:
            return served.foreground_pending(host.running) or (
                host.coordinator is not None
                and host.coordinator.running(preparation_key(served.source))
            )

        publication = served.published
        # Optional work never attaches a store. The first acquisition fetches whatever the
        # checkout lacks from its origin, and every later refresh then fetches into the
        # store, so only a reader's own Changes request starts one; see :mod:`.checkout`.
        if (
            host.prepare is None
            or isinstance(publication, ListedRepository)
            or foreground_waiting()
        ):
            return "not_due"
        reader = served.observed_reader
        record = await asyncio.to_thread(
            cached_comparison_record, publication, reader, ask.number, ask.prepare_comparison
        )
        if (
            record is None
            or not written_without_store(record)
            or served.published is not publication
            or served.observed_reader != reader
            or foreground_waiting()
        ):
            return "not_due"
        return host.prepare(ask.number, ask.prepare_comparison)
    if not ask.retry and not ask.comparison:
        return await _start_refresh(host, ask)
    served = host.pulls
    served.foreground_intents += 1
    try:
        window = served.core_window
        prepared = None
        if window is None or window.previews is None:
            served.core_window = None
            coordinator = host.coordinator
            if coordinator is not None:
                job = coordinator.cancel(preparation_key(served.source))
                if job is not None:
                    await asyncio.shield(asyncio.gather(job, return_exceptions=True))
        elif ask.wait_core:
            preview = window.preview(ask.number)
            if preview is not None:
                prepared = (window, preview)
        started = await _start_refresh(host, ask, prepared)
        if started in {"started", "joined"} and window is not None and window.previews is not None:
            window.previews.pop(ask.number, None)
        return started
    finally:
        served.foreground_intents -= 1


async def _start_refresh(
    host: PullHost, ask: RefreshRequest, prepared: tuple[CoreWindow, PullCorePreview] | None = None
) -> PullRefreshStart:
    """Start the refresh *ask* names, join the one running, or say why it starts nothing.

    A request with *retry*, a reader's own action or a Changes page's one comparison
    request, always may start one. An automatic request may only for a
    pull request with a record (``not_cached`` otherwise), and only when that record is
    stale and no attempt is due to wait (``not_due`` otherwise).
    """

    queued: ServedPull | None = None
    adopt = None
    if ask.retry and not ask.comparison:
        served = await host.pulls.companion(ask.number)
        queued = served
        if ask.recovery is not None and not served.issued_comparison(ask.recovery):
            raise PullRequestError("this pull request did not issue the requested comparison")
        if not served.request_recovery(ask.recovery):
            return "too_many"
        if ask.wait_core:
            cached, _dumped, _revision = await asyncio.to_thread(
                cached_pull_record, host.pulls.home, host.pulls.slug, ask.number
            )
            if isinstance(cached, PullRecord):
                served.saw_record(cached.fetched_at, without_store=written_without_store(cached))
            else:
                served.request_core_preview()
                if (
                    cached == "not_cached"
                    and prepared is not None
                    and prepared[0].publication is served.published
                ):
                    adopt = prepared
    if ask.comparison and host.start_comparison is not None:
        return host.start_comparison(ask.number)
    # Optional comparison work on a checkout reads no metadata, so an automatic request
    # finding it is due as if nothing ran, and when due promotes the job to a metadata read.
    idle = (
        not ask.retry
        and host.preparing is not None
        and host.running(ask.number)
        and host.preparing(ask.number)
    )
    if host.running(ask.number) and not idle:
        # Only checkout jobs can be promoted from idle preparation. The other
        # hosts are already running the requested refresh.
        return host.start(ask.number) if ask.retry and host.prepare is not None else "joined"
    if not ask.retry:
        served = await host.pulls.companion(ask.number)
        if served.fetched_at is None:
            return "not_cached"
        held, freshness, status, probes = await asyncio.to_thread(
            partial(
                held_record,
                host.pulls,
                ask.number,
                scanning=catalog_scanning(host),
                checked_at=catalog_checked_at(host),
            )
        )
        if held is not None:
            served.saw_record(
                held.fetched_at, without_store=written_without_store(held), freshness=freshness
            )
        due = served.automatic_due(pulls.utc_now())
        if due == "probe" and held is not None and held.fetched_at == served.fetched_at:
            # A visible page asks every ATTENDED_PROBE_S; most asks end here, in a free
            # conditional read that finds nothing new (:meth:`ServedPull.probe`).
            try:
                await served.probe(held, status=status, probes=probes, coordinator=host.coordinator)
            except TimeoutError:
                return "not_due"
            due = served.automatic_due(pulls.utc_now())
        if due != "full":
            return "not_due"
    if adopt is not None:
        window, preview = adopt
        # This is the last worker read. Start and adoption below are synchronous.
        catalog_matches = await asyncio.to_thread(window.catalog_matches, ask.number)
        if (
            not catalog_matches
            or host.pulls.published is not window.publication
            or host.pulls.core_window is not window
            or window.preview(ask.number) is not preview
        ):
            adopt = None
    if host.running(ask.number) and not idle:
        return "joined"
    started = host.start(ask.number)
    if queued is not None:
        if started == "too_many":
            queued.discard_recovery(ask.recovery)
        elif started == "started" and adopt is not None:
            window, preview = adopt
            admission = window.admission
            if admission is not None:
                queued.display_core = (preview, admission)
    return started


def status_route(number: int) -> str:
    """Where a one-shot ``--api`` reads how a refresh ended."""

    return f"{PULL_ROUTE}?number={number}"


__all__ = [
    "IMAGE_ROUTE",
    "NUMBER_REQUIRED",
    "PULL_ROUTE",
    "VERIFIED_HEADER",
    "PullEnvelope",
    "PullHost",
    "PullRefreshStart",
    "PullRequestError",
    "PullState",
    "PullView",
    "RefreshRequest",
    "cached_pull_record",
    "catalog_checked_at",
    "catalog_scanning",
    "comparison_route",
    "display_state",
    "envelope_etag",
    "held_record",
    "image_route",
    "judged_readiness",
    "shown_checks",
    "pull_answer",
    "pull_envelope",
    "pull_host",
    "pull_state",
    "pull_view",
    "record_and_freshness",
    "refresh_answer_pull",
    "record_stamp",
    "refresh_request",
    "rendered_route",
    "size_route",
    "requested_number",
    "start_refresh",
    "status_route",
    "verified_header",
]
