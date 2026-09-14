---
type: is
id: is-01m1cdvsvwaqt12yyy2cj2g8sx
title: "PR #90 CODE-07: The recent and activity transcripts can only ever pin empty results"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:52.859Z
updated_at: 2026-09-14T07:01:00.509Z
closed_at: 2026-09-14T07:01:00.508Z
close_reason: "Fixed in PR #116. /api/recent nonempty window=all pin already landed on main in 8ffe964b. /api/activity: a one-shot CLI exits before the tracker's second poll, so the golden and the arch-views-models-routes parity section now state it pins the envelope only and cite tests/test_browser_active_tracker.py for the nonempty case."
resolution: null
duplicate_of: null
---
window=all with the pinned mtimes would give a deterministic non-empty pin; a one-shot CLI can structurally never show a non-empty active_files.
