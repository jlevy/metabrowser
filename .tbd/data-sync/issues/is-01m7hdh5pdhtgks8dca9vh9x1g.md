---
type: is
id: is-01m7hdh5pdhtgks8dca9vh9x1g
title: "PR #465 A1: a record of an earlier projection the catalog vouches for is never refreshed, so its labels stay neutral"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjnnynpvyk66k6knhg5vq
hold: null
hold_until: null
created_at: 2026-11-16T05:33:27.628Z
updated_at: 2026-11-16T06:22:48.574Z
started_at: 2026-11-16T05:33:40.172Z
closed_at: 2026-11-16T06:22:48.572Z
close_reason: "Fixed in 91545dee1 (record_freshness gives no current or checks verdict to a record of an earlier projection, keeping changed) and e5b51e889 (CHANGELOG, pull_record.py projection comment, plan corrected). Confirmed by test_a_record_of_an_earlier_projection_is_never_vouched_for_so_it_is_refreshed_once, which failed before the fix with current. PR #465 review A1."
resolution: null
duplicate_of: null
---
Medium, PR #465 review A (https://github.com/jlevy/metabrowser/pull/465#pullrequestreview-5915428037). record_freshness (src/metabrowser/builtin_plugins/github/pull_freshness.py:117-145) answers current for a closed or merged record whenever the catalog scan is recent and its row unchanged, whatever its projection_version, so a record cached before label colors keeps neutral chips. Texts that promise a refresh: CHANGELOG.md:12-13, pull_record.py:59-61, plan :400-401. Fix (coordinator): Refresh once, plus a test that a closed projection-1 record with a fresh catalog is stale; correct the three texts.
