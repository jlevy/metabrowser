from __future__ import annotations

from devtools.npm_policy import verify_repo_package_policy


def test_repository_package_policy_is_self_consistent() -> None:
    verify_repo_package_policy()
