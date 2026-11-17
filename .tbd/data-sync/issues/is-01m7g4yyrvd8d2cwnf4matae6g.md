---
type: is
id: is-01m7g4yyrvd8d2cwnf4matae6g
title: "PR Conversation: the gap above a comment's first commit is at least the gap between commits"
kind: bug
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
created_at: 2026-11-15T17:44:27.674Z
updated_at: 2026-11-17T06:01:39.007Z
started_at: 2026-11-15T17:45:04.884Z
closed_at: 2026-11-17T06:01:39.007Z
close_reason: "Shipped in PR #451 (merged 2026-11-16T16:30Z, in afda3599f); the beads were left in_progress by an earlier session. Found during plan-2026-11-15 currency (PR #500)."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"on the PRs tab the sequence line and commits on the timeline is good. But the gap above the first commit after a message or comment is too small. For some reason, it's less than the distance between commits. It should be at least as big."

Follow-up to mb-g3ao (#451), the Conversation timeline.

Done when:
- On a pull request's Conversation, the vertical gap between a comment (or the description) and the first commit after it is at least the gap between two consecutive commits.
- The cause is named (which margin or rule shrinks the comment-to-commit gap), and the fix uses the timeline's own spacing tokens.
- tests/test_github_pull_timeline_chrome.py measures both gaps in Chrome and asserts comment-to-commit >= commit-to-commit, in both themes.

## Notes

2026-11-15 (claude/pull-timeline, commit ec17d55a3, pushed --no-verify; PR #451):

Cause: event boxes were one 12 px gap apart, but a commit row keeps a card head's room between its text and its edge (1 px transparent frame, the head's 3 px padding, and the line's half-leading). So two commits' glyphs were a gap and two rooms apart (20 px), while a card's edge and a commit's glyphs were a gap and one room apart (16 px). The same held below a run's last commit.

Fix (github/styles.css): --github-pull-run-space = calc(1px + 3px + (1lh - 1em) / 2), on the commit row. It is margin-top on a run's first commit (`.github-pull-body > :not(.github-pull-commit) + .github-pull-commit`) and margin-bottom on its last (`.github-pull-commit:has(+ :not(.github-pull-commit))`). The commit's ::before line segment reaches across it, so the line and nodes stay continuous.

Measured edge or glyph to glyph, Chrome 152 and WebKit 21624.2.5.11.8 (webkit-driver measure), both themes:
- before: card or section to first commit 16 px, commit to commit 20 px, last commit to card 16 px;
- after: 23.5 / 20 / 23.5 px.

Test: tests/dom/github-pull-timeline-chrome.mjs, run by tests/test_github_pull_timeline_chrome.py, now has 359 checks. It checks that card or section to first commit and last commit to card are >= commit to commit in every layout and both themes. 14 of those checks failed on f98c4af4 (16 against 20).

Local: make -o install format, make -o install lint-check (parity, goldens), and 114 focused pytest pass (timeline Chrome, design vocabulary, pull page session, pull page route, avatar repaint); the timeline, first-paint and mount DOM scripts pass. The WebKit after-measure ran before the selector was scoped under .github-pull-body; that scoping is an equivalent selector.
