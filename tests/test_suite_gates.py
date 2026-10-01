"""A missing prerequisite stops the run, and a skip is judged against its tier."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.admitted_git import required_admitted_git
from tests.required_tools import ALLOW_MISSING_TOOLS_ENV, require_git, require_node
from tests.suite_gates import (
    ADMITTED_GIT_SKIP,
    LIVE_DATA_SKIPS,
    LIVE_GITHUB_ENV,
    REQUIRE_MACOS_TIER_ENV,
    STRICT_SKIPS_ENV,
    admitted_git_tests,
    refused_skip,
    unlisted_floor_request,
)

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
TOOLS: list[tuple[Callable[[], str], str]] = [(require_node, "node"), (require_git, "git")]
# The longest bound a test may put on a child process or a polling loop; pyproject.toml
# says why it has to stay under the suite's own timeout.
MAX_INNER_BOUND_S = 50


# ── The Node and Git gate ──────────────────────────────────────────────────────


@pytest.fixture
def empty_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv(ALLOW_MISSING_TOOLS_ENV, raising=False)
    return tmp_path


@pytest.mark.parametrize(("require", "tool"), TOOLS)
def test_a_missing_tool_stops_the_run_and_names_the_opt_out(
    empty_path: Path, require: Callable[[], str], tool: str
) -> None:
    with pytest.raises(
        pytest.exit.Exception, match=f"{ALLOW_MISSING_TOOLS_ENV}={tool} to skip"
    ) as stop:
        require()
    assert stop.value.returncode == 1


@pytest.mark.parametrize(("require", "tool"), TOOLS)
def test_a_missing_tool_skips_only_when_it_is_the_one_allowed(
    empty_path: Path, monkeypatch: pytest.MonkeyPatch, require: Callable[[], str], tool: str
) -> None:
    other = "git" if tool == "node" else "node"
    monkeypatch.setenv(ALLOW_MISSING_TOOLS_ENV, other)
    with pytest.raises(pytest.exit.Exception):
        require()
    monkeypatch.setenv(ALLOW_MISSING_TOOLS_ENV, f"{other}, {tool}")
    with pytest.raises(pytest.skip.Exception, match=f"{tool} is not on PATH"):
        require()


def test_an_unknown_name_in_the_opt_out_is_called_out(
    empty_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ALLOW_MISSING_TOOLS_ENV, "nodejs")
    with pytest.raises(pytest.exit.Exception) as stop:
        require_node()
    assert "names nodejs, which this gate does not know" in str(stop.value)
    assert "the names it takes are git and node" in str(stop.value)


@pytest.mark.parametrize(("require", "tool"), TOOLS)
def test_a_tool_on_path_is_returned_even_where_missing_is_allowed(
    empty_path: Path, monkeypatch: pytest.MonkeyPatch, require: Callable[[], str], tool: str
) -> None:
    executable = empty_path / tool
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv(ALLOW_MISSING_TOOLS_ENV, tool)
    assert require() == str(executable)


def test_no_test_module_looks_a_tool_up_itself() -> None:
    """A private lookup is how a skip comes back, on the machines without the tool.

    CI has both tools, so strict mode there never sees such a skip; only this does.
    ``metab`` and ``gh`` are not this gate's: the console script is found beside the
    interpreter, and only the live tier uses the real ``gh``.
    """

    lookup = re.compile(r"which\(([^)]*)\)")
    offenders = sorted(
        f"{path.name}: {looked_up}"
        for path in TESTS.glob("*.py")
        if path.name != "required_tools.py"
        for looked_up in lookup.findall(path.read_text(encoding="utf-8"))
        if looked_up.strip() not in {'"metab"', '"gh"'}
    )
    assert offenders == []


def test_no_inner_bound_reaches_the_suites_timeout() -> None:
    """A bound that cannot fire before the suite's timeout does nothing.

    A module that raises its own budget with ``pytest.mark.timeout`` records its
    measurement there and is left to it. So is a ``*_fixture.py`` helper, which a
    tryscript golden runs as a script that no pytest timeout covers.
    """

    settings = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    suite = re.search(r"^timeout = (\d+)$", settings, re.MULTILINE)
    assert suite is not None and int(suite.group(1)) > MAX_INNER_BOUND_S
    bound = re.compile(
        r"(?:\btimeout(?:_s)?\s*=\s*|TIMEOUT\w*(?:: Final)?\s*=\s*|monotonic\(\)\s*\+\s*)"
        r"(\d+(?:\.\d+)?)"
    )
    offenders = sorted(
        f"{path.name}: {value}"
        for path in TESTS.glob("*.py")
        if "pytest.mark.timeout(" not in (text := path.read_text(encoding="utf-8"))
        and not re.fullmatch(r"(?!test_)\w+_fixture\.py", path.name)
        for value in bound.findall(text)
        if float(value) > MAX_INNER_BOUND_S
    )
    assert offenders == []


# ── A skip, judged against its tier ────────────────────────────────────────────

NOTHING_SET: dict[str, str] = {}
STRICT = {STRICT_SKIPS_ENV: "1"}


def test_a_macos_tier_test_may_skip_until_the_tier_is_required() -> None:
    assert refused_skip({"macos_tier"}, "needs macOS", NOTHING_SET) is None
    assert refused_skip({"macos_tier"}, "needs macOS", STRICT) is None
    refusal = refused_skip({"macos_tier"}, "needs macOS", {REQUIRE_MACOS_TIER_ENV: "1"})
    assert refusal == f"{REQUIRE_MACOS_TIER_ENV}=1, so a macOS-tier test may not skip: needs macOS"


def test_a_selected_live_tier_may_skip_only_for_todays_data() -> None:
    unselected = f"set {LIVE_GITHUB_ENV}=1 to run"
    assert refused_skip({"live_github"}, unselected, STRICT) is None
    selected = {LIVE_GITHUB_ENV: "1"}
    for data in LIVE_DATA_SKIPS:
        assert refused_skip({"live_github"}, f"pallets/markupsafe {data}", selected) is None
    refusal = refused_skip({"live_github"}, f"{ADMITTED_GIT_SKIP}; found 'git 2.39'", selected)
    assert refusal is not None and "may skip only for what github.com holds today" in refusal


def test_strict_mode_refuses_a_skip_outside_every_tier() -> None:
    assert refused_skip((), "owner-only cache is POSIX-only", NOTHING_SET) is None
    assert refused_skip((), f"{ADMITTED_GIT_SKIP}; found 'git 2.39'", STRICT) is None
    refusal = refused_skip((), "node is not on PATH, and it was allowed", STRICT)
    assert refusal is not None and "belongs to no tier" in refusal


def test_a_module_that_asks_for_the_floor_has_to_be_listed() -> None:
    listed = admitted_git_tests(ROOT)
    assert listed is not None and "tests/test_cache_acquire.py" in listed
    assert unlisted_floor_request("tests/test_cache_acquire.py", (), listed) is None
    assert unlisted_floor_request("tests/test_new.py", {"live_github"}, listed) is None
    assert unlisted_floor_request("tests/test_new.py", (), None) is None
    refusal = unlisted_floor_request("tests/test_new.py", (), listed)
    assert refusal is not None and "is not in ADMITTED_GIT_TESTS" in refusal


# ── The same judgements, in a real session ─────────────────────────────────────
# Collected only by the nested run below, which names ``probe_*`` as its tests.


@pytest.mark.macos_tier
def probe_a_macos_tier_test_that_skips() -> None:
    pytest.skip("the file system is case-sensitive")


@pytest.mark.macos_tier
@pytest.mark.xfail(reason="a known defect", strict=True)
def probe_a_macos_tier_test_that_is_expected_to_fail() -> None:
    raise AssertionError("the known defect")


def probe_a_skip_outside_every_tier() -> None:
    pytest.skip("a reason no tier owns")


def probe_a_skip_the_admitted_git_tier_owns() -> None:
    pytest.skip(f"{ADMITTED_GIT_SKIP}; found 'git version 2.39.5'")


@pytest.mark.live_github
def probe_a_live_test_that_skips_for_todays_data() -> None:
    pytest.skip(f"the repository {LIVE_DATA_SKIPS[0]}")


@pytest.mark.live_github
def probe_a_live_test_that_skips_for_its_machine() -> None:
    pytest.skip(f"{ADMITTED_GIT_SKIP}; found 'git version 2.39.5'")


def probe_a_test_that_asks_for_the_git_floor() -> None:
    required_admitted_git()


def test_a_real_session_applies_every_judgement(tmp_path: Path) -> None:
    """``tests/conftest.py`` registers the hooks, so run a session that goes through it."""

    this = Path(__file__).relative_to(ROOT)
    session = [sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider", "-p", "no:sugar"]
    completed = subprocess.run(
        [*session, "-o", "python_functions=probe_*", f"--basetemp={tmp_path / 'nested'}", this],
        cwd=ROOT,
        env={
            **os.environ,
            STRICT_SKIPS_ENV: "1",
            REQUIRE_MACOS_TIER_ENV: "1",
            LIVE_GITHUB_ENV: "1",
        },
        capture_output=True,
        text=True,
        timeout=MAX_INNER_BOUND_S,
        check=False,
    )
    report = completed.stdout
    ran = re.findall(rf"^{re.escape(str(this))}::(probe_\w+) ([A-Z]+)", report, re.MULTILINE)
    outcomes = dict(ran)
    assert outcomes == {
        "probe_a_macos_tier_test_that_skips": "FAILED",
        "probe_a_macos_tier_test_that_is_expected_to_fail": "XFAIL",
        "probe_a_skip_outside_every_tier": "FAILED",
        "probe_a_skip_the_admitted_git_tier_owns": "SKIPPED",
        "probe_a_live_test_that_skips_for_todays_data": "SKIPPED",
        "probe_a_live_test_that_skips_for_its_machine": "FAILED",
        "probe_a_test_that_asks_for_the_git_floor": "FAILED",
    }, report + completed.stderr
    assert f"{REQUIRE_MACOS_TIER_ENV}=1, so a macOS-tier test may not skip" in report
    assert "this skip belongs to no tier" in report
    assert f"{LIVE_GITHUB_ENV}=1 selected the live tier" in report
    assert f"{this} asks for the Git floor but is not in ADMITTED_GIT_TESTS" in report
    assert completed.returncode == 1
