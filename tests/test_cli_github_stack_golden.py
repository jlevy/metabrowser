"""A native stack's page through the CLI: its members, its comparison, and admission.

``GET /api/plugin/github/stack`` answers the stack page at ``/stack/<n>``, and
``GET /api/plugin/github/stack-comparison`` the comparison it names (mb-vad1). This drives
both the way a reader's server is driven, through ``metab --api`` and ``--show``, on the
stand-in's pull requests (``tests/github_pull_fixture.py``):

| Stack | Members, bottom first | What it shows |
| --- | --- | --- |
| 70 | 8 (merged), 10 (draft) | The whole stack. 10's base is ``topic`` after 8 merged, and ``topic`` had moved ``README.md`` before: the plain diff from 8's merge base to 10's head holds it, and the stack's comparison leaves it out, since no layer changes it |
| 71 | 8, 7, 10 | 7 is a fork whose head the top lacks, so it contributes no files and is named in ``lacking`` |
| 72 | 10, 8 | Not linear: 10's merge base is not in 8's history |
| 73 | 8, 9 | Pending while 9 has no record, until the page asks for 9 as the reader's own open of it |

The stand-in's merge of 8 keeps ``topic``'s tree, as ``git fast-import`` writes a merge
with no file of its own, so 8's edit of ``docs/guide.md`` is not in 10's head: the
comparison of 70 is ``docs/draft.md`` alone, attributed to 10, and 8 adds no file though
the top contains it. A file two layers change, and one a layer renames, are
``tests/test_github_pull_stack.py``'s, on manifests of their own.

The rendered-diff and image routes take ``stack=`` in place of ``number`` and admit the
stack's current pair alone. Nothing here asks GitHub but the record fetches.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from metabrowser.builtin_plugins.github import pull_list
from metabrowser.cache.urls import GitSource
from metabrowser.git.tree_source import GitPath
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    FIRST_CLONE_GH_CALLS,
    Origin,
    in_a_stable_order,
    install_fake_gh,
    logged_gh_calls,
    ok,
    scenario,
)
from tests.golden_harness import (
    Labels,
    check_golden,
    check_recording,
    isolate_cli,
    label_home,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

ROUTE = "/api/plugin/github/stack"
REFRESH = "/api/plugin/github/pull-refresh"
STACKS = "repos/octo/demo/stacks?per_page=100&page=1"
# An image the stack's head does not have, as the image route spells a path.
SHOT = GitPath.from_display("docs/shot.png").to_wire()


def _stack(number: int, pulls: list[int]) -> dict[str, Any]:
    return {
        "number": number,
        "url": f"https://api.github.com/repos/octo/demo/stacks/{number}",
        "base": {"ref": DEFAULT_BRANCH},
        "open": True,
        "pull_requests": [{"number": n} for n in pulls],
    }


def _scoped(text: str) -> str:
    """*text* with the sandbox store's tag and the checkout's build labeled, as
    `normalize_pull_comparison_scopes` labels a pull request's routes."""

    return re.sub(
        r"([?&]store=)[0-9a-f]{16}",
        r"\1<STORE>",
        re.sub(r"(&build=)[0-9a-f]{12}", r"\1<BUILD>", text),
    )


def _paths(document: dict[str, Any]) -> list[str]:
    return [
        (change.get("new") or change.get("old"))["path"] for change in document["manifest"]["files"]
    ]


def test_golden_stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    local = pull_origin.url

    def remote(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote)
    monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
    monkeypatch.setattr("metabrowser.builtin_plugins.github.pulls.utc_now", lambda: FETCHED_AT)
    answers = scenario(pull_origin)
    answers["stack_version"] = "0.1.0"
    answers["api"][STACKS] = ok(
        STACKS,
        [_stack(70, [8, 10]), _stack(71, [8, 7, 10]), _stack(72, [10, 8]), _stack(73, [8, 9])],
    )
    for key, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(key, value)
    labels = Labels()
    for name in ("base", "topic", "merged_head", "draft_head", "fork_head"):
        labels.add(pull_origin[name], f"<{name}>")
    blocks: list[str] = []

    def run(*args: str, gh_free: bool = True) -> Any:
        result = run_metab(args)
        shown = [arg.removeprefix(f"{tmp_path}/") for arg in args]
        calls = in_a_stable_order(logged_gh_calls(tmp_path))
        if gh_free:
            assert calls in ([], FIRST_CLONE_GH_CALLS), "a stack read asked GitHub"
        blocks.append(result.block(" ".join(quoted(arg) for arg in shown), gh=calls))
        return result

    def api(route: str) -> Any:
        return run(CANONICAL, "--api", route)

    def stack(number: int) -> dict[str, Any]:
        return api(f"{ROUTE}?number={number}").payload()

    def fetch(number: int) -> None:
        assert run(f"{CANONICAL}/pull/{number}", "--no-serve", gh_free=False).exit_code == 0

    blocks.append("## No snapshot yet: no stack is known, and nothing asks GitHub.\n")
    assert stack(70)["reason"] == "not_stacked"
    request = tmp_path / "request.json"
    request.write_text("{}\n")
    run(
        CANONICAL,
        "--api",
        "/api/plugin/github/stacks-refresh",
        "--data",
        str(request),
        gh_free=False,
    )

    blocks.append("## With the snapshot and no member's record, the stack is pending.\n")
    pending = stack(70)
    assert pending["state"] == "pending"
    assert pending["pending"] == [8, 10]
    assert pending["comparison"] is None

    blocks.append(
        "## Both records fetched: the comparison from 8's merge base to 10's head, keeping"
        " only the files a layer changes.\n"
    )
    fetch(8)
    fetch(10)
    current = stack(70)
    assert current["state"] == "current"
    assert [member["in_top"] for member in current["members"]] == [True, True]
    assert current["lacking"] == []
    assert [entry["path"] for entry in current["files"]] == ["docs/draft.md"]
    assert [[layer["number"] for layer in entry["layers"]] for entry in current["files"]] == [[10]]
    assert current["totals"]["files"] == 1
    assert current["github_url"] == f"{CANONICAL}/pull/10"
    assert current["probe"]["number"] == 10
    comparison = current["comparison"]
    assert (comparison["left"], comparison["right"]) == (
        pull_origin["base"],
        pull_origin["draft_head"],
    )
    whole = api(comparison["route"]).payload()
    assert _paths(whole) == ["docs/draft.md"]
    assert whole["manifest"]["totals"]["files"] == 1
    blocks.append(
        "## The plain diff of the same two commits holds README.md too, which topic moved"
        " before 10 began and no layer changes.\n"
    )
    plain = api(
        f"/api/plugin/diff/comparison?left={comparison['left']}&right={comparison['right']}"
        "&base_policy=direct"
    ).payload()
    assert _paths(plain) == ["README.md", "docs/draft.md"]

    blocks.append("## Its documents alone, its File type counts, and one of its files.\n")
    docs = api(f"{comparison['route']}&group=type:docs").payload()
    assert _paths(docs) == ["docs/draft.md"]
    types = api(f"{comparison['route']}&view=types").payload()
    assert types["truncated"] is False
    guide = whole["manifest"]["files"][0]
    one = api(f"{comparison['route']}&file=docs/draft.md").payload()
    assert _paths(one) == ["docs/draft.md"]

    blocks.append(
        "## An address the stack has moved from is refused, as is one that names no key.\n"
    )
    moved = api(comparison["route"].replace(comparison["key"], "0" * 32))
    assert "status: 410" in moved.stdout
    assert '"stack_moved"' in moved.stdout
    unkeyed = api(f"/api/plugin/github/stack-comparison?number=70&left={comparison['left']}")
    assert "status: 400" in unkeyed.stdout

    blocks.append(
        "## The rendered-diff route admits the stack's current pair by `stack=`, and refuses"
        " another.\n"
    )
    rendered = api(f"{comparison['rendered_route']}&file={guide['id']}")
    assert rendered.exit_code == 0
    query = parse_qs(urlsplit(comparison["rendered_route"]).query)
    assert query["stack"] == ["70"] and "number" not in query
    stale = api(
        comparison["rendered_route"].replace(comparison["right"], pull_origin["merged_head"])
        + f"&file={guide['id']}"
    )
    assert "status: 410" in stale.stdout
    both = api(f"{comparison['rendered_route']}&number=70&file={guide['id']}")
    assert "status: 400" in both.stdout

    blocks.append(
        "## The image route admits it too: an image the head lacks is not found after"
        " admission, and a pair that is not the stack's is refused before it.\n"
    )
    image = api(f"{comparison['image_route']}&path={SHOT}")
    assert "snapshot_expired" not in image.stdout
    image_stale = api(
        comparison["image_route"].replace(comparison["right"], pull_origin["merged_head"])
        + f"&path={SHOT}"
    )
    assert "snapshot_expired" in image_stale.stdout

    blocks.append(
        "## A member the top's head lacks: 7's fork head is in no history of 10's, so it adds"
        " no file and is named in `lacking`.\n"
    )
    fetch(7)
    lacking = stack(71)
    assert lacking["state"] == "current"
    assert lacking["lacking"] == [7]
    assert [member["in_top"] for member in lacking["members"]] == [True, False, True]
    assert [entry["path"] for entry in lacking["files"]] == ["docs/draft.md"]
    assert lacking["comparison"]["key"] != comparison["key"]

    blocks.append("## Not linear: 10's merge base is not in 8's history.\n")
    linear = stack(72)
    assert linear["reason"] == "not_linear"

    blocks.append("## A member with no record leaves its stack pending.\n")
    waiting = stack(73)
    assert waiting["state"] == "pending"
    assert waiting["pending"] == [9]

    blocks.append(
        "## The page's ask for that member. An automatic ask refreshes only a record the"
        " server holds, so the page asks as the reader's own open of it, which fetches 9,"
        " and the stack is current.\n"
    )
    ask = tmp_path / "ask.json"
    ask.write_text('{"number": 9}\n')
    automatic = run(CANONICAL, "--api", REFRESH, "--data", str(ask))
    assert automatic.payload()["refresh"] == "not_cached"
    ask.write_text('{"number": 9, "retry": true}\n')
    opened = run(CANONICAL, "--api", REFRESH, "--data", str(ask), gh_free=False)
    assert opened.exit_code == 0, opened.stderr
    assert '"refresh": "started"' in opened.stdout
    fetched = stack(73)
    assert fetched["state"] == "current"
    assert fetched["pending"] == []

    blocks.append("## A number no stack has, and a request that names more than it.\n")
    assert stack(99)["reason"] == "not_stacked"
    refused = api(f"{ROUTE}?number=70&left=main")
    assert "status: 400" in refused.stdout

    blocks.append("## The stack's page, as `--show` reports it: its kind, and a file's layers.\n")
    shown = run(CANONICAL, "--show", "/stack/70")
    assert "kind: pull-stack" in shown.stdout
    file_shown = run(CANONICAL, "--show", "/stack/70/changes/docs/draft.md")
    assert "layers=2/2:#10" in file_shown.stdout

    rendered_text = _scoped("".join(blocks))
    # A rendered document's anchors are named by its sandbox-derived namespace.
    rendered_text = re.sub(r"user-content-[0-9a-f]{24}-", "user-content-<ANCHORS>-", rendered_text)
    rendered_text = label_home(labels.apply(rendered_text), home)
    assert str(tmp_path) not in rendered_text and "file://" not in rendered_text
    check_golden("cli-github-stack.txt", rendered_text)
    # The answers tests/dom/github-stack-page-session.js replays, as the route gave them.
    answers = {"pending": pending, "current": current, "lacking": lacking, "not_linear": linear}
    check_recording(
        "github-stack-responses.json",
        json.loads(labels.apply(_scoped(json.dumps(answers)))),
        transcript="cli-ui-github-stack-page.tryscript.md",
    )
    assert json.loads(json.dumps(current)) == current
