"""The account's GitHub rate budget as its responses report it, and whether background work may spend it.

Every response :func:`~.gh.gh_api` and :func:`~.gh.gh_graphql` parse, refusals and ``304``
answers included, carries ``x-ratelimit-limit``, ``-remaining``, ``-reset`` (epoch seconds),
``-used``, and ``-resource``, ``core`` for REST and ``graphql`` for GraphQL (seen on both
on 2026-11-11). :func:`observe` keeps the newest of each resource for this process, until
its reset. A ``rate_limited`` refusal holds every resource until its ``reset_at``, or for a
freshness window when GitHub gave none (:func:`hold`).

The budget belongs to the account, not to Metabrowser: at the start of that measurement
the account had already spent 416 core and 162 GraphQL points of the hour from other
clients. So background work is admitted only while each observed resource it spends has
more than :data:`BACKGROUND_FLOOR` of its limit remaining and no hold applies
(:func:`admission`). With nothing observed it is admitted, and its first response is
observed. A reader's own work is never asked.

The observations are per process. ``remaining`` is the account's, so several servers on
one cache stop together.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, TypedDict

# A reserve for the reader and the account's other clients, not a measure of Metabrowser's
# own use: 1,250 of 5,000 core points cover a reader who refreshes a pull request every 30 s
# for two hours, 240 refreshes at the 8 points one costs at most (two account checks, the
# pull, and five parts of a page each), with room beside it.
BACKGROUND_FLOOR: Final = 0.25
# How long a refusal that named no reset time holds: the refresh coordinator's window, as
# ``pull_list_refresh`` waits after one.
UNKNOWN_RESET_HOLD_S: Final = 60.0
# Resources are header text, so the ones kept are bounded: GitHub names a handful.
_MAX_RESOURCES: Final = 8
_RESOURCE: Final = re.compile(r"[a-z_]{1,32}")
_COUNT: Final = re.compile(r"[0-9]{1,9}")
_EPOCH: Final = re.compile(r"[0-9]{1,12}")

type AdmissionReason = Literal["below_floor", "rate_hold"]


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RateObservation:
    """One resource's budget as a response reported it, valid until ``reset_at``."""

    resource: str
    limit: int
    remaining: int
    reset_at: str


class ObservationWire(TypedDict):
    limit: int
    remaining: int
    reset_at: str


@dataclass(frozen=True, slots=True)
class Admission:
    """Whether background work may start now, and if not, why."""

    admitted: bool
    reason: AdmissionReason | None = None


_OBSERVED: dict[str, RateObservation] = {}
_held_until: str | None = None


def observe(headers: Mapping[str, str], *, resource: str) -> None:
    """Keep what *headers* (lowercased) say of the budget; *resource* when they name none."""

    named = headers.get("x-ratelimit-resource", resource)
    limit, remaining = (
        headers.get("x-ratelimit-limit", ""),
        headers.get("x-ratelimit-remaining", ""),
    )
    reset = headers.get("x-ratelimit-reset", "")
    if not (
        _RESOURCE.fullmatch(named)
        and _COUNT.fullmatch(limit)
        and _COUNT.fullmatch(remaining)
        and _EPOCH.fullmatch(reset)
        and int(limit) > 0
    ):
        return
    try:
        reset_at = _stamp(datetime.fromtimestamp(int(reset), tz=UTC))
    except (OverflowError, OSError, ValueError):
        return
    if named not in _OBSERVED and len(_OBSERVED) >= _MAX_RESOURCES:
        return
    _OBSERVED[named] = RateObservation(named, int(limit), int(remaining), reset_at)


def hold(reset_at: str | None, *, now: datetime) -> None:
    """Hold background work after a ``rate_limited`` refusal, never shortening a hold."""

    global _held_until
    deadline = reset_at or _stamp(now + timedelta(seconds=UNKNOWN_RESET_HOLD_S))
    try:
        _parse(deadline)
    except ValueError:
        deadline = _stamp(now + timedelta(seconds=UNKNOWN_RESET_HOLD_S))
    if _held_until is None or deadline > _held_until:
        _held_until = deadline


def held_until(now: datetime) -> str | None:
    """When the hold lifts, or ``None`` when none applies at *now*."""

    return _held_until if _held_until is not None and now < _parse(_held_until) else None


def observations(now: datetime) -> dict[str, ObservationWire]:
    """Each resource's budget as last observed, leaving out those past their reset."""

    return {
        name: ObservationWire(limit=seen.limit, remaining=seen.remaining, reset_at=seen.reset_at)
        for name, seen in sorted(_OBSERVED.items())
        if now < _parse(seen.reset_at)
    }


def admission(
    resources: Iterable[str], *, now: datetime, floor: float = BACKGROUND_FLOOR
) -> Admission:
    """Whether background work that spends *resources* may start at *now*."""

    if held_until(now) is not None:
        return Admission(False, "rate_hold")
    for name in resources:
        seen = _OBSERVED.get(name)
        if seen is None or now >= _parse(seen.reset_at):
            continue
        if seen.remaining <= floor * seen.limit:
            return Admission(False, "below_floor")
    return Admission(True)


def forget() -> None:
    """Drop every observation and hold, as a new process starts with none; for tests."""

    global _held_until
    _OBSERVED.clear()
    _held_until = None


__all__ = [
    "BACKGROUND_FLOOR",
    "UNKNOWN_RESET_HOLD_S",
    "Admission",
    "AdmissionReason",
    "ObservationWire",
    "RateObservation",
    "admission",
    "forget",
    "held_until",
    "hold",
    "observations",
    "observe",
]
