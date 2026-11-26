---
type: is
id: is-01m8be2msec8pk98cjcrb5wqzv
title: "Rendered diffs: localize /view/ targets while the page shows the head, and close them with the head links"
kind: task
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-26T08:03:15.374Z
updated_at: 2026-11-26T20:22:52.557Z
started_at: 2026-11-26T19:07:56.480Z
---
From the Fable review of #874 (L2): diff-view.js passes views:false, so a blob/<served branch> link opens in place in a README but goes to GitHub in the same file rendered in Changes. Allow view targets while headLinksOpen holds and convert them in closeHeadLinks.

## Notes

PR: https://github.com/jlevy/metabrowser/pull/891
