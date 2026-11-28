"""An ordered page of children of an addressed JSON or YAML node, with original byte ranges."""

from __future__ import annotations

import io
import json
import re
from collections import deque
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from itertools import islice
from typing import Any, Literal

from ruamel.yaml import YAML
from ruamel.yaml.composer import MaxDepthExceededError
from ruamel.yaml.error import MarkedYAMLError, YAMLError
from ruamel.yaml.events import AliasEvent
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from metabrowser.diff.structured_projection import (
    _MAX_NODES,
    JSONC_MAX_BYTES,
    SLOW_PARSE_MAX_BYTES,
    STRUCTURED_DIFF_MAX_BYTES,
)
from metabrowser.diff.structured_projection import (
    _MAX_YAML_NODES as STRUCTURED_YAML_MAX_NODES,
)
from metabrowser.frontmatter_yaml import YAML_MAX_DEPTH, _Composer, _NodeBudgetError

type Format = Literal["json", "yaml"]
type Segment = str | int

PAGE_MAX = 100
INLINE_DEPTH_MAX = 4
_JSON_SPACE = re.compile(r"[ \t\r\n]*")
_NUMERIC = re.compile(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?")
_PREFIX = "tag:yaml.org,2002:"


@dataclass(slots=True)
class _Value:
    kind: str
    value: str | bool | None
    start: int = field(compare=False)
    end: int = field(compare=False)
    children: dict[Segment, _Value] | None = None
    key_start: int | None = field(default=None, compare=False)
    yaml_node: Node | None = field(default=None, compare=False, repr=False)


class _Refusal(ValueError):
    def __init__(self, reason: str, position: int = 0, *, budget: bool = False) -> None:
        super().__init__(reason)
        self.position = position
        self.budget = budget


def projection_byte_limit(format: Format) -> int:
    """Reuse the measured input bounds of the structured diff's parsers."""
    return STRUCTURED_DIFF_MAX_BYTES if format == "json" else SLOW_PARSE_MAX_BYTES


def _mask_jsonc(text: str) -> str:
    """Mask extensions with one space per code point, keeping marks in original text."""
    decoder = json.JSONDecoder()
    masked = list(text)
    pos = 0
    previous = ""
    comma = None
    while pos < len(text):
        char = text[pos]
        if char in " \t\r\n":
            pos += 1
            continue
        if text.startswith(("//", "/*"), pos):
            if text[pos + 1] == "/":
                stop = pos + 2
                while stop < len(text) and text[stop] not in "\r\n":
                    stop += 1
            else:
                close = text.find("*/", pos + 2)
                if close < 0:
                    raise _Refusal("Unterminated JSON block comment", pos)
                stop = close + 2
            masked[pos:stop] = re.sub(r"[^\r\n]", " ", text[pos:stop])
            pos = stop
            continue
        if char in "]}" and comma is not None:
            masked[comma] = " "
        # A trailing comma must follow a value. Strict JSON validates everything
        # else, including the delimiter type and the syntax of that value.
        comma = pos if char == "," and previous and previous in '"0123456789el}]' else None
        previous = char
        if char == '"':
            _, pos = decoder.raw_decode(text, pos)
        else:
            pos += 1
    return "".join(masked)


def _json(text: str, byte_count: int) -> _Value:
    # Validate punctuation and closing delimiters with the standard decoder. Then walk
    # the same grammar retaining offsets and number tokens; no numeric coercion at either pass.
    decoder = json.JSONDecoder(parse_int=str, parse_float=str)
    try:
        decoder.decode(text)
    except json.JSONDecodeError as exc:
        if byte_count > JSONC_MAX_BYTES:
            raise _Refusal("JSONC retry exceeds its byte budget", exc.pos, budget=True) from exc
        text = _mask_jsonc(text)
        decoder.decode(text)
    nodes = 0

    def read(start: int, depth: int) -> _Value:
        nonlocal nodes
        nodes += 1
        if depth > YAML_MAX_DEPTH or nodes > _MAX_NODES:
            raise _Refusal("JSON exceeds the projection budget", start, budget=True)
        token = text[start]
        if token not in "[{":
            scalar, end = decoder.raw_decode(text, start)
            if token in "-0123456789":
                if text[start:end] == "-Infinity":
                    raise _Refusal("Non-finite JSON number", start)
                return _Value("number", text[start:end], start, end)
            if token == '"':
                return _Value("string", _unicode(scalar, start), start, end)
            if isinstance(scalar, float):
                raise _Refusal("Non-finite JSON number", start)
            return _Value("null" if scalar is None else "boolean", scalar, start, end)
        children: dict[Segment, _Value] = {}
        pos = _skip(text, start + 1)
        while text[pos] not in "]}":
            key_start = pos if token == "{" else None
            segment: Segment = len(children)
            if token == "{":
                name, end = decoder.raw_decode(text, pos)
                segment = _unicode(name, pos)
                if segment in children:
                    raise _Refusal("Duplicate mapping key", pos)
                pos = _skip(text, _skip(text, end) + 1)
            child = read(pos, depth + 1)
            child.key_start = key_start
            children[segment] = child
            pos = _skip(text, child.end)
            if text[pos] == ",":
                pos = _skip(text, pos + 1)
        return _Value("array" if token == "[" else "object", None, start, pos + 1, children)

    return read(_skip(text, 0), 0)


def _skip(text: str, start: int) -> int:
    match = _JSON_SPACE.match(text, start)
    assert match is not None
    return match.end()


def _unicode(value: str, pos: int) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise _Refusal("Unpaired Unicode surrogate", pos) from exc
    return value


class _SourceComposer(_Composer):
    """An alias has its own token range but aliases resolve to the anchor's composed node."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.parser.check_event(AliasEvent):
            mark = self.parser.peek_event().start_mark
            raise _Refusal("YAML aliases are unavailable in the ordered projection", mark.index)
        return super().compose_node(parent, index)


def _yaml(text: str, *, keep_source: bool = False) -> list[_Value]:
    # Only compose nodes. No constructor runs, including for an explicit tag.
    yaml = YAML(typ="safe", pure=True)
    yaml.Composer = _SourceComposer
    yaml.max_depth = YAML_MAX_DEPTH
    yaml.composer.nodes_left = STRUCTURED_YAML_MAX_NODES

    def read(node: Node) -> _Value:
        value = build(node)
        if keep_source:
            value.yaml_node = node
        return value

    def build(node: Node) -> _Value:
        start, end = node.start_mark.index, node.end_mark.index
        tag = node.tag.removeprefix(_PREFIX) if node.tag.startswith(_PREFIX) else ""
        children: dict[Segment, _Value] = {}
        if isinstance(node, MappingNode) and tag == "map":
            for key, child in node.value:
                field = read(key)
                if field.kind != "string" or not isinstance(field.value, str):
                    raise _Refusal("Mapping keys must be strings", field.start)
                if field.value in children:
                    raise _Refusal("Duplicate mapping key", field.start)
                value = read(child)
                value.key_start = field.start
                children[field.value] = value
            return _Value("object", None, start, end, children)
        if isinstance(node, SequenceNode) and tag == "seq":
            return _Value("array", None, start, end, {i: read(v) for i, v in enumerate(node.value)})
        if isinstance(node, ScalarNode):
            value = node.value
            if tag == "str":
                return _Value("string", _unicode(value, start), start, end)
            if tag == "null" and value.lower() in {"null", "~", ""}:
                return _Value("null", None, start, end)
            if tag == "bool" and value.lower() in {"true", "false"}:
                return _Value("boolean", value.lower() == "true", start, end)
            if (tag == "int" and re.fullmatch(r"[-+]?[0-9]+", value)) or (
                tag == "float" and _NUMERIC.fullmatch(value)
            ):
                return _Value("number", value, start, end)
        raise _Refusal("Unsupported YAML tag or scalar spelling", start)

    docs: list[_Value] = []
    for root in yaml.compose_all(text):
        if yaml.resolver.processing_version != (1, 2):
            raise _Refusal("Only YAML 1.2 is supported", root.start_mark.index)
        docs.append(read(root))
    return docs


def _copy_row(text: str, node: _Value, key: Segment | None, parent: _Value | None) -> str:
    """Copy a complete value or a single-field mapping, preserving authored syntax where possible."""
    start = node.key_start if node.key_start is not None else node.start
    fragment = text[start : node.end]
    member = isinstance(key, str)
    if node.yaml_node is None:
        return "{" + fragment + "}" if member else fragment

    if not member and node.kind == "null" and not fragment:
        return "null"
    expected = _Value("object", None, 0, 0, {key: node}) if isinstance(key, str) else node
    if (
        member
        and parent
        and isinstance(parent.yaml_node, MappingNode)
        and parent.yaml_node.flow_style
    ):
        fragment = "{" + fragment + "}"
    elif "\n" in fragment or "\r" in fragment:
        # Restore the first token's column. Further lines already have their original
        # indentation, including indentation that contributes to a block scalar's value.
        line_start = max(text.rfind("\n", 0, start), text.rfind("\r", 0, start)) + 1
        fragment = " " * (start - line_start) + fragment
    try:
        if _yaml(fragment) == [expected]:
            return fragment
    except (YAMLError, AssertionError, ValueError, OverflowError, RecursionError, _NodeBudgetError):
        # Context can be essential, e.g. an explicit mapping key or empty scalar in a list.
        pass
    # The original composed nodes retain scalar tags and full-precision numeric tokens.
    # Let the YAML emitter choose indentation and quoting for their new standalone context.
    source = node.yaml_node
    if isinstance(key, str):
        source = MappingNode(_PREFIX + "map", [(ScalarNode(_PREFIX + "str", key), source)])
    out = io.StringIO()
    YAML(typ="safe", pure=True).serialize(source, out)
    return out.getvalue()


def _tree_value(node: _Value) -> object:
    """The legacy Tree accepts native JSON values. Keep inexact browser numbers as text."""
    if node.children is not None:
        if node.kind == "array":
            return [_tree_value(child) for child in node.children.values()]
        return {key: _tree_value(child) for key, child in node.children.items()}
    if node.kind != "number" or not isinstance(node.value, str):
        return node.value
    try:
        decimal = Decimal(node.value)
        value = float(decimal)
        if decimal == decimal.to_integral_value():
            return node.value if decimal.copy_abs() > 2**53 - 1 else int(decimal)
        if Decimal(str(value)) == decimal:
            return value
    except (InvalidOperation, OverflowError):
        pass
    return node.value


def _summary(node: _Value, offsets: list[int]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "kind": node.kind,
        "child_count": len(node.children or {}),
        "source_range": {"start_byte": offsets[node.start], "end_byte": offsets[node.end]},
    }
    if node.children is None:
        result["value"] = node.value
    return result


type _Branch = tuple[dict[str, Any], Iterator[tuple[Segment, _Value]]]


def _inline_rows(
    page: Iterable[tuple[Segment, _Value]], offsets: list[int], depth: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    level: deque[_Branch] = deque()
    for segment, value in page:
        node = _summary(value, offsets)
        rows.append({"segment": segment, "node": node})
        if depth > 1 and value.children:
            level.append((node, iter(value.children.items())))

    # Reserve the full root page before sharing its remaining row budget. At each
    # depth a branch draws one row per turn, so a wide first branch cannot crowd
    # its siblings out. Each branch's own rows stay in source order.
    remaining = PAGE_MAX - len(rows)
    for layer in range(2, depth + 1):
        next_level: deque[_Branch] = deque()
        while level and remaining:
            parent, entries = level.popleft()
            entry = next(entries, None)
            if entry is None:
                continue
            segment, value = entry
            node = _summary(value, offsets)
            parent.setdefault("children", []).append({"segment": segment, "node": node})
            remaining -= 1
            level.append((parent, entries))
            if layer < depth and value.children:
                next_level.append((node, iter(value.children.items())))
        level = next_level
    return rows


def project_structured(
    data: bytes,
    format: Format,
    *,
    document: int = 0,
    path: Sequence[Segment] = (),
    offset: int = 0,
    limit: int = 50,
    depth: int = 1,
    copy_row: bool = False,
    tree: bool = False,
) -> dict[str, Any]:
    """Return one node and a page of immediate children. Ranges are half-open UTF-8 bytes.

    The number value is its decimal token as text, including its precision and exponent.
    Source reads use the exact bytes from the same revision. Empty YAML documents in a
    stream occupy their own index, including a trailing explicit empty document.
    """
    if (
        format not in ("json", "yaml")
        or document < 0
        or offset < 0
        or not 1 <= limit <= PAGE_MAX
        or type(depth) is not int
        or not 1 <= depth <= INLINE_DEPTH_MAX
    ):
        return {"status": "invalid", "diagnostic": "Invalid projection parameters"}
    if len(path) > YAML_MAX_DEPTH or len(data) > projection_byte_limit(format):
        return {"status": "too_large", "diagnostic": "Projection input exceeds its budget"}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {"status": "invalid", "diagnostic": "Invalid UTF-8", "error_byte": exc.start}
    offsets = [0]
    for char in text:
        offsets.append(offsets[-1] + len(char.encode("utf-8")))
    try:
        docs = [_json(text, len(data))] if format == "json" else _yaml(text, keep_source=copy_row)
    except _Refusal as exc:
        return {
            "status": "too_large" if exc.budget else "invalid",
            "diagnostic": str(exc),
            "error_byte": offsets[exc.position],
        }
    except (_NodeBudgetError, MaxDepthExceededError, RecursionError):
        return {"status": "too_large", "diagnostic": "Projection exceeds its node or depth budget"}
    except json.JSONDecodeError as exc:
        return {"status": "invalid", "diagnostic": exc.msg, "error_byte": offsets[exc.pos]}
    except MarkedYAMLError as exc:
        error: dict[str, Any] = {"status": "invalid", "diagnostic": "Invalid YAML"}
        if exc.problem_mark is not None:
            error["error_byte"] = offsets[min(exc.problem_mark.index, len(text))]
        return error
    except (YAMLError, AssertionError, ValueError, OverflowError):
        # ruamel also raises AssertionError and ValueError for malformed directives.
        return {"status": "invalid", "diagnostic": "Invalid structured document"}

    missing = {"status": "missing", "document_count": len(docs)}
    if document >= len(docs):
        return missing
    node = docs[document]
    parent = None
    for part in path:
        if type(part) not in (str, int) or node.children is None or part not in node.children:
            return missing
        parent, node = node, node.children[part]
    children = node.children or {}
    page = islice(children.items(), min(offset, len(children)), min(offset + limit, len(children)))
    return {
        **(
            {"copy_text": _copy_row(text, node, path[-1] if path else None, parent)}
            if copy_row
            else {}
        ),
        **({"tree_value": _tree_value(node)} if tree else {}),
        "status": "ready",
        "document_count": len(docs),
        "record_table": (
            len(docs) == 1
            and not path
            and node.kind == "array"
            and bool(children)
            and all(child.kind == "object" for child in children.values())
        ),
        "node": _summary(node, offsets),
        "children": _inline_rows(page, offsets, depth),
        "next_offset": offset + limit if offset + limit < len(children) else None,
    }
