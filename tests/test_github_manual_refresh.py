"""Explicit retry for unavailable current comparisons never starts an automatic fetch."""

from tests.golden_harness import run_session


def test_current_failed_comparisons_can_be_retried_explicitly() -> None:
    assert run_session("github-pull-manual-refresh-behavior.js") == {
        "manualFailuresRetry": [
            "comparison_timeout",
            "comparison_too_large",
            "commits_unavailable",
            "base_uncertain",
        ],
        "automaticReadsFetch": False,
        "noStoreKeepsOwnAction": True,
    }
