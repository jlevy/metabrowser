---
type: is
id: is-01m7g57nn5rthmy1dffxxnprpx
title: "Nav rows: slightly tighter icon slots, chevrons and file type icons one width"
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
created_at: 2026-11-15T17:49:13.252Z
updated_at: 2026-11-15T17:50:37.067Z
started_at: 2026-11-15T17:50:37.066Z
---
The user's request (2026-11-15), verbatim:

"the padding around the chevrons in the file toggle and expecially the stacked PRs toggle is slighlty too much. similarly for the padding around the pull request icons and around the stack icons inthe pulls nav column. Things should be very slightly tighter because there's excessive padding, but we should do it in a way that's not too much (because we need the files tab to still align cleanly and not have too much crowding when there are file icons, not just chevron icons). Chevrons and file type icons should all have the same width ultimately in these layouts."

"Together, this should show a lot more text of the PR title. We need a lot more of the text for each PR title in the nav."

Done when:
- The nav rows' leading icon slots are very slightly tighter: the Files tree's folder chevrons and file type icons, the Pulls nav's stack-row chevron and stack icon, and the pull request row's icon.
- Chevrons and file type icons take one shared slot width in these layouts (one token), so the Files tree still aligns cleanly, with file icons and chevrons in one column and no crowding.
- The before and after slot widths and the title width gained are measured in Chrome, recorded beside the token, and pinned in the Files and Pulls Chrome tests.
