---
type: is
id: is-01m7ew07x3j1ntyc8zqtbd2pgk
title: Menu group headings are indented; one design for groups in menus
kind: bug
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
created_at: 2026-11-15T05:48:38.178Z
updated_at: 2026-11-15T06:37:59.860Z
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
