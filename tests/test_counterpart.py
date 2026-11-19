"""A page's github.com counterpart: the mapping's one statement, and the route's refusals.

``tests/golden/cli-api-counterpart.tryscript.md`` answers every page and every reason
over a checkout and a mirror; this module holds the design system's table to
:data:`~metabrowser.counterpart.PAGES`, checks what needs no repository, and holds the
View on GitHub button's browserless session (``tests/dom/counterpart-session.js``,
``tests/golden/cli-ui-counterpart.tryscript.md``) to its menu button's contract.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.github.pull_file_anchor import path_digest
from metabrowser.builtin_plugins.github.urls import (
    GithubUrlReducer,
    file_anchor,
    pulls_url,
    repository_url,
)
from metabrowser.cache.providers import counterpart_host_for
from metabrowser.cache.urls import (
    FileAnchor,
    GitSource,
    RepositorySelection,
    classify_root_argument,
)
from metabrowser.counterpart import MAX_PAGE_CHARS, PAGES, REASONS, CounterpartReason
from metabrowser.repository_context import RepositoryContext
from tests.golden_harness import run_session

DESIGN_SYSTEM = Path(__file__).resolve().parents[1] / "docs" / "design-system.md"
CANONICAL = "https://github.com/octo/demo"
COMMIT = "6df6ba6b3b36f70b432b10b50b9a156ba27bc348"
# `printf README.md | shasum -a 256`, as tests/test_github_url_reducer.py has it.
README_DIGEST = "b335630551682c19a781afebcf4d07bf978fb1f8ac04c6bf87428ed5106870f5"


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n{heading}\n")
    level = heading.split(" ", 1)[0]
    after = text[start + len(heading) + 2 :]
    following = re.search(rf"^#{{1,{len(level)}}} ", after, flags=re.MULTILINE)
    return after if following is None else after[: following.start()]


def _where_it_appears() -> str:
    return _section(DESIGN_SYSTEM.read_text(encoding="utf-8"), "### Where It Appears")


def _table_rows(section: str) -> list[list[str]]:
    rows = [line for line in section.splitlines() if line.startswith("| ")]
    cells = [[cell.strip() for cell in row.strip("|").split(" | ")] for row in rows]
    # The header and its rule.
    return cells[2:]


def _plain(cell: str) -> str:
    return cell.replace("`", "")


def test_the_design_system_table_is_the_mapping() -> None:
    rows = _table_rows(_where_it_appears())

    assert [(_plain(page), _plain(counterpart)) for page, counterpart, _ in rows] == [
        (shape.page, shape.counterpart) for shape in PAGES.values()
    ]
    assert [
        () if reasons == "None" else tuple(_plain(reasons).split(", "))
        for _page, _counterpart, reasons in rows
    ] == [shape.reasons for shape in PAGES.values()]


def test_every_reason_is_listed_once_and_named_where_the_table_is() -> None:
    assert get_args(CounterpartReason.__value__) == REASONS
    assert len(set(REASONS)) == len(REASONS)
    for shape in PAGES.values():
        assert set(shape.reasons) <= set(REASONS), shape
        assert "no_repository" not in shape.reasons and "not_a_page" not in shape.reasons
    section = _where_it_appears()
    for reason in REASONS:
        assert f"`{reason}`" in section, reason


# ── The route ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "query",
    [{}, {"page": ""}, {"page": "/" + "x" * MAX_PAGE_CHARS}],
    ids=["absent", "empty", "too long"],
)
def test_a_request_without_a_page_is_refused(tmp_path: Path, query: dict[str, str]) -> None:
    server._set_root_dir(tmp_path)

    answer = TestClient(server.app).get("/api/counterpart", params=query)

    assert answer.status_code == 400
    assert answer.json()["code"] == "invalid_request"


@pytest.mark.parametrize(
    "page",
    [
        "/settings",
        "/view",
        "/pull/0",
        "/pull/7/commits",
        "/commit/6df6ba6",
        "/commit/main",
        "/" + "x" * (MAX_PAGE_CHARS - 1),
    ],
)
def test_an_address_that_is_no_page_has_no_counterpart(tmp_path: Path, page: str) -> None:
    # Told before the repository is looked for, so a folder with none answers it too.
    server._set_root_dir(tmp_path)

    answer = TestClient(server.app).get("/api/counterpart", params={"page": page})

    assert answer.status_code == 200
    assert answer.json() == {"page": page, "counterpart": None, "reason": "not_a_page"}


def test_the_route_is_a_get(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)

    answer = TestClient(server.app).post("/api/counterpart?page=/view/", json={})

    assert answer.status_code == 405


# ── The URLs, which the GitHub plugin builds ────────────────────────


def _selection(url: str) -> RepositorySelection:
    classified = classify_root_argument(url, reducers=(GithubUrlReducer(),))
    assert isinstance(classified, GitSource), classified
    assert classified.normalized == CANONICAL
    assert classified.selection is not None
    return classified.selection


def test_a_file_anchor_is_the_one_a_pull_request_file_resolves_by() -> None:
    assert file_anchor(b"README.md") == FileAnchor(README_DIGEST)
    for path in ("README.md", "docs/雪 notes.md"):
        assert file_anchor(path.encode()).digest == path_digest(path)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            f"{CANONICAL}/commit/{COMMIT}#diff-{README_DIGEST}",
            RepositorySelection(kind="commit", commit=COMMIT, pull_file=FileAnchor(README_DIGEST)),
        ),
        (
            f"{CANONICAL}/commit/{COMMIT}#diff-{README_DIGEST}R3",
            RepositorySelection(
                kind="commit", commit=COMMIT, pull_file=FileAnchor(README_DIGEST, "R3")
            ),
        ),
        (f"{CANONICAL}/commit/{COMMIT}#L3", RepositorySelection(kind="commit", commit=COMMIT)),
    ],
    ids=["file", "file line", "other fragment"],
)
def test_a_commit_page_anchors_a_file_as_a_changes_tab_does(
    url: str, expected: RepositorySelection
) -> None:
    selection = _selection(url)

    assert selection == expected
    again = GithubUrlReducer().web_url(CANONICAL, expected)
    assert again is not None
    assert _selection(again) == expected


def test_a_pull_request_commit_keeps_no_anchor() -> None:
    url = f"{CANONICAL}/pull/12/commits/abcdef0#diff-{README_DIGEST}"

    selection = _selection(url)

    assert selection == RepositorySelection(kind="commit", commit="abcdef0", pull_request=12)
    assert GithubUrlReducer().web_url(CANONICAL, selection) == (
        f"{CANONICAL}/pull/12/commits/abcdef0"
    )


def test_the_list_of_pull_requests_is_beside_the_repository() -> None:
    assert pulls_url(repository_url("octo", "demo")) == f"{CANONICAL}/pulls"
    assert pulls_url("https://example.com/octo/demo") is None


def _context(host: str, owner: str = "octo", name: str = "demo") -> RepositoryContext:
    return RepositoryContext(
        branch="main",
        branch_on_origin=True,
        host=host,
        name=name,
        owner=owner,
        revision=COMMIT,
        served_prefix="",
    )


def test_the_route_reaches_github_through_its_provider() -> None:
    """``counterpart.py`` names no provider: the host comes from ``cache/providers.py``."""

    source = (Path(__file__).resolve().parents[1] / "src/metabrowser/counterpart.py").read_text(
        encoding="utf-8"
    )
    assert "metabrowser.builtin_plugins" not in source
    hosted = counterpart_host_for(_context("github.com", "Octo", "Demo"))
    assert hosted is not None
    host, clone_url = hosted
    assert (host.provider, host.label, clone_url) == ("github", "View on GitHub", CANONICAL)
    assert host.pulls_url(clone_url) == f"{CANONICAL}/pulls"
    assert host.file_anchor(b"README.md") == FileAnchor(README_DIGEST)
    selection = RepositorySelection(kind="tree", ref_and_path=(COMMIT.encode(), b"docs"))
    assert host.web_url(clone_url, selection) == f"{CANONICAL}/tree/{COMMIT}/docs"
    assert counterpart_host_for(_context("gitlab.com")) is None


def test_the_button_is_one_menu_button_and_the_corner_follows_the_page() -> None:
    """``tests/dom/counterpart-session.js`` over the production SDK: the app's hooks, the
    menu's keyboard and pointer, Copy Link, and what a corner asks the server and keeps."""

    told = run_session("counterpart-session.js")
    markup = told["markup"]
    group, menu = markup["children"]
    link, chevron = group["children"]
    assert markup["data-view-on-github"] == ""
    assert (link["tag"], link["data-view-on-github"], link["target"], link["rel"]) == (
        "a",
        "open",
        "_blank",
        "noopener",
    )
    assert (chevron["aria-haspopup"], chevron["aria-expanded"]) == ("menu", "false")
    copy, external = menu["children"]
    assert (menu["role"], menu.get("hidden")) == ("menu", True)
    assert (copy["role"], external["role"]) == ("menuitem", "menuitem")
    assert (external["data-view-on-github"], external["target"], external["rel"]) == (
        "external",
        "_blank",
        "noopener",
    )
    assert external["href"] == link["href"]
    # The menu holds a listener on the document only while it is open.
    for step in told["menu"]:
        assert step["outsideListeners"] == (1 if step["menu"] == "open" else 0), step
    # Escape is the menu's: it closes it and goes no further.
    escapes = [step for step in told["menu"] if step["step"] == "Escape"]
    assert escapes and all(step["prevented"] and step["stopped"] for step in escapes)
    tips = [(step.get("tip"), step.get("tipAfter")) for step in told["copy"][:3]]
    assert tips == [
        ("Link copied", "Copy Link or Open in Browser"),
        ("Copy failed", "Copy Link or Open in Browser"),
        ("Copy failed", "Copy Link or Open in Browser"),
    ]
    mount = {step["step"]: step for step in told["mount"]}
    assert mount["the same page again"]["asked"] == []
    assert mount["a page with none"]["corner"] == "empty"
    assert mount["the first answer lands late"]["corner"].endswith("/pull/7/files")
    assert mount["an answer whose address is a script"]["corner"] == "empty"
    assert mount["another provider's answer"]["hook"] == "data-view-on-gitlab"
    assert mount["a page with a space and a hash"]["asked"] == [
        "/api/counterpart?page=%2Fview%2Fa%20b%23c.md"
    ]
