---
type: is
id: is-01m84jcww556yrj71kb61gq73b
title: "PR #737 D2: no test reaches CATALOG_SPECULATIVE_CORE_PER_HOUR through the cores walk or the backfill"
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T16:04:04.608Z
updated_at: 2026-11-23T20:48:43.291Z
started_at: 2026-11-23T16:10:26.317Z
closed_at: 2026-11-23T20:48:03.888Z
close_reason: "Fixed by #761 (merged as c7e2b5991): CATALOG_SPECULATIVE_CORE_PER_HOUR is removed, and the share's order is pinned by tests of the reserve, the backfill hold, and a walk across the hour's roll."
resolution: null
duplicate_of: null
---
Review D2 (Medium) of PR #737, a post-merge follow-up review: https://github.com/jlevy/metabrowser/pull/737#pullrequestreview-6024990059 (review D).

B1's ordering rests on catalog=True at four places: the cores walk's admission and its speculative context (pull_cores.py request_preparation), and the backfill's (pull_list_refresh.py backfill_admitted and the page read). The tests that pin B1 call gh_budget.admission and gh_budget.spent themselves (_walk in tests/test_github_pull_prefetch.py, test_the_catalogs_part_holds_the_walk_and_the_backfill_and_not_the_lane_or_the_labels) or seed the hour's spending (the prefetch golden's _Session.run(spent=...)). None drives request_preparation or refresh_pull_list with the catalog's part spent.

Mutations applied to a scratch copy of src/, never the tree, against tests/test_github_pulls.py, test_github_pull_prefetch.py, test_github_gh_budget.py, test_cli_github_pulls_prefetch_golden.py, test_github_pull_list.py, and test_cli_github_pull_golden.py (PM2 also test_github_pull_list_probe.py):
- PM1, catalog=True dropped from pull_cores.py:612 and :737: 511 passed (survived).
- PM2, catalog=True dropped from pull_list_refresh.py:309 and :475: 538 passed (survived).
- For contrast, admission without its catalog clause (gh_budget.py:407) is killed by test_a_cold_walk_that_spends_first_leaves_the_prefetch_its_caps (assert 100 == 8).

Fix: one test for each call site, through the production path: a background walk batch through request_preparation counted in catalog_spent and answered "held" once the part is spent while the share has room; backfill pages through refresh_pull_list likewise (test_the_backfill_is_speculative_work_and_pauses_once_that_works_share_is_spent could assert catalog_spent, and a catalog of more than 8 backfill pages shows the stop). Review A's A9 asked the same for the share.

If D1's fix changes the design, pin whatever order it chooses the same way.
