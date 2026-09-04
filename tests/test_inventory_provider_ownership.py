"""Structural guardrails for the sealed inventory-provider boundary."""

from __future__ import annotations

import ast
from pathlib import Path

_SOURCE_ROOT = Path(__file__).parents[1] / "src" / "metabrowser"
_PROVIDER_ROOT = _SOURCE_ROOT / "inventory_engine" / "providers"
_FACTORY = _SOURCE_ROOT / "inventory_engine" / "factory.py"
_COORDINATOR = _SOURCE_ROOT / "inventory_engine" / "coordinator.py"
_INVENTORY_STATE_CONSTRUCTORS = frozenset(
    {
        "InventoryCoordinator",
        "InventoryRuntime",
        "PythonInventoryBackend",
        "PythonInventoryHandle",
        "create_inventory_backend",
    }
)


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
    assert offenders == [], (
        f"concrete providers may be imported only by inventory_engine/factory.py: {offenders}"
    )


def test_no_process_global_inventory_state_exists_outside_inventory_engine() -> None:
    """Inventory state is lifespan-owned rather than constructed at module import."""

    offenders: list[str] = []
    for path in _SOURCE_ROOT.rglob("*.py"):
        if path.is_relative_to(_SOURCE_ROOT / "inventory_engine"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for statement in tree.body:
            value: ast.expr | None = None
            if isinstance(statement, ast.Assign | ast.AnnAssign):
                value = statement.value
            if not isinstance(value, ast.Call):
                continue
            function = value.func
            name = (
                function.id
                if isinstance(function, ast.Name)
                else function.attr
                if isinstance(function, ast.Attribute)
                else ""
            )
            if name in _INVENTORY_STATE_CONSTRUCTORS:
                offenders.append(f"{path.relative_to(_SOURCE_ROOT)}:{statement.lineno}")
    assert offenders == [], (
        "inventory state must be constructed by an application lifespan, not at module scope: "
        f"{offenders}"
    )


def test_python_provider_handle_exposes_exactly_the_contract_methods() -> None:
    provider_path = _PROVIDER_ROOT / "python_inventory.py"
    tree = ast.parse(provider_path.read_text(encoding="utf-8"), filename=str(provider_path))
    handle = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PythonInventoryHandle"
    )
    public_methods = {
        node.name
        for node in handle.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    }
    assert public_methods == {"read", "changes", "refresh", "prioritize", "close"}, (
        "PythonInventoryHandle is the sealed provider contract; implementation helpers "
        f"belong on the private store, found {sorted(public_methods)}"
    )


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
    forbidden = {
        "apply_walker_entries",
        "emit_event",
        "is_subscribed",
        "subscribe",
        "subscriber_count",
        "unsubscribe",
    }
    assert method_names.isdisjoint(forbidden), (
        f"the provider must publish only changes(); found {sorted(method_names & forbidden)}"
    )


def test_only_coordinator_opens_inventory_handles() -> None:
    callers: list[str] = []
    for path in _SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        backend_attributes: set[str] = set()
        for function in (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ):
            backend_parameters = {
                argument.arg
                for argument in function.args.args + function.args.kwonlyargs
                if isinstance(argument.annotation, ast.Name)
                and argument.annotation.id == "InventoryBackend"
            }
            for assignment in ast.walk(function):
                if (
                    isinstance(assignment, ast.Assign)
                    and isinstance(assignment.value, ast.Name)
                    and assignment.value.id in backend_parameters
                ):
                    for target in assignment.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                        ):
                            backend_attributes.add(target.attr)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if (
                node.func.attr == "open"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr in backend_attributes
            ):
                callers.append(f"{path.relative_to(_SOURCE_ROOT)}:{node.lineno}")
    assert len(callers) == 1 and callers[0].startswith(
        f"{_COORDINATOR.relative_to(_SOURCE_ROOT)}:"
    ), f"only InventoryCoordinator may open an InventoryBackend handle; found {callers}"
