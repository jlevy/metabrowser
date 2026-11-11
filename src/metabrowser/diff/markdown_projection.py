"""Project authoritative Git hunks onto bounded, inert KPress Markdown.

Each side is parsed once, by the MarkdownIt core KPress itself builds, so a block's
source range is the map of the very token that renders it. Every top-level block is
rendered from its own tokens, and the blocks pass KPress's post-processing, its
sanitizer and :func:`metabrowser.inert_html.harden` together, separated by a character
the source may not contain, so a rendered block is known to come from its range and
heading anchors are numbered across the document exactly as the Document view numbers
them. ``tests/test_markdown_diff_projection.py`` checks that the joined blocks equal
KPress's own ``parse_markdown`` render, so a KPress release that changes this pipeline
fails there rather than here. Features that change the block shape without a reliable
range use the exact source diff.

Whatever a block's source says that its render does not show -- a link or image
destination, a title, alt text under a shown image, an HTML comment, an attribute or a
fence's info string -- is its *hidden* signature. A changed block whose hidden signature
differs from the other side's carries ``source_only``, and so does the whole projection
when any source change has no visible counterpart, so the Rendered view never presents
a change as complete while the source says more.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from html import escape
from html.parser import HTMLParser
from typing import Literal, TypedDict
from urllib.parse import unquote

from frontmatter_format import fmf_split_frontmatter
from kpress.format.markdown import (
    _mark_standalone_image_figures,
    _markdown_it,
    _postprocess_html,
)
from kpress.format.sanitize import sanitize_raw_html
from markdown_it.token import Token
from pygments.lexers import get_all_lexers

from metabrowser.diff.format import FilePatch, Hunk, LineOp, LineRecord
from metabrowser.inert_html import ALLOWED_TAGS, ANCHOR_PREFIX, harden, is_inside

MARKDOWN_DIFF_VERSION = "markdown-diff-v1"
# Measured on the development Mac (Python 3.14, warm, minimum of three runs, load
# average 2-5 from other agents) over the 434 Markdown pairs this repository's last 200
# Markdown-touching first-parent commits made, each at most this many combined bytes:
# p50 12 ms, p90 31-33 ms, max 49-51 ms, against p50 26-27 ms, p90 52-54 ms and max
# 87-89 ms in adjacent runs of the earlier two-parse pipeline with highlighting.
# The slowest input found inside every budget is a 48 KiB side of `<`, 222 ms (258-268 ms
# at load average 17-18, as at round 2 of #349); `&#` took 188 ms and `<!-` 167 ms, the
# same at 128-byte, 1 KiB and 4 KiB lines, and in a worker process they delay no other
# request. Line length changed no measured cost (tables, prose and code at 1-23 KiB
# lines are linear in bytes), so lines are not bounded on their own. Bytes alone do not
# bound MarkdownIt's link-label scan: a 45 KiB nested bracket pair took 2.17 s.
MARKDOWN_DIFF_MAX_BYTES = 48 * 1024
# A side's `[` count: nested openers parsed in 15 ms at 256, 31 ms at 512, 62 ms at 1,024.
_MAX_LINK_OPENERS = 256
# A side's lines that open or close a `:::` container. KPress's container rules rescan
# each one, and a run of them parses into a handful of tokens, so the token budget cannot
# refuse it early: 256 lines took 11.5 ms, 1,024 took 42 ms, and 11,000 (44 KB) took
# 456 ms to refuse (load average 19). A real document holds a few dozen.
_MAX_CONTAINER_LINES = 256
# Tokens plus inline children per side. Dense inline Markdown costs about 11 us a token:
# 2,324 took 26 ms, 4,662 took 52 ms and 9,324 took 103 ms. Of the 434 real pairs, 6
# exceed it, generated tables and reference lists. The refusal comes after the parse:
# 44 KB of one-line headings took 148 ms to refuse, of setext headings 130 ms, and of
# thematic breaks 88 ms (load average 19).
_MAX_TOKENS = 2_000
# Rendered elements and text nodes, both sides together. The 383 real pairs that project
# hold p50 478, p90 1,355 and at most 2,355; 6 more exceed it. Highlighting, now gone,
# added 34% to a render's nodes. In headless Chrome a 1,426-node answer built in
# 1.6-1.7 ms with 4.3-4.6 ms of layout (review C of #349), so the server's parse, which
# the token budget bounds first, is the binding cost, and this bounds the page. Code
# blocks need no budget of their own once unhighlighted: 400 one-line fences projected
# in 23 ms, and 1,600 are refused before rendering in 16 ms (93 ms unbounded).
_MAX_NODES = 2_400
# The changed span of one text node, in words, spaces and punctuation runs, after the
# shared ends are trimmed. difflib is quadratic: 256 tokens diffed in 1.6 ms of prose
# and 2.9 ms of one repeated token, 512 in 6.4-13 ms, 1,024 in 26-58 ms. The products of
# the spans compared, summed over a projection, stop at four such diffs.
_MAX_INLINE_WORDS = 256
_MAX_INLINE_WORK = 4 * _MAX_INLINE_WORDS * _MAX_INLINE_WORDS

_VOID = frozenset({"br", "hr", "img"})
_CONTAINERS = frozenset({"bullet_list_open", "ordered_list_open", "blockquote_open"})
# Blocks whose lines can hold a link reference definition that renders nothing.
_HOLDERS = _CONTAINERS | {"list_item_open"}
# Native attributes the render shows; every other token attribute is source-only.
_SHOWN_ATTRIBUTES = frozenset({"start", "style"})
# The attributes MarkdownIt writes itself; an attribute outside these came from KPress's
# attribute syntax and is content the reader cannot see.
_NATIVE_ATTRIBUTES = {
    "link_open": frozenset({"href", "title"}),
    "image": frozenset({"src", "alt", "title"}),
    "ordered_list_open": frozenset({"start"}),
    "th_open": frozenset({"style"}),
    "td_open": frozenset({"style"}),
}
_COMMENT = re.compile(r"<!--(?:(?!-->).)*-->", re.DOTALL)
# A fence info string that is exactly one of these names says nothing the page hides:
# an alias of a lexer Pygments ships, which the Document view highlights by that name, a
# language KPress draws as a diagram, or a common single word too short to carry an
# instruction (review F of #349 found these among added fences elsewhere). Any other info
# string, an unknown single word included, is text no render shows. Pygments 2.20's 920
# aliases took 0.15 ms to collect once KPress had imported Pygments.
_FENCE_LANGUAGES = frozenset(
    {alias.lower() for _, aliases, _, _ in get_all_lexers(plugins=False) for alias in aliases}
    | {"mermaid", "svg"}
    | {"txt", "text", "plaintext", "math", "jsonl", "jsonc", "yml", "gitignore", "patch", "h", "kt"}
)
# A line that opens or closes a container block (`:::`), after any quote or list marker.
_CONTAINER_LINE = re.compile(rb"^[ \t]*(?:(?:>|[-*+]|\d{1,9}[.)])[ \t]*)*:::", re.MULTILINE)
_DEFINITION = re.compile(r"^\s*(?:(?:>|[-*+]|\d{1,9}[.)])\s*)*\[(?:[^\]\\]|\\.)+\]:")
_WORDS = re.compile(r"\w+(?:[-’']\w+)*|[^\w\s]+|\s+")
_SPACE = re.compile(r"\s+")
# Separates rendered blocks through KPress's post-processing, sanitizer and the hardener.
# A source containing it is refused, so every occurrence is the projection's own.
_SPLIT = "\ue000"
_REFERENCE = re.compile("\x00(\\d+)\x00")
_SOURCE_MARK = "\x00src\x00"
_INFO = "metabrowser_info"
# Built once: the same core and plugins KPress's parse_markdown builds per call.
_KPRESS = _markdown_it(trust_mode="sanitized", diagrams="off", math="off")
# MarkdownIt stops parsing blocks at this depth, so a side that reaches it is refused
# rather than shown without its rest. KPress's own limit is 100: 48 KiB of `1. ` lines
# nest 85 deep and parsed in 243 ms; at 32 the same input parsed in 3.0 ms. The render
# tree is held to the same depth.
_MAX_NESTING = 32
_KPRESS.options["maxNesting"] = _MAX_NESTING
_RewriteLocal = Callable[[str, bool], str | None]


class MarkdownDiffBlock(TypedDict):
    kind: Literal["context", "removed", "added"]
    side: Literal["old", "new"]
    html: str
    # This block's source differs from its counterpart in something no render shows.
    source_only: bool


class MarkdownDiffProjection(TypedDict):
    version: Literal["markdown-diff-v1"]
    status: Literal["ready", "unsupported", "too_large"]
    blocks: list[MarkdownDiffBlock]
    source_only: bool


@dataclass(frozen=True, slots=True)
class LocalReference:
    """A live-side destination inside the repository, bound by the caller."""

    href: str
    image: bool
    # For an image, its tag with ``\\0src\\0`` for the bound address, and its alt text.
    template: str = ""
    fallback: str = ""


@dataclass(frozen=True, slots=True)
class PreparedMarkdownDiff:
    """A projection whose local references are still placeholders; it pickles."""

    projection: MarkdownDiffProjection
    references: tuple[LocalReference, ...]


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

    def __init__(self, html: str, budget: int) -> None:
        super().__init__()
        self.root = _Element("")
        self.stack = [self.root]
        self.nodes = 0
        self.budget = budget
        self.feed(html)
        self.close()
        if len(self.stack) != 1:
            raise _Unsupported("incomplete render tree")

    def _count(self) -> None:
        self.nodes += 1
        if self.nodes > self.budget or len(self.stack) > _MAX_NESTING:
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


@dataclass(frozen=True, slots=True)
class _Block:
    start: int
    end: int
    node: _Element
    # The node without heading ids, for matching blocks across the two sides.
    shape: _Element
    # The shape with whitespace runs collapsed outside preformatted text: what the
    # reader actually sees, so a rewrap or a trailing space compares equal.
    seen: _Element
    hidden: tuple[tuple[str, ...], ...]
    # Comments, attribute syntax, a title, or a fence info string that is not exactly one
    # language name (_FENCE_LANGUAGES): content of this block that no render shows at all.
    concealed: bool
    # An image's alt text, which the added side hides under the image it shows.
    alt: bool
    # Each link's or image's rendered label and destination, in order.
    links: tuple[tuple[str, str], ...]
    # The items of a list, or the blocks of a quote, when each maps to one element.
    children: tuple[_Block, ...] | None = None


def _text(node: _Element) -> str:
    return "".join(
        _text(child) if isinstance(child, _Element) else child for child in node.children
    )


# Block elements whose leading and trailing whitespace no render shows.
_EDGED = frozenset({"p", "li", "td", "th", "dt", "dd", "summary", *(f"h{n}" for n in range(1, 7))})


def _shape(node: _Element, *, collapse: bool) -> _Element:
    collapse = collapse and node.tag != "pre"
    children: list[_Element | str] = [
        _shape(child, collapse=collapse)
        if isinstance(child, _Element)
        else (_SPACE.sub(" ", child) if collapse else child)
        for child in node.children
    ]
    if collapse and node.tag in _EDGED and children:
        if isinstance(children[0], str):
            children[0] = children[0].lstrip()
        if isinstance(children[-1], str):
            children[-1] = children[-1].rstrip()
        children = [child for child in children if child != ""]
    return _Element(
        node.tag, tuple((name, value) for name, value in node.attrs if name != "id"), children
    )


@dataclass(frozen=True, slots=True)
class _Hidden:
    entries: tuple[tuple[str, ...], ...]
    concealed: bool
    alt: bool
    links: tuple[tuple[str, str], ...]


def _hidden(tokens: Sequence[Token]) -> _Hidden:
    """What these tokens' source says that their render does not show.

    Each link's destination is also kept with its rendered label, so a destination that
    moves to another label is seen even when the destinations keep their order.
    """

    found: list[tuple[str, ...]] = []
    links: list[tuple[str, str]] = []
    concealed = alt = False
    for token in tokens:
        # The label of each link being read, as its text arrives.
        open_links: list[tuple[str, list[str]]] = []
        for member in (token, *(token.children or ())):
            if member.type in {"html_block", "html_inline"}:
                found.append(("comment", member.content.strip()))
                concealed = True
            attrs = {
                name: str(value)
                for name, value in (member.attrs or {}).items()
                if name not in _SHOWN_ATTRIBUTES
            }
            if attrs:
                found.append((member.type, *(f"{name}={attrs[name]}" for name in sorted(attrs))))
                concealed |= not attrs.keys() <= _NATIVE_ATTRIBUTES.get(member.type, frozenset())
                # The inert render drops a title, so it is shown nowhere.
                concealed |= bool(attrs.get("title", "").strip())
            # A fence's language and a container's name; every other token's info is the
            # source's spelling of what renders (a list item's number, an entity, an
            # escape), which the render shows as it is meant. A fence's info that is not
            # exactly one language name is text no render shows.
            if member.type == "fence" or member.type.startswith("container_"):
                info = str((member.meta or {}).get(_INFO, member.info))
                if info:
                    found.append(("info", info))
                    concealed |= (
                        member.type == "fence" and info.strip().lower() not in _FENCE_LANGUAGES
                    )
            if member.type == "image":
                found.append(("alt", member.content))
                # Under an image the page shows, its alt text is shown nowhere; a removed
                # image is shown as its alt text.
                alt |= bool(member.content.strip())
                links.append((" ".join(member.content.split()), attrs.get("src", "")))
            elif member.type == "link_open":
                open_links.append((attrs.get("href", ""), []))
            elif member.type == "link_close" and open_links:
                href, label = open_links.pop()
                links.append((" ".join("".join(label).split()), href))
            elif open_links and member.type in {"text", "code_inline"}:
                for _, label in open_links:
                    label.append(member.content)
            elif open_links and member.type in {"softbreak", "hardbreak"}:
                # A label wrapped across source lines is the same label once its
                # whitespace collapses, as the page shows it.
                for _, label in open_links:
                    label.append(" ")
    return _Hidden(tuple(found), concealed, alt, tuple(links))


def _rebound(old: Sequence[_Block], new: Sequence[_Block]) -> frozenset[str]:
    """Labels whose link lost a destination and gained another between the two sides."""

    def destinations(blocks: Sequence[_Block]) -> dict[str, set[str]]:
        found: dict[str, set[str]] = {}
        for block in blocks:
            for label, href in block.links:
                found.setdefault(label, set()).add(href)
        return found

    before, after = destinations(old), destinations(new)
    return frozenset(
        label
        for label in before.keys() & after.keys()
        if before[label] - after[label] and after[label] - before[label]
    )


def _close(tokens: Sequence[Token], index: int) -> int:
    """The index after the block that starts at *index*."""

    token = tokens[index]
    if token.nesting == 0:
        return index + 1
    for end in range(index + 1, len(tokens)):
        if tokens[end].level == token.level and tokens[end].nesting == -1:
            return end + 1
    raise _Unsupported("unclosed Markdown block")


def _slices(tokens: Sequence[Token], start: int, stop: int, level: int) -> list[tuple[int, int]]:
    slices: list[tuple[int, int]] = []
    index = start
    while index < stop:
        token = tokens[index]
        if token.level != level or token.nesting < 0:
            index += 1
            continue
        end = _close(tokens, index)
        # KPress removes comments in inert output. They have no rendered range, so a
        # changed one reaches the projection's notice as an unmapped source line.
        if token.type != "html_block":
            slices.append((index, end))
        index = end
    return slices


def _map(token: Token, offset: int, after: int) -> tuple[int, int]:
    span = token.map
    if span is None or span[0] >= span[1] or span[0] + offset < after:
        raise _Unsupported("unmapped Markdown block")
    return span[0] + offset, span[1] + offset


def _segments(root: _Element, count: int) -> list[_Element]:
    """Split the hardened document at the separators between blocks."""

    if count == 0:
        if root.children and any(
            not isinstance(child, str) or child.strip() for child in root.children
        ):
            raise _Unsupported("render without a block")
        return []
    parts: list[list[_Element | str]] = [[]]
    for child in root.children:
        if isinstance(child, str):
            for index, piece in enumerate(child.split(_SPLIT)):
                if index:
                    parts.append([])
                if piece.strip():
                    parts[-1].append(piece)
        else:
            parts[-1].append(child)
    if len(parts) != count:
        raise _Unsupported("rendered blocks differ from source blocks")
    return [
        nodes[0] if len(nodes) == 1 and isinstance(nodes[0], _Element) else _Element("", (), nodes)
        for nodes in parts
    ]


def _elements(node: _Element) -> list[_Element] | None:
    """A container's child elements, or None when it holds text of its own."""

    if any(isinstance(child, str) and child.strip() for child in node.children):
        return None
    return [child for child in node.children if isinstance(child, _Element)]


def _block(
    tokens: Sequence[Token],
    span: tuple[int, int],
    node: _Element,
    lines: Sequence[str],
    offset: int,
    after: int,
    *,
    descend: bool,
) -> _Block:
    first, stop = span
    start, end = _map(tokens[first], offset, after)
    signature = _hidden(tokens[first:stop])
    hidden, concealed = signature.entries, signature.concealed
    if tokens[first].type in _HOLDERS:
        # A link reference definition inside a quote or a list renders nothing where it
        # is written, and one that repeats a label renders nothing at all, title
        # included. It is a line no block inside the container covers: a fence's or a
        # paragraph's own lines are what they render.
        covered: set[int] = set()
        for token in tokens[first + 1 : stop - 1]:
            if token.map is not None and token.nesting >= 0 and token.type not in _HOLDERS:
                covered.update(range(token.map[0] + offset, token.map[1] + offset))
        definitions = tuple(
            ("definition", lines[line - offset].strip())
            for line in range(start, end)
            if line not in covered and _DEFINITION.match(lines[line - offset])
        )
        if definitions:
            hidden, concealed = (*hidden, *definitions), True
    children: tuple[_Block, ...] | None = None
    if descend and tokens[first].type in _CONTAINERS:
        inner = _slices(tokens, first + 1, stop - 1, tokens[first].level + 1)
        elements = _elements(node)
        if elements is not None and len(elements) == len(inner):
            items: list[_Block] = []
            for child_span, child in zip(inner, elements, strict=True):
                items.append(
                    _block(
                        tokens,
                        child_span,
                        child,
                        lines,
                        offset,
                        items[-1].end if items else start,
                        descend=False,
                    )
                )
            if items and items[-1].end <= end:
                children = tuple(items)
    return _Block(
        start,
        end,
        node,
        _shape(node, collapse=False),
        _shape(node, collapse=True),
        hidden,
        concealed,
        signature.alt,
        signature.links,
        children,
    )


@dataclass(slots=True)
class _Side:
    source: str
    offset: int
    tokens: list[Token]
    blocks: list[tuple[int, int]]
    # Elements the tokens must render, which bounds the render tree before building it.
    elements: int


def _parse(text: str) -> _Side:
    offset = 0
    source = text
    if source.startswith(("---\n", "---\r\n")):
        _, body_start, _ = fmf_split_frontmatter(source, strict=False)
        offset = source.count("\n", 0, body_start)
        source = source[body_start:]
    if _SPLIT in source:
        raise _Unsupported("source contains the block separator")
    env: dict[str, object] = {}
    tokens = _KPRESS.parse(source, env)
    if sum(1 + len(token.children or ()) for token in tokens) > _MAX_TOKENS:
        raise _OverBudget("Markdown tokens")
    if any(
        member.level >= _MAX_NESTING - 1
        for token in tokens
        for member in (token, *(token.children or ()))
    ):
        raise _OverBudget("Markdown nesting")
    # A standalone image's paragraph renders as a figure, which the hardener unwraps.
    _mark_standalone_image_figures(tokens)
    elements = 0
    for token in tokens:
        for member in (token, *(token.children or ())):
            if member.type.startswith("footnote"):
                raise _Unsupported("footnotes render away from their source")
            # Raw markup is outside the versioned Markdown block contract.
            if member.type in {"html_block", "html_inline"} and not _COMMENT.fullmatch(
                member.content.strip()
            ):
                raise _Unsupported("raw HTML has no reliable Markdown projection")
            if (
                member.nesting == 1
                and not member.hidden
                and member.tag in ALLOWED_TAGS
                and not member.meta.get("kpress_figure_image")
            ):
                elements += 1
            elif member.type in {"fence", "code_block"}:
                # `pre` and `code`.
                elements += 2
    return _Side(source, offset, tokens, _slices(tokens, 0, len(tokens), 0), elements)


def _render(side: _Side, budget: int) -> tuple[list[_Block], int]:
    if side.elements > budget:
        raise _OverBudget("Markdown elements")
    tokens = side.tokens
    for token in tokens:
        if token.type == "fence":
            # Highlighting is discarded with its classes, so KPress renders plain code;
            # the info string stays in the block's hidden signature.
            token.meta[_INFO] = token.info
            token.info = ""
    pieces = [
        _KPRESS.renderer.render(tokens[start:stop], _KPRESS.options, {})
        for start, stop in side.blocks
    ]
    sanitized, _ = sanitize_raw_html(_postprocess_html(_SPLIT.join(pieces)), "sanitized")
    hardened = harden(sanitized)
    if hardened.count(_SPLIT) != max(len(pieces) - 1, 0):
        raise _Unsupported("a block separator moved inside a block")
    tree = _Html(hardened, budget)
    blocks: list[_Block] = []
    lines = side.source.split("\n")
    for span, node in zip(side.blocks, _segments(tree.root, len(side.blocks)), strict=True):
        blocks.append(
            _block(
                tokens,
                span,
                node,
                lines,
                side.offset,
                blocks[-1].end if blocks else 0,
                descend=True,
            )
        )
    return blocks, tree.nodes


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
    floor = -1
    for left, block in enumerate(old):
        start = unchanged.get(block.start)
        if start is None or start not in right_by_start:
            continue
        right = right_by_start[start]
        other = new[right]
        if (
            right > floor
            and other.end - start == block.end - block.start
            and block.shape == other.shape
            and all(
                unchanged.get(line) == start + line - block.start
                for line in range(block.start, block.end)
            )
        ):
            matches.append((left, right))
            floor = right
    return matches


def _runs(
    left: list[str], right: list[str], *, exact: bool
) -> tuple[list[tuple[str, int, int, int, int]], int] | None:
    """Word edits and their diff work, or None past the inline budget.

    Outside preformatted text whitespace compares as one space, and two edits a space
    apart join into one changed phrase. The shared ends are trimmed before the
    quadratic diff, so its cost follows the changed span, not the paragraph.
    """

    def key(word: str) -> str:
        return " " if word.isspace() and not exact else word

    left_keys, right_keys = [key(word) for word in left], [key(word) for word in right]
    shortest = min(len(left), len(right))
    prefix = 0
    while prefix < shortest and left_keys[prefix] == right_keys[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < shortest - prefix
        and left_keys[len(left) - 1 - suffix] == right_keys[len(right) - 1 - suffix]
    ):
        suffix += 1
    middle_left = left_keys[prefix : len(left) - suffix]
    middle_right = right_keys[prefix : len(right) - suffix]
    if max(len(middle_left), len(middle_right)) > _MAX_INLINE_WORDS:
        return None
    opcodes = [("equal", 0, prefix, 0, prefix)] if prefix else []
    opcodes.extend(
        (tag, prefix + i1, prefix + i2, prefix + j1, prefix + j2)
        for tag, i1, i2, j1, j2 in SequenceMatcher(
            None, middle_left, middle_right, autojunk=False
        ).get_opcodes()
    )
    if suffix:
        opcodes.append(("equal", len(left) - suffix, len(left), len(right) - suffix, len(right)))
    runs: list[tuple[str, int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in opcodes:
        if (
            tag != "equal"
            and not exact
            and len(runs) >= 2
            and runs[-2][0] != "equal"
            and runs[-1][0] == "equal"
            and all(word.isspace() for word in left[runs[-1][1] : runs[-1][2]])
        ):
            # Two edits a space apart read as one changed phrase.
            runs.pop()
            _, start_left, _, start_right, _ = runs.pop()
            runs.append(("replace", start_left, i2, start_right, j2))
        elif runs and runs[-1][0] == tag == "equal":
            runs[-1] = ("equal", runs[-1][1], i2, runs[-1][3], j2)
        else:
            runs.append((tag, i1, i2, j1, j2))
    return runs, max(len(middle_left) * len(middle_right), 1)


def _marked(words: list[str], tag: str, *, exact: bool) -> list[_Element | str]:
    """A changed run; outside preformatted text its edge whitespace stays unmarked."""

    lead = 0
    trail = len(words)
    if not exact:
        while lead < len(words) and words[lead].isspace():
            lead += 1
        while trail > lead and words[trail - 1].isspace():
            trail -= 1
    pieces: list[_Element | str] = []
    if lead:
        pieces.append("".join(words[:lead]))
    if trail > lead:
        pieces.append(_Element(tag, children=["".join(words[lead:trail])]))
    if trail < len(words):
        pieces.append("".join(words[trail:]))
    return pieces


def _joined(pieces: list[_Element | str]) -> list[_Element | str]:
    result: list[_Element | str] = []
    for piece in pieces:
        if isinstance(piece, str) and result and isinstance(result[-1], str):
            result[-1] += piece
        elif not isinstance(piece, str) or piece:
            result.append(piece)
    return result


def _occurs_once(text: str, source: str, *, exact: bool) -> bool:
    if exact:
        return source.replace("\r\n", "\n").count(text) == 1
    text = _SPACE.sub(" ", text).strip()
    return not text or _SPACE.sub(" ", source).count(text) == 1


@dataclass(frozen=True, slots=True)
class _Inline:
    old: _Element
    new: _Element
    nodes: int
    work: int


def _inline_change(
    old: _Element, new: _Element, old_source: str, new_source: str, work: int
) -> _Inline | None:
    """Mark the changed words of a block whose only change is within one text node.

    Each side's changed span must occur exactly once in that side's changed source
    lines, so the marked text is text those lines changed. Where the same words also
    stand on an untouched line beside it, the mark may sit on that copy instead: the
    rendered texts are equal either way, and the redline is still a true edit of them.
    """

    if old.tag != new.tag:
        return None
    changes: list[tuple[tuple[int, ...], str, str, bool]] = []

    def compare(left: _Element, right: _Element, at: tuple[int, ...], pre: bool) -> bool:
        if (
            left.tag != right.tag
            or tuple(pair for pair in left.attrs if pair[0] != "id")
            != tuple(pair for pair in right.attrs if pair[0] != "id")
            or len(left.children) != len(right.children)
        ):
            return False
        pre = pre or left.tag == "pre"
        for index, (before, after) in enumerate(zip(left.children, right.children, strict=True)):
            address = (*at, index)
            if isinstance(before, _Element) and isinstance(after, _Element):
                # A link is shown independently on each side and never redlined as
                # though a removed label belonged to the live link.
                if before.tag in {"a", "img"}:
                    if before != after:
                        return False
                elif not compare(before, after, address, pre):
                    return False
            elif isinstance(before, str) and isinstance(after, str):
                if before != after:
                    changes.append((address, before, after, pre))
            else:
                return False
        return True

    if not compare(old, new, (), False) or len(changes) != 1:
        return None
    address, before, after, exact = changes[0]
    left, right = _WORDS.findall(before), _WORDS.findall(after)
    diff = _runs(left, right, exact=exact)
    if diff is None or diff[1] > work:
        return None
    runs, cost = diff
    edits = [run for run in runs if run[0] != "equal"]
    if not edits or not (
        _occurs_once("".join(left[edits[0][1] : edits[-1][2]]), old_source, exact=exact)
        and _occurs_once("".join(right[edits[0][3] : edits[-1][4]]), new_source, exact=exact)
    ):
        return None
    old_pieces: list[_Element | str] = []
    new_pieces: list[_Element | str] = []
    for tag, i1, i2, j1, j2 in runs:
        if tag == "equal":
            old_pieces.append("".join(left[i1:i2]))
            new_pieces.append("".join(right[j1:j2]))
            continue
        old_pieces.extend(_marked(left[i1:i2], "del", exact=exact))
        new_pieces.extend(_marked(right[j1:j2], "ins", exact=exact))
    old_pieces, new_pieces = _joined(old_pieces), _joined(new_pieces)
    # Each piece is a node, each mark also holds a text node, and one text node goes.
    nodes = sum(
        len(pieces) + sum(isinstance(piece, _Element) for piece in pieces) - 1
        for pieces in (old_pieces, new_pieces)
    )

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

    return _Inline(
        replace_run(old, address, old_pieces), replace_run(new, address, new_pieces), nodes, cost
    )


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
    node: _Element, ids: dict[str, str], *, removed: bool, references: list[LocalReference]
) -> str:
    """Serialize a block; a live local destination becomes a numbered placeholder."""

    def inner() -> str:
        return "".join(
            _html(child, ids, removed=removed, references=references)
            if isinstance(child, _Element)
            else escape(child, quote=False)
            for child in node.children
        )

    if not node.tag:
        return inner()
    alt = escape(dict(node.attrs).get("alt") or "image", quote=False)
    if removed and node.tag == "img":
        return alt
    tag = "span" if removed and node.tag == "a" else node.tag
    attrs: list[str] = []
    local_image = ""
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
            if node.tag == "img":
                local_image = value
                attrs.append(f' {name}="{_SOURCE_MARK}"')
            else:
                references.append(LocalReference(value, image=False))
                attrs.append(f"\x00{len(references) - 1}\x00")
            continue
        attrs.append(f' {name}="{escape(value)}"')
    start = f"<{tag}{''.join(attrs)}>"
    if local_image:
        references.append(LocalReference(local_image, True, start, alt))
        return f"\x00{len(references) - 1}\x00"
    if tag in _VOID:
        return start
    return f"{start}{inner()}</{tag}>"


def _shifted2(
    wrap: Callable[[_Element, bool, int], _Element], left: int, right: int
) -> Callable[[_Element, bool, int], _Element]:
    def at(node: _Element, old_side: bool, index: int) -> _Element:
        return wrap(node, old_side, (left if old_side else right) + index)

    return at


# Adjacent edited blocks pair when they share at least half their words (difflib's ratio
# over word tokens): an edited sentence shares far more, and a deleted block beside an
# edited one far less ("Never deploy on Friday." against "Run the tests first, always."
# is 0.0; "Run the tests first." against it is 0.89).
_PAIR_RATIO = 0.5
# Runs of at most this many blocks a side are aligned block against block, unless each
# block already resembles the one in its place. Past it, or past _MAX_PAIR_WORK, a run of
# equal length pairs in order where the quick bound allows (_in_order), so a longer
# find-and-replace keeps its marks, and an unequal run is shown whole.
_PAIR_RUN = 16
# The word pairs one projection's alignments may compare with difflib's ratio, len(a) *
# len(b) a comparison: two 256-word comparisons. Over the 434 real pairs alignments spend
# p99 74,127 and at most 108,908, so none reaches it. Words drawn from two letters pass
# every quick bound and are ratio's slowest input (review F of #349): three runs of 16
# such 250-word paragraphs a side, 24 KB, took 3.7 s compared in full and now take
# 21.7-22.2 ms in order, against 18.7-19.1 ms at round 2. Against runs of 15 they take
# 26.1-26.3 ms, against 11.5-11.8 ms shown whole at round 2 (load average 17-18).
_MAX_PAIR_WORK = 2 * _MAX_INLINE_WORDS * _MAX_INLINE_WORDS


def _filled(lines: Sequence[bytes]) -> list[bytes]:
    return [line for line in lines if line.strip()]


def _words(block: _Block) -> list[str]:
    return re.findall(r"\w+", _text(block.node))[:_MAX_INLINE_WORDS]


def _quick(a: Counter[str], b: Counter[str]) -> float:
    """difflib's quick_ratio from word counts: the most ratio could be, in linear time."""

    size = a.total() + b.total()
    return 2 * (a & b).total() / size if size else 1.0


def _in_order(old: Sequence[_Block], new: Sequence[_Block]) -> list[tuple[int, int]]:
    """An equal-length run's blocks paired in order, where the quick bound allows it."""

    if len(old) != len(new):
        return []
    return [
        (index, index)
        for index, (before, after) in enumerate(zip(old, new, strict=True))
        if before.node.tag == after.node.tag
        and _quick(Counter(_words(before)), Counter(_words(after))) >= _PAIR_RATIO
    ]


def _align(
    old: Sequence[_Block], new: Sequence[_Block], budget: int
) -> tuple[list[tuple[int, int]] | None, int]:
    """The pairs of a run, in order, that maximize the shared words of paired blocks, and
    the work spent; no pairs when the run is too long or the budget runs out."""

    if max(len(old), len(new)) > _PAIR_RUN:
        return None, 0
    old_words, new_words = [_words(block) for block in old], [_words(block) for block in new]
    old_counts, new_counts = [Counter(a) for a in old_words], [Counter(b) for b in new_words]
    spent = 0

    def similarity(left: int, right: int) -> float | None:
        nonlocal spent
        if old[left].node.tag != new[right].node.tag:
            return 0.0
        a, b = old_words[left], new_words[right]
        if not a and not b:
            return 1.0
        if (
            2 * min(len(a), len(b)) / (len(a) + len(b)) < _PAIR_RATIO
            or _quick(old_counts[left], new_counts[right]) < _PAIR_RATIO
        ):
            return 0.0
        if spent + len(a) * len(b) > budget:
            return None
        spent += len(a) * len(b)
        ratio = SequenceMatcher(None, a, b, autojunk=False).ratio()
        return ratio if ratio >= _PAIR_RATIO else 0.0

    # Needleman-Wunsch over the run: the best total similarity of the first i old and
    # first j new blocks.
    best = [[0.0] * (len(new) + 1) for _ in range(len(old) + 1)]
    for i in range(1, len(old) + 1):
        for j in range(1, len(new) + 1):
            paired = similarity(i - 1, j - 1)
            if paired is None:
                return None, spent
            best[i][j] = max(
                best[i - 1][j],
                best[i][j - 1],
                best[i - 1][j - 1] + paired if paired else 0.0,
            )
    pairs: list[tuple[int, int]] = []
    i, j = len(old), len(new)
    while i and j:
        if best[i][j] == best[i - 1][j]:
            i -= 1
        elif best[i][j] == best[i][j - 1]:
            j -= 1
        else:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
    return pairs[::-1], spent


@dataclass(slots=True)
class _Projector:
    old_lines: list[bytes]
    new_lines: list[bytes]
    unchanged: dict[int, int]
    removed: set[int]
    added: set[int]
    old_ids: dict[str, str]
    new_ids: dict[str, str]
    nodes: int
    # Labels whose links point somewhere new anywhere in the document (see _rebound).
    rebound: frozenset[str] = frozenset()
    # The inline word diffs' quadratic work so far, against _MAX_INLINE_WORK.
    work: int = 0
    # The alignments' word comparisons so far, against _MAX_PAIR_WORK.
    pair_work: int = 0
    blocks: list[MarkdownDiffBlock] = field(default_factory=list)
    references: list[LocalReference] = field(default_factory=list)
    # A source change with no visible counterpart in the blocks around it.
    notice: bool = False
    # A changed blank line inside a block that is otherwise the same: a source change
    # worth the notice only when nothing visible changed.
    blank: bool = False
    # Blocks shown whole, removed (True) or added, with where each was emitted.
    moved: list[tuple[bool, _Block, int]] = field(default_factory=list)

    def emit(
        self,
        kind: Literal["context", "removed", "added"],
        node: _Element,
        *,
        source_only: bool = False,
    ) -> None:
        old = kind == "removed"
        self.blocks.append(
            {
                "kind": kind,
                "side": "old" if old else "new",
                "html": _html(
                    node,
                    self.old_ids if old else self.new_ids,
                    removed=old,
                    references=self.references,
                ),
                "source_only": source_only,
            }
        )

    def spend(self, nodes: int) -> bool:
        if self.nodes + nodes > _MAX_NODES:
            return False
        self.nodes += nodes
        return True

    def consume(self, old: Sequence[_Block], new: Sequence[_Block]) -> None:
        for block in old:
            self.removed.difference_update(range(block.start, block.end))
        for block in new:
            self.added.difference_update(range(block.start, block.end))

    def changed(self, block: _Block, lines: set[int]) -> set[int]:
        return lines.intersection(range(block.start, block.end))

    def covered(self, block: _Block, lines: set[int]) -> bool:
        assert block.children is not None
        return all(
            any(child.start <= line < child.end for child in block.children)
            for line in self.changed(block, lines)
        )

    def walk(
        self,
        old: Sequence[_Block],
        new: Sequence[_Block],
        wrap: Callable[[_Element, bool, int], _Element] | None = None,
    ) -> None:
        """Emit unchanged blocks as context and each run of changes between them."""

        def wrapped(node: _Element, old_side: bool, index: int) -> _Element:
            return node if wrap is None else wrap(node, old_side, index)

        def offset(left: int, right: int) -> Callable[[_Element, bool, int], _Element]:
            def at(node: _Element, old_side: bool, index: int) -> _Element:
                return wrapped(node, old_side, (left if old_side else right) + index)

            return at

        left = right = 0
        for stop_left, stop_right in (
            *_matches(old, new, self.unchanged),
            (len(old), len(new)),
        ):
            self.group(old[left:stop_left], new[right:stop_right], offset(left, right))
            if stop_right < len(new):
                self.emit("context", wrapped(new[stop_right].node, False, stop_right))
            left, right = stop_left + 1, stop_right + 1

    def source(self, block: _Block, old_side: bool) -> list[bytes]:
        return (self.old_lines if old_side else self.new_lines)[block.start : block.end]

    def align(self, old: Sequence[_Block], new: Sequence[_Block]) -> list[tuple[int, int]]:
        """Pair a run's blocks by likeness within the budget, or else in order."""

        in_order = _in_order(old, new)
        if in_order and len(in_order) == len(old):
            # Each block resembles the one in its place, as a find-and-replace leaves
            # them: no block needs comparing with every other.
            return in_order
        pairs, spent = _align(old, new, _MAX_PAIR_WORK - self.pair_work)
        self.pair_work += spent
        return in_order if pairs is None else pairs

    def differs(self, old: Sequence[_Block], new: Sequence[_Block]) -> bool:
        """Whether the source of these blocks changed in a way their renders do not show."""

        return [entry for block in old for entry in block.hidden] != [
            entry for block in new for entry in block.hidden
        ] or any(label in self.rebound for block in (*old, *new) for label, _ in block.links)

    def group(
        self,
        old: Sequence[_Block],
        new: Sequence[_Block],
        wrap: Callable[[_Element, bool, int], _Element],
    ) -> None:
        if not old and not new:
            return
        if len(old) == len(new) and all(a.seen == b.seen for a, b in zip(old, new, strict=True)):
            # Rendered alike once whitespace collapses: a rewrap, a trailing space, a
            # renumbered item, or a change only the source shows. A block whose filled
            # source lines are byte for byte the same, which a hunk beside it brought
            # into the run, has nothing for the notice to name; if only its blank lines
            # differ, which a diff may give to either neighbour of an insertion, that
            # counts as a blank line no block holds does (see blank).
            self.consume(old, new)
            for index, (before, after) in enumerate(zip(old, new, strict=True)):
                hidden = self.differs([before], [after])
                lines = self.source(before, True), self.source(after, False)
                if hidden or _filled(lines[0]) != _filled(lines[1]):
                    self.notice = True
                elif lines[0] != lines[1]:
                    self.blank = True
                self.emit("context", wrap(after.node, False, index), source_only=hidden)
            return
        if len(old) == len(new) == 1 and self.pair(old[0], new[0], wrap):
            return
        pairs = self.align(old, new) if len(old) + len(new) > 2 else []
        if pairs:
            # Adjacent edited blocks pair only with a block of the same kind that shares
            # most of its words, so each is shown, marked and flagged as itself; the rest
            # are shown whole.
            left = right = 0
            for stop_left, stop_right in (*pairs, (len(old), len(new))):
                self.whole(old[left:stop_left], new[right:stop_right], _shifted2(wrap, left, right))
                if stop_left < len(old):
                    self.group(
                        [old[stop_left]], [new[stop_right]], _shifted2(wrap, stop_left, stop_right)
                    )
                left, right = stop_left + 1, stop_right + 1
            return
        self.whole(old, new, wrap)

    def whole(
        self,
        old: Sequence[_Block],
        new: Sequence[_Block],
        wrap: Callable[[_Element, bool, int], _Element],
    ) -> None:
        """Show blocks as removed and added in full."""

        if not old and not new:
            return
        if old and new:
            source_only = self.differs(old, new)
            if " ".join(" ".join(_text(block.node).split()) for block in old) == " ".join(
                " ".join(_text(block.node).split()) for block in new
            ):
                # The same words in a different structure, such as emphasis: visible,
                # yet named in the notice in case a structure renders alike.
                self.notice = True
        else:
            # An added link shows its destination on hover; a comment, attribute syntax,
            # a title, an added image's alt text, or a label whose link moved elsewhere
            # in the document does not show.
            source_only = (
                any(block.concealed for block in old)
                or any(block.concealed or block.alt for block in new)
                or any(label in self.rebound for block in (*old, *new) for label, _ in block.links)
            )
        self.consume(old, new)
        for index, block in enumerate(old):
            self.moved.append((True, block, len(self.blocks)))
            self.emit("removed", wrap(block.node, True, index), source_only=source_only)
        for index, block in enumerate(new):
            self.moved.append((False, block, len(self.blocks)))
            self.emit("added", wrap(block.node, False, index), source_only=source_only)

    def flag_moves(self) -> None:
        """Flag a block removed in one place and added in another, its text unchanged,
        when its source changed in a way neither render shows."""

        removed: dict[str, list[tuple[_Block, int]]] = {}
        for old_side, block, at in self.moved:
            if old_side:
                removed.setdefault(" ".join(_text(block.node).split()), []).append((block, at))
        for old_side, block, at in self.moved:
            if old_side:
                continue
            for before, where in removed.get(" ".join(_text(block.node).split()), []):
                if self.differs([before], [block]):
                    self.blocks[where]["source_only"] = True
                    self.blocks[at]["source_only"] = True

    def pair(
        self, old: _Block, new: _Block, wrap: Callable[[_Element, bool, int], _Element]
    ) -> bool:
        if (
            old.children is not None
            and new.children is not None
            # A list that starts at another number renumbers every item visibly.
            and old.node.tag == new.node.tag
            and old.node.attrs == new.node.attrs
            and self.covered(old, self.removed)
            and self.covered(new, self.added)
        ):
            old_items, new_items = old.children, new.children
            if not self.spend(len(old_items) + len(new_items)):
                return False

            def item(node: _Element, old_side: bool, index: int) -> _Element:
                # One list or quote per item keeps its numbering and its marker.
                parent = old.node if old_side else new.node
                attrs = tuple(pair for pair in parent.attrs if pair[0] != "start")
                number = int(dict(parent.attrs).get("start") or "1") + index
                if parent.tag == "ol" and number != 1:
                    attrs = (("start", str(number)), *attrs)
                return wrap(_Element(parent.tag, attrs, [node]), old_side, 0)

            self.walk(old_items, new_items, item)
            self.consume([old], [new])
            return True
        old_changed = sorted(self.changed(old, self.removed))
        new_changed = sorted(self.changed(new, self.added))
        if not (old_changed or new_changed) or any(
            lines and lines[-1] - lines[0] != len(lines) - 1 for lines in (old_changed, new_changed)
        ):
            # Marks are witnessed against one contiguous run of changed lines a side.
            return False
        inline = _inline_change(
            old.node,
            new.node,
            b"".join(self.old_lines[line] for line in old_changed).decode(),
            b"".join(self.new_lines[line] for line in new_changed).decode(),
            _MAX_INLINE_WORK - self.work,
        )
        if inline is None or not self.spend(inline.nodes):
            return False
        self.work += inline.work
        source_only = self.differs([old], [new])
        self.consume([old], [new])
        self.emit("removed", wrap(inline.old, True, 0), source_only=source_only)
        self.emit("added", wrap(inline.new, False, 0), source_only=source_only)
        return True


def _project(
    old: bytes | None, new: bytes | None, patch: FilePatch, namespace: str
) -> PreparedMarkdownDiff:
    before, after = old or b"", new or b""
    if len(before) + len(after) > MARKDOWN_DIFF_MAX_BYTES:
        raise _OverBudget("Markdown input bytes")
    if max(before.count(b"["), after.count(b"[")) > _MAX_LINK_OPENERS:
        raise _OverBudget("Markdown link-label work")
    if max(len(_CONTAINER_LINE.findall(data)) for data in (before, after)) > _MAX_CONTAINER_LINES:
        raise _OverBudget("Markdown container lines")
    old_lines, new_lines = _lines(old), _lines(new)
    if patch.truncated or any(
        b"\0" in data or b"\r" in data.replace(b"\r\n", b"") for data in (before, after)
    ):
        raise _Unsupported("unmapped Markdown source")
    unchanged, removed, added = _correspondence(old_lines, new_lines, patch)
    old_side, new_side = _parse(before.decode()), _parse(after.decode())
    if old_side.elements + new_side.elements > _MAX_NODES:
        raise _OverBudget("combined Markdown elements")
    old_blocks, old_nodes = _render(old_side, _MAX_NODES - new_side.elements)
    new_blocks, new_nodes = _render(new_side, _MAX_NODES - old_nodes)
    projector = _Projector(
        old_lines,
        new_lines,
        unchanged,
        removed,
        added,
        _namespace_ids(old_blocks, namespace, "old"),
        _namespace_ids(new_blocks, namespace, "new"),
        old_nodes + new_nodes,
        _rebound(old_blocks, new_blocks),
    )
    projector.walk(old_blocks, new_blocks)
    projector.flag_moves()
    # A blank separator beside an already visible addition or deletion adds no
    # information to the notice. Standalone whitespace changes still point to Source.
    has_visual_change = any(block["kind"] != "context" for block in projector.blocks)
    unmapped = any(old_lines[i].strip() for i in projector.removed) or any(
        new_lines[i].strip() for i in projector.added
    )
    source_only = (
        projector.notice
        or unmapped
        or any(block["source_only"] for block in projector.blocks)
        or (
            not has_visual_change
            and (projector.blank or bool(projector.removed or projector.added))
        )
    )
    return PreparedMarkdownDiff(
        {
            "version": MARKDOWN_DIFF_VERSION,
            "status": "ready",
            "blocks": projector.blocks,
            "source_only": source_only,
        },
        tuple(projector.references),
    )


def unavailable_markdown_diff(status: Literal["unsupported", "too_large"]) -> PreparedMarkdownDiff:
    """A projection that refuses, with no partial HTML."""

    return PreparedMarkdownDiff(
        {"version": MARKDOWN_DIFF_VERSION, "status": status, "blocks": [], "source_only": False},
        (),
    )


def prepare_markdown_diff(
    *, old: bytes | None, new: bytes | None, patch: FilePatch, namespace: str
) -> PreparedMarkdownDiff:
    """The projection with its live local destinations still unbound.

    It holds only plain data, so a worker process can compute it and the server bind it.
    """

    try:
        return _project(old, new, patch, namespace)
    except _OverBudget:
        return unavailable_markdown_diff("too_large")
    except (UnicodeError, _Unsupported):
        return unavailable_markdown_diff("unsupported")


def bind_markdown_diff(
    prepared: PreparedMarkdownDiff, rewrite_local: _RewriteLocal | None
) -> MarkdownDiffProjection:
    """Bind each live local destination; one *rewrite_local* refuses goes inert."""

    def bound(match: re.Match[str]) -> str:
        reference = prepared.references[int(match.group(1))]
        target = None if rewrite_local is None else rewrite_local(reference.href, reference.image)
        if reference.image:
            if target is None:
                return reference.fallback
            return reference.template.replace(_SOURCE_MARK, escape(target))
        return "" if target is None else f' href="{escape(target)}"'

    projection = prepared.projection
    blocks: list[MarkdownDiffBlock] = [
        {
            "kind": block["kind"],
            "side": block["side"],
            "html": _REFERENCE.sub(bound, block["html"]),
            "source_only": block["source_only"],
        }
        for block in projection["blocks"]
    ]
    return {
        "version": projection["version"],
        "status": projection["status"],
        "blocks": blocks,
        "source_only": projection["source_only"],
    }


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

    return bind_markdown_diff(
        prepare_markdown_diff(old=old, new=new, patch=patch, namespace=namespace), rewrite_local
    )


def warm_markdown_projection() -> None:
    """Import and exercise the projection once, as a worker process's first job."""

    text = b"# Warm\n\nA [link](a.md) and `code`.\n"
    prepare_markdown_diff(
        old=None,
        new=text,
        patch=FilePatch(
            file_id="warm",
            hunks=(
                Hunk(
                    old_start=0,
                    old_count=0,
                    new_start=1,
                    new_count=3,
                    lines=tuple(
                        LineRecord(op=LineOp.add, text=line) for line in text.decode().splitlines()
                    ),
                ),
            ),
            truncated=False,
        ),
        namespace="warm",
    )
