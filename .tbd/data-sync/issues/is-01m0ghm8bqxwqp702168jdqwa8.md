---
type: is
id: is-01m0ghm8bqxwqp702168jdqwa8
title: Branch chips get their own pale-orange ground
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-20T21:35:55.767Z
updated_at: 2026-08-20T21:35:55.767Z
---
Git ref chips (branches and tags) use the generic pale-gray chip background; give the Branch Chips vocabulary its own very pale orange ground so a ref is distinguishable from a filter chip at a glance, in both themes. Add the token beside the other --git-ref-* tokens, apply it everywhere ref chips render (graph rows, commit detail), state it in design-system.md's Branch Chips section, and pin the token in tests/test_design_vocabulary.py.
