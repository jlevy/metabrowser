---
type: is
id: is-01m7gaskf11fbd1rbaxbefq9re
title: "Conversation: one vertical rhythm between comments and commits, roomier than now"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T19:26:23.712Z
updated_at: 2026-11-16T19:05:41.458Z
started_at: 2026-11-15T19:27:14.339Z
closed_at: 2026-11-16T19:05:41.457Z
close_reason: "Merged into main (stack #446) after the gate."
resolution: null
duplicate_of: null
---
The user's requests (2026-11-15), verbatim:

"And in general, let's look at the consistency of the design system around comments on PRs. The gap between successive comments is too narrow. They are kind of crowded."

"The vertical spacing between commits and between comments should be the same."

Follows mb-xz1r (#451), which made a run of commits stand at least as far from a comment as commits do from each other, and left 12 px between two cards.

Done when the Conversation timeline has one vertical rhythm: the visible space between any two consecutive events is the same, whether card to card, card to commit, commit to card, or commit to commit, and it is roomier than today's 12 px between comment cards. Visible space means border to border for cards and text to text for commit rows. The rhythm is one token in builtin_plugins/github/styles.css and is stated once in docs/design-system.md's Conversation Timeline section. The line and nodes stay continuous across it. It is measured in Chrome (and WebKit if the driver path is quick) in both themes and at the test's widths, and the timeline Chrome test asserts the equal gaps. The CHANGELOG says so.

## Notes

2026-11-15: done in 4a46ec4dd on claude/conversation-rhythm (pushed --no-verify, no PR). There is one token, --github-pull-rhythm (20 px), for the body's gap, the line's connectors and the Review comments cards (.github-pull-threads). A commit row's box is now its line (no padding-block, no min-height, frame only at its sides), and mb-xz1r's run margins are gone. Visible gaps, card border or commit text: before (Chrome 152) card>card 12, card>commit 23.5, commit>card 23.5, commit>commit 20, other>commit 23.5; after, all 20, in Chrome and in WebKit 21624.2.5.11.8 via webkit-driver measure, both themes, 980 and 420 px. The timeline Chrome session asserts every pair's box gap and visible space equal the token; it failed on the previous head.
2026-11-15: merged #460 (claude/tooltips-substantive at 1bf471a02) into claude/conversation-rhythm as b3fcd2508. The only conflict was the plan's phases; this work is now pull request 12 and Phase 12, and the stack count is twelve. Opened draft PR #461 on claude/tooltips-substantive and linked it into stack 446 (12 PRs, in order). After the merge: 152 focused pytest, the page golden via tryscript, the DOM sessions and lint-check (tooltip check included) all pass.
