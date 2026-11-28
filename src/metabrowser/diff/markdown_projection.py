"""Project authoritative Git hunks onto bounded, inert KPress Markdown.

Each side is parsed once, by the MarkdownIt core KPress itself builds, so a block's
source range is the map of the very token that renders it. Every top-level block is
rendered from its own tokens, and the blocks pass KPress's post-processing, its
sanitizer and :func:`metabrowser.inert_html.harden` together, separated by markers of a
character the render does not hold (:func:`_separator`), so a rendered block is known to
come from its range and heading anchors are numbered across the document exactly as the
Document view numbers them.
Raw HTML renders as the Document view renders it: blocks that an element it opens holds
together, whose markers land inside that element, are one block of all their lines
(:func:`_units`). A footnote's note, which the Document view lists at the end, renders
where its definition is written, numbered as the Document view numbers it
(:func:`_footnotes_in_place`). ``tests/test_markdown_diff_projection.py`` checks that
the joined blocks equal KPress's own ``parse_markdown`` render, notes compared by their
numbers, so a KPress release that changes this pipeline fails there rather than here.

Each side reads as the Document view reads it: a byte that is not UTF-8 is U+FFFD, and
MarkdownIt itself makes a NUL U+FFFD. Git counts lines by line feeds and MarkdownIt also
ends one at a carriage return no line feed follows, so a Git line that holds such a
return is that many of the projection's lines, changed or unchanged as Git says the
whole line is (:func:`_markdown_lines`).

Whatever a block's source says that its render does not show -- a link or image
destination, a title, alt text under a shown image, an HTML comment, an attribute, raw
HTML KPress's sanitizer or the allowlist drops, or a fence's info string -- is its
*hidden* signature. A changed block whose hidden signature differs from the other
side's carries ``source_only``, and so does the whole projection when any source change
has no visible counterpart, a whitespace-only or rewrap edit included. Both flags are
metadata for the page: a flagged block is kept out of a fold of unchanged blocks, and
the Rendered view draws no note about either, so a change with no visible counterpart
shows only in the Source view.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from functools import lru_cache
from html import escape, unescape
from html.parser import HTMLParser
from itertools import islice, pairwise
from math import inf
from typing import Any, Final, Literal, NotRequired, TypedDict, cast
from urllib.parse import unquote

from frontmatter_format import fmf_split_frontmatter
from kpress.format.markdown import (
    _mark_standalone_image_figures,
    _markdown_it,
    _postprocess_html,
)
from kpress.format.sanitize import sanitize_raw_html
from markdown_it.rules_core import StateCore
from markdown_it.token import Token
from pygments.lexers import get_all_lexers

from metabrowser.diff.format import FilePatch, Hunk, LineOp, LineRecord
from metabrowser.frontmatter_yaml import FrontmatterError, load_frontmatter_yaml
from metabrowser.inert_html import (
    ALLOWED_TAGS,
    ANCHOR_PREFIX,
    BARE_ATTRIBUTES,
    DROPPED_WITH_CONTENT,
    allowed_attributes,
    harden,
    is_inside,
)
from metabrowser.markdown_limits import (
    _CONTAINER_LINE,
    _MAX_CONTAINER_LINES,
    _MAX_NESTING,
)
from metabrowser.markdown_limits import (
    MARKDOWN_DIFF_MAX_BYTES as MARKDOWN_DIFF_MAX_BYTES,
)

MARKDOWN_DIFF_VERSION = "markdown-diff-v1"
# A side's `[` count: nested openers parsed in 15 ms at 256, 31 ms at 512, 62 ms at 1,024.
_MAX_LINK_OPENERS = 256
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
# The nodes one side's front matter may compose to. Composing costs a few tens of
# microseconds a node, and a flow list of one-digit integers is a node every three
# bytes, so inside MARKDOWN_DIFF_MAX_BYTES front matter alone took 762 ms (mb-8274
# review A4). Of the 191 tracked Markdown files of this repository whose front matter
# loads, the largest is 694 nodes (10 KB). A flow list of 2,000 loaded in 80 ms at a
# load average of 70-115 (Apple M1 Pro, Python 3.14, 2026-11-18). Past it the side shows
# no disclosure and its front matter lines count as unmapped, as for front matter that
# does not load.
_FRONTMATTER_MAX_NODES = 2_000

_VOID = frozenset({"br", "hr", "img", "input"})
# The token KPress draws a task list item's box from (`_TASK_CHECKBOX_TOKEN` in
# kpress/format/markdown.py), with the box's state in `meta["checked"]`: one `input`,
# which the allowlist keeps as a disabled checkbox, ticked as the token is
# (`CHECKBOX_ATTRIBUTES` in inert_html.py). Its attributes are that box, which the
# render shows, so they are no part of the hidden signature, and a tick is a change in
# what the block renders.
_TASK_BOX = "kpress_task_checkbox"
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
# A comment as HTML5, and so the sanitizer's parser, reads one: `<!-->` and `<!--->` are
# whole empty comments, and any other ends at its first `-->` or `--!>`. MarkdownIt reads
# `--!>`, and a block's opening `<!-->`, as comment text, so a token it calls a comment can
# end early in the sanitizer and render the rest as raw HTML, which a thread must refuse
# (_is_raw). `test_a_comment_is_one_only_where_the_sanitizer_ends_it` checks the pattern
# against the sanitizer.
_COMMENT = re.compile(r"<!---?>|<!--(?!-?>)(?:(?!--!?>).)*-->", re.DOTALL)
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
# A carriage return that ends a line for MarkdownIt, as for KPress, and not for Git.
_LONE_CR = re.compile(rb"\r(?!\n)")
_LONE_CR_TEXT = re.compile(r"\r(?!\n)")
_DEFINITION = re.compile(r"^\s*(?:(?:>|[-*+]|\d{1,9}[.)])\s*)*\[(?:[^\]\\]|\\.)+\]:")
_WORDS = re.compile(r"\w+(?:[-’']\w+)*|[^\w\s]+|\s+")
_SPACE = re.compile(r"\s+")
# The characters a render's blocks may be parted with through KPress's post-processing,
# sanitizer and the hardener: private use, which no Markdown or HTML parser gives a
# meaning, in the Basic Multilingual Plane and planes 15 and 16 (each but its last two
# code points, which are not characters). Each render takes the first one its blocks
# do not hold (_separator), so every occurrence is the projection's own. The boundary
# after block `n` is written as the separator, `n`, and the separator again (_marker),
# so where each boundary lands in the hardened tree says which blocks it parts.
_SEPARATORS = (range(0xE000, 0xF900), range(0xF0000, 0xFFFFE), range(0x100000, 0x10FFFE))
_REFERENCE = re.compile("\x00(\\d+)\x00")
_SOURCE_MARK = "\x00src\x00"
_INFO = "metabrowser_info"
# Built once: the same core and plugins KPress's parse_markdown builds per call.
_KPRESS = _markdown_it(trust_mode="sanitized", diagrams="off", math="off")
_KPRESS.options["maxNesting"] = _MAX_NESTING
_RewriteLocal = Callable[[str, bool], str | None]

# ── Footnotes, each where its source is ─────────────────────────

# The number a note's own list starts at (_note).
_NOTE = "metabrowser_note"
# Marks an inline note's list, which is part of the block before it (_slices).
_ATTACHED = "metabrowser_attached"
# A parse's env holds the lines of the source here when its notes are KPress's own, at
# the end (_footnotes_in_place).
_NOTES_AT_END = "metabrowser_notes_at_end"
# The elements each footnote token renders once hardened: a reference's `sup` and
# link, a note's list (KPress's `section` around it goes) and item, and a link back.
_NOTE_ELEMENTS = {
    "footnote_ref": 2,
    "footnote_block_open": 1,
    "footnote_open": 1,
    "footnote_anchor": 1,
}
# KPress's own footnote_tail, which _footnotes_in_place takes the place of and calls when
# a side's notes follow no source line. markdown-it-py's Ruler replaces a rule by name
# (`at`) but publishes no way to read one, so this reads its list, `__rules__`
# (markdown-it-py 4.2.0, pinned in pyproject.toml); the module fails to import when that
# moves, and test_the_projection_replaces_kpress_own_footnote_tail when the rule does.
_FOOTNOTE_TAIL = next(
    rule.fn for rule in _KPRESS.core.ruler.__rules__ if rule.name == "footnote_tail"
)
_KPRESS_NOTES_OPEN = cast(Any, _KPRESS.renderer).rules["footnote_block_open"]


def _render_notes_open(tokens: list[Token], idx: int, options: Any, env: Any) -> str:
    """KPress's list of notes, starting at its note's number when it holds one note."""

    html = str(_KPRESS_NOTES_OPEN(tokens, idx, options, env))
    number = tokens[idx].meta.get(_NOTE, 1)
    return html if number == 1 else html.replace("<ol>", f'<ol start="{number}">', 1)


def _note(identity: int, note: dict[str, Any], content: Sequence[Token], level: int) -> list[Token]:
    """Note *identity* as KPress's footnote_tail writes it, in a list of its own that
    starts at its number, at *level*."""

    def token(kind: str, tag: str, nesting: Literal[-1, 0, 1], depth: int) -> Token:
        made = Token(kind, tag, nesting)
        made.level = depth
        made.block = kind.startswith("paragraph")
        return made

    label = note.get("label")
    body = list(content)
    if "tokens" in note:
        # An inline note (`^[...]`), whose text is a paragraph.
        text = token("inline", "", 0, level + 2)
        text.children = note["tokens"]
        text.content = note["content"]
        body = [token("paragraph_open", "p", 1, level + 1), text]
        body.append(token("paragraph_close", "p", -1, level + 1))
    last = body.pop() if body and body[-1].type == "paragraph_close" else None
    # One link back for each reference, or one when nothing counts them.
    anchors = [token("footnote_anchor", "", 0, level + 2) for _ in range(note.get("count") or 1)]
    for sub, anchor in enumerate(anchors):
        anchor.meta = {"id": identity, "subId": sub, "label": label}
    opened, item = (
        token("footnote_block_open", "", 1, level),
        token("footnote_open", "", 1, level + 1),
    )
    opened.meta = {_NOTE: identity + 1}
    item.meta = {"id": identity, "label": label}
    closing = [
        token("footnote_close", "", -1, level + 1),
        token("footnote_block_close", "", -1, level),
    ]
    return [opened, item, *body, *anchors, *([last] if last else []), *closing]


def _inline_notes(
    tokens: Sequence[Token], notes: dict[int, dict[str, Any]], seen: set[int]
) -> list[int]:
    """The inline notes *tokens* refer to that are not in *seen*, which gains them."""

    found: list[int] = []
    for member in tokens:
        identity = int(member.meta.get("id", -1)) if member.type == "footnote_ref" else -1
        if "tokens" in notes.get(identity, {}) and identity not in seen:
            seen.add(identity)
            found.append(identity)
    return found


def _notes_at_end(state: StateCore) -> None:
    """KPress's own notes, at the end, with the lines they and the rest are written on."""

    maps = [token.map for token in state.tokens if token.map is not None]
    state.env[_NOTES_AT_END] = (min(span[0] for span in maps), max(span[1] for span in maps))
    _FOOTNOTE_TAIL(state)


def _footnotes_in_place(state: StateCore) -> None:
    """KPress's footnote_tail, with each note where its source is.

    footnote_tail moves every note to one list at the end, numbered by its first
    reference, and the Document view shows them there. Here each is a list of its own
    that starts at that number, so a note is a block of its definition's lines, and an
    inline note (`^[...]`), which has no lines of its own, is part of the top-level
    block that holds it. As footnote_tail does, the last definition of a label is the
    one that renders, and one that no reference names renders nothing. A definition
    written inside another's, which footnote_tail sorts by no rule a block can follow,
    and an inline note held only by a definition that renders nothing leave the notes
    KPress's own, at the end, and the side renders as one block (_render).
    """

    data = cast(dict[str, Any] | None, state.env.get("footnotes"))
    if not data:
        return
    notes = cast(dict[int, dict[str, Any]], data["list"])
    refs = cast(dict[str, int], data["refs"])
    tokens = state.tokens
    last: dict[str, int] = {}
    inside = False
    for index, token in enumerate(tokens):
        if token.type == "footnote_reference_open":
            if inside:
                _notes_at_end(state)
                return
            inside = True
            last[token.meta["label"]] = index
        elif token.type == "footnote_reference_close":
            inside = False
    flow: list[Token] = []
    placed: set[int] = set()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type != "footnote_reference_open":
            flow.append(token)
            index += 1
            continue
        close = index + 1
        while tokens[close].type != "footnote_reference_close":
            close += 1
        identity = refs.get(":" + token.meta["label"], -1)
        if last[token.meta["label"]] == index and identity >= 0:
            written = _note(identity, notes[identity], tokens[index + 1 : close], token.level)
            written[0].map = token.map
            flow.extend(written)
            placed.add(identity)
        index = close + 1
    result: list[Token] = []
    waiting: list[int] = []
    for token in flow:
        result.append(token)
        if token.type == "inline":
            waiting.extend(_inline_notes(token.children or (), notes, placed))
        if token.level == 0 and token.nesting <= 0:
            # The end of a top-level block, which the inline notes it holds follow.
            while waiting:
                identity = waiting.pop(0)
                written = _note(identity, notes[identity], (), 0)
                written[0].meta[_ATTACHED] = True
                result.extend(written)
                waiting.extend(_inline_notes(notes[identity]["tokens"], notes, placed))
    if waiting or placed != notes.keys():
        _notes_at_end(state)
        return
    state.tokens = result


_KPRESS.core.ruler.at("footnote_tail", _footnotes_in_place)
cast(Any, _KPRESS.renderer).rules["footnote_block_open"] = _render_notes_open


class MarkdownDiffBlock(TypedDict):
    kind: Literal["context", "removed", "added"]
    side: Literal["old", "new"]
    html: str
    # This block's source differs from its counterpart in something no render shows.
    source_only: bool
    # The lines of its side the block's source spans, from 0, the end not included: what
    # the route folds by (`metabrowser.diff.markdown_views`). The route keeps it off the
    # wire, since the page draws a block from its HTML alone.
    lines: list[int]


class FrontmatterDiffEntry(TypedDict):
    """One front matter key, as KPress's Frontmatter disclosure lists it, and its change."""

    key: str
    change: Literal["context", "removed", "added"]
    # The value as the disclosure shows it: `str` of its JSON-safe value.
    text: str


class FrontmatterDiff(TypedDict):
    """Both sides' front matter, in the order KPress lists it: keys sorted as text."""

    change: Literal["context", "modified", "removed", "added"]
    entries: list[FrontmatterDiffEntry]


# Why a projection refuses, where that says more than its status: the page tells the
# reader in each one's own sentence (`REFUSALS` in builtin_plugins/diff/diff-markdown.js).
# ``no_changes`` is the route's, for a file whose content did not change, and ``deadline``
# the worker's, for a projection it stopped.
type MarkdownRefusal = Literal["nesting", "deadline", "memory", "no_changes"]


class MarkdownDiffProjection(TypedDict):
    version: Literal["markdown-diff-v1"]
    status: Literal["ready", "unsupported", "too_large"]
    # Present on a refusal whose cause the page can name.
    reason: NotRequired[MarkdownRefusal]
    blocks: list[MarkdownDiffBlock]
    source_only: bool
    # Present when either side shows front matter.
    frontmatter: NotRequired[FrontmatterDiff]


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


class _Refused(ValueError):
    """A projection that answers no blocks, and the cause the page can name, if any."""

    def __init__(self, message: str, reason: MarkdownRefusal | None = None) -> None:
        super().__init__(message)
        self.reason: MarkdownRefusal | None = reason


class _Unsupported(_Refused):
    """The source patch and render could not be mapped with confidence."""


class _OverBudget(_Refused):
    """The projection would exceed its work budget."""


@dataclass(frozen=True, slots=True)
class _Limits:
    """What one projection's input may hold.

    The budgets beside the constants above bound a projection nothing can stop: one in a
    thread, on the server's interpreter. A projection that can be stopped, the Markdown
    child's, has none of them, since its deadline bounds it whatever it holds
    (``_PROJECTION_TIMEOUT_S`` in ``markdown_projection_worker.py``; "Stop what no
    estimate bounds" in docs/large-content-rendering.md). The nesting limit holds for
    both: past it MarkdownIt drops the rest of a block, and no deadline restores it.

    *raw_html* says a side may hold raw HTML that renders, which only the child's may: no
    count over the input bounds what the sanitizer makes of it. Its HTML parser rebuilds
    each formatting element left open at every later block, as HTML5 says, so one line
    of ``n`` distinct ``<b a=i>`` then ``m`` ``<div>x</div>`` renders ``n * m`` elements.
    Measured 2026-11-23 on an Apple M1 Pro, Python 3.14.7, KPress 0.3.9 (nh3), at a load
    average of 220 to 340, each size in its own process, on a thread before this bound:

    =========  ============  =========================  =========
    Bytes      ``n * m``     Time (nh3, then harden)    Peak RSS
    =========  ============  =========================  =========
    7,987      151,267       3.9 s (0.12 s, 3.0 s)      128 MB
    11,989     338,142       10.5 s (0.88 s, 8.5 s)     189 MB
    15,988     598,928       20.4 s (2.5 s, 16.1 s)     280 MB
    23,988     1,308,378     59.5 s (12.8 s, 45.5 s)    459 MB
    =========  ============  =========================  =========

    nh3 alone took 1,281 MB and 40 s on 47,988 bytes (5 million rebuilt), and a side of
    48 KiB of ``<``, the slowest input inside every budget without raw HTML, took 3.1 to
    7.2 s with 75 MB in the same runs. Markdown with no raw HTML renders balanced
    elements, which the parser rebuilds none of, and a comment renders nothing, so for
    them the budgets above are the bound. A comment that the parser ends before
    MarkdownIt's token does renders the rest, so it is raw HTML here (``_COMMENT``).
    A side that holds raw HTML is refused on a thread with a budget's refusal,
    which names no cause, so the server asks the child for the pair (``past_a_thread``
    in ``markdown_projection_worker.py``). The child, as when it renders the same file
    for the Document view, now has an RSS watchdog. Before that bound, stopped 10 s after
    the call, 47,988 bytes had reached 1,295 MB, and 2,000 elements left open then
    20,000 blocks (258,902 bytes) 1,016 MB (mb-zrng).
    """

    input_bytes: float
    link_openers: float
    container_lines: float
    tokens: float
    nodes: float
    raw_html: bool


def _limits(stoppable: bool) -> _Limits:
    if stoppable:
        return _Limits(inf, inf, inf, inf, inf, raw_html=True)
    # Read at each call, so a test that lowers a budget sees it applied.
    return _Limits(
        MARKDOWN_DIFF_MAX_BYTES,
        _MAX_LINK_OPENERS,
        _MAX_CONTAINER_LINES,
        _MAX_TOKENS,
        _MAX_NODES,
        raw_html=False,
    )


@dataclass(slots=True)
class _Element:
    tag: str
    attrs: tuple[tuple[str, str], ...] = ()
    children: list[_Element | str] = field(default_factory=list)


# A document's own `ins` and `del`, as the tags the allowlist draws them as without the
# page's change tints, so every `ins` and `del` in a block is one `_marked` wrote: the
# page tints any `ins` in an added row and any `del` in a removed one (diff styles.css),
# and a class the projection added would not do, since raw HTML may write one.
_DOCUMENT_MARKS = {"ins": "span", "del": "s"}


class _Html(HTMLParser):
    """Read the small already hardened HTML subset without repairing its structure.

    A document's `ins` and `del` are read as `span` and `s` (`_DOCUMENT_MARKS`).
    """

    def __init__(self, html: str, budget: float) -> None:
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
        if self.nodes > self.budget:
            raise _OverBudget("render tree")
        if len(self.stack) > _MAX_NESTING:
            raise _OverBudget("render tree nesting", "nesting")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._count()
        tag = _DOCUMENT_MARKS.get(tag, tag)
        node = _Element(tag, tuple((key, value or "") for key, value in attrs))
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = _DOCUMENT_MARKS.get(tag, tag)
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
    """What *node* reads as: its text, and a task's box as a ballot box, ticked or not, so
    an item whose box was ticked does not read as the same words as the item before."""

    if node.tag == "input":
        return "☑" if any(name == "checked" for name, _ in node.attrs) else "☐"
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


# The elements HTML writes without an end tag, which open nothing.
_HTML_VOID = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track"}
    | {"wbr", "param", "keygen"}
)
# The attributes the allowlist keeps that the render shows as layout, as a Markdown table's
# alignment is: every other attribute it keeps, a destination or an alt text, is shown
# nowhere or only on hover, as a Markdown link's is.
_RAW_DESTINATIONS = frozenset({"href", "src", "alt"})
# What KPress's sanitizer drops before the allowlist reads it, though the allowlist would
# keep it: an element whose content stays, and attributes. The render shows neither; the
# hardener writes an image's referrer policy itself. Asked of the sanitizer by
# test_what_kpress_drops_first_is_what_the_projection_says_it_drops.
_SANITIZER_DROPPED_TAGS = frozenset({"tfoot"})
_SANITIZER_DROPPED_ATTRIBUTES = frozenset(
    {("details", "open"), ("img", "referrerpolicy"), ("pre", "lang")}
)
# KPress's sanitizer keeps an input as its box when the input's `type`, without the ASCII
# whitespace around it, is `checkbox` in ASCII letters of any case (`_is_checkbox_type` in
# its sanitize.py), and writes that box as `type="checkbox"`, which the allowlist keeps; it
# removes any other input. Asked of the sanitizer by
# test_kpress_keeps_the_boxes_the_projection_says_it_keeps.
_KPRESS_TYPE_SPACE = "\t\n\f\r "


def _kpress_keeps_box(kind: str | None) -> bool:
    written = (kind or "").strip(_KPRESS_TYPE_SPACE)
    return written.isascii() and written.lower() == "checkbox"


def _shows_value(tag: str, name: str, value: str | None, kept: str) -> bool:
    """Whether the first copy of an attribute the render keeps says only what the render
    writes of it, *kept*. The allowlist reads no boolean attribute's value, nor one it
    writes as a constant, such as a link's `target`, so other text in either is shown
    nowhere."""

    written = value or ""
    if name in BARE_ATTRIBUTES:
        # The spellings HTML gives a boolean attribute's value: none, or its own name in
        # any case.
        return not written or (written.isascii() and written.lower() == name)
    if name == "align":
        # A keyword, which the allowlist reads in any case.
        written = written.lower()
    elif tag == "input" and name == "type":
        # A box's type, as KPress reads it (_kpress_keeps_box).
        written = written.strip(_KPRESS_TYPE_SPACE).lower()
    return written == kept


# Raw HTML at most this long is read once for each spelling (_raw_markup): a tag such as
# `<br>` or `</kbd>` is a few dozen characters, and longer content, a whole `html_block`,
# is read where it stands, so the cache's 1,024 entries hold at most about 256 KiB.
_CACHED_RAW_CHARS = 256


class _RawMarkup(HTMLParser):
    """What raw HTML says that its render does not show.

    The allowlist decides it as it decides the render (:func:`allowed_attributes`): an
    attribute it drops, an element it drops with its content and that content, and a
    comment or declaration are shown nowhere, and make the block *concealed*. A
    destination or an alt text it keeps is shown only on hover or under its image, as a
    Markdown link's or image's is. A checkbox the document writes is kept as a task
    list's box is, so its `type` and `checked` are shown and nothing else of it is. Each
    attribute is read as its first copy, so every later copy is shown nowhere, and so is
    a value the allowlist does not read (:func:`_shows_value`), such as text in a box's
    `checked`. The text and layout the render shows are compared through the render
    itself, so they are not part of the signature.
    """

    def __init__(self, dropped: int = 0) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[tuple[str, ...]] = []
        self.concealed = self.alt = False
        # Depth inside an element dropped with its content, which raw HTML before this
        # may have opened.
        self.dropped = dropped

    def _hide(self, *entry: str) -> None:
        self.entries.append(entry)
        self.concealed = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        written = [f"{name}={value or ''}" for name, value in attrs]
        if self.dropped or tag in DROPPED_WITH_CONTENT:
            if tag not in _HTML_VOID:
                self.dropped += 1
            self._hide("dropped", tag, *written)
            return
        # An attribute written twice is its first, as a browser and KPress's sanitizer read
        # it: `<input type="checkbox" type="text">` renders a box, and its second `type`
        # is shown nowhere.
        values = dict(reversed(attrs))
        # An image and a checkbox are kept though neither is an allowed tag; any other
        # input goes, as KPress's sanitizer removes it, and the box it keeps it writes as
        # `type="checkbox"`.
        box = tag == "input" and _kpress_keeps_box(values.get("type"))
        if not (tag in ALLOWED_TAGS or tag == "img" or box) or tag in _SANITIZER_DROPPED_TAGS:
            # The element goes and its content stays: its name changes nothing the page
            # draws, and its attributes are shown nowhere.
            self.entries.append(("element", tag))
            if attrs:
                self._hide(tag, *written)
            return
        kept = {
            name: value
            for name, value in allowed_attributes(
                tag, {**values, "type": "checkbox"} if box else values, None
            )
            if (tag, name) not in _SANITIZER_DROPPED_ATTRIBUTES
        }
        shown: list[str] = []
        hidden: list[str] = []
        seen: set[str] = set()
        for (name, value), entry in zip(attrs, written, strict=True):
            if name in seen:
                # A later copy, which nothing reads.
                hidden.append(entry)
                continue
            seen.add(name)
            if name in _RAW_DESTINATIONS:
                shown.append(entry)
                # An empty alt text, which the allowlist does not write, says the image
                # has none.
                if name not in kept and (name != "alt" or value):
                    hidden.append(entry)
            elif name not in kept or not _shows_value(tag, name, value, kept[name]):
                hidden.append(entry)
        if shown:
            self.entries.append((tag, *shown))
        if hidden:
            self._hide(tag, *hidden)
        if tag == "img" and (values.get("alt") or "").strip():
            self.alt = True

    def handle_endtag(self, tag: str) -> None:
        if self.dropped and tag not in _HTML_VOID:
            self.dropped -= 1

    def handle_data(self, data: str) -> None:
        if self.dropped and data.strip():
            self._hide("dropped", data)

    def handle_comment(self, data: str) -> None:
        self._hide("comment", data)

    def handle_decl(self, decl: str) -> None:
        self._hide("declaration", decl)

    def unknown_decl(self, data: str) -> None:
        self._hide("declaration", data)

    def handle_pi(self, data: str) -> None:
        self._hide("declaration", data)


type _RawRead = tuple[tuple[tuple[str, ...], ...], bool, bool, int]


def _raw_markup(content: str, dropped: int) -> _RawRead:
    """Raw HTML's hidden entries, whether it conceals anything, whether it holds alt text
    under an image, and the depth inside dropped elements after it, read from *dropped*.
    Inline HTML repeats a handful of tags, such as `<br>`, so each short one is read once
    (_CACHED_RAW_CHARS)."""

    if len(content) <= _CACHED_RAW_CHARS:
        return _raw_markup_once(content, dropped)
    return _read_raw_markup(content, dropped)


def _read_raw_markup(content: str, dropped: int) -> _RawRead:
    parser = _RawMarkup(dropped)
    parser.feed(content)
    if parser.rawdata.startswith("<"):
        # A tag the content does not finish, which a browser drops with what it holds, and
        # which in the document reads on into what follows.
        parser._hide("unfinished", parser.rawdata)  # pyright: ignore[reportPrivateUsage]
    parser.close()
    return tuple(parser.entries), parser.concealed, parser.alt, parser.dropped


_raw_markup_once = lru_cache(maxsize=1024)(_read_raw_markup)


def _hidden(tokens: Sequence[Token]) -> _Hidden:
    """What these tokens' source says that their render does not show.

    Each link's destination is also kept with its rendered label, so a destination that
    moves to another label is seen even when the destinations keep their order.
    """

    found: list[tuple[str, ...]] = []
    links: list[tuple[str, str]] = []
    concealed = alt = False
    # Depth inside an element raw HTML opened that the render drops with its content: the
    # text between two inline tags, `<svg>` and `</svg>`, is its content too.
    dropped = 0
    for token in tokens:
        # The label of each link being read, as its text arrives.
        open_links: list[tuple[str, list[str]]] = []
        for member in (token, *(token.children or ())):
            if member.type == _TASK_BOX:
                continue
            if member.type in {"html_block", "html_inline"}:
                entries, conceals, holds_alt, dropped = _raw_markup(member.content, dropped)
                found.extend(entries)
                concealed |= conceals
                alt |= holds_alt
            elif dropped and not member.children and member.content.strip():
                found.append(("dropped", member.content))
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
        # An inline note's list is part of the block that holds the note. KPress removes
        # comments in inert output: they have no rendered range, so a changed one reaches
        # the projection's notice as an unmapped source line.
        if token.meta.get(_ATTACHED) and slices:
            slices[-1] = (slices[-1][0], end)
        elif not _is_comment(token):
            slices.append((index, end))
        index = end
    return slices


def _is_comment(token: Token) -> bool:
    return token.type == "html_block" and bool(_COMMENT.fullmatch(token.content.strip()))


def _is_raw(token: Token) -> bool:
    """Raw HTML that renders, as opposed to a comment the sanitizer ends where its token
    ends (_COMMENT)."""

    if token.type == "html_inline":
        return not _COMMENT.fullmatch(token.content.strip())
    return token.type == "html_block" and not _is_comment(token)


def _map(token: Token, offset: int, after: int) -> tuple[int, int]:
    span = token.map
    if span is None or span[0] >= span[1] or span[0] + offset < after:
        raise _Unsupported("unmapped Markdown block")
    return span[0] + offset, span[1] + offset


def _separator(text: str) -> str | None:
    """Eleven of _SEPARATORS that *text* does not hold, or None when it holds all but
    fewer: the first opens and closes a boundary marker, and the other ten are its
    index's digits. A heading's slug drops them all, as it drops no ASCII digit, so a
    marker inside a heading that raw HTML left open adds nothing to its anchor."""

    first = "".join(map(chr, _SEPARATORS[0][:11]))
    if len(first) == 11 and not _holds(text, first):
        return first
    held = set(text)
    free = "".join(
        islice(
            (chr(point) for points in _SEPARATORS for point in points if chr(point) not in held),
            11,
        )
    )
    return free if len(free) == 11 else None


def _holds(text: str, split: str) -> bool:
    """Whether *text* holds any character of the separator *split*."""

    return any(character in text for character in split)


@lru_cache(maxsize=8)
def _markers(split: str) -> re.Pattern[str]:
    """The boundaries a render parted by *split* carries."""

    return re.compile(f"{split[0]}([{split[1:]}]+){split[0]}")


def _marker(index: int, split: str) -> str:
    """The boundary after block *index*, as the render carries it."""

    return split[0] + str(index).translate(str.maketrans("0123456789", split[1:])) + split[0]


def _marked_index(digits: str, split: str) -> int:
    """The block index a marker's *digits* write."""

    return int(digits.translate(str.maketrans(split[1:], "0123456789")))


def _hardened(html: str, budget: float) -> _Html:
    """*html* through KPress's post-processing and sanitizer and the inert-HTML hardener,
    as the Document view renders a document, read as a tree."""

    # The diagnostics say what the sanitizer removed, which no diff shows, and cost most
    # of its time (mb-d1gq).
    sanitized, _ = sanitize_raw_html(_postprocess_html(html), "sanitized", diagnose=False)
    return _Html(harden(sanitized), budget)


def _trimmed(nodes: Sequence[_Element | str]) -> list[_Element | str]:
    """*nodes* without the whitespace around them, which no render shows at the top level."""

    start, stop = 0, len(nodes)
    while start < stop and isinstance(nodes[start], str) and not str(nodes[start]).strip():
        start += 1
    while stop > start and isinstance(nodes[stop - 1], str) and not str(nodes[stop - 1]).strip():
        stop -= 1
    return list(nodes[start:stop])


def _joined_nodes(parts: Sequence[Sequence[_Element | str]]) -> list[_Element | str]:
    """Consecutive parts of the top level as one, their text joined where a marker was."""

    nodes: list[_Element | str] = []
    for part in parts:
        for node in part:
            if isinstance(node, str) and nodes and isinstance(nodes[-1], str):
                nodes[-1] += node
            else:
                nodes.append(node)
    return _trimmed(nodes)


def _unmarked(node: _Element, split: str) -> bool:
    """Remove the boundary markers inside *node*: a boundary inside an element parts
    nothing, so the blocks on either side render as one. False when a separator is left
    anywhere else, such as in an attribute."""

    whole = not any(_holds(value, split) for _, value in node.attrs)
    children: list[_Element | str] = []
    for child in node.children:
        if isinstance(child, _Element):
            whole &= _unmarked(child, split)
            children.append(child)
            continue
        text = _markers(split).sub("", child)
        whole &= not _holds(text, split)
        if text and children and isinstance(children[-1], str):
            children[-1] += text
        elif text:
            children.append(text)
    node.children = children
    return whole


@dataclass(slots=True)
class _Unit:
    """Consecutive top-level blocks, *first* to *last*, and what they render together."""

    first: int
    last: int
    nodes: list[_Element | str]


def _units(root: _Element, count: int, split: str) -> list[_Unit] | None:
    """The blocks the hardened render parts at its top level, and what each part renders,
    or None when it does not keep its boundaries in order.

    A boundary the render carries at its top level parts the blocks on either side. One
    that lands inside an element, which raw HTML opened in one block and closed in a
    later one, or that the render drops with what held it, parts nothing, so those
    blocks render as one: a `<div>` around Markdown, or a `<details>` whose summary is in
    one block and whose body is the next.
    """

    if count == 0:
        return [] if not _trimmed(root.children) else None
    parts: list[list[_Element | str]] = [[]]
    ends: list[int] = []
    for child in root.children:
        if isinstance(child, _Element):
            if not _unmarked(child, split):
                return None
            parts[-1].append(child)
            continue
        position = 0
        for match in _markers(split).finditer(child):
            parts[-1].append(child[position : match.start()])
            ends.append(_marked_index(match.group(1), split))
            parts.append([])
            position = match.end()
        parts[-1].append(child[position:])
    if any(_holds(node, split) for part in parts for node in part if isinstance(node, str)):
        return None
    if any(later <= earlier for earlier, later in pairwise(ends)) or (
        ends and ends[-1] >= count - 1
    ):
        return None
    units: list[_Unit] = []
    first = 0
    for last, part in zip([*ends, count - 1], parts, strict=True):
        units.append(_Unit(first, last, _joined_nodes([part])))
        first = last + 1
    return units


def _skeleton(nodes: Sequence[_Element | str]) -> list[object]:
    """Each element, its attributes but an id, and its text without whitespace: what two
    renders of the same source must agree on when neither moved a block's content into
    the other's. A parser moves whitespace a table holds out ahead of it, which shows
    nothing either way."""

    skeleton: list[object] = []
    for node in nodes:
        if isinstance(node, _Element):
            attrs = tuple(pair for pair in node.attrs if pair[0] != "id")
            skeleton.append((node.tag, attrs, _skeleton(node.children)))
        elif text := "".join(node.split()):
            if skeleton and isinstance(skeleton[-1], str):
                skeleton[-1] += text
            else:
                skeleton.append(text)
    return skeleton


def _alone(unit: _Unit, pieces: Sequence[str], budget: float) -> bool:
    """Whether *unit* renders by itself as it does in its document."""

    alone = _hardened("".join(pieces[unit.first : unit.last + 1]), budget).root.children
    return _skeleton(alone) == _skeleton(unit.nodes)


def _trusted(
    units: list[_Unit], root: _Element, raw: Sequence[bool], pieces: Sequence[str], budget: float
) -> list[_Unit] | None:
    """*units*, the parts from the first one that does not render alone as it does here
    held together as one, or None when even they do not.

    A boundary the render carries at its top level is where every element the blocks
    before it opened is closed, with one exception: a table the parser holds open moves
    the text after it, a marker included, out ahead of the table, to where the table
    sits. KPress wraps every table it sees in a `<div>`, so such a marker lands in the
    wrapper and parts nothing; only a table KPress's own parser reads as text, and the
    sanitizer's as a table, sits at the top level, as one in an SVG's `<style>` does.
    Only then is each part that holds raw HTML rendered on its own to find the first one
    whose content moved, which only the Markdown child does, since only it renders raw
    HTML (_Limits). A side of `<br>` blocks under such a table costs one render a block:
    1,190 took 1.6 s, 5,000 took 12.1 s and 20,000 took 52 s, against 46 ms, 282 ms and
    4.6 s without the table (Apple M1 Pro, Python 3.14.7, load average 347-357,
    2026-11-23). It is linear in the blocks, and the child's deadline stops a long one.
    """

    if not any(isinstance(child, _Element) and child.tag == "table" for child in root.children):
        return units
    for position, unit in enumerate(units):
        if not any(raw[unit.first : unit.last + 1]) or _alone(unit, pieces, budget):
            continue
        rest = _Unit(
            unit.first, len(pieces) - 1, _joined_nodes([later.nodes for later in units[position:]])
        )
        return [*units[:position], rest] if _alone(rest, pieces, budget) else None
    return units


def _elements(node: _Element) -> list[_Element] | None:
    """A container's child elements, or None when it holds text of its own."""

    if any(isinstance(child, str) and child.strip() for child in node.children):
        return None
    return [child for child in node.children if isinstance(child, _Element)]


def _block(
    tokens: Sequence[Token],
    spans: Sequence[tuple[int, int]],
    node: _Element,
    lines: Sequence[str],
    offset: int,
    after: int,
    *,
    descend: bool,
    bounds: tuple[int, int] | None = None,
) -> _Block:
    """A block of one top-level slice of tokens, or of several that render as one, or
    of all of them on the lines *bounds* names."""

    first, stop = spans[0][0], spans[-1][1]
    if bounds is not None:
        start, end = bounds
    else:
        start, end = _map(tokens[first], offset, after)
    if len(spans) > 1:
        end = _map(tokens[spans[-1][0]], offset, start)[1]
    signature = _hidden(tokens[first:stop])
    hidden, concealed = signature.entries, signature.concealed
    merged = len(spans) > 1 or bounds is not None
    if merged or tokens[first].type in _HOLDERS:
        # A link reference definition inside a quote or a list renders nothing where it
        # is written, and one that repeats a label renders nothing at all, title
        # included. It is a line no block inside the container covers: a fence's or a
        # paragraph's own lines are what they render. Between the blocks raw HTML holds
        # together, one renders nothing there either.
        covered: set[int] = set()
        for token in tokens[first:stop] if merged else tokens[first + 1 : stop - 1]:
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
    if descend and not merged and node.tag and tokens[first].type in _CONTAINERS:
        # Within the container's own close: an inline note's list, which the slice was
        # extended over, is not one of its children.
        inner = _slices(tokens, first + 1, _close(tokens, first) - 1, tokens[first].level + 1)
        elements = _elements(node)
        if elements is not None and len(elements) == len(inner):
            items: list[_Block] = []
            for child_span, child in zip(inner, elements, strict=True):
                items.append(
                    _block(
                        tokens,
                        [child_span],
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
    # The YAML between the front matter's fences, when the source opens with them.
    frontmatter: str | None = None
    # Whether a top-level slice holds raw HTML that renders (_is_raw), by slice.
    raw: tuple[bool, ...] = ()
    # The lines of a source whose notes are KPress's own, at the end, which then
    # renders as one block (_footnotes_in_place).
    whole: tuple[int, int] | None = None


def _parse(text: str, token_budget: float = inf) -> _Side:
    offset = 0
    source = text
    frontmatter = None
    if source.startswith(("---\n", "---\r\n")):
        frontmatter, body_start, _ = fmf_split_frontmatter(source, strict=False)
        offset = source.count("\n", 0, body_start)
        source = source[body_start:]
    env: dict[str, object] = {}
    tokens = _KPRESS.parse(source, env)
    if sum(1 + len(token.children or ()) for token in tokens) > token_budget:
        raise _OverBudget("Markdown tokens")
    if any(
        member.level >= _MAX_NESTING - 1
        for token in tokens
        for member in (token, *(token.children or ()))
    ):
        raise _OverBudget("Markdown nesting", "nesting")
    # A standalone image's paragraph renders as a figure, which the hardener unwraps.
    _mark_standalone_image_figures(tokens)
    elements = 0
    for token in tokens:
        for member in (token, *(token.children or ())):
            if member.type in _NOTE_ELEMENTS:
                elements += _NOTE_ELEMENTS[member.type]
                continue
            if member.type == _TASK_BOX:
                # Its `input`.
                elements += 1
                continue
            # Raw HTML renders what the sanitizer and the allowlist keep of it, which may
            # be nothing, so it adds no element the render must hold. Only a run that can
            # be stopped renders it (_Limits.raw_html).
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
    blocks = _slices(tokens, 0, len(tokens), 0)
    raw = tuple(
        any(
            _is_raw(member)
            for token in tokens[start:stop]
            for member in (token, *(token.children or ()))
        )
        for start, stop in blocks
    )
    whole = cast(tuple[int, int] | None, env.get(_NOTES_AT_END))
    return _Side(source, offset, tokens, blocks, elements, frontmatter, raw, whole)


def _render(side: _Side, budget: float) -> tuple[list[_Block], int]:
    if side.elements > budget:
        raise _OverBudget("Markdown elements")
    tokens = side.tokens
    for token in tokens:
        if token.type == "fence":
            # Highlighting is discarded with its classes, so KPress renders plain code;
            # the info string stays in the block's hidden signature.
            token.meta[_INFO] = token.info
            token.info = ""
    lines = side.source.split("\n")
    if side.whole is not None:
        # Notes KPress places by no rule a block can follow: the side is one block, the
        # document's own render.
        tree = _hardened(_KPRESS.renderer.render(tokens, _KPRESS.options, {}), budget)
        nodes = _trimmed(tree.root.children)
        start, end = side.whole
        whole = _block(
            tokens,
            [(0, len(tokens))],
            _Element("", (), nodes),
            lines,
            side.offset,
            0,
            descend=False,
            bounds=(start + side.offset, end + side.offset),
        )
        return ([whole] if nodes else []), tree.nodes
    pieces = [
        _KPRESS.renderer.render(tokens[start:stop], _KPRESS.options, {})
        for start, stop in side.blocks
    ]
    # A character the render holds, written or as a reference, cannot part its blocks.
    split = _separator(unescape("".join(pieces)))
    units: list[_Unit] | None = None
    nodes = 0
    if split is not None:
        tree = _hardened(
            "".join(
                piece + (_marker(index, split) if index < len(pieces) - 1 else "")
                for index, piece in enumerate(pieces)
            ),
            budget,
        )
        units = _units(tree.root, len(pieces), split)
        if units is not None and any(side.raw):
            units = _trusted(units, tree.root, side.raw, pieces, budget)
        nodes = tree.nodes
    if units is None:
        # No part of the render can be trusted to be its own blocks', or it holds every
        # separator, so the side is one block: the document's own render, which is never
        # refused for its shape.
        tree = _hardened("".join(pieces), budget)
        units = [_Unit(0, len(pieces) - 1, _trimmed(tree.root.children))] if pieces else []
        nodes = tree.nodes
    blocks: list[_Block] = []
    for unit in units:
        if not unit.nodes:
            # Raw HTML the render drops whole, such as a script: like a comment, it has no
            # rendered range, and a changed one reaches the notice as unmapped lines.
            continue
        only = unit.nodes[0]
        blocks.append(
            _block(
                tokens,
                side.blocks[unit.first : unit.last + 1],
                only
                if len(unit.nodes) == 1 and isinstance(only, _Element)
                else _Element("", (), unit.nodes),
                lines,
                side.offset,
                blocks[-1].end if blocks else 0,
                descend=True,
            )
        )
    return blocks, nodes


def _lines(data: bytes | None) -> list[bytes]:
    if not data:
        return []
    # Git line numbers count LF; Python splitlines also splits several Unicode
    # separators, which would shift the witness away from the actual patch.
    result = data.split(b"\n")
    return [line + b"\n" for line in result[:-1]] + (result[-1:] if result[-1] else [])


def _markdown_lines(lines: Sequence[bytes]) -> tuple[list[bytes], list[range]]:
    """*lines*, Git's, split where MarkdownIt also ends a line, and each Git line's range
    of the lines that makes: a carriage return no line feed follows ends one."""

    split: list[bytes] = []
    ranges: list[range] = []
    for line in lines:
        start, cut = len(split), 0
        for found in _LONE_CR.finditer(line):
            split.append(line[cut : found.end()])
            cut = found.end()
        if cut < len(line):
            split.append(line[cut:])
        ranges.append(range(start, len(split)))
    return split, ranges


def _decoded(data: bytes) -> str:
    """*data* as the Document view reads it: a byte that is not UTF-8 is U+FFFD, and a
    carriage return no line feed follows is a line feed, so the text's lines are the
    projection's (:func:`_markdown_lines`).

    A CRLF stays, where the file view's read makes it a line feed too
    (:func:`metabrowser.structured_text.decode_text`), since MarkdownIt reads both alike."""

    text = data.decode("utf-8", errors="replace")
    return _LONE_CR_TEXT.sub("\n", text) if "\r" in text else text


def _verify_line(record: LineRecord, lines: Sequence[bytes], index: int) -> None:
    if index >= len(lines):
        raise _Unsupported("patch does not match the snapshot")
    try:
        # A line that is not UTF-8 carries its exact bytes; a text no file holds, such as
        # an unpaired surrogate, or bytes that are not base64, match no snapshot.
        body = (
            record.text.encode()
            if record.text_b64 is None
            else base64.b64decode(record.text_b64, validate=True)
        )
    except (UnicodeEncodeError, binascii.Error) as error:
        raise _Unsupported("patch does not match the snapshot") from error
    if lines[index] != body + (b"" if record.no_newline else b"\n"):
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

    def attributes(node: _Element) -> tuple[tuple[str, str], ...]:
        # A box is drawn on each side in its own state, so a tick beside the one changed
        # text does not stop that text being marked; a tick alone changes no text.
        ignored = ("id", "checked") if node.tag == "input" else ("id",)
        return tuple(pair for pair in node.attrs if pair[0] not in ignored)

    def compare(left: _Element, right: _Element, at: tuple[int, ...], pre: bool) -> bool:
        if (
            left.tag != right.tag
            or attributes(left) != attributes(right)
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
    node: _Element,
    ids: dict[str, str],
    *,
    removed: bool,
    changed: bool,
    references: list[LocalReference],
) -> str:
    """Serialize a block; a live local destination becomes a numbered placeholder.

    A `<details>` in a *changed* block, removed or added, is written open, so the marks
    inside it show without a reader opening each side's to compare them. KPress's
    sanitizer drops a source's own `open`, so the Document view shows every one closed.
    """

    def inner() -> str:
        return "".join(
            _html(child, ids, removed=removed, changed=changed, references=references)
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
    if changed and tag == "details":
        attrs.append(" open")
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
    # The nodes the answer may hold (`_Limits.nodes`), which a word diff's marks add to.
    node_budget: float = inf
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
        block: _Block,
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
                    changed=kind != "context",
                    references=self.references,
                ),
                "source_only": source_only,
                "lines": [block.start, block.end],
            }
        )

    def spend(self, nodes: int) -> bool:
        if self.nodes + nodes > self.node_budget:
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
                self.emit(
                    "context", wrapped(new[stop_right].node, False, stop_right), new[stop_right]
                )
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
                self.emit("context", wrap(after.node, False, index), after, source_only=hidden)
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
            self.emit("removed", wrap(block.node, True, index), block, source_only=source_only)
        for index, block in enumerate(new):
            self.moved.append((False, block, len(self.blocks)))
            self.emit("added", wrap(block.node, False, index), block, source_only=source_only)

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
            _decoded(b"".join(self.old_lines[line] for line in old_changed)),
            _decoded(b"".join(self.new_lines[line] for line in new_changed)),
            _MAX_INLINE_WORK - self.work,
        )
        if inline is None or not self.spend(inline.nodes):
            return False
        self.work += inline.work
        source_only = self.differs([old], [new])
        self.consume([old], [new])
        self.emit("removed", wrap(inline.old, True, 0), old, source_only=source_only)
        self.emit("added", wrap(inline.new, False, 0), new, source_only=source_only)
        return True


class _NotShown:
    """Front matter the Document view shows no disclosure for, or that this diff does not
    load: YAML that does not load or is past _FRONTMATTER_MAX_NODES, and YAML that is not
    a non-empty mapping."""


_NOT_SHOWN: Final = _NotShown()
_MISSING: Final = object()


def _frontmatter_mapping(text: str | None) -> dict[str, Any] | _NotShown | None:
    """The mapping the Document view's disclosure lists, ``None`` for no front matter, or
    :data:`_NOT_SHOWN`.

    Loaded as the Document view loads it (:func:`~metabrowser.frontmatter_yaml.load_frontmatter_yaml`),
    with each value's type kept, so the key ``1`` and the key ``"1"``, or ``false`` and
    ``"False"``, compare as different values though the disclosure writes them alike.
    """

    if text is None:
        return None
    try:
        parsed = load_frontmatter_yaml(text, max_nodes=_FRONTMATTER_MAX_NODES, typed=True)
    except FrontmatterError:
        # The Document view shows its body with a front matter error, which this leaves
        # to Source: the lines stay unmapped (mb-8274 review A3).
        return _NOT_SHOWN
    return cast("dict[str, Any]", parsed) if isinstance(parsed, dict) and parsed else _NOT_SHOWN


def _identity(value: object) -> object:
    """A value with the type of each key and scalar the loader wrote as text, to compare."""

    if isinstance(value, dict):
        return (
            "map",
            tuple(
                sorted(
                    (key, getattr(key, "origin", ""), _identity(item))
                    for key, item in cast("dict[str, object]", value).items()
                )
            ),
        )
    if isinstance(value, list):
        items = cast("list[object]", value)
        return ("list", getattr(value, "origin", ""), tuple(_identity(item) for item in items))
    return (type(value).__name__, getattr(value, "origin", ""), value)


@dataclass(frozen=True, slots=True)
class _FrontmatterChange:
    diff: FrontmatterDiff | None
    # Whether the disclosure lists each side, so its changed lines count as shown.
    old_shown: bool
    new_shown: bool
    # Two values differ that the disclosure writes alike, so it draws them unchanged.
    hidden: bool


def _frontmatter_diff(old: str | None, new: str | None) -> _FrontmatterChange:
    """Both sides' front matter, merged key by key, as KPress's disclosure lists it."""

    before = _frontmatter_mapping(old)
    after = before if old == new else _frontmatter_mapping(new)
    old_map = before if isinstance(before, dict) else None
    new_map = after if isinstance(after, dict) else None
    if old_map is None and new_map is None:
        return _FrontmatterChange(None, False, False, False)
    rows = {str(key): value for key, value in (old_map or {}).items()}
    now = {str(key): value for key, value in (new_map or {}).items()}
    entries: list[FrontmatterDiffEntry] = []
    hidden = False
    for key in sorted(rows.keys() | now.keys()):
        was, value = rows.get(key, _MISSING), now.get(key, _MISSING)
        was_text = None if was is _MISSING else str(was)
        text = None if value is _MISSING else str(value)
        if was is not _MISSING and value is not _MISSING and _identity(was) == _identity(value):
            assert text is not None
            entries.append({"key": key, "change": "context", "text": text})
            continue
        if text is not None and was_text == text:
            # A value whose type changed and whose text did not, such as `false` and
            # "False": the disclosure cannot show it, so Source does.
            hidden = True
            entries.append({"key": key, "change": "context", "text": text})
            continue
        if was_text is not None:
            entries.append({"key": key, "change": "removed", "text": was_text})
        if text is not None:
            entries.append({"key": key, "change": "added", "text": text})
    change: Literal["context", "modified", "removed", "added"]
    if old_map is None:
        change = "added"
    elif new_map is None:
        change = "removed"
    elif any(entry["change"] != "context" for entry in entries):
        change = "modified"
    else:
        change = "context"
    return _FrontmatterChange(
        {"change": change, "entries": entries}, old_map is not None, new_map is not None, hidden
    )


def _project(
    old: bytes | None, new: bytes | None, patch: FilePatch, namespace: str, limits: _Limits
) -> PreparedMarkdownDiff:
    before, after = old or b"", new or b""
    if len(before) + len(after) > limits.input_bytes:
        raise _OverBudget("Markdown input bytes")
    if max(before.count(b"["), after.count(b"[")) > limits.link_openers:
        raise _OverBudget("Markdown link-label work")
    split = [_LONE_CR.search(data) is not None for data in (before, after)]
    if (
        limits.container_lines != inf
        and max(
            # Counted where MarkdownIt starts a line, a lone carriage return's included.
            len(_CONTAINER_LINE.findall(_LONE_CR.sub(b"\n", data) if lone else data))
            for data, lone in zip((before, after), split, strict=True)
        )
        > limits.container_lines
    ):
        raise _OverBudget("Markdown container lines")
    old_lines, new_lines = _lines(old), _lines(new)
    if patch.truncated:
        # No adapter cuts one file's patch today; a cut one cannot vouch for its lines.
        raise _Unsupported("truncated patch")
    unchanged, removed, added = _correspondence(old_lines, new_lines, patch)
    if any(split):
        old_lines, old_at = _markdown_lines(old_lines)
        new_lines, new_at = _markdown_lines(new_lines)
        # An unchanged Git line is the same bytes on both sides, so the same lines.
        unchanged = {
            left: right
            for old_line, new_line in unchanged.items()
            for left, right in zip(old_at[old_line], new_at[new_line], strict=True)
        }
        removed = {line for git in removed for line in old_at[git]}
        added = {line for git in added for line in new_at[git]}
    old_side = _parse(_decoded(before), limits.tokens)
    new_side = _parse(_decoded(after), limits.tokens)
    if not limits.raw_html and any(
        _is_raw(member)
        for side in (old_side, new_side)
        for token in side.tokens
        for member in (token, *(token.children or ()))
    ):
        raise _OverBudget("raw HTML on a thread")
    shown = _frontmatter_diff(old_side.frontmatter, new_side.frontmatter)
    frontmatter = shown.diff
    if old_side.elements + new_side.elements > limits.nodes:
        raise _OverBudget("combined Markdown elements")
    old_blocks, old_nodes = _render(old_side, limits.nodes - new_side.elements)
    new_blocks, new_nodes = _render(new_side, limits.nodes - old_nodes)
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
        limits.nodes,
    )
    projector.walk(old_blocks, new_blocks)
    projector.flag_moves()
    if frontmatter is not None and frontmatter["change"] != "context":
        # The disclosure shows what changed in the front matter's lines. It cannot say
        # which line a key came from, so a comment changed beside a key counts as shown;
        # a side it does not list keeps its lines unmapped (mb-8274 review D2).
        if shown.old_shown:
            projector.removed.difference_update(range(old_side.offset))
        if shown.new_shown:
            projector.added.difference_update(range(new_side.offset))
    # A blank separator beside an already visible addition or deletion adds no
    # information to the notice. Standalone whitespace changes still point to Source.
    has_visual_change = any(block["kind"] != "context" for block in projector.blocks) or (
        frontmatter is not None and frontmatter["change"] != "context"
    )
    unmapped = any(old_lines[i].strip() for i in projector.removed) or any(
        new_lines[i].strip() for i in projector.added
    )
    source_only = (
        projector.notice
        or shown.hidden
        or unmapped
        or any(block["source_only"] for block in projector.blocks)
        or (
            not has_visual_change
            and (projector.blank or bool(projector.removed or projector.added))
        )
    )
    projection: MarkdownDiffProjection = {
        "version": MARKDOWN_DIFF_VERSION,
        "status": "ready",
        "blocks": projector.blocks,
        "source_only": source_only,
    }
    if frontmatter is not None:
        projection["frontmatter"] = frontmatter
    return PreparedMarkdownDiff(projection, tuple(projector.references))


def unavailable_markdown_diff(
    status: Literal["unsupported", "too_large"], reason: MarkdownRefusal | None = None
) -> PreparedMarkdownDiff:
    """A projection that refuses, with no partial HTML, and *reason* where one is known."""

    projection: MarkdownDiffProjection = {
        "version": MARKDOWN_DIFF_VERSION,
        "status": status,
        "blocks": [],
        "source_only": False,
    }
    if reason is not None:
        projection["reason"] = reason
    return PreparedMarkdownDiff(projection, ())


def prepare_markdown_diff(
    *,
    old: bytes | None,
    new: bytes | None,
    patch: FilePatch,
    namespace: str,
    stoppable: bool = False,
) -> PreparedMarkdownDiff:
    """The projection with its live local destinations still unbound.

    It holds only plain data, so a worker process can compute it and the server bind it.
    *stoppable* says the caller stops this run at a deadline, as the Markdown child's
    server does, so the input budgets of a run nothing stops do not apply (:class:`_Limits`).
    """

    try:
        return _project(old, new, patch, namespace, _limits(stoppable))
    except _OverBudget as refused:
        return unavailable_markdown_diff("too_large", refused.reason)
    except _Unsupported as refused:
        return unavailable_markdown_diff("unsupported", refused.reason)


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
            "lines": block["lines"],
        }
        for block in projection["blocks"]
    ]
    answer: MarkdownDiffProjection = {
        "version": projection["version"],
        "status": projection["status"],
        "blocks": blocks,
        "source_only": projection["source_only"],
    }
    if "frontmatter" in projection:
        answer["frontmatter"] = projection["frontmatter"]
    if "reason" in projection:
        answer["reason"] = projection["reason"]
    return answer


def project_markdown_diff(
    *,
    old: bytes | None,
    new: bytes | None,
    patch: FilePatch,
    namespace: str,
    rewrite_local: _RewriteLocal | None = None,
    stoppable: bool = False,
) -> MarkdownDiffProjection:
    """Return a versioned projection; unavailable projections carry no partial HTML.

    Local destinations are inert unless the caller binds them to the head snapshot.
    *stoppable* is :func:`prepare_markdown_diff`'s.
    """

    return bind_markdown_diff(
        prepare_markdown_diff(
            old=old, new=new, patch=patch, namespace=namespace, stoppable=stoppable
        ),
        rewrite_local,
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
