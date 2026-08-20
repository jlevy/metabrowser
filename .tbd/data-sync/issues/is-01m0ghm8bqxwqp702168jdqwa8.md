---
type: is
id: is-01m0ghm8bqxwqp702168jdqwa8
title: Branch chips get their own pale-orange ground
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T21:35:55.767Z
updated_at: 2026-08-20T21:47:43.894Z
closed_at: 2026-08-20T21:47:43.893Z
close_reason: "Landed in d84e934: --git-ref-bg is its own very pale warm ground in both themes, stated in Branch Chips and pinned."
---
Git ref chips (branches and tags) use the generic pale-gray chip background; give the Branch Chips vocabulary its own very pale orange ground so a ref is distinguishable from a filter chip at a glance, in both themes. Add the token beside the other --git-ref-* tokens, apply it everywhere ref chips render (graph rows, commit detail), state it in design-system.md's Branch Chips section, and pin the token in tests/test_design_vocabulary.py.
