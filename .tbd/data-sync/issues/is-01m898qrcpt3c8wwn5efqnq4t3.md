---
type: is
id: is-01m898qrcpt3c8wwn5efqnq4t3
title: "PR #838 A5: the first show after a mount can name a superseded revision"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m898q9z40pe69kyfzr97xxjv
hold: null
hold_until: null
created_at: 2026-11-25T11:51:26.869Z
updated_at: 2026-11-25T12:28:28.660Z
started_at: 2026-11-25T12:28:28.659Z
---
Low. stack-page.js:1250 captures guide before paintGuided awaits the import and 1259 shows carried.revision afterwards; a newer revision arriving meanwhile is dropped by the keep path (1211). Review: https://github.com/jlevy/metabrowser/pull/838#pullrequestreview-6057040965
