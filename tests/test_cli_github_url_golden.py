"""Golden CLI transcript: every GitHub URL shape opened end to end, with no network.

Each command runs the production CLI in-process, as ``tests/test_cli_git_pin_golden.py``
does, with two substitutions and nothing else:

- ``metabrowser.cache.acquire.remote_url_for`` fetches ``https://github.com/octo/demo``
  from the local origin in ``tests/github_origin.py``, so the store, the source alias,
  and every line of output carry the canonical GitHub identity while no request leaves
  the machine; and
- the GitHub provider sees no ``gh``, so there is no size check and no credential
  helper (both are covered in ``tests/test_github_provider.py`` and
  ``tests/test_github_credentials.py``).

Pull-request URLs run against a ``gh`` that fails every command, so they show the
fallback to what the mirror answers without pull-request data. Reading that data is
``tests/test_cli_github_pull_golden.py``, with a fake ``gh`` that answers.

The Git floor and the clock are replaced as in the other acquisition goldens
(``tests/golden_harness.py``). Real HTTPS is the opt-in live smoke test,
``tests/test_github_live_smoke.py``. Refusals that stop at classification need no Git
and run as a subprocess in ``tests/golden/cli-github-urls.tryscript.md``.

What an origin answers for a repository it does not show cannot be asked for without the
network, so ``cli-github-not-found.txt`` answers ``ls-remote`` with the text Git printed
for one; its test says what is substituted.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cache import acquire
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import GitCommandError
from metabrowser.git.tree_source import GitPath
from tests.git_pin_harness import git_env
from tests.github_origin import FIRST_COMMIT, SECOND_COMMIT, _commit, github_origin
from tests.golden_harness import Invocation, check_golden, isolate_cli, quoted, run_metab

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

CANONICAL = "https://github.com/octo/demo"
REPO = "https://github.com/octo/demo"
RAW = "https://raw.githubusercontent.com/octo/demo"


def _stand_in(monkeypatch: pytest.MonkeyPatch, origin: Path) -> None:
    local = f"file://{origin.resolve()}"

    def remote_url_for(source: GitSource) -> str:
        return local if source.normalized == CANONICAL else source.normalized

    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
    monkeypatch.setattr("metabrowser.builtin_plugins.github.provider.gh_executable", lambda: None)
    # Every other gh run finds one that fails first on PATH, so nothing here can reach
    # the gh a developer has signed in.
    failing = origin.parent / "failing-gh"
    failing.mkdir(exist_ok=True)
    gh = failing / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{failing}{os.pathsep}{os.environ.get('PATH', '')}")


def _add_unicode_branch(origin: Path) -> None:
    """``unicode``: the first commit plus ``docs/雪.md``, a path a person pastes raw,
    ``docs/a<U+202E>b.md``, whose name holds a right-to-left override, and
    ``docs/❤️.md``, an emoji whose variation selector U+FE0F is part of its name.

    The shared origin's commit IDs are pinned by every GitHub golden, so the name lives
    on a branch of its own, written with a fixed committer and date.
    """

    stream = _commit(
        "refs/heads/unicode",
        "a name outside ASCII",
        {
            "docs/雪.md".encode(): b"# Snow\n",
            f"docs/a{chr(0x202E)}b.md".encode(): b"# Override\n",
            f"docs/{chr(0x2764)}{chr(0xFE0F)}.md".encode(): b"# Heart\n",
        },
        parent=FIRST_COMMIT,
        when=1767236400,
    )
    subprocess.run(
        ["git", "--git-dir", str(origin), "fast-import", "--quiet"],
        check=True,
        capture_output=True,
        input=stream + b"done\n",
        env=git_env(origin.parent),
    )


def _block(args: list[str], result: Invocation) -> str:
    return result.block(" ".join(quoted(arg) for arg in args))


# U+2764 HEAVY BLACK HEART and U+FE0F VARIATION SELECTOR-16: the emoji ❤️.
HEART = f"{chr(0x2764)}{chr(0xFE0F)}"
OPENED: list[list[str]] = [
    [f"{REPO.replace('octo/demo', 'Octo/Demo')}.git", "--no-serve"],
    ["https://www.github.com/octo/demo/", "--no-serve"],
    ["git@github.com:octo/demo.git", "--no-serve"],
    [f"{REPO}/tree/release/v1/docs", "--no-serve"],
    [f"{REPO}/blob/topic/README.md?plain=1&utm_source=chat#L3-L4", "--no-serve"],
    [f"{REPO}/blob/v1.0/docs/v1.md#L1C3-L1C9", "--no-serve"],
    [f"{REPO}/tree/refs/tags/same", "--no-serve"],
    [f"{REPO}/tree/523f/docs", "--no-serve"],
    [f"{REPO}/commit/523F476", "--no-serve"],
    [f"{REPO}/pull/7/files", "--no-serve"],
    [f"{REPO}/pull/7/commits/89e0fad", "--no-serve"],
    [f"{RAW}/refs/heads/release/v1/docs/v1.md", "--no-serve"],
    [f"{RAW}/topic/docs/My%20Notes.md", "--no-serve"],
    [f"{REPO}/blob/release/v1/docs/v1.md#L1", "--show", "docs/v1.md"],
    [f"{REPO}/tree/release/v1", "--api", "/api/git/repo"],
    [f"{REPO}/tree/v1.0", "--api", "/api/tree?depth=1"],
    [f"{REPO}/pull/7", "--api", "/api/git/repo"],
    [f"{REPO}/blob/HEAD/docs/guide.md", "--no-serve"],
    # Pasted as an address bar shows it, and as a browser sends it: each raw spelling
    # opens what its encoded one opens (RAW_AND_ENCODED).
    [f"{REPO}/blob/topic/docs/My Notes.md", "--no-serve"],
    [f"{REPO}/blob/topic/docs/My%20Notes.md", "--no-serve"],
    [f"{RAW}/topic/docs/My Notes.md", "--no-serve"],
    [f"{REPO}/blob/unicode/docs/雪.md#L1", "--no-serve"],
    [f"{REPO}/blob/unicode/docs/%E9%9B%AA.md#L1", "--no-serve"],
    # A name holding a right-to-left override prints it as U+FFFD.
    [f"{REPO}/blob/unicode/docs/a%E2%80%AEb.md", "--no-serve"],
    # An emoji name keeps its variation selector, pasted raw or encoded.
    [f"{REPO}/blob/unicode/docs/{HEART}.md", "--no-serve"],
    [f"{REPO}/blob/unicode/docs/%E2%9D%A4%EF%B8%8F.md", "--no-serve"],
]
# The raw spellings above, each with the encoded one it must equal.
RAW_AND_ENCODED: list[tuple[str, str]] = [
    (f"{REPO}/blob/topic/docs/My Notes.md", f"{REPO}/blob/topic/docs/My%20Notes.md"),
    (f"{RAW}/topic/docs/My Notes.md", f"{RAW}/topic/docs/My%20Notes.md"),
    (f"{REPO}/blob/unicode/docs/雪.md#L1", f"{REPO}/blob/unicode/docs/%E9%9B%AA.md#L1"),
    (f"{REPO}/blob/unicode/docs/{HEART}.md", f"{REPO}/blob/unicode/docs/%E2%9D%A4%EF%B8%8F.md"),
]
REFUSED: list[list[str]] = [
    [f"{REPO}/tree/nope/docs", "--no-serve"],
    [f"{REPO}/blob/topic/docs/missing.md", "--show", "README.md"],
    [f"{REPO}/commit/0000000", "--no-serve"],
    [f"{REPO}/tree/tree-tag", "--no-serve"],
    [f"{REPO}/pull/7/commits/abcdef0", "--api", "/api/git/repo"],
    # GitHub refs are case-sensitive, whatever this filesystem is.
    [f"{REPO}/tree/TOPIC", "--no-serve"],
    # U+009B, a one-character CSI, and U+202E, which reverses the text after it, reach
    # the message as U+FFFD.
    [f"{REPO}/blob/topic/docs/%E2%80%AE2J.md", "--no-serve"],
    [f"{REPO}/blob/topic/docs/%C2%9B2J.md", "--no-serve"],
    # The reducer's hint for a raw U+3164 HANGUL FILLER, which most fonts draw as
    # nothing: its encoded spelling reaches the message as U+FFFD, as does U+2800, the
    # blank braille pattern, rather than reading as README.md or README .md.
    [f"{REPO}/blob/topic/README%E3%85%A4.md", "--no-serve"],
    [f"{REPO}/blob/topic/README%E2%A0%80.md", "--no-serve"],
    # A variation selector with no base to attach to is drawn as nothing, so it does
    # too; the one after an emoji above is kept.
    [f"{REPO}/blob/topic/README%EF%B8%8F.md", "--no-serve"],
]


def test_golden_github_urls_open_through_a_local_stand_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    origin = github_origin(tmp_path)
    _add_unicode_branch(origin)
    _stand_in(monkeypatch, origin)

    opened = [(args, run_metab(args)) for args in OPENED]
    refused = [(args, run_metab(args)) for args in REFUSED]
    for args, result in opened:
        assert result.exit_code == 0, (args, result.stdout, result.stderr)
    for args, result in refused:
        assert result.exit_code == 1, (args, result.stdout, result.stderr)
        assert "Error: " in result.stderr

    by_command = {" ".join(args): result for args, result in opened}
    first = opened[0][1].stdout
    # Every spelling of the repository is one source, one alias, and one store.
    for args, result in opened[:3]:
        assert result.stdout == first, args
    assert f"acquired: {CANONICAL}\n" in first
    assert f"revision: {FIRST_COMMIT}\n" in first
    slash = by_command[f"{REPO}/tree/release/v1/docs --no-serve"].stdout
    assert f"pin: {SECOND_COMMIT} (branch release/v1)\npath: docs\n" in slash
    anchored = by_command[f"{REPO}/blob/topic/README.md?plain=1&utm_source=chat#L3-L4 --no-serve"]
    assert "lines: L3-L4\nplain: true\n" in anchored.stdout
    assert "utm_source" not in anchored.stdout
    assert "(branch 523f)" in by_command[f"{REPO}/tree/523f/docs --no-serve"].stdout
    pull = by_command[f"{REPO}/pull/7 --api /api/git/repo"]
    assert "pull_request: 7 (not opened: " in pull.stderr and FIRST_COMMIT in pull.stdout
    assert "(gh_failed); the pin is the default branch)" in pull.stderr
    pinned = by_command[f"{REPO}/tree/release/v1 --api /api/git/repo"]
    assert f'"revision": "{SECOND_COMMIT}"' in pinned.stdout

    head = by_command[f"{REPO}/blob/HEAD/docs/guide.md --no-serve"].stdout
    assert f"pin: {FIRST_COMMIT} (default branch topic)\npath: docs/guide.md\n" in head
    for raw, encoded in RAW_AND_ENCODED:
        pasted = by_command[f"{raw} --no-serve"]
        assert (pasted.stdout, pasted.stderr) == (
            by_command[f"{encoded} --no-serve"].stdout,
            by_command[f"{encoded} --no-serve"].stderr,
        ), raw
    snow = by_command[f"{REPO}/blob/unicode/docs/雪.md#L1 --no-serve"].stdout
    assert "(branch unicode)\npath: docs/雪.md\nlines: L1\n" in snow
    assert (
        "path: docs/My Notes.md\n"
        in by_command[f"{REPO}/blob/topic/docs/My Notes.md --no-serve"].stdout
    )
    assert "\u009b" not in refused[-4][1].stderr and "\ufffd2J.md" in refused[-4][1].stderr
    override = by_command[f"{REPO}/blob/unicode/docs/a%E2%80%AEb.md --no-serve"].stdout
    assert "path: docs/a\ufffdb.md\n" in override
    assert "\ufffd2J.md is not in" in refused[-5][1].stderr
    for _args, result in refused[-3:]:
        assert "Error: README\ufffd.md is not in " in result.stderr
        assert "(path_not_found)" in result.stderr

    rendered = "".join(_block(args, result) for args, result in [*opened, *refused])
    assert chr(0x202E) not in rendered and chr(0x9B) not in rendered
    assert chr(0x3164) not in rendered and chr(0x2800) not in rendered
    heart = by_command[f"{REPO}/blob/unicode/docs/{HEART}.md --no-serve"].stdout
    assert f"(branch unicode)\npath: docs/{HEART}.md\n" in heart
    assert str(tmp_path) not in rendered and str(home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-url-open.txt", rendered)


def _add_branch(origin: Path, name: str, commit: str) -> None:
    subprocess.run(
        ["git", "--git-dir", str(origin), "update-ref", f"refs/heads/{name}", commit],
        check=True,
        env=git_env(origin.parent),
    )


def test_golden_a_selection_waits_for_the_refresh_it_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A URL selection the mirror lacks, reached through the one route that fetches.

    ``--api /api/source/refresh`` with a body is the request that fetches, so the
    selection waits for it as it would in a server: the answer is ``202`` with
    ``selection_state`` ``pending`` while the default branch is served, and the status
    after the refresh is ``found`` with the selection served and its address, or
    ``not_found``, or ``fetch_failed`` when the fetch could not run.
    """

    sandbox = isolate_cli(tmp_path, monkeypatch)
    home = sandbox.home
    origin = github_origin(tmp_path)
    _stand_in(monkeypatch, origin)
    assert run_metab([REPO, "--no-serve"]).exit_code == 0
    _add_branch(origin, "later", SECOND_COMMIT)
    body = tmp_path / "refresh.json"
    body.write_text("{}\n", encoding="utf-8")

    def refresh(url: str) -> tuple[list[str], Invocation]:
        # Each fetch has its own time, so the transcript shows which one set last_fetch_at.
        sandbox.clock.advance(10)
        return [url, "--api", "/api/source/refresh", "--data", body.name], run_metab(
            [url, "--api", "/api/source/refresh", "--data", str(body)]
        )

    found = refresh(f"{REPO}/blob/later/docs/v1.md?plain=1#L1-L2")
    missing = refresh(f"{REPO}/tree/never/docs")
    origin.rename(tmp_path / "origin-away.git")
    failed = refresh(f"{REPO}/tree/gone/docs")

    assert found[1].exit_code == 0, found[1].stderr
    assert '"selection_state": "pending"' in found[1].stdout
    assert '"selection_state": "found"' in found[1].stdout
    assert f'"pin": "{SECOND_COMMIT}"' in found[1].stdout
    wire = GitPath.from_display("docs/v1.md").to_wire()
    assert f'"selection_href": "/view/{wire}?plain=1#L1-L2"' in found[1].stdout
    assert missing[1].exit_code == 0 and '"selection_state": "not_found"' in missing[1].stdout
    assert failed[1].exit_code == 1 and '"selection_state": "fetch_failed"' in failed[1].stdout

    rendered = "".join(_block(args, result) for args, result in (found, missing, failed))
    assert str(tmp_path) not in rendered and str(home) not in rendered
    check_golden("cli-github-url-waits.txt", rendered)


# What Git 2.50.1 printed with LC_ALL=C when an origin did not show a repository;
# ``tests/test_cache_origin.py`` holds the captured set. With a credential that the
# origin refuses, and for a repository that does not exist, GitHub answers "not found";
# with no credential to offer, Git stops at the challenge. Another host's 404 is Git's
# own message with no ``remote:`` line.
_NOT_FOUND = (
    "remote: Repository not found.\nfatal: repository 'https://github.com/octo/absent/' not found"
)
_NO_CREDENTIAL = (
    "fatal: could not read Username for 'https://github.com': terminal prompts disabled"
)
_NOT_FOUND_ELSEWHERE = "fatal: repository 'https://example.com/owner/absent.git/' not found"
ABSENT = "https://github.com/octo/absent"
ELSEWHERE = "https://example.com/owner/absent.git"


def test_golden_a_repository_the_origin_does_not_show(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What ``metab`` says when an https origin answers that a repository is not there.

    An origin answers alike for a repository that does not exist, one read with no
    credentials, and one the account a credential helper answered with cannot see, so
    the message claims nothing about credentials; the provider's hint says what to do.

    No request leaves the machine, and one thing is substituted: ``ls-remote``, the
    first command that would reach the origin, raises with the text Git printed in that
    situation. So Git, ``gh``, and the origin are not exercised here, and the
    transcript's first line says so. Classifying the text, the message, the hint, and
    the exit status are production code. The ``gh`` on ``PATH`` in the first two
    commands fails every command, so the size check steps aside.
    """

    home = isolate_cli(tmp_path, monkeypatch).home
    real_run = acquire._run  # pyright: ignore[reportPrivateUsage]
    printed = {"stderr": _NOT_FOUND}

    async def not_shown(args: list[str], **kwargs: Any) -> bytes:
        if "ls-remote" in args:
            raise GitCommandError(args, 128, printed["stderr"])
        return await real_run(args, **kwargs)

    monkeypatch.setattr(acquire, "_run", not_shown)
    failing = tmp_path / "failing-gh"
    failing.mkdir()
    gh = failing / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{failing}{os.pathsep}{os.environ.get('PATH', '')}")

    with_gh = [
        ([ABSENT, "--no-serve"], run_metab([ABSENT, "--no-serve"])),
        ([ABSENT, "--show", "README.md"], run_metab([ABSENT, "--show", "README.md"])),
    ]
    monkeypatch.setattr("metabrowser.builtin_plugins.github.provider.gh_executable", lambda: None)
    printed["stderr"] = _NO_CREDENTIAL
    without_gh = ([ABSENT, "--no-serve"], run_metab([ABSENT, "--no-serve"]))
    printed["stderr"] = _NOT_FOUND_ELSEWHERE
    elsewhere = ([ELSEWHERE, "--no-serve"], run_metab([ELSEWHERE, "--no-serve"]))

    for _args, result in (*with_gh, without_gh, elsewhere):
        assert result.exit_code == 1 and result.stdout == ""
    sources = home / "cache" / "sources"
    assert not sources.is_dir() or list(sources.iterdir()) == []

    rendered = (
        "## Git's ls-remote is answered here with text Git printed when an origin did not "
        "show a repository; Git, gh, and the origin are not run.\n"
        "## gh is installed, so Git would ask it for credentials; the origin answers "
        '"Repository not found" for a refused credential and for no repository alike.\n'
        + "".join(_block(args, result) for args, result in with_gh)
        + "## Without gh Git has no credential to offer and stops at the challenge "
        '("could not read Username"); the hint is to install gh.\n'
        + _block(*without_gh)
        + "## Another host answers 404, and there is no hint.\n"
        + _block(*elsewhere)
    )
    assert str(tmp_path) not in rendered and str(home) not in rendered
    check_golden("cli-github-not-found.txt", rendered)
