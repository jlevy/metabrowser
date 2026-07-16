"""Distribution tooling policy tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from devtools.check_distribution import ROOT, _smoke_install


def test_wheel_smoke_commands_select_the_repository_uv_config() -> None:
    wheel = Path("/tmp/metabrowser-test.whl")
    with patch("devtools.check_distribution.subprocess.run") as run:
        _smoke_install(wheel)

    commands = [call.args[0] for call in run.call_args_list]
    expected_prefix = ["uv", "--config-file", str(ROOT / "uv.toml"), "run"]
    assert len(commands) == 4
    assert all(command[:4] == expected_prefix for command in commands)
    assert all(call.kwargs["cwd"] == ROOT for call in run.call_args_list)
