---
type: is
id: is-01m7pdw10jp8vpk7fbw4g994r4
title: "View headers step 2: pull requests and commits onto the shared view header (icon, optional eyebrow, metadata lines, tab bar, one ground and rule)"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7pab7r3k7xe521vyg5xmrgb
created_at: 2026-11-18T04:15:35.441Z
updated_at: 2026-11-18T05:54:25.091Z
---
Owner, 2026-11-18: "make sure that the headers are better organized for consistency on files, PRs, and commits"; "the overall layout of the header material, the heading, and the metadata below it, and then the tabs ... should all be similarly styled"; "Eyebrow should be optional"; "about white versus gray backgrounds and border lines all of this should have a consistent design system."

PR #550 (mb-6x33) built the shared view header (viewHeaderHtml in app.js) and put files and folders on it; docs/design-system.md "View Headers" states the pattern for all four kinds, with pull requests and commits marked planned. This is step 2 of the stack: move a pull request's page (github plugin pull-page.js) and a commit's page (git-panel.js) onto the same rows.

- Heading row: the kind's icon at the title's size (PR: its state icon, as now; commit: the commit icon the Commits UI uses, or propose one), the title at --page-title-font-size, the row's end slot (the GitHub toggle, mb-zp7y, on github.com repositories).
- Eyebrow: only where it carries something the rows do not (repository and branch context); absent means no reserved space.
- Metadata lines: the author line, branches, ages (Page Headers), at the body size.
- Tab bar: one style and inset; today a PR's tab bar is on --sidebar-bg and only the 735 px reading column wide (measured at 1200x600), against files' --bg across the pane after #550.
- Grounds and rules: header block and tab bar on --bg, one rule under the tabs; a commit (no tabs) ends its header with the one rule.
- A Chrome rhythm measurement across file, folder, PR, and commit at one pane width (row heights, gaps, the tab bar's position), with and without an eyebrow.
Wait for #506 (PR author line and freshness note), which rewrites the same PR header; build on it once it lands.

## Notes

2026-11-18, review A on #552, A11: a pull request page's View on GitHub is a numbered header control (docs/keyboard-shortcuts.md), and the view header's GitHub toggle has no key on files and folders, as Print and Copy path have none. Decide here, before pull requests move onto the view header, whether the toggle takes that number on all four kinds. Also from #550's review: A2 (a plugin shares the header by its class structure; the builder is app.js's own) and A6 (a pull request's tab bar is on --bg since #550 but spans only its reading column).
