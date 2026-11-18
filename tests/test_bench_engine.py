"""`devtools/bench_engine.py` times the selected provider alone, without a server.

These run one tiny trial, in process and through the command, so the harness keeps
working; they assert what was measured and never how long it took.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from devtools import bench_engine
from metabrowser.inventory_engine.factory import InventoryProvider
from tests.inventory_harness import selected_inventory_provider


def _corpus(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    for index in range(3):
        (root / "src" / f"module{index}.py").write_text("pass\n")
    (root / "README.md").write_text("# corpus\n")
    return root


def test_a_trial_settles_and_times_every_folder_view_query(tmp_path: Path) -> None:
    root = _corpus(tmp_path / "corpus")
    provider = selected_inventory_provider()
    record = asyncio.run(bench_engine.measure(root, provider, watch_mode="off", repeats=2))
    assert record["provider"] == provider.value
    assert record["watch_mode"] == "off"
    assert record["settled_phase"] == "ready"
    assert record["complete"] is True
    assert (record["files"], record["directories"]) == (4, 2)
    assert set(record["reads"]) == set(bench_engine.folder_view_queries(1, 1))
    for timing in record["reads"].values():
        assert set(timing) == {"first_ms", "repeat_min_ms", "repeat_median_ms"}
    assert record["open_ms"] <= record["settled_ms"]


def test_trials_rotate_which_provider_runs_first() -> None:
    providers = [InventoryProvider.PYTHON, InventoryProvider.PYTHON]
    assert bench_engine.rotated(providers, 0) == providers
    letters = ["a", "b", "c"]
    assert [bench_engine.rotated(letters, trial)[0] for trial in range(3)] == ["a", "b", "c"]


def test_the_command_runs_each_trial_in_a_fresh_process(tmp_path: Path) -> None:
    root = _corpus(tmp_path / "corpus")
    output = tmp_path / "engine.json"
    provider = selected_inventory_provider().value
    status = bench_engine.main(
        [
            str(root),
            "--provider",
            provider,
            "--watch-mode",
            "off",
            "--repeats",
            "1",
            "--json",
            str(output),
        ]
    )
    assert status == 0
    runs = json.loads(output.read_text())["runs"]
    assert [(run["trial"], run["provider"], run["files"]) for run in runs] == [(0, provider, 4)]
