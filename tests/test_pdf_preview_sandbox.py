"""The macOS sandbox the PDF preview's render child runs under (threat model T7).

A preview of an untrusted source's PDF is drawn only inside it
(``metabrowser.builtin_plugins.pdf.preview_isolation``). These tests start the real
probe, draw a real PDF under the profile it found, and then run code of the test's own
under the same profile, standing in for a PDFium a PDF has taken over: a file write, a
connection to a listening socket, a fork, an exec of another program, and a read of a
file outside the directories the profile names all fail, where the same code without the
profile succeeds. The control is what shows each failure is the sandbox's.

macOS only: ``sandbox-exec`` is macOS's, and elsewhere the probe answers no sandbox, which
``tests/test_pdf_preview_routes.py`` covers.
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.pdf import preview, preview_isolation
from metabrowser.builtin_plugins.pdf.preview_isolation import Isolation, Sandbox
from tests.test_pdf_surfaces_session import _PDF

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="sandbox-exec, the confinement under test, is macOS's"
)

# What the hostile code tries, each printing "allowed" or the error that stopped it.
_ATTEMPTS = r"""
import os, socket, subprocess, sys
target, port, secret = sys.argv[1], int(sys.argv[2]), sys.argv[3]
def attempt(name, action):
    try:
        action()
        print(name, "allowed")
    except BaseException as exc:
        print(name, "refused", type(exc).__name__)
def write():
    with open(target, "w") as handle:
        handle.write("x")
def connect():
    with socket.create_connection(("127.0.0.1", port), timeout=2):
        pass
def fork():
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
def run():
    subprocess.run(["/bin/echo", "hi"], check=True, capture_output=True)
def read():
    with open(secret) as handle:
        handle.read()
attempt("write", write)
attempt("connect", connect)
attempt("fork", fork)
attempt("exec", run)
attempt("read", read)
"""


def _probed() -> Sandbox:
    found = asyncio.run(preview_isolation.probe_sandbox())
    if found is None:
        pytest.fail("the probe found no sandbox on this macOS; previews of untrusted PDFs are off")
    return found


def _attempts(prefix: tuple[str, ...], tmp_path: Path) -> dict[str, str]:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    secret = tmp_path / "secret.txt"
    secret.write_text("the reader's own file\n")
    try:
        result = subprocess.run(
            [
                *prefix,
                sys.executable,
                "-I",
                "-B",
                "-c",
                _ATTEMPTS,
                str(tmp_path / "written.txt"),
                str(listener.getsockname()[1]),
                str(secret),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=preview_isolation.child_environment(),
            cwd="/",
            check=False,
        )
    finally:
        listener.close()
    assert result.returncode == 0, result.stderr
    return {line.split()[0]: line.split(" ", 1)[1] for line in result.stdout.splitlines()}


def test_the_probed_sandbox_draws_a_pdf() -> None:
    sandbox = _probed()
    assert sandbox.prefix[:2] == (preview_isolation.SANDBOX_EXEC, "-p")
    facts, png = asyncio.run(preview.render(_PDF, Isolation(sandbox)))
    assert (facts.width, facts.height, facts.pages) == (480, 320, 1)
    assert preview.png_facts(png) == facts


def test_the_sandbox_refuses_what_a_taken_over_renderer_would_try(tmp_path: Path) -> None:
    sandbox = _probed()
    # The control: bare, every attempt succeeds, so each refusal below is the sandbox's.
    bare = _attempts((), tmp_path)
    assert set(bare.values()) == {"allowed"}, bare
    (tmp_path / "written.txt").unlink()
    confined = _attempts(sandbox.prefix, tmp_path)
    assert {name: seen.split()[0] for name, seen in confined.items()} == {
        "write": "refused",
        "connect": "refused",
        "fork": "refused",
        "exec": "refused",
        "read": "refused",
    }, confined
    assert not (tmp_path / "written.txt").exists()
