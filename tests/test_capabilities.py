"""Capability resolution and the raw sandbox token set it governs."""

from __future__ import annotations

import pytest

from metabrowser.capabilities import (
    DEFAULT_CAPABILITIES,
    Capabilities,
    get_capabilities,
    raw_sandbox_csp,
    resolve_capabilities,
    set_capabilities,
)


def test_defaults_keep_scripts_and_refuse_mutations() -> None:
    caps = resolve_capabilities()
    assert caps == DEFAULT_CAPABILITIES
    assert caps.as_wire() == {"active_content": True, "mutations": False}
    csp = raw_sandbox_csp(active_content=caps.active_content)
    assert csp == "sandbox allow-scripts allow-popups allow-forms allow-downloads"
    assert "allow-same-origin" not in csp
    assert "frame-ancestors" not in csp


def test_untrusted_profile_is_conservative() -> None:
    caps = resolve_capabilities(untrusted=True)
    assert caps == Capabilities(active_content=False, mutations=False)
    csp = raw_sandbox_csp(active_content=caps.active_content)
    assert csp == "sandbox allow-popups allow-forms allow-downloads"
    assert "allow-scripts" not in csp


def test_no_active_content_drops_scripts_only() -> None:
    caps = resolve_capabilities(no_active_content=True)
    assert caps.active_content is False
    assert caps.mutations is False


def test_allow_edits_overrides_untrusted_mutations() -> None:
    caps = resolve_capabilities(untrusted=True, allow_edits=True)
    assert caps == Capabilities(active_content=False, mutations=True)


def test_env_profile_and_individual_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METAB_UNTRUSTED", "1")
    assert resolve_capabilities() == Capabilities(active_content=False, mutations=False)
    monkeypatch.setenv("METAB_ACTIVE_CONTENT", "1")
    assert resolve_capabilities() == Capabilities(active_content=True, mutations=False)
    monkeypatch.setenv("METAB_ALLOW_EDITS", "1")
    assert resolve_capabilities() == Capabilities(active_content=True, mutations=True)
    assert resolve_capabilities(no_active_content=True) == Capabilities(
        active_content=False, mutations=True
    )


def test_cli_no_active_content_beats_env_enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METAB_ACTIVE_CONTENT", "1")
    assert resolve_capabilities(no_active_content=True).active_content is False


def test_unknown_env_values_do_not_enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METAB_UNTRUSTED", "maybe")
    monkeypatch.setenv("METAB_ALLOW_EDITS", "maybe")
    monkeypatch.setenv("METAB_ACTIVE_CONTENT", "maybe")
    assert resolve_capabilities() == DEFAULT_CAPABILITIES


def test_set_capabilities_is_process_global() -> None:
    try:
        set_capabilities(Capabilities(active_content=False, mutations=True))
        assert get_capabilities().mutations is True
    finally:
        set_capabilities(DEFAULT_CAPABILITIES)
