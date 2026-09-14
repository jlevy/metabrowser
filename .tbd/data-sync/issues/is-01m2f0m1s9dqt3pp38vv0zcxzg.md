---
type: is
id: is-01m2f0m1s9dqt3pp38vv0zcxzg
title: "PR #115 review R3: Only the first run of a series launches without a preceding full traversal"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2f0m0sdxg3fe8v091zxkby8
created_at: 2026-09-14T03:50:52.456Z
updated_at: 2026-09-14T04:48:10.513Z
closed_at: 2026-09-14T04:48:10.512Z
close_reason: "Fixed in bbd16783 (option a, enforced): record/fingerprint hand the post-walk traversal forward, serve carries it, record and capture --record refuse a run without it; README and harness-22 comment corrected; folded into harness 22 (no rows recorded under 22)"
resolution: null
duplicate_of: null
---
PR #115 review R3 (Medium). explorations/performance-loop/run.py:961-964, 1189-1191; README.md:186-194, 386-398.

Harness 22 moved the full corpus traversal from serve to record. Runs 2..n of a series still launch seconds after the previous record's traversal; run 1 launches after none. The recipe always starts with the control, so the one regime-distinct row always lands on the control, in walk_elapsed_ms. README "identically for every condition" and the harness-22 comment overclaim.

Fix (pick one): (a) an unrecorded warm-up cycle at the start of each series (e.g. a run.py fingerprint subcommand); (b) alternate the leading condition. Correct the README and the harness-22 comment either way.
