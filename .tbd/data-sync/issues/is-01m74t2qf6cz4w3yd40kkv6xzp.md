---
type: is
id: is-01m74t2qf6cz4w3yd40kkv6xzp
title: "PR #346 A8: first Changes visit per checkout source refreshes GitHub twice"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
created_at: 2026-11-11T08:02:38.181Z
updated_at: 2026-11-11T09:25:07.755Z
closed_at: 2026-11-11T09:25:07.754Z
close_reason: "Removed by #348 (codex/pr-review-cache-loads at 10b7dafa): a cold direct Changes visit makes 8 gh calls for the selected metadata job and 0 for the comparison job, which prepares the fresh record's comparison without reading GitHub again (the #347 base 8dd80d0c made 8 + 8). Measured with the checkout fake-gh fixture through metab --api; pinned in tests/test_github_checkout.py (_Session.attach_store asserts no gh call for the comparison request; test_a_comparison_from_the_cached_record_keeps_the_metadata_stamp). A stale record still reads GitHub first (review A2)."
resolution: null
duplicate_of: null
---
Suggestion. Cold direct visit runs companion.refresh() in the selected metadata job, then again in the comparison job after acquisition (checkout.py:376-406). Options: comparison:true on a cold Changes miss, skip the GitHub read within FRESHNESS_WINDOW_S, or leave to #348. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).

## Notes

Deferred to PR #348 (tracked by mb-y40t). On origin/codex/pr-review-cache-loads, checkout.py _prepare_comparison projects the comparison from the cached record with prepare_pull_comparison and returns before companion.refresh() when the record is usable, which removes the second GitHub read on a first Changes visit. Verify there when #348 is reviewed; close when #348 merges with that path.
