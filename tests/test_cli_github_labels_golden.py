"""The repository's label set through the CLI: cache-only reads, refreshes, and its use.

A record cached before label colors names its labels alone; the pull envelope then carries
the set's entries for them, ``repository_labels``, which color its chips (``mb-varu``).
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_list, pulls
from metabrowser.cache.paths import source_pull_record
from metabrowser.cache.urls import GitSource
from tests.cache_home_fixture import FixtureSource
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    Origin,
    in_a_stable_order,
    install_fake_gh,
    logged_gh_calls,
    scenario,
)
from tests.golden_harness import (
    Labels,
    check_golden,
    isolate_cli,
    label_home,
    normalize_pull_comparison_scopes,
    operational_once,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

LABELS = "/api/plugin/github/labels"
REFRESH = "/api/plugin/github/labels-refresh"
PAGE = "repos/octo/demo/labels?per_page=100&page=1"


def test_golden_repository_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    local = pull_origin.url

    def remote(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote)
    now = FETCHED_AT
    monkeypatch.setattr(pull_list, "utc_now", lambda: now)
    monkeypatch.setattr(pulls, "utc_now", lambda: now)
    answers = scenario(pull_origin)

    def answer() -> None:
        for key, value in install_fake_gh(tmp_path, answers).items():
            monkeypatch.setenv(key, value)

    answer()
    blocks: list[str] = []

    def run(route: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        args = [CANONICAL, "--api", route]
        sections: dict[str, list[str]] = {}
        if body is not None:
            request = tmp_path / "request.json"
            request.write_text(json.dumps(body) + "\n")
            args += ["--data", str(request)]
            sections["body"] = [json.dumps(body)]
        result = run_metab(args)
        shown = [arg.removeprefix(f"{tmp_path}/") for arg in args]
        # A record's parts are read together, in whatever order the processes ran.
        calls = in_a_stable_order(logged_gh_calls(tmp_path))
        blocks.append(result.block(" ".join(quoted(arg) for arg in shown), **sections, gh=calls))
        if "status: 200\n{" in result.stdout:
            return json.loads(
                result.stdout[result.stdout.rindex("status: 200\n{") + len("status: 200\n") :]
            )
        return result.payload()

    blocks.append("## A cache-only read; a refresh asks GitHub for the set, one page.\n")
    assert run(LABELS)["reason"] == "not_cached"
    # A one-shot command follows the refresh to its status route, the read, once it ends.
    fetched = run(REFRESH, {})
    assert fetched["count"] == 3
    read = run(LABELS)
    assert read == fetched
    assert read["state"] == "current" and read["complete"] and read["count"] == 3
    assert [label["name"] for label in read["labels"]] == ["enhancement", "invalid", "bug"]
    assert read["labels"][0]["color"] == "2700af"
    assert run(REFRESH, {})["refresh"] == "not_due"

    blocks.append(
        "## A record cached before label colors names its labels alone; the pull envelope\n"
        "## carries the set's entry for each, and a colored record needs none.\n"
    )
    refreshed = run("/api/plugin/github/pull-refresh", {"number": 7, "retry": True})
    assert refreshed["state"] == "current"
    colored = run("/api/plugin/github/pull?number=7")
    assert colored["repository_labels"] == [] and colored["labels_pending"] is False
    slug = FixtureSource("https", CANONICAL).slug
    path = home / source_pull_record(slug, 7)
    old = json.loads(path.read_bytes())
    old["projection_version"] = 1
    old["pull"]["labels"] = ["enhancement", "deleted-on-github"]
    path.write_text(json.dumps(old))
    bare = run("/api/plugin/github/pull?number=7")
    assert [label["color"] for label in bare["record"]["pull"]["labels"]] == [None, None]
    assert bare["repository_labels"] == [
        {
            "name": "enhancement",
            "color": "2700af",
            "description": "A label's description is its chip's tooltip",
        }
    ]

    blocks.append("## A due refresh asks again with the page's ETag; a 304 keeps the set.\n")
    now += timedelta(seconds=301)
    answers["api"][PAGE] = {"status": 304}
    answer()
    run(REFRESH, {})
    kept = run(LABELS)
    assert kept["labels"] == read["labels"] and kept["fetched_at"] != read["fetched_at"]
    rendered = normalize_pull_comparison_scopes(label_home(Labels().apply("".join(blocks)), home))
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-labels.txt", operational_once(rendered))
