---
type: is
id: is-01m7gx8pw4d54azw9v3zgfx9ew
title: "Pulls rows: number, author and age on line 1; the full title on line 2"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T00:49:13.090Z
updated_at: 2026-11-16T00:49:13.090Z
---
The user's request (2026-11-15), verbatim:

"on the PR nav view, lets adjust the 2 rows so the first row is the stack and PR and author and age, i.e. "1/4 · #113 · [icon] jlevy" with the age right aligned and then the full title on the second line, running all the way to right edge of the nav panel with an ellipsis there"

Today a Pulls row shows the title on its first line, with its place and age, and "#N · author" on its second (builtin_plugins/github/pulls-panel.js, with the stack place from mb-dzsi).

Done when every Pulls nav row has two lines:
- Line 1 is the stack place (for stack members), the PR number, the author's avatar and login, joined by " · " as "1/4 · #113 · [avatar] jlevy". The age is right-aligned at the row's end. A row not in a stack starts at its number.
- Line 2 is the full title, with the conventional-commit prefix rule and the row's state icon or indent kept, running to the nav panel's right edge and cut with an ellipsis there.

The row height, keyboard navigation, the selected and current treatments, the read-ahead on hover, title prefix weights, bold PR numbers and the "no tooltips" rule stay as they are. Measured in Chrome at 299 px and narrower (title width gained, line 1 fitting), pinned in the Pulls stacks Chrome test and the Pulls panel session or golden, and stated in docs/design-system.md's Pulls section. The CHANGELOG says so.
