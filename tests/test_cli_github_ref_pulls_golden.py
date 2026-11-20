"""The ref chooser's pull requests through the CLI: a branch lists the pull requests it heads.

``GET /api/source/refs`` lists a mirror's branches, and a branch that is the head of a
pull request in the repository's cached catalog lists it (``mb-tjbm``). Each command runs
the production CLI in process, as ``tests/test_cli_github_labels_golden.py`` does, with
the stand-in origin of ``tests/github_pull_fixture.py`` fetched for
``https://github.com/octo/demo`` and a fake ``gh`` that fails every call, so a read that
asked GitHub would show. The catalog is written by the production publisher
(``seed_catalog``) after the first command has cached the mirror:

- nothing is cached, and the listing says so;
- a catalog whose pull requests head ``topic`` and ``wip``: ``wip`` of three, an open
  one, an earlier closed one, and one from a fork, which is another branch of the same
  name and is not listed, and ``topic`` of a merged one;
- the filter finds a branch by its pull request's number or title, and lists the
  pull request that matched first.

``tests/golden/cli-github-pulls.tryscript.md`` shows the same route over the shared
catalog the Pulls tab's transcripts read.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_list, pulls
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.cache.urls import GitSource
from tests.cache_home_fixture import FixtureSource
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    Origin,
    head_item,
    install_fake_gh,
    scenario,
    seed_catalog,
)
from tests.golden_harness import (
    Labels,
    check_golden,
    isolate_cli,
    label_home,
    normalize_pull_comparison_scopes,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

REFS = "/api/source/refs"


def test_golden_a_branch_lists_the_pull_requests_it_heads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    local = pull_origin.url

    def remote(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    # `gh` fails every call: nothing here may ask GitHub.
    for key, value in install_fake_gh(
        tmp_path, {**scenario(pull_origin), "api_failure": {"stderr": "no gh\n"}}
    ).items():
        monkeypatch.setenv(key, value)
    blocks: list[str] = []

    def run(query: str) -> dict[str, Any]:
        args = [CANONICAL, "--api", f"{REFS}?{query}"]
        result = run_metab(args)
        blocks.append(result.block(" ".join(quoted(arg) for arg in args)))
        return result.payload()

    blocks.append(
        "## The mirror is cached by this first command, and no pull request is: the listing\n"
        "## says the catalog is absent, and no row has a pull request.\n"
    )
    nothing = run("kind=branch")
    assert nothing["pull_requests"] == {"state": "absent", "complete": False, "refreshing": False}
    assert [row["name"] for row in nothing["refs"]] == ["topic", "wip"]
    assert not any("pulls" in row for row in nothing["refs"])

    slug = FixtureSource("https", CANONICAL).slug
    seed_catalog(
        ListedRepository(home, slug, "octo", "demo"),
        [
            head_item(12, "topic", "Start the topic", state="closed", merged=True),
            head_item(28, "wip", "An earlier try at the page", state="closed"),
            head_item(31, "wip", "WIP: draft the next page", draft=True),
            head_item(40, "wip", "From a fork's own wip", head_repository="forker/demo"),
            head_item(41, "elsewhere", "Its branch is not in the mirror"),
        ],
        fetched_at="2026-10-01T12:00:00Z",
    )
    blocks.append(
        "## With the catalog cached, a branch lists the pull requests it heads: `wip`'s open\n"
        "## draft first and then its earlier closed one, `topic`'s merged one. The fork's\n"
        "## `wip` is another branch, and `elsewhere` is no branch of the mirror.\n"
    )
    listed = run("kind=branch")
    assert listed["pull_requests"] == {"state": "ready", "complete": True, "refreshing": False}
    by_name = {row["name"]: row for row in listed["refs"]}
    assert [pull["number"] for pull in by_name["wip"]["pulls"]] == [31, 28]
    assert [pull["state"] for pull in by_name["wip"]["pulls"]] == ["draft", "closed"]
    assert [pull["number"] for pull in by_name["topic"]["pulls"]] == [12]

    blocks.append(
        "## The filter finds a branch by a pull request's number, the start of it after `#`,\n"
        "## and lists the pull request that matched first.\n"
    )
    by_number = run("kind=branch&q=%2328")
    assert [row["name"] for row in by_number["refs"]] == ["wip"]
    assert [pull["number"] for pull in by_number["refs"][0]["pulls"]] == [28, 31]

    blocks.append("## Or by every word of a title, in any case, whatever the branch is named.\n")
    by_title = run("kind=branch&q=START+topic")
    assert [row["name"] for row in by_title["refs"]] == ["topic"]

    blocks.append(
        "## A fork's pull request, and one whose branch the mirror lacks, find nothing.\n"
    )
    assert run("kind=branch&q=fork")["refs"] == []

    blocks.append("## A list of tags has no pull requests.\n")
    tags = run("kind=tag")
    assert tags["pull_requests"] is None

    rendered = normalize_pull_comparison_scopes(label_home(Labels().apply("".join(blocks)), home))
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-ref-pulls.txt", rendered)
