"""The three tiers partition the suite, ``--shard`` partitions a tier, and each tier
marker is held to its meaning (``tests/suite_tiers.py``, ``tests/suite_gates.py``)."""

from __future__ import annotations

import argparse
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.required_tools import require_chrome
from tests.suite_gates import (
    admitted_git_tests,
    misused_tier_marker,
    tiered_admitted_git_test,
    unmarked_chrome_request,
)
from tests.suite_tiers import (
    CHROME_FIXTURE,
    CHROME_MARKER,
    CHROME_TIER,
    PARALLEL_TIER,
    SERIAL_MARKER,
    SERIAL_TIER,
    TIERS,
    Shard,
    dealt,
    parse_shard,
)
from tests.test_suite_gates import MAX_INNER_BOUND_S

ROOT = Path(__file__).resolve().parents[1]
THIS = Path(__file__).relative_to(ROOT)
REASON = "a probe of the serial tier; it measures nothing"


# ── --shard ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("value", "shard"), [("1/1", Shard(1, 1)), (" 2/4 ", Shard(2, 4))])
def test_a_shard_is_i_of_n(value: str, shard: Shard) -> None:
    assert parse_shard(value) == shard
    assert str(shard) == value.strip()


@pytest.mark.parametrize("value", ["0/3", "4/3", "1/0", "3", "a/b", "-1/2", "1/2/3"])
def test_a_shard_outside_1_through_n_is_refused(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="--shard"):
        parse_shard(value)


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_the_shards_of_any_selection_are_disjoint_and_cover_it(count: int) -> None:
    """Every size from none to several rounds of *count*, in any order it is collected."""

    for size in range(4 * count + 3):
        nodeids = [f"tests/test_m{index % 3}.py::test_{index}" for index in range(size)]
        shuffled = random.Random(size).sample(nodeids, len(nodeids))
        parts: list[set[str]] = []
        for index in range(1, count + 1):
            shard = Shard(index, count)
            kept = {
                nodeid for nodeid, keep in zip(nodeids, dealt(nodeids, shard), strict=True) if keep
            }
            # Membership depends on the node IDs, not on the order they arrive in.
            assert kept == {
                nodeid
                for nodeid, keep in zip(shuffled, dealt(shuffled, shard), strict=True)
                if keep
            }
            parts.append(kept)
        assert sum(len(part) for part in parts) == size
        assert set().union(*parts) == set(nodeids)
        assert max(map(len, parts)) - min(map(len, parts)) <= 1


# ── The tier markers' meaning, as pure judgements ──────────────────────────────


def test_a_test_that_asks_for_chrome_has_to_be_in_the_chrome_tier() -> None:
    assert unmarked_chrome_request({CHROME_MARKER}) is None
    refusal = unmarked_chrome_request({SERIAL_MARKER})
    assert refusal is not None and "is not in the Chrome tier" in refusal


def test_the_chrome_marker_comes_from_the_fixture_alone() -> None:
    assert misused_tier_marker({CHROME_MARKER}, [], {CHROME_FIXTURE, "tmp_path"}) is None
    refusal = misused_tier_marker({CHROME_MARKER}, [], {"tmp_path"})
    assert refusal is not None and f"does not use the {CHROME_FIXTURE} fixture" in refusal


def test_a_serial_marker_gives_its_reason() -> None:
    assert misused_tier_marker({SERIAL_MARKER}, [REASON], ()) is None
    for missing in (None, "", "  ", 3):
        refusal = misused_tier_marker({SERIAL_MARKER}, [REASON, missing], ())
        assert refusal is not None and "without a reason" in refusal


def test_no_admitted_git_module_holds_a_tier_marker() -> None:
    listed = admitted_git_tests(ROOT)
    assert listed is not None and "tests/test_refresh_signals.py" in listed
    module = "tests/test_refresh_signals.py"
    assert tiered_admitted_git_test(module, {"timeout"}, listed) is None
    assert tiered_admitted_git_test("tests/test_new.py", {SERIAL_MARKER}, listed) is None
    assert tiered_admitted_git_test(module, {SERIAL_MARKER}, None) is None
    for marker in (SERIAL_MARKER, CHROME_MARKER):
        refusal = tiered_admitted_git_test(module, {marker}, listed)
        assert refusal is not None and f"a {marker} test there" in refusal


# ── The same, in a real session ────────────────────────────────────────────────
# Collected only by the nested runs below, which name ``probe_*`` as their tests.


@pytest.fixture
def _drives_chrome(chrome_profile: Path) -> Path:  # pyright: ignore[reportUnusedFunction]
    return chrome_profile


def probe_a_plain_test() -> None:
    pass


def probe_a_test_on_chrome_profile(chrome_profile: Path) -> None:
    assert chrome_profile.is_dir()


def probe_a_test_whose_fixture_uses_chrome_profile(_drives_chrome: Path) -> None:
    assert _drives_chrome.is_dir()


@pytest.mark.serial(reason=REASON)
def probe_a_serial_test() -> None:
    pass


@pytest.mark.serial(reason=REASON)
def probe_a_serial_test_on_chrome_profile(chrome_profile: Path) -> None:
    assert chrome_profile.is_dir()


@pytest.mark.chrome
def probe_a_test_marked_chrome_by_hand() -> None:
    pass


@pytest.mark.serial
def probe_a_serial_test_without_a_reason() -> None:
    pass


def probe_a_test_that_asks_for_chrome_without_the_fixture() -> None:
    require_chrome()


def _session(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    run = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:sugar"]
    basetemp = tmp_path / f"nested-{len(list(tmp_path.glob('nested-*')))}"
    return subprocess.run(
        [*run, "-o", "python_functions=probe_*", f"--basetemp={basetemp}", *arguments, THIS],
        cwd=ROOT,
        # The probe that asks for Chrome finds one, so that only the gate can fail it.
        env={**os.environ, "CHROME_BIN": "/bin/true"},
        capture_output=True,
        text=True,
        timeout=MAX_INNER_BOUND_S,
        check=False,
    )


def _collected(tmp_path: Path, *arguments: str) -> set[str]:
    completed = _session(tmp_path, "--collect-only", "-q", *arguments)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return set(re.findall(rf"^{re.escape(str(THIS))}::(probe_\w+)$", completed.stdout, re.M))


@pytest.fixture(scope="module")
def tiers(tmp_path_factory: pytest.TempPathFactory) -> dict[str, set[str]]:
    """Every probe, then the probes each tier's ``-m`` expression selects."""

    base = tmp_path_factory.mktemp("tiers")
    return {"": _collected(base)} | {tier: _collected(base, "-m", tier) for tier in TIERS}


def test_the_three_tiers_partition_the_suite(tiers: dict[str, set[str]]) -> None:
    every = tiers[""]
    assert len(every) == 8
    assert sum(len(tiers[tier]) for tier in TIERS) == len(every)
    assert set().union(*(tiers[tier] for tier in TIERS)) == every
    assert tiers[PARALLEL_TIER] == {
        "probe_a_plain_test",
        "probe_a_test_that_asks_for_chrome_without_the_fixture",
    }
    assert tiers[SERIAL_TIER] == {"probe_a_serial_test", "probe_a_serial_test_without_a_reason"}
    # Using chrome_profile, directly or through another fixture, is what makes a test
    # chrome; a serial test that uses it is in the Chrome tier.
    assert tiers[CHROME_TIER] == {
        "probe_a_test_on_chrome_profile",
        "probe_a_test_whose_fixture_uses_chrome_profile",
        "probe_a_serial_test_on_chrome_profile",
        "probe_a_test_marked_chrome_by_hand",
    }


def test_the_shards_of_a_tier_partition_it(tmp_path: Path, tiers: dict[str, set[str]]) -> None:
    """``--shard`` deals what ``-m`` selected, not the whole collection."""

    tier = CHROME_TIER
    parts = [_collected(tmp_path, "-m", tier, f"--shard={index}/3") for index in (1, 2, 3)]
    assert [len(part) for part in parts] == [2, 1, 1]
    assert set().union(*parts) == tiers[tier]


def test_a_shard_outside_its_count_stops_the_session(tmp_path: Path) -> None:
    completed = _session(tmp_path, "--collect-only", "-q", "--shard=3/2")
    assert completed.returncode == 4
    assert "the parts are 1 through 2" in completed.stderr


def test_a_real_session_holds_each_marker_to_its_meaning(tmp_path: Path) -> None:
    completed = _session(tmp_path, "-v")
    report = completed.stdout
    ran = re.findall(rf"^{re.escape(str(THIS))}::(probe_\w+) ([A-Z]+)", report, re.MULTILINE)
    assert dict(ran) == {
        "probe_a_plain_test": "PASSED",
        "probe_a_test_on_chrome_profile": "PASSED",
        "probe_a_test_whose_fixture_uses_chrome_profile": "PASSED",
        "probe_a_serial_test": "PASSED",
        "probe_a_serial_test_on_chrome_profile": "PASSED",
        "probe_a_test_marked_chrome_by_hand": "FAILED",
        "probe_a_serial_test_without_a_reason": "FAILED",
        "probe_a_test_that_asks_for_chrome_without_the_fixture": "FAILED",
    }, report + completed.stderr
    assert f"is marked {CHROME_MARKER} but does not use the {CHROME_FIXTURE} fixture" in report
    assert f"is marked {SERIAL_MARKER} without a reason" in report
    assert "asks for Chrome through require_chrome but is not in the Chrome tier" in report
    assert completed.returncode == 1
