---
type: is
id: is-01m776jgqzq5gxfpfmdxpzgsxr
title: "PR #362 D3: the crash guarantee omits startup before the stdin watcher exists"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m776j8hxq7djw7fdr69cdhxd
created_at: 2026-11-12T06:19:27.358Z
updated_at: 2026-11-12T07:24:42.100Z
closed_at: 2026-11-12T07:24:42.099Z
close_reason: "Fixed in 66c127c8 on claude/v1-robustness, cherry-picked from f92e0bf9 on #366: the --exit-on-eof watch is armed before startup can block."
resolution: null
duplicate_of: null
---
Medium finding D3 on PR #362 (apps/macos/README.md:565; src/metabrowser/cli/serve.py:370). Fixed by the #366 agent's core commits, which the coordinator cherry-picks. Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5869938647
