"""The admitted-Git gate skips locally and cannot skip where CI requires a release."""

from __future__ import annotations

import pytest

from tests import admitted_git
from tests.admitted_git import REQUIRE_ADMITTED_GIT_ENV, require_admitted_git


def _detected(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    parsed = admitted_git.parse_git_version(raw)
    monkeypatch.setattr(admitted_git, "detect_git_version", lambda: (parsed, raw))


def test_below_the_floor_skips_when_no_release_is_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(REQUIRE_ADMITTED_GIT_ENV, raising=False)
    _detected(monkeypatch, "git version 2.43.0")
    with pytest.raises(pytest.skip.Exception, match="acquisition floor admits"):
        require_admitted_git()


def test_below_the_floor_fails_when_a_release_is_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(REQUIRE_ADMITTED_GIT_ENV, "2.43.0")
    _detected(monkeypatch, "git version 2.43.0")
    with pytest.raises(pytest.fail.Exception, match="below the acquisition floor"):
        require_admitted_git()


@pytest.mark.parametrize("raw", ["git version 2.50.1", "", "git version 2.43.6"])
def test_a_different_git_than_the_required_release_fails(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv(REQUIRE_ADMITTED_GIT_ENV, "2.43.7")
    _detected(monkeypatch, raw)
    with pytest.raises(pytest.fail.Exception, match="answered"):
        require_admitted_git()


def test_the_required_admitted_release_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REQUIRE_ADMITTED_GIT_ENV, "2.43.7")
    _detected(monkeypatch, "git version 2.43.7")
    assert require_admitted_git() == (2, 43, 7)
