---
type: is
id: is-01m82xjjbb78jqxb7vgy68s5f5
title: Use the working tree for ordinary local folder opens
kind: bug
status: closed
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:40:55.912Z
updated_at: 2026-11-23T00:46:34.225Z
started_at: 2026-11-23T00:42:49.810Z
closed_at: 2026-11-23T00:46:34.200Z
close_reason: Verified independently that fresh local File and Recent opens always launch on the live working tree with no ref. A reopen foregrounds the existing session, which explains the requested checkout already showing a revision. Preserved explicit user pins across existing windows, since the server is shared. Four focused checkout launch, navigation and Commits tests passed.
resolution: null
duplicate_of: null
---
Determine why a plain File menu open can land in a pinned checkout. Start ordinary new local-folder opens on the working tree, and keep explicit revision selections and intentional session restoration. Verify re-opening an existing pinned checkout does not silently retarget unrelated windows or servers.
