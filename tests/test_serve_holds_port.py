"""A server holds the port its ``Serving`` line names, from before that line to its exit.

Two servers started together on one ``--port`` each used to find it free, since the search
only probed, and each printed it. One then failed to bind and exited, and the other
answered at the address the first had printed, with its own folder: a reader, or a test
fixture, that followed the first server's line was shown the second server's files
(mb-oru2, mb-a124: ``tests/test_nav_reveal_chrome.py`` starts two servers together, and
lost a nightly run on ``main`` that way). ``listen_on_available_local_port`` in
``metabrowser.server_utils`` takes the port as a listening socket instead, which Uvicorn
then serves on.

So this starts pairs of real servers at the same moment on the same port, and reads each
folder's own file back from the address its server printed. Before, every pair on a
10-core Mac printed one port twice and lost a server.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path

import pytest

from tests.test_nav_metadata_chrome import (
    _BANNER_BUDGET_S,
    _METAB,
    _SERVER_STOP_S,
    _SERVING_BUDGET_S,
    _free_port,
    _log_tail,
    _private,
    _read_port,
    _stop_server,
    _wait_until_serving,
)

# Pairs started, one after another: each is a fresh race for one port.
_PAIRS = 3
pytestmark = pytest.mark.timeout(
    _PAIRS * 2 * (_BANNER_BUDGET_S + _SERVING_BUDGET_S + _SERVER_STOP_S) + 10
)


def _listed_names(port: int) -> list[str]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tree", timeout=10) as response:
        listing = json.load(response)
    return sorted(entry["name"] for entry in listing["tree"])


@pytest.mark.parametrize("pair", range(_PAIRS))
def test_two_servers_started_together_on_one_port_each_serve_their_own_folder(
    pair: int, tmp_path: Path
) -> None:
    port = _free_port()
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    env["METABROWSER_RECORD_RECENT"] = "0"
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    names = ("first", "second")
    logs = [tmp_path / f"{name}.log" for name in names]
    servers: list[subprocess.Popen[str]] = []
    # --exit-on-eof: closing stdin stops a server however this test ends.
    command = [str(_METAB), "--no-open", "--exit-on-eof"]
    try:
        for name, log in zip(names, logs, strict=True):
            folder = tmp_path / name
            folder.mkdir()
            (folder / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
            with log.open("w", encoding="utf-8") as output:
                # Neither is waited for before the next starts: they search together.
                servers.append(
                    subprocess.Popen(
                        [*command, str(folder), "--port", str(port)],
                        stdin=subprocess.PIPE,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        text=True,
                        env={
                            **env,
                            "METABROWSER_CACHE_DIR": str(_private(tmp_path / f"{name}-cache")),
                        },
                        start_new_session=True,
                    )
                )
        ports = []
        for server, log in zip(servers, logs, strict=True):
            announced = _read_port(server, log)
            _wait_until_serving(server, announced, log)
            ports.append(announced)
        tails = [_log_tail(log) for log in logs]
        assert len(set(ports)) == 2, f"both servers printed one port: {tails}"
        for name, announced in zip(names, ports, strict=True):
            assert _listed_names(announced) == [f"{name}.md"], (
                f"the address {name} printed serves another folder: {tails}"
            )
        assert [server.poll() for server in servers] == [None, None], tails
    finally:
        for server in servers:
            _stop_server(server)
