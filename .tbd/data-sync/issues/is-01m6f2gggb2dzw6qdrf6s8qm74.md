---
type: is
id: is-01m6f2gggb2dzw6qdrf6s8qm74
title: "PR #272 https://github.com/jlevy/metabrowser/pull/272#discussion_r4447865362: new compressed-patch test said to always fail"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6f1c0tknva4bd436kj524e0
created_at: 2026-11-02T21:26:40.905Z
updated_at: 2026-11-02T21:43:00.983Z
closed_at: 2026-11-02T21:43:00.982Z
close_reason: "rebutted, by the coordinator's decision on the escalation: the test passes locally and in CI runs 41526601982 and 41528650627, and both documents it compares read the same bounded prefix. No code changed. Reply: https://github.com/jlevy/metabrowser/pull/272#discussion_r4448120771"
resolution: null
duplicate_of: null
---
Unmarked bot comment, bot severity High, on commit 38447bdc. tests/test_diff_plugin_sidekick.py:370. Would be rebutted: escalated to the coordinator, since the rule escalates rebutting a High.

## Notes

ESCALATED to the coordinator: bot severity High, and the disposition would be rebutted. Evidence: the test passes locally and in all four CI test jobs; both documents compared are read through the same bound, totals files 9 on both, files 10 with the bound lifted. Reply text ready, not posted.
