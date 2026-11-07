---
type: is
id: is-01m6thd4vjfenzzqnxmbehgph4
title: Persist lightweight PR cores for instant cached descriptions
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:18:38.065Z
updated_at: 2026-11-07T08:19:49.389Z
started_at: 2026-11-07T08:19:49.388Z
---
Prepared PR descriptions currently live only in an eight-row CoreWindow and expire after 60 seconds, so viewport changes and later clicks lose useful metadata. Persist the validated lightweight core projection using the existing catalog or private-cache primitives; preserve repository/reader identity and version/fingerprint boundaries, serve validated cached descriptions immediately while refresh proceeds, and keep full discussion/checks/Git acquisition separate. Provide a batch-completion receipt that permits progressive startup warmup without N per-row reads. Measure cache reuse past 60 seconds and across cohorts/server restarts, and test stale/update/auth/offline/rate-limit cases with focused sessions.
