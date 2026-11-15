---
type: is
id: is-01m7g5w0nr4cbfm4xtmtqzztrh
title: "PR page: the stack chip leads the author's row, under the title"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T18:00:19.895Z
updated_at: 2026-11-15T18:00:53.721Z
started_at: 2026-11-15T18:00:53.720Z
---
The user's request (2026-11-15), verbatim:

"also on the main PR view page let's make a couple changs

the button with the stack icon and number should go directliy below the PR title, to the left of the author."

Today the stack chip sits in a slot at the end of the labels row (static header layout in builtin_plugins/github/pull-page.js `mountPullPage` and `paintHeader`; docs/design-system.md, "The Pull Request Page"), chosen so a stack arriving after first paint moves nothing.

Done when the stack chip leads the row directly under the title, left of the author ("[Stack #N] [avatar] jlevy wants to merge ..."), and the header still moves nothing when the stack's answer arrives after the first paint: no horizontal shift of the author line and no vertical shift of the rows below. Measured in Chrome (and in WebKit if the driver path is quick) with the stack arriving late, early, and never. The design system and the header Chrome checks say so.
