---
type: is
id: is-01m7s7zh93f3ycgfz7f4asgtpc
title: "Main view: the parent path row aligns with the navigation's folder name row (baseline, padding, and the rule under it)"
kind: task
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T06:30:22.242Z
updated_at: 2026-11-19T07:54:03.683Z
started_at: 2026-11-19T06:31:14.997Z
---
Owner, 2026-11-18, verbatim: "on the main file view, the up arrow can do without a box except on hover, like the collapse chevron. / also on the main file view that path, e.g. ~/wrk/github should be cleanly aligned with the main folder name, same baseline, same padding / also on that, the border below it should be the same and aligned with the border below the main folder name in the nav bar. / the other main page views for commits and PRs don't have a parent folder applicable so this i sjust skipped for these / for all, the View on GitHub button should be aligned with same baseline as the main title (large text filename, PR title, or commit title)". Then: "When done, the top bar should have the same rhythm on the nav panel and on the right, and the title and the Open View on GitHub buttons should all look the same and be aligned properly. The only difference will be that the file view has an extra section at the top for the parent folder." Done together with mb-48rf (nav path row padding) in one PR, branch claude/nav-root-padding.

## Notes

PR #608 (branch claude/nav-root-padding). .view-header-eyebrow is the path row's twin: --pane-header-row-height, 1px solid var(--border) rule, --nav-font-size, centered. Measured 1400 px: nav rule top 33 == eyebrow rule top 33; address baseline == nav name baseline (view-header test pins both). Type table moves the eyebrow to List text. Fragment changelog.d/mb-ch82.md.
