"""``devtools/check_plugin_deps.py``: each plugin's ``python_requires`` matches its imports.

The check runs in ``make lint-check`` over the real package; these tests pin each rule
on small synthetic trees, and the manifest field's own validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from devtools import check_plugin_deps
from devtools.check_plugin_deps import check, runtime_dependencies, third_party_imports
from metabrowser.plugin_loader.manifest import (
    PLUGIN_SDK_VERSION,
    PluginInfo,
    normalize_distribution,
)

# What `importlib.metadata.packages_distributions()` answers, for the modules used here.
PROVIDERS = {
    "yaml": ["PyYAML"],
    "starlette": ["starlette"],
    "prettyfmt": ["prettyfmt"],
    "ruamel": ["ruamel.yaml", "ruamel.yaml.clib"],
}


def _write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _run(
    tmp_path: Path,
    *,
    core: str = "import starlette\n",
    plugin: str = "",
    declared: list[str] | None = None,
    runtime: set[str] | None = None,
) -> check_plugin_deps.Report:
    return check(
        core_files=[_write(tmp_path / "core.py", core)],
        plugins={"p": ([_write(tmp_path / "p" / "hooks.py", plugin)], declared or [])},
        runtime={"starlette", "pyyaml"} if runtime is None else runtime,
        providers=PROVIDERS,
    )


def test_imports_count_inside_functions_but_not_under_type_checking(tmp_path: Path) -> None:
    source = (
        "from __future__ import annotations\n"
        "import json, os.path\n"
        "from typing import TYPE_CHECKING\n"
        "from . import sibling\n"
        "from metabrowser.server import app\n"
        "if TYPE_CHECKING:\n"
        "    import prettyfmt\n"
        "else:\n"
        "    import ruamel.yaml\n"
        "def f():\n"
        "    from yaml import safe_load\n"
    )
    assert third_party_imports([_write(tmp_path / "a.py", source)]) == {"ruamel", "yaml"}


def test_a_plugin_whose_declarations_match_its_imports_passes(tmp_path: Path) -> None:
    report = _run(tmp_path, plugin="import yaml\n", declared=["PyYAML"])
    assert report.problems == []
    assert report.plugin_only == {"pyyaml": ["p"]}


def test_a_package_core_imports_too_is_not_plugin_only(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        core="import starlette, yaml\n",
        plugin="import yaml\n",
        declared=["pyyaml"],
    )
    assert report.problems == []
    assert report.plugin_only == {}


def test_an_undeclared_import_fails(tmp_path: Path) -> None:
    report = _run(tmp_path, core="import starlette, yaml\n", plugin="import yaml\n")
    assert report.problems == [
        "plugin p imports yaml but does not declare pyyaml in python_requires"
    ]


def test_a_declaration_the_plugin_does_not_import_fails(tmp_path: Path) -> None:
    report = _run(tmp_path, core="import starlette, yaml\n", declared=["pyyaml"])
    assert report.problems == ["plugin p declares pyyaml but does not import it"]


def test_a_declaration_outside_the_runtime_list_fails(tmp_path: Path) -> None:
    report = _run(tmp_path, plugin="import prettyfmt\n", declared=["prettyfmt"])
    assert "plugin p declares prettyfmt, which is not a runtime dependency" in report.problems


def test_a_runtime_dependency_nothing_imports_fails(tmp_path: Path) -> None:
    report = _run(tmp_path, runtime={"starlette", "pyyaml", "psutil"})
    assert report.problems == [
        "runtime dependency psutil is imported by neither core nor any plugin",
        "runtime dependency pyyaml is imported by neither core nor any plugin",
    ]


def test_core_importing_a_package_outside_the_runtime_list_fails(tmp_path: Path) -> None:
    report = _run(tmp_path, core="import starlette, prettyfmt\n", runtime={"starlette"})
    assert report.problems == [
        "core imports prettyfmt (prettyfmt), which is not a runtime dependency"
    ]


def test_a_namespace_module_resolves_to_the_runtime_distribution(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        plugin="import ruamel.yaml\n",
        declared=["ruamel.yaml"],
        runtime={"starlette", "ruamel-yaml"},
    )
    assert report.problems == []


def test_a_module_no_distribution_provides_fails(tmp_path: Path) -> None:
    report = _run(tmp_path, plugin="import nowhere\n", runtime={"starlette"})
    assert report.problems == ["plugin p imports nowhere, which no installed distribution provides"]


def test_runtime_dependencies_reads_names_from_requirements(tmp_path: Path) -> None:
    pyproject = _write(
        tmp_path / "pyproject.toml",
        '[project]\ndependencies = ["ruamel.yaml>=0.19", "PyYAML==6.0", '
        "\"uvicorn[standard]>=0.49; python_version >= '3.11'\"]\n",
    )
    assert runtime_dependencies(pyproject) == {"ruamel-yaml", "pyyaml", "uvicorn"}


def test_the_real_package_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_plugin_deps.main() == 0
    assert "plugin-only: prettyfmt (agents); pypdfium2 (pdf)." in capsys.readouterr().out


# ── The manifest field ───────────────────────────────────────


def test_normalize_distribution_follows_pep_503() -> None:
    assert normalize_distribution("Ruamel_.YAML") == "ruamel-yaml"


def test_python_requires_defaults_to_none() -> None:
    assert PluginInfo(name="p", sdk_version=PLUGIN_SDK_VERSION).python_requires == []


@pytest.mark.parametrize(
    ("names", "message"),
    [
        (["pyyaml>=6"], "is not a distribution name"),
        (["-yaml"], "is not a distribution name"),
        (["PyYAML", "pyyaml"], "more than once"),
    ],
)
def test_python_requires_names_each_distribution_once(names: list[str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        PluginInfo(name="p", sdk_version=PLUGIN_SDK_VERSION, python_requires=names)
