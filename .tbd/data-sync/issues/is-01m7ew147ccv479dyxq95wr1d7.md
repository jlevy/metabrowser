---
type: is
id: is-01m7ew147ccv479dyxq95wr1d7
title: Files type filter menu is too short for its rows
kind: bug
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T05:49:07.179Z
updated_at: 2026-11-17T05:58:15.514Z
started_at: 2026-11-15T05:50:26.989Z
closed_at: 2026-11-16T16:30:44.780Z
close_reason: "Merged into main at afda3599f (stack #446 lower layers)."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim: "the height of that menu should be taller if it has more items. Approximately double the size for a max height. it holds about 8 lines but should hold more like up to 16, but appropriate to the number of items and always within the window". Then: "(the age drop down is fine as it has only a few items)".

"That menu" is the Files tab's type filter dropdown. On main, every filter chip menu uses `.chip-menu-panel` in `static/styles.css`, with `max-height: 320px; overflow-y: auto`. That holds about 8 rows plus the section headings.

Done when:
- the type filter menu takes its content's natural height, up to about 16 rows;
- the cap is expressed from the row height (a token or rows × the row's measured height, not a bare pixel guess);
- the menu always stays inside the window: it is capped by the space between its trigger and the window's edge, re-measured on open and on window resize, and scrolls inside itself past that;
- the age menu, which has few rows, is unchanged in size;
- the cap and the in-window rule are measured and pinned in a real browser at a tall and a short window.

Same menu as mb-s6vu (group headings), so they go in one PR.

## Notes

PR #444 (draft, base main), branch claude/menu-group-pattern, head 1c1964f8; bottom of native stack #446 (444 then 445). Plan: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md (in this PR, indexed in docs/project/README.md).

Change (commit 0986f649): one menu group pattern, a .menu-group with role="group" and aria-labelledby naming its .group-heading; the group draws its own divider; the heading starts on --menu-row-inset (8 px), which every menu row, title, and foot reads. .menu-section-label is gone. Moved onto it: the Files type filter's preset sections and the pull request stack menu (its "Stack #N" heading keeps the documented class and label tokens, no stack-specific face). filterControls.fitOpenMenus sets each open filter dropdown's max-height to 16 rendered rows plus frame, or the room to the window's bottom edge less 8 px; the shell fits on render, bind refits on resize. Docs: design-system "Groups in a Menu" and "Menu Height", plugins.md, CHANGELOG, paint-exempt row navigation.filter-menu-geometry.

Measured in headless Chrome: heading text 24 px past the rows' edge before, 0 after; type menu 320 px (8 rows) before, 474 px (16 rows) after at a 913 px viewport; at 413 px it ran 12 px past the window before and stops 8 px short after; Modified within 184 px before and after at both.

Tests: tests/test_files_tab_chrome.py (new; fails on main's 32 px inset, without the render fit, and without the resize listener), the stack part of tests/test_github_pull_header_chrome.py, filter-controls-behavior.js (menuMaxHeight, fitting, resize, disposal, markup), test_browser_filter_ui.py (shared inset, divider geometry). Local: focused suites, lint-check, parity, all goldens passed after merging main ab0dbcc0. CI on PR #444 (run 43691124504): all nine checks passed (lint, distribution, stack-integration, admitted-git 2.43.7 and 2.50.1, test 3.12, 3.13, 3.14, 3.14t). Bead left open until the PR merges.
