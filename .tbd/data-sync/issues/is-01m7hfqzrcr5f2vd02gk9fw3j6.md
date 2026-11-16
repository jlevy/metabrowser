---
type: is
id: is-01m7hfqzrcr5f2vd02gk9fw3j6
title: "PR #472 A4: a header place inside an open Diff summary restores far from where it was"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7hcjx7q1sk1bp90ba48mdha
created_at: 2026-11-16T06:12:08.075Z
updated_at: 2026-11-16T06:13:22.685Z
closed_at: 2026-11-16T06:13:22.684Z
close_reason: "fixed in 957b79efc (PR #472 review A, A4)"
resolution: null
duplicate_of: null
---
src/metabrowser/builtin_plugins/github/pull-page.js:2769-2774 scrollTopOf applies a header place as its raw top; a remounted page draws its summary collapsed, so the pane lands that far into the Conversation. Severity: Low. PR #472, review A round 1: https://github.com/jlevy/metabrowser/pull/472#pullrequestreview-5915650916
