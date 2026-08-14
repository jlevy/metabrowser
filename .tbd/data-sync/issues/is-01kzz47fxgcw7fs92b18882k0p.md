---
type: is
id: is-01kzz47fxgcw7fs92b18882k0p
title: "PR #35 review R4: bfcache restore leaves the keyboard layer disposed"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:40.688Z
updated_at: 2026-08-14T03:32:02.737Z
closed_at: 2026-08-14T03:32:02.737Z
close_reason: "Fixed in 78ee53e: pagehide skips a persisted hide and a persisted pageshow re-initializes the keyboard layer."
---
app.js registers pagehide -> disposeKeyboardInfrastructure with {once:true} and ignores event.persisted, so a back/forward-cache restore leaves the shortcut registry, Help, tree navigation, and Quick File dead with no DOMContentLoaded to rebuild them.
