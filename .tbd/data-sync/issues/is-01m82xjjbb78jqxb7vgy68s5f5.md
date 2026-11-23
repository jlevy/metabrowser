---
type: is
id: is-01m82xjjbb78jqxb7vgy68s5f5
title: Use the working tree for ordinary local folder opens
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:40:55.912Z
updated_at: 2026-11-23T00:42:49.817Z
started_at: 2026-11-23T00:42:49.810Z
---
Determine why a plain File menu open can land in a pinned checkout. Start ordinary new local-folder opens on the working tree, and keep explicit revision selections and intentional session restoration. Verify re-opening an existing pinned checkout does not silently retarget unrelated windows or servers.
