from __future__ import annotations

import importlib.metadata
import sys
from types import ModuleType
from typing import Any, cast

import pytest

from metabrowser.plugin_loader.artifact_contracts import (
    CapabilityRegistryError,
    CapabilitySet,
    build_installed_registries,
)
from metabrowser.plugin_loader.capability_discovery import (
    CAPABILITY_ENTRY_POINT_GROUP,
    discover_capability_sets,
)


def _entry_point(name: str, module_name: str) -> importlib.metadata.EntryPoint:
    return importlib.metadata.EntryPoint(
        name=name,
        value=f"{module_name}:capabilities",
        group=CAPABILITY_ENTRY_POINT_GROUP,
    )


def _install_factory(monkeypatch: pytest.MonkeyPatch, module_name: str, value: object) -> None:
    module = ModuleType(module_name)
    cast(Any, module).capabilities = lambda: value
    monkeypatch.setitem(sys.modules, module_name, module)


def test_capabilities_load_only_from_the_installed_v1_entry_point_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_factory(monkeypatch, "metabrowser_test_capabilities", CapabilitySet())
    entry_point = _entry_point("fixture", "metabrowser_test_capabilities")
    requested_groups: list[str | None] = []

    def entry_points(**kwargs: object) -> list[importlib.metadata.EntryPoint]:
        requested_groups.append(cast(str | None, kwargs.get("group")))
        return [entry_point]

    monkeypatch.setattr(importlib.metadata, "entry_points", entry_points)

    result = discover_capability_sets()

    assert requested_groups == [CAPABILITY_ENTRY_POINT_GROUP]
    assert result.errors == ()
    assert tuple(provider.provider_id for provider in result.providers) == ("fixture",)
    assert result.providers[0].capabilities == CapabilitySet()


def test_duplicate_capability_provider_ids_fail_without_ordered_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_factory(monkeypatch, "metabrowser_test_capabilities_a", CapabilitySet())
    _install_factory(monkeypatch, "metabrowser_test_capabilities_b", CapabilitySet())
    entry_points = [
        _entry_point("duplicate", "metabrowser_test_capabilities_a"),
        _entry_point("duplicate", "metabrowser_test_capabilities_b"),
    ]
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda **_kwargs: entry_points,
    )

    result = discover_capability_sets()

    assert result.providers == ()
    assert len(result.errors) == 1
    assert "duplicate capability provider id 'duplicate'" in result.errors[0]


def test_capability_factory_must_return_a_capability_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_factory(monkeypatch, "metabrowser_test_bad_capabilities", {"contracts": []})
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda **_kwargs: [_entry_point("bad", "metabrowser_test_bad_capabilities")],
    )

    result = discover_capability_sets()

    assert result.providers == ()
    assert len(result.errors) == 1
    assert "must return CapabilitySet" in result.errors[0]
    with pytest.raises(CapabilityRegistryError, match="capability discovery failed"):
        build_installed_registries(result)


def test_capability_factory_rejects_mutable_or_missing_declaration_collections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_values: tuple[object, ...] = (None, [])
    for index, invalid_value in enumerate(invalid_values):
        module_name = f"metabrowser_test_invalid_capabilities_{index}"
        module = ModuleType(module_name)
        cast(Any, module).capabilities = lambda value=invalid_value: CapabilitySet(
            artifact_contracts=cast(Any, value)
        )
        monkeypatch.setitem(sys.modules, module_name, module)
        monkeypatch.setattr(
            importlib.metadata,
            "entry_points",
            lambda module_name=module_name, **_kwargs: [_entry_point("bad-shape", module_name)],
        )

        result = discover_capability_sets()

        assert result.providers == ()
        assert "artifact_contracts must be a tuple" in result.errors[0]
        with pytest.raises(CapabilityRegistryError, match="capability discovery failed"):
            build_installed_registries(result)
