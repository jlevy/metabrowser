---
type: is
id: is-01m7gzdk5rsg1kaz7kpn7p2fyj
title: "Diff summary: one summary at the top of the commit and PR pages, replacing the commit page's counts"
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
created_at: 2026-11-16T01:26:50.295Z
updated_at: 2026-11-16T01:27:37.999Z
started_at: 2026-11-16T01:27:37.998Z
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
