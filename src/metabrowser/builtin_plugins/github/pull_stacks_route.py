"""One cache-only stack snapshot and one optional repository refresh job."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, TypedDict

from metabrowser.builtin_plugins.github.pull_catalog import MAX_WINDOW, catalog_rows
from metabrowser.builtin_plugins.github.pull_list import ListedRepository, PullListRow
from metabrowser.builtin_plugins.github.pull_list_route import served_repository
from metabrowser.builtin_plugins.github.pull_stacks import (
    last_refresh,
    read_stacks,
    refresh_stacks,
    remaining_freshness,
)
from metabrowser.http_caching import build_scoped_etag
from metabrowser.mirror_refresh import RefreshCoordinator, refresh_coordinator

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_record import PullRecord

STACKS_ROUTE = "/api/plugin/github/stacks"


class MemberIdentity(NamedTuple):
    """A stack member's title, author, and the author's avatar, as a member row draws them,
    and its labels' names, which a stack's page decides its labels row by before its answer
    lands (`knownLabels` in stack-page.js): None where they are not known."""

    title: str | None
    author: str | None
    avatar: str | None
    labels: tuple[str, ...] | None


def member_identity(record: PullRecord | None, row: PullListRow | None) -> MemberIdentity:
    """*record*'s, the member's cached record, which a reader's fetch wrote, else *row*'s, its
    row in the repository's cached list, else none: the one rule the stacks route and a
    stack's route (pull_stack.py) name a member by, so the stack menu and a stack's page name
    it alike (docs/design-system.md, "Stacks"). Labels are the exception: *row*'s wherever
    there is one, since the stacks route reads a record only for a member with no row, and a
    label change marks neither stale, so the two routes would otherwise disagree for as long
    as the two caches do, and the labels row would come and go after first paint."""

    if record is not None:
        return MemberIdentity(
            record.pull.title,
            record.pull.author,
            record.pull.author_avatar_url,
            row.labels if row is not None else tuple(label.name for label in record.pull.labels),
        )
    if row is not None:
        return MemberIdentity(row.title, row.author, row.author_avatar_url, row.labels)
    return MemberIdentity(None, None, None, None)


def _member_record(repository: ListedRepository, reader: str, number: int) -> PullRecord | None:
    """*number*'s cached record, read through the pull route's parse cache, when it is of
    *repository* and was read by *reader*, the account the snapshot was read by."""

    from metabrowser.builtin_plugins.github.pull_record import PullRecord
    from metabrowser.builtin_plugins.github.pull_route import cached_pull_record

    found, _dumped, _revision = cached_pull_record(repository.home, repository.slug, number)
    if (
        isinstance(found, PullRecord)
        and found.source.casefold() == repository.source.casefold()
        and found.reader == reader
    ):
        return found
    return None


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
    stacks = [stack.model_dump(mode="json") for page in snapshot.pages for stack in page.stacks]
    # Native stack members contain no titles or authors. Project the repository's existing
    # metadata caches instead, without provider calls or duplicate storage: each member's
    # title, its author, and the author's avatar, which the page's stack menu draws after
    # the member's number as a Pulls row does (docs/design-system.md, "Stacks"), and its
    # labels' names, from which a stack's page decides at first paint whether it has a
    # labels row (docs/design-system.md, "The Stack Page"), by the rule a stack's page names
    # it by (`member_identity`). The catalog's rows are read in indexed
    # batches. A member the catalog does not hold, as a merged member the list no longer
    # holds, is named by its cached record, read through the pull route's parse cache, for
    # at most as many such members as that cache keeps, so the records an answer reads stay
    # parsed across polls; one beyond them, or with no record, has none of the three.
    numbers = tuple(dict.fromkeys(number for stack in stacks for number in stack["pulls"]))
    rows: dict[int, PullListRow] = {}
    for offset in range(0, len(numbers), MAX_WINDOW):
        rows.update(
            catalog_rows(repository, snapshot.reader, numbers[offset : offset + MAX_WINDOW])
        )
    from metabrowser.builtin_plugins.github.pull_route import MAX_PARSED_RECORDS

    unlisted = [number for number in numbers if number not in rows][:MAX_PARSED_RECORDS]
    records = {number: _member_record(repository, snapshot.reader, number) for number in unlisted}
    for stack in stacks:
        members = [
            member_identity(records.get(number), rows.get(number)) for number in stack["pulls"]
        ]
        stack["titles"] = [member.title for member in members]
        stack["authors"] = [member.author for member in members]
        stack["avatars"] = [member.avatar for member in members]
        stack["labels"] = [
            None if member.labels is None else list(member.labels) for member in members
        ]
        stack["updated_at"] = max(
            [rows[number].updated_at for number in stack["pulls"] if number in rows]
            + [
                record.pull.updated_at
                for number in stack["pulls"]
                if (record := records.get(number)) is not None
            ],
            default=None,
        )
        stack["leaders"] = {}
    _assign_leaders(stacks, rows)
    fresh = result["fresh_for_s"] > 0 and stamp is not None and stamp.outcome == "succeeded"
    result.update(
        state="current" if fresh else "stale",
        reason=None,
        reader=snapshot.reader,
        fetched_at=snapshot.fetched_at,
        complete=snapshot.complete,
        stacks=stacks,
    )
    return result


def _assign_leaders(stacks: list[dict[str, Any]], rows: dict[int, PullListRow]) -> None:
    """Project one owned member per filter for a stack above the loaded list's end.

    Claim shared members in stack rank order, as the column does. A later stack can
    then be represented by its own highest-ranked member when it shares the first.
    """
    # GitHub’s snapshot order breaks equal-activity ties in the column as well.
    ranked = sorted(stacks, key=lambda stack: stack["updated_at"] or "", reverse=True)
    for name in ("open", "closed", "all"):
        claimed: set[int] = set()
        for stack in ranked:
            available = [
                rows[number]
                for number in stack["pulls"]
                if number not in claimed
                and number in rows
                and (name == "all" or rows[number].state == name)
            ]
            if available:
                claimed.update(row.number for row in available)
                lead = max(available, key=lambda row: (row.updated_at, row.number))
                stack["leaders"][name] = lead.model_dump(
                    mode="json",
                    include={
                        "number",
                        "title",
                        "state",
                        "draft",
                        "author",
                        "author_avatar_url",
                        "updated_at",
                        "head_oid",
                    },
                ) | {"merged": lead.merged}


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
