"""How much render work a Markdown document an untrusted author wrote may cost the server.

Under the untrusted profile, which a pinned revision always runs under, a Markdown file's
author is not the reader's to trust, and a render holds the interpreter for as long as it
takes. A document past :data:`DOCUMENT_BYTES`, or estimated past :data:`DOCUMENT_WORK_MS`
by :func:`document_work_ms`, therefore opens as Source and is not rendered; one within
them renders with its fenced code plain (``kpress_adapter``'s ``plain_code``), since
highlighting costs what no estimate over the text bounds. ``git/content_routes.py``
applies both to the pinned viewer: its file envelope offers no rendered view for such a
document, and its render route refuses one.

The bounds and their measurements came with the pull request's revision page, which
rendered a pull request author's Markdown on its own; that page is gone, and the pinned
viewer, which a pull request's View on branch opens one click from every changed file,
now holds them.
"""

from __future__ import annotations

import re
from typing import Final

# The largest Markdown file rendered as a document; a larger one opens as Source. An
# untrusted author writes it, so DOCUMENT_WORK_MS below bounds what its render costs; this
# cap bounds the document the estimate reads, and every measurement below is of documents
# up to it. Review B of #347 measured 16.99 s for a run of `[` at an earlier 256 KiB cap.
DOCUMENT_BYTES: Final = 64 * 1024
# The whole document's render work a page may spend, as an estimate in milliseconds; a
# document estimated above it opens as Source. Measured 2026-11-11 with the revision
# page's KPress render on one thread, three adjacent runs per shape with the fastest kept,
# load average 1.9 to 4.7: ordinary prose costs 0.5 µs a byte (24 ms at 64 KiB), but what
# the renderer spends grows with constructs an author can repeat, linearly in all of them
# but task lists, and splitting the text into paragraphs does not lower it. So the
# estimate charges each construct the most it was measured to cost, over the whole
# document:
# - per `[` whose next bracket on its line is not a `]`, 280 µs (followed by inline
#   content: `[*a*a` took 1.8 s for 6,554, as much with one `]` at the end, and `[<a`
#   168 µs each);
# - per `[` its line closes before another opens, 60 µs (a bare run 60 µs each,
#   `[*a*a]` 44 µs, a line of prose with a link 0.1 ms);
# - per `$`, 90 µs (inline math, 2.7 s for 32,768);
# - per `|`, 40 µs (a table, 1.2 to 1.3 s for 32,768 at any width);
# - per line that starts a block (a heading, list item, quote, table row, setext rule, or
#   container), 55 µs (16,384 headings 0.73 s, list items 0.88 s);
# - per line, 26 µs more (64 KiB of one-character paragraphs took 0.75 s, of lines that
#   end in a backslash 0.55 s);
# - per other inline delimiter, 20 µs (`*a` runs 0.48 s, autolinks 0.29 s, code spans
#   0.35 s).
# Fenced code renders as escaped plain text and is charged as the text it is.
# Highlighting it cost what no estimate over the text bounds: review G found a 1.6 KB
# `console` line that took 12 s, and 48 KB of `devicetree` that took 79 s.
# Task-list items cost more than linearly (1,024 took 0.19 s, 2,048 0.55 s, 8,192 6.4 s),
# so at most TASK_ITEMS are admitted, behind any container, each charged 190 µs.
# Re-measured the same day for review G at load average 12 to 20, where 64 KiB of prose
# took 28 to 30 ms, over about 200 shapes and mixes each grown to the bound: the worst
# admitted render is 417 ms (lines that end in a backslash), then 415 ms (the same mixed
# with inline math), 410 ms (a wide table), and 406 ms (inline math). Scaled to the quiet
# run's prose, the worst is about 335 to 350 ms. One fence of any language reviews F and
# G timed renders in 4 to 10 ms at the bound, and the most fences, short ones one after
# another, in 129 ms. Of this repository's 346 Markdown files up to 64 KiB, the 64
# under node_modules, and 441 from nine other repositories, none opens as Source. Before,
# 16,384 `[` admitted a 64 KiB task list that took 6.4 s, and before reviews F and G
# admitted documents took up to 1.2 s and highlighted fences 79 s. The estimate covers
# the constructs measured; it is not a deadline, which only a renderer that can be
# stopped could give.
DOCUMENT_WORK_MS: Final = 400
TASK_ITEMS: Final = 1024
_UNPAIRED_OPENER_US: Final = 280
_PAIRED_OPENER_US: Final = 60
_HEAVY_US: Final = ((b"$", 90), (b"|", 40))
_DELIMITERS: Final = b"*_`~<>!]&:^=+{}"
_DELIMITER_US: Final = 20
_BLOCK_LINE_US: Final = 55
_LINE_US: Final = 26
_TASK_ITEM_US: Final = 190
_BYTE_US: Final = 0.5
_BLOCK_LINE: Final = re.compile(rb"^[ \t]*(?:[#>|=+*:-]|[0-9]+[.)])", re.MULTILINE)
# A checkbox after any container prefix: quote markers, list markers, or neither, for a
# list item whose first line is blank. KPress renders a task in each; a checkbox that
# starts a line of a paragraph is counted too, which only overcounts.
_TASK_ITEM: Final = re.compile(
    rb"^(?:[ \t>]*+(?:[-*+]|[0-9]{1,9}[.)])[ \t]++)*+[ \t>]*+\[[ xX]\]", re.MULTILINE
)
# A `[` whose line holds a `]` before any other bracket. The lookahead stops at the next
# bracket, so each scan ends where the next begins, and the whole count is linear.
_PAIRED_OPENER: Final = re.compile(rb"\[(?=[^\[\]\n]*\])")


def document_work_ms(body: bytes) -> float:
    """The render work *body* may cost, at the most each construct was measured to cost.

    Infinite past :data:`TASK_ITEMS` task-list items, whose cost grows faster than their
    count. Blocking and linear in *body*; run it off the event loop.
    """
    # Every line ending is one, as the renderer reads it.
    body = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    tasks = len(_TASK_ITEM.findall(body))
    if tasks > TASK_ITEMS:
        return float("inf")
    work = _BYTE_US * len(body) + _TASK_ITEM_US * tasks
    paired = len(_PAIRED_OPENER.findall(body))
    work += _PAIRED_OPENER_US * paired + _UNPAIRED_OPENER_US * (body.count(b"[") - paired)
    work += sum(cost * body.count(char) for char, cost in _HEAVY_US)
    work += _DELIMITER_US * sum(body.count(bytes((char,))) for char in _DELIMITERS)
    work += _BLOCK_LINE_US * len(_BLOCK_LINE.findall(body))
    work += _LINE_US * body.count(b"\n")
    return work / 1000


def within_render_bound(body: bytes) -> bool:
    """Whether a document an untrusted author wrote may be rendered. Blocking and linear."""

    return len(body) <= DOCUMENT_BYTES and document_work_ms(body) <= DOCUMENT_WORK_MS


__all__ = [
    "DOCUMENT_BYTES",
    "DOCUMENT_WORK_MS",
    "TASK_ITEMS",
    "document_work_ms",
    "within_render_bound",
]
