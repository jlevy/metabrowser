"""Structural guardrails for the sealed inventory-provider boundary."""

from __future__ import annotations

import ast
from pathlib import Path

_SOURCE_ROOT = Path(__file__).parents[1] / "src" / "metabrowser"
_PROVIDER_ROOT = _SOURCE_ROOT / "inventory_engine" / "providers"
_FACTORY = _SOURCE_ROOT / "inventory_engine" / "factory.py"


def _modules_imported_by(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_concrete_provider_is_visible_only_to_its_factory() -> None:
    offenders: list[str] = []
    for path in _SOURCE_ROOT.rglob("*.py"):
        if path == _FACTORY or path.is_relative_to(_PROVIDER_ROOT):
            continue
        imported = _modules_imported_by(path)
        if any(module.startswith("metabrowser.inventory_engine.providers") for module in imported):
            offenders.append(str(path.relative_to(_SOURCE_ROOT)))
    assert offenders == []


def test_obsolete_inventory_module_and_singleton_api_are_absent() -> None:
    assert not (_SOURCE_ROOT / "inventory.py").exists()
    forbidden = {
        "InventoryIndex",
        "bind_instance",
        "get_instance",
        "reset_instance_for_tests",
    }
    offenders: list[str] = []
    for path in _SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        if identifiers & forbidden:
            offenders.append(str(path.relative_to(_SOURCE_ROOT)))
    assert offenders == []


def test_python_provider_has_only_the_contract_change_stream() -> None:
    provider_path = _PROVIDER_ROOT / "python_inventory.py"
    tree = ast.parse(
        provider_path.read_text(encoding="utf-8"),
        filename=str(provider_path),
    )
    method_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    assert method_names.isdisjoint(
        {
            "apply_walker_entries",
            "emit_event",
            "is_subscribed",
            "subscribe",
            "subscriber_count",
            "unsubscribe",
        }
    )


def test_only_coordinator_opens_inventory_handles() -> None:
    callers: list[str] = []
    for path in _SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if (
                node.func.attr == "open"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "_backend"
            ):
                callers.append(str(path.relative_to(_SOURCE_ROOT)))
    assert callers == ["inventory_engine/coordinator.py"]
