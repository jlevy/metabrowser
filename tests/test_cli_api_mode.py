"""Tests for `metab --api`, the wire-parity mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cli.api_cli import run_api
from metabrowser.errors import CLIError


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("hello\n")
    return tmp_path


def test_api_prints_the_route_status_and_json_envelope(root: Path, capsys: Any) -> None:
    run_api(root, route="/api/tree?depth=1", fmt="json")

    out = capsys.readouterr().out
    assert out.startswith("api: /api/tree?depth=1\nstatus: 200\n")
    payload = json.loads(out.split("\n", 2)[2])
    assert isinstance(payload["tree"], list)


def test_api_normalizes_the_sandbox_root(root: Path, capsys: Any) -> None:
    """A transcript must not carry the temporary directory it happened to run in."""

    run_api(root, route="/api/tree?depth=1", fmt="json")

    out = capsys.readouterr().out
    assert str(root) not in out
    assert "<ROOT>" in out


def test_api_renders_yaml_when_asked(root: Path, capsys: Any) -> None:
    run_api(root, route="/api/tree?depth=1", fmt="yaml")

    out = capsys.readouterr().out
    assert "status: 200" in out
    assert "tree:" in out


def test_api_reports_a_failing_status_and_exits_nonzero(root: Path, capsys: Any) -> None:
    """A transcript should be able to assert a failure honestly."""

    with pytest.raises(CLIError):
        run_api(root, route="/api/file?path=missing.md", fmt="json")

    out = capsys.readouterr().out
    assert "status: 404" in out


def test_api_rejects_a_route_outside_the_api_surface(root: Path) -> None:
    with pytest.raises(CLIError, match="must begin with /api/"):
        run_api(root, route="/etc/passwd", fmt="json")


def test_api_passes_the_query_string_through_to_the_route(root: Path, capsys: Any) -> None:
    """The parameters a route parses are exactly what the browser would send.

    This is the gap the parity plan named: a library-level transcript proves the
    model, so a route could accept a parameter the library never sees and stay
    green. Here the filter is applied by the route, and the envelope shows it.
    """

    (root / "notes.txt").write_text("x\n")

    run_api(root, route="/api/tree?depth=1", fmt="json")
    unfiltered = json.loads(capsys.readouterr().out.split("\n", 2)[2])

    run_api(root, route="/api/tree?depth=1&types=.md", fmt="json")
    filtered = json.loads(capsys.readouterr().out.split("\n", 2)[2])

    assert unfiltered.get("filtered") is None
    assert len(unfiltered["tree"]) == 2
    assert filtered["filtered"]["entries"] == 1
    assert len(filtered["tree"]) == 1
