"""Distribution tooling policy tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from devtools.check_distribution import (
    ROOT,
    VSCODE_LICENSE_PATH,
    _check_project_metadata,
    _check_vscode_license,
    _smoke_install,
)


def test_wheel_metadata_declares_project_license_and_notice() -> None:
    _check_project_metadata(
        b"Metadata-Version: 2.4\n"
        b"License-Expression: AGPL-3.0-or-later\n"
        b"License-File: LICENSE\n"
        b"License-File: NOTICE.md\n"
    )


def test_wheel_metadata_rejects_incomplete_license_declarations() -> None:
    with pytest.raises(RuntimeError, match="License-File: NOTICE.md"):
        _check_project_metadata(
            b"Metadata-Version: 2.4\nLicense-Expression: AGPL-3.0-or-later\nLicense-File: LICENSE\n"
        )


def test_vscode_license_pin_matches_the_bundled_notice() -> None:
    payload = (ROOT / "src" / VSCODE_LICENSE_PATH).read_bytes()
    _check_vscode_license(payload)


def test_vscode_license_pin_rejects_incomplete_text() -> None:
    with pytest.raises(RuntimeError, match="incomplete or modified"):
        _check_vscode_license(b"MIT License\nCopyright Microsoft\n")


def test_wheel_smoke_commands_select_repository_config_and_validate_versions() -> None:
    wheel = Path("/tmp/metabrowser-test.whl")

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        output = ""
        if command[-2] == "-c":
            output = "0.1.0\n"
        elif command[-1] == "--version":
            output = f"{command[-2]} 0.1.0\n"
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    with patch("devtools.check_distribution.subprocess.run", side_effect=fake_run) as run:
        _smoke_install(wheel)

    commands = [call.args[0] for call in run.call_args_list]
    expected_prefix = ["uv", "--config-file", str(ROOT / "uv.toml"), "run"]
    assert len(commands) == 6
    assert all(command[:4] == expected_prefix for command in commands)
    assert [command[-2:] for command in commands if command[-1] == "--version"] == [
        ["metab", "--version"],
        ["metabrowser", "--version"],
    ]
    assert all(call.kwargs["cwd"] == ROOT for call in run.call_args_list)
