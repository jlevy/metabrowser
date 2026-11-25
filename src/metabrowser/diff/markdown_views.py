"""The two rendered views of a Markdown diff: Full, every block, and Concise, the changes.

Concise shows each change with :data:`CONTEXT_BLOCKS` unchanged blocks on either side of
it and folds the unchanged blocks between, so a long document reads as its changes. A
block whose source says more than its render shows (``source_only``) never folds: Source
is how a reader reaches such a change, and a fold would hide where to look. Full shows
every block. The page draws both from one answer's ``folds``
(``builtin_plugins/diff/diff-markdown.js``), so this module is the one place that says
which blocks fold.

A fold that spans :data:`INLINE_FOLD_MAX_LINES` source lines or more is *withheld* from a
Concise answer: its blocks are left out, and the page asks for them
(``GET github/pull-rendered-diff`` with ``blocks=``) when the reader opens the fold or
follows a link to a heading inside it, which the fold's ``ids`` name. A shorter fold is
sent with the answer, so opening it asks for nothing.

A pull request's Docs tab opens a document in Full when it is within
:data:`FULL_MAX_BLOCKS` and :data:`FULL_MAX_BYTES` (:func:`prefers_full`), and in Concise
past either, since what a whole draw costs grows with the document.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from html import unescape

from metabrowser.diff.markdown_projection import MarkdownDiffBlock

# The unchanged blocks kept beside a change. A run of unchanged blocks folds when it holds
# more than twice this and one more, so a fold always hides at least two blocks.
CONTEXT_BLOCKS = 2
# The source lines a fold may span and still be sent with a Concise answer; a fold this
# long or longer is withheld until the reader opens it. Sent, a fold costs its HTML in the
# answer; withheld, one request when it opens. Measured 2026-11-24 against a local server at
# a load average of about 430, in headless Chrome 152: in finterm-ai/investment-research
# #22, a fold sent opened in 1-2 ms (six folds, two runs), and a withheld one of 49 blocks
# and 272 lines in 20-135 ms (four opens; its request took 8-118 ms, 25.6 KB, 6.6 KB
# compressed); its file's Concise answer was 10.6 KB and its Full one 34.9 KB. Its HTML is
# 94 bytes a line, so a fold sent adds at most about 9 KB to an answer, and a withheld one
# only the anchors of its headings, however long the unchanged run. The answer's size was
# not timed apart from the request.
INLINE_FOLD_MAX_LINES = 100
# The blocks, and their HTML bytes, of a document the Docs tab opens in Full. Block
# count, not bytes, predicts what drawing them costs: measured 2026-11-24 in headless
# Chrome 152 at 1,280 x 900 on an Apple M1 Pro at a load average of 130 to 195, the
# production draw (`appendBlocks` and `sanitizeBlock` in diff-markdown.js) and its first
# layout and paint, two fresh browsers a size, took 59-62 ms for 500 one-line list items
# and headings (42 KB), 96-100 ms for 1,000 (85 KB), and 369-395 ms for 4,000 (345 KB);
# 76-77 ms for the first 800 blocks of a real book (finterm-ai/investment-research #31,
# 197 KB) and 297-305 ms for all 3,408 (886 KB); and 48-53 ms for 200 paragraphs of
# 2.3 KB (468 KB) and 83-84 ms for 400 (940 KB). So 500 blocks or 512 KiB keeps a whole
# draw near 60 ms in every shape measured. The page draws a document within these bounds
# whole (`WHOLE_UNITS` and `WHOLE_BYTES` in diff-markdown.js, which a test holds equal to
# them) and a longer one a chunk at a time, so past them Full costs a chunk to draw, but its
# answer still holds every block, and the browser's find reaches only the chunks drawn.
FULL_MAX_BLOCKS = 500
FULL_MAX_BYTES = 512 * 1024

# A heading's anchor, as KPress writes it into a block's HTML.
_ID = re.compile(r'\sid="([^"]+)"')


@dataclass(frozen=True, slots=True)
class Fold:
    """One run of unchanged blocks Concise folds: *count* blocks of the projection from
    *at*, spanning *lines* source lines, with the anchors of the headings among them."""

    at: int
    count: int
    lines: int
    ids: tuple[str, ...]

    @property
    def withheld(self) -> bool:
        """Whether a Concise answer leaves this fold's blocks out."""

        return self.lines >= INLINE_FOLD_MAX_LINES


def _foldable(block: MarkdownDiffBlock) -> bool:
    return block["kind"] == "context" and not block["source_only"]


def fold_runs(blocks: Sequence[MarkdownDiffBlock]) -> list[Fold]:
    """The folds of a projection's blocks, in order."""

    folds: list[Fold] = []
    index = 0
    while index < len(blocks):
        if not _foldable(blocks[index]):
            index += 1
            continue
        first = index
        while index < len(blocks) and _foldable(blocks[index]):
            index += 1
        if index - first <= 2 * CONTEXT_BLOCKS + 1:
            continue
        hidden = blocks[first + CONTEXT_BLOCKS : index - CONTEXT_BLOCKS]
        # Unchanged blocks are the new side's, in its order, so the run spans the lines
        # from its first block's start to its last block's end, blank lines between included.
        lines = hidden[-1]["lines"][1] - hidden[0]["lines"][0]
        ids = tuple(unescape(match) for block in hidden for match in _ID.findall(block["html"]))
        folds.append(Fold(first + CONTEXT_BLOCKS, len(hidden), lines, ids))
    return folds


def prefers_full(count: int, html_bytes: int) -> bool:
    """Whether the Docs tab opens a document of *count* blocks and *html_bytes* in Full."""

    return count <= FULL_MAX_BLOCKS and html_bytes <= FULL_MAX_BYTES
