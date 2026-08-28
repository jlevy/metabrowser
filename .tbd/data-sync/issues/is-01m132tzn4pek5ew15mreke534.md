---
type: is
id: is-01m132tzn4pek5ew15mreke534
title: "Git status Phase 0: dirty-tree corpus and the measurement gate"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md
labels: []
dependencies:
  - type: blocks
    target: is-01m10z5s3nhwmdyp1dcbwfwc33
parent_id: is-01m10z5hmf2m2tndf00k0jznx8
created_at: 2026-08-28T02:23:01.794Z
updated_at: 2026-08-28T02:23:02.899Z
---
Build the dirty-tree fixture corpus and benchmark command, record latency/bytes/retained memory/browser row cost, and close the three open decisions: submodule inspection option, the entry/byte/timeout/debounce/row budgets, and whether copy detection earns its cost. Deliverable is recorded measurements plus written decisions, not code. If a complete --untracked-files=all status cannot be bounded usefully this ends in a return to design review. Blocks mb-u4mf.
