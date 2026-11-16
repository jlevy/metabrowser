---
type: is
id: is-01m7hfr08j4smv94r327jagfcw
title: "PR #472 A5: disposal of the summary's document and window listeners is untested"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7hcjx7q1sk1bp90ba48mdha
created_at: 2026-11-16T06:12:08.593Z
updated_at: 2026-11-16T06:13:21.416Z
closed_at: 2026-11-16T06:13:21.414Z
close_reason: "fixed in e6c6a67aa (PR #472 review A)"
resolution: null
duplicate_of: null
---
tests/dom/diff-view-behavior.js:598-606 fakes drop the listeners' signals; diff-summary.js:572-573 added a document scroll and a window resize listener. Severity: Low. PR #472, review A round 1: https://github.com/jlevy/metabrowser/pull/472#pullrequestreview-5915650916
