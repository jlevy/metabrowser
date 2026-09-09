"""Bounded instrumentation for the disposable fdu inventory adapter spike."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReadObservation:
    """One adapter read, including every deliberately naive operation."""

    query_kinds: tuple[str, ...]
    native_calls: int
    native_pages: int
    materialized_rows: int
    materialized_path_bytes: int
    child_bucket_sorts: int
    full_result_sorts: int
    aggregate_passes: int
    rows_returned: int
    wall_time_ns: int
    cpu_time_ns: int


class AdapterProbe:
    """Thread-safe, bounded evidence recorder shared by one spike handle."""

    _MAX_OBSERVATIONS = 10_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reads: list[ReadObservation] = []
        self._dropped = 0
        self._change_polls = 0
        self._refreshes = 0
        self._priorities = 0

    def record_read(self, observation: ReadObservation) -> None:
        with self._lock:
            if len(self._reads) == self._MAX_OBSERVATIONS:
                self._dropped += 1
                return
            self._reads.append(observation)

    def record_change_poll(self) -> None:
        with self._lock:
            self._change_polls += 1

    def record_refresh(self) -> None:
        with self._lock:
            self._refreshes += 1

    def record_priority(self) -> None:
        with self._lock:
            self._priorities += 1

    def snapshot(self) -> dict[str, Any]:
        """Return immutable JSON-compatible evidence for the current run."""

        with self._lock:
            reads = tuple(self._reads)
            return {
                "read_observations": [asdict(read) for read in reads],
                "dropped_observations": self._dropped,
                "change_polls": self._change_polls,
                "refreshes": self._refreshes,
                "priorities": self._priorities,
                "totals": {
                    "reads": len(reads),
                    "native_calls": sum(read.native_calls for read in reads),
                    "native_pages": sum(read.native_pages for read in reads),
                    "materialized_rows": sum(read.materialized_rows for read in reads),
                    "materialized_path_bytes": sum(read.materialized_path_bytes for read in reads),
                    "child_bucket_sorts": sum(read.child_bucket_sorts for read in reads),
                    "full_result_sorts": sum(read.full_result_sorts for read in reads),
                    "aggregate_passes": sum(read.aggregate_passes for read in reads),
                    "rows_returned": sum(read.rows_returned for read in reads),
                    "wall_time_ns": sum(read.wall_time_ns for read in reads),
                    "cpu_time_ns": sum(read.cpu_time_ns for read in reads),
                },
            }


__all__ = ["AdapterProbe", "ReadObservation"]
