"""The repository's cached label set, read from the cache alone, and the job that fills it.

``GET github/labels`` answers the set :mod:`.pull_labels` keeps; ``POST
github/labels-refresh`` starts or joins its job, the only one that reads it, under
:func:`.pull_labels.labels_job_key`. A pull request's envelope carries the entries of the
labels its record names without a color (:func:`.pull_labels.labels_for`), so its chips
are colored on first paint once the set is cached, and its page asks for the set when one
of them has none.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import partial
from typing import Any, Literal, TypedDict

from metabrowser.builtin_plugins.github.pull_labels import (
    LabelEntry,
    label_index,
    labels_job_key,
    last_refresh,
    refresh_labels,
    remaining_freshness,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_list_route import served_repository
from metabrowser.http_caching import build_scoped_etag
from metabrowser.mirror_refresh import RefreshCoordinator, refresh_coordinator

LABELS_ROUTE = "/api/plugin/github/labels"


class LabelEnvelope(TypedDict):
    state: Literal["absent", "current", "stale"]
    reason: str | None
    source: str | None
    reader: str | None
    fetched_at: str | None
    fresh_for_s: float
    refreshing: bool
    last_refresh: dict[str, Any] | None
    complete: bool
    count: int
    labels: list[LabelEntry]


@dataclass(frozen=True, slots=True)
class LabelView:
    repository: ListedRepository | None
    coordinator: RefreshCoordinator | None
    refreshing: bool


def label_view(app: Any) -> LabelView:
    repository, coordinator = served_repository(app), refresh_coordinator(app)
    return LabelView(
        repository,
        coordinator,
        bool(
            repository is not None
            and coordinator is not None
            and coordinator.running(labels_job_key(repository.source))
        ),
    )


def label_envelope(view: LabelView) -> LabelEnvelope:
    """The cached set, every label in GitHub's order. Blocking and bounded."""

    result = LabelEnvelope(
        state="absent",
        reason="not_github",
        source=None,
        reader=None,
        fetched_at=None,
        fresh_for_s=0,
        refreshing=view.refreshing,
        last_refresh=None,
        complete=False,
        count=0,
        labels=[],
    )
    repository = view.repository
    if repository is None:
        return result
    index = label_index(repository.home, repository.slug, repository.source)
    cache = index.cache if index is not None else None
    stamp = last_refresh(repository.home, repository.source, cache)
    result.update(source=repository.source, reason=stamp.outcome if stamp else "not_cached")
    if stamp is not None:
        result.update(
            last_refresh=stamp.model_dump(exclude={"reader"}),
            fresh_for_s=remaining_freshness(stamp),
        )
    snapshot = cache.snapshot if cache is not None else None
    if snapshot is None:
        return result
    labels = [
        LabelEntry(name=label.name, color=label.color, description=label.description)
        for label in snapshot.labels()
    ]
    fresh = result["fresh_for_s"] > 0 and stamp is not None and stamp.outcome == "succeeded"
    result.update(
        state="current" if fresh else "stale",
        reason=None,
        reader=snapshot.reader,
        fetched_at=snapshot.fetched_at,
        complete=snapshot.complete,
        count=len(labels),
        labels=labels,
    )
    return result


def envelope_etag(envelope: LabelEnvelope) -> str:
    # As the stack snapshot's: the countdown alone is left out; its expiry changes state.
    stable = {key: value for key, value in envelope.items() if key != "fresh_for_s"}
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
    return build_scoped_etag(f"labels-{digest[:32]}")


def start_refresh(
    view: LabelView, *, retry: bool, wanted: bool
) -> Literal["started", "joined", "not_due"]:
    repository, coordinator = view.repository, view.coordinator
    assert repository is not None and coordinator is not None
    key = labels_job_key(repository.source)
    if coordinator.running(key):
        return "joined"
    if not wanted:
        return "not_due"
    return coordinator.start(
        key,
        partial(refresh_labels, repository, slot=coordinator.slot(), retry=retry),
        network=False,
    )


__all__ = [
    "LABELS_ROUTE",
    "LabelEnvelope",
    "LabelView",
    "envelope_etag",
    "label_envelope",
    "label_view",
    "start_refresh",
]
