"""How the structured views read a YAML or JSON file's bytes as text and a stream as one value.

A leaf module: the structured plugin's route (``builtin_plugins/structured/parser.py``)
and a pull request's rendered diff (:mod:`metabrowser.diff.structured_projection`), which
runs in the projection child, both read files this way, and the child imports nothing of
the plugin package, whose ``__init__`` brings in the web framework.
"""

from __future__ import annotations

import io


def decode_text(data: bytes) -> str:
    """*data* as the text a file opened in text mode reads as.

    That is how 0.11.0 read a file, and what its answers depend on: a byte that is
    not UTF-8 becomes U+FFFD and the rest still parses, so a Latin-1 file opens as a
    tree; and CRLF and a lone CR read as LF, so a parse error counts lines and columns
    as an editor does. Decoding strictly turned the first into a `UnicodeDecodeError`
    and a Source view. A leading byte order mark is kept, as it was.
    """

    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="replace").read()


def collapse_yaml_documents(docs: list[object]) -> object:
    """Reduce a YAML document stream to a single tree-renderable value.

    A lone document renders as itself. A multi-document stream renders as a
    list, after dropping empty (``None``) documents — these are usually a
    trailing ``---`` followed only by comments. If exactly one real document
    remains it renders bare, not as a one-element list.
    """

    if len(docs) <= 1:
        return docs[0] if docs else None
    meaningful = [doc for doc in docs if doc is not None]
    if len(meaningful) == 1:
        return meaningful[0]
    return meaningful or None
