---
type: is
id: is-01m0hj1mb77mk6t2440pn6pp5j
title: Filtered tree expansion reads as unresponsive
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:02:28.453Z
updated_at: 2026-08-21T07:02:28.453Z
---
In a filtered tree, repeated expand clicks stop doing what the user means, which reads as the panel becoming unresponsive.

Two mechanisms, both downstream of rows disappearing on expand:

1. Rows shift under the pointer. Expanding a folder that then prunes itself removes one row, so the next row slides up into the pointer position. A second click at the same spot toggles a different folder, and a third can collapse the folder that actually held the matches. From the user side this is "I expand things and then it stops responding."

2. Genuinely dead rows. `markFolderKnownEmpty` (static/app.js) adds `tree-item-empty` and removes the `.tree-children` sibling. `setFolderExpanded` early-returns on both conditions, so that row can never expand again. Under a filter those rows are still listed, because the empty-folder bead keeps every folder with no loaded children. A dimmed folder that ignores every click is the worst version of the symptom.

Wanted: no row moves as a result of its own activation, and no listed folder silently ignores a click.

Depends on the empty-folder and vanishing-row beads; verify this one after those land.
