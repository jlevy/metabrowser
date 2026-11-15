---
type: is
id: is-01m7g4yyrvd8d2cwnf4matae6g
title: "PR Conversation: the gap above a comment's first commit is at least the gap between commits"
kind: bug
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
created_at: 2026-11-15T17:44:27.674Z
updated_at: 2026-11-15T17:45:04.885Z
started_at: 2026-11-15T17:45:04.884Z
---
The user's request (2026-11-15), verbatim:

"on the PRs tab the sequence line and commits on the timeline is good. But the gap above the first commit after a message or comment is too small. For some reason, it's less than the distance between commits. It should be at least as big."

Follow-up to mb-g3ao (#451), the Conversation timeline.

Done when:
- On a pull request's Conversation, the vertical gap between a comment (or the description) and the first commit after it is at least the gap between two consecutive commits.
- The cause is named (which margin or rule shrinks the comment-to-commit gap), and the fix uses the timeline's own spacing tokens.
- tests/test_github_pull_timeline_chrome.py measures both gaps in Chrome and asserts comment-to-commit >= commit-to-commit, in both themes.
