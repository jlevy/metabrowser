---
type: is
id: is-01m7gaskf11fbd1rbaxbefq9re
title: "Conversation: one vertical rhythm between comments and commits, roomier than now"
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
created_at: 2026-11-15T19:26:23.712Z
updated_at: 2026-11-15T19:27:14.340Z
started_at: 2026-11-15T19:27:14.339Z
---
The user's requests (2026-11-15), verbatim:

"And in general, let's look at the consistency of the design system around comments on PRs. The gap between successive comments is too narrow. They are kind of crowded."

"The vertical spacing between commits and between comments should be the same."

Follows mb-xz1r (#451), which made a run of commits stand at least as far from a comment as commits do from each other, and left 12 px between two cards.

Done when the Conversation timeline has one vertical rhythm: the visible space between any two consecutive events is the same, whether card to card, card to commit, commit to card, or commit to commit, and it is roomier than today's 12 px between comment cards. Visible space means border to border for cards and text to text for commit rows. The rhythm is one token in builtin_plugins/github/styles.css and is stated once in docs/design-system.md's Conversation Timeline section. The line and nodes stay continuous across it. It is measured in Chrome (and WebKit if the driver path is quick) in both themes and at the test's widths, and the timeline Chrome test asserts the equal gaps. The CHANGELOG says so.
