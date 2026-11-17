---
type: is
id: is-01m7g57nn5rthmy1dffxxnprpx
title: "Nav rows: slightly tighter icon slots, chevrons and file type icons one width"
kind: task
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
created_at: 2026-11-15T17:49:13.252Z
updated_at: 2026-11-17T05:58:33.807Z
started_at: 2026-11-15T17:50:37.066Z
closed_at: 2026-11-15T18:48:31.171Z
close_reason: null
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"the padding around the chevrons in the file toggle and expecially the stacked PRs toggle is slighlty too much. similarly for the padding around the pull request icons and around the stack icons inthe pulls nav column. Things should be very slightly tighter because there's excessive padding, but we should do it in a way that's not too much (because we need the files tab to still align cleanly and not have too much crowding when there are file icons, not just chevron icons). Chevrons and file type icons should all have the same width ultimately in these layouts."

"Together, this should show a lot more text of the PR title. We need a lot more of the text for each PR title in the nav."

Done when:
- The nav rows' leading icon slots are very slightly tighter: the Files tree's folder chevrons and file type icons, the Pulls nav's stack-row chevron and stack icon, and the pull request row's icon.
- Chevrons and file type icons take one shared slot width in these layouts (one token), so the Files tree still aligns cleanly, with file icons and chevrons in one column and no crowding.
- The before and after slot widths and the title width gained are measured in Chrome, recorded beside the token, and pinned in the Files and Pulls Chrome tests.

## Notes

Done in 751d007da on claude/pulls-stack-groups (#450). One token, --tree-icon-slot: 14px (static/styles.css), for every tree row's leading slot: Files folder and container chevrons, file type icons (.tree-item-icon.file-identity-icon), change letters (.tree-container-badge), Pulls row chevron and state icon (grid columns), stack row chevron and Layers icon, PR file rows, and the Diff summary's chevrons. Palette and menu icon boxes stay 16px. Chrome at the default pane: Files names 22 -> 20 px from the row's content edge (folder chevron 12 px at 1 px in, file icon 14 px filling the slot, gap 6 px unchanged); Pulls title and stack label 44 -> 40 px; title room +4 px (member 165.7 -> 169.7, first level 181.7 -> 185.7). Pinned in tests/test_files_tab_chrome.py (slots) and tests/dom/github-pulls-stacks-chrome.mjs. Not checked in WebKit.
