"""``--event-log``: ROOT is the directory Metabrowser's own event log lives in.

A served ``metab`` writes its event log to ``events/`` under the state directory
(:func:`metabrowser.event_log.log_directory`), and the event-log plugin opens a segment of
it as spans and latencies. This names that directory as ROOT, so every mode that takes a
folder reads the log: ``metab --event-log`` serves it at its newest segment, and
``metab --event-log --api /api/tree`` lists the segments.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from metabrowser import event_log
from metabrowser.errors import CLIError


def event_log_directory(environ: Mapping[str, str] | None = None) -> Path:
    """The directory the event log is in, or a :class:`CLIError` saying why there is none."""

    try:
        _state, directory = event_log.log_directory(environ)
    except ValueError as exc:
        raise CLIError(f"the event log's directory is not configured: {exc}") from exc
    if not directory.is_dir():
        raise CLIError(
            f"there is no event log at {directory}: a served metab writes one there "
            f"({event_log.ENABLE_ENV}=0 turns it off, and a one-shot command writes none)"
        )
    return directory


def newest_segment(directory: Path) -> str:
    """The name of the segment most recently started in *directory*, or ``""`` for none."""

    files = event_log.list_files(directory)
    return files[0].name if files else ""
