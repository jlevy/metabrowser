---
type: is
id: is-01m776jgqzq5gxfpfmdxpzgsxr
title: "PR #362 D3: the crash guarantee omits startup before the stdin watcher exists"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m776j8hxq7djw7fdr69cdhxd
created_at: 2026-11-12T06:19:27.358Z
updated_at: 2026-11-12T06:19:27.358Z
---
Medium finding D3 on PR #362 (apps/macos/README.md:565; src/metabrowser/cli/serve.py:370). Fixed by the #366 agent's core commits, which the coordinator cherry-picks. Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5869938647
