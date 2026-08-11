"""Lightweight console-script boundary for interruption-safe CLI startup."""

from __future__ import annotations

from metabrowser.cli.exit_codes import INTERRUPTED_EXIT_CODE


def _run_cli() -> None:
    from metabrowser.cli.main import main

    main()


def main() -> int:
    """Load and run the CLI without printing a traceback for Ctrl-C."""
    try:
        _run_cli()
    except KeyboardInterrupt:
        return INTERRUPTED_EXIT_CODE
    return 0
