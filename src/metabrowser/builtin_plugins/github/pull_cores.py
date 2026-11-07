"""Catalog-admitted core batches, backed by durable lightweight private entries."""

from __future__ import annotations

import asyncio
import os
import re
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.gh import GhError, gh_graphql
from metabrowser.builtin_plugins.github.gh_lists import READ_FAILURES, as_dict
from metabrowser.builtin_plugins.github.pull_catalog import (
    MAX_CATALOG_MEMBERS,
    CatalogMember,
    CatalogState,
    catalog_members,
    read_catalog,
)
from metabrowser.builtin_plugins.github.pull_core_cache import (
    read_cached_core,
    read_core_failure,
    write_cached_cores,
    write_core_failure,
)
from metabrowser.builtin_plugins.github.pull_list import (
    ListedRepository,
    parse_stamp,
    rate_limit_holds,
    read_list_refresh,
)
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.builtin_plugins.github.served_pull import PullCorePreview, make_core_preview
from metabrowser.cache.locks import run_lock_section
from metabrowser.cache.paths import (
    MAX_PULL_REQUEST_NUMBER,
    PULL_LIST_NAMES,
    PullListName,
    source_pull_record,
)
from metabrowser.home import PrivateStorageError, open_private_file
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S, RefreshCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from metabrowser.builtin_plugins.github.served_pull import ServedPulls
    from metabrowser.cache.acquire import PublishedSource

_TOKEN = re.compile(r"[a-zA-Z0-9_-]{1,64}")
# Do not evict a live entry: token churn across many rows could then spend it again.
_MAX_CORE_ATTEMPTS: Final = 256
type CoreAttempt = tuple[str, str, str, str, int, CatalogMember]
type Preparation = Literal[
    "started", "joined", "ready", "released", "not_owner", "busy", "failed", "held"
]


@dataclass(frozen=True, slots=True)
class CoreRequest:
    state: PullListName
    owner: str
    generation: str
    numbers: tuple[int, ...]

    def owns(self, other: CoreRequest) -> bool:
        return (self.state, self.owner, self.generation) == (
            other.state,
            other.owner,
            other.generation,
        )


def core_request(body: Mapping[str, object]) -> CoreRequest:
    state = body.get("state")
    window = body.get("window")
    numbers = body.get("numbers")
    if set(body) != {"state", "window", "numbers"} or state not in PULL_LIST_NAMES:
        raise ValueError('expected "state", "window", and "numbers"')
    if not isinstance(window, dict) or set(window) != {"id", "generation"}:
        raise ValueError('"window" requires "id" and "generation"')
    owner, generation = window["id"], window["generation"]
    if (
        not isinstance(owner, str)
        or _TOKEN.fullmatch(owner) is None
        or not isinstance(generation, str)
        or not 1 <= len(generation) <= 96
    ):
        raise ValueError("invalid preparation window")
    if (
        not isinstance(numbers, list)
        or len(numbers) > MAX_CATALOG_MEMBERS
        or any(type(n) is not int or not 1 <= n <= MAX_PULL_REQUEST_NUMBER for n in numbers)
        or len(set(numbers)) != len(numbers)
    ):
        raise ValueError("expected at most eight distinct pull request numbers")
    return CoreRequest(state, owner, generation, tuple(numbers))


def _batch_query(count: int) -> str:
    # Only the count changes the fixed selection. Numbers travel as typed variables.
    variables = ",".join(f"$n{i}:Int!" for i in range(count))
    aliases = "\n".join(
        f"    p{i}:pullRequest(number:$n{i}) {{{pulls._CORE_FIELDS}\n    }}" for i in range(count)
    )
    return (
        f"query VisiblePullCores($owner:String!,$name:String!,{variables}) {{\n"
        "  viewer { login }\n"
        "  repository(owner:$owner,name:$name) {\n"
        "    id nameWithOwner\n"
        f"{aliases}\n  }}\n}}"
    )


@dataclass(frozen=True, slots=True)
class CoreAdmission:
    """The catalog proof shared by ready and adopted display observations."""

    publication: PublishedSource | ListedRepository
    source: str
    state: PullListName
    epoch: str
    reader: str
    repository_id: str
    members: tuple[tuple[int, CatalogMember], ...]

    def matching_members(
        self, number: int | None = None
    ) -> tuple[CatalogState | None, tuple[int, ...]]:
        """Recheck each requested member in the same catalog, even if pagination shifted."""
        expected = {
            member_number: member
            for member_number, member in self.members
            if number is None or member_number == number
        }
        if not expected:
            return None, ()
        now, members = catalog_members(
            self.publication.home, self.publication.slug, self.state, tuple(expected)
        )
        if now is None or not self.matches_identity(now):
            return None, ()
        return now, tuple(n for n, member in expected.items() if members.get(n) == member)

    def matches_identity(self, catalog: CatalogState) -> bool:
        return (
            catalog.source == self.source
            and catalog.reader == self.reader
            and catalog.repository_id == self.repository_id
            and catalog.epoch == self.epoch
        )

    def catalog_matches(self, number: int) -> bool:
        _, matched = self.matching_members(number)
        return bool(matched)


@dataclass(frozen=True, slots=True)
class PreparedCore:
    preview: PullCorePreview


@dataclass(eq=False, slots=True)
class CoreWindow:
    ask: CoreRequest
    coordinator: RefreshCoordinator
    key: str
    publication: PublishedSource | ListedRepository
    source: str
    admission: CoreAdmission | None = None
    previews: dict[int, PreparedCore] | None = None
    checking_replacement: bool = False
    failure: PullRefreshStamp | None = None

    def prepared(self, number: int) -> PreparedCore | None:
        return self.previews.get(number) if self.previews is not None else None

    def preview(self, number: int) -> PullCorePreview | None:
        entry = self.prepared(number)
        return entry.preview if entry is not None else None

    def catalog_matches(self, number: int) -> bool:
        return self.admission is not None and self.admission.catalog_matches(number)

    def availability(self) -> tuple[str | None, tuple[int, ...]]:
        proof = self.admission
        if proof is None:
            return None, ()
        catalog, matched = proof.matching_members()
        if catalog is None or not matched:
            return None, ()
        numbers = tuple(number for number in matched if _record_missing(self, number))
        return catalog.generation(self.ask.state), numbers

    def cancel(self) -> asyncio.Task[None] | None:
        return self.coordinator.cancel(self.key)


def _record_missing(window: CoreWindow, number: int) -> bool:
    return _record_path_missing(window.publication.home, window.publication.slug, number)


def _record_path_missing(home: Path, slug: str, number: int) -> bool:
    """Admit only a missing private entry, without reading a record's contents."""
    try:
        fd = open_private_file(
            home,
            source_pull_record(slug, number),
            os.O_RDONLY | os.O_NONBLOCK,
            shared="refuse",
        )
    except FileNotFoundError:
        return True
    except (PrivateStorageError, OSError):
        return False
    os.close(fd)
    return False


def _eligible(window: CoreWindow) -> tuple[CatalogState | None, dict[int, CatalogMember]]:
    home, slug, source = window.publication.home, window.publication.slug, window.source
    ask = window.ask
    catalog, members = catalog_members(home, slug, ask.state, ask.numbers)
    stamp = read_list_refresh(home, slug, "all")
    if (
        catalog is None
        or catalog.source != source
        or catalog.generation(ask.state) != ask.generation
        or members.keys() != set(ask.numbers)
        or (
            stamp is not None
            and stamp.reader in {None, catalog.reader}
            and rate_limit_holds(stamp, now=pulls.utc_now())
        )
    ):
        return None, {}
    return catalog, {n: members[n] for n in ask.numbers if _record_missing(window, n)}


def cached_batch(
    pulls_set: ServedPulls, ask: CoreRequest
) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """Classify an exact catalog batch using local files only, before provider admission."""

    catalog, members = catalog_members(pulls_set.home, pulls_set.slug, ask.state, ask.numbers)
    if (
        catalog is None
        or catalog.source != pulls_set.source
        or catalog.generation(ask.state) != ask.generation
        or (pulls_set.observed_reader is not None and catalog.reader != pulls_set.observed_reader)
        or members.keys() != set(ask.numbers)
    ):
        return None
    ready: list[int] = []
    skipped: list[int] = []
    for number in ask.numbers:
        if not _record_path_missing(pulls_set.home, pulls_set.slug, number):
            skipped.append(number)
        elif read_cached_core(pulls_set.home, pulls_set.slug, number, fresh_only=True) is not None:
            ready.append(number)
    return tuple(ready), tuple(skipped)


def _cached_previews(
    window: CoreWindow, members: dict[int, CatalogMember]
) -> dict[int, PreparedCore]:
    return {
        number: PreparedCore(preview)
        for number in members
        if (
            preview := read_cached_core(
                window.publication.home, window.publication.slug, number, fresh_only=True
            )
        )
        is not None
    }


def _failure_held(pulls_set: ServedPulls) -> bool:
    failure = pulls_set.core_failure
    if failure is None:
        return False
    now = pulls.utc_now()
    if failure.outcome == "rate_limited" and failure.reset_at is not None:
        return now < parse_stamp(failure.reset_at)
    return now < parse_stamp(failure.at) + timedelta(seconds=FRESHNESS_WINDOW_S)


def _attemptable(
    pulls_set: ServedPulls,
    catalog: CatalogState,
    admitted: dict[int, CatalogMember],
    running: Callable[[int], bool],
) -> dict[int, CoreAttempt]:
    """Check a per-source cooldown for this exact catalog row, regardless of its owner."""
    recent = pulls_set.core_attempts
    now = time.monotonic()
    while recent:
        oldest = next(iter(recent))
        if recent[oldest] > now:
            break
        del recent[oldest]
    remaining = _MAX_CORE_ATTEMPTS - len(recent)
    identity = catalog.source, catalog.repository_id, catalog.reader, catalog.epoch
    allowed: dict[int, CoreAttempt] = {}
    for number, member in admitted.items():
        if len(allowed) >= remaining:
            break
        key = (*identity, number, member)
        if key not in recent and not running(number):
            allowed[number] = key
    return allowed


async def _prepare(
    pulls_set: ServedPulls,
    window: CoreWindow,
    running: Callable[[int], bool],
    eligible: tuple[CatalogState, dict[int, CatalogMember]] | None = None,
    overlap: dict[int, tuple[CatalogMember, PreparedCore]] | None = None,
) -> None:
    carried = overlap or {}
    publication = window.publication

    def owns() -> bool:
        return pulls_set.core_window is window and pulls_set.published is publication

    catalog: CatalogState | None = None
    try:
        catalog, admitted = (
            await asyncio.to_thread(_eligible, window) if eligible is None else eligible
        )
        slot = window.coordinator.slot()
        if not owns() or catalog is None or pulls_set.foreground_pending(running) or slot.locked():
            return
        disk = await asyncio.to_thread(_cached_previews, window, admitted)
        if not owns():
            return
        carried = {**carried, **{n: (admitted[n], entry) for n, entry in disk.items()}}
        remaining = {number: member for number, member in admitted.items() if number not in carried}
        attempts = _attemptable(pulls_set, catalog, remaining, running)
        if not attempts:
            window.previews = {number: entry for number, (_member, entry) in carried.items()}
            return
        numbers = tuple(attempts)
        window.admission = CoreAdmission(
            publication,
            window.source,
            window.ask.state,
            catalog.epoch,
            catalog.reader,
            catalog.repository_id,
            tuple((number, admitted[number]) for number in numbers)
            + tuple((number, member) for number, (member, _entry) in carried.items()),
        )
        owner, repo = pulls._owner_and_repo(publication)
        variables: dict[str, str | int] = {"owner": owner, "name": repo}
        variables.update({f"n{i}": number for i, number in enumerate(numbers)})
        # No await separates the locked check from acquiring the free permit.
        async with slot:
            retry_at = time.monotonic() + FRESHNESS_WINDOW_S
            pulls_set.core_attempts.update(dict.fromkeys(attempts.values(), retry_at))
            data = await gh_graphql(_batch_query(len(numbers)), variables, now=pulls.utc_now())
        if not owns():
            return
        observed_at = pulls.utc_now()
        repository = as_dict(data["repository"])
        login = as_dict(data["viewer"])["login"]
        name = repository["nameWithOwner"]
        if isinstance(login, str):
            pulls_set.observe_reader(publication, f"gh:{login}")
        if (
            not isinstance(login, str)
            or catalog.reader != f"gh:{login}"
            or repository["id"] != catalog.repository_id
            or not isinstance(name, str)
            or name.casefold() != f"{owner}/{repo}".casefold()
        ):
            return
        models = {
            number: pulls._graph_pull(repository[f"p{i}"], number)
            for i, number in enumerate(numbers)
        }
        _, still_missing = await asyncio.to_thread(window.availability)
        if not owns():
            return
        ready: dict[int, PreparedCore] = {}
        for number in still_missing:
            if running(number):
                continue
            previous = carried.get(number)
            if previous is not None:
                _, entry = previous
                ready[number] = entry
                continue
            model = models[number]
            if parse_stamp(model.updated_at) >= parse_stamp(admitted[number].updated_at):
                ready[number] = PreparedCore(
                    make_core_preview(
                        window.source, catalog.reader, model, observed_at, "not_started"
                    ),
                )
        published = await run_lock_section(
            partial(
                write_cached_cores,
                publication.home,
                publication.slug,
                catalog,
                admitted,
                {number: models[number] for number in ready if number in models},
                observed_at,
            )
        )
        if owns():
            window.previews = {
                **{number: entry for number, entry in ready.items() if number not in models},
                **{number: PreparedCore(preview) for number, preview in published.items()},
            }
            # A durable cache entry now supplies the duplicate-admission proof. Free
            # transient attempt slots so a successful pass has no coverage ceiling.
            for number, attempt in attempts.items():
                if number in published:
                    pulls_set.core_attempts.pop(attempt, None)
            pulls_set.core_failure = None
    except GhError as exc:
        if owns():
            from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
            from metabrowser.builtin_plugins.github.pull_list_refresh import _rate_limit_retry_at

            reset_at = exc.reset_at
            if exc.state == "rate_limited" and reset_at is None:
                reset_at = _rate_limit_retry_at(pulls.utc_now(), pulls_set.core_failure)
            window.failure = PullRefreshStamp(
                outcome=exc.state,
                message=str(exc)[:1000],
                at=utc_stamp(pulls.utc_now()),
                reset_at=reset_at,
                reader=catalog.reader if catalog is not None else None,
            )
            pulls_set.core_failure = window.failure
            if reset_at is not None:
                pulls_set.core_hold_until = parse_stamp(reset_at)
            if catalog is not None:
                with suppress(OSError, PrivateStorageError):
                    await run_lock_section(
                        partial(
                            write_core_failure,
                            publication.home,
                            publication.slug,
                            catalog,
                            window.failure,
                        )
                    )
    except (OSError, PrivateStorageError, *READ_FAILURES, ValueError) as exc:
        if owns():
            from metabrowser.builtin_plugins.github.gh_lists import utc_stamp

            window.failure = PullRefreshStamp(
                outcome="cache_unwritable"
                if isinstance(exc, (OSError, PrivateStorageError))
                else "gh_failed",
                message="The local pull-request cache could not be written"
                if isinstance(exc, (OSError, PrivateStorageError))
                else "GitHub returned unreadable pull-request metadata",
                at=utc_stamp(pulls.utc_now()),
                reader=catalog.reader if catalog is not None else None,
            )
            pulls_set.core_failure = window.failure
    finally:
        if owns() and not window.previews and window.failure is None:
            pulls_set.core_window = None


def preparation_key(source: str) -> str:
    return f"{source}:pull-core-window"


async def request_preparation(
    pulls_set: ServedPulls,
    coordinator: RefreshCoordinator,
    ask: CoreRequest,
    running: Callable[[int], bool],
) -> Preparation:
    current = pulls_set.core_window
    if not ask.numbers:
        if current is None or not current.ask.owns(ask):
            return "not_owner"
        pulls_set.core_window = None
        current.cancel()
        return "released"
    if current is not None and current.ask == ask and coordinator.running(current.key):
        return "joined"
    publication = pulls_set.published
    catalog = await asyncio.to_thread(read_catalog, pulls_set.home, pulls_set.slug)
    if pulls_set.published is not publication:
        return "not_owner"
    pulls_set.observe_catalog(catalog)
    cached = await asyncio.to_thread(cached_batch, pulls_set, ask)
    if cached is None or pulls_set.published is not publication:
        return "not_owner"
    current = pulls_set.core_window
    ready, skipped = cached
    if len(ready) + len(skipped) == len(ask.numbers):
        return "ready"
    persisted, listed = await asyncio.gather(
        asyncio.to_thread(read_core_failure, pulls_set.home, pulls_set.slug),
        asyncio.to_thread(read_list_refresh, pulls_set.home, pulls_set.slug, "all"),
    )
    for failure in (persisted, listed):
        if (
            failure is not None
            and catalog is not None
            and failure.reader in {None, catalog.reader}
            and failure.outcome != "succeeded"
            and (
                pulls_set.core_failure is None
                or parse_stamp(failure.at) > parse_stamp(pulls_set.core_failure.at)
            )
        ):
            pulls_set.core_failure = failure
    if _failure_held(pulls_set):
        return (
            "failed"
            if current is not None and current.ask == ask and current.failure is not None
            else "held"
        )
    current = pulls_set.core_window
    if current is not None and current.failure is not None:
        pulls_set.core_window = None
        current = None
    if current is not None and current.ask == ask:
        if coordinator.running(current.key):
            return "joined"
        if current.previews:
            generation, available = await asyncio.to_thread(current.availability)
            if (
                pulls_set.core_window is not current
                or pulls_set.published is not current.publication
                or (generation is not None and generation != ask.generation)
            ):
                return "not_owner"
            current.previews = {
                number: preview
                for number in available
                if not running(number) and (preview := current.prepared(number)) is not None
            }
            if current.previews:
                # Coverage is checked above. A partial provider observation must
                # never claim the whole batch is ready for a progressive caller.
                return "not_owner"
        pulls_set.core_window = None
        return "not_owner"
    key = preparation_key(pulls_set.source)

    def busy() -> bool:
        return (
            pulls_set.foreground_pending(running)
            or coordinator.running(key)
            or coordinator.slot().locked()
            or (
                pulls_set.core_hold_until is not None
                and pulls.utc_now() < pulls_set.core_hold_until
            )
        )

    if busy():
        return "busy"
    window = CoreWindow(ask, coordinator, key, pulls_set.published, pulls_set.source)
    eligible = None
    carried: dict[int, tuple[CatalogMember, PreparedCore]] = {}
    if current is not None:
        # Keep a ready window while at most one competing token proves eligibility.
        if current.checking_replacement:
            return "busy"
        current.checking_replacement = True
        try:
            catalog, admitted = await asyncio.to_thread(_eligible, window)
        finally:
            current.checking_replacement = False
        if (
            pulls_set.core_window is not current
            or pulls_set.published is not window.publication
            or busy()
        ):
            return "busy"
        if catalog is None:
            return "not_owner"
        proof = current.admission
        if (
            proof is not None
            and proof.publication is window.publication
            and proof.matches_identity(catalog)
        ):
            # A still-visible unchanged row needs neither a new read nor a renewed lease.
            carried = {
                number: (member, entry)
                for number, member in proof.members
                if admitted.get(number) == member
                and not running(number)
                and (entry := current.prepared(number)) is not None
            }
        remaining = {number: member for number, member in admitted.items() if number not in carried}
        if not _attemptable(pulls_set, catalog, remaining, running):
            return "not_owner"
        eligible = (catalog, remaining)
    # With no ready owner, the single job also owns its cached eligibility lookup.
    # It clears the temporary claim if no row can actually be attempted.
    pulls_set.core_window = window
    return coordinator.start(
        key, partial(_prepare, pulls_set, window, running, eligible, carried), network=False
    )
