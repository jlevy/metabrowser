"""The Folder Overview's labels share one left edge at every width, in a real Chrome.

A served folder with a README and a few kinds of file shows both Overview panels and
File Overview's Details toggle. ``tests/dom/folder-overview-alignment-chrome.mjs`` then
measures where each label's text starts at window widths that put the preview pane in
each KPress document band, and checks that every label starts on the Overview tab's
label. The rule is in ``docs/design-system.md``, "Folder Overview Is a Panel Stack".

Where text starts is computed layout, so this needs a browser; it skips without Chrome,
as ``docs/e2e-testing.md`` lists, and CI runs it.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from pathlib import Path

from tests.child_io import read_line
from tests.required_tools import require_chrome, require_node

DOM = Path(__file__).parent / "dom"
_METAB = Path(sys.executable).with_name("metab")
# The first line a server prints, naming the address it took, which is not always the
# one asked for: a port in use sends the search to the next one.
_SERVING_LINE = re.compile(r"^Serving .* at http://127\.0\.0\.1:(\d+)/view/")
# Measured at about 4 s on a 10-core Mac; the bound is for a browser that hangs, and with
# the server's 20 s start bound and its stop it stays under the suite's 60 s.
_MEASURE_TIMEOUT_S = 30
_STOP_TIMEOUT_S = 5

README = """# Sample Project

This folder exists so the Overview has both of its panels: a README long enough to wrap
at a narrow width, and files of several kinds for File Overview to break down.

## Usage

Run the tool and read the output.
"""


def _served_folder(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "README.md").write_text(README, encoding="utf-8")
    for n in range(1, 4):
        (root / "src" / f"module{n}.py").write_text(f"VALUE = {n}\n", encoding="utf-8")
        (root / "docs" / f"note{n}.md").write_text(f"# Note {n}\n", encoding="utf-8")
        (root / f"data{n}.json").write_text(f'{{"n": {n}}}\n', encoding="utf-8")
    (root / "src" / "app.js").write_text("export const ready = true;\n", encoding="utf-8")


def _free_port() -> int:
    """A port to start the server's search from; the banner says where it went."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_overview_labels_start_on_the_tab_label_at_every_width(tmp_path: Path) -> None:
    chrome = require_chrome()
    node = require_node()
    root = tmp_path / "served"
    _served_folder(root)
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_CACHE_DIR"] = str(tmp_path / "cache")
    env["METABROWSER_CONFIG_DIR"] = str(tmp_path / "config")
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    # --exit-on-eof: closing stdin stops the server however this test ends.
    server = subprocess.Popen(
        [str(_METAB), str(root), "--no-open", "--port", str(_free_port()), "--exit-on-eof"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        banner = read_line(server)
        match = _SERVING_LINE.match(banner)
        assert match is not None, f"not a banner: {banner!r}"
        result = subprocess.run(
            [
                node,
                str(DOM / "folder-overview-alignment-chrome.mjs"),
                f"http://127.0.0.1:{match.group(1)}",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=_MEASURE_TIMEOUT_S,
            env={**os.environ, "CHROME_BIN": chrome},
        )
    finally:
        assert server.stdin is not None
        server.stdin.close()
        # Closed here, so ``communicate`` must not flush it: Python 3.12 and 3.13 raise
        # ``ValueError`` for a flush of a closed stdin, which 3.14 ignores.
        server.stdin = None
        try:
            server.communicate(timeout=_STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate(timeout=_STOP_TIMEOUT_S)
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == "folder overview alignment: 30 checks passed\n"
