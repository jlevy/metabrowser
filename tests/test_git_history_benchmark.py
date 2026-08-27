"""Contract tests for the Git-history measurement and session prototype."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from devtools.git_history_benchmark import (
    DEFAULT_PAGE_SIZE,
    HistoryShape,
    build_history_corpus,
    measure_history_corpus,
    spool_history,
)
from metabrowser.git.process import GIT_COMMON_ARGS, git_environment
from metabrowser.settings import (
    GIT_HISTORY_PAGE_CACHE_PAGES,
    GIT_HISTORY_SEGMENT_REBASE_PX,
    GIT_HISTORY_SESSION_IDLE_TTL_S,
    GIT_HISTORY_SESSION_MAX_ENTRIES,
    GIT_HISTORY_SESSION_MAX_STORAGE_BYTES,
    GIT_HISTORY_SESSION_MAX_WALKS,
    GIT_HISTORY_SESSION_PARSER_MAX_BYTES,
    GIT_HISTORY_WINDOW_MAX_ROWS,
    GIT_HISTORY_WINDOW_OVERSCAN_ROWS,
    GIT_LOG_DEFAULT_LIMIT,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required to build history corpora",
)


def test_measured_history_budgets_remain_structurally_bounded() -> None:
    assert GIT_LOG_DEFAULT_LIMIT == 250
    assert GIT_HISTORY_WINDOW_MAX_ROWS == 256
    assert GIT_HISTORY_WINDOW_OVERSCAN_ROWS == 64
    assert GIT_HISTORY_WINDOW_OVERSCAN_ROWS * 2 < GIT_HISTORY_WINDOW_MAX_ROWS
    assert GIT_HISTORY_PAGE_CACHE_PAGES == 8
    assert GIT_HISTORY_SEGMENT_REBASE_PX == 8_000_000
    assert GIT_HISTORY_SESSION_IDLE_TTL_S == 300.0
    assert GIT_HISTORY_SESSION_MAX_ENTRIES == 8
    assert GIT_HISTORY_SESSION_MAX_WALKS == 2
    assert GIT_HISTORY_SESSION_PARSER_MAX_BYTES == 128 * 1024
    assert GIT_HISTORY_SESSION_MAX_STORAGE_BYTES == 64 * 1024 * 1024


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *GIT_COMMON_ARGS, "-C", str(root), *args],
        check=True,
        capture_output=True,
        env=git_environment(),
        text=True,
    ).stdout.strip()


@pytest.mark.parametrize(
    ("shape", "expected_branches", "minimum_merges"),
    [
        ("linear", 1, 0),
        ("branch-heavy", 5, 0),
        ("merge-heavy", 2, 3),
    ],
)
def test_history_corpus_builder_preserves_requested_shape(
    tmp_path: Path,
    shape: HistoryShape,
    expected_branches: int,
    minimum_merges: int,
) -> None:
    root = tmp_path / shape

    facts = build_history_corpus(root, shape=shape, commit_count=9)

    assert facts == {
        "commit_count": 9,
        "object_format": "sha1",
        "shape": shape,
    }
    assert int(_git(root, "rev-list", "--all", "--count")) == 9
    assert len(_git(root, "for-each-ref", "--format=%(refname)", "refs/heads").splitlines()) == (
        expected_branches
    )
    merge_count = len(
        [line for line in _git(root, "rev-list", "--all", "--min-parents=2").splitlines() if line]
    )
    assert merge_count >= minimum_merges


def test_streaming_spool_replays_exact_order_after_the_walk_finishes(tmp_path: Path) -> None:
    root = tmp_path / "history"
    build_history_corpus(root, shape="merge-heavy", commit_count=17)

    with spool_history(root, page_size=4) as spool:
        expected = _git(root, "rev-list", "--date-order", "--all").splitlines()
        observed = [commit["id"] for page in spool.replay_all() for commit in page]

        assert observed == expected
        assert spool.commit_count == 17
        assert spool.page_count == 5
        assert spool.peak_buffer_bytes <= spool.max_page_bytes + spool.read_chunk_bytes
        third_page = [commit["id"] for commit in spool.replay_page(2)]
        assert third_page == expected[8:12]
        assert [commit["id"] for commit in spool.replay_page(0)] == expected[:4]
        assert [commit["id"] for commit in spool.replay_page(2)] == third_page


def test_measurement_records_cost_shape_without_machine_timing_gates(tmp_path: Path) -> None:
    root = tmp_path / "history"
    build_history_corpus(root, shape="linear", commit_count=31)

    result = measure_history_corpus(
        root,
        shape="linear",
        commit_count=31,
        page_size=DEFAULT_PAGE_SIZE,
        skip_depths=(0, 7, 23),
    )

    assert result["schema"] == "metabrowser-git-history-measurement/v1"
    assert result["corpus"] == {
        "commit_count": 31,
        "object_format": "sha1",
        "shape": "linear",
    }
    assert [sample["skip"] for sample in result["offset_pages"]] == [0, 7, 23]
    assert all(sample["commits"] > 0 for sample in result["offset_pages"])
    assert all(sample["elapsed_ms"] >= 0 for sample in result["offset_pages"])
    prototype = result["streaming_prototype"]
    assert prototype["commit_count"] == 31
    assert prototype["ordered_revision_match"] is True
    assert prototype["page_count"] == 1
    assert prototype["spool_bytes"] > 0
    assert prototype["spool_bytes_per_commit"] > 0
    assert prototype["peak_buffer_bytes"] > 0
