---
type: is
id: is-01m6f3nddgbv150407xewcjwds
title: Measure large PRs against GitHub and reason from first principles
kind: task
status: in_progress
priority: 1
version: 5
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6f3ndv0s9tpwhvbjwdmtkev
  - type: blocks
    target: is-01m6f3ne8f25m4n06r3d09zw9d
  - type: blocks
    target: is-01m6f3njzx91ssw9yq9x2smtv5
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:50.159Z
updated_at: 2026-11-02T21:47:06.400Z
started_at: 2026-11-02T21:47:06.399Z
---
Running on branch claude/v012-pr-review-perf. Six real PRs, the largest 1,183 files, +281,131 lines over 1,218 commits. Same-PR back-to-back comparison against github.com on public repositories. Also jump to file N and held-key traversal. Delivers a committed experiment record, ranked fixes, and proposed budgets.
