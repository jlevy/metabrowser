"""Golden CLI transcripts for file:// acquisition.

Successful ``metab file:// --no-serve`` cannot run as a tryscript subprocess
on ubuntu-latest: Git 2.43.0 is below the acquisition floor (2.43.7 / patched
tracks), by design. These goldens invoke the production CLI in-process with
only ``require_acquisition_git`` monkeypatched — the same boundary
``tests/test_cache_acquire.py`` uses to exercise fetch — and pin logical
identity: publication, transport, object format, remote-tracking
ref, and the deterministic revision. Sandbox-dependent slug, store/source
ids, file:// URL, timestamps, git version, and package version are
placeholders. The origin branch is ``topic`` so the remote-tracking ref is not
the default-branch spelling public hygiene rejects; ``--initial-branch`` still
pins the name so it does not vary by Git version.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_cache_acquire_golden.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from click import unstyle
from typer.testing import CliRunner

from metabrowser.cache.layout import migrate_layout
from metabrowser.cache.paths import staging_entry
from metabrowser.cli.main import _app
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from metabrowser.home import ensure_home, ensure_private_directory
from tests.cache_home_fixture import (
    FIXTURE_VERSION,
    LEFTOVER_STAGING_ENTRY,
    ORPHAN_STORE_KEY,
    _stage_and_publish_store,
)
from tests.test_cache_acquire import (
    _allow_installed_git,
    _remove_owner_write,
    _restore_owner_write,
)
from tests.test_cli_golden import check_golden

# Pinned by GIT_AUTHOR_DATE / GIT_COMMITTER_DATE and the origin recipe below.
# A commit hash is a function of tree, parents, author, committer, and message.
ORIGIN_REVISION = "8f05aafe23bbeade03ef581868a59e3c944ac5c4"
ORIGIN_REMOTE_REF = "refs/remotes/origin/topic"

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
skip_as_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root is never denied by modes, so a denial cannot be staged"
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")

runner = CliRunner()

_LOG_LINE = re.compile(r"^\d{2}:\d{2}:\d{2} \S+ \| .*\n?", re.MULTILINE)
_TIME_KEYS = frozenset({"created_at", "updated_at", "last_fetch_at", "last_opened_at", "at"})
_URL_KEYS = frozenset({"display_url", "clone_url"})
_PACKAGE_VERSION_KEYS = frozenset({"created_by", "written_by"})


def _git_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_AUTHOR_DATE": "2020-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env=_git_env(),
    )


def _deterministic_origin(tmp_path: Path) -> Path:
    """A bare origin whose HEAD is ``ORIGIN_REVISION`` on every machine."""

    work = tmp_path / "work"
    origin = tmp_path / "origin.git"
    work.mkdir()
    _git(work, "init", "-q", "--initial-branch=topic")
    (work / "README").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "README")
    _git(work, "-c", "commit.gpgsign=false", "commit", "-qm", "first")
    _git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    revision = subprocess.run(
        ["git", "-C", str(origin), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(),
    ).stdout.strip()
    assert revision == ORIGIN_REVISION
    return origin


def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("METABROWSER_PLUGINS_DIRS", "")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("TZ", "UTC")
    _allow_installed_git(monkeypatch)
    return home


def _file_url(origin: Path) -> str:
    return f"file://{origin.resolve()}"


def _strip_logs(text: str) -> str:
    out = unstyle(text)
    return _LOG_LINE.sub("", out)


def _elide_string(path: tuple[str, ...], value: str) -> str:
    key = path[-1] if path else ""
    if key in _TIME_KEYS:
        return "<TIME>"
    if key in _URL_KEYS:
        return "<ORIGIN>"
    if key == "slug":
        return "<SLUG>"
    if key == "store_id":
        return "<STORE_ID>"
    if key == "git_version":
        return "<GIT_VERSION>"
    if key in _PACKAGE_VERSION_KEYS:
        return "<VERSION>"
    if key == "id":
        if path[-2:] == ("identity", "id"):
            return "<SOURCE_ID>"
        return "<STORE_ID>"
    return value


def _elide_payload(value: Any, *, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, str):
        return _elide_string(path, value)
    if isinstance(value, Mapping):
        return {
            item_key: _elide_payload(item, path=(*path, str(item_key)))
            for item_key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_elide_payload(item, path=path) for item in value]
    return value


def _elide_no_serve(text: str, origin_url: str) -> str:
    out = text.replace(origin_url, "<ORIGIN>")
    out = re.sub(r"(?m)^slug: .+$", "slug: <SLUG>", out)
    return re.sub(r"(?m)^store: sha256:[0-9a-f]{64}$", "store: <STORE_ID>", out)


def _elide_api_stdout(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return text
    header, body = text[:start], text[start:]
    payload = json.loads(body)
    rendered = json.dumps(_elide_payload(payload), indent=2, sort_keys=False, ensure_ascii=False)
    return f"{header}{rendered}\n"


def _block(command: str, result: Any, *, origin_url: str | None, api: bool) -> str:
    stdout = _strip_logs(result.stdout)
    stderr = _strip_logs(result.stderr)
    if api:
        stdout = _elide_api_stdout(stdout)
    elif origin_url is not None:
        stdout = _elide_no_serve(stdout, origin_url)
    return (
        f"# metab {command}\n"
        f"exit: {result.exit_code}\n"
        f"--- stdout ---\n{stdout}"
        f"--- stderr ---\n{stderr}"
    )


def _invoke(args: list[str]) -> Any:
    result = runner.invoke(_app, args)
    assert result.exit_code == 0, result.output
    return result


@posix_only
def test_golden_file_url_acquire_and_reuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _isolate(tmp_path, monkeypatch)
    origin = _deterministic_origin(tmp_path)
    url = _file_url(origin)
    empty = tmp_path / "root"
    empty.mkdir()

    first = _invoke([url, "--no-serve"])
    second = _invoke([url, "--no-serve"])
    assert first.stdout == second.stdout
    assert ORIGIN_REVISION in first.stdout
    assert str(home) not in first.stdout
    assert "Serving" not in first.stdout

    layout = _invoke([str(empty), "--api", "/api/cache/layout"])
    sources = _invoke([str(empty), "--api", "/api/cache/sources"])
    stores = _invoke([str(empty), "--api", "/api/cache/stores"])
    assert ORIGIN_REVISION in stores.stdout
    assert ORIGIN_REMOTE_REF in stores.stdout
    assert '"object_format": "sha1"' in stores.stdout
    assert '"transport": "file"' in sources.stdout
    assert '"publication": "published"' in sources.stdout

    rendered = "".join(
        [
            _block("file://<ORIGIN> --no-serve", first, origin_url=url, api=False),
            _block("file://<ORIGIN> --no-serve", second, origin_url=url, api=False),
            _block("<ROOT> --api /api/cache/layout", layout, origin_url=None, api=True),
            _block("<ROOT> --api /api/cache/sources", sources, origin_url=None, api=True),
            _block("<ROOT> --api /api/cache/stores", stores, origin_url=None, api=True),
        ]
    )
    assert str(tmp_path) not in rendered
    check_golden("cli-cache-acquire.txt", rendered)


@posix_only
def test_golden_lock_free_staging_is_swept_on_acquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate(tmp_path, monkeypatch)
    ensure_home(home)
    migrate_layout(home, version=FIXTURE_VERSION)
    ensure_private_directory(home, f"{staging_entry(LEFTOVER_STAGING_ENTRY)}/repository.git")
    empty = tmp_path / "root"
    empty.mkdir()

    before = _invoke([str(empty), "--api", "/api/cache/layout"])
    assert '"staging_entries": 1' in before.stdout

    origin = _deterministic_origin(tmp_path)
    acquired = _invoke([_file_url(origin), "--no-serve"])

    after = _invoke([str(empty), "--api", "/api/cache/layout"])
    assert '"staging_entries": 0' in after.stdout
    assert list((home / "cache" / "staging").iterdir()) == []

    rendered = "".join(
        [
            _block("<ROOT> --api /api/cache/layout", before, origin_url=None, api=True),
            _block(
                "file://<ORIGIN> --no-serve",
                acquired,
                origin_url=_file_url(origin),
                api=False,
            ),
            _block("<ROOT> --api /api/cache/layout", after, origin_url=None, api=True),
        ]
    )
    assert str(tmp_path) not in rendered
    check_golden("cli-cache-recover.txt", rendered)


@posix_only
def test_golden_unreferenced_store_is_reclaimed_on_the_next_acquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate(tmp_path, monkeypatch)
    ensure_home(home)
    migrate_layout(home, version=FIXTURE_VERSION)
    _stage_and_publish_store(home, ORPHAN_STORE_KEY, with_revision=False)
    empty = tmp_path / "root"
    empty.mkdir()

    before = _invoke([str(empty), "--api", "/api/cache/stores"])
    assert '"reference_state": "unreferenced"' in before.stdout
    assert f"sha256:{ORPHAN_STORE_KEY}" in before.stdout

    origin = _deterministic_origin(tmp_path)
    acquired = _invoke([_file_url(origin), "--no-serve"])

    after = _invoke([str(empty), "--api", "/api/cache/stores"])
    assert '"reference_state": "unreferenced"' not in after.stdout
    assert '"reference_state": "referenced"' in after.stdout
    assert f"sha256:{ORPHAN_STORE_KEY}" not in after.stdout
    assert ORIGIN_REVISION in after.stdout
    assert list((home / "cache" / "repository-stores").iterdir()) != []

    rendered = "".join(
        [
            _block("<ROOT> --api /api/cache/stores", before, origin_url=None, api=True),
            _block(
                "file://<ORIGIN> --no-serve",
                acquired,
                origin_url=_file_url(origin),
                api=False,
            ),
            _block("<ROOT> --api /api/cache/stores", after, origin_url=None, api=True),
        ]
    )
    assert str(tmp_path) not in rendered
    check_golden("cli-cache-orphan-reclaim.txt", rendered)


@posix_only
@skip_as_root
def test_golden_cache_hit_against_a_home_without_owner_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate(tmp_path, monkeypatch)
    origin = _deterministic_origin(tmp_path)
    url = _file_url(origin)
    first = _invoke([url, "--no-serve"])
    _remove_owner_write(home)
    try:
        second = _invoke([url, "--no-serve"])
        assert first.stdout == second.stdout
        assert ORIGIN_REVISION in second.stdout
        rendered = "".join(
            [
                _block("file://<ORIGIN> --no-serve", first, origin_url=url, api=False),
                _block("file://<ORIGIN> --no-serve", second, origin_url=url, api=False),
            ]
        )
        assert str(tmp_path) not in rendered
        check_golden("cli-cache-readonly-hit.txt", rendered)
    finally:
        _restore_owner_write(home)
