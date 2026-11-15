---
type: is
id: is-01m7ew07x3j1ntyc8zqtbd2pgk
title: Menu group headings are indented; one design for groups in menus
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T05:48:38.178Z
updated_at: 2026-11-15T08:04:24.221Z
started_at: 2026-11-15T05:50:26.613Z
---
The user's request (2026-11-15), verbatim: "in the drop down of Files, under the type filter, the groups like "GROUPS" are indented but theyshould not be. We should have a consistent design system for groups within menu items like this."

On main, the Files type filter (`filter-controls.js`, `presetRows`) heads each preset section with `.menu-section-label`. In `static/styles.css` that rule is `padding: 3px 8px 2px 32px`: an icon-column inset that lines the heading up with the row labels rather than with the menu's edge. The gear menu's `.menu-title` uses the same small-caps register without the inset. The PR page's stack menu (`builtin_plugins/github/pull-page.js`, "Stack #N") also uses `.menu-section-label`, and other menus may head groups their own way.

Done when:
- every menu that groups its rows is inventoried with how it heads and separates a group (type filter, age filter, gear menu, stack menu, branch and ref selector, kind and view menus, plugin menus, and any other);
- a group heading sits at the menu's row inset, not indented to the icon or check column;
- groups follow one documented pattern (heading, separator, spacing, ARIA `role="group"` with `aria-labelledby`), stated once in `docs/design-system.md` under Overlays, Menus, and Dialogs and reachable by plugins through a documented class;
- any menu that heads groups its own way is moved onto it;
- a test pins the heading's inset and the shared pattern, measured in a real browser where the claim is about paint.

## Notes

PR #444 (draft, base main), branch claude/menu-group-pattern, head 1c1964f8; bottom of native stack #446 (444 then 445). Plan: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md (in this PR, indexed in docs/project/README.md).

Change (commit 0986f649): one menu group pattern, a .menu-group with role="group" and aria-labelledby naming its .group-heading; the group draws its own divider; the heading starts on --menu-row-inset (8 px), which every menu row, title, and foot reads. .menu-section-label is gone. Moved onto it: the Files type filter's preset sections and the pull request stack menu (its "Stack #N" heading keeps the documented class and label tokens, no stack-specific face). filterControls.fitOpenMenus sets each open filter dropdown's max-height to 16 rendered rows plus frame, or the room to the window's bottom edge less 8 px; the shell fits on render, bind refits on resize. Docs: design-system "Groups in a Menu" and "Menu Height", plugins.md, CHANGELOG, paint-exempt row navigation.filter-menu-geometry.

Measured in headless Chrome: heading text 24 px past the rows' edge before, 0 after; type menu 320 px (8 rows) before, 474 px (16 rows) after at a 913 px viewport; at 413 px it ran 12 px past the window before and stops 8 px short after; Modified within 184 px before and after at both.

Tests: tests/test_files_tab_chrome.py (new; fails on main's 32 px inset, without the render fit, and without the resize listener), the stack part of tests/test_github_pull_header_chrome.py, filter-controls-behavior.js (menuMaxHeight, fitting, resize, disposal, markup), test_browser_filter_ui.py (shared inset, divider geometry). Local: focused suites, lint-check, parity, all goldens passed after merging main ab0dbcc0. CI on PR #444 (run 43691124504): all nine checks passed (lint, distribution, stack-integration, admitted-git 2.43.7 and 2.50.1, test 3.12, 3.13, 3.14, 3.14t). Bead left open until the PR merges.
