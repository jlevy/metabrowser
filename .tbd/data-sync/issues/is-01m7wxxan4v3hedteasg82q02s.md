---
type: is
id: is-01m7wxxan4v3hedteasg82q02s
title: "Store keys: a clean single-dash slug plus a short deterministic base36 digest (e.g. github-com-jlevy-metabrowser-<base36>), instead of github-com--jlevy--metabrowser--<16 hex>"
kind: task
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T16:51:21.891Z
updated_at: 2026-11-20T16:52:06.241Z
started_at: 2026-11-20T16:52:06.238Z
---
Owner, 2026-11-20, follow-up to mb-j2cp (#647): keys like github-com--jlevy--metabrowser--589d51b16fd8f1a2 are still too long. Keep it deterministic (a digest of the source identity, never random), just encoded compactly: base36 (as strif's short id helpers do) at the number of bits #647's collision analysis needs, with the readable part a plain slug joined by single dashes. Keep the collision-escalation path (longer suffix on a claimed key) and the store rename so existing stores move without refetching.
