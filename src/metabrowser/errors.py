"""Error types raised by the `metab` CLI and MetaBrowser library code."""

from __future__ import annotations

from typing import override


class CLIError(Exception):
    """User-facing error from a `metab` CLI command.

    Carries an exit code (default 1). Rendered by the CLI entry points as
    ``Error: <message>`` on stderr; library code may catch it explicitly when
    it needs the same user-facing surface.
    """

    @override
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code: int = exit_code
