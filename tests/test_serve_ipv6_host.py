"""``metab --host`` serves on the address family the host names, at the URL it prints.

The port search made every socket ``AF_INET``, so ``--host ::`` and ``--host ::1`` failed
on every port and the server exited with "No available port", though the ``--host`` help
names ``::`` (mb-vxcq). ``listen_on_available_local_port`` in ``metabrowser.server_utils``
now takes the family from the host.

So this starts real servers and reads a folder's file back from the address each printed:
an IPv6 literal in the brackets a URL needs, a wildcard at loopback. ``::`` listens
dual-stack, so it answers at ``[::1]`` as well as at the ``127.0.0.1`` it prints.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from metabrowser.cli.http_readiness import wait_for_http_ok_then
from tests.ipv6_loopback import require_ipv6_loopback
from tests.test_nav_metadata_chrome import (
    _BANNER_BUDGET_S,
    _METAB,
    _SERVER_STOP_S,
    _SERVING_BUDGET_S,
    _free_port,
    _log_tail,
    _private,
    _stop_server,
)

pytestmark = pytest.mark.timeout(_BANNER_BUDGET_S + _SERVING_BUDGET_S + _SERVER_STOP_S + 10)

_SERVING_URL = re.compile(r"^Serving .* at (http://\S+/view/)", re.MULTILINE)


def _environment(tmp_path: Path) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    env["METABROWSER_RECORD_RECENT"] = "0"
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_CACHE_DIR"] = str(_private(tmp_path / "cache"))
    # A name allowed from outside would hide a bind host the server failed to admit.
    env.pop("METABROWSER_ALLOWED_HOSTS", None)
    return env


def _folder(tmp_path: Path) -> Path:
    folder = tmp_path / "served"
    folder.mkdir()
    (folder / "only.md").write_text("# only\n", encoding="utf-8")
    return folder


def _printed_url(server: subprocess.Popen[str], log: Path) -> str:
    deadline = time.monotonic() + _BANNER_BUDGET_S
    while time.monotonic() < deadline:
        if match := _SERVING_URL.search(log.read_text(encoding="utf-8", errors="replace")):
            return match.group(1)
        if server.poll() is not None:
            pytest.fail(f"the server exited before its banner: {_log_tail(log)!r}")
        time.sleep(0.05)
    pytest.fail(f"no banner within {_BANNER_BUDGET_S:g} s: {_log_tail(log)!r}")


def _listed_names(origin: str) -> list[str]:
    with urllib.request.urlopen(f"{origin}/api/tree", timeout=10) as response:
        listing = json.load(response)
    return sorted(entry["name"] for entry in listing["tree"])


@pytest.mark.parametrize(
    ("host", "printed_host", "also_answers_at"),
    [
        ("::1", "[::1]", ()),
        ("[::1]", "[::1]", ()),
        # The wildcard prints loopback, and is dual-stack: both loopbacks reach it.
        ("::", "127.0.0.1", ("[::1]",)),
        ("0.0.0.0", "127.0.0.1", ()),
        ("127.0.0.1", "127.0.0.1", ()),
        ("localhost", "localhost", ("127.0.0.1",)),
    ],
)
def test_a_server_answers_at_the_url_it_prints_for_its_host(
    host: str, printed_host: str, also_answers_at: tuple[str, ...], tmp_path: Path
) -> None:
    if ":" in host:
        require_ipv6_loopback()
    folder = _folder(tmp_path)
    log = tmp_path / "server.log"
    with log.open("w", encoding="utf-8") as output:
        # --exit-on-eof: closing stdin stops the server however this test ends.
        server = subprocess.Popen(
            [
                str(_METAB),
                "--no-open",
                "--exit-on-eof",
                str(folder),
                "--host",
                host,
                "--port",
                str(_free_port()),
            ],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            env=_environment(tmp_path),
            start_new_session=True,
        )
    try:
        url = _printed_url(server, log)
        printed = urlsplit(url)
        assert printed.netloc == f"{printed_host}:{printed.port}", url
        outcome: list[str] = []
        assert printed.hostname is not None and printed.port is not None
        wait_for_http_ok_then(
            printed.hostname,
            printed.port,
            url,
            on_ready=lambda: outcome.append("ready"),
            on_error=outcome.append,
            is_cancelled=lambda: server.poll() is not None,
            timeout_s=_SERVING_BUDGET_S,
        )
        assert outcome == ["ready"], f"{url} did not answer: {outcome} {_log_tail(log)!r}"
        # urllib sends the URL's own host, brackets and all, as the Host header, so
        # this is also the Host allowlist admitting the address the server printed.
        for reached in (printed_host, *also_answers_at):
            assert _listed_names(f"http://{reached}:{printed.port}") == ["only.md"], reached
        assert server.poll() is None, _log_tail(log)
    finally:
        _stop_server(server)


def test_a_host_this_machine_has_no_address_for_is_refused_by_name(tmp_path: Path) -> None:
    """Not "No available port": no port would have worked.

    ``192.0.2.1`` is in TEST-NET-1 (RFC 5737), which no interface is given.
    """

    done = subprocess.run(
        [str(_METAB), "--no-open", str(_folder(tmp_path)), "--host", "192.0.2.1"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=_environment(tmp_path),
        timeout=_BANNER_BUDGET_S,
        check=False,
    )
    assert done.returncode != 0, done.stdout
    assert "Cannot listen on host '192.0.2.1'" in done.stderr, done.stderr
    assert "No available port" not in done.stderr
    assert "Serving" not in done.stdout
