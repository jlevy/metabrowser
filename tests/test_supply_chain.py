from __future__ import annotations

import json
from pathlib import Path

import pytest

from devtools.check_supply_chain import verify_supply_chain


def _write_repository(root: Path) -> None:
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".npmrc").write_text(
        "engine-strict=true\nignore-scripts=true\nmin-release-age=14\n"
        "package-lock=true\nsave-exact=true\n",
        encoding="utf-8",
    )
    package = {
        "private": True,
        "engines": {"node": ">=24 <25", "npm": ">=11.10.0 <12"},
        "devDependencies": {"example": "1.2.3"},
        "peerDependencies": {"example-peer": ">=1 <2"},
    }
    lock = {
        "packages": {
            "": {
                "devDependencies": {"example": "1.2.3"},
            },
            "node_modules/example": {
                "version": "1.2.3",
                "resolved": "https://registry.npmjs.org/example/-/example-1.2.3.tgz",
                "integrity": "sha512-example",
            },
        }
    }
    (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
    (root / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (root / ".nvmrc").write_text("24.18.0\n", encoding="utf-8")
    (root / ".node-version").write_text("24.18.0\n", encoding="utf-8")
    (root / "uv.toml").write_text('exclude-newer = "14 days"\n', encoding="utf-8")
    (root / ".github" / "workflows" / "publish.yml").write_text(
        "on:\n  release:\n    types: [published]\n"
        "jobs:\n  publish:\n    environment: pypi\n"
        "    permissions:\n      id-token: write\n"
        "    steps:\n      - uses: actions/checkout@"
        + "a" * 40
        + "\n      - uses: docker://example/image@sha256:"
        + "b" * 64
        + "\n      - run: uv publish --trusted-publishing always\n",
        encoding="utf-8",
    )


def test_repository_supply_chain_policy_is_valid() -> None:
    verify_supply_chain()


def test_accepts_a_minimal_repository(tmp_path: Path) -> None:
    _write_repository(tmp_path)

    verify_supply_chain(tmp_path)


def test_reports_all_npm_errors(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    (tmp_path / ".npmrc").write_text("ignore-scripts=false\n", encoding="utf-8")
    (tmp_path / ".node-version").write_text("23.0.0\n", encoding="utf-8")
    package = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
    package["engines"]["npm"] = ">=11 <12"
    package["devDependencies"]["example"] = "^1.2.3"
    (tmp_path / "package.json").write_text(json.dumps(package), encoding="utf-8")
    lock = json.loads((tmp_path / "package-lock.json").read_text(encoding="utf-8"))
    entry = lock["packages"]["node_modules/example"]
    entry["resolved"] = "https://example.invalid/example.tgz"
    entry["integrity"] = "sha256-example"
    (tmp_path / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(RuntimeError) as error:
        verify_supply_chain(tmp_path)

    message = str(error.value)
    assert ".npmrc is missing required settings" in message
    assert ".nvmrc and .node-version must match" in message
    assert "must require npm >=11.10.0 <12" in message
    assert "devDependencies.example must use an exact version" in message
    assert "must resolve from https://registry.npmjs.org/" in message
    assert "must have sha512 integrity" in message


def test_reports_a_missing_node_version_file(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    (tmp_path / ".nvmrc").unlink()

    with pytest.raises(RuntimeError, match=r"\.nvmrc must exist"):
        verify_supply_chain(tmp_path)


def test_publish_smoke_retries_must_refresh_the_package_index(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    workflow = tmp_path / ".github" / "workflows" / "publish.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8")
        + "      - name: Smoke-test the package from PyPI\n"
        + "        run: uv tool run example@1.2.3 --help\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="post-publish smoke must refresh"):
        verify_supply_chain(tmp_path)


def test_reports_uv_action_and_publish_errors(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    (tmp_path / "uv.toml").write_text('exclude-newer = "7 days"\n', encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "publish.yml").write_text(
        "on:\n  workflow_dispatch:\n  push:\njobs:\n  publish:\n    steps:\n"
        "      - uses: example/actions/nested\n"
        "      - uses: actions/checkout/path@v4\n"
        "      - uses: ./local-action\n"
        "      - uses: docker://example/image:latest\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as error:
        verify_supply_chain(tmp_path)

    message = str(error.value)
    assert "uv.toml must set exclude-newer to 14 days" in message
    assert "GitHub Actions must use full commit SHAs" in message
    assert "docker://example/image:latest" in message
    assert "publish workflow requires uv trusted publishing" in message
    assert "publish workflow must not allow workflow_dispatch" in message
    assert "trusted publishing must run only for published releases" in message
    assert "trusted publishing requires id-token: write" in message
    assert "trusted publishing requires an environment" in message


def _write_admitted_git(root: Path, *, reviewed: str, matrix: str) -> None:
    pin_a, pin_b = "a" * 64, "b" * 64
    (root / "devtools").mkdir()
    (root / "devtools" / "build_admitted_git.sh").write_text(
        f'case "$version" in\n  2.43.7) sha256={pin_a} ;;\n  2.50.1) sha256={pin_b} ;;\nesac\n',
        encoding="utf-8",
    )
    (root / "SUPPLY-CHAIN-SECURITY.md").write_text(
        "| Release | Role | SHA-256 |\n| --- | --- | --- |\n"
        f"| 2.43.7 | Lowest | `{pin_a}` |\n| 2.50.1 | Newest | `{reviewed}` |\n",
        encoding="utf-8",
    )
    (root / ".github" / "workflows" / "ci.yml").write_text(
        f"jobs:\n  admitted-git:\n    strategy:\n      matrix:\n        git: [{matrix}]\n",
        encoding="utf-8",
    )
    gates = {
        "gates": [{"name": "acquisition", "minimum": [2, 43, 7], "newest_patched": [2, 50, 1]}]
    }
    fixtures = root / "tests" / "fixtures" / "repository-cache"
    fixtures.mkdir(parents=True)
    (fixtures / "git-version-gates.json").write_text(json.dumps(gates), encoding="utf-8")


def test_admitted_git_pins_review_matrix_and_floors_agree(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    _write_admitted_git(tmp_path, reviewed="b" * 64, matrix='"2.43.7", "2.50.1"')

    verify_supply_chain(tmp_path)


def test_admitted_git_drift_and_an_untested_floor_are_reported(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    _write_admitted_git(tmp_path, reviewed="c" * 64, matrix='"2.50.1"')

    with pytest.raises(RuntimeError) as error:
        verify_supply_chain(tmp_path)

    message = str(error.value)
    assert "admitted Git table" in message
    assert "must test the acquisition minimum 2.43.7" in message
    assert "newest_patched" not in message
