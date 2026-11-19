---
type: is
id: is-01m7s7zgq53sd17agbjv7bcsva
title: "Main view: the Up arrow has no box except on hover, like the navigation collapse chevron"
kind: task
status: closed
priority: 2
version: 6
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T06:30:21.668Z
updated_at: 2026-11-19T08:59:17.832Z
started_at: 2026-11-19T06:31:14.611Z
closed_at: 2026-11-19T08:59:17.831Z
close_reason: "PR #608 merged"
resolution: null
duplicate_of: null
---
Owner, 2026-11-18, verbatim: "on the main file view, the up arrow can do without a box except on hover, like the collapse chevron. / also on the main file view that path, e.g. ~/wrk/github should be cleanly aligned with the main folder name, same baseline, same padding / also on that, the border below it should be the same and aligned with the border below the main folder name in the nav bar. / the other main page views for commits and PRs don't have a parent folder applicable so this i sjust skipped for these / for all, the View on GitHub button should be aligned with same baseline as the main title (large text filename, PR title, or commit title)". Then: "When done, the top bar should have the same rhythm on the nav panel and on the right, and the title and the Open View on GitHub buttons should all look the same and be aligned properly. The only difference will be that the file view has an extra section at the top for the parent folder." Done together with mb-48rf (nav path row padding) in one PR, branch claude/nav-root-padding.

## Notes

PR #608 (branch claude/nav-root-padding). .folder-up is an icon-btn (--icon-btn-size: --view-header-up-size): no frame at rest, hover surface on hover/focus; view-header test reads rest transparent and hover not, after transitions finish. cli-ui-mirror-heading golden updated for the class. Labelled .parent-nav-btn (treemap) unchanged. Fragment changelog.d/mb-igva.md.

Review A on #608 (A4, Low), fixed in 14248fda0: --view-header-up-size 20 -> 24 px (WCAG 2.2 2.5.8), Up 4 px after the chevron (.view-header-eyebrow > .folder-up margin-inline-start). 1400 px: Up 328-352, 4.5-28.5. Address baseline still equals the nav name's (test_view_header_chrome exact check passes). Fragment updated; docs name the token instead of restating 24 px.
