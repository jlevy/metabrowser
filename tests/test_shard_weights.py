"""The shard weights: how units are dealt by them, what an unmeasured unit weighs, and how
a refresh reads them from CI's logs (``devtools/shard_weights.py``,
``devtools/refresh_shard_weights.py``)."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest
import yaml

from devtools import refresh_shard_weights, shard_weights
from devtools.check_goldens import makefile_list, recipe
from devtools.refresh_shard_weights import (
    CHROME_JOB,
    JOBS,
    SERIAL_JOB,
    UNIT_JOB,
    RefreshError,
    Samples,
    durations_of,
    refresh,
    render,
)
from devtools.shard_weights import (
    FILES,
    GOLDENS,
    TABLES,
    TESTS,
    UNMEASURED_S,
    WEIGHTS,
    WeightsError,
    fallback,
    load,
    parts,
)

ROOT = Path(__file__).resolve().parents[1]


def _loads(part_of: dict[str, int], weights: dict[str, float], count: int) -> list[float]:
    loads = [0.0] * count
    for name, part in part_of.items():
        loads[part] += weights[name]
    return loads


# ── Dealing ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_the_parts_hold_every_unit_once_whatever_the_order_and_are_bounded(count: int) -> None:
    """From no unit to several rounds of *count*, with weights from even to one giant."""

    for size in range(4 * count + 3):
        rng = random.Random(count * 100 + size)
        seconds = {f"unit-{index}": rng.choice([0.01, 1.0, 7.5, 94.0]) for index in range(size)}
        names = list(seconds)
        part_of = parts(names, count, seconds)

        assert part_of == parts(rng.sample(names, len(names)), count, seconds)
        assert set(part_of) == set(names)
        assert set(part_of.values()) <= set(range(count))
        loads = _loads(part_of, seconds, count)
        # What dealing heaviest first to the lightest part guarantees, whatever the weights.
        assert max(loads) <= sum(loads) / count + max(seconds.values(), default=0.0) + 1e-9


def test_units_go_heaviest_first_to_the_lightest_part_and_ties_to_the_lowest() -> None:
    seconds = {"a": 9.0, "b": 5.0, "c": 4.0, "d": 3.0, "e": 1.0}

    assert parts(seconds, 2, seconds) == {"a": 0, "b": 1, "c": 1, "d": 0, "e": 1}
    # Equal weights fall back to the name, so the parts differ by one unit at most.
    assert parts("dcba", 2, {}) == {"a": 0, "b": 1, "c": 0, "d": 1}
    assert parts(["a", "a", "b"], 1, seconds) == {"a": 0, "b": 0}


def test_one_long_test_no_longer_fills_a_part_with_others() -> None:
    """The case of run 45062416967: a 94 s test among the Chrome tier's, in four parts."""

    seconds = {"long": 94.0} | {f"test-{index:02}": 10.0 for index in range(30)}
    loads = _loads(parts(seconds, 4, seconds), seconds, 4)

    assert sorted(loads) == [94.0, 100.0, 100.0, 100.0]
    # By rank in name order, as before, the long test's part held seven others.
    assert parts(seconds, 4, seconds)["long"] == 0


def test_a_unit_with_no_measurement_weighs_the_median_of_those_dealt_with_it() -> None:
    seconds = {"a": 1.0, "b": 3.0, "c": 20.0, "elsewhere": 500.0}

    assert fallback(["a", "b", "c", "new"], seconds) == 3.0
    assert fallback(["a", "b", "new", "newer"], seconds) == 2.0
    # None dealt here is measured, as with no weights file: every unit weighs the same.
    assert fallback(["new", "newer"], seconds) == UNMEASURED_S
    assert fallback([], seconds) == UNMEASURED_S


def test_new_units_are_spread_over_the_parts_not_piled_on_the_lightest() -> None:
    seconds = {"a": 30.0, "b": 20.0, "c": 4.0, "d": 4.0}
    new = [f"new-{index}" for index in range(6)]

    part_of = parts([*seconds, *new], 2, seconds)

    assert sorted(part_of[name] for name in new) == [0, 0, 0, 1, 1, 1]


# ── The committed file ─────────────────────────────────────────────────────────


def test_a_missing_file_gives_no_seconds_and_a_malformed_one_is_refused(tmp_path: Path) -> None:
    assert load(TESTS, tmp_path / "absent.json") == {}
    good = tmp_path / "good.json"
    good.write_text(json.dumps({TESTS: {"a": 2}, FILES: {}}), encoding="utf-8")
    assert load(TESTS, good) == {"a": 2.0}
    assert load(FILES, good) == load(GOLDENS, good) == {}
    for text in ("{", "[]", json.dumps({TESTS: {"a": "slow"}}), json.dumps({TESTS: [1]})):
        bad = tmp_path / "bad.json"
        bad.write_text(text, encoding="utf-8")
        with pytest.raises(WeightsError, match="does not hold a tests table"):
            load(TESTS, bad)


def test_the_committed_weights_name_their_runs_and_units_that_exist() -> None:
    """The file is what a refresh writes, from runs it names, of units still in the tree."""

    text = WEIGHTS.read_text(encoding="utf-8")
    document = json.loads(text)
    tables = {table: load(table) for table in TABLES}

    assert render(tables, document["source"]["runs"]) == text
    assert document["source"]["runs"]
    for run in document["source"]["runs"]:
        assert isinstance(run["id"], int) and re.fullmatch(r"[0-9a-f]{40}", run["commit"])
    for table in TABLES:
        assert tables[table], table
        assert all(seconds >= 0 for seconds in tables[table].values())
    # A weight for a file that is gone is only unused, but most being gone means the
    # names no longer match what the dealers ask for.
    for table, names in (
        (FILES, list(tables[FILES])),
        (GOLDENS, list(tables[GOLDENS])),
        (TESTS, [name.split("::", 1)[0] for name in tables[TESTS]]),
    ):
        present = sum((ROOT / name).is_file() for name in names)
        assert present >= 0.9 * len(names), table


# ── Reading CI's logs ──────────────────────────────────────────────────────────


def _log(job: str, *lines: str) -> str:
    """Lines as ``gh run view --job <id> --log`` prints them."""

    stamp = "2026-11-22T19:53:01.2268593Z"
    return "".join(f"{job}\tUNKNOWN STEP\t{stamp} {line}\n" for line in lines)


CHROME_LINES = (
    "============== slowest 2 of 2 test files, 105.39 s of test time ==============",
    "94.20s tests/test_files_chrome.py",
    "11.19s tests/test_header_chrome.py",
    "chrome starts: 16, 0 failed; slowest 9.0 s (the run's Chrome warm-up, start 1)",
    "============================= slowest durations =============================",
    "94.14s call     tests/test_files_chrome.py::test_nothing_moves",
    "10.91s call     tests/test_header_chrome.py::test_the_box[header narrow]",
    "0.25s setup    tests/test_header_chrome.py::test_the_box[header narrow]",
    "0.03s setup    tests/test_files_chrome.py::test_nothing_moves",
    "0.03s teardown tests/test_files_chrome.py::test_nothing_moves",
    "",
    "(3 durations < 0.005s hidden.  Use -vv to show these durations.)",
    "=============== 2 passed, 9446 deselected in 120.20s (0:02:00) ================",
    "9.99s call     tests/test_after_the_section.py::test_is_not_a_duration",
)
SERIAL_LINES = (
    "^[[32m^[[1mPASS^[[22m^[[39m /work/m/tests/golden/cli-api-git.tryscript.md",
    "golden: PASS 10.3 s tests/golden/cli-api-git.tryscript.md",
    "golden: PASS 0.5 s tests/golden/cli-ui-count-parts.tryscript.md",
    "golden: 2 files and 13 commands in 10.6 s, 4 at a time (10.8 s of files): 2 passed, 0 failed",
    "=============== slowest 1 of 1 test files, 12.60 s of test time ================",
    "12.60s tests/test_process_group.py",
    "============================= slowest 25 durations =============================",
    "12.50s call     tests/test_process_group.py::test_a_stop_keeps_to_its_time",
    "0.09s call     tests/test_process_group.py::test_a_failure_still_reaps",
    "0.01s setup    tests/test_process_group.py::test_a_stop_keeps_to_its_time",
    "===================== 33 passed, 9430 deselected in 41.65s =====================",
)
UNIT_LINES = (
    "============= all of 3 test files, 88.00 s of test time ==============",
    "51.36s tests/test_plugin_public_api.py",
    "35.65s tests/test_check_parity.py",
    "0.99s tests/test_small.py",
    "============================= slowest 25 durations =============================",
    "30.00s call     tests/test_plugin_public_api.py::test_the_api",
    "================= 4605 passed, 61 skipped in 209.41s (0:03:29) =================",
)


def test_a_tests_seconds_are_its_phases_summed_within_the_durations_section() -> None:
    for log in (_log("chrome (3.13, 1/4)", *CHROME_LINES), "\n".join(CHROME_LINES)):
        assert durations_of(log) == {
            "tests/test_files_chrome.py::test_nothing_moves": pytest.approx(94.20),
            "tests/test_header_chrome.py::test_the_box[header narrow]": pytest.approx(11.16),
        }
    assert durations_of(_log("lint", "ruff: no durations here")) == {}


def test_each_kind_of_job_fills_only_the_tables_it_measures() -> None:
    samples = Samples()
    samples.add("chrome (3.13, 1/4)", _log("chrome (3.13, 1/4)", *CHROME_LINES))
    samples.add("goldens and serial (3.14t, 2/2)", _log("goldens", *SERIAL_LINES))
    samples.add("unit (3.12, 1/2)", _log("unit (3.12, 1/2)", *UNIT_LINES))
    samples.add("lint", _log("lint", *UNIT_LINES, *CHROME_LINES, *SERIAL_LINES))

    assert samples.combined() == {
        # A Chrome or serial job's files, and a unit job's tests, are not what is dealt.
        TESTS: {
            "tests/test_files_chrome.py::test_nothing_moves": 94.2,
            "tests/test_header_chrome.py::test_the_box[header narrow]": 11.16,
            "tests/test_process_group.py::test_a_failure_still_reaps": 0.09,
            "tests/test_process_group.py::test_a_stop_keeps_to_its_time": 12.51,
        },
        FILES: {
            "tests/test_check_parity.py": 35.65,
            "tests/test_plugin_public_api.py": 51.36,
            "tests/test_small.py": 0.99,
        },
        GOLDENS: {
            "tests/golden/cli-api-git.tryscript.md": 10.3,
            "tests/golden/cli-ui-count-parts.tryscript.md": 0.5,
        },
    }


def test_a_units_weight_is_the_median_of_the_jobs_that_ran_it() -> None:
    samples = Samples()
    for python, seconds in (("3.12", 4.0), ("3.13", 5.0), ("3.14", 6.0), ("3.14t", 40.0)):
        job = f"unit ({python}, 1/2)"
        lines = (
            "============= all of 1 test files, 9.00 s of test time ==============",
            f"{seconds:.2f}s tests/test_a.py",
            "================= 5 passed in 9.41s =================",
        )
        samples.add(job, _log(job, *lines))

    # One slow runner moves the maximum to 40 and the mean to 13.75.
    assert samples.combined()[FILES] == {"tests/test_a.py": 5.5}


def test_the_file_is_written_sorted_with_its_source_first() -> None:
    tables = {TESTS: {"b": 2.0, "a": 1.25}, FILES: {"f": 3.0}, GOLDENS: {"g": 0.5}}
    text = render(tables, [{"id": 7, "commit": "c" * 40}])

    assert text == render(
        {table: dict(reversed(rows.items())) for table, rows in tables.items()},
        [{"id": 7, "commit": "c" * 40}],
    )
    assert list(json.loads(text)) == [shard_weights.SOURCE, *TABLES]
    assert text.index('"a": 1.25') < text.index('"b": 2.0')
    assert text.endswith("}\n")


def _gh(conclusions: dict[str, str], logs: dict[str, str], event: str = "push"):
    """A stand-in for ``gh``: one run, 7, with these jobs."""

    ids = {name: 100 + index for index, name in enumerate(conclusions)}

    def ask(*arguments: str) -> str:
        if arguments[0] == "api" and "/workflows/" in arguments[1]:
            assert "branch=main&event=push&status=success" in arguments[1]
            return json.dumps({"workflow_runs": [{"id": 7}]})
        if arguments[0] == "api" and arguments[1].endswith("/runs/7"):
            return json.dumps({"head_sha": "c" * 40, "event": event})
        if arguments[0] == "api":
            assert "/runs/7/jobs" in arguments[1]
            jobs = [
                {"id": ids[name], "name": name, "conclusion": conclusion}
                for name, conclusion in conclusions.items()
            ]
            return json.dumps({"total_count": len(jobs), "jobs": jobs})
        assert arguments[:3] == ("run", "view", "--job") and arguments[4] == "--log"
        name = next(name for name, number in ids.items() if str(number) == arguments[3])
        return logs[name]

    return ask


JOB_LOGS = {
    "chrome (3.13, 1/4)": _log("chrome (3.13, 1/4)", *CHROME_LINES),
    "goldens and serial (3.13, 1/2)": _log("goldens and serial (3.13, 1/2)", *SERIAL_LINES),
    "unit (3.13, 1/2)": _log("unit (3.13, 1/2)", *UNIT_LINES),
}


def test_a_refresh_reads_the_newest_green_run_on_main_or_the_runs_named() -> None:
    green = dict.fromkeys(JOB_LOGS, "success") | {"lint": "success", "stack": "skipped"}
    ask = _gh(green, JOB_LOGS)

    text = refresh([], ask)

    assert text == refresh([7], ask) == refresh([7, 7], ask)
    document = json.loads(text)
    assert document[shard_weights.SOURCE] == {
        "workflow": "ci.yml",
        "runs": [{"id": 7, "commit": "c" * 40}],
    }
    assert len(document[TESTS]) == 4 and len(document[FILES]) == 3 and len(document[GOLDENS]) == 2


def test_a_run_that_did_not_measure_every_tier_is_refused() -> None:
    green = dict.fromkeys(JOB_LOGS, "success")

    with pytest.raises(RefreshError, match=r"did not succeed: chrome \(3.13, 1/4\)"):
        refresh([7], _gh(green | {"chrome (3.13, 1/4)": "failure"}, JOB_LOGS))
    without_unit = {name: "success" for name in JOB_LOGS if not name.startswith(UNIT_JOB)}
    with pytest.raises(RefreshError, match=r"no job named unit \("):
        refresh([7], _gh(without_unit, JOB_LOGS))
    # A pull request's run may hold the Chrome tier without its slow tests.
    with pytest.raises(RefreshError, match="run 7 is of a pull_request, not a push"):
        refresh([7], _gh(green, JOB_LOGS, event="pull_request"))
    # A log from before the tiers printed their times lists none.
    silent = JOB_LOGS | {"unit (3.13, 1/2)": _log("unit (3.13, 1/2)", "5 passed in 1.00s")}
    with pytest.raises(RefreshError, match="list no time for: files"):
        refresh([7], _gh(green, silent))


def test_a_gh_that_fails_is_reported_with_what_was_asked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def fails(*arguments: str) -> str:
        raise RefreshError(f"gh {' '.join(arguments)} failed: no network")

    monkeypatch.setattr(refresh_shard_weights, "gh", fails)
    output = tmp_path / "weights.json"

    assert refresh_shard_weights.main(["--output", str(output)]) == 1
    assert "shard-weights: gh api repos/" in capsys.readouterr().err
    assert not output.exists()


# ── What the refresh relies on ─────────────────────────────────────────────────


def test_the_jobs_read_are_ci_ymls_sharded_jobs() -> None:
    """Each prefix names exactly the jobs of one sharded tier, as ci.yml names them."""

    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    names = {key: str(job.get("name") or key) for key, job in workflow["jobs"].items()}

    assert {
        prefix: [key for key, name in names.items() if name.startswith(prefix)] for prefix in JOBS
    } == {CHROME_JOB: ["chrome"], SERIAL_JOB: ["goldens"], UNIT_JOB: ["unit"]}


def test_the_tiers_print_the_times_a_refresh_reads() -> None:
    """Every file of every tier, and every test of the tiers that are dealt by test."""

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "--file-durations=0" in makefile_list(makefile, "PYTEST")
    assert makefile_list(makefile, "EVERY_TEST") == ["--durations=0"]
    for target in ("test-serial", "test-chrome"):
        assert "$(PYTEST) $(EVERY_TEST) " in recipe(makefile, target)
    assert recipe(makefile, "shard-weights") == (
        "\t$(UV_RUN) python -m devtools.refresh_shard_weights $(SHARD_WEIGHTS_FLAGS)"
    )
