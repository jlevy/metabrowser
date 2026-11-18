"""Which changed file GitHub's ``#diff-<hash>`` anchor names: the sources, in order.

The two sources are replaced by their readers, so no Git or cache runs here: the cached
list ``GET /api/plugin/github/pull-files`` answers from, then the record's comparison.
The whole path, from a URL to the address served, runs against the pull-request stand-in
in ``tests/test_github_pulls.py`` and ``tests/golden/cli-github-pull-file-anchor.txt``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_file_anchor
from metabrowser.builtin_plugins.github.pull_file_anchor import path_digest, pull_file_for_anchor
from metabrowser.builtin_plugins.github.pull_list import (
    PULL_FILES_SCHEMA,
    PullFileList,
    PullFileRow,
)
from metabrowser.builtin_plugins.github.pull_record import Comparison, PullRecord
from metabrowser.cache.providers import PullRequestFile
from metabrowser.cache.urls import FileAnchor
from metabrowser.git.process import GitError

CANONICAL = "https://github.com/octo/demo"
_PUBLISHED: Any = SimpleNamespace(home=Path("/nonexistent"), slug="github-com--octo--demo")


def _listed(*paths: str) -> PullFileList:
    return PullFileList(
        schema_version=PULL_FILES_SCHEMA,
        generation="1" * 32,
        source=CANONICAL,
        number=7,
        listed_from="comparison",
        fetched_at="2026-09-17T12:00:00Z",
        reader=None,
        head="c" * 40,
        base="b" * 40,
        pages=0,
        last_page=None,
        complete=True,
        capped=False,
        truncated=False,
        marks=(),
        rows=tuple(
            PullFileRow(path=path, previous_path=None, status="modified", additions=1, deletions=0)
            for path in paths
        ),
    )


def _record(*, comparison: bool = True) -> PullRecord:
    endpoints = Comparison(base="b" * 40, head="c" * 40, base_commit="b" * 40, base_from="base_sha")
    return PullRecord.model_construct(comparison=endpoints if comparison else None)


def _side(path: str, *, lossy: bool = False) -> SimpleNamespace:
    return SimpleNamespace(path=path, path_b64="AA==" if lossy else None)


def _change(new: str | None, old: str | None = None, *, lossy: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        new=None if new is None else _side(new, lossy=lossy),
        old=None if old is None else _side(old),
    )


class _Sources:
    """The two readers, answering what a test gives them and counting the comparison's."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        listed: PullFileList | str = "not_cached",
        record: PullRecord | str = "not_cached",
        changes: list[SimpleNamespace] | None = None,
        truncated: bool = False,
        fails: bool = False,
    ) -> None:
        self.compared = 0

        async def manifest(*_args: object, **_kwargs: object) -> SimpleNamespace:
            self.compared += 1
            if fails:
                raise GitError("the store cannot list it")
            return SimpleNamespace(
                manifest=SimpleNamespace(files=tuple(changes or ()), truncated=truncated)
            )

        monkeypatch.setattr(pull_file_anchor, "read_pull_files", lambda *_args: listed)
        monkeypatch.setattr(pull_file_anchor, "read_pull_record", lambda *_args: record)
        monkeypatch.setattr(pull_file_anchor, "shared_pull_manifest", manifest)


def _resolve(path: str, line: str = "") -> PullRequestFile:
    anchor = FileAnchor(path_digest(path) or "", line)
    return asyncio.run(pull_file_for_anchor(_PUBLISHED, 7, anchor))


def test_the_cached_list_answers_first_without_listing_the_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _Sources(monkeypatch, listed=_listed("docs/new.md", "src/app.txt"), record=_record())

    assert _resolve("src/app.txt", "R2") == PullRequestFile("src/app.txt")
    assert sources.compared == 0


def test_the_comparison_answers_when_the_list_is_not_cached_or_lacks_the_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A list read for an older head may lack a file a newer push changed.
    changes = [_change("src/app.txt"), _change(None, old="gone.md"), _change("b.md", old="a.md")]
    for listed in ("not_cached", _listed("docs/new.md")):
        _Sources(monkeypatch, listed=listed, record=_record(), changes=changes)
        assert _resolve("src/app.txt") == PullRequestFile("src/app.txt")
        # A removed file is anchored by its old path, and a renamed one by its new path.
        assert _resolve("gone.md") == PullRequestFile("gone.md")
        assert _resolve("b.md") == PullRequestFile("b.md")
        assert _resolve("a.md").path is None


def test_an_anchor_no_list_names_says_why_and_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Sources(monkeypatch, record=_record(), changes=[_change("src/app.txt")])
    unchanged = _resolve("README.md")
    assert unchanged.path is None
    assert unchanged.unresolved is not None
    assert unchanged.unresolved.endswith("(file_not_changed)")

    # A comparison cut short may hold the file past where it stops.
    _Sources(monkeypatch, listed=_listed("src/app.txt"), record=_record(), truncated=True)
    not_listed = _resolve("README.md")
    assert not_listed.unresolved is not None
    assert not_listed.unresolved.endswith("(file_not_listed)")

    for record, fails in (
        (_record(comparison=False), False),
        ("not_cached", False),
        (_record(), True),
    ):
        _Sources(monkeypatch, record=record, fails=fails)
        unknown = _resolve("src/app.txt")
        assert unknown.path is None
        assert unknown.unresolved is not None
        assert unknown.unresolved.endswith("(files_unknown)")


def test_a_path_the_changes_tab_cannot_address_or_git_could_not_spell_is_not_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A backslash is a valid Git path byte that the Changes tab's address refuses, and a
    # path Git could not spell in UTF-8 has a lossy `path` that GitHub did not hash.
    _Sources(
        monkeypatch,
        listed=_listed("a\\b.md"),
        record=_record(),
        changes=[_change("a\\b.md"), _change("lossy.md", lossy=True)],
    )
    assert _resolve("a\\b.md").path is None
    assert _resolve("lossy.md").path is None
