"""Golden transcript: a repository folder's store of its origin, through ``metab``.

``tests/checkout_replica.py`` builds a bare origin standing in for
``https://github.com/octo/demo`` with pinned dates, so each commit ID in the transcript is
the same on every machine: ``trunk`` is ``M1`` to ``M5``. ``checkout`` is a clone of it
whose ``origin`` names the GitHub address, as a real checkout's does, with a tag of its
own, ``local-only``. The origin then moves on without the checkout fetching: ``M6`` on
``trunk``, a branch ``feature`` off ``M3``, and a tag ``v2`` at ``M4``. So the checkout's
own ``origin/trunk`` is at ``M5``, where the reader's last fetch left it, and the origin's
``trunk`` is at ``M6``.

A folder lists its origin's branches and tags from a store Metabrowser keeps beside the
checkout (``metabrowser/checkout_store.py``). A server makes that store and keeps it
fresh; a one-shot command reads the store the cache has, and fetches only through an
explicit ``POST /api/source/refresh``, which is how this transcript makes it. Each command
is its own start of the application.

The transcript runs in process, and not as a tryscript, for the reasons
``tests/test_cli_source_checkout_golden.py`` gives: a checkout's refs are read, and a store
acquired, only with a Git the acquisition floor admits. ``remote_url_for`` fetches from
the local origin, as in every acquisition transcript of a provider's address. The last
block is Git's own account of the checkout after every command above;
``tests/test_checkout_store.py`` compares every file under it byte for byte.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from metabrowser.source import reset_source_session
from tests.checkout_replica import build_linear, clone_checkout
from tests.golden_harness import (
    block,
    check_golden,
    isolate_cli,
    normalize_console,
    pinned_git,
    pinned_git_env,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

GOLDEN = "cli-api-source-checkout-store.txt"

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="the fixture's Git environment is POSIX"),
    needs_git,
]

_BODIES = {
    "refresh.json": "{}",
    "page-ask.json": '{"for": "page"}',
    "pin-origin-trunk.json": '{"ref": "refs/remotes/origin/trunk"}',
    "pin-local-trunk.json": '{"ref": "refs/heads/trunk"}',
    "pin-origin-tag.json": '{"ref": "refs/tags/v2"}',
    "pin-short-origin.json": '{"ref": "origin/trunk"}',
    "pin-short-local.json": '{"ref": "trunk"}',
}

# Each section's words, then its commands: the arguments after ``metab`` and the exit
# status each must have.
_SECTIONS: tuple[tuple[str, tuple[tuple[tuple[str, ...], int], ...]], ...] = (
    (
        "Before Metabrowser has a store of the origin, a one-shot command says so and makes "
        "none: origin is absent with the reason not_fetched, and the lists are the "
        "checkout's own, as they were before this feature. origin/trunk is where the "
        "reader's last fetch left it, at M5.",
        (
            (("checkout", "--api", "/api/source/refs?kind=remote"), 0),
            (("checkout", "--api", "/api/source/refs?kind=tag"), 0),
        ),
    ),
    (
        "With no store, --ref origin/trunk opens the checkout's own remote-tracking branch, "
        "at M5, and says on standard error that it read the checkout.",
        ((("checkout", "--ref", "origin/trunk", "--api", "/api/source/status"), 0),),
    ),
    (
        "A refresh asked of a folder makes the store: it borrows the checkout's objects and "
        "fetches what the checkout lacks. The answer is 202 and names the store's state; the "
        "status after it is the folder's, whose working tree is still served.",
        ((("checkout", "--api", "/api/source/refresh", "--data", "refresh.json"), 0),),
    ),
    (
        "With the store, the list of remote-tracking branches has the origin's branches as "
        "Metabrowser fetched them: origin/trunk at M6, first and marked as the origin's "
        "default branch, and origin/feature, which the checkout "
        "never fetched. The checkout's own origin/* is not a second list: each row says in "
        "checkout where the reader's own ref is when that is another commit, M5 on "
        "origin/trunk, and nulls on origin/feature, which the checkout has no ref for. "
        "origin says when the store was last fetched.",
        ((("checkout", "--api", "/api/source/refs?kind=remote"), 0),),
    ),
    (
        "Tags are the origin's from the store, v2, and the tag only the checkout has. The "
        "checkout's own branches are still read from the checkout: trunk at M5, checked out.",
        (
            (("checkout", "--api", "/api/source/refs?kind=tag"), 0),
            (("checkout", "--api", "/api/source/refs"), 0),
        ),
    ),
    (
        "An origin branch is served from the store, at a commit the checkout does not have. "
        "It is a folder's page still, named and placed as the folder is, and its freshness "
        "is the store's: refreshable, following its branch, and probed while a page is "
        "visible, as a mirror's pin is. read_from says the store was read.",
        ((("checkout", "--api", "/api/source/pin", "--data", "pin-origin-trunk.json"), 0),),
    ),
    (
        "The checkout's own branch is read from the checkout, at M5, and nothing fetches "
        "into it: it follows the checkout's own ref, which a visible page asks about every "
        "probe_every_s and the server answers by reading the checkout, and what is "
        "refreshable is the store of the origin. A tag the origin has is the store's.",
        (
            (("checkout", "--api", "/api/source/pin", "--data", "pin-local-trunk.json"), 0),
            (("checkout", "--api", "/api/source/pin", "--data", "pin-origin-tag.json"), 0),
        ),
    ),
    (
        "A short name is read as --ref reads one: origin/trunk and a tag the origin has "
        "from the store, and the checkout's own branch of a name from the checkout. The "
        "answer says which in read_from. --ref origin/trunk now opens the origin's trunk, "
        "at M6, and says it read the store.",
        (
            (("checkout", "--api", "/api/source/pin", "--data", "pin-short-origin.json"), 0),
            (("checkout", "--api", "/api/source/pin", "--data", "pin-short-local.json"), 0),
            (("checkout", "--ref", "origin/trunk", "--api", "/api/source/status"), 0),
        ),
    ),
    (
        "A visible page's own ask on the working tree fetches the store only when it is "
        "older than the freshness window. It was just fetched, so nothing is due.",
        ((("checkout", "--api", "/api/source/refresh", "--data", "page-ask.json"), 0),),
    ),
    (
        "A checkout whose origin is on this machine keeps no store: origin is null, the "
        "lists are the checkout's own, and a refresh is refused as a folder's always was.",
        (
            (("local", "--api", "/api/source/refs?kind=remote"), 0),
            (("local", "--api", "/api/source/refresh", "--data", "refresh.json"), 1),
        ),
    ),
)


def test_golden_a_folders_store_of_its_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    isolate_cli(root, monkeypatch)
    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(root / "config"))
    replica = build_linear(root)
    checkout = clone_checkout(replica, root / "checkout")
    pinned_git(checkout, "tag", "local-only")
    # A clone that names the local origin, which is the checkout that keeps no store.
    pinned_git(root, "clone", "-q", replica.url, str(root / "local"))
    work = root / "source"
    pinned_git(work, "checkout", "-q", "-b", "feature", replica["M3"])
    (work / "feature.txt").write_text("feature\n", encoding="utf-8")
    pinned_git(work, "add", "feature.txt")
    pinned_git(work, "commit", "-q", "-m", "F1")
    pinned_git(work, "checkout", "-q", "trunk")
    pinned_git(work, "tag", "v2", replica["M4"])
    (work / "m").write_text("m6\n", encoding="utf-8")
    pinned_git(work, "commit", "-q", "-a", "-m", "M6")
    pinned_git(work, "push", "-q", str(replica.origin), "trunk", "feature", "v2")
    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", lambda _source: replica.url)
    for name, body in _BODIES.items():
        (root / name).write_text(body + "\n", encoding="utf-8")
    monkeypatch.chdir(root)

    parts: list[str] = []
    for words, commands in _SECTIONS:
        parts.append(f"== {words}\n")
        for arguments, status in commands:
            # Each command is its own start of the application, as a process of its own was.
            reset_source_session()
            ran = run_metab(list(arguments))
            assert ran.exit_code == status, (arguments, ran.stdout, ran.stderr)
            parts.append(ran.block(" ".join(quoted(argument) for argument in arguments)))
    parts.append(
        "== None of it wrote the checkout: after every command above its branch, its tags, "
        "and its own remote-tracking branch are what the clone left, with origin/trunk at M5.\n"
    )
    for arguments in (
        ("status", "--porcelain=v1", "--branch"),
        ("for-each-ref", "--format=%(refname) %(objectname)"),
    ):
        told = subprocess.run(
            ["git", "-C", str(checkout), *arguments],
            check=True,
            capture_output=True,
            text=True,
            env=pinned_git_env(),
        )
        parts.append(block(f"git -C checkout {' '.join(arguments)}", 0, told.stdout, told.stderr))
    check_golden(GOLDEN, normalize_console("\n".join(parts), root))
