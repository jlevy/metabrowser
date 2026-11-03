---
type: is
id: is-01m6f3aces3z20vehpwkkxdd7m
title: The rules this work keeps, as tests
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3acyxhn6fc74nvnwbb6gm
parent_id: is-01m2nz9gwd4wyxmrpx49cp9yck
hold: null
hold_until: null
created_at: 2026-11-02T21:40:48.728Z
updated_at: 2026-11-03T20:17:10.208Z
started_at: 2026-11-03T07:01:14.434Z
closed_at: 2026-11-03T20:17:10.208Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
An unopened tab runs no gh and loads nothing past _ROUTE_TABLE_ONLY, the full flow leaves .git byte-for-byte unchanged and passes with it read-only, and listing works with no store.

## Notes

2026-11-03 HANDOFF: on wip/pulls-5-checkout (24a95778), tests/test_github_checkout.py. Proven: an unopened tab runs no gh and loads nothing past _ROUTE_TABLE_ONLY (fresh interpreter, logging failing gh, checkout.py not loaded, no home created). The whole flow on a read-only checkout leaves .git byte for byte (inode and mtime included) and runs no git (logging wrapper). Nothing is written under an unclaimed slug; mutation-checked by hand, since restoring ensure_private_directory fails it. Listing with no store is the existing test_listing_succeeds_for_a_source_directory_with_no_store. Not run: make test. See mb-cbak.
