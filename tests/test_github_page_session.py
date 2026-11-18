"""The GitHub toggle's input is what the server derives, and only a GitHub page carries it.

The owner, 2026-11-18 (mb-zp7y): the view header's upper right is "a toggle between a
gray version of the metabrowser icon and the github icon", which "would only appear on
pages that have a corresponding GitHub repo" and "only applies if the repo is available
on GitHub.com". Pages open in the Metabrowser view.

Whether a page has one is the repository context the server writes into its shell,
``window.METABROWSER_REPOSITORY_CONTEXT``, from the same functions that decide the Pulls
tab: ``discover_repository_context`` for a served checkout, which reads the ``origin``
remote and takes only github.com, and ``repository_context_for`` for a served mirror,
which asks the installed providers, the GitHub provider through the GitHub URL reducer's
grammar (``parse_repository_url``). This records those functions' answers for checkouts
whose origin is github.com over HTTPS and over SSH, served whole and from a subfolder, on
``main`` and on ``feature/x`` where origin has the branch, on ``feature/x`` where it does not,
and detached; for origins on GitLab and on a GitHub Enterprise host; for a
repository with no remote; for a plain folder; and for mirrors of a github.com
repository and of a ``file://`` one. ``tests/fixtures/github-page-shell.json`` holds the
record, which ``tests/dom/github-page-session.js`` replays and
``tests/golden/cli-ui-github-page.tryscript.md`` pins.

It also renders two shells in process: a checkout on github.com carries
``static/github-page.js`` inline, and a plain folder's does not.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from httpx2 import ASGITransport, AsyncClient

from metabrowser import paths_safe, server
from metabrowser.cache.providers import repository_context_for
from metabrowser.paths_safe import _set_root_dir
from metabrowser.repository_context import discover_repository_context
from metabrowser.source import AttachedFilesystemSubject, attach_subject, reset_source_session
from tests.golden_harness import check_recording, read_recording, run_session

_REVISION = "0123456789abcdef0123456789abcdef01234567"
# Each checkout's origin, or None for a repository with no remote; its HEAD; where it is
# served from; and whether origin has its branch (`refs/remotes/origin/<branch>`).
_CHECKOUTS: dict[str, tuple[str | None, str, str, bool]] = {
    "github-https": ("https://github.com/octo/demo.git", "ref: refs/heads/main", "", True),
    "github-feature-pushed": (
        "https://github.com/octo/demo.git",
        "ref: refs/heads/feature/x",
        "",
        True,
    ),
    "github-ssh-detached": ("git@github.com:octo/demo.git", _REVISION, "", False),
    "github-subfolder-unpushed": (
        "https://github.com/octo/demo",
        "ref: refs/heads/feature/x",
        "docs",
        False,
    ),
    "gitlab": ("https://gitlab.com/octo/demo.git", "ref: refs/heads/main", "", True),
    "github-enterprise": (
        "https://github.example.com/octo/demo.git",
        "ref: refs/heads/main",
        "",
        True,
    ),
    "no-remote": (None, "ref: refs/heads/main", "", False),
}
_MIRRORS: dict[str, str] = {
    "mirror-github": "https://github.com/octo/demo",
    "mirror-file": "file:///srv/git/demo.git",
}


def _checkout(
    root: Path, origin: str | None, head: str, served: str, on_origin: bool = False
) -> Path:
    git = root / ".git"
    (git / "refs" / "heads" / "feature").mkdir(parents=True)
    if on_origin:
        (git / "refs" / "remotes" / "origin" / "feature").mkdir(parents=True)
        for branch in ("main", "feature/x"):
            (git / "refs" / "remotes" / "origin" / branch).write_text(
                f"{_REVISION}\n", encoding="utf-8"
            )
    config = "[core]\n\trepositoryformatversion = 0\n"
    if origin is not None:
        config += f'[remote "origin"]\n\turl = {origin}\n'
    (git / "config").write_text(config, encoding="utf-8")
    (git / "HEAD").write_text(f"{head}\n", encoding="utf-8")
    for branch in ("main", "feature/x"):
        (git / "refs" / "heads" / branch).write_text(f"{_REVISION}\n", encoding="utf-8")
    target = root / served if served else root
    target.mkdir(parents=True, exist_ok=True)
    (target / "README.md").write_text("# Demo\n", encoding="utf-8")
    return target


def _recorded(tmp_path: Path) -> dict[str, Any]:
    contexts: dict[str, Any] = {}
    for name, (origin, head, served, on_origin) in _CHECKOUTS.items():
        contexts[name] = discover_repository_context(
            _checkout(tmp_path / name, origin, head, served, on_origin)
        )
    plain = tmp_path / "plain"
    plain.mkdir()
    contexts["plain-folder"] = discover_repository_context(plain)
    for name, source in _MIRRORS.items():
        contexts[name] = repository_context_for(source, revision=_REVISION, branch="main")
    return contexts


def test_fixture_is_what_the_server_derives_for_each_repository(tmp_path: Path) -> None:
    check_recording(
        "github-page-shell.json", _recorded(tmp_path), transcript="cli-ui-github-page.tryscript.md"
    )


def test_only_a_page_with_a_github_repository_carries_the_toggle(tmp_path: Path) -> None:
    module = server.STATIC_DIR.joinpath("github-page.js").read_text(encoding="utf-8")
    github = _checkout(
        tmp_path / "github", "https://github.com/octo/demo.git", "ref: refs/heads/main", ""
    )
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "README.md").write_text("# Plain\n", encoding="utf-8")

    async def shell(root: Path) -> str:
        original = paths_safe.ROOT_DIR
        _set_root_dir(root)
        attach_subject(AttachedFilesystemSubject(root))
        try:
            async with server.app.router.lifespan_context(server.app):
                transport = ASGITransport(app=server.app, raise_app_exceptions=True)
                async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                    answer = await client.get("/view/")
                    assert answer.status_code == 200, answer.text
                    return answer.text
        finally:
            reset_source_session()
            _set_root_dir(original)

    assert f"<script>{module}</script>" in asyncio.run(shell(github))
    assert "MetabrowserGithubPage" not in asyncio.run(shell(plain))


def test_the_session_shows_the_toggle_only_for_a_repository_on_github() -> None:
    recorded = read_recording("github-page-shell.json")
    pages = run_session("github-page-session.js")
    shown = {page["context"] for page in pages if page["toggle"] is not None}
    assert shown == {name for name, context in recorded.items() if context is not None}
    assert shown == {
        "github-https",
        "github-feature-pushed",
        "github-ssh-detached",
        "github-subfolder-unpushed",
        "mirror-github",
    }


def test_both_inline_scripts_are_read_once() -> None:
    """Each shell render takes the inline module from memory, not from disk."""

    assert hasattr(server._github_page_script, "cache_info")  # pyright: ignore[reportPrivateUsage]
    assert hasattr(server._mirror_heading_script, "cache_info")  # pyright: ignore[reportPrivateUsage]
