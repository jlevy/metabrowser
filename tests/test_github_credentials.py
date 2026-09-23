"""``gh`` is Git's credential helper for https://github.com and for nothing else.

Proved with ``git credential fill``, which asks the configured helpers exactly as a
fetch would after a server challenge, so no network is needed. A fake ``gh`` answers
``auth git-credential get`` with a sentinel password; a user-level helper answers with
another. The provider's arguments must clear the user's helper everywhere and let the
fake ``gh`` answer only for ``https://github.com``.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.github import provider as github_provider
from metabrowser.builtin_plugins.github.provider import GithubProvider, credential_helper_args
from metabrowser.cache.remote import remote_git_args
from metabrowser.git.process import ACQUISITION_POLICY, git_environment

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX shell script"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]

GH_SENTINEL = "gh-sentinel-7f3a"
USER_SENTINEL = "user-sentinel-91c2"

_FAKE_GH = f"""#!/bin/sh
if [ "$1 $2 $3" = "auth git-credential get" ]; then
  while IFS= read -r line && [ -n "$line" ]; do :; done
  printf 'username=x-access-token\\npassword={GH_SENTINEL}\\n'
  exit 0
fi
exit 1
"""


def _fake_gh(tmp_path: Path) -> Path:
    # A space and a quote in the directory prove the helper path is shell-quoted.
    directory = tmp_path / "fake gh's bin"
    directory.mkdir()
    gh = directory / "gh"
    gh.write_text(_FAKE_GH, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    return gh


def _user_config(tmp_path: Path) -> Path:
    config = tmp_path / "user.gitconfig"
    config.write_text(
        "[credential]\n"
        f'\thelper = "!f() {{ echo username=u; echo password={USER_SENTINEL}; }}; f"\n',
        encoding="utf-8",
    )
    return config


def _fill(
    tmp_path: Path, args: tuple[str, ...], *, protocol: str, host: str
) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_GLOBAL": str(_user_config(tmp_path)),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
        }
    )
    return subprocess.run(
        ["git", *args, "credential", "fill"],
        input=f"protocol={protocol}\nhost={host}\n\n",
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
        timeout=30,
    )


def test_only_https_github_com_reaches_gh_and_user_helpers_are_cleared(tmp_path: Path) -> None:
    args = credential_helper_args(str(_fake_gh(tmp_path)))

    github = _fill(tmp_path, args, protocol="https", host="github.com")
    assert github.returncode == 0, github.stderr
    assert f"password={GH_SENTINEL}" in github.stdout
    assert USER_SENTINEL not in github.stdout

    for protocol, host in (
        ("https", "example.com"),
        ("https", "gist.github.com"),
        ("https", "github.com.example.com"),
        ("http", "github.com"),
    ):
        other = _fill(tmp_path, args, protocol=protocol, host=host)
        assert other.returncode != 0, (protocol, host, other.stdout)
        assert GH_SENTINEL not in other.stdout, (protocol, host)
        assert USER_SENTINEL not in other.stdout, (protocol, host)
        assert "terminal prompts disabled" in other.stderr


def test_without_the_reset_the_user_helper_would_answer(tmp_path: Path) -> None:
    """The control: the empty ``credential.helper=`` is what keeps the user's out."""

    gh = _fake_gh(tmp_path)
    scoped_only = credential_helper_args(str(gh))[2:]
    other = _fill(tmp_path, scoped_only, protocol="https", host="example.com")
    assert f"password={USER_SENTINEL}" in other.stdout


def test_the_provider_adds_the_helper_only_for_github_remotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = _fake_gh(tmp_path)
    monkeypatch.setattr(github_provider, "gh_executable", lambda: str(gh))
    provider = GithubProvider()
    helper = credential_helper_args(str(gh))
    assert provider.git_config("https://github.com/octo/demo") == helper
    assert provider.git_config("https://example.com/octo/demo.git") == ()
    assert provider.git_config("file:///srv/git/demo.git") == ()
    quoted = "'" + str(gh).replace("'", "'\"'\"'") + "'"
    assert helper == (
        "-c",
        "credential.helper=",
        "-c",
        f"credential.https://github.com.helper=!{quoted} auth git-credential",
    )
    # Every network command gets it, after the protocol allowlist and stall bound.
    args = remote_git_args("https://github.com/octo/demo")
    assert args[-len(helper) :] == helper
    assert "protocol.allow=never" in args and "http.lowSpeedLimit=1000" in args
    assert remote_git_args("https://example.com/octo/demo.git")[-1] == "http.lowSpeedTime=30"
    monkeypatch.setattr(github_provider, "gh_executable", lambda: None)
    assert provider.git_config("https://github.com/octo/demo") == ()


def test_the_acquisition_environment_asks_gh_the_same_way(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same answer in the isolated environment every acquisition Git runs with."""

    gh = _fake_gh(tmp_path)
    monkeypatch.setattr(github_provider, "gh_executable", lambda: str(gh))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(_user_config(tmp_path)))

    def fill(url_args: tuple[str, ...], host: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", *url_args, "credential", "fill"],
            input=f"protocol=https\nhost={host}\n\n".encode(),
            capture_output=True,
            env=git_environment(ACQUISITION_POLICY),
            cwd=tmp_path,
            check=False,
            timeout=30,
        )

    github = fill(remote_git_args("https://github.com/octo/demo"), "github.com")
    assert f"password={GH_SENTINEL}".encode() in github.stdout
    other = fill(remote_git_args("https://example.com/octo/demo.git"), "example.com")
    assert other.returncode != 0
    assert GH_SENTINEL.encode() not in other.stdout
    assert USER_SENTINEL.encode() not in other.stdout
