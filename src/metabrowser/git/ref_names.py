"""Validate Git ref names without opening a repository or running Git."""

from __future__ import annotations

from typing import Final

# Git's own bound on a ref name is the file system's; this is the record bound for one.
_REF_NAME_MAX_BYTES: Final = 1024
_REF_FORBIDDEN = frozenset(" ~^:?*[\\\x7f")


def is_valid_ref_name(name: str) -> bool:
    """Git's ``check-ref-format`` rules, for a short name or a full one under ``refs/``.

    No empty component, none that begins with ``.`` or ends with ``.lock``; no ``..``,
    ``@{``, control character, space, ``~ ^ : ? * [ \\``; not ``@`` alone; no ``.`` or
    ``/`` at the end; encodable as UTF-8 and at most 1024 bytes. Checked here rather
    than by running Git, so a name is refused before any process sees it.
    """

    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if len(encoded) > _REF_NAME_MAX_BYTES:
        return False
    if not name or name == "@" or name.endswith((".", "/")) or name.startswith("/"):
        return False
    if ".." in name or "@{" in name:
        return False
    if any(ord(ch) < 0x20 or ch in _REF_FORBIDDEN for ch in name):
        return False
    return all(
        part and not part.startswith(".") and not part.endswith(".lock") for part in name.split("/")
    )
