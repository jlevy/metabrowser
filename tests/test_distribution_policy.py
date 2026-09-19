"""Distribution tooling policy tests."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from devtools.check_distribution import (
    ROOT,
    _check_capability_entry_points,
    _check_project_metadata,
    _project_capability_entry_points,
    _smoke_install,
    _smoke_installed_capabilities,
)

EXAMPLE_ENTRY_POINTS = {
    "example": "example_package.capabilities:build_capabilities",
}


def _materialize_browser_evidence(
    python_command: list[str],
    *,
    module_source: str = (
        "export function parseWidget(value) {\n"
        "  return value.name === 'accepted'\n"
        "    ? { ok: true, value }\n"
        "    : { ok: false, error: 'invalid widget' };\n"
        "}\n"
    ),
) -> Path:
    script_index = python_command.index("-c") + 1
    evidence_root = Path(python_command[script_index + 1])
    module_path = evidence_root / "installed-parser.mjs"
    corpus_path = evidence_root / "installed-corpus.json"
    descriptor_path = evidence_root / "descriptors.json"
    module_path.write_text(module_source, encoding="utf-8")
    corpus_path.write_text(
        json.dumps(
            {
                "base_records": {"widget": {"name": "accepted"}},
                "cases": [
                    {
                        "name": "valid-widget",
                        "record": "widget",
                        "changes": [],
                        "expect": "valid",
                    },
                    {
                        "name": "invalid-widget",
                        "record": "widget",
                        "changes": [{"path": ["name"], "value": ""}],
                        "expect": "invalid",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    descriptor_path.write_text(
        json.dumps(
            [
                {
                    "contract_id": "org.example.widgets:Widget/v1",
                    "module_path": str(module_path),
                    "export_name": "parseWidget",
                    "corpus_path": str(corpus_path),
                    "record_selectors": ["widget"],
                    "expected_case_count": 2,
                }
            ]
        ),
        encoding="utf-8",
    )
    return descriptor_path


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


def test_wheel_metadata_declares_at_least_one_installed_capability_factory() -> None:
    _check_capability_entry_points(
        b"[metabrowser.capabilities.v1]\n"
        b"example = example_package.capabilities:build_capabilities\n",
        EXAMPLE_ENTRY_POINTS,
    )


def test_wheel_metadata_rejects_empty_capability_factory_group() -> None:
    with pytest.raises(RuntimeError, match="must not be empty"):
        _check_capability_entry_points(b"[metabrowser.capabilities.v1]\n", EXAMPLE_ENTRY_POINTS)


def test_wheel_metadata_rejects_a_provider_omitted_from_project_metadata() -> None:
    expected = {
        **EXAMPLE_ENTRY_POINTS,
        "second": "example_package.capabilities:build_second_capabilities",
    }

    with pytest.raises(RuntimeError, match=r"missing.*second"):
        _check_capability_entry_points(
            b"[metabrowser.capabilities.v1]\n"
            b"example = example_package.capabilities:build_capabilities\n",
            expected,
        )


def test_project_capability_authority_is_nonempty_and_generic() -> None:
    entry_points = _project_capability_entry_points()

    assert entry_points
    assert all(entry_points)
    assert all(isinstance(target, str) and target for target in entry_points.values())


def test_distribution_capability_gate_has_no_hosted_review_allowlist() -> None:
    source = (ROOT / "devtools" / "check_distribution.py").read_text(encoding="utf-8")

    assert "EXPECTED_CAPABILITY_ENTRY_POINTS" not in source
    assert "HOSTED_REVIEW_SCHEMA_ASSETS" not in source
    assert "data/hosted-review-format" not in source
    assert "builtin_plugins.hosted_review" not in source
    assert "len(capabilities.contracts) == 16" not in source


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
    assert "discover_capability_sets()" not in python_script
    assert "validate_installed_evidence" not in python_script
    assert [command[-2:] for command in commands if command[-1] == "--version"] == [
        ["metab", "--version"],
        ["metabrowser", "--version"],
    ]
    assert commands[-1][-2:] == [str(ROOT / "tests" / "manual-fixtures"), "--check-api"]
    assert all(call.kwargs["cwd"] == ROOT for call in run.call_args_list)


def test_wheel_and_sdist_run_the_same_installed_capability_evidence_smoke() -> None:
    artifacts = [
        Path("/tmp/metabrowser-test.whl"),
        Path("/tmp/metabrowser-test.tar.gz"),
    ]

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "node":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="artifact browser evidence OK (1 parser(s), 2 cases)\n",
                stderr="",
            )
        _materialize_browser_evidence(command)
        return subprocess.CompletedProcess(command, 0, stdout="0.1.0\n", stderr="")

    with patch("devtools.check_distribution.subprocess.run", side_effect=fake_run) as run:
        for artifact in artifacts:
            _smoke_installed_capabilities(artifact, EXAMPLE_ENTRY_POINTS)

    commands = [call.args[0] for call in run.call_args_list]
    assert len(commands) == 4
    python_commands = [command for command in commands if command[0] == "uv"]
    browser_commands = [command for command in commands if command[0] == "node"]
    assert len(python_commands) == 2
    assert len(browser_commands) == 2
    scripts = [command[command.index("-c") + 1] for command in python_commands]
    assert scripts[0] == scripts[1]
    assert all(command[command.index("python") + 1] == "-I" for command in python_commands)
    assert [command[command.index("--with") + 1] for command in python_commands] == [
        str(artifact) for artifact in artifacts
    ]
    assert all(
        command[1:3] == ["--experimental-vm-modules", "--no-warnings"]
        for command in browser_commands
    )
    assert all(
        command[-2] == str(ROOT / "devtools" / "artifact-contract-browser-check.mjs")
        for command in browser_commands
    )
    python_script = scripts[0]
    assert "discover_capability_sets()" in python_script
    assert "validate_installed_evidence(build_installed_registries(discovery))" in python_script
    assert "provider.capabilities.artifact_contracts" in python_script
    assert "provider.capabilities.resource_profiles" in python_script
    assert '("frontmatter_format", "jsonschema", "softschema")' in python_script
    assert "expected_provider_ids" in python_script
    assert "actual_provider_ids" in python_script
    assert "assert " not in python_script
    assert "hosted_review" not in python_script
    assert "hosted-review-format" not in python_script
    assert "change_request" not in python_script
    assert all(call.kwargs["cwd"] == ROOT for call in run.call_args_list)


@pytest.mark.parametrize(
    "artifact",
    [
        Path("/tmp/metabrowser-test.whl"),
        Path("/tmp/metabrowser-test.tar.gz"),
    ],
)
def test_installed_artifact_browser_evidence_rejects_node_imports(artifact: Path) -> None:
    real_run = subprocess.run
    node_only_module = (
        'import fs from "node:fs";\n'
        "export function parseWidget(value) {\n"
        "  return fs.constants.F_OK === 0 && value.name === 'accepted'\n"
        "    ? { ok: true, value }\n"
        "    : { ok: false, error: 'invalid widget' };\n"
        "}\n"
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "node":
            return real_run(command, **kwargs)  # type: ignore[arg-type]
        _materialize_browser_evidence(command, module_source=node_only_module)
        return subprocess.CompletedProcess(command, 0, stdout="0.1.0\n", stderr="")

    with (
        patch("devtools.check_distribution.subprocess.run", side_effect=fake_run),
        pytest.raises(
            RuntimeError,
            match=rf"{artifact.name}.*self-contained browser ESM; imports are forbidden",
        ),
    ):
        _smoke_installed_capabilities(artifact, EXAMPLE_ENTRY_POINTS)


def test_broken_sdist_capability_evidence_is_fatal_and_visible() -> None:
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
        _smoke_installed_capabilities(sdist, EXAMPLE_ENTRY_POINTS)
