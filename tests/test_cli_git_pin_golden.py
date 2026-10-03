"""Golden CLI transcripts for a leased file:// Git pin over a multi-entry origin.

One transcript per scenario, each small enough to read in a review:

- ``cli-git-pin-show.txt`` -- ``--show`` kinds and routes, and how a typed selection is
  read when a tracked name looks like a wire identity;
- ``cli-git-pin-index.txt`` -- index status, capabilities, source status, ``--check-api``;
- ``cli-git-pin-tree.txt`` -- ``/api/tree`` chrome, nesting, a subtree, and a type filter;
- ``cli-git-pin-rollup.txt`` -- ``/api/rollup`` and ``/api/catalog``;
- ``cli-git-pin-files.txt`` -- ``/api/file`` per kind of entry, and the blob-reading hooks;
- ``cli-git-pin-refusals.txt`` -- every refusal ``--api`` can reach.

Commands run through ``_run_cli``, the entry point the ``metab`` console script
uses, so a refused route records the exit code and the ``Error:`` line a user
sees rather than a test-only rendering of the exception. Nothing binds a port.

Why in-process and not tryscript
--------------------------------

A subprocess can open a pin: ``tests/golden/cli-api-source.tryscript.md`` does, on a
store ``tests/source_mirror_fixture.py`` acquired beforehand with the floor stood in
for. These transcripts stay in-process for what that would give up:

- This module is in ``ADMITTED_GIT_TESTS``, so the admitted-Git jobs compare the same
  transcripts on the lowest admitted Git and the newest patched one, with the real
  floor: the acquisition, and every ``ls-tree`` and ``cat-file`` read behind a block.
  tryscript runs in the default tier only, on the runner's own Git.
- A command costs a function call here and a process there. Measured on 2026-10-01 in
  the CI ``test (3.13)`` job: the 35 commands of the single transcript this module then
  wrote took 2.3 s, and the tryscript transcripts 0.5 s a command (306 in 148 s).

``/raw`` and ``/view/`` are not ``/api/`` routes, so ``--api`` cannot reach them and no
transcript here shows them; ``tests/test_git_revision_content_routes.py`` asserts them.

The origin
----------

``pin_origin`` builds one bare repository with ``git fast-import``, which
writes tree entries directly: no worktree, so no filesystem name normalization,
no umask, and no mode bits a checkout decides. The committer line, message,
and every blob are fixed, so ``PIN_ORIGIN_REVISION`` holds on every machine and
the builder asserts it. The branch is ``topic`` because public hygiene rejects
the default-branch spelling.

Every entry answers something a one-file origin cannot:

- ``README.md`` -- a direct-child README, which is what mounts folder Overview.
- ``a-b``, ``a.txt``, ``a/``, ``ab`` -- the byte-order boundary around ``/``
  (0x2F). Git orders a tree as if a directory name ended in ``/``, so its
  canonical order is ``a-b``, ``a.txt``, ``a/...``, ``ab``. ``/api/tree`` lists its
  ``entries`` by name bytes with directories interleaved (``a``, ``a-b``, ``a.txt``,
  ``ab``) and its SPA ``tree`` directories first, the order of a folder listing, while
  ``/api/catalog`` keeps the recursive blob order. ``a-b`` and ``ab`` have no
  extension, which pins where ``ext`` is omitted.
- ``a/deep/nested.md``, ``a/deep/payload.json`` -- a second directory level,
  so ``depth`` nesting and the lazy sentinel past the cap are visible.
- ``a/one.py`` -- source, so ``type_families`` has a code member.
- ``bin/glyph.png`` -- a real 1x1 PNG, so the image kind is pinned from stored
  bytes.
- ``bin/sample.bin`` -- NUL-bearing bytes, so the binary kind and its chunk
  hook are pinned.
- ``bin/oversize.bin`` -- one byte past ``TEXT_PREVIEW_REQUEST_MAX_BYTES``, with
  the production constant rather than a lowered test bound. It packs to a few
  kilobytes because the content is one repeated byte. It shows that a blob past
  the whole-read limit is classified from a bounded window and paged like a large
  file on disk, and that a window starting past the text budget is refused.
- ``data/events.jsonl`` -- a JSONL blob, a distinct kind with a parsed envelope.
- ``links/to-readme.md`` -- an in-tree relative symlink (mode 120000).
  Listings show the link; ``/api/file`` and the binary hook follow it.
- ``odd/`` -- names the tree stores exactly and displays with U+FFFD: a
  newline, a tab, and a byte that is not UTF-8. The GitPath wire stays lossless.
- ``tools/run.sh`` -- an executable blob (mode 100755).
- ``vendor`` -- a gitlink (mode 160000) whose commit the store does not have.

Git cannot record an empty directory in a commit's tree, so the fixture has
none. ``object_unavailable`` is not in a transcript: reaching it needs a tree
that names an object the store lacks, and acquisition refuses such an origin.
``tests/test_git_revision_content_routes.py`` asserts it directly.

The assertions beside each transcript are relations a reader could not check by eye
and a regeneration could drop without anyone noticing: a figure that must equal the
fixture's, an order, a format the payload must satisfy. What a transcript shows
literally is not asserted again.
"""

from __future__ import annotations

import difflib
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from metabrowser.git.tree_source import GitPath
from metabrowser.settings import TEXT_PREVIEW_REQUEST_MAX_BYTES
from metabrowser.wire_models import validate_rollup_node
from tests.git_pin_harness import git_env
from tests.golden_harness import (
    Invocation,
    Labels,
    block,
    check_golden,
    file_url,
    isolate_cli,
    label_home,
    ok,
    quoted,
    refused,
)
from tests.required_tools import needs_git

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = needs_git

# Pinned by the fast-import recipe below: tree, committer identity and date,
# and message are fixed, and a commit id is a function of nothing else.
PIN_ORIGIN_REVISION = "8653ceb4d5ca69e2e7e3b39d04645b3820233854"
PIN_ORIGIN_BRANCH = "topic"

# A 1x1 fully transparent PNG: the eight-byte signature, IHDR, one IDAT, IEND.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001"
    "08060000001f15c4890000000a49444154789c630001000005"
    "00010d0a2db40000000049454e44ae426082"
)
# A gitlink records a commit id, not an object this repository holds.
_SUBMODULE_COMMIT = "1" * 40

NEWLINE_NAME = b"line\nbreak.txt"
TAB_NAME = b"tab\there.txt"
LATIN1_NAME = b"latin-\xe9.txt"

# (mode, path segments, body). Order is irrelevant: Git sorts each tree.
PIN_ORIGIN_BLOBS: tuple[tuple[bytes, tuple[bytes, ...], bytes], ...] = (
    (b"100644", (b"README.md",), b"# Pinned fixture\n"),
    (b"100644", (b"a-b",), b"dash\n"),
    (b"100644", (b"a.txt",), b"dot text\n"),
    (b"100644", (b"a", b"deep", b"nested.md"), b"# Nested\n\nTwo levels down.\n"),
    (b"100644", (b"a", b"deep", b"payload.json"), b'{"k": 1, "list": [1, 2]}\n'),
    (b"100644", (b"a", b"one.py"), b"x = 1\n"),
    (b"100644", (b"ab",), b"plain\n"),
    (b"100644", (b"bin", b"glyph.png"), _PNG),
    (b"100644", (b"bin", b"oversize.bin"), b"\n" * (TEXT_PREVIEW_REQUEST_MAX_BYTES + 1)),
    (b"100644", (b"bin", b"sample.bin"), bytes(range(8))),
    (b"100644", (b"data", b"events.jsonl"), b'{"e": 1}\n{"e": 2}\n'),
    (b"120000", (b"links", b"to-readme.md"), b"../README.md"),
    (b"100644", (b"odd", NEWLINE_NAME), b"newline name\n"),
    (b"100644", (b"odd", TAB_NAME), b"tab name\n"),
    (b"100644", (b"odd", LATIN1_NAME), b"latin-1 name\n"),
    (b"100755", (b"tools", b"run.sh"), b"#!/bin/sh\necho pinned\n"),
)


def _wire(*segments: bytes) -> str:
    return GitPath.from_segments(*segments).to_wire()


README_WIRE = _wire(b"README.md")
DIR_A_WIRE = _wire(b"a")
NESTED_WIRE = _wire(b"a", b"deep", b"nested.md")
JSON_WIRE = _wire(b"a", b"deep", b"payload.json")
IMAGE_WIRE = _wire(b"bin", b"glyph.png")
BINARY_WIRE = _wire(b"bin", b"sample.bin")
OVERSIZE_WIRE = _wire(b"bin", b"oversize.bin")
JSONL_WIRE = _wire(b"data", b"events.jsonl")
LINKS_WIRE = _wire(b"links")
SYMLINK_WIRE = _wire(b"links", b"to-readme.md")
NEWLINE_WIRE = _wire(b"odd", NEWLINE_NAME)
LATIN1_WIRE = _wire(b"odd", LATIN1_NAME)
SCRIPT_WIRE = _wire(b"tools", b"run.sh")
GITLINK_WIRE = _wire(b"vendor")
ABSENT_WIRE = _wire(b"nope.txt")

# Tracked names that begin with Metabrowser's own wire prefix, which nothing reserves in
# Git. ``g1-data`` is the one that decodes: four base64url characters are a valid atom,
# so read as a wire it names another path instead of failing.
NAMES_ORIGIN_BLOBS: tuple[tuple[bytes, tuple[bytes, ...], bytes], ...] = (
    (b"100644", (b"g1-notes.md",), b"notes\n"),
    (b"100644", (b"plain.md",), b"plain\n"),
    (b"100644", (b"g1-tools", b"x.md"), b"tool\n"),
    (b"100644", (b"g1-data", b"x.md"), b"data\n"),
)


def _quoted_path(segments: tuple[bytes, ...]) -> bytes:
    """A fast-import C-style quoted path, so any byte but NUL survives the stream."""

    out = bytearray(b'"')
    for byte in b"/".join(segments):
        if byte in b'"\\':
            out += b"\\" + bytes([byte])
        elif 0x20 <= byte < 0x7F:
            out.append(byte)
        else:
            out += b"\\%03o" % byte
    return bytes(out + b'"')


def _fast_import_stream(
    blobs: tuple[tuple[bytes, tuple[bytes, ...], bytes], ...], gitlinks: tuple[bytes, ...]
) -> bytes:
    stream = bytearray(
        f"commit refs/heads/{PIN_ORIGIN_BRANCH}\n".encode()
        + b"committer Test <test@example.com> 1577836800 +0000\n"
        + b"data 6\nfirst\n\n"
    )
    for mode, segments, body in blobs:
        stream += b"M " + mode + b" inline " + _quoted_path(segments) + b"\n"
        stream += b"data " + str(len(body)).encode() + b"\n" + body + b"\n"
    for name in gitlinks:
        stream += b"M 160000 " + _SUBMODULE_COMMIT.encode() + b" " + name + b"\n"
    return bytes(stream + b"\ndone\n")


def _origin(
    tmp_path: Path,
    name: str,
    blobs: tuple[tuple[bytes, tuple[bytes, ...], bytes], ...],
    *,
    gitlinks: tuple[bytes, ...] = (),
) -> tuple[Path, str]:
    """A bare origin written by ``git fast-import``, and the commit its branch names."""

    origin = tmp_path / name
    env = git_env(tmp_path)
    subprocess.run(
        ["git", "init", "-q", "--bare", "--template=", "-b", PIN_ORIGIN_BRANCH, str(origin)],
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "--git-dir", str(origin), "fast-import", "--quiet", "--done"],
        check=True,
        capture_output=True,
        input=_fast_import_stream(blobs, gitlinks),
        env=env,
    )
    revision = subprocess.run(
        ["git", "--git-dir", str(origin), "rev-parse", f"refs/heads/{PIN_ORIGIN_BRANCH}"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    return origin, revision


def pin_origin(tmp_path: Path) -> Path:
    """A bare origin whose ``topic`` is ``PIN_ORIGIN_REVISION`` on every machine."""

    origin, revision = _origin(tmp_path, "origin.git", PIN_ORIGIN_BLOBS, gitlinks=(b"vendor",))
    assert revision == PIN_ORIGIN_REVISION
    return origin


# A run of lines this long that a block shares with an earlier one is shown once. Below
# it a repeat is cheaper to read in place than to look up.
_REPEAT_MIN_LINES = 40


def _name_the_repeat(stdout: str, first: str, *, shown_by: str) -> str:
    """*stdout* with the longest run of lines it shares with *first* replaced by one line.

    Every ``/api/tree`` answer carries the whole pin's filter tallies, which is some 160
    lines that do not depend on the directory listed. The first block prints them; a
    later one says how many lines it repeats and where they begin. The run is found by
    comparing the two outputs, not assumed: where they stop agreeing, the lines that
    stopped repeating print and the marker's count changes, and a run shorter than
    ``_REPEAT_MIN_LINES`` is not replaced at all. Either shows in the diff.
    """

    earlier, lines = first.splitlines(), stdout.splitlines()
    run = difflib.SequenceMatcher(None, earlier, lines, autojunk=False).find_longest_match()
    if run.size < _REPEAT_MIN_LINES:
        return stdout
    begins = lines[run.b].strip()
    # The marker names the run by its first line, which must be one place in *first*.
    assert sum(line.strip() == begins for line in earlier) == 1, begins
    marker = f"  <{run.size} lines, from {begins} on, are the same as in {shown_by} above>"
    return "\n".join([*lines[: run.b], marker, *lines[run.b + run.size :]]) + "\n"


@dataclass(slots=True)
class _Pin:
    """``metab <origin> …`` commands against the origin in use, collected as one transcript."""

    sandbox: Path
    url: str = ""
    shown: str = ""
    labels: Labels = field(default_factory=Labels)
    blocks: list[str] = field(default_factory=list)
    printed: dict[str, str] = field(default_factory=dict)

    def use(self, origin: Path, suffix: str = "") -> None:
        self.url = file_url(origin)
        self.shown = f"file://<ORIGIN{suffix}>"
        self.labels.origin(self.url, suffix, store="STORE_ID", source="SOURCE_ID")

    def _run(
        self, mode: str, *args: str, fails: bool = False, repeats: str | None = None
    ) -> Invocation:
        result = refused([self.url, mode, *args]) if fails else ok([self.url, mode, *args])
        stdout = self.printed[args[0] if args else mode] = result.stdout
        if repeats is not None:
            stdout = _name_the_repeat(stdout, self.printed[repeats], shown_by=quoted(repeats))
        command = " ".join(["metab", self.shown, mode, *(quoted(arg) for arg in args)])
        self.blocks.append(block(command, result.exit_code, stdout, result.stderr))
        return result

    def show(self, selection: str, *options: str, fails: bool = False) -> Invocation:
        return self._run("--show", selection, *options, fails=fails)

    def api(self, route: str, *, fails: bool = False, repeats: str | None = None) -> Invocation:
        """``--api route``; *repeats* names an earlier route whose output this one repeats."""

        return self._run("--api", route, fails=fails, repeats=repeats)

    def check_api(self) -> Invocation:
        return self._run("--check-api")

    def check(self, name: str) -> None:
        rendered = label_home(self.labels.apply("".join(self.blocks)), self.sandbox / "home")
        # Nothing a command printed names the sandbox or a pack, and only a clone's own
        # lines name the application home.
        assert str(self.sandbox) not in rendered
        assert "pack-" not in rendered and ".pack" not in rendered
        check_golden(name, rendered)


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One directory for the module: both origins, and the application home beside them.

    Whichever test runs first acquires an origin with its first command, and every
    later command, in that test or another, is a cache hit, as it was when one test ran
    them all. An origin and an acquisition per test cost about half a second each.
    """

    directory = tmp_path_factory.mktemp("pin")
    pin_origin(directory)
    _origin(directory, "names.git", NAMES_ORIGIN_BLOBS)
    return directory


@pytest.fixture
def pin(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> _Pin:
    isolate_cli(sandbox, monkeypatch)
    session = _Pin(sandbox)
    session.use(sandbox / "origin.git")
    return session


@posix_only
def test_golden_pin_show(pin: _Pin) -> None:
    """``--show`` kinds and routes, and a typed selection read as a display name first."""

    for selection in (
        "README.md",
        "a/deep/nested.md",
        "a/deep",
        "links/to-readme.md",
        "bin/glyph.png",
        "bin/sample.bin",
        NEWLINE_WIRE,
    ):
        pin.show(selection)
    pin.show("nope.txt", fails=True)

    pin.use(pin.sandbox / "names.git", "-NAMES")
    # A typed selection is a display name, so each tracked name resolves to itself,
    # wire-shaped or not; `g1-data` read as a wire would be another path.
    for selection in ("plain.md", "g1-notes.md", "g1-tools/x.md", "g1-data/x.md", "g1-data"):
        pin.show(selection)
    # A `/view/` address is a wire identity that a lookalike file cannot capture, and a
    # bare wire with no tracked name of that spelling still resolves.
    pin.show(f"/view/{_wire(b'g1-notes.md')}")
    pin.show(_wire(b"plain.md"))
    # The same answer as JSON, which is what a script reads.
    pin.show("g1-data/x.md", "--format", "json")
    pin.show("g1-absent.md", fails=True)
    pin.check("cli-git-pin-show.txt")


@posix_only
def test_golden_pin_index_and_status(pin: _Pin) -> None:
    """What the index, the capabilities, and the source report for a pin, and ``--check-api``."""

    for route in ("/api/index/progress", "/api/index/meta", "/api/capabilities"):
        pin.api(route)
    status = pin.api("/api/source/status").payload()
    checked = pin.check_api()
    # The recipe's commit is the one served, and the check-api scenario passes on a pin
    # because the live filter's typed refusal is the pin's honest answer.
    assert status["pin"] == status["latest"] == PIN_ORIGIN_REVISION
    assert "result: pass" in checked.stdout
    pin.check("cli-git-pin-index.txt")


@posix_only
def test_golden_pin_tree(pin: _Pin) -> None:
    """``/api/tree``: chrome, nesting to the depth cap, a subtree, a symlink, and a type filter."""

    tallies = "/api/tree?depth=0"
    chrome = pin.api(tallies)
    listing = pin.api("/api/tree?depth=2", repeats=tallies).payload()
    pin.api(f"/api/tree?path={DIR_A_WIRE}&depth=1", repeats=tallies)
    pin.api(f"/api/tree?path={LINKS_WIRE}&depth=1", repeats=tallies)
    pin.api("/api/tree?depth=1&types=.md", repeats=tallies)

    # The totals are the fixture's: every blob once, and no gitlink.
    summary = chrome.payload()["summary"]
    assert summary["files"] == len(PIN_ORIGIN_BLOBS)
    assert summary["size"] == sum(len(body) for _mode, _path, body in PIN_ORIGIN_BLOBS)
    # Directories first, then name bytes, at every level: the order a folder listing
    # uses (tree.py), which the shell renders as the server sent it.
    for nodes in (listing["tree"], listing["tree"][0]["children"]):
        expected = sorted(nodes, key=lambda node: (node["type"] != "dir", node["name"].encode()))
        assert nodes == expected
    pin.check("cli-git-pin-tree.txt")


@posix_only
def test_golden_pin_rollup_and_catalog(pin: _Pin) -> None:
    """The treemap's rollup and Quick File's catalog, both from recursive blob names."""

    rollup = pin.api("/api/rollup?depth=1").payload()
    catalog = pin.api("/api/catalog").payload()
    # The node is a File Rollup Format node, which only this check holds it to.
    validate_rollup_node(rollup["node"])
    # The catalog keeps Git's recursive blob order, where "a/…" sorts after "a.txt".
    assert [row["p"] for row in catalog["files"]] == [
        _wire(*segments) for _mode, segments, _body in sorted(PIN_ORIGIN_BLOBS, key=_blob_order)
    ]
    pin.check("cli-git-pin-rollup.txt")


def _blob_order(blob: tuple[bytes, tuple[bytes, ...], bytes]) -> bytes:
    return b"/".join(blob[1])


@posix_only
def test_golden_pin_files(pin: _Pin) -> None:
    """``/api/file`` for each kind of entry, and the plugin hooks that read a blob."""

    pin.api("/api/file")
    readme = pin.api(f"/api/file?path={README_WIRE}").payload()
    for wire in (NESTED_WIRE, DIR_A_WIRE, IMAGE_WIRE, JSONL_WIRE):
        pin.api(f"/api/file?path={wire}")
    followed = pin.api(f"/api/file?path={SYMLINK_WIRE}").payload()
    for wire in (LATIN1_WIRE, SCRIPT_WIRE, GITLINK_WIRE, JSON_WIRE):
        pin.api(f"/api/file?path={wire}")
    pin.api(f"/api/plugin/structured/parsed?path={JSON_WIRE}")
    pin.api(f"/api/plugin/binary/chunk?path={BINARY_WIRE}")
    pin.api(f"/api/plugin/binary/chunk?path={BINARY_WIRE}&offset=3&limit=4")
    pin.api(f"/api/plugin/binary/chunk?path={SYMLINK_WIRE}")
    oversize = pin.api(f"/api/file?path={OVERSIZE_WIRE}&limit=64").payload()

    # The requested link stays the route identity; the object facts are the followed
    # blob's, which is why its oid is the README's.
    assert followed["path"] == SYMLINK_WIRE and followed["oid"] == readme["oid"]
    # One byte past the whole-read limit, by the production constant, is still paged.
    assert oversize["size"] == TEXT_PREVIEW_REQUEST_MAX_BYTES + 1
    pin.check("cli-git-pin-files.txt")


@posix_only
def test_golden_pin_refusals(pin: _Pin) -> None:
    """Each way a pin says no: a capability it lacks, a path it does not hold, a bad window."""

    for route in (
        # No recency on an immutable tree, as a route and as a tree filter.
        "/api/recent",
        "/api/tree?recency=24h",
        # Absent from the tree.
        f"/api/file?path={ABSENT_WIRE}",
        # A filesystem spelling is not a GitPath identity, on any route.
        "/api/file?path=README.md",
        "/api/tree?path=a",
        "/api/rollup?path=a",
        "/api/plugin/binary/chunk?path=bin/sample.bin",
        "/api/plugin/structured/parsed?path=a/deep/payload.json",
        # A gitlink is not a tree, and a blob has no rollup.
        f"/api/tree?path={GITLINK_WIRE}",
        f"/api/rollup?path={README_WIRE}",
        # The structured hook reads structured files only.
        f"/api/plugin/structured/parsed?path={README_WIRE}",
        # A window that starts past the text budget.
        f"/api/file?path={OVERSIZE_WIRE}&offset={TEXT_PREVIEW_REQUEST_MAX_BYTES + 1}",
    ):
        pin.api(route, fails=True)
    pin.check("cli-git-pin-refusals.txt")
