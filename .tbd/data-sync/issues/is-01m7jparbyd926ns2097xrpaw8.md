---
type: is
id: is-01m7jparbyd926ns2097xrpaw8
title: "PR #477 A4: two routes of the folder-home Chrome check can silently not run"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7jjcfgz5r5ykt72449xb6as
hold: null
hold_until: null
created_at: 2026-11-16T17:26:28.987Z
updated_at: 2026-11-16T17:46:12.756Z
started_at: 2026-11-16T17:28:21.695Z
closed_at: 2026-11-16T17:46:12.755Z
close_reason: "Fixed in c1b48908d (PR #477 review A): both preconditions are checks; the text-field route, which had never run, now opens the settings menu after Commits lands and runs (109 checks). Disposition reply: https://github.com/jlevy/metabrowser/pull/477#issuecomment-6924312625"
resolution: null
duplicate_of: null
---
Low. tests/dom/folder-home-chrome.mjs:483 and :509-515. Review A (round 1), PR #477: https://github.com/jlevy/metabrowser/pull/477#pullrequestreview-5923748713
