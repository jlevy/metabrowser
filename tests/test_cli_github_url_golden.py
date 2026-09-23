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

Pull-request URLs read pull-request data through ``gh``, so they are opened in
``tests/test_cli_github_pull_golden.py`` with a fake ``gh`` instead.

The Git floor is patched as in the other acquisition goldens, because CI's Git is below
it. Real HTTPS is the opt-in live smoke test, ``tests/test_github_live_smoke.py``.
Refusals that stop at classification need no Git and run as a subprocess in
``tests/golden/cli-github-urls.tryscript.md``.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_github_url_golden.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from metabrowser.cache.urls import GitSource
from tests.github_origin import FIRST_COMMIT, SECOND_COMMIT, github_origin
from tests.test_cli_cache_acquire_golden import _isolate, _strip_logs
from tests.test_cli_git_pin_golden import _Invocation, _run
from tests.test_cli_golden import check_golden

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
    # Every other gh run, so nothing here can reach the gh a developer has signed in.
    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.gh_executable", lambda: None)


def _quoted(argument: str) -> str:
    return f"'{argument}'" if any(ch in argument for ch in "?#& ") else argument


def _block(args: list[str], result: _Invocation) -> str:
    return (
        f"# metab {' '.join(_quoted(arg) for arg in args)}\n"
        f"exit: {result.exit_code}\n"
        f"--- stdout ---\n{_strip_logs(result.stdout)}"
        f"--- stderr ---\n{_strip_logs(result.stderr)}"
    )


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
    [f"{RAW}/refs/heads/release/v1/docs/v1.md", "--no-serve"],
    [f"{RAW}/topic/docs/My%20Notes.md", "--no-serve"],
    [f"{REPO}/blob/release/v1/docs/v1.md#L1", "--show", "docs/v1.md"],
    [f"{REPO}/tree/release/v1", "--api", "/api/git/repo"],
    [f"{REPO}/tree/v1.0", "--api", "/api/tree?depth=1"],
]
REFUSED: list[list[str]] = [
    [f"{REPO}/tree/nope/docs", "--no-serve"],
    [f"{REPO}/blob/topic/docs/missing.md", "--show", "README.md"],
    [f"{REPO}/commit/0000000", "--no-serve"],
    [f"{REPO}/tree/tree-tag", "--no-serve"],
]


def test_golden_github_urls_open_through_a_local_stand_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate(tmp_path, monkeypatch)
    origin = github_origin(tmp_path)
    _stand_in(monkeypatch, origin)

    opened = [(args, _run(args)) for args in OPENED]
    refused = [(args, _run(args)) for args in REFUSED]
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
    pinned = by_command[f"{REPO}/tree/release/v1 --api /api/git/repo"]
    assert f'"revision": "{SECOND_COMMIT}"' in pinned.stdout

    rendered = "".join(_block(args, result) for args, result in [*opened, *refused])
    assert str(tmp_path) not in rendered and str(home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-url-open.txt", rendered)
