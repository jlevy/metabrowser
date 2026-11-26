"""A native stack's page through the CLI: its members, its comparison, and admission.

``GET /api/plugin/github/stack`` answers the stack page at ``/stack/<n>``, and
``GET /api/plugin/github/stack-comparison`` the comparison it names (mb-vad1). This drives
both the way a reader's server is driven, through ``metab --api`` and ``--show``, on the
stand-in's pull requests (``tests/github_pull_fixture.py``):

| Stack | Members, bottom first | What it shows |
| --- | --- | --- |
| 70 | 8 (merged), 10 (draft), then 10 alone | The whole stack. 10's base is ``topic`` after 8 merged, and ``topic`` had moved ``README.md`` before: the plain diff from 8's merge base to 10's head holds it, and the stack's comparison leaves it out, since no layer changes it. Last, the stack moves to 10 alone, and its earlier comparison keeps answering |
| 71 | 8, 7, 10 | 7 is a fork whose head the top lacks, so it contributes no files and is named in ``lacking`` |
| 72 | 10, 8 | Not linear: 10's merge base is not in 8's history |
| 73 | 8, 9 | Pending while 9 has no record, until the page asks for 9 as the reader's own open of it |
| 74 | 7, from the last snapshot | 7's description has two ``stack-review`` blocks |

The stand-in's merge of 8 keeps ``topic``'s tree, as ``git fast-import`` writes a merge
with no file of its own, so 8's edit of ``docs/guide.md`` is not in 10's head: the
comparison of 70 is ``docs/draft.md`` alone, attributed to 10, and 8 adds no file though
the top contains it. A file two layers change, and one a layer renames, are
``tests/test_github_pull_stack.py``'s, on manifests of their own.

The rendered-diff and image routes take ``stack=`` in place of ``number`` and admit the
stack's current pair, and a pair the stack route gave before and keeps
(``pull_stack_retained.py``). Nothing here asks GitHub but the record and stack fetches.

A stack's guide is a ``stack-review`` block in a member's description, the top-most
member's that has one (mb-ri96). 10's block is pinned to stack 70's pair, so 70's
guide reads ready, and it is left out of 10's rendered description; 8's, pinned to 8's own
head, is below 10 there and is 73's guide, out of date, since 73's top is 9. The guide's
answers, each under the step of the stack's story it is read at, are
``cli-github-stack-guide.txt``. Stack 70's comparison and the routes that admit it, and
71, are ``cli-github-stack.txt``; 72, 73, a number no stack has, and 70's move are
``cli-github-stack-states.txt``. So each transcript stays inside the review budget.

A stack's size is its comparison's, measured where the comparison is built, and only where
it is the plain diff of its two commits, so the size and the file count describe one diff:
70's and 71's comparisons leave ``README.md`` out, so they have none, and 74's, 7's own diff,
has one. A pushed size is zlib's output, masked in the transcripts and a stand-in in the
recording (``mask_pushed_bytes``).

A page that drew a comparison asks with ``since``, its key, and the stack route says how
each member's head moved from it (``moved``), which the page's notice of a new comparison
says (docs/reviewing-pull-requests.md, "A Stack's Guide"). The states transcript holds it
after 70 loses 8, and as 74's one member, 7, is rewritten to its earlier commit and then
gains a commit again.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
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
    git_env,
    graph_core_entry,
    in_a_stable_order,
    install_fake_gh,
    logged_gh_calls,
    ok,
    page,
    scenario,
)
from tests.golden_harness import (
    Labels,
    check_golden,
    check_recording,
    isolate_cli,
    label_home,
    mask_pushed_bytes,
    operational_once,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

ROUTE = "/api/plugin/github/stack"
GUIDE = "/api/plugin/github/guided-review"
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


def _label(name: str, color: str) -> dict[str, Any]:
    """A label as GitHub's pull request answer gives it."""
    return {"name": name, "color": color, "description": None}


def _stack_guide(merge_base: str, head: str, items: str) -> str:
    """A `stack-review` block pinned to *merge_base* and *head*, whose `items` are the YAML
    lines *items*."""
    return f"""```stack-review
softschema:
  contract: metabrowser.collection:Collection/v1
  envelope: collection
  status: enforced
collection:
  comparison:
    merge_base: "{merge_base}"
    head: "{head}"
  items:
{items}```
"""


# 10's: the stack's layers, then its one file, as a stack guide orients and then reads.
_TOP_GUIDE = """    - title: The layers
      note: 8 extends the guide; 10 starts a draft on top of it.
      references:
        - {pull: 8}
        - {pull: 10}
    - title: The draft
      note: Read the draft whole.
      references:
        - {path: docs/draft.md}
"""
# 8's, which no stack's top carries.
_LOWER_GUIDE = """    - title: The guide
      note: Check the guide's new line.
      references:
        - {path: docs/guide.md}
"""


def _paths(document: dict[str, Any]) -> list[str]:
    return [
        (change.get("new") or change.get("old"))["path"] for change in document["manifest"]["files"]
    ]


# The story is 63 `metab` runs, each a process of its own: measured 2026-11-25, the test took
# 64.8 s at a load average near 240, past the suite's 60 s default.
@pytest.mark.timeout(150)
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
        [
            _stack(70, [8, 10]),
            _stack(71, [8, 7, 10]),
            _stack(72, [10, 8]),
            _stack(73, [8, 9]),
        ],
    )
    pulls = answers["api"]
    top = pulls["repos/octo/demo/pulls/10"]["body"]
    top["body"] = (
        f"{top['body']}\n\n"
        f"{_stack_guide(pull_origin['base'], pull_origin['draft_head'], _TOP_GUIDE)}"
    )
    lower = pulls["repos/octo/demo/pulls/8"]["body"]
    lower["body"] = _stack_guide(pull_origin["base"], pull_origin["merged_head"], _LOWER_GUIDE)
    # Labels on both members of 70, one of them shared, so its answer gathers them top first,
    # each once (mb-68uk): bugfix, shared design, then earnings analysis.
    top["labels"] = [_label("bugfix", "d73a4a"), _label("shared design", "0e8a16")]
    lower["labels"] = [_label("shared design", "0e8a16"), _label("earnings analysis", "5319e7")]
    twice = _stack_guide(pull_origin["base"], pull_origin["fork_head"], _LOWER_GUIDE)
    pulls["repos/octo/demo/pulls/7"]["body"]["body"] = f"{twice}\n{twice}"
    for key, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(key, value)
    labels = Labels()
    for name in (
        "base",
        "topic",
        "merged_head",
        "draft_head",
        "fork_earlier",
        "fork_head",
        "closed_head",
    ):
        labels.add(pull_origin[name], f"<{name}>")
    blocks: list[str] = []
    # The stack's guide (mb-ri96) has a transcript of its own, cli-github-stack-guide.txt,
    # which these collect, so each stays inside the review budget (devtools/check_goldens.py).
    guide_blocks: list[str] = []
    # The stacks other than 70 and 71, and 70's move, have one of their own too,
    # cli-github-stack-states.txt, which these collect.
    states: list[str] = []
    into = [blocks]

    def run(*args: str, gh_free: bool = True) -> Any:
        result = run_metab(args)
        shown = [arg.removeprefix(f"{tmp_path}/") for arg in args]
        calls = in_a_stable_order(logged_gh_calls(tmp_path))
        if gh_free:
            assert calls in ([], FIRST_CLONE_GH_CALLS), "a stack read asked GitHub"
        into[0].append(result.block(" ".join(quoted(arg) for arg in shown), gh=calls))
        return result

    def api(route: str) -> Any:
        return run(CANONICAL, "--api", route)

    def in_guide(heading: str, *args: str, gh_free: bool = True) -> Any:
        """Run `metab` on *args* into the guide's transcript under *heading*."""
        guide_blocks.append(heading)
        main = into[0]
        into[0] = guide_blocks
        try:
            return run(CANONICAL, *args, gh_free=gh_free)
        finally:
            into[0] = main

    def read_guide(heading: str, route: str) -> Any:
        """Read *route*, a guide's, into the guide's transcript under *heading*."""
        return in_guide(heading, "--api", route)

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
    assert pending["guide"] is None
    waits = read_guide(
        "## Stack 70 is pending: its guide waits for the members too, since a member not read"
        " yet may carry it.\n",
        f"{GUIDE}?stack=70",
    )
    assert waits.payload()["state"] == "not_cached"

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
    ready = read_guide(
        "## 8 and 10 read, 70 is current: 10, its top, carries a `stack-review` block pinned"
        " to the stack's pair, so its guide reads ready, its layers as rows and its file from"
        " the stack's Changes; 8's block below it is not the stack's.\n",
        f"{GUIDE}?stack=70",
    ).payload()
    assert (ready["state"], ready["carrier"], ready["step_count"]) == ("ready", 10, 2)
    assert ready["carrier_url"] == "https://github.com/octo/demo/pull/10"
    assert current["guide"] == {"number": 10, "revision": ready["record_revision"]}
    assert [(ref["kind"], ref["state"]) for ref in ready["references"]] == [
        ("pull", "ready"),
        ("pull", "ready"),
    ]
    assert [ref["target"]["stack"]["number"] for ref in ready["references"]] == [70, 70]
    draft = read_guide("## Its second step.\n", f"{GUIDE}?stack=70&step=2").payload()
    assert draft["references"][0]["state"] == "ready"
    assert draft["references"][0]["href"] == "/stack/70/changes/docs/draft.md"
    assert draft["comparison"] == {"merge_base": comparison["left"], "head": comparison["right"]}
    # The page asks at the comparison it draws, here the current one, which reads the same.
    drawn = f"&left={comparison['left']}&right={comparison['right']}&key={comparison['key']}"
    at_drawn = run_metab((CANONICAL, "--api", f"{GUIDE}?stack=70&step=2{drawn}")).payload()
    assert at_drawn == draft
    half = read_guide(
        "## A comparison named by less than its two commits and its key is refused.\n",
        f"{GUIDE}?stack=70&left={comparison['left']}",
    )
    assert "status: 400" in half.stdout
    beyond = read_guide("## A step past its last.\n", f"{GUIDE}?stack=70&step=3")
    assert beyond.payload()["state"] == "step_not_found"
    described = read_guide(
        "## 10's description renders without the block, as a guide's does.\n",
        "/api/plugin/github/pull-markdown?number=10&part=body",
    ).payload()
    assert "stack-review" not in described["html"] and "The layers" not in described["html"]
    both_names = read_guide(
        "## A request that names a pull request and a stack is refused.\n",
        f"{GUIDE}?stack=70&number=10",
    )
    assert "status: 400" in both_names.stdout

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

    # From here on, the stacks' other states, and 70's move, are their own transcript's.
    first_blocks, blocks = blocks, states
    into[0] = blocks
    blocks.append("## Not linear: 10's merge base is not in 8's history.\n")
    linear = stack(72)
    assert linear["reason"] == "not_linear"
    unpaired = read_guide(
        "## Stack 72 is not linear, so its guide is unavailable, with the stack's reason.\n",
        f"{GUIDE}?stack=72",
    ).payload()
    assert (unpaired["state"], unpaired["reason"]) == ("stack_unavailable", "not_linear")

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

    assert fetched["guide"] is not None and fetched["guide"]["number"] == 8
    below = read_guide(
        "## 9 read, 73 is current. Its top, 9, carries no block, so its guide is 8's, below"
        " it: pinned to 8's own head, it is out of date, and its file is no longer in the"
        " stack's changes, since 9's head lacks 8's.\n",
        f"{GUIDE}?stack=73",
    ).payload()
    assert (below["state"], below["carrier"]) == ("stale", 8)
    assert below["stale"]["current"] == {
        "merge_base": pull_origin["base"],
        "head": pull_origin["closed_head"],
    }
    assert below["references"][0]["state"] == "path_not_changed"

    blocks.append("## A number no stack has, and a request that names more than it.\n")
    assert stack(99)["reason"] == "not_stacked"
    refused = api(f"{ROUTE}?number=70&left=main")
    assert "status: 400" in refused.stdout

    shown = in_guide(
        "## The stack's page, as `--show` reports it: the merge its header shows, its guide,"
        " Guided Review as its front page's tab, and Changes at Changes' own address. Its files"
        " are its header's Diff summary, so there is no Files tab to show.\n",
        "--show",
        "/stack/70",
    )
    assert "kind: pull-stack" in shown.stdout
    assert "guide=#10 tab=guided" in shown.stdout
    changes_shown = in_guide("", "--show", "/stack/70/changes")
    assert "tab=changes" in changes_shown.stdout
    files_shown = in_guide("", "--show", "/stack/70/files")
    assert files_shown.exit_code != 0
    guided_shown = in_guide("", "--show", "/stack/70/guided")
    assert "guide=#10 tab=guided" in guided_shown.stdout

    file_shown = in_guide(
        "## The stack's page at a file, as `--show` reports it: its kind and layers.\n",
        "--show",
        "/stack/70/changes/docs/draft.md",
    )
    assert "kind: pull-stack" in file_shown.stdout
    assert "layers=2/2:#10" in file_shown.stdout

    blocks.append(
        "## The stack moves: 70 is now 10 alone. A page still draws the comparison it was"
        " given, so that comparison keeps answering and its rendered documents keep being"
        " admitted, while an address the route never gave is still refused. Asked `since` that"
        " comparison, the answer's `moved` names no member: 8's going is in the two answers'"
        " members, and 10, which stayed, did not move.\n"
    )
    answers["api"][STACKS] = ok(
        STACKS,
        [_stack(70, [10]), _stack(71, [8, 7, 10]), _stack(72, [10, 8]), _stack(73, [8, 9])],
    )
    install_fake_gh(tmp_path, answers)
    request.write_text('{"retry": true}\n')
    run(
        CANONICAL,
        "--api",
        "/api/plugin/github/stacks-refresh",
        "--data",
        str(request),
        gh_free=False,
    )
    moved_on = api(f"{ROUTE}?number=70&since={comparison['key']}").payload()
    assert moved_on["state"] == "current"
    assert [member["number"] for member in moved_on["members"]] == [10]
    assert moved_on["comparison"]["key"] != comparison["key"]
    assert moved_on["moved"] == {"since": comparison["key"], "members": []}
    kept = api(comparison["route"])
    assert kept.exit_code == 0, kept.stderr
    assert _paths(kept.payload()) == ["docs/draft.md"]
    kept_rendered = api(f"{comparison['rendered_route']}&file={guide['id']}")
    assert kept_rendered.exit_code == 0, kept_rendered.stderr
    assert "status: 410" not in kept_rendered.stdout
    never = api(comparison["route"].replace(comparison["key"], "0" * 32))
    assert "status: 410" in never.stdout
    # The guide follows the comparison the page draws, as the Diff summary, Docs, and Changes
    # do: at the current pair, 10 alone, its pins are behind; at the pair the page still
    # draws, it reads as it did, until the reader takes the new comparison.
    now = run_metab((CANONICAL, "--api", f"{GUIDE}?stack=70&step=2")).payload()
    assert (now["state"], now["comparison"]["merge_base"]) == ("stale", pull_origin["topic"])
    still = read_guide(
        "## Its guide, asked at the comparison a page still draws, reads as it did there.\n",
        f"{GUIDE}?stack=70&step=2{drawn}",
    ).payload()
    assert {**still, "record_revision": None} == {**draft, "record_revision": None}
    gone = read_guide(
        "## A comparison the route never gave has moved, as the stack's comparison route says.\n",
        f"{GUIDE}?stack=70&step=2{drawn.replace(comparison['key'], '0' * 32)}",
    ).payload()
    assert (gone["state"], gone["carrier"]) == ("stack_moved", 10)
    # 10's author pins its guide to the stack's new pair. Read at that pair it is current;
    # at the pair a page still draws, it was written for a later comparison than that one, so
    # it is `stack_moved` there too, never out of date the wrong way round (B1 of review B
    # on #838).
    pinned_old = _stack_guide(pull_origin["base"], pull_origin["draft_head"], _TOP_GUIDE)
    top["body"] = top["body"].replace(
        pinned_old,
        _stack_guide(now["comparison"]["merge_base"], now["comparison"]["head"], _TOP_GUIDE),
    )
    # A new body is a new ETag, so the refresh reads it rather than a 304.
    top_answer = pulls["repos/octo/demo/pulls/10"]
    top_answer["headers"] = {
        **top_answer["headers"],
        "Etag": ok("repos/octo/demo/pulls/10", top)["headers"]["Etag"],
    }
    install_fake_gh(tmp_path, answers)
    ask.write_text('{"number": 10, "retry": true}\n')
    pinned = in_guide(
        "## 10's author pins its guide to the stack's new pair, and 10 is read again.\n",
        "--api",
        REFRESH,
        "--data",
        str(ask),
        gh_free=False,
    )
    assert '"refresh": "started"' in pinned.stdout
    repinned = run_metab((CANONICAL, "--api", f"{GUIDE}?stack=70&step=2")).payload()
    assert (repinned["state"], repinned["comparison"]["merge_base"]) == (
        "ready",
        pull_origin["topic"],
    )
    past = read_guide(
        "## Its guide, asked at the comparison a page still draws, is pinned past it, so it"
        " says the stack has moved, as a comparison the route never gave does.\n",
        f"{GUIDE}?stack=70&step=2{drawn}",
    ).payload()
    assert (past["state"], past["carrier"], past["record_revision"]) == (
        "stack_moved",
        10,
        repinned["record_revision"],
    )

    answers["api"][STACKS] = ok(
        STACKS,
        [
            _stack(70, [10]),
            _stack(71, [8, 7, 10]),
            _stack(72, [10, 8]),
            _stack(73, [8, 9]),
            _stack(74, [7]),
        ],
    )
    install_fake_gh(tmp_path, answers)
    in_guide(
        "## Last, stack 74 arrives, 7 alone.\n",
        "--api",
        "/api/plugin/github/stacks-refresh",
        "--data",
        str(request),
        gh_free=False,
    )
    refused_twice = read_guide(
        "## 7's description has two `stack-review` blocks, so 74's guide is refused, and"
        " says why.\n",
        f"{GUIDE}?stack=74",
    ).payload()
    assert (refused_twice["state"], refused_twice["carrier"]) == ("invalid", 7)
    assert refused_twice["message"] == "Use one stack-review block in the pull request description."

    # `since`: how a member's head moved since a comparison a page drew.
    seven = "repos/octo/demo/pulls/7"

    def move_seven(head: str) -> None:
        """Move 7's head to *head*, at the stand-in and in GitHub's answers, and read 7 again
        as the reader's own open of it."""
        subprocess.run(
            ["git", "--git-dir", str(pull_origin.path), "update-ref", "refs/pull/7/head", head],
            check=True,
            capture_output=True,
            env=git_env(tmp_path),
        )
        body = {**pulls[seven]["body"], "head": {**pulls[seven]["body"]["head"], "sha": head}}
        pulls[seven] = ok(seven, body)
        pulls["graphql:core:7"] = graph_core_entry(body)
        for part in ("check-runs", "status"):
            listed = page(f"repos/octo/demo/commits/{head}/{part}")
            held = page(f"repos/octo/demo/commits/{pull_origin['fork_head']}/{part}")
            pulls[listed] = ok(listed, pulls[held]["body"])
        install_fake_gh(tmp_path, answers)
        ask.write_text('{"number": 7, "retry": true}\n')
        reread = run_metab((CANONICAL, "--api", REFRESH, "--data", str(ask)))
        assert '"refresh": "started"' in reread.stdout, reread.stderr
        # The read asked GitHub, as the transcripts above show a page's own ask does.
        assert logged_gh_calls(tmp_path)

    blocks.append("## 74 is 7 alone, drawn at 7's head.\n")
    drawn_74 = stack(74)
    assert drawn_74["state"] == "current" and drawn_74["moved"] is None
    move_seven(pull_origin["fork_earlier"])
    blocks.append(
        "## 7's branch is rewritten to its earlier commit, which lacks the head the page drew:"
        " asked `since` the comparison the page drew, 7 moved, and no count says what is new.\n"
    )
    rewritten = api(f"{ROUTE}?number=74&since={drawn_74['comparison']['key']}").payload()
    assert rewritten["moved"] == {
        "since": drawn_74["comparison"]["key"],
        "members": [{"number": 7, "commits": None}],
    }
    move_seven(pull_origin["fork_head"])
    blocks.append(
        "## 7 gains a commit on top of the earlier one, so asked `since` the comparison a page"
        " drew there, 7 has one new commit.\n"
    )
    grown = api(f"{ROUTE}?number=74&since={rewritten['comparison']['key']}").payload()
    assert grown["moved"] == {
        "since": rewritten["comparison"]["key"],
        "members": [{"number": 7, "commits": 1}],
    }
    assert grown["comparison"]["key"] == drawn_74["comparison"]["key"]
    blocks.append(
        "## `since` the comparison it answers names no move, and nor does a key the route"
        " never gave; one that is not a key is refused.\n"
    )
    assert api(f"{ROUTE}?number=74&since={grown['comparison']['key']}").payload()["moved"] is None
    assert api(f"{ROUTE}?number=74&since={'0' * 32}").payload()["moved"] is None
    assert "status: 400" in api(f"{ROUTE}?number=74&since=main").stdout

    for name, written in (
        ("cli-github-stack.txt", first_blocks),
        ("cli-github-stack-states.txt", states),
        ("cli-github-stack-guide.txt", guide_blocks),
    ):
        rendered_text = operational_once(_scoped("".join(written)))
        # A rendered document's anchors are named by its sandbox-derived namespace.
        rendered_text = re.sub(
            r"user-content-[0-9a-f]{24}-", "user-content-<ANCHORS>-", rendered_text
        )
        rendered_text = mask_pushed_bytes(label_home(labels.apply(rendered_text), home))
        assert str(tmp_path) not in rendered_text and "file://" not in rendered_text
        check_golden(name, rendered_text)
    # The answers tests/dom/github-stack-page-session.js replays, as the route gave them.
    answers = {
        "pending": pending,
        "current": current,
        "lacking": lacking,
        "not_linear": linear,
        "left": moved_on,
        "rewritten": rewritten,
        "grown": grown,
    }
    # A pushed size is zlib's output, so the recording holds a stand-in for it, which the
    # session replays as it would any size.
    check_recording(
        "github-stack-responses.json",
        json.loads(
            re.sub(
                r'"pushed_bytes": \d+',
                '"pushed_bytes": 4096',
                labels.apply(_scoped(json.dumps(answers))),
            )
        ),
        transcript="cli-ui-github-stack-page.tryscript.md",
    )
    assert json.loads(json.dumps(current)) == current
    # The comparison `current` names, as its route gave it: what the Pulls tab reads for the
    # Whole stack row's files, whose rows tests/dom/github-pulls-stack-files-session.js has
    # the diff view make of it (`summaryRows`).
    check_recording(
        "github-stack-comparison-responses.json",
        json.loads(labels.apply(_scoped(json.dumps({"current": whole})))),
        transcript="cli-ui-github-pulls-stack-files.tryscript.md",
    )

    # The stack's size is its comparison's, measured where the comparison was built, and only
    # where that is the plain diff of its two commits, so the size and the file count
    # describe one diff (mb-68uk). 70's and 71's leave README.md out, which the plain diff
    # holds, so no pair of commits pushes their files alone and they have no size; a member
    # page's measuring its own adds none. 74's is 7's whole diff: its patch's size is the
    # pinned patch of its two commits, counted here from Git itself.
    from metabrowser.git.change_size import DIFF_ARGS

    assert current["size"] is None and lacking["size"] is None
    store = parse_qs(urlsplit(lacking["comparison"]["route"]).query)["store"][0]
    for member in lacking["members"]:
        if not member["in_top"]:
            continue
        run_metab(
            (
                CANONICAL,
                "--api",
                f"/api/plugin/github/pull-size?number={member['number']}"
                f"&left={member['base']}&right={member['head']}&store={store}",
            )
        )
    assert run_metab((CANONICAL, "--api", f"{ROUTE}?number=71")).payload()["size"] is None
    pair = grown["comparison"]
    patch = subprocess.run(
        ["git", "--git-dir", str(pull_origin.path), *DIFF_ARGS, pair["left"], pair["right"], "--"],
        check=True,
        capture_output=True,
        env=git_env(tmp_path),
    ).stdout
    assert grown["size"] is not None and grown["size"]["diff_bytes"] == len(patch), grown["size"]
    assert grown["size"]["pushed_bytes"] > 0
    assert lacking["commits"] == current["commits"] == 2
