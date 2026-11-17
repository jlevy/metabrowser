---
type: is
id: is-01m7gx8pw4d54azw9v3zgfx9ew
title: "Pulls rows: number, author and age on line 1; the full title on line 2"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-16T00:49:13.090Z
updated_at: 2026-11-17T05:59:17.719Z
started_at: 2026-11-16T00:49:57.110Z
closed_at: 2026-11-16T01:05:40.629Z
close_reason: null
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"on the PR nav view, lets adjust the 2 rows so the first row is the stack and PR and author and age, i.e. "1/4 · #113 · [icon] jlevy" with the age right aligned and then the full title on the second line, running all the way to right edge of the nav panel with an ellipsis there"

Today a Pulls row shows the title on its first line, with its place and age, and "#N · author" on its second (builtin_plugins/github/pulls-panel.js, with the stack place from mb-dzsi).

Done when every Pulls nav row has two lines:
- Line 1 is the stack place (for stack members), the PR number, the author's avatar and login, joined by " · " as "1/4 · #113 · [avatar] jlevy". The age is right-aligned at the row's end. A row not in a stack starts at its number.
- Line 2 is the full title, with the conventional-commit prefix rule and the row's state icon or indent kept, running to the nav panel's right edge and cut with an ellipsis there.

The row height, keyboard navigation, the selected and current treatments, the read-ahead on hover, title prefix weights, bold PR numbers and the "no tooltips" rule stay as they are. Measured in Chrome at 299 px and narrower (title width gained, line 1 fitting), pinned in the Pulls stacks Chrome test and the Pulls panel session or golden, and stated in docs/design-system.md's Pulls section. The CHANGELOG says so.

## Notes

Done in 63779083d on claude/pulls-rows-two-lines; draft PR #469 on #467, linked into stack #446. Line 1: place, number, author (.github-pulls-meta, grid row 1, column 3, height 1lh at the number size, overflow clip) with the age at the row end; line 2: chevron, state icon, title (grid-column 3 / -1). The DOM keeps the title first, for the accessible name. Decision on line 1 overflow: one line always; the author ellipsizes to its floor, then leaves the line whole onto a clipped second line; then the place ellipsizes, the number whole; the age never moves. Chrome: title +38.3 px at every width (default pane member 169.7 -> 208, first level 185.7 -> 224; header session 420/360/300/240/180 px: 340/280/220/160/100); rows 43 px at every width (before, 18 px taller where the line wrapped). Pinned: tests/dom/github-pulls-stacks-chrome.mjs, tests/dom/github-pull-header-chrome.mjs (rows now inside .github-pulls, which carries the avatar size), tests/test_reserved_chrome.py, tests/test_design_vocabulary.py, and the panel session key "its text leads with its title". Tests: 329 focused pytest incl. test_modified_keys, 77 cli-ui goldens, format and lint clean. Not checked in WebKit.
