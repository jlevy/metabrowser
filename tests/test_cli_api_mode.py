"""Tests for `metab --api`, the wire-parity mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from metabrowser.cli.api_cli import (  # pyright: ignore[reportPrivateUsage]
    _emit_api_response,
    run_api,
)
from metabrowser.cli.asgi_client import ApiResponse
from metabrowser.cli.main import _app
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


@pytest.mark.parametrize(
    ("fmt", "load"),
    [("json", json.loads), ("yaml", yaml.safe_load)],
)
def test_a_format_asked_for_is_that_document_alone(root: Path, fmt: str, load: Any) -> None:
    """A tool parses stdout, so nothing is printed above the envelope."""

    result = CliRunner().invoke(_app, [str(root), "--api", "/api/tree?depth=1", "--format", fmt])

    assert result.exit_code == 0, result.output
    document = load(result.stdout)
    assert isinstance(document["tree"], list)
    assert not {"api", "status"} & set(document)


def test_no_format_asked_for_is_the_transcript(root: Path) -> None:
    """The form every golden pins: the route and the status come first."""

    result = CliRunner().invoke(_app, [str(root), "--api", "/api/tree?depth=1"])

    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("api: /api/tree?depth=1\nstatus: 200\n{")


def test_a_failing_answer_still_parses_and_exits_nonzero(root: Path, capsys: Any) -> None:
    with pytest.raises(CLIError, match="returned HTTP 404"):
        run_api(root, route="/api/file?path=missing.md", fmt="json", headers=False)

    assert "error" in json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(("fmt", "load"), [("json", json.loads), ("yaml", yaml.safe_load)])
def test_a_body_that_is_not_json_is_one_string(
    root: Path, capsys: Any, fmt: str, load: Any
) -> None:
    with pytest.raises(CLIError, match="returned HTTP 405"):
        run_api(root, route="/api/plugin/github/pull-refresh", fmt=fmt, headers=False)

    assert load(capsys.readouterr().out) == "Method Not Allowed"


def test_work_followed_to_its_end_prints_only_the_status_that_ended_it(
    root: Path, capsys: Any
) -> None:
    """One document: the transcript's two answers would not parse as one."""

    ended = ApiResponse(200, json.dumps({"refreshing": False, "state": "current"}).encode())
    arguments: dict[str, Any] = {
        "fmt": "json",
        "normalize_root": root,
        "after": ("/api/plugin/github/pull", ended),
    }
    started = ApiResponse(202, b'{"status_route": "/api/plugin/github/pull"}')

    _emit_api_response("/api/plugin/github/pull-refresh", started, "skipped", **arguments)
    transcript = capsys.readouterr().out
    assert transcript.startswith("api: /api/plugin/github/pull-refresh\nstatus: 202\n{")
    assert "after: /api/plugin/github/pull\nstatus: 200\n{" in transcript

    _emit_api_response(
        "/api/plugin/github/pull-refresh", started, "skipped", headers=False, **arguments
    )
    assert json.loads(capsys.readouterr().out) == {"refreshing": False, "state": "current"}


def test_an_answer_cut_mid_response_points_only_at_what_was_printed(
    root: Path, capsys: Any
) -> None:
    """With work to follow, one document prints nothing of the first answer."""

    ended = ApiResponse(200, json.dumps({"refreshing": False}).encode())
    cut = ApiResponse(202, b'{"status_ro', incomplete=True)
    arguments: dict[str, Any] = {
        "fmt": "json",
        "normalize_root": root,
        "after": ("/api/plugin/github/pull", ended),
    }

    with pytest.raises(CLIError, match="failed mid-response; the body above is truncated$"):
        _emit_api_response("/api/plugin/github/pull-refresh", cut, "skipped", **arguments)
    assert capsys.readouterr().out.startswith("api: /api/plugin/github/pull-refresh\nstatus: 202\n")

    with pytest.raises(CLIError, match="HTTP 202 and then failed mid-response$"):
        _emit_api_response(
            "/api/plugin/github/pull-refresh", cut, "skipped", headers=False, **arguments
        )
    assert capsys.readouterr().out == ""


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


def test_a_folder_envelope_is_complete_not_pending(root: Path, capsys: Any) -> None:
    """A folder's aggregates come from the inventory, so /api/file must wait for it.

    The sweep that decided which routes wait only ever requested a file, and the
    folder branch returned `state: "pending"` with null aggregates, HTTP 200 and
    exit 0 -- degraded data reported as a clean answer.
    """

    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("a\n")

    run_api(root, route="/api/file?path=docs", fmt="json")

    payload = json.loads(capsys.readouterr().out.split("\n", 2)[2])
    assert payload["kind"] == "folder"
    assert payload["dir"]["state"] == "complete"
    assert payload["dir"]["total_files"] is not None
