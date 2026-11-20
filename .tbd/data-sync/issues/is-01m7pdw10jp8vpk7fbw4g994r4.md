---
type: is
id: is-01m7pdw10jp8vpk7fbw4g994r4
title: "View headers step 2: pull requests and commits onto the shared view header (icon, optional eyebrow, metadata lines, tab bar, one ground and rule)"
kind: task
status: open
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
created_at: 2026-11-18T04:15:35.441Z
updated_at: 2026-11-20T17:18:15.532Z
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

Owner decision 2026-11-18 (object model plan, Decision 12 C): ship the shared view header to the pull request and commit pages as an SDK frame that plugins call, not as .view-header-* classes plugins write, so moving pages onto the object model later has nothing to undo. See docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md, Decision 12.
