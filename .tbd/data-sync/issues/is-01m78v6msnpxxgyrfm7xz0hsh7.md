---
type: is
id: is-01m78v6msnpxxgyrfm7xz0hsh7
title: "Open new windows larger: a little wider, and about 80% of the screen's height"
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T21:39:12.820Z
updated_at: 2026-11-12T23:40:55.293Z
closed_at: 2026-11-12T23:40:55.292Z
close_reason: "Done in jlevy/metabrowser#384 (a3dacf51, d9b4e07f): NewWindowFrame, 80% of the visible height, 90% of the width up to 1440, cascade kept on screen, restore and tabs unchanged. Review A approved with nits, fixed; CI green."
resolution: null
duplicate_of: null
---
The user, 2026-11-12: a new window opens at BrowserWindowController.initialSize, a fixed 1200x820, which is awkwardly small. Make the default a little wider, and its height about 80% of the screen's height whatever the screen's size. Restored windows keep their saved frames.

## Notes

2026-11-12: implemented in jlevy/metabrowser#384 (claude/v1-window-polish, stacked on #377 in stack #360): defd9d04 (logo) and a3dacf51 (window size). Renders checked by the coordinator in light and dark; review A running.
