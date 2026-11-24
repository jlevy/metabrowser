"""A PDF's view in Chrome: the browser's viewer inline when trusted, a note when not.

``tests/dom/pdf-preview-chrome.mjs`` serves a folder holding a PDF, trusted and
``--untrusted``, and in headless Chrome opens its view and then its ``/raw`` address as a
top-level tab, as the view's Open in new tab does. Trusted, the view's ``<embed>`` loads
Chrome's PDF viewer under ``/raw``'s CSP sandbox, with no policy violation. Untrusted,
the page's ``object-src 'none'`` leaves no ``<embed>`` to block: the view draws its note
and actions instead. Either way the top-level tab loads the viewer, sandbox and all.

Whether the viewer loaded is read from the frame tree, where Chrome's viewer is a frame
of its extension's origin; its painting of the pages is Chrome's. What the view draws for
each host and profile is pinned without a browser in
``tests/dom/pdf-preview-session.js``. Without Chrome this skips (``require_chrome`` in
``tests/required_tools.py``).
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import pytest

from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_node

SESSION = Path(__file__).resolve().parent / "dom" / "pdf-preview-chrome.mjs"
# A server start, one Chrome, and two pages, each waiting at most 20 s for the viewer.
# A cold Chrome start in CI has taken 28.2 s (the Overview alignment test, 2026-11-14),
# and the server's start is bounded at 60 s inside the session.
SESSION_TIMEOUT_S = 100
# The longest the test can take: the session's bound, its process group stopped after it
# (Chrome and the server are in it), and the profile's teardown (tests/process_group.py),
# with 10 s more for the rest of the setup; tests/test_process_group.py holds the sum under
# the module's limit.
LIFECYCLE_S = SESSION_TIMEOUT_S + GROUP_STOP_S + PROFILE_TEARDOWN_S
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)
_METAB = Path(sys.executable).with_name("metab")

# A one-page PDF with a binary comment after its header, as writers emit, and an xref
# table whose offsets are computed below, so the viewer opens it without repair.
_OBJECTS = (
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R"
    b" /Resources << /Font << /F1 5 0 R >> >> >>",
    b"<< /Length 44 >>\nstream\nBT /F1 24 Tf 40 100 Td (Hello PDF) Tj ET\nendstream",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
)


def _pdf() -> bytes:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(_OBJECTS, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(_OBJECTS) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(_OBJECTS) + 1,
        xref,
    )
    return bytes(out)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _run(tmp_path: Path, chrome_profile: Path, flags: list[str]) -> dict[str, object]:
    chrome = require_chrome()
    root = tmp_path / "served"
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "hello.pdf").write_bytes(_pdf())
    state = tmp_path / "state"
    state.mkdir()
    result = run_in_own_group(
        [
            require_node(),
            str(SESSION),
            str(_METAB),
            str(root),
            str(_free_port()),
            str(state),
            "papers/hello.pdf",
            *flags,
        ],
        timeout_s=SESSION_TIMEOUT_S,
        env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
    )
    assert not result.timed_out, (
        f"the session ran past {SESSION_TIMEOUT_S} s: {result.stderr or result.stdout}"
    )
    assert result.returncode == 0, result.stderr or result.stdout
    record: dict[str, object] = json.loads(result.stdout.strip().splitlines()[-1])
    return record


def test_a_trusted_pdf_shows_in_chromes_viewer_inline(tmp_path: Path, chrome_profile: Path) -> None:
    record = _run(tmp_path, chrome_profile, [])
    view = record["view"]
    assert isinstance(view, dict)
    assert view["embed"] == {
        "type": "application/pdf",
        "src": "/raw?path=papers%2Fhello.pdf",
        "height": view["embed"]["height"],
    }
    assert view["embed"]["height"] > 200
    assert view["note"] is None
    assert view["actions"] == ["Download", "Open in new tab"]
    assert view["violations"] == []
    assert view["viewerLoaded"] is True
    assert record["newTabHref"] == "/raw?path=papers%2Fhello.pdf"
    assert record["topLevel"] == {"viewerLoaded": True}


def test_an_untrusted_pdf_draws_a_note_and_opens_in_a_tab(
    tmp_path: Path, chrome_profile: Path
) -> None:
    record = _run(tmp_path, chrome_profile, ["--untrusted"])
    view = record["view"]
    assert isinstance(view, dict)
    assert view["embed"] is None
    assert view["note"] == (
        "This source is untrusted, so its PDFs are not shown inline."
        " Open in new tab shows this one."
    )
    assert view["actions"] == ["Download", "Open in new tab"]
    assert view["violations"] == []
    assert view["viewerLoaded"] is False
    assert record["topLevel"] == {"viewerLoaded": True}
