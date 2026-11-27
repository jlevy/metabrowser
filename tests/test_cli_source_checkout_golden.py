"""Golden transcript: a checkout's refs, revisions, and working tree through ``metab``.

``tests/source_checkout_fixture.py`` builds ``checkout``, a clone of the fixture origin
``tests/source_mirror_fixture.py`` writes with ``git fast-import``, so each commit ID in
the transcript is the same on every machine: ``topic`` is ``first`` (``fcb9d63c3…``) then
``second`` (``42382ea…``), ``feature`` (``c7ae2a3…``) branches from ``first``, and ``v1``
is an annotated tag of ``first``. The checkout is on ``topic`` and adds what only a
checkout has: a branch ``local-work`` with a commit no remote holds, the remote-tracking
branches ``origin/topic`` and ``origin/feature``, a lightweight tag ``local-tag``, and a
working tree that is not any commit: ``README.md`` edited and not staged, ``STAGED.md`` in
the index and not committed, and ``UNTRACKED.md`` on disk only.

A folder that is a repository's root shows any branch or tag as a mirror shows one, a
pinned revision read from the checkout's own Git objects, and its working tree is a
separate choice, the one the folder opens on. Each command is its own start of the
application, so a switch lasts for that command only, and every command without ``--ref``
starts on the working tree.

The transcript runs in process, and not as a tryscript, because a checkout's revisions
are read only with a Git the acquisition floor admits (``checkout_revisions.py``, "Which
Git"), and a transcript has to read the same on whatever Git a machine has. In process the
installed Git is admitted as every acquisition transcript admits it
(``admit_installed_git``); the CI ``admitted-git`` job runs this module with nothing
patched. The last two blocks are Git's own account of the checkout after every command
above: ``HEAD``, the index, and the working tree as the fixture left them.
``tests/test_checkout_revisions.py`` compares every file under the checkout byte for byte.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from metabrowser.source import reset_source_session
from tests.golden_harness import (
    block,
    check_golden,
    isolate_cli,
    normalize_console,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git
from tests.source_checkout_fixture import (
    admit_installed_git,
    build_checkout,
    git_env,
    write_bodies,
)

GOLDEN = "cli-api-source-checkout.txt"

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="the fixture's Git environment is POSIX"),
    needs_git,
]

# A visible page's own ask, as ``--api`` posts it.
_PAGE_ASK = ("--api", "/api/source/refresh", "--data", "page-ask.json")

# Each section's words, then its commands: the arguments after ``metab`` and the exit
# status each must have.
_SECTIONS: tuple[tuple[str, tuple[tuple[tuple[str, ...], int], ...]], ...] = (
    (
        "A folder opens on its working tree: no pin and no ref, and the subject is the folder.",
        ((("checkout", "--api", "/api/source/status"), 0),),
    ),
    (
        "The selector lists the working tree and the checkout's own branches. working_tree says "
        "the working tree is served and where HEAD is, its branch and its commit, read from "
        "the checkout as the listing is made; kinds names the four lists in the order of the "
        "selector's tabs. The origin's default branch lists with the primary branches. "
        "The checked_out field names the branch the working tree is on. The current field marks "
        "a served ref.",
        ((("checkout", "--api", "/api/source/refs"), 0),),
    ),
    (
        "The working tree's own list has no refs and answers working_tree alone, with no Git "
        "process: what the selector's Working tree tab shows, and what a page asks each time "
        "its watch says the checkout's HEAD moved. That watch is on the path .git/HEAD of "
        "the page's event stream, whose generation is what HEAD names, so it is the same for "
        "a linked worktree, whose HEAD is not under that path.",
        (
            (("checkout", "--api", "/api/source/refs?kind=working_tree"), 0),
            (("checkout", "--api", "/api/events/watch", "--data", "watch-head.json"), 0),
        ),
    ),
    (
        "Remote-tracking branches are a third list, each with its remote's name. The symbolic "
        "origin/HEAD a clone writes puts its target among the primary branches. Tags list newest "
        "first, peeled to the commit they name.",
        (
            (("checkout", "--api", "/api/source/refs?kind=remote"), 0),
            (("checkout", "--api", "/api/source/refs?kind=tag"), 0),
        ),
    ),
    (
        "A branch is served as a revision of the checkout: a pin named as the folder is, with "
        "no origin and nothing to refresh, since nothing is fetched into a checkout. location "
        "is the checkout, whose Git objects the pages are read from. The page was on the "
        "folder's README.md; view_href is that file at the revision's address.",
        ((("checkout", "--api", "/api/source/pin", "--data", "pin-feature-view.json"), 0),),
    ),
    (
        "The checked-out branch is its last commit, not the working tree. STAGED.md is in the "
        "index and in no commit, so a page on it goes to the root.",
        ((("checkout", "--api", "/api/source/pin", "--data", "pin-checked-out.json"), 0),),
    ),
    (
        "A remote-tracking branch and a tag are served by name.",
        (
            (("checkout", "--api", "/api/source/pin", "--data", "pin-remote.json"), 0),
            (("checkout", "--api", "/api/source/pin", "--data", "pin-tag.json"), 0),
        ),
    ),
    (
        "The working tree is asked for by name. It is already served in a new start, so "
        "nothing changes.",
        ((("checkout", "--api", "/api/source/pin", "--data", "pin-working-tree.json"), 0),),
    ),
    (
        "A ref the checkout lacks is not found, and nothing is fetched. Revision syntax and a "
        "mixed selection are refused before any lookup.",
        (
            (("checkout", "--api", "/api/source/pin", "--data", "pin-gone.json"), 1),
            (("checkout", "--api", "/api/source/pin", "--data", "pin-syntax.json"), 1),
            (
                ("checkout", "--api", "/api/source/pin", "--data", "pin-working-tree-and-ref.json"),
                1,
            ),
        ),
    ),
    (
        "--ref opens the folder on a branch: metab PATH --ref NAME starts on a revision where "
        "metab PATH starts on the working tree, by the switch the selector makes.",
        ((("checkout", "--ref", "feature", "--api", "/api/source/status"), 0),),
    ),
    (
        "A revision of one of the checkout's own branches follows that branch: follows is "
        "true, latest is the branch's commit as last read in the checkout, and "
        "probe_every_s is how often a visible page asks where the branch is. That ask is "
        "the page's own; for it the server reads the checkout's refs, fetches nothing, and "
        "answers probed. A commit opened by its ID and the working tree never move, so the "
        "ask is refused there as a folder's refresh is.",
        (
            (("checkout", "--ref", "feature", *_PAGE_ASK), 0),
            (("checkout", "--ref", "fcb9d63c3c85", *_PAGE_ASK), 1),
            (("checkout", *_PAGE_ASK), 1),
        ),
    ),
    (
        "A revision's files are read by the routes a page reads them by. feature has "
        "FEATURE.md and the committed README.md, and none of the working tree's edited, "
        "staged, or untracked files. The catalog is every file of the revision, each named by "
        "its GitPath wire (p), as on a mirror.",
        (
            (("checkout", "--ref", "feature", "--api", "/api/catalog"), 0),
            (("checkout", "--ref", "feature", "--show", "FEATURE.md"), 0),
        ),
    ),
    (
        "The Commits tab shows the revision the Files tab shows: on feature, HEAD is "
        "feature's commit, detached, and the history is that commit's, from feature "
        "back to first, where the working tree's starts at the checked-out topic.",
        (
            (("checkout", "--ref", "feature", "--api", "/api/git/repo"), 0),
            (("checkout", "--ref", "feature", "--api", "/api/git/log?limit=2"), 0),
        ),
    ),
    (
        "--ref takes a tag, a remote-tracking branch, and a commit ID. A window of a revision "
        "is still called by its folder, and its full name adds what is shown. The two "
        "identities run with HOME at the sandbox, so the folder is named from ~.",
        (
            (("checkout", "--ref", "v1", "--api", "/api/identity"), 0),
            (("checkout", "--ref", "origin/feature", "--api", "/api/identity"), 0),
            (("checkout", "--ref", "fcb9d63c3c85", "--show", "README.md"), 0),
        ),
    ),
    (
        "The navigation check runs on a revision. A revision has no recency, so the live "
        "filter answers its typed refusal, which is what a page hides that filter by.",
        ((("checkout", "--ref", "feature", "--check-api"), 0),),
    ),
    (
        "A ref the checkout lacks, revision syntax, and a root with no checkout are refused, "
        "and nothing starts. A Git source names its branch or tag in its URL.",
        (
            (("checkout", "--ref", "gone", "--api", "/api/source/status"), 1),
            (("checkout", "--ref", "topic~1", "--show", "README.md"), 1),
            (("plain", "--ref", "feature", "--api", "/api/source/status"), 1),
            (("file://<ROOT>/origin.git", "--ref", "feature", "--api", "/api/source/status"), 1),
        ),
    ),
    (
        "A window of a checkout is called by its folder, and a plain folder has no refs to "
        "choose among.",
        (
            (("checkout", "--api", "/api/identity"), 0),
            (("plain", "--api", "/api/source/refs"), 1),
        ),
    ),
)


# The commands run with ``HOME`` at the sandbox, as a reader's checkout under their home
# directory is: a revision's full name then starts ``~/``.
_AT_HOME: frozenset[tuple[str, ...]] = frozenset(
    {
        ("checkout", "--ref", "v1", "--api", "/api/identity"),
        ("checkout", "--ref", "origin/feature", "--api", "/api/identity"),
    }
)


def test_golden_a_checkouts_refs_revisions_and_working_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    isolate_cli(root, monkeypatch)
    admit_installed_git(monkeypatch)
    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(root / "config"))
    checkout = build_checkout(root)
    write_bodies(root)
    (root / "plain").mkdir()
    monkeypatch.chdir(root)

    parts: list[str] = []
    for words, commands in _SECTIONS:
        parts.append(f"== {words}\n")
        for arguments, status in commands:
            # Each command is its own start of the application, as a process of its own
            # was: nothing served or counted by the one before it carries over.
            reset_source_session()
            with monkeypatch.context() as scoped:
                if arguments in _AT_HOME:
                    scoped.setenv("HOME", str(root))
                ran = run_metab([argument.replace("<ROOT>", str(root)) for argument in arguments])
            assert ran.exit_code == status, (arguments, ran.stdout, ran.stderr)
            parts.append(ran.block(" ".join(quoted(argument) for argument in arguments)))
    parts.append(
        "== None of it wrote the checkout: after every command above, HEAD, the index, and "
        "the working tree are what the fixture left, on topic, with README.md modified and "
        "not staged, STAGED.md added, and UNTRACKED.md untracked.\n"
    )
    for arguments in (("status", "--porcelain=v1", "--branch"), ("rev-parse", "HEAD")):
        told = subprocess.run(
            ["git", "-C", str(checkout), *arguments],
            check=True,
            capture_output=True,
            text=True,
            env=git_env(root),
        )
        parts.append(block(f"git -C checkout {' '.join(arguments)}", 0, told.stdout, told.stderr))
    check_golden(GOLDEN, normalize_console("\n".join(parts), root))
