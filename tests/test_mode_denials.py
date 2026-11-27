"""``tests/mode_denials.py`` skips a test that stages a refusal only where root runs it."""

from __future__ import annotations

import os

import pytest

from tests.mode_denials import MODE_DENIAL_SKIP, modes_deny, require_mode_denials
from tests.suite_gates import STRICT_SKIPS_ENV, refused_skip


def test_root_skips_with_the_reason_that_names_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 0)

    assert not modes_deny()
    with pytest.raises(pytest.skip.Exception) as skipped:
        require_mode_denials()
    assert skipped.value.msg == MODE_DENIAL_SKIP


@pytest.mark.parametrize("euid", [1, 1000, 65534])
def test_any_other_user_runs_the_test(monkeypatch: pytest.MonkeyPatch, euid: int) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: euid)

    assert modes_deny()
    require_mode_denials()


def test_strict_mode_fails_the_skip_where_ci_would_take_it() -> None:
    """CI runs as an ordinary user, so a skip there means the runner became root."""

    assert refused_skip((), MODE_DENIAL_SKIP, {STRICT_SKIPS_ENV: "1"}) is not None
    assert refused_skip((), MODE_DENIAL_SKIP, {}) is None
