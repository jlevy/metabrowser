"""One cache-only stack snapshot and one optional repository refresh job."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import partial
from typing import Any, Literal, TypedDict

from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_list_route import served_repository
from metabrowser.builtin_plugins.github.pull_stacks import (
    last_refresh,
    read_stacks,
    refresh_stacks,
    remaining_freshness,
)
from metabrowser.http_caching import build_scoped_etag
from metabrowser.mirror_refresh import RefreshCoordinator, refresh_coordinator

STACKS_ROUTE = "/api/plugin/github/stacks"


class StackEnvelope(TypedDict):
    state: Literal["absent", "current", "stale"]
    reason: str | None
    source: str | None
    reader: str | None
    fetched_at: str | None
    fresh_for_s: float
    refreshing: bool
    last_refresh: dict[str, Any] | None
    complete: bool
    stacks: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class StackView:
    repository: ListedRepository | None
    coordinator: RefreshCoordinator | None
    refreshing: bool


def job_key(repository: ListedRepository) -> str:
    return f"{repository.source}:native-stacks"


def stack_view(app: Any) -> StackView:
    repository, coordinator = served_repository(app), refresh_coordinator(app)
    return StackView(
        repository,
        coordinator,
        bool(
            repository is not None
            and coordinator is not None
            and coordinator.running(job_key(repository))
        ),
    )


def stack_envelope(view: StackView) -> StackEnvelope:
    """Project only known positive membership; incomplete/absent never means unstacked."""
    repository = view.repository
    result = StackEnvelope(
        state="absent",
        reason="not_github",
        source=None,
        reader=None,
        fetched_at=None,
        fresh_for_s=0,
        refreshing=view.refreshing,
        last_refresh=None,
        complete=False,
        stacks=[],
    )
    if repository is None:
        return result
    cache = read_stacks(repository)
    stamp = last_refresh(repository, cache)
    result.update(source=repository.source, reason=stamp.outcome if stamp else "not_cached")
    if stamp is not None:
        result.update(
            last_refresh=stamp.model_dump(exclude={"reader"}),
            fresh_for_s=remaining_freshness(stamp),
        )
    snapshot = cache.snapshot if cache else None
    if snapshot is None:
        return result
    fresh = result["fresh_for_s"] > 0 and stamp is not None and stamp.outcome == "succeeded"
    result.update(
        state="current" if fresh else "stale",
        reason=None,
        reader=snapshot.reader,
        fetched_at=snapshot.fetched_at,
        complete=snapshot.complete,
        stacks=[stack.model_dump(mode="json") for page in snapshot.pages for stack in page.stacks],
    )
    return result


def envelope_etag(envelope: StackEnvelope) -> str:
    # The client keeps the original absolute deadline after 304. A countdown alone
    # does not change membership; expiry still changes state and therefore the tag.
    stable = {key: value for key, value in envelope.items() if key != "fresh_for_s"}
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"stacks-{digest[:32]}")


def start_refresh(
    view: StackView, *, retry: bool, wanted: bool
) -> Literal["started", "joined", "not_due"]:
    repository, coordinator = view.repository, view.coordinator
    assert repository is not None and coordinator is not None
    key = job_key(repository)
    if coordinator.running(key):
        return "joined"
    if not wanted:
        return "not_due"
    return coordinator.start(
        key,
        partial(refresh_stacks, repository, slot=coordinator.slot(), retry=retry),
        network=False,
    )
