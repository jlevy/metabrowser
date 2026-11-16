---
type: is
id: is-01m7hfqy5k4cg3ba8ytn4c9vx7
title: "PR #472 A1: the CSS comment's account of the page-top indent before this change is wrong"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7hcjx7q1sk1bp90ba48mdha
created_at: 2026-11-16T06:12:06.450Z
updated_at: 2026-11-16T06:13:20.235Z
closed_at: 2026-11-16T06:13:20.234Z
close_reason: "fixed in e6c6a67aa (PR #472 review A)"
resolution: null
duplicate_of: null
---
src/metabrowser/builtin_plugins/diff/styles.css:151-153 said the rows started 16px in from where the header was placed, 20px right of it, at a page's top; they were already 16px right of the header there. Severity: Low. PR #472, review A round 1: https://github.com/jlevy/metabrowser/pull/472#pullrequestreview-5915650916
