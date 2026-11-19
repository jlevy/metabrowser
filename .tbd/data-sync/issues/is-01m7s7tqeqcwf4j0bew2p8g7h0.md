---
type: is
id: is-01m7s7tqeqcwf4j0bew2p8g7h0
title: "Nav root row: vertical padding matches the tabs below it"
kind: task
status: closed
priority: 3
version: 5
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T06:27:44.725Z
updated_at: 2026-11-19T08:59:17.487Z
started_at: 2026-11-19T06:31:14.223Z
closed_at: 2026-11-19T08:59:17.485Z
close_reason: "PR #608 merged"
resolution: null
duplicate_of: null
---
Owner, 2026-11-18, verbatim: "on the main file view, the up arrow can do without a box except on hover, like the collapse chevron. / also on the main file view that path, e.g. ~/wrk/github should be cleanly aligned with the main folder name, same baseline, same padding / also on that, the border below it should be the same and aligned with the border below the main folder name in the nav bar. / the other main page views for commits and PRs don't have a parent folder applicable so this i sjust skipped for these / for all, the View on GitHub button should be aligned with same baseline as the main title (large text filename, PR title, or commit title)". Then: "When done, the top bar should have the same rhythm on the nav panel and on the right, and the title and the Open View on GitHub buttons should all look the same and be aligned properly. The only difference will be that the file view has an extra section at the top for the parent folder." Done together with mb-48rf (nav path row padding) in one PR, branch claude/nav-root-padding.

## Notes

PR #608 (branch claude/nav-root-padding). --pane-header-row-height 34 px (was 41): the path's text sits 7.25 px under the row's top vs the tabs' 7 px; at 41 it was 10.75 (Chrome, 2026-11-18). Fragment changelog.d/mb-48rf.md.
