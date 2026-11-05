"""One ephemeral, catalog-admitted core window on the served pull source."""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Literal

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.gh import GhError, gh_graphql
from metabrowser.builtin_plugins.github.gh_lists import READ_FAILURES, as_dict
from metabrowser.builtin_plugins.github.pull_catalog import (
    MAX_CATALOG_MEMBERS,
    CatalogMember,
    CatalogState,
    catalog_members,
)
from metabrowser.builtin_plugins.github.pull_list import (
    ListedRepository,
    parse_stamp,
    rate_limit_holds,
    read_list_refresh,
)
from metabrowser.builtin_plugins.github.served_pull import PullCorePreview, make_core_preview
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
type Preparation = Literal["started", "joined", "ready", "released", "not_owner", "busy"]


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

    def matching_catalog(self) -> CatalogState | None:
        """Recheck admitted rows in the same catalog, even if pagination shifted."""
        now, members = catalog_members(
            self.publication.home,
            self.publication.slug,
            self.state,
            tuple(number for number, _ in self.members),
        )
        if (
            now is not None
            and now.source == self.source
            and now.reader == self.reader
            and now.repository_id == self.repository_id
            and now.epoch == self.epoch
            and members == dict(self.members)
        ):
            return now
        return None

    def catalog_matches(self) -> bool:
        return self.matching_catalog() is not None


@dataclass(eq=False, slots=True)
class CoreWindow:
    ask: CoreRequest
    coordinator: RefreshCoordinator
    key: str
    publication: PublishedSource | ListedRepository
    source: str
    admission: CoreAdmission | None = None
    previews: dict[int, PullCorePreview] | None = None
    expires_at: float = 0
    checking_replacement: bool = False

    def preview(self, number: int) -> PullCorePreview | None:
        if self.previews is None or time.monotonic() >= self.expires_at:
            return None
        return self.previews.get(number)

    def catalog_matches(self) -> bool:
        return self.admission is not None and self.admission.catalog_matches()

    def availability(self) -> tuple[str | None, tuple[int, ...]]:
        proof = self.admission
        catalog = proof.matching_catalog() if proof is not None else None
        if proof is None or catalog is None:
            return None, ()
        numbers = tuple(number for number, _ in proof.members if _record_missing(self, number))
        return catalog.generation(self.ask.state), numbers

    def cancel(self) -> asyncio.Task[None] | None:
        return self.coordinator.cancel(self.key)


def _record_missing(window: CoreWindow, number: int) -> bool:
    """Admit only a missing private entry, without reading a record's contents."""
    try:
        fd = open_private_file(
            window.publication.home,
            source_pull_record(window.publication.slug, number),
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
    if (
        catalog is None
        or catalog.source != source
        or catalog.generation(ask.state) != ask.generation
        or members.keys() != set(ask.numbers)
        or rate_limit_holds(read_list_refresh(home, slug, "all"), now=pulls.utc_now())
    ):
        return None, {}
    return catalog, {n: members[n] for n in ask.numbers if _record_missing(window, n)}


async def _prepare(
    pulls_set: ServedPulls,
    window: CoreWindow,
    running: Callable[[int], bool],
    eligible: tuple[CatalogState, dict[int, CatalogMember]] | None = None,
) -> None:
    publication = window.publication

    def owns() -> bool:
        return pulls_set.core_window is window and pulls_set.published is publication

    try:
        catalog, admitted = (
            await asyncio.to_thread(_eligible, window) if eligible is None else eligible
        )
        numbers = tuple(number for number in admitted if not running(number))
        slot = window.coordinator.slot()
        if (
            not owns()
            or catalog is None
            or not numbers
            or pulls_set.foreground_pending(running)
            or slot.locked()
        ):
            return
        window.admission = CoreAdmission(
            publication,
            window.source,
            window.ask.state,
            catalog.epoch,
            catalog.reader,
            catalog.repository_id,
            tuple((number, admitted[number]) for number in numbers),
        )
        owner, repo = pulls._owner_and_repo(publication)
        variables: dict[str, str | int] = {"owner": owner, "name": repo}
        variables.update({f"n{i}": number for i, number in enumerate(numbers)})
        # No await separates the locked check from acquiring the free permit.
        async with slot:
            data = await gh_graphql(_batch_query(len(numbers)), variables, now=pulls.utc_now())
        observed_at = pulls.utc_now()
        expires_at = time.monotonic() + FRESHNESS_WINDOW_S
        repository = as_dict(data["repository"])
        login = as_dict(data["viewer"])["login"]
        name = repository["nameWithOwner"]
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
        window.previews = {
            number: make_core_preview(
                window.source, catalog.reader, models[number], observed_at, "not_started"
            )
            for number in still_missing
            if not running(number)
            and parse_stamp(models[number].updated_at) >= parse_stamp(admitted[number].updated_at)
        }
        window.expires_at = expires_at
    except GhError as exc:
        if owns() and exc.state == "rate_limited" and exc.reset_at is not None:
            pulls_set.core_hold_until = parse_stamp(exc.reset_at)
    except (*READ_FAILURES, ValueError):
        return
    finally:
        if owns() and not window.previews:
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
                if not running(number) and (preview := current.preview(number)) is not None
            }
            if current.previews:
                return "ready"
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
        if catalog is None or not any(not running(number) for number in admitted):
            return "not_owner"
        eligible = (catalog, admitted)
    pulls_set.core_window = window
    return coordinator.start(
        key, partial(_prepare, pulls_set, window, running, eligible), network=False
    )
