"""The three tiers partition the suite, ``--shard`` partitions a tier, and each tier
marker is held to its meaning (``tests/suite_tiers.py``, ``tests/suite_gates.py``)."""

from __future__ import annotations

import argparse
import logging
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

from devtools.check_goldens import makefile_list, recipe
from devtools.shard_weights import FILES, TESTS, fallback, load
from tests.required_tools import require_chrome
from tests.suite_gates import (
    admitted_git_tests,
    misused_tier_marker,
    tiered_admitted_git_test,
    unmarked_chrome_request,
)
from tests.suite_tiers import (
    BY_FILE,
    BY_TEST,
    CHROME_FIXTURE,
    CHROME_MARKER,
    CHROME_TIER,
    PARALLEL_TIER,
    SERIAL_MARKER,
    SERIAL_TIER,
    TIERS,
    Shard,
    dealt,
    empty_by_selection,
    parse_shard,
)
from tests.suite_workers import encodable
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


def _kept(nodeids: list[str], shard: Shard, by: str, seconds: dict[str, float]) -> set[str]:
    kept = dealt(nodeids, shard, by, seconds)
    return {nodeid for nodeid, keep in zip(nodeids, kept, strict=True) if keep}


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_the_shards_of_any_selection_are_disjoint_and_cover_it(count: int) -> None:
    """Every size from none to several rounds of *count*, in any order it is collected,
    with some tests measured, one of them long, and some not."""

    for size in range(4 * count + 3):
        rng = random.Random(size)
        nodeids = [f"tests/test_m{index % 3}.py::test_{index}" for index in range(size)]
        seconds = {nodeid: rng.choice([0.5, 3.0, 94.0]) for nodeid in nodeids[::2]}
        shuffled = rng.sample(nodeids, len(nodeids))
        shards = [Shard(index, count) for index in range(1, count + 1)]
        parts = [_kept(nodeids, shard, BY_TEST, seconds) for shard in shards]
        # Membership depends on the node IDs and their seconds, not on the order they
        # arrive in.
        assert parts == [_kept(shuffled, shard, BY_TEST, seconds) for shard in shards]
        assert sum(len(part) for part in parts) == size
        assert set().union(*parts) == set(nodeids)
        # An unmeasured test weighs what the measured ones' median does.
        weights = dict.fromkeys(nodeids, fallback(nodeids, seconds)) | seconds
        loads = [sum(weights[nodeid] for nodeid in part) for part in parts]
        assert max(loads) <= sum(loads) / count + max(weights.values(), default=0.0) + 1e-9


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_the_shards_by_file_are_disjoint_whole_files_and_cover_the_selection(count: int) -> None:
    """Each file in one part, whatever the order; the parts balanced to a file's time."""

    rng = random.Random(count)
    nodeids = [
        f"tests/test_m{module}.py::test_{index}"
        for module in range(17)
        for index in range(rng.randint(1, 9))
    ]
    files = sorted({nodeid.split("::")[0] for nodeid in nodeids})
    # A file's time is not its count of tests: the weights say, and two files have none.
    seconds = {name: rng.choice([0.2, 5.0, 51.0]) for name in files[2:]}
    shuffled = rng.sample(nodeids, len(nodeids))
    shards = [Shard(index, count) for index in range(1, count + 1)]
    parts = [_kept(nodeids, shard, BY_FILE, seconds) for shard in shards]
    assert parts == [_kept(shuffled, shard, BY_FILE, seconds) for shard in shards]
    assert sum(len(part) for part in parts) == len(nodeids)
    assert set().union(*parts) == set(nodeids)
    for name in files:
        assert sum(any(nodeid.startswith(f"{name}::") for nodeid in part) for part in parts) == 1
    weights = dict.fromkeys(files, fallback(files, seconds)) | seconds
    loads = [
        sum(weights[name] for name in {nodeid.split("::")[0] for nodeid in part}) for part in parts
    ]
    assert max(loads) <= sum(loads) / count + max(weights.values()) + 1e-9


def test_a_tier_is_dealt_by_the_seconds_measured_for_its_tests_and_files() -> None:
    """With no seconds passed, the committed weights: the tests table, or by file the files."""

    tests, files = load(TESTS), load(FILES)
    longest = max(tests, key=lambda nodeid: tests[nodeid])
    nodeids = sorted(tests)
    alone = _kept(nodeids, Shard(1, 4), BY_TEST, tests)
    assert longest in alone
    assert [dealt(nodeids, Shard(index, 4)) for index in (1, 2, 3, 4)] == [
        dealt(nodeids, Shard(index, 4), BY_TEST, tests) for index in (1, 2, 3, 4)
    ]
    modules = [f"{name}::test_it" for name in sorted(files)]
    assert dealt(modules, Shard(2, 2), BY_FILE) == dealt(modules, Shard(2, 2), BY_FILE, files)
    assert dealt(modules, Shard(2, 2), BY_FILE) != dealt(modules, Shard(2, 2), BY_FILE, {})


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


def probe_a_test_that_calls_gh() -> None:
    subprocess.run(["gh", "auth", "status"], capture_output=True, check=False, timeout=10)


def probe_a_test_that_logs_a_name_that_is_not_utf8() -> None:
    logging.getLogger("tests.probe").warning("reran for %s", os.fsdecode(b"calf\xe9.txt"))


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
        # A probe logs a name that is not UTF-8, which pytest prints as its bytes.
        errors="backslashreplace",
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
    assert len(every) == 10
    assert sum(len(tiers[tier]) for tier in TIERS) == len(every)
    assert set().union(*(tiers[tier] for tier in TIERS)) == every
    assert tiers[PARALLEL_TIER] == {
        "probe_a_plain_test",
        "probe_a_test_that_asks_for_chrome_without_the_fixture",
        "probe_a_test_that_calls_gh",
        "probe_a_test_that_logs_a_name_that_is_not_utf8",
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
    assert sorted(len(part) for part in parts) == [1, 1, 2]
    assert sum(len(part) for part in parts) == len(tiers[tier])
    assert set().union(*parts) == tiers[tier]


def test_a_shard_outside_its_count_stops_the_session(tmp_path: Path) -> None:
    completed = _session(tmp_path, "--collect-only", "-q", "--shard=3/2")
    assert completed.returncode == 4
    assert "the parts are 1 through 2" in completed.stderr


@pytest.mark.parametrize("workers", [[], ["-n", "2"]], ids=["one process", "two workers"])
def test_a_real_session_holds_each_marker_to_its_meaning(
    tmp_path: Path, workers: list[str]
) -> None:
    """The gates judge a test where it runs, so they hold on a worker as in one process,
    and the gh guard's summary names a call a worker's test made."""

    completed = _session(tmp_path, "-rA", *workers)
    report = completed.stdout
    ran = re.findall(rf"^([A-Z]+) {re.escape(str(THIS))}::(probe_\w+)", report, re.MULTILINE)
    assert {probe: outcome for outcome, probe in ran} == {
        "probe_a_plain_test": "PASSED",
        "probe_a_test_on_chrome_profile": "PASSED",
        "probe_a_test_whose_fixture_uses_chrome_profile": "PASSED",
        "probe_a_serial_test": "PASSED",
        "probe_a_serial_test_on_chrome_profile": "PASSED",
        "probe_a_test_marked_chrome_by_hand": "FAILED",
        "probe_a_serial_test_without_a_reason": "FAILED",
        "probe_a_test_that_asks_for_chrome_without_the_fixture": "FAILED",
        "probe_a_test_that_calls_gh": "PASSED",
        # A worker sends its report, with the log line it captured, intact.
        "probe_a_test_that_logs_a_name_that_is_not_utf8": "PASSED",
    }, report + completed.stderr
    assert f"is marked {CHROME_MARKER} but does not use the {CHROME_FIXTURE} fixture" in report
    assert f"is marked {SERIAL_MARKER} without a reason" in report
    assert "asks for Chrome through require_chrome but is not in the Chrome tier" in report
    assert (
        "gh guard: 1 gh call(s) reached the failing stand-in, from 1 test(s): "
        f"{THIS}::probe_a_test_that_calls_gh"
    ) in report
    assert completed.returncode == 1


# ── The Makefile's tier targets ────────────────────────────────────────────────


def _makefile_value(makefile: str, name: str) -> str:
    found = re.search(rf"^{name} := (.*)$", makefile, re.MULTILINE)
    assert found is not None, name
    return found.group(1).strip()


def test_make_test_runs_each_tier_by_its_expression_and_the_parallel_ones_on_workers() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    targets = ("test-parallel", "test-serial", "test-chrome", "test-goldens")

    # `make test`, the release gate, runs the whole Chrome tier, slow tests included.
    prerequisites = re.search(r"^test: (.*)$", makefile, re.MULTILINE)
    assert prerequisites is not None and prerequisites.group(1).split() == list(targets)
    names = ("PARALLEL_TIER", "SERIAL_TIER", "CHROME_TIER")
    assert tuple(_makefile_value(makefile, name) for name in names) == TIERS
    workers = "-n $(PYTEST_WORKERS) --dist loadfile"
    assert recipe(makefile, "test-parallel") == (
        f'\t$(PYTEST) -m "$(PARALLEL_TIER)" {workers} --shard-by=file'
    )
    assert recipe(makefile, "test-serial") == '\t$(PYTEST) $(EVERY_TEST) -m "$(SERIAL_TIER)"'
    assert recipe(makefile, "test-chrome") == '\t$(PYTEST) $(EVERY_TEST) -m "$(CHROME_TIER)"'
    assert workers in recipe(makefile, "test-admitted-git")
    assert "$(if $(SHARD),--shard=$(SHARD) --shard-by=file)" in recipe(
        makefile, "test-admitted-git"
    )
    assert "$(if $(SHARD),--shard=$(SHARD))" in " ".join(makefile_list(makefile, "PYTEST"))
    # A CI job calls each target directly, so each installs first and is phony.
    order_only = re.search(r"^([\w -]+): \| install$", makefile, re.MULTILINE)
    phony = re.search(r"^\.PHONY: (.*)$", makefile, re.MULTILINE)
    assert order_only is not None and phony is not None
    assert set(targets) <= set(order_only.group(1).split()) & set(phony.group(1).split())


def test_a_report_s_strings_are_made_encodable_and_nothing_else_changes() -> None:
    name = os.fsdecode(b"calf\xe9.txt")
    report = {"sections": [("Captured log call", f"reran for {name}")], "duration": 0.5}

    assert encodable(report) == {
        "sections": [("Captured log call", "reran for calf\\udce9.txt")],
        "duration": 0.5,
    }
    assert encodable({"nodeid": "tests/test_a.py::test_b", "keywords": {"b": 1}}) == {
        "nodeid": "tests/test_a.py::test_b",
        "keywords": {"b": 1},
    }


# ── A tier that selects no test ────────────────────────────────────────────────


def test_only_a_tier_or_shard_that_deselected_everything_is_excused() -> None:
    assert empty_by_selection(SERIAL_TIER, False, 3)
    assert empty_by_selection(f"  {SERIAL_TIER} ", False, 3)
    assert empty_by_selection("", True, 1)
    assert not empty_by_selection(SERIAL_TIER, False, 0)
    assert not empty_by_selection("serail and not chrome", False, 3)
    assert not empty_by_selection("", False, 3)


@pytest.mark.parametrize(
    ("arguments", "status"),
    [
        # The serial tier, with -k leaving it nothing: a tier that holds no test.
        (["-m", SERIAL_TIER, "-k", "probe_a_plain_test"], 0),
        # A shard numbered past what -k left: a shard that holds none.
        (["-k", "probe_a_plain_test", "--shard=3/3"], 0),
        # A misspelt tier still fails.
        (["-m", "serail and not chrome"], 5),
        # So does a run that collected nothing at all.
        (["-m", SERIAL_TIER, "-o", "python_functions=nothing_*"], 5),
    ],
    ids=["empty tier", "empty shard", "misspelt tier", "nothing collected"],
)
def test_an_empty_tier_passes_and_a_mistaken_selection_does_not(
    tmp_path: Path, arguments: list[str], status: int
) -> None:
    completed = _session(tmp_path, "-q", *arguments)

    assert completed.returncode == status, completed.stdout + completed.stderr
    excused = "selects no test here, which a tier may" in completed.stdout
    assert excused == (status == 0), completed.stdout


# ── The ADMITTED_GIT_TESTS gate, in a session ──────────────────────────────────

_MARK_EVERY_TEST_SERIAL = """
import pytest


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.serial(reason="a probe of the admitted-git gate"))
"""


def test_a_serial_test_in_an_admitted_git_module_fails_in_a_real_session(tmp_path: Path) -> None:
    """The gate reads the real list, so a plugin marks a listed module's test ``serial``."""

    (tmp_path / "mark_every_test_serial.py").write_text(_MARK_EVERY_TEST_SERIAL, encoding="utf-8")
    module = "tests/test_admitted_git_gate.py"
    assert module in (admitted_git_tests(ROOT) or ())
    session = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:sugar"]
    probe = ["-p", "mark_every_test_serial", f"--basetemp={tmp_path / 'nested'}", "-rf"]
    completed = subprocess.run(
        [*session, *probe, "-k", "the_required_admitted_release_passes", module],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path), str(ROOT)])},
        capture_output=True,
        text=True,
        timeout=MAX_INNER_BOUND_S,
        check=False,
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert f"{module} is in ADMITTED_GIT_TESTS" in completed.stdout
    assert "a serial test there would not have the machine to itself" in completed.stdout
