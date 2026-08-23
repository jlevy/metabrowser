---
type: is
id: is-01m0r1a7hnqaejjgaqn9kyrcfy
title: "PR #73 review R4: preserve ordered response semantics in equivalence"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0r191gatek6ffx1e50wmgr8
created_at: 2026-08-23T19:24:45.491Z
updated_at: 2026-08-23T21:34:06.337Z
closed_at: 2026-08-23T21:34:06.335Z
close_reason: Comparator equivalence now projects only the documented wire fields, preserves ordered lists and nested keys, and has regression tests for both failure modes.
---
PR #73. devtools/compare_builds.py:203 recursively sorts every list and drops generic keys recursively, hiding ordering and nested-field regressions. Canonicalize only explicitly unordered or volatile locations and test it. Review: https://github.com/jlevy/metabrowser/pull/73#pullrequestreview-5003175212
