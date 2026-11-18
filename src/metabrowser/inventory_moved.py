"""One retryable outcome for an inventory answer no single version could give.

A complete answer assembled from bounded pages is read at one engine version: the
directory and filtered trees of ``/api/tree`` (`assemble_tree_pages`), its grouped tree
(`assemble_grouped_tree`), the ``/api/catalog`` assembly, and the ``/api/events``
snapshot. A pinned page whose version the provider no longer retains raises
`VersionUnavailableError`, and the assembly restarts; once its bounded attempts run out
it raises the same error. ``/api/rollup`` falls back from its pinned read to one
unpinned read, and a provider that cannot answer that one at its current version raises
it too. The Version Pins section of
``docs/project/architecture/arch-inventory-provider.md`` states the rule.

None of these is a fault of the request or of the data: the files kept changing while
the answer was read, and the same request shortly after usually succeeds. So every
consumer reports it as this one outcome, never as a 500 or a partial answer:

- a route answers 503 with ``Retry-After`` and `inventory_moved_payload`, through the
  handler `server.py` registers for `VersionUnavailableError`;
- ``/api/events`` sends ``fs.resync_required`` with `INVENTORY_MOVED_CODE` as its reason
  and ends, and the browser reconnects with its own backoff for a fresh snapshot;
- ``metab --walk`` stops with `inventory_moved_message` as its error.

``metab --api`` reaches the routes in process, so it prints the 503 envelope and exits
non-zero. `tests/golden/cli-api-inventory-moved.txt` pins all of it.

A read the provider fails with `ProviderFailureError`, while the coordinator's
supervisor replaces the handle or after it has left the root failed (D14), is the same
outcome under its own code, `INVENTORY_PROVIDER_FAILED_CODE`: retrying is again the
remedy, since a reopen or a later open usually answers, but the cause is the provider,
not the files. `inventory_retry_code` picks the code for an error.
"""

from __future__ import annotations

from typing import Final

from metabrowser.inventory_engine.contract import ProviderFailureError

INVENTORY_RETRY_AFTER_S: Final = 1
"""Seconds a client waits before it asks again, sent as ``Retry-After``.

Not measured: it is the smallest delay ``Retry-After`` can express in whole seconds. An
assembly has already retried within the request (`_MAX_ASSEMBLY_ATTEMPTS` in
`inventory_engine/tree_page_assembly.py`, `_CATALOG_ASSEMBLY_ATTEMPTS` in
`events_route.py`), so what the hint adds is only a pause past the burst of changes that
exhausted those attempts; a longer one would keep a reader waiting on a version that has
usually settled by then.
"""

INVENTORY_MOVED_CODE: Final = "inventory_version_moved"
"""The stable token for this outcome: a route body's ``code`` and the SSE resync reason."""

INVENTORY_PROVIDER_FAILED_CODE: Final = "inventory_provider_failed"
"""The same outcome's token when the provider failed rather than the version moved."""

_SUMMARIES: Final = {
    INVENTORY_MOVED_CODE: "Inventory changed while this answer was read",
    INVENTORY_PROVIDER_FAILED_CODE: "The inventory provider failed while this answer was read",
}
_MESSAGES: Final = {
    INVENTORY_MOVED_CODE: "the inventory changed while this answer was read",
    INVENTORY_PROVIDER_FAILED_CODE: "the inventory provider failed while this answer was read",
}


def inventory_retry_code(error: Exception) -> str:
    """The outcome's code for *error*: a provider failure, or else a moved version."""

    if isinstance(error, ProviderFailureError):
        return INVENTORY_PROVIDER_FAILED_CODE
    return INVENTORY_MOVED_CODE


def inventory_moved_payload(code: str = INVENTORY_MOVED_CODE) -> dict[str, str | int]:
    """The 503 body: the existing ``error`` and ``code`` envelope, plus the retry hint."""

    return {
        "error": _SUMMARIES[code],
        "code": code,
        "retry_after_s": INVENTORY_RETRY_AFTER_S,
    }


def inventory_moved_headers() -> dict[str, str]:
    """The 503 response's headers: the retry hint, in the form HTTP defines."""

    return {"Retry-After": str(INVENTORY_RETRY_AFTER_S)}


def inventory_moved_message(code: str = INVENTORY_MOVED_CODE) -> str:
    """The command-line error for the same outcome."""

    return f"{_MESSAGES[code]}; retry in {INVENTORY_RETRY_AFTER_S}s ({code})"


__all__ = [
    "INVENTORY_MOVED_CODE",
    "INVENTORY_PROVIDER_FAILED_CODE",
    "INVENTORY_RETRY_AFTER_S",
    "inventory_moved_headers",
    "inventory_moved_message",
    "inventory_moved_payload",
    "inventory_retry_code",
]
