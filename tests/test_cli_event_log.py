"""``metab --event-log``: ROOT is the directory the event log lives in.

``cli-event-log.tryscript.md`` pins the flag through the modes that read a folder; serving
cannot run in a transcript, so what serving is handed is checked here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from click import unstyle
from typer.testing import CliRunner

from metabrowser.cli.event_log_cli import event_log_directory, newest_segment
from metabrowser.cli.main import _app
from metabrowser.errors import CLIError

runner = CliRunner()


def _plain(output: str) -> str:
    """What a person reads of a usage error: no styling, no panel borders, one line of words.

    CI forces a terminal, so Rich styles and boxes the error as it would on one.
    """

    return " ".join(re.sub(r"[│╭╮╰╯─]", " ", unstyle(output)).split())


OLD = "events-20261118T090000Z-p17-000.jsonl"
NEW = "events-20261119T210201Z-p4242-000.jsonl"


@pytest.fixture
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "state"
    events = home / "events"
    events.mkdir(parents=True, mode=0o700)
    for name in (OLD, NEW):
        (events / name).write_text("")
    # What the event log's own tests set, so no served process in a test writes in a home.
    monkeypatch.setenv("METABROWSER_STATE_DIR", str(home))
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    return events


def test_the_directory_is_where_the_log_is_written(state: Path) -> None:
    assert event_log_directory() == state


def test_the_newest_segment_is_the_one_started_last(state: Path) -> None:
    assert newest_segment(state) == NEW
    assert newest_segment(state / "absent") == ""


def test_a_state_directory_with_no_log_is_said_so(tmp_path: Path) -> None:
    environ = {"METABROWSER_STATE_DIR": str(tmp_path / "none")}
    with pytest.raises(CLIError, match="there is no event log at .*events"):
        event_log_directory(environ)


def test_serving_is_handed_the_directory_at_its_newest_segment(
    state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    served: dict[str, Any] = {}
    monkeypatch.setattr(
        "metabrowser.cli.main.run_serve",
        lambda root, **options: served.update(root=root, **options),
    )
    result = runner.invoke(_app, ["--event-log", "--no-open"])
    assert result.exit_code == 0, result.output
    assert (served["root"], served["path"]) == (state, NEW)


def test_a_path_the_command_names_is_kept(state: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    served: dict[str, Any] = {}
    monkeypatch.setattr(
        "metabrowser.cli.main.run_serve",
        lambda root, **options: served.update(root=root, **options),
    )
    result = runner.invoke(_app, ["--event-log", "--no-open", "--path", OLD])
    assert result.exit_code == 0, result.output
    assert served["path"] == OLD


def test_a_root_beside_the_flag_is_refused(state: Path) -> None:
    result = runner.invoke(_app, ["--event-log", str(state)])
    assert result.exit_code == 2
    assert "ROOT is not used with it" in _plain(result.output)


@pytest.mark.parametrize("flag", ["--diff", "--no-serve", "--doctor", "--present", "--recent"])
def test_a_mode_with_no_folder_refuses_the_flag(state: Path, flag: str) -> None:
    arguments = ["--event-log", flag] + (["HEAD"] if flag == "--diff" else [])
    result = runner.invoke(_app, arguments)
    assert result.exit_code == 2, result.output
    assert "--event-log" in _plain(result.output)


def test_the_flag_is_in_the_helps_shared_options() -> None:
    result = runner.invoke(_app, ["--help"], env={"COLUMNS": "200"})
    assert "--event-log" in _plain(result.output)
