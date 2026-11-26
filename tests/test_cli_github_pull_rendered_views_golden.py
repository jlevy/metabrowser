"""Golden transcript: a rendered Markdown file's Full and Concise views through ``metab --api``.

``GET github/pull-rendered-diff`` answers a ready Markdown file in the view ``view``
names (:mod:`metabrowser.builtin_plugins.github.pull_rendered_diff`): ``full``, every
block; ``concise``, each change with the unchanged blocks beside it and each longer run
folded, a fold of :data:`~metabrowser.diff.markdown_views.INLINE_FOLD_MAX_LINES` source
lines or more withheld, its blocks left out and its headings' anchors named; and
``prefer-full``, Full for a document within the Docs tab's bounds and Concise past them.
``blocks=I-J`` answers a withheld fold's blocks. Each answer lists the projection's
``count`` of blocks and its ``folds``, so the page draws either view once it holds the
blocks. A request the route cannot read is refused with its code.

Pull request 7's head edits three paragraphs of a document whose unchanged runs between
them fold: a short run (sent with the Concise answer) and a long one holding a heading
(withheld). This drives it in-process, as ``tests/test_cli_github_pull_rendered_golden.py``
drives the route's admission and refusals, and writes
``tests/golden/cli-github-pull-rendered-views.txt``. Every answer's KPress asset manifest
is the same, so the transcript prints it once and names it after.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser.diff import markdown_views
from metabrowser.diff.markdown_views import INLINE_FOLD_MAX_LINES
from tests.github_pull_fixture import CANONICAL, DEFAULT_BRANCH, Origin
from tests.golden_harness import (
    Labels,
    check_golden,
    label_home,
    normalize_pull_comparison_scopes,
    operational_once,
    run_metab,
)
from tests.test_cli_github_pull_golden import PULL, ROUTE, _body, _Session
from tests.test_cli_github_pull_rendered_golden import (  # pyright: ignore[reportPrivateUsage]
    _ANCHOR,  # pyright: ignore[reportPrivateUsage]
    _answering,  # pyright: ignore[reportPrivateUsage]
    _commit,  # pyright: ignore[reportPrivateUsage]
    _git,  # pyright: ignore[reportPrivateUsage]
)

# A paragraph of one source line, and one of many.
_LONG = 60


def _short(name: str) -> bytes:
    return f"Short paragraph {name}.\n\n".encode()


def _long(name: str) -> bytes:
    return b"".join(f"Line {line} of long paragraph {name}.\n".encode() for line in range(_LONG))


_FOLDS = (
    b"# Folds\n\nChange one is old.\n\n"
    + b"".join(_short(name) for name in "ABCDEF")
    + b"Change two is old.\n\n"
    + _short("G")
    + _short("H")
    + b"## Deep heading\n\n"
    + _long("I")
    + b"\n"
    + _long("J")
    + b"\n"
    + _short("K")
    + _short("L")
    + b"Change three is old.\n"
)
_FOLDS_HEAD = _FOLDS.replace(b" is old.", b" is new.")

# The KPress asset manifest of a ready answer, from its key to its closing brace.
_ASSETS = re.compile(r'^  "assets": \{\n(?:    .*\n)*?  \}', re.MULTILINE)


def _head(origin: Origin, tmp_path: Path) -> tuple[str, str]:
    """Pull request 7's base, which gains the document, and its head, which edits it."""

    based = _commit(origin, tmp_path, origin["base"], {"docs/folds.md": _FOLDS}, origin["base"])
    topic = _commit(
        origin, tmp_path, origin["topic"], {"docs/folds.md": _FOLDS}, origin["topic"], based
    )
    head = _commit(
        origin,
        tmp_path,
        origin["fork_head"],
        {"docs/folds.md": _FOLDS_HEAD},
        origin["fork_head"],
        based,
    )
    _git(origin, tmp_path, "update-ref", f"refs/heads/{DEFAULT_BRANCH}", topic)
    _git(origin, tmp_path, "update-ref", "refs/pull/7/head", head)
    return topic, head


def _assets_once(text: str) -> str:
    """The transcript with every asset manifest after the first named, not printed."""

    seen: list[str] = []

    def once(found: re.Match[str]) -> str:
        if seen and found.group(0) == seen[0]:
            return '  "assets": "<ASSETS>"'
        seen.append(found.group(0))
        return found.group(0)

    return _ASSETS.sub(once, text)


def test_golden_rendered_markdown_views_fold_and_withhold_unchanged_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    selected = f"{PULL}/7"
    acquired = session.run(selected, "--no-serve")
    assert acquired.exit_code == 0, acquired.stderr
    base, head = _head(pull_origin, tmp_path)
    session.answer(_answering(pull_origin, base, head))
    refreshed = session.run(
        selected, "--api", f"{ROUTE}-refresh", "--data", _body(tmp_path, number=7, retry=True)
    )
    assert refreshed.exit_code == 0, refreshed.stderr
    envelope = run_metab((selected, "--api", f"{ROUTE}?number=7")).payload()
    manifest = run_metab((selected, "--api", envelope["comparison_route"])).payload()["manifest"]
    ids = {(change["new"] or change["old"])["path"]: change["id"] for change in manifest["files"]}
    route = f"{envelope['rendered_route']}&file={ids['docs/folds.md']}"

    def rendered(query: str, *, ok: bool = True, shown: bool = True) -> dict[str, Any]:
        result = (
            session.run(selected, "--api", f"{route}{query}")
            if shown
            else run_metab((selected, "--api", f"{route}{query}"))
        )
        assert (result.exit_code == 0) is ok, (query, result.stdout, result.stderr)
        return cast("dict[str, Any]", result.payload())

    concise = rendered("&view=concise")
    assert (concise["status"], concise["view"], concise["count"]) == ("ready", "concise", 20)
    short, long = concise["folds"]
    # The short run's two hidden paragraphs are three source lines, sent with the answer;
    # the long run's heading and two paragraphs are past the bound, and withheld.
    assert (short["count"], short["lines"], "withheld" in short) == (2, 3, False)
    assert (long["count"], long["withheld"]) == (3, True)
    assert long["lines"] == 2 + 2 * _LONG + 1 >= INLINE_FOLD_MAX_LINES
    assert len(long["ids"]) == 1 and long["ids"][0].endswith("deep-heading")
    assert len(concise["blocks"]) == concise["count"] - long["count"]
    withheld = rendered(f"&blocks={long['at']}-{long['at'] + long['count']}")
    assert withheld["at"] == long["at"]
    assert [block["kind"] for block in withheld["blocks"]] == ["context"] * 3
    assert 'id="' in withheld["blocks"][0]["html"]
    full = rendered("&view=prefer-full")
    assert (full["view"], len(full["blocks"]), full["folds"]) == (
        "full",
        20,
        [short, {key: value for key, value in long.items() if key not in ("withheld", "ids")}],
    )
    # Full is the default, and a projection the route keeps answers every view.
    assert rendered("", shown=False) == full
    assert rendered("&view=full", shown=False) == full
    # Past the Docs tab's bounds, `prefer-full` answers Concise.
    monkeypatch.setattr(markdown_views, "FULL_MAX_BLOCKS", 10)
    assert rendered("&view=prefer-full", shown=False) == concise
    for query in (
        "&view=whole",
        "&blocks=5-2",
        "&blocks=0-99",
        "&view=concise&blocks=0-1",
        "&blocks=a-b",
    ):
        assert rendered(query, ok=False)["code"] == "invalid_rendered_diff"

    labels = Labels()
    labels.origin(CANONICAL)
    text = normalize_pull_comparison_scopes(
        label_home(labels.apply("".join(session.blocks)), session.home)
    )
    text = _assets_once(_ANCHOR.sub("user-content-<ANCHORS>-", text))
    assert str(tmp_path) not in text
    check_golden("cli-github-pull-rendered-views.txt", operational_once(text))
