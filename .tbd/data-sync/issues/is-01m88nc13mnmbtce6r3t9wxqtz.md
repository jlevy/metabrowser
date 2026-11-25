---
type: is
id: is-01m88nc13mnmbtce6r3t9wxqtz
title: "Pulls row: a stack member's place sits on top of its state icon"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T06:12:59.566Z
updated_at: 2026-11-25T06:13:47.630Z
started_at: 2026-11-25T06:13:47.621Z
---
Reported by the user after #821 merged: in the Pulls tab's nav column, a stack member's place (e.g. bold 1/2) is drawn on top of the PR state icon instead of after it. #821 positions the icon absolutely and leaves its slot with the heading's first-line text-indent. Done when the place always starts after the icon (one stack, several stacks, every width the pane allows, both themes), pinned by a Chrome check that the icon's box and the place's box do not overlap, on markup the real Pulls panel renders.
