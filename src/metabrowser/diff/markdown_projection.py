"""Project authoritative Git hunks onto bounded, inert KPress Markdown.

MarkdownIt's top-level source ranges are a witness, checked against the complete KPress
render of each side before any range can label output. Features that change the block
shape without a reliable witness use the exact source diff.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from html import escape
from html.parser import HTMLParser
from typing import Literal, TypedDict
from urllib.parse import unquote

from frontmatter_format import fmf_split_frontmatter
from kpress.format import parse_markdown
from markdown_it import MarkdownIt

from metabrowser.diff.format import FilePatch, LineOp, LineRecord
from metabrowser.inert_html import ANCHOR_PREFIX, harden, is_inside

MARKDOWN_DIFF_VERSION = "markdown-diff-v1"
# A 48 KiB real documentation pair projected in 72 ms warm on the development
# Mac. Bytes alone do not bound MarkdownIt's link-label scan: a 45 KiB nested
# bracket pair took 2.17 s. At 256 openers the slowest measured parse was 16 ms.
# Bound parsing, source-range work, and browser mounting independently.
MARKDOWN_DIFF_MAX_BYTES = 48 * 1024
_MAX_LINE_BYTES = 4 * 1024
_MAX_LINK_OPENERS = 256
_MAX_TOKENS = 2_000
_MAX_NODES = 2_400
_MAX_CODE_BLOCKS = 16
_MAX_INLINE_WORDS = 256

_VOID = frozenset({"br", "hr", "img"})
_HEADINGS = frozenset(f"h{level}" for level in range(1, 7))
_PROSE = _HEADINGS | {"p"}
_COMMENT = re.compile(r"<!--(?:(?!-->).)*-->", re.DOTALL)
_WORDS = re.compile(r"\w+(?:[-’']\w+)*|[^\w\s]+|\s+")
_RewriteLocal = Callable[[str, bool], str | None]


class MarkdownDiffBlock(TypedDict):
    kind: Literal["context", "removed", "added"]
    side: Literal["old", "new"]
    html: str


class MarkdownDiffProjection(TypedDict):
    version: Literal["markdown-diff-v1"]
    status: Literal["ready", "unsupported", "too_large"]
    blocks: list[MarkdownDiffBlock]
    source_only: bool


class _Unsupported(ValueError):
    """The source patch and render could not be mapped with confidence."""


class _OverBudget(ValueError):
    """The projection would exceed its work budget."""


@dataclass(slots=True)
class _Element:
    tag: str
    attrs: tuple[tuple[str, str], ...] = ()
    children: list[_Element | str] = field(default_factory=list)


class _Html(HTMLParser):
    """Read the small already hardened HTML subset without repairing its structure."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.root = _Element("")
        self.stack = [self.root]
        self.nodes = 0
        self.feed(html)
        self.close()
        if len(self.stack) != 1 or any(
            isinstance(node, str) and node.strip() for node in self.root.children
        ):
            raise _Unsupported("incomplete render tree")

    def _count(self) -> None:
        self.nodes += 1
        if self.nodes > _MAX_NODES or len(self.stack) > 32:
            raise _OverBudget("render tree")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._count()
        node = _Element(tag, tuple((key, value or "") for key, value in attrs))
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if self.stack[-1].tag != tag or len(self.stack) == 1:
            raise _Unsupported("unbalanced render tree")
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        children = self.stack[-1].children
        if children and isinstance(last := children[-1], str):
            children[-1] = last + data
        else:
            self._count()
            children.append(data)

    def blocks(self) -> list[_Element]:
        return [node for node in self.root.children if isinstance(node, _Element)]


@dataclass(frozen=True, slots=True)
class _Block:
    start: int
    end: int
    node: _Element
    shape: _Element


def _text(node: _Element) -> str:
    return "".join(
        _text(child) if isinstance(child, _Element) else child for child in node.children
    )


def _shape(node: _Element, *, top: bool = True) -> _Element:
    # KPress wraps tables, treats a standalone image as a figure, and highlights code.
    # These transformations preserve the witness's one top-level source block.
    if len(node.children) == 1 and isinstance(child := node.children[0], _Element):
        if top and (node.tag, child.tag) in {("div", "table"), ("p", "img")}:
            return _shape(child)
        if node.tag == "pre" and child.tag == "code":
            return _Element(
                "pre", children=[_Element("code", children=[_text(child).rstrip("\n")])]
            )
    return _Element(
        node.tag,
        tuple((name, value) for name, value in node.attrs if name != "id"),
        [
            _shape(child, top=False) if isinstance(child, _Element) else child
            for child in node.children
        ],
    )


def _blocks(source: str) -> tuple[list[_Block], int]:
    offset = 0
    if source.startswith(("---\n", "---\r\n")):
        _, body_start, _ = fmf_split_frontmatter(source, strict=False)
        offset = source.count("\n", 0, body_start)
        source = source[body_start:]
    parser = MarkdownIt("js-default", {"html": True})
    env: dict[str, object] = {}
    tokens = parser.parse(source, env)
    work = sum(1 + len(token.children or ()) for token in tokens)
    if (
        work > _MAX_TOKENS
        or sum(token.type in {"fence", "code_block"} for token in tokens) > _MAX_CODE_BLOCKS
    ):
        raise _OverBudget("Markdown tokens")
    ranges: list[tuple[int, int]] = []
    for token in tokens:
        # KPress removes comments in inert output. They have no rendered range;
        # raw markup is outside the versioned Markdown block contract.
        for member in [token, *(token.children or ())]:
            if member.type in {"html_block", "html_inline"} and not _COMMENT.fullmatch(
                member.content.strip()
            ):
                raise _Unsupported("raw HTML has no reliable Markdown projection")
        if token.type == "html_block" or token.level != 0 or token.nesting < 0:
            continue
        span = token.map
        if span is None or span[0] >= span[1] or (ranges and span[0] < ranges[-1][1]):
            raise _Unsupported("unmapped Markdown block")
        ranges.append((span[0], span[1]))
    witness = _Html(harden(parser.renderer.render(tokens, parser.options, env)))
    document_title = ""
    rendered = _Html(
        harden(
            parse_markdown(
                source, title=document_title, trust_mode="sanitized", diagrams="off", math="off"
            ).html
        )
    )
    witness_nodes, rendered_nodes = witness.blocks(), rendered.blocks()
    if len(witness_nodes) != len(ranges) or len(rendered_nodes) != len(ranges):
        raise _Unsupported("KPress block count differs from the range witness")
    blocks: list[_Block] = []
    for (start, end), candidate, actual in zip(ranges, witness_nodes, rendered_nodes, strict=True):
        shape = _shape(actual)
        if _shape(candidate) != shape:
            raise _Unsupported("KPress block structure differs from the range witness")
        blocks.append(_Block(start + offset, end + offset, actual, shape))
    return blocks, rendered.nodes


def _lines(data: bytes | None) -> list[bytes]:
    if not data:
        return []
    # Git line numbers count LF; Python splitlines also splits several Unicode
    # separators, which would shift the witness away from the actual patch.
    result = data.split(b"\n")
    return [line + b"\n" for line in result[:-1]] + (result[-1:] if result[-1] else [])


def _verify_line(record: LineRecord, lines: Sequence[bytes], index: int) -> None:
    if record.text_b64 is not None or index >= len(lines):
        raise _Unsupported("patch does not match the snapshot")
    expected = record.text.encode() + (b"" if record.no_newline else b"\n")
    if lines[index] != expected:
        raise _Unsupported("patch does not match the snapshot")


def _correspondence(
    old: Sequence[bytes], new: Sequence[bytes], patch: FilePatch
) -> tuple[dict[int, int], set[int], set[int]]:
    unchanged: dict[int, int] = {}
    removed: set[int] = set()
    added: set[int] = set()
    left = right = 0

    def match(stop_left: int, stop_right: int) -> None:
        nonlocal left, right
        if (
            stop_left - left != stop_right - right
            or not left <= stop_left <= len(old)
            or not right <= stop_right <= len(new)
            or old[left:stop_left] != new[right:stop_right]
        ):
            raise _Unsupported("patch does not cover the differences")
        unchanged.update(zip(range(left, stop_left), range(right, stop_right), strict=True))
        left, right = stop_left, stop_right

    for hunk in patch.hunks:
        match(hunk.old_start - bool(hunk.old_count), hunk.new_start - bool(hunk.new_count))
        for line in hunk.lines:
            if line.op is LineOp.context:
                _verify_line(line, old, left)
                _verify_line(line, new, right)
                unchanged[left] = right
                left += 1
                right += 1
            elif line.op is LineOp.delete:
                _verify_line(line, old, left)
                removed.add(left)
                left += 1
            else:
                _verify_line(line, new, right)
                added.add(right)
                right += 1
    match(len(old), len(new))
    return unchanged, removed, added


def _matches(
    old: Sequence[_Block], new: Sequence[_Block], unchanged: dict[int, int]
) -> list[tuple[int, int]]:
    right_by_start = {block.start: index for index, block in enumerate(new)}
    matches: list[tuple[int, int]] = []
    for left, block in enumerate(old):
        start = unchanged.get(block.start)
        if start is None or start not in right_by_start:
            continue
        right = right_by_start[start]
        other = new[right]
        if (
            other.end - start == block.end - block.start
            and block.shape == other.shape
            and all(
                unchanged.get(line) == start + line - block.start
                for line in range(block.start, block.end)
            )
        ):
            matches.append((left, right))
    return matches


def _inline_change(
    old: _Element, new: _Element, old_source: str, new_source: str
) -> tuple[_Element, _Element] | None:
    """Mark only a single uniquely located text run in compatible prose blocks."""

    if old.tag not in _PROSE or old.tag != new.tag:
        return None
    changes: list[tuple[tuple[int, ...], str, str]] = []

    def compare(left: _Element, right: _Element, at: tuple[int, ...]) -> bool:
        if (
            left.tag != right.tag
            or tuple(pair for pair in left.attrs if pair[0] != "id")
            != tuple(pair for pair in right.attrs if pair[0] != "id")
            or len(left.children) != len(right.children)
        ):
            return False
        for index, (before, after) in enumerate(zip(left.children, right.children, strict=True)):
            address = (*at, index)
            if isinstance(before, _Element) and isinstance(after, _Element):
                # A link is shown independently on each side and never redlined as
                # though a removed label belonged to the live link.
                if before.tag in {"a", "code", "img"}:
                    if before != after:
                        return False
                elif not compare(before, after, address):
                    return False
            elif isinstance(before, str) and isinstance(after, str):
                if before != after:
                    changes.append((address, before, after))
            else:
                return False
        return True

    if not compare(old, new, ()) or len(changes) != 1:
        return None
    address, before, after = changes[0]
    left, right = _WORDS.findall(before), _WORDS.findall(after)
    if max(len(left), len(right)) > _MAX_INLINE_WORDS:
        return None
    prefix = 0
    for a, b in zip(left, right, strict=False):
        if a != b:
            break
        prefix += 1
    suffix = 0
    for a, b in zip(reversed(left), reversed(right), strict=False):
        if a != b:
            break
        suffix += 1
    if prefix + suffix > min(len(left), len(right)):
        # The unchanged words could have come from either end of a repeated run.
        return None

    old_middle = left[prefix : len(left) - suffix]
    new_middle = right[prefix : len(right) - suffix]
    if {word for word in old_middle if not word.isspace()} & set(new_middle):
        # Multiple or ambiguous edits belong in complete before/after blocks.
        return None

    def pieces(words: list[str], source: str, tag: str) -> list[_Element | str] | None:
        end = len(words) - suffix
        middle = "".join(words[prefix:end])
        if middle and source.count(middle) != 1:
            return None
        result: list[_Element | str] = ["".join(words[:prefix])]
        if middle:
            result.append(_Element(tag, children=[middle]))
        result.append("".join(words[end:]))
        return result

    old_pieces = pieces(left, old_source, "del")
    new_pieces = pieces(right, new_source, "ins")
    if old_pieces is None or new_pieces is None:
        return None

    def replace_run(
        node: _Element, path: tuple[int, ...], content: list[_Element | str]
    ) -> _Element:
        children = list(node.children)
        index = path[0]
        if len(path) == 1:
            children[index : index + 1] = content
        else:
            child = children[index]
            assert isinstance(child, _Element)
            children[index] = replace_run(child, path[1:], content)
        return replace(node, children=children)

    return replace_run(old, address, old_pieces), replace_run(new, address, new_pieces)


def _namespace_ids(blocks: Sequence[_Block], namespace: str, side: str) -> dict[str, str]:
    prefix = ANCHOR_PREFIX + hashlib.sha256(namespace.encode()).hexdigest()[:24] + f"-{side}-"
    ids: dict[str, str] = {}

    def collect(node: _Element) -> None:
        if original := dict(node.attrs).get("id"):
            ids[original] = prefix + original.removeprefix(ANCHOR_PREFIX)
        for child in node.children:
            if isinstance(child, _Element):
                collect(child)

    for block in blocks:
        collect(block.node)
    return ids


def _html(
    node: _Element, ids: dict[str, str], *, removed: bool, rewrite_local: _RewriteLocal | None
) -> str:
    if removed and node.tag == "img":
        return escape(dict(node.attrs).get("alt") or "image", quote=False)
    tag = "span" if removed and node.tag == "a" else node.tag
    attrs: list[str] = []
    for name, value in node.attrs:
        if removed and node.tag == "a":
            continue
        if name == "id":
            value = ids[value]
        elif name == "href" and value.startswith("#"):
            target = ids.get(unquote(value[1:]))
            if target is None:
                continue
            value = "#" + target
        elif name in {"href", "src"} and is_inside(value):
            rewritten = None if rewrite_local is None else rewrite_local(value, name == "src")
            if rewritten is None:
                if node.tag == "img":
                    return escape(dict(node.attrs).get("alt") or "image", quote=False)
                continue
            value = rewritten
        attrs.append(f' {name}="{escape(value)}"')
    start = f"<{tag}{''.join(attrs)}>"
    if tag in _VOID:
        return start
    body = "".join(
        _html(child, ids, removed=removed, rewrite_local=rewrite_local)
        if isinstance(child, _Element)
        else escape(child, quote=False)
        for child in node.children
    )
    return f"{start}{body}</{tag}>"


def _project(
    old: bytes | None,
    new: bytes | None,
    patch: FilePatch,
    namespace: str,
    rewrite_local: _RewriteLocal | None,
) -> tuple[list[MarkdownDiffBlock], bool]:
    before, after = old or b"", new or b""
    if len(before) + len(after) > MARKDOWN_DIFF_MAX_BYTES:
        raise _OverBudget("Markdown input bytes")
    if max(before.count(b"["), after.count(b"[")) > _MAX_LINK_OPENERS:
        raise _OverBudget("Markdown link-label work")
    old_lines, new_lines = _lines(old), _lines(new)
    if max((len(line) for line in (*old_lines, *new_lines)), default=0) > _MAX_LINE_BYTES:
        raise _OverBudget("Markdown line bytes")
    if patch.truncated or any(
        b"\0" in data or b"\r" in data.replace(b"\r\n", b"") for data in (before, after)
    ):
        raise _Unsupported("unmapped Markdown source")
    unchanged, removed, added = _correspondence(old_lines, new_lines, patch)
    old_blocks, old_nodes = _blocks(before.decode())
    new_blocks, new_nodes = _blocks(after.decode())
    nodes = old_nodes + new_nodes
    if nodes > _MAX_NODES:
        raise _OverBudget("combined render tree")
    old_ids = _namespace_ids(old_blocks, namespace, "old")
    new_ids = _namespace_ids(new_blocks, namespace, "new")
    blocks: list[MarkdownDiffBlock] = []
    source_only = False
    left = right = 0
    matches = _matches(old_blocks, new_blocks, unchanged)
    for stop_left, stop_right in (*matches, (len(old_blocks), len(new_blocks))):
        old_group = old_blocks[left:stop_left]
        new_group = new_blocks[right:stop_right]
        old_content = [block.node for block in old_group]
        new_content = [block.node for block in new_group]
        visible_change = [_text(node) for node in old_content] != [
            _text(node) for node in new_content
        ]
        if old_group or new_group:
            source_only |= not visible_change
        if len(old_group) == len(new_group) == 1 and visible_change:
            old_block, new_block = old_group[0], new_group[0]
            old_changed = removed.intersection(range(old_block.start, old_block.end))
            new_changed = added.intersection(range(new_block.start, new_block.end))
            if len(old_changed) == len(new_changed) == 1:
                inline = _inline_change(
                    old_block.node,
                    new_block.node,
                    old_lines[old_changed.pop()].decode(),
                    new_lines[new_changed.pop()].decode(),
                )
                if inline is not None and nodes + 6 <= _MAX_NODES:
                    # Each wrapper can add one element and two text siblings.
                    nodes += 6
                    old_content, new_content = [inline[0]], [inline[1]]
        for block, node in zip(old_group, old_content, strict=True):
            removed.difference_update(range(block.start, block.end))
            blocks.append(
                {
                    "kind": "removed",
                    "side": "old",
                    "html": _html(node, old_ids, removed=True, rewrite_local=None),
                }
            )
        for block, node in zip(new_group, new_content, strict=True):
            added.difference_update(range(block.start, block.end))
            blocks.append(
                {
                    "kind": "added",
                    "side": "new",
                    "html": _html(node, new_ids, removed=False, rewrite_local=rewrite_local),
                }
            )
        if stop_right < len(new_blocks):
            node = new_blocks[stop_right].node
            blocks.append(
                {
                    "kind": "context",
                    "side": "new",
                    "html": _html(node, new_ids, removed=False, rewrite_local=rewrite_local),
                }
            )
        left, right = stop_left + 1, stop_right + 1
    # A blank separator beside an already visible addition or deletion adds no
    # information to the notice. Standalone whitespace changes still point to Source.
    has_visual_change = any(block["kind"] != "context" for block in blocks)
    unmapped = any(old_lines[i].strip() for i in removed) or any(
        new_lines[i].strip() for i in added
    )
    return blocks, source_only or unmapped or (not has_visual_change and bool(removed or added))


def project_markdown_diff(
    *,
    old: bytes | None,
    new: bytes | None,
    patch: FilePatch,
    namespace: str,
    rewrite_local: _RewriteLocal | None = None,
) -> MarkdownDiffProjection:
    """Return a versioned projection; unavailable projections carry no partial HTML.

    Local destinations are inert unless the caller binds them to the head snapshot.
    """

    status: Literal["ready", "unsupported", "too_large"] = "ready"
    blocks: list[MarkdownDiffBlock] = []
    source_only = False
    try:
        blocks, source_only = _project(old, new, patch, namespace, rewrite_local)
    except _OverBudget:
        status = "too_large"
    except (UnicodeError, _Unsupported):
        status = "unsupported"
    return {
        "version": MARKDOWN_DIFF_VERSION,
        "status": status,
        "blocks": blocks,
        "source_only": source_only,
    }
