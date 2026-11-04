"""Actual CLI stack acquisition, cache-only reads, conditional refresh and optional refusal."""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    Origin,
    install_fake_gh,
    logged_gh_calls,
    next_link,
    ok,
    scenario,
)
from tests.golden_harness import Labels, check_golden, isolate_cli, label_home, quoted, run_metab
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]


def _stack(number: int, pulls: list[int]) -> dict[str, Any]:
    return {
        "number": number,
        "url": f"https://api.github.com/repos/octo/demo/stacks/{number}",
        "base": {"ref": "main"},
        "open": True,
        "pull_requests": [{"number": n} for n in pulls],
    }


def test_golden_optional_stacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    local = pull_origin.url

    def remote(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote)
    now = FETCHED_AT
    monkeypatch.setattr(pull_list, "utc_now", lambda: now)
    answers = scenario(pull_origin)
    first = "repos/octo/demo/stacks?per_page=100&page=1"
    second = "repos/octo/demo/stacks?per_page=100&page=2"
    answers["stack_version"] = "0.1.0"
    answers["api"].update(
        {
            first: ok(first, [_stack(70, [7, 8])], next_link(first, 1)),
            second: ok(second, [_stack(90, [9])]),
        }
    )

    def answer() -> None:
        for key, value in install_fake_gh(tmp_path, answers).items():
            monkeypatch.setenv(key, value)

    answer()
    blocks: list[str] = []
    opened = False

    def run(*, body: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal opened
        route = "/api/plugin/github/stacks" if body is None else "/api/plugin/github/stacks-refresh"
        args = [CANONICAL, "--api", route]
        sections: dict[str, list[str]] = {}
        if body is not None:
            request = tmp_path / "request.json"
            request.write_text(json.dumps(body) + "\n")
            args += ["--data", str(request)]
            sections["body"] = [json.dumps(body)]
        result = run_metab(args)
        shown = [arg.removeprefix(f"{tmp_path}/") for arg in args]
        calls = logged_gh_calls(tmp_path)
        blocks.append(result.block(" ".join(quoted(arg) for arg in shown), **sections, gh=calls))
        if body is None:
            assert calls == ([] if opened else ["gh api repos/octo/demo --jq .size"])
        opened = True
        if "status: 200\n{" in result.stdout:
            return json.loads(
                result.stdout[result.stdout.rindex("status: 200\n{") + len("status: 200\n") :]
            )
        return result.payload()

    blocks.append(
        "## A cache-only read; explicit optional acquisition fetches two repository pages.\n"
    )
    assert run()["reason"] == "not_cached"
    fetched = run(body={})
    assert fetched["complete"] and [s["number"] for s in fetched["stacks"]] == [70, 90]
    assert run()["stacks"] == fetched["stacks"]
    assert run(body={})["refresh"] == "not_due"
    blocks.append("## A due refresh asks conditionally; a 304 without Link retains page two.\n")
    now += timedelta(seconds=301)
    answers["api"] = {first: {"status": 304}, second: {"status": 304}}
    answer()
    assert run(body={})["stacks"] == fetched["stacks"]
    blocks.append("## Removing optional tooling retains known membership and backs off.\n")
    answers.pop("stack_version")
    answer()
    failed = run(body={"retry": True})
    assert failed["state"] == "stale" and failed["last_refresh"]["outcome"] == "gh_stack_missing"
    assert failed["stacks"] == fetched["stacks"]
    assert run(body={})["refresh"] == "not_due"
    assert run()["stacks"] == fetched["stacks"]
    rendered = label_home(Labels().apply("".join(blocks)), home)
    assert str(tmp_path) not in rendered and "file://" not in rendered
    check_golden("cli-github-stacks.txt", rendered)
