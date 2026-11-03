"""Explicit recovery of the immutable objects a comparison failed to read.

A normal read and an automatic refresh never call this. Recovery checks the displayed
commits and a bounded set of observed object IDs, fetches missing IDs before the ordinary
PR-ref refresh, and authenticates complete recovered objects before clearing failures.
There is no history walk, clone, or write to the checkout. A corrupt lender remains a
typed refusal: fetch negotiation cannot repair an object it already claims to have.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from metabrowser.cache.pull_refs import PullRefError, fetch_objects
from metabrowser.git.object_failures import FailedObject, observed_object_failures
from metabrowser.git.process import GitError, repository_store_target
from metabrowser.git.tree_source import (
    GitObjectCorruptError,
    GitObjectUnavailableError,
    verify_store_object,
)
from metabrowser.git.wire import is_full_revision

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

# The existing fetch-lock wait is sixty seconds. Give the entire explicit repair one
# such window, including lock waits and at most ten IDs (two ends and eight observations),
# rather than giving every object its own fifteen-minute acquisition timeout.
RECOVERY_TIMEOUT_S = 60.0


async def recover_comparison_objects(
    published: PublishedSource, commits: tuple[str, ...]
) -> tuple[FailedObject, ...]:
    """Restore missing displayed IDs; return only observations successfully authenticated.

    A refused or failed recovery leaves observations and the caller's prior record intact.
    Objects beyond the ordinary whole-read bound are not called verified. Their normal
    partial windows remain available; this recovery simply cannot certify them.
    """
    if not 1 <= len(commits) <= 2 or not all(is_full_revision(oid) for oid in commits):
        raise ValueError("recovery requires one or two complete commit IDs")
    target = repository_store_target(git_dir=published.git_dir)
    failures = observed_object_failures.pending(target, commits)
    oids = tuple(dict.fromkeys((*commits, *(failure.oid for failure in failures))))

    async def verify(oid: str) -> bool:
        complete = await verify_store_object(target, oid)
        if not complete:
            raise PullRefError(
                "comparison_too_large",
                "an object is too large to verify within the comparison read limit",
            )
        return complete

    try:
        async with asyncio.timeout(RECOVERY_TIMEOUT_S):
            missing: list[str] = []
            for oid in oids:
                try:
                    await verify(oid)
                except GitObjectUnavailableError:
                    missing.append(oid)
            if missing:
                await fetch_objects(published, tuple(missing), timeout_s=RECOVERY_TIMEOUT_S)
                for oid in missing:
                    await verify(oid)
    except PullRefError as exc:
        if exc.state in {"fetch_failed", "not_found_or_private"}:
            raise PullRefError(
                "commits_unavailable",
                "the origin could not restore an object of the displayed comparison",
            ) from exc
        raise
    except GitObjectCorruptError as exc:
        raise PullRefError(
            "object_corrupt",
            "an object supplied by this store does not match its ID; repair the checkout before retrying",
        ) from exc
    except GitObjectUnavailableError as exc:
        raise PullRefError(
            "commits_unavailable",
            "the origin could not restore an object of the displayed comparison",
        ) from exc
    except TimeoutError as exc:
        raise PullRefError(
            "network_error", "the comparison recovery did not finish in time"
        ) from exc
    except GitError as exc:
        raise PullRefError(
            "commits_unavailable", "an object of the displayed comparison could not be verified"
        ) from exc
    for failure in failures:
        observed_object_failures.verified(target, commits, failure)
    return failures
