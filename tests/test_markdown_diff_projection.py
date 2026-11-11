"""Source-range witness and inert markup for rendered Git Markdown diffs."""

from __future__ import annotations

import difflib
from collections.abc import Sequence

import pytest

from metabrowser.diff.format import FilePatch, Hunk, LineOp, LineRecord
from metabrowser.diff.markdown_projection import (
    MARKDOWN_DIFF_MAX_BYTES,
    MarkdownDiffProjection,
    project_markdown_diff,
)


def _patch(old: bytes | None, new: bytes | None, context: int = 3) -> FilePatch:
    before = (old or b"").decode().splitlines(keepends=True)
    after = (new or b"").decode().splitlines(keepends=True)
    hunks: list[Hunk] = []

    def records(part: Sequence[str], op: LineOp) -> list[LineRecord]:
        return [
            LineRecord(op=op, text=line.removesuffix("\n"), no_newline=not line.endswith("\n"))
            for line in part
        ]

    for group in difflib.SequenceMatcher(None, before, after, autojunk=False).get_grouped_opcodes(
        context
    ):
        lines: list[LineRecord] = []

        _, start_old, _, start_new, _ = group[0]
        _, _, end_old, _, end_new = group[-1]
        count_old, count_new = end_old - start_old, end_new - start_new
        for action, old_start, old_end, new_start, new_end in group:
            if action == "equal":
                lines.extend(records(before[old_start:old_end], LineOp.context))
            if action in {"replace", "delete"}:
                lines.extend(records(before[old_start:old_end], LineOp.delete))
            if action in {"replace", "insert"}:
                lines.extend(records(after[new_start:new_end], LineOp.add))
        hunks.append(
            Hunk(
                old_start=start_old + bool(count_old),
                old_count=count_old,
                new_start=start_new + bool(count_new),
                new_count=count_new,
                lines=tuple(lines),
            )
        )
    return FilePatch(file_id="markdown", hunks=tuple(hunks), truncated=False)


def _project(
    old: bytes | None, new: bytes | None, *, namespace: str = "comparison/file", context: int = 3
) -> MarkdownDiffProjection:
    return project_markdown_diff(
        old=old,
        new=new,
        patch=_patch(old, new, context),
        namespace=namespace,
        rewrite_local=lambda href, _image: href,
    )


def test_redlines_preserve_inline_markdown_and_untouched_blocks() -> None:
    old = b"# Topic\n\nThis is **old** documentation.\n\n> Keep the note.\n"
    new = old.replace(b"**old**", b"**updated**")
    result = _project(old, new)
    assert result["status"] == "ready"
    assert result["source_only"] is False
    assert [block["kind"] for block in result["blocks"]] == [
        "context",
        "removed",
        "added",
        "context",
    ]
    assert [block["html"] for block in result["blocks"][1:3]] == [
        "<p>This is <strong><del>old</del></strong> documentation.</p>",
        "<p>This is <strong><ins>updated</ins></strong> documentation.</p>",
    ]


def test_same_rendered_words_with_link_destination_change_is_source_only() -> None:
    old = b"See [the guide][doc].\n\n[doc]: ./old.md\n"
    result = _project(old, old.replace(b"old.md", b"new.md"))
    assert result["status"] == "ready"
    assert result["source_only"] is True
    assert [block["html"] for block in result["blocks"]] == [
        "<p>See <span>the guide</span>.</p>",
        '<p>See <a href="./new.md">the guide</a>.</p>',
    ]


def test_distinct_ranges_keep_repeated_blocks_in_source_order() -> None:
    old = b"Repeated.\n\nMiddle line.\n\nRepeated.\n"
    result = _project(old, old.replace(b"Middle", b"Updated"), context=0)
    assert result["status"] == "ready"
    assert [block["html"] for block in result["blocks"]] == [
        "<p>Repeated.</p>",
        "<p><del>Middle</del> line.</p>",
        "<p><ins>Updated</ins> line.</p>",
        "<p>Repeated.</p>",
    ]


def test_heading_and_fragment_names_are_scoped_by_file_and_side() -> None:
    old = b"# Same\n\n# Same\n\n[Earlier](#same)\n\n![old](old.png)\n"
    new = b"# Same\n\n# New\n\n[Second](#new)\n\n![new](new.png)\n"
    result = _project(old, new)
    assert result["status"] == "ready"
    blocks = result["blocks"]
    assert [block["kind"] for block in blocks] == ["context"] + ["removed"] * 3 + ["added"] * 3
    old_id = blocks[1]["html"].split('"')[1]
    new_id = blocks[4]["html"].split('"')[1]
    assert old_id.endswith("-old-same-1")
    assert new_id.endswith("-new-new")
    assert f'href="#{new_id}"' in blocks[5]["html"]
    assert "<a" not in blocks[2]["html"]
    assert blocks[3]["html"] == "old"
    assert 'src="new.png"' in blocks[6]["html"]
    another_file = _project(old, new, namespace="comparison/another")
    assert new_id not in another_file["blocks"][4]["html"]


@pytest.mark.parametrize(
    ("old", "new", "kind", "expected"),
    [
        (None, b"*Added*", "added", "<p><em>Added</em></p>"),
        (b"*Deleted*\n", None, "removed", "<p><em>Deleted</em></p>"),
        (b"old\r\n", b"new\r\n", "added", "<p><ins>new</ins></p>"),
    ],
)
def test_missing_sides_and_git_line_endings(
    old: bytes | None, new: bytes | None, kind: str, expected: str
) -> None:
    result = _project(old, new)
    assert result["status"] == "ready"
    assert result["blocks"][-1]["kind"] == kind
    assert result["blocks"][-1]["html"] == expected


def test_structural_edits_keep_complete_table_and_code_blocks() -> None:
    old = b"| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```python\nvalue = 1\n```\n"
    new = old.replace(b"| 1 |", b"| 3 |").replace(b"value = 1", b"value = 4")
    result = _project(old, new)
    assert result["status"] == "ready"
    blocks = result["blocks"]
    assert [block["kind"] for block in blocks] == ["removed", "removed", "added", "added"]
    assert "<table>" in blocks[0]["html"] and "</table>" in blocks[0]["html"]
    assert blocks[1]["html"].startswith("<pre><code>")
    assert "<td>3</td>" in blocks[2]["html"]
    assert "<span>4</span>" in blocks[3]["html"]


def test_ambiguous_inline_runs_keep_whole_changed_blocks() -> None:
    result = _project(b"Repeat repeat repeat.\n", b"Repeat repeat.\n")
    assert result["status"] == "ready"
    assert [block["html"] for block in result["blocks"]] == [
        "<p>Repeat repeat repeat.</p>",
        "<p>Repeat repeat.</p>",
    ]


@pytest.mark.parametrize(
    "text",
    [
        b"<script>alert('unsafe')</script>\n",
        b"note[^n]\n\n[^n]: Note text\n",
    ],
)
def test_unverified_render_shapes_fall_back_without_partial_html(text: bytes) -> None:
    result = _project(None, text)
    assert result == {
        "version": "markdown-diff-v1",
        "status": "unsupported",
        "blocks": [],
        "source_only": False,
    }


def test_mismatched_patch_never_labels_a_different_snapshot() -> None:
    old = b"Original.\n"
    new = b"Updated.\n"
    result = project_markdown_diff(
        old=old, new=new, patch=_patch(old, b"Different.\n"), namespace="comparison/file"
    )
    assert result["status"] == "unsupported"
    assert result["blocks"] == []


def test_budget_checked_before_starting_markdown_work(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> None:
        pytest.fail("ran KPress before applying the byte budget")

    monkeypatch.setattr("metabrowser.diff.markdown_projection.parse_markdown", unexpected)
    text = b"x" * (MARKDOWN_DIFF_MAX_BYTES + 1)
    assert _project(None, text)["status"] == "too_large"


def test_frontmatter_stays_out_of_prose_and_keeps_original_git_ranges() -> None:
    old = b"---\ntitle: Old\n---\n\nThe **old** content.\n"
    new = old.replace(b"Old", b"New").replace(b"**old**", b"**new**")
    result = _project(old, new)
    assert result["status"] == "ready"
    assert result["source_only"] is True
    assert [block["html"] for block in result["blocks"]] == [
        "<p>The <strong><del>old</del></strong> content.</p>",
        "<p>The <strong><ins>new</ins></strong> content.</p>",
    ]


def test_rewrite_local_uses_only_live_links_and_assets() -> None:
    old = b"[old](../old.md)\n\n![old](../old.png)\n"
    new = b"[new](../new.md)\n\n![new](../new.png)\n\n[outside](https://example.com)\n"
    seen: list[tuple[str, bool]] = []

    def rewrite(href: str, image: bool) -> str | None:
        seen.append((href, image))
        return None if image else "/view/revision/new.md"

    result = project_markdown_diff(
        old=old, new=new, patch=_patch(old, new), namespace="comparison/file", rewrite_local=rewrite
    )
    assert result["status"] == "ready"
    assert seen == [("../new.md", False), ("../new.png", True)]
    assert [block["html"] for block in result["blocks"][:4]] == [
        "<p><span>old</span></p>",
        "old",
        '<p><a href="/view/revision/new.md">new</a></p>',
        "new",
    ]
    assert 'href="https://example.com"' in result["blocks"][-1]["html"]


def test_comments_stay_out_of_prose_without_shifting_git_ranges() -> None:
    old = b"<!-- old metadata -->\n\nThe old sentence.\n\n<!-- Footer -->\n"
    new = old.replace(b"old", b"new")
    result = _project(old, new)
    assert result["status"] == "ready"
    assert result["source_only"] is True
    assert [block["html"] for block in result["blocks"]] == [
        "<p>The <del>old</del> sentence.</p>",
        "<p>The <ins>new</ins> sentence.</p>",
    ]


def test_unbound_references_cannot_point_into_the_live_checkout() -> None:
    new = b"[local](local.md)\n\n![local image](local.png)\n"
    result = project_markdown_diff(
        old=None, new=new, patch=_patch(None, new), namespace="comparison/file"
    )
    assert result["status"] == "ready"
    assert [block["html"] for block in result["blocks"]] == ["<p><a>local</a></p>", "local image"]


def test_link_label_work_is_bounded_before_either_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> None:
        pytest.fail("ran MarkdownIt before applying the link-label work budget")

    monkeypatch.setattr("metabrowser.diff.markdown_projection.MarkdownIt", unexpected)
    text = b"[\n" * 300 + b"text" + b"]" * 300
    assert _project(None, text)["status"] == "too_large"


def test_soft_wrapped_paragraph_redlines_only_the_changed_source_line() -> None:
    old = b"Introductory prose soft wraps across the\nold second line.\n"
    result = _project(old, old.replace(b"old", b"new"), context=0)
    assert result["status"] == "ready"
    assert [block["html"] for block in result["blocks"]] == [
        "<p>Introductory prose soft wraps across the\n<del>old</del> second line.</p>",
        "<p>Introductory prose soft wraps across the\n<ins>new</ins> second line.</p>",
    ]
