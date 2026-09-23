"""Golden CLI transcript for a leased file:// Git pin over a multi-entry origin.

Successful ``metab file:// --show`` / ``--api`` cannot run as a tryscript
subprocess on ubuntu-latest: Git 2.43.0 is below the acquisition floor, which
has no environment escape by design. These goldens invoke the production CLI
in-process with only ``require_acquisition_git`` monkeypatched -- the same
boundary as ``tests/test_cli_cache_acquire_golden.py`` -- and stay a ``.txt``
transcript rather than a ``.tryscript.md`` one. Nothing binds a port.

Commands run through ``_run_cli``, the entry point the ``metab`` console script
uses, so a refused route records the exit code and the ``Error:`` line a user
sees rather than a test-only rendering of the exception.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_git_pin_golden.py

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
  canonical order is ``a-b``, ``a.txt``, ``a/...``, ``ab``. ``/api/tree``
  currently lists by name bytes with directories interleaved (``a``, ``a-b``,
  ``a.txt``, ``ab``), unlike the directories-first order of a folder listing,
  while ``/api/catalog`` keeps the recursive blob order. The transcript records
  both as they are today. ``a-b`` and ``ab`` have no extension, which pins
  where ``ext`` is omitted.
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
  Listings show the link; ``/api/file`` follows it.
- ``odd/`` -- names the tree stores exactly and displays with U+FFFD: a
  newline, a tab, and a byte that is not UTF-8. The GitPath wire stays lossless.
- ``tools/run.sh`` -- an executable blob (mode 100755).
- ``vendor`` -- a gitlink (mode 160000) whose commit the store does not have.

Git cannot record an empty directory in a commit's tree, so the fixture has
none. ``object_unavailable`` is not in the transcript: reaching it needs a tree
that names an object the store lacks, and acquisition refuses such an origin.
``tests/test_git_revision_content_routes.py`` asserts it directly.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cli.main import _run_cli
from metabrowser.git.tree_source import GitPath
from metabrowser.settings import TEXT_PREVIEW_REQUEST_MAX_BYTES
from tests.git_pin_harness import git_env
from tests.test_cli_cache_acquire_golden import _block, _file_url, _isolate
from tests.test_cli_golden import check_golden

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")

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
SYMLINK_WIRE = _wire(b"links", b"to-readme.md")
NEWLINE_WIRE = _wire(b"odd", NEWLINE_NAME)
LATIN1_WIRE = _wire(b"odd", LATIN1_NAME)
SCRIPT_WIRE = _wire(b"tools", b"run.sh")
GITLINK_WIRE = _wire(b"vendor")
ABSENT_WIRE = _wire(b"nope.txt")


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


def _fast_import_stream() -> bytes:
    stream = bytearray(
        f"commit refs/heads/{PIN_ORIGIN_BRANCH}\n".encode()
        + b"committer Test <test@example.com> 1577836800 +0000\n"
        + b"data 6\nfirst\n\n"
    )
    for mode, segments, body in PIN_ORIGIN_BLOBS:
        stream += b"M " + mode + b" inline " + _quoted_path(segments) + b"\n"
        stream += b"data " + str(len(body)).encode() + b"\n" + body + b"\n"
    stream += b"M 160000 " + _SUBMODULE_COMMIT.encode() + b" vendor\n"
    return bytes(stream + b"\ndone\n")


def pin_origin(tmp_path: Path) -> Path:
    """A bare origin whose ``topic`` is ``PIN_ORIGIN_REVISION`` on every machine."""

    origin = tmp_path / "origin.git"
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
        input=_fast_import_stream(),
        env=env,
    )
    revision = subprocess.run(
        ["git", "--git-dir", str(origin), "rev-parse", f"refs/heads/{PIN_ORIGIN_BRANCH}"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    assert revision == PIN_ORIGIN_REVISION
    return origin


@dataclass(frozen=True, slots=True)
class _Invocation:
    """The three fields ``_block`` records for one command."""

    exit_code: int
    stdout: str
    stderr: str


def _run(args: list[str]) -> _Invocation:
    out = io.StringIO()
    err = io.StringIO()
    exit_code = 0
    with redirect_stdout(out), redirect_stderr(err):
        try:
            _run_cli(args)
        except SystemExit as exc:
            exit_code = 0 if exc.code is None else int(exc.code)
    return _Invocation(exit_code=exit_code, stdout=out.getvalue(), stderr=err.getvalue())


def _ok(args: list[str]) -> _Invocation:
    result = _run(args)
    assert result.exit_code == 0, result.stdout + result.stderr
    return result


def _refused(args: list[str]) -> _Invocation:
    result = _run(args)
    assert result.exit_code == 1, result.stdout + result.stderr
    assert "Error: " in result.stderr
    return result


def _payload(result: _Invocation) -> Any:
    return json.loads(result.stdout[result.stdout.index("{") :])


def _flatten(nodes: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Depth-first (display name, type) pairs of an SPA ``tree`` array."""

    flat: list[tuple[str, str]] = []
    for node in nodes:
        flat.append((node["name"], node["type"]))
        flat.extend(_flatten(node.get("children") or []))
    return flat


def _shell(route: str) -> str:
    """Quote a route the way the tryscript goldens do when it carries an ``&``."""

    return f"'{route}'" if "&" in route else route


@posix_only
def test_golden_multi_entry_pin_show_and_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _isolate(tmp_path, monkeypatch)
    url = _file_url(pin_origin(tmp_path))

    shows = [
        "README.md",
        "a/deep/nested.md",
        "a/deep",
        "links/to-readme.md",
        "bin/glyph.png",
        "bin/sample.bin",
        NEWLINE_WIRE,
    ]
    routes = [
        "/api/index/progress",
        "/api/index/meta",
        "/api/capabilities",
        "/api/tree?depth=0",
        "/api/tree?depth=2",
        f"/api/tree?path={DIR_A_WIRE}&depth=1",
        "/api/tree?depth=1&types=.md",
        "/api/rollup?depth=1",
        "/api/catalog",
        "/api/file",
        f"/api/file?path={README_WIRE}",
        f"/api/file?path={NESTED_WIRE}",
        f"/api/file?path={DIR_A_WIRE}",
        f"/api/file?path={IMAGE_WIRE}",
        f"/api/file?path={JSONL_WIRE}",
        f"/api/file?path={SYMLINK_WIRE}",
        f"/api/file?path={LATIN1_WIRE}",
        f"/api/file?path={SCRIPT_WIRE}",
        f"/api/file?path={GITLINK_WIRE}",
        f"/api/plugin/structured/parsed?path={JSON_WIRE}",
        f"/api/plugin/binary/chunk?path={BINARY_WIRE}",
        f"/api/file?path={OVERSIZE_WIRE}&limit=64",
    ]
    show_refusals = ["nope.txt"]
    api_refusals = [
        "/api/recent",
        f"/api/file?path={ABSENT_WIRE}",
        f"/api/file?path={OVERSIZE_WIRE}&offset={TEXT_PREVIEW_REQUEST_MAX_BYTES + 1}",
    ]

    shown = {selection: _ok([url, "--show", selection]) for selection in shows}
    answered = {route: _ok([url, "--api", route]) for route in routes}
    shown_refused = {selection: _refused([url, "--show", selection]) for selection in show_refusals}
    refused = {route: _refused([url, "--api", route]) for route in api_refusals}

    # The transcript is the contract. These assertions name what a reader
    # should take from it, so a careless regeneration cannot quietly drop them.
    assert "Serving" not in shown["README.md"].stdout
    assert f"route: /view/{README_WIRE}" in shown["README.md"].stdout
    assert "kind: markdown" in shown["a/deep/nested.md"].stdout
    assert f"route: /view/{NESTED_WIRE}" in shown["a/deep/nested.md"].stdout
    assert "kind: folder" in shown["a/deep"].stdout
    assert "kind: markdown" in shown["links/to-readme.md"].stdout
    assert "kind: image" in shown["bin/glyph.png"].stdout
    assert "kind: binary" in shown["bin/sample.bin"].stdout

    progress = _payload(answered["/api/index/progress"])
    blob_count = len(PIN_ORIGIN_BLOBS)
    assert progress["indexed_files"] == blob_count
    assert progress["complete"] is True

    chrome = _payload(answered["/api/tree?depth=0"])
    assert chrome["entries"] == [] and chrome["tree"] == []
    assert chrome["summary"]["files"] == blob_count
    assert chrome["summary"]["size"] == sum(len(body) for _mode, _path, body in PIN_ORIGIN_BLOBS)

    listing = _payload(answered["/api/tree?depth=2"])
    # Directories first, then name bytes: the order a folder listing uses
    # (tree.py), since the shell renders server order.
    names = [node["name"] for node in listing["tree"]]
    kinds = [node.get("type") for node in listing["tree"]]
    first_file = next(index for index, kind in enumerate(kinds) if kind != "dir")
    assert all(kind != "dir" for kind in kinds[first_file:]), kinds
    assert names[:first_file] == sorted(names[:first_file], key=str.encode)
    assert names[first_file:] == sorted(names[first_file:], key=str.encode)
    assert names[0] == "a" and "README.md" in names[first_file:]
    # Nested listings are directories-first too: a/deep/ precedes a/one.py.
    assert [name for name, _type in _flatten(listing["tree"])][:3] == ["a", "deep", "one.py"]
    # depth=2 nests a/'s children; a/deep/ is past the cap, so it is lazy.
    by_name = {node["name"]: node for node in listing["tree"]}
    deep = by_name["a"]["children"][0]
    assert deep["name"] == "deep" and deep["type"] == "dir"
    assert deep.get("children") is None and deep["has_children"] is True
    assert deep["total_files"] == 2
    assert by_name["links"]["children"][0]["type"] == "symlink"
    assert by_name["vendor"]["type"] == "file"
    assert [child["name"] for child in by_name["odd"]["children"]] == [
        "latin-�.txt",
        "line�break.txt",
        "tab�here.txt",
    ]

    # The catalog keeps the recursive blob order, where "a/..." sorts after "a.txt".
    catalog = _payload(answered["/api/catalog"])
    assert [row["n"] for row in catalog["files"]][:7] == [
        "README.md",
        "a-b",
        "a.txt",
        "nested.md",
        "payload.json",
        "one.py",
        "ab",
    ]
    assert catalog["complete"] is True
    assert len(catalog["files"]) == blob_count

    assert _payload(answered["/api/file"])["readme_path"] == README_WIRE
    nested = _payload(answered[f"/api/file?path={NESTED_WIRE}"])
    assert nested["content"] == "# Nested\n\nTwo levels down.\n"
    assert nested["display"] == "a/deep/nested.md"
    # The requested link stays the route identity; the object facts are the
    # followed blob's, which is why its oid is the README's.
    followed = _payload(answered[f"/api/file?path={SYMLINK_WIRE}"])
    assert followed["path"] == SYMLINK_WIRE
    assert followed["oid"] == _payload(answered[f"/api/file?path={README_WIRE}"])["oid"]
    assert _payload(answered[f"/api/file?path={LATIN1_WIRE}"])["display"] == "odd/latin-�.txt"
    assert _payload(answered[f"/api/file?path={SCRIPT_WIRE}"])["mode"] == "100755"
    assert _payload(answered[f"/api/file?path={GITLINK_WIRE}"])["type"] == "gitlink"
    assert "status: 409" in refused["/api/recent"].stdout
    assert _payload(refused["/api/recent"])["code"] == "unsupported_for_subject"
    assert "status: 404" in refused[f"/api/file?path={ABSENT_WIRE}"].stdout
    oversize = _payload(answered[f"/api/file?path={OVERSIZE_WIRE}&limit=64"])
    assert oversize["size"] == TEXT_PREVIEW_REQUEST_MAX_BYTES + 1
    assert oversize["kind"] == "text" and oversize["content_truncated"] is True
    past = f"/api/file?path={OVERSIZE_WIRE}&offset={TEXT_PREVIEW_REQUEST_MAX_BYTES + 1}"
    assert "status: 416" in refused[past].stdout

    rendered = "".join(
        [
            *(
                _block(
                    f"file://<ORIGIN> --show {selection}",
                    shown[selection],
                    origin_url=url,
                    api=False,
                )
                for selection in shows
            ),
            *(
                _block(
                    f"file://<ORIGIN> --show {selection}",
                    shown_refused[selection],
                    origin_url=url,
                    api=False,
                )
                for selection in show_refusals
            ),
            *(
                _block(
                    f"file://<ORIGIN> --api {_shell(route)}",
                    answered[route],
                    origin_url=url,
                    api=False,
                )
                for route in routes
            ),
            *(
                _block(
                    f"file://<ORIGIN> --api {_shell(route)}",
                    refused[route],
                    origin_url=url,
                    api=False,
                )
                for route in api_refusals
            ),
        ]
    )
    assert str(tmp_path) not in rendered
    assert str(home) not in rendered
    assert "pack-" not in rendered and ".pack" not in rendered
    check_golden("cli-git-pin.txt", rendered)
