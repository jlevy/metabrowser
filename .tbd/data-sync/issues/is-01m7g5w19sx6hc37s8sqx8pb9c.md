---
type: is
id: is-01m7g5w19sx6hc37s8sqx8pb9c
title: "PR page: the state badge leads the Opened row"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T18:00:20.536Z
updated_at: 2026-11-15T18:15:01.631Z
started_at: 2026-11-15T18:00:53.286Z
---
The user's request (2026-11-15), verbatim:

"the [Draft] status indicator sh0ould go down one line to the left of the "Opened 9 h ago" on that line instead"

Done when the pull request's state badge (Draft, and by the same rule Open, Merged and Closed, unless one of them reads wrong there) leads the "Opened 9h ago · updated ... · View on GitHub" row instead of the author's row, the header's box stays fixed across states, and the design system and header Chrome checks say so.

## Notes

2026-11-15: done in commit e1a4e78a6 on claude/pull-timeline (PR #451), pushed. The state badge slot leads a new .github-pull-opened row ('[Open] Opened … · View on GitHub · Browse code'). The badge and the ages are both 18 px tall in Chrome 152, and the row is fixed across states. The badge is centred on its row, checked by the header Chrome checks. Pins updated: the mount session (row place and parts, ages read from the new row), test_reserved_chrome, the avatar-repaint build count (43 -> 44), the design system, the plan and the CHANGELOG.
