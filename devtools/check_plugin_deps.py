"""Hold each built-in plugin's ``python_requires`` to what its Python code imports.

The built-in plugins ship inside the ``metabrowser`` package today, so every
package they import is a runtime dependency in ``pyproject.toml``. If plugins are
ever moved out of the package, someone has to know which of those dependencies
core needs and which only a plugin does. A list kept in prose would drift, so each
plugin's manifest declares the third-party distributions its own Python files
import, and this check holds the lists to the code.

**The rules.** For every built-in plugin:

- each third-party module its Python imports belongs to a distribution it declares;
- each distribution it declares is one that its Python imports;
- each distribution it declares is a runtime dependency in ``pyproject.toml``.

And for the package as a whole:

- each third-party module core (everything outside ``builtin_plugins/``) imports
  belongs to a runtime dependency;
- each runtime dependency is imported by core or declared by some plugin, so a
  dependency nothing uses cannot sit in the runtime list unnoticed.

An import counts wherever it is written, inside a function too, except under
``if TYPE_CHECKING:``, which never runs. The standard library, ``metabrowser``,
and relative imports are not third-party. A module is mapped to its distribution
by ``importlib.metadata.packages_distributions()`` over the locked environment.

On success it prints the plugin-only distributions, each with the plugins that
declare it: the dependencies core would drop if the plugins left the package.

Run it through ``make lint-check``. ``tests/test_check_plugin_deps.py`` pins
what it finds.
"""

from __future__ import annotations

import ast
import importlib.metadata
import re
import sys
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from metabrowser.plugin_loader.manifest import load_manifest, normalize_distribution

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "metabrowser"
PLUGINS = PACKAGE / "builtin_plugins"

# A requirement's distribution name: what PEP 508 allows before a version, an
# extra, a marker, or a URL.
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


class _Imports(ast.NodeVisitor):
    def __init__(self) -> None:
        self.modules: set[str] = set()

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking(node.test):
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.modules.add(alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            self.modules.add(node.module.split(".")[0])


def third_party_imports(files: Iterable[Path]) -> set[str]:
    """The top-level third-party modules these Python files import at run time."""

    found: set[str] = set()
    for path in files:
        visitor = _Imports()
        visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        found |= visitor.modules
    return {
        module
        for module in found
        if module not in sys.stdlib_module_names and module not in {"__future__", "metabrowser"}
    }


def runtime_dependencies(pyproject: Path) -> set[str]:
    """``[project].dependencies`` from ``pyproject.toml``, normalized."""

    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    names: set[str] = set()
    for requirement in project.get("dependencies", []):
        match = _REQUIREMENT_NAME.match(requirement)
        if match is None:
            raise ValueError(f"cannot read a distribution name from {requirement!r}")
        names.add(normalize_distribution(match.group(1)))
    return names


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    plugin_only: dict[str, list[str]] = field(default_factory=dict)


def _distribution(
    module: str,
    providers: Mapping[str, list[str]],
    runtime: set[str],
    problems: list[str],
    who: str,
) -> str | None:
    candidates = sorted({normalize_distribution(name) for name in providers.get(module, [])})
    if len(candidates) > 1:
        candidates = [name for name in candidates if name in runtime] or candidates
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        problems.append(f"{who} imports {module}, which no installed distribution provides")
    else:
        problems.append(f"{who} imports {module}, which {', '.join(candidates)} all provide")
    return None


def check(
    *,
    core_files: Iterable[Path],
    plugins: Mapping[str, tuple[list[Path], list[str]]],
    runtime: set[str],
    providers: Mapping[str, list[str]],
) -> Report:
    """Check the plugins' declarations against their imports and the runtime list.

    ``plugins`` maps each plugin's name to its Python files and its declared
    ``python_requires``.
    """

    report = Report()
    problems = report.problems

    core: set[str] = set()
    for module in sorted(third_party_imports(core_files)):
        distribution = _distribution(module, providers, runtime, problems, "core")
        if distribution is None:
            continue
        core.add(distribution)
        if distribution not in runtime:
            problems.append(
                f"core imports {module} ({distribution}), which is not a runtime dependency"
            )

    declared_anywhere: dict[str, list[str]] = {}
    for name, (files, declared_names) in plugins.items():
        who = f"plugin {name}"
        declared = {normalize_distribution(entry) for entry in declared_names}
        imported: set[str] = set()
        for module in sorted(third_party_imports(files)):
            distribution = _distribution(module, providers, runtime, problems, who)
            if distribution is None:
                continue
            imported.add(distribution)
            if distribution not in declared:
                problems.append(
                    f"{who} imports {module} but does not declare {distribution} in python_requires"
                )
        for distribution in sorted(declared - imported):
            problems.append(f"{who} declares {distribution} but does not import it")
        for distribution in sorted(declared):
            if distribution not in runtime:
                problems.append(f"{who} declares {distribution}, which is not a runtime dependency")
            declared_anywhere.setdefault(distribution, []).append(name)

    for distribution in sorted(runtime - core - set(declared_anywhere)):
        problems.append(
            f"runtime dependency {distribution} is imported by neither core nor any plugin"
        )

    report.plugin_only = {
        distribution: sorted(names)
        for distribution, names in sorted(declared_anywhere.items())
        if distribution not in core
    }
    return report


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _built_in_plugins() -> dict[str, tuple[list[Path], list[str]]]:
    plugins: dict[str, tuple[list[Path], list[str]]] = {}
    for manifest_path in sorted(PLUGINS.glob("*/manifest.toml")):
        manifest = load_manifest(manifest_path)
        plugins[manifest.plugin.name] = (
            _python_files(manifest_path.parent),
            list(manifest.plugin.python_requires),
        )
    return plugins


def main() -> int:
    core_files = [path for path in _python_files(PACKAGE) if PLUGINS not in path.parents]
    plugins = _built_in_plugins()
    report = check(
        core_files=core_files,
        plugins=plugins,
        runtime=runtime_dependencies(ROOT / "pyproject.toml"),
        providers=importlib.metadata.packages_distributions(),
    )
    if report.problems:
        for problem in report.problems:
            print(problem, file=sys.stderr)
        return 1
    plugin_only = (
        "; ".join(
            f"{distribution} ({', '.join(names)})"
            for distribution, names in report.plugin_only.items()
        )
        or "none"
    )
    print(
        f"Plugin dependencies match their imports: {len(plugins)} plugins; "
        f"plugin-only: {plugin_only}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
