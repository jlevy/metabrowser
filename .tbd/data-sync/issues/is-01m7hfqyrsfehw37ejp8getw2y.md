---
type: is
id: is-01m7hfqyrsfehw37ejp8getw2y
title: "PR #472 A2: the 106-file height and the boxed tree's row counts do not hold"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7hcjx7q1sk1bp90ba48mdha
created_at: 2026-11-16T06:12:07.064Z
updated_at: 2026-11-16T06:13:20.623Z
closed_at: 2026-11-16T06:13:20.622Z
close_reason: "fixed in e6c6a67aa (PR #472 review A)"
resolution: null
duplicate_of: null
---
src/metabrowser/builtin_plugins/diff/diff-summary.js:65 and docs/design-system.md:1342 gave 133 rows as 3,221 px; the module comment (diff-summary.js:35-44) and the diff.summary-paint row (arch-views-models-routes.md:1009) present the boxed tree's 61 and 102 rows as current. Severity: Low. PR #472, review A round 1: https://github.com/jlevy/metabrowser/pull/472#pullrequestreview-5915650916
