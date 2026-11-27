"""Which lane each piece of GitHub work serves, so every ``gh`` span can say so.

A lane says who waits for the answer, which is what work competing for the network should
be ordered by (the GitHub request performance work of
``docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md``). There are
four, :data:`LANES` in that order, most urgent first:

``visible``
    A page the reader is looking at shows the answer, or the reader's own action asked for
    it: a pull request page's probe and the read a change, a due full read, or a Refresh
    starts, its files list, timeline, label set, and stacks; the Pulls tab's list probe, the
    catalog's pages of its filter as far as the reader has scrolled, a delta scan a change
    or a Refresh asks for, and the cores of the rows on screen; a prefetched record a page
    then asks for; a one-shot command's reads, and the GitHub status check.
``attended``
    The session reads it for what the reader is looking at, and no page shows it: the
    attended pull request read with its mirror (only ``"due"`` asks it,
    :data:`~metabrowser.mirror_refresh.RefreshAsk`), and the list a pull request page keeps
    probed and scanned so the catalog keeps vouching for its record
    (:func:`.pull_list_route.attend_list`, and the page's own ``pulls-refresh`` ask).
``prefetch``
    What the reader may open next, read before they ask: the prefetch's records and files
    lists (:mod:`.pull_prefetch`).
``background``
    What the server reads on its own clock, or to finish what it holds: the catalog's delta
    scan when it is due by age, and its backfill past every reader's prefix
    (:func:`.pull_list_refresh.refresh_pull_list`); the scan of every open pull request's
    status, but for a reader's Refresh (:mod:`.pull_status_scan`); and the cores walk past
    the rows on screen (:mod:`.pull_cores`).

The lane is a context variable set where the work starts (:func:`serving`), so a job a
refresh coordinator starts copies it with the rest of its context, as it copies the budget
:mod:`.gh_budget` charges, and :func:`.gh._run` records :func:`current_lane` as ``lane`` on
every ``gh`` span, which the request report groups by (:mod:`.gh_requests`). Nothing passes
it by hand. Work nothing marks is ``visible``: a page or a command asked for it and waits,
and every other lane is a decision the code that schedules the work makes, so that code says
so. A job shared by asks of different lanes serves the most urgent of them where it can tell
(:meth:`.served_pull.ServedPull.refresh` reads its asks), and otherwise the lane it was
started in, as a job a reader's click only joins keeps its budget.

The lanes are recorded, not yet scheduled by: what is in flight is bounded by the
coordinator's network slots and the probes' cap, whatever the lane, and ordering them is
among that plan's tuning.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Final, Literal

type Lane = Literal["visible", "attended", "prefetch", "background"]
# The lanes, most urgent first; the module docstring says what each holds.
LANES: Final[tuple[Lane, ...]] = ("visible", "attended", "prefetch", "background")

# The lane the work running in this context serves. A task created inside copies it.
_LANE: ContextVar[Lane] = ContextVar("metabrowser_gh_lane", default="visible")


@contextmanager
def serving(lane: Lane) -> Generator[None]:
    """Mark the work started inside as serving *lane*, until the block ends.

    A scheduler enters it around the start of work no page shows (a job's task copies the
    context when it is created), or around one step of a job that serves another lane than
    the job was started for, as a catalog page past every reader's prefix does.
    """

    token = _LANE.set(lane)
    try:
        yield
    finally:
        _LANE.reset(token)


def current_lane() -> Lane:
    """The lane the work running in this context serves (:func:`serving`)."""

    return _LANE.get()


__all__ = ["LANES", "Lane", "current_lane", "serving"]
