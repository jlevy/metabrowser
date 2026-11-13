---
type: is
id: is-01m7b1dkb51yg93bvh8bdx6trv
title: "Title-bar mark: a little further from the right, with a square hover like other hover targets"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-13T18:06:21.027Z
updated_at: 2026-11-13T18:36:25.299Z
closed_at: 2026-11-13T18:36:25.298Z
close_reason: "Merged in #398 (3381f87f): the title-bar MB mark sits 14 pt from the trailing edge and its hover box is square, matching the web UI."
resolution: null
duplicate_of: null
---
The user, 2026-11-13: the MB logo in the upper right should be a little further from the right edge (today it ends 9.2 pt from the trailing edge), and its hover highlight should be square, like the hover on other clickable things such as the main directory heading, not a capsule. Follow-up to mb-j441 (#391).

## Notes

2026-11-13: jlevy/metabrowser#398 (claude/v1-mark-hover to main), 48477a9a: 14 pt from the trailing edge (was 9.2), hover a square box (radius 0, matching .header-path:hover), 3 pt past the ink. Sheet checked by the coordinator; review A running.
