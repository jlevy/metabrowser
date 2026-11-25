"""Which runs of a Markdown diff's unchanged blocks fold, and which folds a Concise answer
withholds (``metabrowser.diff.markdown_views``).

The route's goldens (``tests/golden/cli-github-pull-rendered-views.txt``) show a fold of
each kind through ``metab --api``; these hold the edges: the shortest run that folds, a
block whose source says more than its render, the line count at the withholding bound,
the Docs tab's Full bound, and that the page draws a document within it whole.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pytest

from metabrowser.diff.markdown_projection import MarkdownDiffBlock
from metabrowser.diff.markdown_views import (
    CONTEXT_BLOCKS,
    FULL_MAX_BLOCKS,
    FULL_MAX_BYTES,
    INLINE_FOLD_MAX_LINES,
    Fold,
    fold_runs,
    prefers_full,
)


def _block(
    kind: Literal["context", "removed", "added"],
    start: int,
    *,
    lines: int = 1,
    html: str = "<p>x</p>",
    source_only: bool = False,
) -> MarkdownDiffBlock:
    return {
        "kind": kind,
        "side": "old" if kind == "removed" else "new",
        "html": html,
        "source_only": source_only,
        "lines": [start, start + lines],
    }


def _run(count: int, *, first_line: int = 2, lines: int = 1) -> list[MarkdownDiffBlock]:
    """*count* unchanged blocks of *lines* lines each, a blank line between them."""

    return [
        _block("context", first_line + index * (lines + 1), lines=lines) for index in range(count)
    ]


def test_a_run_folds_only_when_it_hides_two_blocks_or_more() -> None:
    edit = _block("added", 0)
    short = [edit, *_run(2 * CONTEXT_BLOCKS + 1)]
    assert fold_runs(short) == []
    long = [edit, *_run(2 * CONTEXT_BLOCKS + 2)]
    assert fold_runs(long) == [Fold(at=1 + CONTEXT_BLOCKS, count=2, lines=3, ids=())]


def test_a_block_whose_source_says_more_never_folds_and_splits_its_run() -> None:
    run = _run(13)
    run[6] = {**run[6], "source_only": True}
    folds = fold_runs([_block("added", 0), *run])
    # Six blocks on each side of the flagged one: each keeps two beside each end.
    assert [(fold.at, fold.count) for fold in folds] == [(3, 2), (10, 2)]


def test_a_fold_spans_the_lines_from_its_first_block_to_its_last() -> None:
    run = _run(2 * CONTEXT_BLOCKS + 3, lines=4)
    (fold,) = fold_runs([_block("removed", 0), *run])
    hidden = run[CONTEXT_BLOCKS : CONTEXT_BLOCKS + 3]
    assert fold.lines == hidden[-1]["lines"][1] - hidden[0]["lines"][0] == 14


def test_a_fold_names_the_headings_it_hides_as_the_page_links_to_them() -> None:
    run = _run(2 * CONTEXT_BLOCKS + 2)
    run[CONTEXT_BLOCKS] = {
        **run[CONTEXT_BLOCKS],
        "html": '<h2 id="user-content-q&amp;a">Q&amp;A</h2>',
    }
    (fold,) = fold_runs([_block("added", 0), *run])
    assert fold.ids == ("user-content-q&a",)


@pytest.mark.parametrize(
    ("lines", "withheld"),
    [(INLINE_FOLD_MAX_LINES - 1, False), (INLINE_FOLD_MAX_LINES, True)],
)
def test_a_fold_is_withheld_from_its_bound_of_lines(lines: int, withheld: bool) -> None:
    assert Fold(at=0, count=2, lines=lines, ids=()).withheld is withheld


def test_the_docs_tab_opens_full_within_both_bounds() -> None:
    assert prefers_full(FULL_MAX_BLOCKS, FULL_MAX_BYTES)
    assert not prefers_full(FULL_MAX_BLOCKS + 1, 0)
    assert not prefers_full(0, FULL_MAX_BYTES + 1)


def test_the_page_draws_whole_what_the_docs_tab_opens_in_full() -> None:
    """``WHOLE_UNITS`` and ``WHOLE_BYTES`` in diff-markdown.js, past which the page draws a
    document a chunk at a time, are the Full bounds, so a document Docs opens in Full keeps
    the browser's find and Select All over all of it."""

    script = (
        Path(__file__).resolve().parents[1]
        / "src/metabrowser/builtin_plugins/diff/diff-markdown.js"
    ).read_text(encoding="utf-8")
    units = re.search(r"^const WHOLE_UNITS = (\d+);$", script, re.MULTILINE)
    whole_bytes = re.search(r"^const WHOLE_BYTES = (\d+) \* 1024;$", script, re.MULTILINE)
    assert units is not None and whole_bytes is not None
    assert int(units.group(1)) == FULL_MAX_BLOCKS
    assert int(whole_bytes.group(1)) * 1024 == FULL_MAX_BYTES
