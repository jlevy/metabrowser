---
type: is
id: is-01m8577a93twx8hbzm7srsw9pj
title: "Review PR #759 (Docs tab file header fixes) with review-github-pr and address its findings"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m83968ry3rs287s3mgg0r93y
hold: null
hold_until: null
created_at: 2026-11-23T22:08:01.826Z
updated_at: 2026-11-23T23:52:00.492Z
started_at: 2026-11-23T22:43:39.049Z
closed_at: 2026-11-23T23:52:00.490Z
close_reason: "Review A of #759 addressed: A1 to A8 fixed at cbb9fb6, disposition reply https://github.com/jlevy/metabrowser/pull/759#issuecomment-7117430895, CI green (run 45291034137)."
resolution: null
duplicate_of: null
---

## Notes

Review A of PR #759 (https://github.com/jlevy/metabrowser/pull/759#pullrequestreview-6030672058, at ddac23d) addressed at cbb9fb6754dded4c6740a8b232494b2b6b1b281d. Disposition reply: https://github.com/jlevy/metabrowser/pull/759#issuecomment-7117430895. Findings are recorded in this bead, with no child beads.

- A1 fixed in 48144d3: the View file controls are parts of the bar of their own between the name's group and the end group, and every bar wraps; --diff-file-lead-basis 176 px. Held by tests/test_diff_file_bar_chrome.py (181 checks, 1,063 to 159 px).
- A2 fixed in 38cf669: the repair-lifecycle session asserts that Docs alone asks for layout "unified"; the comparison route session asserts that the plugin forwards it. Deleting either production line fails a browserless test.
- A3 fixed in cbb9fb6: changelog.d/mb-leg0.md describes the bar as it now is.
- A4 fixed in 48144d3: --diff-file-actions-gap 32 px; at rest the stats are 28 px from the name and 44 px from View file.
- A5 fixed in cbb9fb6: the two bar bullets are folded into mb-leg0.md.
- A6 fixed in cbb9fb6: both architecture documents say "Changes and Docs".
- A7 fixed in ca7c334: the layout option is narrowed to "unified".
- A8 fixed in 48144d3: the order check accepts bars with or without stats.

CI run 45291034137 is green at cbb9fb6. Known limit, documented: the name's group never breaks, so a group wider than its line (a mode note with five-digit stats) still covers part of itself.
