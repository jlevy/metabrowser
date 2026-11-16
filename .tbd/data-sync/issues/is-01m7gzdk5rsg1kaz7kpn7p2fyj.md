---
type: is
id: is-01m7gzdk5rsg1kaz7kpn7p2fyj
title: "Diff summary: one summary at the top of the commit and PR pages, replacing the commit page's counts"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-16T01:26:50.295Z
updated_at: 2026-11-16T20:03:33.646Z
started_at: 2026-11-16T01:27:37.998Z
closed_at: 2026-11-16T20:03:33.646Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"We need to consolidate the diff summaries. On top of a commit I see

106 M
5 A
files
+2572
−1272
lines

This version of summarizing the number of files modified, added, deleted, and lines should be part of our toggleable summary. And it should be clearly at the top of both the commit and the PR page, not within the tab for the changes."

Done when:
- A commit page and a pull request page each show one Diff summary: the toggleable changed-files summary (diff-summary.js, from mb-epw2), with its header ("N changed files (A added, D removed, M modified) +X −Y" or its final wording).
- The summary sits at the top of the page, above the page's tabs and their content: under the PR header and above the Conversation/Changes tab bar, and in the matching place on a commit page. It is not inside the Changes tab.
- The commit page's separate block of file-status counts and line totals (the "106 M / 5 A / files / +2572 / −1272 / lines" block) is gone. Its information lives in the Diff summary's header, with one wording and one set of counts on both pages, from one shared model function.
- Collapsed by default, as before. The header's fixed-height and nothing-moves-on-arrival guarantees still hold, including when the counts arrive after first paint.
- Routes and goldens, the commit and PR page Chrome checks, docs/design-system.md (Diff Summary, the PR page and commit page layouts), and the CHANGELOG say so.

## Notes

2026-11-15: implemented on claude/diff-summary-top at 0d99e545e, draft PR #470 on #469 (claude/pulls-rows-two-lines), linked into stack #446. claude/label-color-cache did not exist on origin, so nothing was merged.

Design: the commit page's diff draws its Diff summary in the commit summary's place (summaryHost); the PR page draws it as the header's last row on every tab through the diff view's new summary method, from the prefetch's loaded callback or Changes' onDocument, and Changes draws none (summary: false). The commit page's M/A/D and line-totals block is gone; the hover summary keeps it.

Measured (Chrome 152): the PR header's row is 24 px from first paint at 980-320 px, and the summary arriving moves no row and not the tab bar. On the commit page the summary is 6 px under the identity and 16 px over the description; its header is one 24 px row at 560 px and wider and wraps at 420 and 320 px; an empty place takes no room.

Open for review: the commit page shows no totals when no diff is drawn; the commit page wraps where the PR header ellipsizes; a PR with no comparison keeps an empty 24 px row. A test failure that predates this change, in tests/test_pull_page_route.py (stylesheet reach, from mb-xlla), fails identically on the base.
