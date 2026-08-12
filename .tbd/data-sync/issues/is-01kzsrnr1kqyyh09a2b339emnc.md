---
type: is
id: is-01kzsrnr1kqyyh09a2b339emnc
title: "PR #30 review R6: replace live rows when entry type changes"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzsrn1678d07r42wx26b1kwh
created_at: 2026-08-12T01:16:32.690Z
updated_at: 2026-08-12T01:33:14.829Z
closed_at: 2026-08-12T01:33:14.828Z
close_reason: Implemented synchronous stale-row replacement for path type changes and rapid remove/recreate events, including folder descendants.
---
PR #30 senior review R6, app.js:4481 and 4590-4596. A live file-to-symlink or symlink-to-file upsert selects by the new type, then insertion refuses the stale same-path row, leaving incorrect DOM state until reload.
