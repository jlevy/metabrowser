from __future__ import annotations

import importlib.metadata
import json
import sys
from collections.abc import Callable, Generator
from types import ModuleType
from typing import Any, cast

import pytest

from metabrowser.builtin_plugins.hosted_review.contracts import (
    HOSTED_REVIEW_CONTRACTS,
    validate_contract_values,
)
from metabrowser.builtin_plugins.hosted_review.models import RESOURCE_SET_CONTRACT_ID
from metabrowser.plugin_loader.artifact_contracts import (
    CapabilityRegistryError,
    CapabilitySet,
    build_installed_registries,
    get_installed_registries,
    reset_installed_registries_for_tests,
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


@pytest.fixture
def _isolated_installed_registries() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Keep the process-wide installed snapshot out of every other test."""
    reset_installed_registries_for_tests()
    yield
    reset_installed_registries_for_tests()


def _break_one_third_party_entry_point(monkeypatch: pytest.MonkeyPatch) -> Callable[[], int]:
    """Add one unloadable third-party provider and count capability discoveries."""
    real_entry_points = importlib.metadata.entry_points
    installed = tuple(real_entry_points(group=CAPABILITY_ENTRY_POINT_GROUP))
    assert installed, "the built-in capability providers must be installed"
    broken = _entry_point("zz-third-party", "metabrowser_absent_third_party_capabilities")
    discoveries = 0

    def entry_points(**kwargs: object) -> Any:
        nonlocal discoveries
        if kwargs.get("group") == CAPABILITY_ENTRY_POINT_GROUP:
            discoveries += 1
            return [*installed, broken]
        return real_entry_points(**cast(Any, kwargs))

    monkeypatch.setattr(importlib.metadata, "entry_points", entry_points)
    return lambda: discoveries


def _valid_resource_set_record() -> dict[str, Any]:
    """Return one packaged built-in record that validates against its contract."""
    spec = next(
        contract
        for contract in HOSTED_REVIEW_CONTRACTS
        if contract.contract_id == RESOURCE_SET_CONTRACT_ID
    )
    corpus = cast(dict[str, Any], json.loads(spec.corpus.payload))
    return cast(dict[str, Any], corpus["base_records"]["resource_set"])


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


@pytest.mark.usefixtures("_isolated_installed_registries")
def test_a_broken_third_party_provider_is_an_installation_error_not_a_record_defect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _valid_resource_set_record()
    healthy = validate_contract_values(RESOURCE_SET_CONTRACT_ID, record)
    assert healthy.semantic.ok, healthy.semantic.errors

    _break_one_third_party_entry_point(monkeypatch)
    reset_installed_registries_for_tests()

    with pytest.raises(CapabilityRegistryError, match="capability discovery failed"):
        validate_contract_values(RESOURCE_SET_CONTRACT_ID, record)
    with pytest.raises(CapabilityRegistryError, match="capability discovery failed") as installed:
        get_installed_registries()
    # A record-level validator reports a defect of its input by raising ValueError.
    # An installation failure is not such a defect, so it must not be a ValueError.
    assert not isinstance(installed.value, ValueError)


@pytest.mark.usefixtures("_isolated_installed_registries")
def test_a_failed_capability_installation_is_discovered_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discoveries = _break_one_third_party_entry_point(monkeypatch)
    reset_installed_registries_for_tests()

    for _ in range(5):
        with pytest.raises(CapabilityRegistryError, match="capability discovery failed"):
            get_installed_registries()

    assert discoveries() == 1
