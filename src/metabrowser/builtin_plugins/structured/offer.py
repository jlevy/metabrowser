"""Where the structured kind offers its Table view: a document that starts as a list of
records.

The record-list source (records.py) reads a list of mappings, and a JSON or YAML file
that is not one has no table to show. The server asks :func:`offers_table` before it
lists a file's views (the manifest's ``offer``), so such a file has no Table tab at
all, rather than a tab that says it does not apply.

The question is answered from the file's leading bytes, never a parse of the whole
file: every response that lists a file's views asks it, the hover prefetch among them,
and a whole YAML parse takes seconds (records.py measured 5 s for 1 MiB). So it reads
only as far as the shape is decided:

- JSON: the first value is a list and its first item a mapping.
- YAML: the first document's root is a list whose first item is a mapping, or a mapping
  that a second document, also a mapping, follows; the structured parse reads several
  documents as the list of them (``collapse_yaml_documents``).

A file that starts as a list of records and turns out not to be one, a later item that
is not a mapping or a parse error further on, is still offered, and its Table view says
why the source refused it.
"""

from __future__ import annotations

from collections.abc import Iterator

import yaml

# The most of a YAML file's start read for its shape: as much as the content predicates
# that classify a file read of a YAML prefix (`_YAML_PREFIX_BYTES` in
# plugin_loader/classify.py). Every offer is decided within a document's first item, or
# for a mapping by the start of the next document. A first document longer than this is
# taken as the only one, so the rare stream whose first document is larger has no Table
# tab. A 16 KiB mapping, the case that reads all of it, took 2.9 ms with libyaml and 34 ms
# with PyYAML's Python parser, and a list of records or a stream of small documents was
# settled in under 0.3 ms with either (best of 30, Python 3.14, a 10-core arm64 Mac at a
# load average of 130 to 170, 2026-11-24). The JSON check reads a few bytes, under 1 µs.
OFFER_YAML_PREFIX_BYTES = 16 * 1024

_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

_JSON_SPACE = b" \t\r\n"
_UTF8_BOM = b"\xef\xbb\xbf"

_MAP_TAGS = frozenset({None, "!", "tag:yaml.org,2002:map"})
_SEQ_TAGS = frozenset({None, "!", "tag:yaml.org,2002:seq"})
_OMAP_TAG = "tag:yaml.org,2002:omap"
_NULL_PLAIN = frozenset({"", "~", "null", "Null", "NULL"})


def offers_table(prefix: bytes, ext: str) -> bool:
    """Whether a structured file whose leading bytes are *prefix* starts as a list of
    records."""

    if ext == ".json":
        return _json_starts_records(prefix)
    if ext in (".yaml", ".yml"):
        return _yaml_starts_records(prefix[:OFFER_YAML_PREFIX_BYTES])
    return False


def _json_starts_records(data: bytes) -> bool:
    data = data.removeprefix(_UTF8_BOM)
    at = _skip_json_space(data, 0)
    if data[at : at + 1] != b"[":
        return False
    at = _skip_json_space(data, at + 1)
    return data[at : at + 1] == b"{"


def _skip_json_space(data: bytes, at: int) -> int:
    """The index past whitespace and the comments the JSONC dialect allows, which the
    structured parse reads through ``json5`` (``parser._parse_text``)."""

    while at < len(data):
        if data[at] in _JSON_SPACE:
            at += 1
        elif data.startswith(b"//", at):
            end = data.find(b"\n", at)
            at = len(data) if end < 0 else end + 1
        elif data.startswith(b"/*", at):
            end = data.find(b"*/", at + 2)
            at = len(data) if end < 0 else end + 2
        else:
            break
    return at


class _Unsettled(Exception):
    """The prefix ended before the document's shape was settled."""


def _yaml_starts_records(data: bytes) -> bool:
    # A cut prefix can end inside a character; that only touches the text the cut ends.
    events = yaml.parse(data.decode("utf-8", errors="replace"), Loader=_LOADER)
    try:
        return _stream_starts_records(events)
    except (yaml.YAMLError, _Unsettled):
        # Malformed within the prefix, or cut before its shape is settled.
        return False
    finally:
        events.close()


def _stream_starts_records(events: Iterator[yaml.Event]) -> bool:
    after_mapping = False  # a document that is a mapping came first
    for event in events:
        if not isinstance(event, yaml.DocumentStartEvent):
            continue
        root = _next(events)
        if _is_null(root):
            continue  # an empty document, which the parse leaves out
        if isinstance(root, yaml.SequenceStartEvent) and root.tag in _SEQ_TAGS:
            # A list among several documents is not a record.
            return not after_mapping and _is_mapping(_next(events))
        if not _is_mapping(root):
            return False
        if after_mapping:
            return True
        after_mapping = True
        _skip_collection(events)
    return False


def _next(events: Iterator[yaml.Event]) -> yaml.Event:
    event = next(events, None)
    if event is None:
        raise _Unsettled
    return event


def _is_mapping(event: yaml.Event) -> bool:
    """Whether a node's first event starts a mapping: one in either style, or an ordered
    map, a list of one-key mappings that the parse reads as one mapping."""

    if isinstance(event, yaml.MappingStartEvent):
        return event.tag in _MAP_TAGS
    return isinstance(event, yaml.SequenceStartEvent) and event.tag == _OMAP_TAG


def _is_null(event: yaml.Event) -> bool:
    if not isinstance(event, yaml.ScalarEvent):
        return False
    if event.tag == "tag:yaml.org,2002:null":
        return True
    return event.tag is None and event.implicit[0] and event.value in _NULL_PLAIN


def _skip_collection(events: Iterator[yaml.Event]) -> None:
    """Read to the end of the collection whose start was just read."""

    depth = 1
    for event in events:
        if isinstance(event, yaml.CollectionStartEvent):
            depth += 1
        elif isinstance(event, yaml.CollectionEndEvent):
            depth -= 1
            if depth == 0:
                return
    raise _Unsettled
