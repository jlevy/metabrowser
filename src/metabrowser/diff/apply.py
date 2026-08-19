"""The File Diff Format correctness oracle.

A fully hydrated change set applied to its base tree must reproduce the
target tree — entries, modes, entry types, and exact bytes, including a
missing final newline. A document that cannot be applied must have said
so through ``availability``; ``NotFullyHydrated`` raised for a ``ready``
file is a producer bug, which is exactly what the oracle exists to catch.

Trees here are the corpus representation: a flat mapping of
'/'-separated paths to typed entries with inline content. The git
fixtures materialize real repositories into the same shape so the oracle
can compare a produced document against what git itself did.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from metabrowser.diff.format import (
    Availability,
    ChangeKind,
    ChangeSetDocument,
    EntryType,
    FileChange,
    FilePatch,
    LineOp,
)


class ApplyError(Exception):
    """The document contradicts the base tree it claims to change."""


class NotFullyHydrated(ApplyError):
    """A change needs content the document neither carries nor can resolve."""


@dataclass(frozen=True)
class TreeEntry:
    entry_type: EntryType
    mode: str
    content: bytes

    def as_corpus(self) -> dict[str, str]:
        return {
            "entry_type": self.entry_type.value,
            "mode": self.mode,
            "content_b64": b64encode(self.content).decode("ascii"),
        }


@dataclass
class TreeSnapshot:
    """A flat, path-keyed tree; the corpus 'entries' shape."""

    entries: dict[str, TreeEntry] = field(default_factory=dict)

    @classmethod
    def from_corpus(cls, raw: dict[str, Any]) -> TreeSnapshot:
        entries: dict[str, TreeEntry] = {}
        for path, entry in raw["entries"].items():
            entries[path] = TreeEntry(
                entry_type=EntryType(entry["entry_type"]),
                mode=entry["mode"],
                content=b64decode(entry["content_b64"]),
            )
        return cls(entries=entries)

    def as_corpus(self) -> dict[str, Any]:
        return {
            "entries": {path: entry.as_corpus() for path, entry in sorted(self.entries.items())}
        }

    def tree_hash(self) -> str:
        """Canonical digest over paths, types, modes, and exact bytes."""
        digest = sha256()
        for path, entry in sorted(self.entries.items()):
            digest.update(path.encode("utf-8", "surrogateescape"))
            digest.update(b"\0")
            digest.update(entry.entry_type.value.encode("ascii"))
            digest.update(entry.mode.encode("ascii"))
            digest.update(b"\0")
            digest.update(sha256(entry.content).digest())
        return digest.hexdigest()


ContentResolver = Callable[[FileChange, str], bytes]
"""Reads referenced content for (change, side); side is 'old' or 'new'."""


def _no_resolver(change: FileChange, side: str) -> bytes:
    raise NotFullyHydrated(f"change {change.id!r} needs {side} content and no resolver was given")


def _line_bytes(record: Any) -> bytes:
    if record.text_b64 is not None:
        return b64decode(record.text_b64)
    return record.text.encode("utf-8")


def _patched_content(change: FileChange, patch: FilePatch, old: bytes) -> bytes:
    """Replay hunks over the old bytes, byte-exactly.

    Old content is split into newline-terminated segments; the final
    segment's missing newline is what ``no_newline`` on a ``del`` or
    ``context`` line asserts, and on an ``add`` line what the output
    reproduces.
    """
    old_lines = old.split(b"\n")
    trailing_newline = old_lines and old_lines[-1] == b""
    if trailing_newline:
        old_lines.pop()
    out: list[bytes] = []
    out_no_newline = False
    cursor = 0  # index into old_lines, 0-based
    for hunk in patch.hunks:
        anchor = max(hunk.old_start - 1, 0)
        if anchor < cursor:
            raise ApplyError(f"change {change.id!r}: hunks overlap or are out of order")
        out.extend(old_lines[cursor:anchor])
        cursor = anchor
        for record in hunk.lines:
            if record.op is LineOp.add:
                out.append(_line_bytes(record))
                if record.no_newline:
                    out_no_newline = True
            else:
                if cursor >= len(old_lines):
                    raise ApplyError(
                        f"change {change.id!r}: hunk consumes line {cursor + 1}, past the end"
                    )
                expected = _line_bytes(record)
                if old_lines[cursor] != expected:
                    raise ApplyError(
                        f"change {change.id!r}: line {cursor + 1} does not match the hunk"
                    )
                if record.op is LineOp.context:
                    out.append(old_lines[cursor])
                    if record.no_newline:
                        out_no_newline = True
                cursor += 1
    out.extend(old_lines[cursor:])
    if not out:
        return b""
    tail_newline = trailing_newline if cursor < len(old_lines) or not patch.hunks else True
    if out_no_newline:
        tail_newline = False
    body = b"\n".join(out)
    return body + b"\n" if tail_newline else body


def apply_file_change(
    change: FileChange,
    patch: FilePatch | None,
    base_entry: TreeEntry | None,
    resolve_content: ContentResolver = _no_resolver,
) -> TreeEntry | None:
    """One change against one base entry; None means the path ends deleted."""
    if change.availability is not Availability.ready:
        raise NotFullyHydrated(
            f"change {change.id!r} is {change.availability.value}, not applicable"
        )
    if change.kind is ChangeKind.deleted:
        if base_entry is None:
            raise ApplyError(f"change {change.id!r} deletes a path the base does not have")
        # A delete still asserts what it removes: replaying the hunks over the
        # base must consume the whole file, exactly as `git apply` checks.
        if not change.binary and patch is not None:
            remnant = _patched_content(change, patch, base_entry.content)
            if remnant != b"":
                raise ApplyError(
                    f"change {change.id!r}: delete patch does not consume the whole file"
                )
        return None
    new = change.new
    assert new is not None  # guaranteed by the model's side rules
    if change.binary:
        return TreeEntry(new.entry_type, new.mode.value, resolve_content(change, "new"))
    if change.kind is ChangeKind.added:
        old_bytes = b""
    elif base_entry is None:
        raise ApplyError(f"change {change.id!r} modifies a path the base does not have")
    else:
        old_bytes = base_entry.content
    if patch is None:
        raise NotFullyHydrated(f"change {change.id!r} is ready but its patch is absent")
    return TreeEntry(new.entry_type, new.mode.value, _patched_content(change, patch, old_bytes))


def apply_change_set(
    document: ChangeSetDocument,
    base: TreeSnapshot,
    resolve_content: ContentResolver = _no_resolver,
) -> TreeSnapshot:
    """The oracle: base tree in, target tree out, or a precise refusal."""
    result = TreeSnapshot(entries=dict(base.entries))
    for change in document.manifest.files:
        patch = document.patches.get(change.id)
        old_path = change.old.path if change.old is not None else None
        new_path = change.new.path if change.new is not None else None
        base_entry = result.entries.get(old_path) if old_path is not None else None
        produced = apply_file_change(change, patch, base_entry, resolve_content)
        consumes_old = change.kind in (
            ChangeKind.deleted,
            ChangeKind.modified,
            ChangeKind.renamed,
            ChangeKind.type_changed,
        )
        if consumes_old and old_path is not None:
            result.entries.pop(old_path, None)
        if produced is not None and new_path is not None:
            result.entries[new_path] = produced
    return result
