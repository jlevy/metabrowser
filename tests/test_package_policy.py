from __future__ import annotations

import pytest

from devtools.npm_policy import _verify_documented_uv_commands, verify_repo_package_policy


def test_repository_package_policy_is_self_consistent() -> None:
    verify_repo_package_policy()


@pytest.mark.parametrize(
    "command",
    (
        "uv add package-name",
        "uv lock --upgrade-package package-name",
        "uv sync --locked",
        "uv run pytest",
    ),
)
def test_documented_uv_commands_cannot_bypass_repository_policy(command: str) -> None:
    with pytest.raises(RuntimeError):
        _verify_documented_uv_commands("docs/example.md", command)


@pytest.mark.parametrize(
    "command",
    (
        "uv --config-file uv.toml add package-name",
        "uv --config-file uv.toml lock --upgrade-package package-name",
        "uv --config-file uv.toml sync --locked",
        "uv run --frozen pytest",
    ),
)
def test_documented_uv_commands_accept_repository_policy(command: str) -> None:
    _verify_documented_uv_commands("docs/example.md", command)
