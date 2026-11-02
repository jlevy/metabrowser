---
type: is
id: is-01m6f6a6zn06rv4qf5dzs85dce
title: "PR #275 layer: a capped tree's file-list note says '500,000 files files'"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m6f50p52sbg40g9qx5rc11h1
created_at: 2026-11-02T22:33:08.851Z
updated_at: 2026-11-02T23:11:51.799Z
closed_at: 2026-11-02T23:11:51.798Z
close_reason: "fixed in 5d1c0d6b; pinned by the note's step in tests/dom/file-overview-session.js, which fails without the fix. PR #275 comment names the commit."
resolution: null
duplicate_of: null
---
Found running the sign-off addendum's page claims in headless Chrome on the #275 head 2ca297fa with INVENTORY_MAX_FILES lowered to 3: the note reads 'File list incomplete. Metabrowser stopped after 3 files files, so some files and folders are not shown.' src/metabrowser/static/app.js treeTruncationNoteHtml writes ${formatCount(maxFiles)} files, and formatCount (app.js:216) already appends the noun. v0.11.0 has the same code but never reached it, because a capped index answered idle; mb-1qwp's fix on #275 makes it reachable. #275's description lists a real browser for the capped notices as not run. Fix belongs on #275's layer: drop the literal word; pin it in a session. Reported to the coordinator, not fixed on #277.
