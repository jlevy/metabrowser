---
type: is
id: is-01m7s93mbp2n4fh3spgb68tc5e
title: "View headers: one moderate gap between the title and the metadata line on file, pull request, and commit views"
kind: task
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T06:50:05.044Z
updated_at: 2026-11-19T07:54:04.714Z
started_at: 2026-11-19T06:50:45.477Z
---
Owner, 2026-11-18, verbatim: "text like this on a PR page [title "fix: align Market Shock Dashboard with shared viewers", "#1176", then "jlevy wants to merge 1 commit · Fetched just now via GitHub CLI"] has a lot of space below the title and PR number and above the "wants to merge" author line. Let's make sure there's a moderate amount and it's consistent across file view with file names, PR views, and commit views before the metadata block." Folded into the header-rhythm PR, branch claude/nav-root-padding (with mb-48rf, mb-igva, mb-ch82, mb-tatf).

## Notes

PR #608 (branch claude/nav-root-padding). One token --page-title-gap: 12px (replaces --view-header-title-gap) beside the file/folder name and under PR title / commit subject (.page-header > .page-heading margin = gap - 6px line gap). Before (1400 px): commit one-line 34 px, two-line 4 px; PR one-line 36.5, long two-line ~6.5. After: box gap 12 on both (text gap commit 10, PR 12.5: the PR author row is chip height); file/folder horizontal 12. Removed min-height 2lh from one-line PR titles and commit subjects; only the cold PR title holds two lines, so the tab bar moves up 30 px when a one-line record lands. Tests: page-header-chrome first line = title height + gap; PR header rows (titleGap) and title give-back. Fragment changelog.d/mb-wcbc.md.
