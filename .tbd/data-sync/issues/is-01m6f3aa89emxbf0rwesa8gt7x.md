---
type: is
id: is-01m6f3aa89emxbf0rwesa8gt7x
title: Tree rendering with the Files tree's contract
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3aapq93hetda33rkdc9zv
parent_id: is-01m6f39zpnk9rc3kjy552b88qj
hold: null
hold_until: null
created_at: 2026-11-02T21:40:46.472Z
updated_at: 2026-11-03T07:19:03.092Z
started_at: 2026-11-03T06:46:31.798Z
---
Row markup, chevrons, child groups, change badges, and inline stats, with the gesture and keyboard split through tree-keyboard-navigation.js handed by the host, the current row auto-expanded, and paths painted as text through the display rule.

## Notes

2026-11-03 HANDOFF: half done on wip/pulls-4-files fff7d6a3, never run in a browser (see mb-q3jt). Rendering is pull-files-view.js: a .tree-children[role=group] after the row's anchor, aria-owns from the anchor, aria-expanded and expanded/collapsed (the registry chevron) on the row; one flat list of rows with aria-level/posinset/setsize, drawn a window at a time (windowRange, FILE_ROWS_OVERSCAN placeholder 40), positioned by index at --ui-row-height. File rows are <a href> through pullHref, with the tree-container-badge letter, the name painted as text, and +N/-N stats; folder rows have the chevron. Neither uses .tree-item or data-tree-id, so app.js's pane listeners and resolveApplicationFocusFallback do not claim them, with no app.js change. pulls-panel.js adds the 16px chevron column (grid 16px 16px; meta at column 3), the click (open plus toggle), auto-expansion of the shown page's row, and attach on a rebuilt item so trees survive paintRows' keyed rebuild. The gesture's keyboard split is the plugin's own (the controller's left/right/activateAnchor), bound by pulls-nav.js: tree-keyboard-navigation.js registers fixed ids in the "tree" scope and rewrites every row's tabindex per move, so it is not handed over. AUTO_EXPAND_FILES is a placeholder (300) still to measure. Next: browser checkpoint in both themes, screenshots against the design system, sessions and design tests.

2026-11-03, from #285 round-2 review C6: step 4 adds more than child rows. Also: aria-owns from each pull-request row (a[role=treeitem]) to its file group, since the group sits beside the anchor inside li[role=none]; scope app.js's pane-wide .tree-item click (activateTreeRow), tooltip, hover prefetch and setSelectedPath handling to the Files tab, or file rows in #tab-pulls are claimed by them; check the [data-tree-id] focus fallback; widen pulls-nav.js's a.github-pulls-row focus check to file rows, with their own key scope so J/K on a file row moves files, not pull requests; a grid column for the chevron; and paintRows' keyed reuse (JSON.stringify of the described row) must keep children hung off an item. Consider aria-posinset/aria-setsize, since content-visibility: auto keeps undrawn rows out of Chrome's accessibility tree (C7).

2026-11-02, coordinator decision from #285 review A5: step 3's addressing makes the Pulls list role=tree with treeitem rows (aria-level) and scopes the Files tree's keyboard handler to the Files panel, so step 4 only adds children: a .tree-children[role=group] per row and aria-expanded on a row that has them. Key moves replace the history entry and a click or Enter pushes (A1), for file rows too.
