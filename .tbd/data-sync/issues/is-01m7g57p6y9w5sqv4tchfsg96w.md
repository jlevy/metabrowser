---
type: is
id: is-01m7g57p6y9w5sqv4tchfsg96w
title: "Pulls nav: a stack member's place sits on its number's line, with no stack icon"
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
created_at: 2026-11-15T17:49:13.821Z
updated_at: 2026-11-17T05:58:35.597Z
started_at: 2026-11-15T17:50:36.655Z
closed_at: 2026-11-15T18:29:13.302Z
close_reason: null
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"the PR stackcount in the stacked Pulls nav should be on the same line as the PR number and the stack icon is already in the enclosing toggle so we don't need to duplicate it so it should be more like: 1/6 · #455 · [profile icon] jlevy ..."

"Together, this should show a lot more text of the PR title. We need a lot more of the text for each PR title in the nav."

Done when a stack member's row in the Pulls nav puts its place in the stack on the PR number's line, as "1/6 · #455 · [avatar] jlevy ...", with no stack icon of its own (the enclosing Stack #N toggle has it), and the title gets the line it frees. Pinned by the Pulls stack golden or session and the Pulls Chrome test.

## Notes

Done in 172d9a10c on claude/pulls-stack-groups (#450). The place sits before the number on the muted line (.github-pulls-id: place + number, nowrap, shrinking alone on a short line so the place ends in an ellipsis and the number shows whole); no stack icon on member rows. Title room at the 299 px default pane (tests/test_github_pulls_stacks_chrome.py MEASURE_OUT): member in two stacks 65.4 -> 165.7 px, one-stack member 125.0 -> 165.7, first-level row 175.7 -> 181.7 (the removed column's 6 px gap); rows stay 43 px. Header Chrome session (tests/dom/github-pull-header-chrome.mjs) at 420/360/300/240/180 px: title line never moves, three stacks take a third line at 300 px, two stacks with a 39-character login at 240 px, one stack at 180 px.
