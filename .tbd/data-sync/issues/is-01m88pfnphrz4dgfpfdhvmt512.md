---
type: is
id: is-01m88pfnphrz4dgfpfdhvmt512
title: File-view menus do not close on an outside click or a second press
kind: bug
status: in_progress
priority: 1
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/835
    at: 2026-11-25T09:17:13.775Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T06:32:27.585Z
updated_at: 2026-11-25T09:17:13.776Z
started_at: 2026-11-25T06:34:39.465Z
---
Reported by the user: some menus in the file view, such as the grouping menu and the filter menus, stay open when they click outside them, while others, such as the branch menu, close. Every menu should behave the same: it closes on a click outside it, on a second press of the button that opened it, and on Escape, with focus returning to that button. Done when all of the shell's and built-in plugins' menus share one behavior from one component or helper, the design system says so, and a check fails a menu that does not use it, with browserless sessions and a Chrome check pinning outside click, second press, and Escape for each menu.
