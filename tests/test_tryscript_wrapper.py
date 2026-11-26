"""``devtools/tryscript.sh``: tryscript in the goldens' environment, whatever the caller's.

The Makefile's ``TRYSCRIPT`` is this script, and so is the command a developer types in a
shell, so neither the caller's environment nor the directory the shell is in may change
what a golden sees.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tests.required_tools import require_node

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "devtools" / "tryscript.sh"
# A stand-in for tryscript that prints each argument it was given, then its environment.
_ECHO = """#!/bin/sh
for argument in "$@"; do printf 'argument=%s\\n' "$argument"; done
env
"""
# What a developer's shell or a cloud container may export that a golden must not see.
_CALLERS = {
    "UV_NATIVE_TLS": "true",
    "METABROWSER_CACHE_RESERVE_MB": "5",
    "METABROWSER_EVENT_LOG": "1",
    "METABROWSER_NETWORK_PROBE": "example.org:443",
    "METABROWSER_SLOW_SERVER_MS": "1",
}


def _checkout(tmp_path: Path) -> Path:
    """A checkout holding the script, a stand-in tryscript, and the stand-in gh's folder."""

    root = tmp_path / "checkout"
    (root / "devtools").mkdir(parents=True)
    shutil.copy2(SCRIPT, root / "devtools" / "tryscript.sh")
    (root / "tests" / "no-real-gh").mkdir(parents=True)
    echo = root / "node_modules" / ".bin" / "tryscript"
    echo.parent.mkdir(parents=True)
    echo.write_text(_ECHO, encoding="utf-8")
    echo.chmod(0o755)
    return root


def _run(
    root: Path, cwd: Path, extra: dict[str, str], *arguments: str
) -> tuple[list[str], dict[str, str]]:
    environment = {"PATH": os.environ["PATH"], **extra}
    completed = subprocess.run(
        [str(root / "devtools" / "tryscript.sh"), *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    given = [
        line.removeprefix("argument=")
        for line in completed.stdout.splitlines()
        if line.startswith("argument=")
    ]
    seen = dict(
        line.split("=", 1)
        for line in completed.stdout.splitlines()
        if "=" in line and not line.startswith("argument=")
    )
    return given, seen


def _golden_facing(seen: dict[str, str]) -> dict[str, str]:
    return {name: value for name, value in seen.items() if name.startswith(("METABROWSER_", "UV_"))}


def test_the_callers_environment_does_not_reach_a_golden(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    arguments = ("run", "--update", "a golden with spaces.tryscript.md")

    given, plain = _run(root, root, {}, *arguments)
    given_elsewhere, crowded = _run(root, elsewhere, _CALLERS, *arguments)

    assert given == given_elsewhere == list(arguments)
    assert _golden_facing(crowded) == _golden_facing(plain)
    assert not {"UV_NATIVE_TLS", "METABROWSER_CACHE_RESERVE_MB"} & set(crowded)
    # The stand-in gh's folder is first on PATH, from whatever directory the shell is in.
    assert crowded["PATH"].split(os.pathsep)[0] == str(root / "tests" / "no-real-gh")


def test_a_checkout_without_tryscript_says_to_install(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    (root / "node_modules" / ".bin" / "tryscript").unlink()

    completed = subprocess.run(
        [str(root / "devtools" / "tryscript.sh"), "run"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 127
    assert "make install" in completed.stderr


def test_a_golden_passes_from_a_shell_outside_the_checkout(tmp_path: Path) -> None:
    """The repository's own script and tryscript, with the caller's variables set."""

    require_node()
    golden = ROOT / "tests" / "golden" / "cli-ui-treemap-not-indexed.tryscript.md"
    completed = subprocess.run(
        [str(SCRIPT), "run", str(golden)],
        cwd=tmp_path,
        env={**os.environ, **_CALLERS},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=50,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert f"PASS {golden}" in completed.stdout
