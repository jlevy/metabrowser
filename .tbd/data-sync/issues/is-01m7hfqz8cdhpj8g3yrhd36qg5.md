---
type: is
id: is-01m7hfqz8cdhpj8g3yrhd36qg5
title: "PR #472 A3: the golden and the session still describe the tree's box's view"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7hcjx7q1sk1bp90ba48mdha
created_at: 2026-11-16T06:12:07.563Z
updated_at: 2026-11-16T06:13:21.031Z
closed_at: 2026-11-16T06:13:21.030Z
close_reason: "fixed in e6c6a67aa (PR #472 review A)"
resolution: null
duplicate_of: null
---
tests/golden/cli-ui-diff-summary.tryscript.md:31 and tests/dom/diff-summary-session.js:293 say the box's view; the tree has no box of its own now. Severity: Low. PR #472, review A round 1: https://github.com/jlevy/metabrowser/pull/472#pullrequestreview-5915650916
