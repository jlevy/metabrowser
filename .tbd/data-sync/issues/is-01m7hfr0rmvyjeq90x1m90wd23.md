---
type: is
id: is-01m7hfr0rmvyjeq90x1m90wd23
title: "PR #472 A6: the summary's scroll listener draws for scrolls of boxes that cannot move it"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7hcjx7q1sk1bp90ba48mdha
created_at: 2026-11-16T06:12:09.107Z
updated_at: 2026-11-16T06:13:21.823Z
closed_at: 2026-11-16T06:13:21.822Z
close_reason: "fixed in e6c6a67aa (PR #472 review A)"
resolution: null
duplicate_of: null
---
src/metabrowser/builtin_plugins/diff/diff-summary.js:561-573: the capture-phase listener schedules a frame for every scroll in the document. Severity: Suggestion. PR #472, review A round 1: https://github.com/jlevy/metabrowser/pull/472#pullrequestreview-5915650916
