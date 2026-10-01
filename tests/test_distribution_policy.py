"""Distribution tooling policy tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from devtools.check_distribution import (
    ROOT,
    _check_project_metadata,
    _smoke_install,
    _smoke_installed_contracts,
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


def test_wheel_smoke_commands_isolate_python_and_validate_versions() -> None:
    wheel = Path("/tmp/metabrowser-test.whl")

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        output = ""
        if "-c" in command:
            output = "0.1.0\n"
        elif command[-1] == "--version":
            output = f"{command[-2]} 0.1.0\n"
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    poisoned = {
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONHOME": "/tmp/not-a-python-home",
        "PYTHONOPTIMIZE": "1",
    }
    with (
        patch.dict(os.environ, poisoned),
        patch("devtools.check_distribution.subprocess.run", side_effect=fake_run) as run,
    ):
        _smoke_install(wheel)

    commands = [call.args[0] for call in run.call_args_list]
    expected_prefix = ["uv", "--config-file", str(ROOT / "uv.toml"), "run"]
    assert len(commands) == 7
    assert all(command[:4] == expected_prefix for command in commands)
    python_command = commands[0]
    python_script = python_command[python_command.index("-c") + 1]
    assert python_command[python_command.index("python") + 1] == "-I"
    assert "assert " not in python_script
    for call in run.call_args_list:
        subprocess_env = call.kwargs["env"]
        assert all(name not in subprocess_env for name in poisoned)
    assert "_require(" in python_script
    assert "metabrowser.__version__" in python_script
    assert "load_file_type_registry()" in python_script
    assert "discover_plugins()" in python_script
    assert "render_kpress_view(" in python_script
    assert "validate_installed_evidence" not in python_script
    assert [command[-2:] for command in commands if command[-1] == "--version"] == [
        ["metab", "--version"],
        ["metabrowser", "--version"],
    ]
    assert commands[-1][-2:] == [str(ROOT / "tests" / "manual-fixtures"), "--check-api"]
    assert all(call.kwargs["cwd"] == ROOT for call in run.call_args_list)


def test_wheel_and_sdist_run_the_same_installed_contract_evidence_smoke() -> None:
    artifacts = [
        Path("/tmp/metabrowser-test.whl"),
        Path("/tmp/metabrowser-test.tar.gz"),
    ]

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout="0.1.0\n", stderr="")

    with patch("devtools.check_distribution.subprocess.run", side_effect=fake_run) as run:
        for artifact in artifacts:
            _smoke_installed_contracts(artifact)

    python_commands = [call.args[0] for call in run.call_args_list]
    assert len(python_commands) == 2
    assert all(command[0] == "uv" for command in python_commands)
    scripts = [command[command.index("-c") + 1] for command in python_commands]
    assert scripts[0] == scripts[1]
    assert all(command[command.index("python") + 1] == "-I" for command in python_commands)
    assert [command[command.index("--with") + 1] for command in python_commands] == [
        str(artifact) for artifact in artifacts
    ]
    python_script = scripts[0]
    assert "validate_installed_evidence(cache_contract_registry())" in python_script
    assert '("frontmatter_format", "jsonschema", "softschema")' in python_script
    assert "assert " not in python_script
    assert all(call.kwargs["cwd"] == ROOT for call in run.call_args_list)


def test_broken_sdist_contract_evidence_is_fatal_and_visible() -> None:
    sdist = Path("/tmp/metabrowser-test.tar.gz")

    def fail_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            1,
            command,
            output="",
            stderr="contract corpus digest does not match packaged evidence",
        )

    with (
        patch("devtools.check_distribution.subprocess.run", side_effect=fail_run),
        pytest.raises(RuntimeError, match=r"metabrowser-test\.tar\.gz.*corpus digest"),
    ):
        _smoke_installed_contracts(sdist)
