---
type: is
id: is-01m7v81nhc6xr14nbpj9tqb3cw
title: "Title folder menu: the cloud or folder icon sits on the name's line, not centered across the two-line row"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T01:10:01.003Z
updated_at: 2026-11-20T01:12:38.419Z
started_at: 2026-11-20T01:12:38.418Z
---
Owner, 2026-11-19, verbatim: "in the dropdown menu in the title, the cloud and folder icons should be to the left of the name of the foler or repo, not centered vertically as they are now. i.e. they should be on the same line as the main name and the smaller text below should be subsequent lines". Likely apps/macos/Sources/Metabrowser/FolderChooserMenu.swift (each.image = row.mark.image on a two-line item) and the same pattern in RecentTargetsMenu.swift and TitleAccessory.swift; RootMark.swift maps folder/cloud.
