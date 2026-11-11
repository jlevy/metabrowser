---
type: is
id: is-01m751yvnqmybb3ns5vxx01awc
title: "PR #346 C2: a walk settling on a path the route cannot encode leaves Changes spinning"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m751ytvafc561t05kr196g8y
hold: null
hold_until: null
created_at: 2026-11-11T10:20:20.023Z
updated_at: 2026-11-11T10:34:27.608Z
started_at: 2026-11-11T10:20:28.134Z
closed_at: 2026-11-11T10:34:27.608Z
close_reason: "Fixed in 6d924fd3 (option 1): pull-files-tree.js claims settling only when deps.routable(path) is true; pull-files-view.js passes routable from host.href (tab.fileHref); no dep claims nothing. Confirmed by R14 as written (showFile settling=false; page part with that claim leaves Fetch changes, 0 POSTs), the files-tree session's backslash-path step, and the focus behavior test's view wiring; mutations claim-all and view-routable killed."
resolution: null
duplicate_of: null
---
Low. settleWalk ends quietly (pull-files-tree.js:1135) and deps.open rejects for a backslash segment (pull-route.js:34-43, :398-400), so the page stays settling with nothing sent. Fix: claim settling only for encodable paths (tab.fileHref), or cancel when the open does not land. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5857164511 (PR #346, review C, follow-up round 3, head 4318e80).
