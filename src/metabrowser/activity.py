"""Bounded filesystem probes for host-owned activity decorations.

Inventory providers retain filesystem facts. This module performs only the small,
recurring stat and PID probes needed for the browser's "being written now" badge. The
application-owned tracker in :mod:`metabrowser.active_tracker` chooses candidates from
the provider contract and publishes the resulting state through the sparse overlay.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

ACTIVITY_POLL_INTERVAL_MS = 5_000
TRACKABLE_FILE_MAX_SIZE = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ActivityPoll:
    """One bounded probe result, keyed by absolute path strings."""

    active: tuple[str, ...]
    observed: tuple[tuple[str, int, int], ...]
    modified: tuple[tuple[str, int, int], ...]
    missing: tuple[str, ...]


class FileActivityTracker:
    """Detect recent ``(size, mtime_ns)`` changes for a supplied path set."""

    def __init__(self, stale_after_s: float = 30.0):
        if stale_after_s <= 0:
            raise ValueError("stale_after_s must be positive")
        self.stale_after_s = stale_after_s
        # path -> (last fingerprint, monotonic time of the last observed change)
        self._state: dict[str, tuple[tuple[int, int], float]] = {}

    def poll_observations(self, paths: list[Path]) -> ActivityPoll:
        """Re-stat *paths* and report activity plus actual metadata transitions.

        First observations establish a baseline and do not count as writes. Paths no
        longer supplied are pruned, while a supplied path that vanished is reported so
        the inventory provider can verify the deletion.
        """

        now = monotonic()
        requested = {str(path) for path in paths}
        for stale in self._state.keys() - requested:
            del self._state[stale]

        active: list[str] = []
        observed: list[tuple[str, int, int]] = []
        modified: list[tuple[str, int, int]] = []
        missing: list[str] = []
        for path in paths:
            key = str(path)
            try:
                stat_result = path.stat()
            except OSError:
                self._state.pop(key, None)
                missing.append(key)
                continue

            fingerprint = (stat_result.st_size, stat_result.st_mtime_ns)
            observed.append((key, fingerprint[0], fingerprint[1]))
            previous = self._state.get(key)
            if previous is None:
                self._state[key] = (fingerprint, 0.0)
            elif previous[0] != fingerprint:
                self._state[key] = (fingerprint, now)
                modified.append((key, fingerprint[0], fingerprint[1]))

            _fingerprint, changed_at = self._state[key]
            if changed_at > 0 and now - changed_at < self.stale_after_s:
                active.append(key)

        return ActivityPoll(
            active=tuple(active),
            observed=tuple(observed),
            modified=tuple(modified),
            missing=tuple(missing),
        )

    @staticmethod
    def check_pid_alive(pid_path: Path) -> bool:
        """Whether the process named by *pid_path* is currently addressable."""

        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False


__all__ = [
    "ACTIVITY_POLL_INTERVAL_MS",
    "ActivityPoll",
    "FileActivityTracker",
    "TRACKABLE_FILE_MAX_SIZE",
]
