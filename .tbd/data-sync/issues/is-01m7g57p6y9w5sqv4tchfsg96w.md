---
type: is
id: is-01m7g57p6y9w5sqv4tchfsg96w
title: "Pulls nav: a stack member's place sits on its number's line, with no stack icon"
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
created_at: 2026-11-15T17:49:13.821Z
updated_at: 2026-11-15T17:50:36.656Z
started_at: 2026-11-15T17:50:36.655Z
---
The user's request (2026-11-15), verbatim:

"the PR stackcount in the stacked Pulls nav should be on the same line as the PR number and the stack icon is already in the enclosing toggle so we don't need to duplicate it so it should be more like: 1/6 · #455 · [profile icon] jlevy ..."

"Together, this should show a lot more text of the PR title. We need a lot more of the text for each PR title in the nav."

Done when a stack member's row in the Pulls nav puts its place in the stack on the PR number's line, as "1/6 · #455 · [avatar] jlevy ...", with no stack icon of its own (the enclosing Stack #N toggle has it), and the title gets the line it frees. Pinned by the Pulls stack golden or session and the Pulls Chrome test.
