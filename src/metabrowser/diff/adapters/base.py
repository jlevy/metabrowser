"""The DiffSource port.

Four methods and no source-specific vocabulary — this smallness is what
keeps patch-file, git, hosted, and document-edit sources interchangeable.
An intent is adapter-specific and arrives as plain data; everything a
source returns is File Diff Format.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from metabrowser.diff.format import ChangeSetManifest, FilePatch, ResolvedComparison


class DiffSourceError(Exception):
    """A source could not resolve or produce.

    ``str()`` is the detail an agent, the CLI, and the log read: it names the revision or
    file asked for. ``reader_message`` is the one sentence a page shows in their place
    (docs/design-system-messages.md), and ``code``, when set, names the refusal for a
    caller that tells refusals apart.
    """

    def __init__(
        self,
        detail: str,
        *,
        reader_message: str = "This comparison cannot be shown.",
        code: str = "",
    ) -> None:
        super().__init__(detail)
        self.reader_message = reader_message
        self.code = code


class DiffSource(Protocol):
    async def resolve(self, intent: dict[str, Any]) -> ResolvedComparison: ...

    async def manifest(self, resolved: ResolvedComparison) -> ChangeSetManifest: ...

    async def file_patch(self, resolved: ResolvedComparison, file_id: str) -> FilePatch: ...

    def content(
        self, resolved: ResolvedComparison, file_id: str, side: str
    ) -> AsyncIterator[bytes]: ...
