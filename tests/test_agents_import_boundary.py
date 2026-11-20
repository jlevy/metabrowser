"""The ``agents`` plugin reaches Metabrowser only through its public plugin API.

The plugin ships inside the Metabrowser wheel, but it is written as a plugin author
would write one: a private helper it needs is a gap in ``metabrowser.plugin_api``, and
the fix is an export there, not an import of the private name.
The check parses every module in the package, so a module added later is covered
without touching this test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import metabrowser.builtin_plugins.agents as agents_package

PACKAGE_NAME = "metabrowser.builtin_plugins.agents"
PACKAGE_DIR = Path(agents_package.__file__ or "").parent
ALLOWED_PUBLIC = "metabrowser.plugin_api"


def _imported_modules(tree: ast.AST, module_package: str) -> list[tuple[str, int]]:
    """Return each absolute module the tree imports from, with its line."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = module_package.split(".")
                base = parts[: len(parts) - node.level + 1]
                tail = [node.module] if node.module else []
                found.append((".".join([*base, *tail]), node.lineno))
            elif node.module == "metabrowser":
                # ``from metabrowser import x`` names a top-level export or a submodule.
                found.extend((f"metabrowser.{alias.name}", node.lineno) for alias in node.names)
            elif node.module:
                found.append((node.module, node.lineno))
    return found


def _is_allowed(module: str) -> bool:
    if module != "metabrowser" and not module.startswith("metabrowser."):
        return True
    return module in (ALLOWED_PUBLIC, PACKAGE_NAME) or module.startswith(f"{PACKAGE_NAME}.")


def test_the_package_has_modules_to_check() -> None:
    names = {path.name for path in PACKAGE_DIR.glob("*.py")}
    assert {"adapters.py", "sidekick.py", "model.py"} <= names


def test_every_agents_module_imports_metabrowser_only_through_the_plugin_api() -> None:
    violations: list[str] = []
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        relative = path.relative_to(PACKAGE_DIR)
        parts = [PACKAGE_NAME, *relative.with_suffix("").parts]
        # A module's package is everything before its own name; an ``__init__`` is its
        # directory's package, which this takes the same way.
        module_package = ".".join(parts[:-1])
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module, line in _imported_modules(tree, module_package):
            if not _is_allowed(module):
                violations.append(f"{relative}:{line} imports {module}")
    assert violations == []


def test_the_allowlist_rejects_a_private_core_module() -> None:
    assert not _is_allowed("metabrowser.logutil.parsing")
    assert not _is_allowed("metabrowser.plugin_api_extra")
    assert _is_allowed("metabrowser.plugin_api")
    assert _is_allowed("metabrowser.builtin_plugins.agents.model")
    assert _is_allowed("json")
