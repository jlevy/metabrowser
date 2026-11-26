"""The unchanged lines a comparison's hunks leave out, by range (mb-zz81).

``/api/plugin/diff/comparison`` with ``view=lines`` answers a run of one changed file's side,
read from its snapshot, for the page's fold between hunks (diff-view.js, ``renderGapFold``).
``diff/side_lines.py`` cuts a run of a side's lines, from a start or up to an end; the route
reads the side, bounds the ask, and refuses a side it cannot number as the hunks do, and the
patch is written with the context the page counts on. ``tests/golden/cli-api-diff-lines.tryscript.md``
pins the answers through ``metab --api``; these are the cases a transcript would make long.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from metabrowser import server
from metabrowser.builtin_plugins.diff import sidekick
from metabrowser.diff import side_lines as side_lines_module
from metabrowser.diff.side_lines import side_lines, side_lines_before
from tests.diff_fixture_repo import git
from tests.git_pin_harness import pinned_client
from tests.required_tools import needs_git

# ── Cutting a side into lines ──────────────────────────────────────────────


def test_a_run_is_the_sides_lines_from_start_with_where_the_side_ends() -> None:
    cut = side_lines(b"one\ntwo\nthree\n", 2, 5)
    assert (cut.start, cut.lines, cut.line_count, cut.ends_with_newline) == (
        2,
        ("two", "three"),
        3,
        True,
    )


def test_a_last_line_with_no_newline_is_a_line_and_says_so() -> None:
    cut = side_lines(b"one\ntwo", 1, 10)
    assert (cut.lines, cut.line_count, cut.ends_with_newline) == (("one", "two"), 2, False)


def test_an_empty_side_and_a_start_past_the_end_answer_no_lines() -> None:
    assert (side_lines(b"", 1, 5).lines, side_lines(b"", 1, 5).line_count) == ((), 0)
    past = side_lines(b"one\n", 3, 5)
    assert (past.lines, past.line_count, past.start) == ((), 1, 3)


def test_a_line_keeps_its_carriage_return_and_bad_bytes_are_replaced() -> None:
    # A hunk's line keeps what Git wrote of it, a CR among it; bytes that are not UTF-8 are
    # the replacement character, as a patch's undecodable line is.
    cut = side_lines(b"one\r\n\xffx\n", 1, 2)
    assert cut.lines == ("one\r", "�x")


def test_an_answer_stops_before_the_line_that_would_pass_its_byte_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(side_lines_module, "MAX_LINES_ANSWER_BYTES", 10)
    assert side_lines(b"aaaa\nbbbb\ncccc\n", 1, 3).lines == ("aaaa", "bbbb")
    # One line past the bound alone is still answered, so a reader is never stuck.
    assert side_lines(b"a" * 50 + b"\nb\n", 1, 2).lines == ("a" * 50,)


def test_a_start_or_count_below_one_is_refused() -> None:
    with pytest.raises(ValueError):
        side_lines(b"one\n", 0, 1)
    with pytest.raises(ValueError):
        side_lines(b"one\n", 1, 0)
    with pytest.raises(ValueError):
        side_lines_before(b"one\n", 0, 1)


def test_a_run_before_a_line_is_the_lines_up_to_it_with_where_it_starts() -> None:
    content = b"one\ntwo\nthree\nfour\n"
    cut = side_lines_before(content, 4, 2)
    assert (cut.start, cut.lines, cut.line_count) == (2, ("two", "three"), 4)
    # From the side's first line where it asks past it, and to its last past the end.
    assert side_lines_before(content, 3, 10).lines == ("one", "two")
    tail = side_lines_before(content, 6, 3)
    assert (tail.start, tail.lines) == (3, ("three", "four"))
    # Before line 1, and wholly past the end, there is nothing; the start is where it ends.
    assert (side_lines_before(content, 1, 5).start, side_lines_before(content, 1, 5).lines) == (
        1,
        (),
    )
    assert (side_lines_before(content, 20, 5).start, side_lines_before(content, 20, 5).lines) == (
        5,
        (),
    )


def test_a_run_cut_by_its_byte_bound_keeps_the_lines_nearest_where_it_was_asked_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A gap opened upward to a hunk asks for the lines before it, so the lines a short answer
    # keeps are the ones beside that hunk, and the page's nested bar stands for the rest.
    monkeypatch.setattr(side_lines_module, "MAX_LINES_ANSWER_BYTES", 10)
    cut = side_lines_before(b"aaaa\nbbbb\ncccc\ndddd\n", 5, 4)
    assert (cut.start, cut.lines) == (3, ("cccc", "dddd"))
    one = side_lines_before(b"b\n" + b"a" * 50 + b"\n", 3, 2)
    assert (one.start, one.lines) == (2, ("a" * 50,))


@pytest.mark.parametrize("line", [b"a\n", b"x" * 39 + b"\n", b"\xe2\x80\x94\r\n"])
def test_a_run_far_into_a_side_is_the_run_splitting_the_whole_side_would_give(
    line: bytes,
) -> None:
    # The run's start is found by counting newlines in chunks, across the chunks' edges.
    content = line * 50_000 + b"last"
    pieces = content.split(b"\n")
    for start in (1, 2, 8_191, 16_385, 49_999, 50_001):
        want = tuple(piece.decode("utf-8", "replace") for piece in pieces[start - 1 : start + 2])
        cut = side_lines(content, start, 3)
        assert (cut.lines, cut.line_count, cut.ends_with_newline) == (want, 50_001, False)
        before = side_lines_before(content, start + 3, 3)
        assert (before.start, before.lines) == (start, want[: 50_002 - start])


# ── The route ──────────────────────────────────────────────────────────────


class _Query:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)

    def getlist(self, key: str) -> list[str]:
        return [self._params[key]] if key in self._params else []


def _lines(**params: str) -> tuple[int, dict[str, Any]]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _Query({"revision": "HEAD", "view": "lines", **params})
    request.headers = {}
    response = asyncio.run(sidekick.comparison_handler(request))
    return response.status_code, json.loads(bytes(response.body))


def _commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD").decode().strip()


def _repository(root: Path) -> None:
    """A commit that edits a 40-line file at lines 5 and 30, deletes one, changes a binary,
    and edits a file that ends with no newline."""
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    lines = [f"line {number}" for number in range(1, 41)]
    (root / "app.py").write_text("\n".join(lines) + "\n")
    (root / "gone.py").write_text("first\nsecond\n")
    (root / "logo.bin").write_bytes(b"\x00\x01\x02")
    (root / "open.txt").write_text("a\nb\nc")
    _commit(root, "base")
    lines[4] = "line 5, changed"
    lines[29] = "line 30, changed"
    (root / "app.py").write_text("\n".join(lines) + "\n")
    (root / "gone.py").unlink()
    (root / "logo.bin").write_bytes(b"\x00\x01\x03")
    (root / "open.txt").write_text("A\nb\nc")
    _commit(root, "target")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _repository(root)
    server._set_root_dir(root)
    return root


@needs_git
def test_full_source_reads_the_pinned_new_side(repository: Path) -> None:
    status, body = _lines(file="app.py", whole="1")
    assert status == 200
    assert body["start"] == 1
    assert len(body["lines"]) == body["line_count"] == 40
    assert [body["lines"][i] for i in (0, 4, 15, 29, 39)] == [
        "line 1",
        "line 5, changed",
        "line 16",
        "line 30, changed",
        "line 40",
    ]
    status, refusal = _lines(file="app.py", whole="1", count="20")
    assert status == 400 and "whole=1" in refusal["message"]


@needs_git
def test_a_run_of_the_new_side_between_hunks(repository: Path) -> None:
    status, body = _lines(file="app.py", start="9", count="3")
    assert status == 200, body
    assert {key: body[key] for key in ("path", "start", "line_count")} == {
        "path": "app.py",
        "start": 9,
        "line_count": 40,
    }
    assert (body["lines"], body["ends_with_newline"]) == (["line 9", "line 10", "line 11"], True)
    assert body["comparison_id"].startswith("git:") and body["file_id"].startswith("f")


@needs_git
def test_the_end_of_a_side_is_where_its_answer_stops(repository: Path) -> None:
    _status, tail = _lines(file="app.py", start="39", count="10")
    assert (tail["lines"], tail["line_count"]) == (["line 39", "line 40"], 40)
    _status, past = _lines(file="app.py", start="41", count="10")
    assert (past["lines"], past["line_count"]) == ([], 40)
    _status, open_end = _lines(file="open.txt", start="1", count="5")
    assert (open_end["lines"], open_end["ends_with_newline"]) == (["A", "b", "c"], False)


@needs_git
def test_a_run_up_to_a_hunk_is_asked_for_by_its_end(repository: Path) -> None:
    status, body = _lines(file="app.py", end="27", count="3")
    assert status == 200, body
    assert (body["start"], body["lines"]) == (24, ["line 24", "line 25", "line 26"])


@needs_git
def test_a_deleted_file_has_no_new_side_to_read(repository: Path) -> None:
    status, body = _lines(file="gone.py", start="1", count="5")
    assert (status, body["code"]) == (409, "no_side")
    assert body["message"] == "These lines cannot be shown."


@needs_git
def test_a_binary_side_is_refused_as_not_text(repository: Path) -> None:
    status, body = _lines(file="logo.bin", start="1", count="5")
    assert (status, body["code"], body["path"]) == (409, "not_text", "logo.bin")


@needs_git
def test_one_answer_holds_no_more_than_one_open_shows(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sidekick, "DIFF_GAP_LINES", 2)
    _status, body = _lines(file="app.py", start="1", count="40")
    assert body["lines"] == ["line 1", "line 2"]


@needs_git
def test_a_side_past_the_read_bound_is_refused(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sidekick, "MAX_LINES_SIDE_BYTES", 16)
    status, body = _lines(file="app.py", start="1", count="5")
    assert (status, body["code"]) == (409, "blob_too_large")


@needs_git
@pytest.mark.parametrize(
    ("params", "said"),
    [
        ({"start": "1", "count": "5"}, "file"),
        ({"file": "app.py", "start": "0", "count": "5"}, "start"),
        ({"file": "app.py", "start": "1", "count": "x"}, "count"),
        ({"file": "app.py", "start": "\u00b2", "count": "5"}, "start"),
        ({"file": "app.py", "start": "1" * 40, "count": "5"}, "start"),
        ({"file": "app.py", "count": "5"}, "start or an end"),
        ({"file": "app.py", "start": "1", "end": "4", "count": "5"}, "not both"),
        ({"file": "app.py", "end": "0", "count": "5"}, "end"),
    ],
)
def test_an_ask_the_route_cannot_read_is_a_400_naming_what(
    repository: Path, params: dict[str, str], said: str
) -> None:
    status, body = _lines(**params)
    assert (status, body["error"]) == (400, "diff_lines")
    assert said in body["message"]


@needs_git
def test_a_path_the_comparison_does_not_hold_is_a_404(repository: Path) -> None:
    status, body = _lines(file="nowhere.py", start="1", count="5")
    assert status == 404, body


@needs_git
def test_a_file_a_textconv_driver_converts_is_refused_in_a_folder(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _repository(root)
    (root / ".gitattributes").write_text("app.py diff=upper\n")
    _commit(root, "attributes")
    lines = [f"line {number}" for number in range(1, 41)]
    lines[19] = "line 20, changed"
    (root / "app.py").write_text("\n".join(lines) + "\n")
    _commit(root, "convert")
    server._set_root_dir(root)
    # No driver is configured, so the attribute converts nothing and the lines are the file's.
    status, body = _lines(file="app.py", start="1", count="2")
    assert (status, body.get("lines")) == (200, ["line 1", "line 2"]), body
    git(root, "config", "diff.upper.textconv", "tr a-z A-Z <")
    status, body = _lines(file="app.py", start="1", count="2")
    assert (status, body["code"]) == (409, "textconv"), body


@needs_git
def test_a_store_answers_from_its_own_objects_and_keeps_each_run_apart(tmp_path: Path) -> None:
    """A store's answer is kept by its key, so each run, by start, end, and count, is kept
    apart from the others and from the comparison's document, and asking again for one is
    that run's body and tag."""
    work = tmp_path / "work"
    _repository(work)
    target = git(work, "rev-parse", "HEAD").decode().strip()
    store = tmp_path / "store.git"
    git(tmp_path, "clone", "-q", "--bare", "--template=", str(work), str(store))
    asks = [
        {"start": "29", "count": "3"},
        {"start": "29", "count": "2"},
        {"start": "9", "count": "3"},
        {"end": "32", "count": "3"},
        {"start": "29", "count": "3"},
    ]

    async def run() -> list[tuple[int, str, dict[str, Any]]]:
        answers: list[tuple[int, str, dict[str, Any]]] = []
        async with pinned_client(store, target) as (client, _subject):
            for ask in asks:
                response = await client.get(
                    "/api/plugin/diff/comparison",
                    params={"revision": target, "view": "lines", "file": "app.py", **ask},
                )
                answers.append(
                    (response.status_code, response.headers.get("etag", ""), response.json())
                )
        return answers

    answers = asyncio.run(run())
    assert all(status == 200 for status, _tag, _body in answers), answers
    assert [body["lines"] for _status, _tag, body in answers] == [
        ["line 29", "line 30, changed", "line 31"],
        ["line 29", "line 30, changed"],
        ["line 9", "line 10", "line 11"],
        ["line 29", "line 30, changed", "line 31"],
        ["line 29", "line 30, changed", "line 31"],
    ]
    tags = [tag for _status, tag, _body in answers]
    assert all(tags) and len(set(tags[:4])) == 4, tags
    assert tags[4] == tags[0]


# ── The context the hunks were written with ────────────────────────────────


@needs_git
@pytest.mark.parametrize("configured", ["1", "5"])
def test_a_folders_diff_context_does_not_change_the_context_a_comparison_says(
    repository: Path, configured: str
) -> None:
    """The page offers the lines below a last hunk only past a full ``options.context`` of
    trailing context lines (``hunkGaps`` in diff-view.js), so the patch is written with that
    context whatever a reader's ``diff.context`` says, or a file would never offer them, or
    would offer an empty bar."""
    git(repository, "config", "diff.context", configured)
    request = Mock(spec=["query_params", "headers"])
    request.query_params = _Query({"revision": "HEAD", "file": "app.py"})
    request.headers = {}
    response = asyncio.run(sidekick.comparison_handler(request))
    document = json.loads(bytes(response.body))
    assert document["resolved"]["options"]["context"] == 3
    (patch,) = document["patches"].values()
    ranges = [(hunk["new_start"], hunk["new_count"], hunk["lines"][-3:]) for hunk in patch["hunks"]]
    assert [(start, count) for start, count, _tail in ranges] == [(2, 7), (27, 7)]
    assert all(line["op"] == "context" for _s, _c, tail in ranges for line in tail)
