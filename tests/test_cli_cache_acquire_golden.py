"""Golden CLI transcripts for file:// acquisition, and the session the cache goldens share.

Successful ``metab file:// --no-serve`` cannot run as a tryscript subprocess
where the installed Git is below the acquisition floor, which has no environment
escape by design. These goldens invoke the production CLI in-process with only
``require_acquisition_git`` and the clock replaced -- the same boundary
``tests/test_cache_acquire.py`` uses to exercise fetch. Every command goes through
``metabrowser.cli.main._run_cli``, the console script's own error rendering, so a
refusal is pinned as the ``Error:`` line and exit status a user sees.

A :class:`Session` is one transcript: its commands, their outcomes, and the labels for
what no fixture can pin. Each origin's normalized ``file://`` URL, path, source
identity, store identity, and slug depend on the sandbox path, so they become
per-origin labels such as ``<ORIGIN-A>``, ``<SOURCE-A>``, ``<STORE-A>``, and
``<SLUG-A>``; equal labels are equal values. Revisions, refs, publication and reference
states, counts, messages, and every recorded time are literal, and no transcript names
a pack file or a cache path. The origin branch is ``topic`` so the remote-tracking ref
is not the default-branch spelling public hygiene rejects; ``--initial-branch`` still
pins the name so it does not vary by Git version.

``tests/test_cli_cache_recovery_golden.py`` holds the interrupted, failed, and refused
sessions.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from metabrowser.cache.layout import migrate_layout
from metabrowser.home import ensure_home
from tests.cache_home_fixture import FIXTURE_VERSION, _stage_and_publish_store
from tests.golden_harness import (
    FixedClock,
    Labels,
    block,
    check_golden,
    file_url,
    isolate_cli,
    pinned_git,
    run_metab,
)
from tests.required_tools import needs_git

# Pinned by the identity and dates of ``pinned_git_env`` and the origin recipe below.
# A commit hash is a function of tree, parents, author, committer, and message.
ORIGIN_REVISION = "8f05aafe23bbeade03ef581868a59e3c944ac5c4"
ORIGIN_REMOTE_REF = "refs/remotes/origin/topic"

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
    needs_git,
]


def deterministic_origin(tmp_path: Path) -> Path:
    """A bare origin whose HEAD is ``ORIGIN_REVISION`` on every machine."""

    work = tmp_path / "work"
    origin = tmp_path / "origin.git"
    work.mkdir()
    pinned_git(work, "init", "-q", "--initial-branch=topic")
    (work / "README").write_text("hello\n", encoding="utf-8")
    pinned_git(work, "add", "README")
    pinned_git(work, "-c", "commit.gpgsign=false", "commit", "-qm", "first")
    pinned_git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    assert pinned_git(origin, "rev-parse", "HEAD") == ORIGIN_REVISION
    return origin


def named_origin(tmp_path: Path, name: str) -> Path:
    """A deterministic origin in its own directory, so one session can hold several."""

    parent = tmp_path / name
    parent.mkdir()
    return deterministic_origin(parent)


@dataclass(slots=True)
class Session:
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

    def no_serve(self, letter: str, url: str, *, exit_code: int = 0) -> str:
        return self.run(
            f"metab <ORIGIN-{letter}> --no-serve", [url, "--no-serve"], exit_code=exit_code
        )

    def render(self) -> str:
        text = self.labels.apply("".join(self.blocks))
        if self.child_ran:
            # What a killed child published carries its own clock's times.
            text = self.clock.elide_other_times(text)
        for leaked in {str(self.tmp_path), str(self.tmp_path.resolve())}:
            assert leaked not in text, f"sandbox path leaked into the transcript: {leaked}"
        assert ".pack" not in text
        return text


def open_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Session, Path]:
    """A session over a private home and an empty directory to serve; returns the home."""

    sandbox = isolate_cli(tmp_path, monkeypatch)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "root"
    root.mkdir()
    return Session(tmp_path=tmp_path, root=root, clock=sandbox.clock), sandbox.home


def test_golden_file_url_acquire_and_reuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session, home = open_session(tmp_path, monkeypatch)
    url = file_url(named_origin(tmp_path, "a"))
    session.origin("A", url)

    session.note("The first command fetches and publishes; the second reuses the store.")
    first = session.no_serve("A", url)
    assert session.no_serve("A", url) == first
    assert ORIGIN_REVISION in first
    assert str(home) not in first
    assert "Serving" not in first

    session.note("One source is published, aliased to the one store it acquired.")
    session.inspect("/api/cache/layout")
    sources = session.inspect("/api/cache/sources")
    stores = session.inspect("/api/cache/stores")
    assert '"transport": "file"' in sources
    assert '"publication": "published"' in sources
    assert ORIGIN_REVISION in stores
    assert ORIGIN_REMOTE_REF in stores
    assert '"object_format": "sha1"' in stores

    check_golden("cli-cache-acquire.txt", session.render())


FIRST_ORPHAN_KEY = "0" * 64


def test_golden_unreferenced_store_is_kept_by_the_next_acquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, home = open_session(tmp_path, monkeypatch)
    # The acquired store's key hashes a URL under tmp_path, so /api/cache/stores lists
    # the two stores in a different order from run to run unless the orphan's key
    # sorts first whatever that hash is.
    ensure_home(home)
    migrate_layout(home, version=FIXTURE_VERSION)
    _stage_and_publish_store(home, FIRST_ORPHAN_KEY, with_revision=False)
    url = file_url(named_origin(tmp_path, "a"))
    session.origin("A", url)

    session.note("A home an earlier release wrote holds a store no alias names.")
    layout = session.inspect("/api/cache/layout")
    assert f'"created_by": "{FIXTURE_VERSION}"' in layout
    before = session.inspect("/api/cache/stores")
    assert '"reference_state": "unreferenced"' in before
    assert f"sha256:{FIRST_ORPHAN_KEY}" in before

    session.note("Acquiring another source keeps it, unreferenced, beside the new store.")
    session.no_serve("A", url)
    after = session.inspect("/api/cache/stores")
    assert '"reference_state": "unreferenced"' in after
    assert '"reference_state": "referenced"' in after
    assert f"sha256:{FIRST_ORPHAN_KEY}" in after
    assert ORIGIN_REVISION in after

    session.note(
        "The home is current, so the acquisition rewrote neither its layout nor its config."
    )
    assert session.inspect("/api/cache/layout") == layout

    check_golden("cli-cache-orphan-kept.txt", session.render())
