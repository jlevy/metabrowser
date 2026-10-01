"""Golden CLI transcripts for interrupted, failed, and refused file:// acquisition.

These sessions complete ``tests/test_cli_cache_acquire_golden.py`` and run in-process
for the same reason: a successful acquisition cannot run as a tryscript subprocess
where the installed Git is below the acquisition floor. Every command goes
through ``metabrowser.cli.main._run_cli``, the console script's own error rendering, so
a refusal is pinned as the ``Error:`` line and exit status a user sees. Apart from the
interruptions below, the floor and the clock are the only behavior replaced:
``require_acquisition_git`` admits the installed Git, and the below-floor session
replaces ``detect_git_version`` instead so the production gate itself refuses. The other
substitutions only observe: a spy records what reclamation removed, and a guard fails
the test if a cache hit runs Git.

An interruption is a real process death. A child interpreter runs the same CLI with the
production ``publish_entry`` wrapped to SIGKILL the child at a chosen publication, so
no cleanup runs and the next command finds exactly what a crash leaves on disk. The
transcript then inspects that state through ``/api/cache/*`` and shows the next
acquisition recovering from it.

Each origin's normalized ``file://`` URL, path, source identity, store identity, and
slug depend on the sandbox path, so they become per-origin labels such as
``<ORIGIN-A>``, ``<SOURCE-A>``, ``<STORE-A>``, and ``<SLUG-A>``; equal labels are equal
values. The clock is fixed, so times are literal; the two interruption sessions also
show records a killed child wrote with the real clock, and those times read ``<TIME>``.
Revisions, refs, strategies, publication and reference states, counts, and messages are
literal, and no transcript names a pack file or a cache path.
"""

from __future__ import annotations

import os
import shutil
import signal
import stat
import subprocess
import sys
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pytest

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.identity import store_key
from metabrowser.git import process as git_process
from tests.golden_harness import (
    FixedClock,
    Labels,
    block,
    check_golden,
    file_url,
    isolate_cli,
    origin_identity,
    pinned_git,
    pinned_git_env,
    run_metab,
    strip_logs,
)
from tests.test_cache_acquire import _remove_owner_write, _restore_owner_write
from tests.test_cli_cache_acquire_golden import ORIGIN_REVISION, deterministic_origin

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
skip_as_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root is never denied by modes, so a denial cannot be staged"
)

pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]

CHILD_TIMEOUT: Final = 120
# A Git release below the acquisition floor.
BELOW_FLOOR_GIT: Final = ((2, 43, 0), "git version 2.43.0")

# The child is the production CLI with two substitutions: the acquisition floor admits
# the installed Git, as in every in-process acquisition golden, and the publication
# after the first ``survive`` ones kills the process before its rename can commit.
_KILLED_AT_PUBLICATION: Final = textwrap.dedent(
    """
    import os, signal, sys, time
    from metabrowser.cache import acquire
    from metabrowser.cli.main import _run_cli
    from metabrowser.git.process import detect_git_version

    version, _raw = detect_git_version()
    acquire.require_acquisition_git = lambda: version
    publish = acquire.publish_entry
    survive = int(sys.argv[1])
    published = 0

    def publish_entry(*args, **kwargs):
        global published
        if published == survive:
            os.kill(os.getpid(), signal.SIGKILL)
            # Publication runs on a worker thread, which on macOS can keep running
            # until the kernel tears the process down; never reach the rename.
            while True:
                time.sleep(1)
        published += 1
        return publish(*args, **kwargs)

    acquire.publish_entry = publish_entry
    _run_cli(sys.argv[2:], prog_name="metab")
    """
)


@dataclass(slots=True)
class _Session:
    """One golden transcript: commands, their outcomes, and the labels that elide them."""

    tmp_path: Path
    root: Path
    clock: FixedClock
    labels: Labels = field(default_factory=Labels)
    blocks: list[str] = field(default_factory=list[str])
    child_ran: bool = False

    def origin(self, letter: str, url: str) -> None:
        """Label every sandbox-dependent value derived from the origin at *url*."""

        self.labels.origin(url, f"-{letter}")

    def note(self, text: str) -> None:
        self.blocks.append(f"## {text}\n")

    def run(self, command: str, args: Sequence[str], *, exit_code: int = 0) -> str:
        """Run one command through the console script's error rendering."""

        result = run_metab(args)
        assert result.exit_code == exit_code, f"{command}: {result}"
        self.blocks.append(block(command, result.exit_code, result.stdout, result.stderr))
        return result.stdout + result.stderr

    def inspect(self, route: str, *, exit_code: int = 0) -> str:
        return self.run(
            f"metab <ROOT> --api {route}", [str(self.root), "--api", route], exit_code=exit_code
        )

    def killed_at_publication(self, command: str, args: Sequence[str], *, survive: int) -> None:
        """Run *args* in a child killed at the publication after *survive* others."""

        result = subprocess.run(
            [sys.executable, "-c", _KILLED_AT_PUBLICATION, str(survive), *args],
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT,
            check=False,
            env=pinned_git_env(),
        )
        assert result.returncode == -signal.SIGKILL, result.stderr
        self.child_ran = True
        self.blocks.append(block(command, "SIGKILL", result.stdout, strip_logs(result.stderr)))

    def render(self) -> str:
        text = self.labels.apply("".join(self.blocks))
        if self.child_ran:
            # What the killed child published carries its own clock's times.
            text = self.clock.elide_other_times(text)
        for leaked in {str(self.tmp_path), str(self.tmp_path.resolve())}:
            assert leaked not in text, f"sandbox path leaked into the transcript: {leaked}"
        assert ".pack" not in text
        return text


def _session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[_Session, Path]:
    sandbox = isolate_cli(tmp_path, monkeypatch)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "root"
    root.mkdir()
    return _Session(tmp_path=tmp_path, root=root, clock=sandbox.clock), sandbox.home


def _origin(tmp_path: Path, name: str) -> Path:
    parent = tmp_path / name
    parent.mkdir()
    return deterministic_origin(parent)


def _snapshot(home: Path) -> list[tuple[str, int, int, int]]:
    """Every entry below *home* with its mode, size, and modification time."""

    entries: list[tuple[str, int, int, int]] = []
    for directory, names, files in os.walk(home):
        for name in [*names, *files]:
            path = Path(directory) / name
            info = path.lstat()
            entries.append(
                (
                    str(path.relative_to(home)),
                    stat.S_IMODE(info.st_mode),
                    info.st_size if path.is_file() else 0,
                    info.st_mtime_ns,
                )
            )
    return sorted(entries)


def _no_serve(session: _Session, letter: str, url: str, *, exit_code: int = 0) -> str:
    return session.run(
        f"metab <ORIGIN-{letter}> --no-serve", [url, "--no-serve"], exit_code=exit_code
    )


# ── Interruption ──────────────────────────────────────────────────


def test_golden_interrupted_before_store_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, home = _session(tmp_path, monkeypatch)
    url = file_url(_origin(tmp_path, "a"))
    session.origin("A", url)

    session.note("A child is killed at the rename that would publish the store.")
    session.killed_at_publication("metab <ORIGIN-A> --no-serve", [url, "--no-serve"], survive=0)
    assert len(list((home / "cache" / "staging").iterdir())) == 1
    assert list((home / "cache" / "repository-stores").iterdir()) == []

    session.note("Nothing is published: one abandoned staging entry, no store, no source.")
    assert '"staging_entries": 1' in session.inspect("/api/cache/layout")
    assert '"stores": []' in session.inspect("/api/cache/stores")
    assert '"sources": []' in session.inspect("/api/cache/sources")

    session.note("The next acquisition sweeps the entry, fetches again, and publishes.")
    assert ORIGIN_REVISION in _no_serve(session, "A", url)
    assert '"staging_entries": 0' in session.inspect("/api/cache/layout")
    assert '"reference_state": "referenced"' in session.inspect("/api/cache/stores")
    assert '"publication": "published"' in session.inspect("/api/cache/sources")
    assert list((home / "cache" / "staging").iterdir()) == []

    check_golden("cli-cache-interrupt-store.txt", session.render())


def test_golden_interrupted_between_store_and_alias_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, home = _session(tmp_path, monkeypatch)
    url = file_url(_origin(tmp_path, "a"))
    session.origin("A", url)

    session.note("A child publishes the store and is killed at the source alias rename.")
    session.killed_at_publication("metab <ORIGIN-A> --no-serve", [url, "--no-serve"], survive=1)
    assert len(list((home / "cache" / "repository-stores").iterdir())) == 1
    assert list((home / "cache" / "sources").iterdir()) == []

    session.note(
        "The store is published but unreferenced, and the source is not visible: "
        "the alias is the visibility commit."
    )
    assert '"staging_entries": 1' in session.inspect("/api/cache/layout")
    assert '"reference_state": "unreferenced"' in session.inspect("/api/cache/stores")
    assert '"sources": []' in session.inspect("/api/cache/sources")

    (orphan,) = list((home / "cache" / "repository-stores").iterdir())
    orphan_inode = orphan.stat().st_ino
    session.note(
        "The next acquisition fetches again, finds the same store already published, "
        "reuses it, and publishes the alias."
    )
    assert ORIGIN_REVISION in _no_serve(session, "A", url)
    assert orphan.name == store_key(origin_identity(url).store_id)
    assert orphan.stat().st_ino == orphan_inode
    layout = session.inspect("/api/cache/layout")
    assert '"staging_entries": 0' in layout
    stores = session.inspect("/api/cache/stores")
    assert '"reference_state": "unreferenced"' not in stores
    assert stores.count('"publication": "published"') == 1
    assert '"publication": "published"' in session.inspect("/api/cache/sources")

    check_golden("cli-cache-interrupt-alias.txt", session.render())


# ── Fetch failures ────────────────────────────────────────────────


def test_golden_fetch_failures_leave_other_sources_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, home = _session(tmp_path, monkeypatch)
    url = file_url(_origin(tmp_path, "a"))
    session.origin("A", url)
    missing = tmp_path / "missing.git"
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "README").write_text("not a repository\n", encoding="utf-8")
    empty = tmp_path / "empty.git"
    empty.mkdir()
    pinned_git(empty, "init", "-q", "--bare", "--initial-branch=topic")
    detached_origin = _origin(tmp_path, "detached")
    detached = detached_origin.parent / "work"
    pinned_git(detached, "checkout", "-q", "--detach")
    failures = {
        "MISSING": ("a path that does not exist", missing),
        "PLAIN": ("a directory that is not a repository", plain),
        "EMPTY": ("a repository with no commits", empty),
        "DETACHED": ("a repository whose HEAD is not a branch", detached),
    }
    for letter, (_why, path) in failures.items():
        session.origin(letter, file_url(path))

    session.note("Source A is acquired.")
    first = _no_serve(session, "A", url)
    snapshot = _snapshot(home / "cache" / "repository-stores")

    for letter, (why, path) in failures.items():
        session.note(f"Source {letter}, {why}, fails without publishing anything.")
        failed = _no_serve(session, letter, file_url(path), exit_code=1)
        assert str(tmp_path) not in failed
    session.note("The route mode refuses the same way and never issues the route.")
    session.run(
        "metab <ORIGIN-MISSING> --api /api/cache/sources",
        [file_url(missing), "--api", "/api/cache/sources"],
        exit_code=1,
    )

    session.note("Only A is published, its alias generation is unchanged, and staging is empty.")
    layout = session.inspect("/api/cache/layout")
    assert '"staging_entries": 0' in layout
    sources = session.inspect("/api/cache/sources")
    assert sources.count('"slug":') == 1
    assert '"generation": 1' in sources
    session.inspect("/api/cache/stores")
    assert _snapshot(home / "cache" / "repository-stores") == snapshot

    session.note("A is still a cache hit, and another spelling of A normalizes to A.")
    assert _no_serve(session, "A", url) == first
    path_a = url.removeprefix("file://")
    folded = session.run(
        "metab FILE://LocalHost<PATH-A>/ --no-serve",
        [f"FILE://LocalHost{path_a}/", "--no-serve"],
    )
    assert folded == first
    assert _snapshot(home / "cache" / "repository-stores") == snapshot

    check_golden("cli-cache-fetch-failures.txt", session.render())


# ── Unsupported Git ───────────────────────────────────────────────


def _below_floor_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the production floor check against a Git below the floor."""

    monkeypatch.setattr(
        "metabrowser.cache.acquire.require_acquisition_git", git_process.require_acquisition_git
    )
    monkeypatch.setattr(git_process, "detect_git_version", lambda: BELOW_FLOOR_GIT)


def test_golden_below_floor_git_refuses_a_miss_and_still_reuses_a_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, home = _session(tmp_path, monkeypatch)
    url_a = file_url(_origin(tmp_path, "a"))
    url_b = file_url(_origin(tmp_path, "b"))
    session.origin("A", url_a)
    session.origin("B", url_b)
    installed = git_process.detect_git_version()[0]
    assert installed is not None

    _below_floor_git(monkeypatch)
    session.note(
        "Git 2.43.0 is below the acquisition floor. The first acquisition is refused "
        "and the application home is not created."
    )
    refused = _no_serve(session, "A", url_a, exit_code=1)
    assert "unsupported Git version (git version 2.43.0)" in refused
    assert not home.exists()
    session.run(
        "metab <ORIGIN-A> --api /api/cache/layout",
        [url_a, "--api", "/api/cache/layout"],
        exit_code=1,
    )
    assert not home.exists()
    assert '"home": "absent"' in session.inspect("/api/cache/layout")
    assert not home.exists()

    session.note("An empty directory named as the home is left empty.")
    home.mkdir(mode=0o700)
    _no_serve(session, "A", url_a, exit_code=1)
    assert list(home.iterdir()) == []

    session.note("With a Git at or above the floor, A is acquired.")
    monkeypatch.setattr("metabrowser.cache.acquire.require_acquisition_git", lambda: installed)
    acquired = _no_serve(session, "A", url_a)

    _below_floor_git(monkeypatch)
    origin_a = Path(url_a.removeprefix("file://"))
    origin_a.rename(origin_a.with_name("moved.git"))

    async def no_git(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("a cache hit runs no Git")

    monkeypatch.setattr(acquire_module, "_run", no_git)
    session.note(
        "Below the floor again, with origin A moved away, A is reused without Git, and a "
        "new source B is refused without changing the home."
    )
    assert _no_serve(session, "A", url_a) == acquired
    before = _snapshot(home)
    _no_serve(session, "B", url_b, exit_code=1)
    assert _snapshot(home) == before
    sources = session.inspect("/api/cache/sources")
    assert sources.count('"slug":') == 1

    check_golden("cli-cache-unsupported-git.txt", session.render())


# ── Repair guidance ───────────────────────────────────────────────


def test_golden_refusals_name_their_repair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session, home = _session(tmp_path, monkeypatch)
    url_a = file_url(_origin(tmp_path, "a"))
    url_b = file_url(_origin(tmp_path, "b"))
    session.origin("A", url_a)
    session.origin("B", url_b)

    session.note("METABROWSER_HOME must name an absolute path; nothing is created otherwise.")
    for value in ("", "relative/home"):
        monkeypatch.setenv("METABROWSER_HOME", value)
        session.run(
            f"METABROWSER_HOME={value} metab <ORIGIN-A> --no-serve",
            [url_a, "--no-serve"],
            exit_code=1,
        )
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    assert not home.exists()
    assert not (Path.cwd() / "relative").exists()

    session.note("A is acquired into a private home.")
    acquired = _no_serve(session, "A", url_a)

    session.note(
        "A home other users can read refuses both a cache hit and a new acquisition, "
        "says how to fix it, and is not changed."
    )
    home.chmod(0o755)
    before = _snapshot(home)
    assert "Run chmod 700 on it" in _no_serve(session, "A", url_a, exit_code=1)
    assert "Run chmod 700 on it" in _no_serve(session, "B", url_b, exit_code=1)
    assert _snapshot(home) == before
    session.note("After chmod 700, A is reused and B is acquired.")
    home.chmod(0o700)
    assert _no_serve(session, "A", url_a) == acquired
    _no_serve(session, "B", url_b)

    session.note("A home written by a newer release is refused before anything is written.")
    layout = home / "cache" / "layout.yml"
    layout.write_text(
        layout.read_text(encoding="utf-8").replace("format: f01", "format: f02", 1),
        encoding="utf-8",
    )
    before = _snapshot(home)
    refused = _no_serve(session, "A", url_a, exit_code=1)
    assert "Upgrade Metabrowser" in refused
    assert _snapshot(home) == before

    session.note("Another METABROWSER_HOME, as the message suggests, acquires independently.")
    other = tmp_path / "other-home"
    monkeypatch.setenv("METABROWSER_HOME", str(other))
    _no_serve(session, "A", url_a)
    assert _snapshot(home) == before

    check_golden("cli-cache-repair-guidance.txt", session.render())


@skip_as_root
def test_golden_a_home_without_owner_write_refuses_a_miss_and_reuses_a_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, home = _session(tmp_path, monkeypatch)
    url_a = file_url(_origin(tmp_path, "a"))
    url_b = file_url(_origin(tmp_path, "b"))
    session.origin("A", url_a)
    session.origin("B", url_b)

    session.note("A is acquired, then the owner's write permission is removed from the home.")
    acquired = _no_serve(session, "A", url_a)
    _remove_owner_write(home)
    try:
        before = _snapshot(home)
        session.note("A is reused. A new source B is refused, and nothing in the home changes.")
        assert _no_serve(session, "A", url_a) == acquired
        refused = _no_serve(session, "B", url_b, exit_code=1)
        assert str(tmp_path) not in refused
        assert _snapshot(home) == before
    finally:
        _restore_owner_write(home)

    session.note("With owner write restored, B is acquired.")
    _no_serve(session, "B", url_b)

    check_golden("cli-cache-readonly-miss.txt", session.render())
