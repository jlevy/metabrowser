---
type: is
id: is-01m7et4ereqng8q5eb6qmsyje1
title: Sizes of a gigabyte or more show in MB in the shell
kind: bug
status: in_progress
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-15T05:15:59.117Z
updated_at: 2026-11-15T05:30:03.371Z
started_at: 2026-11-15T05:19:38.318Z
---
`formatSize` in `src/metabrowser/static/app.js` stops at MB, so a size of a gigabyte or more renders in megabytes: 10.1 GB of ignored files shows as "(9632.1 MB)" in the Files tab's metadata line, not "(10.1 GB)".

Found while addressing review A on #435 (tab metadata line). The new `cli-ui-tree-summary-line.tryscript.md` golden records the MB rendering; it predates #435.

Done when: the shell's size formatter has a GB step (check whether the shared formatter runtime that `sizeClass` delegates to, and the Python side, already have one, and share it instead of adding a second formatter); the affected goldens show GB; a focused test pins the MB-to-GB boundary.

## Notes

Fixed in draft PR https://github.com/jlevy/metabrowser/pull/439 (branch claude/format-size-gigabytes): app.js formatSize now delegates to the shared formatters.js formatBytes, which already had GB. B/KB/MB unchanged byte-for-byte. New golden cli-ui-byte-sizes.tryscript.md, parity row shell.byte-sizes. 10,100,000,000 bytes reads 9.4 GB (binary steps). Draft #435 must load formatters.js in tests/dom/tree-summary-line-session.js and change its golden's (9632.1 MB) to (9.4 GB) once #439 lands.
