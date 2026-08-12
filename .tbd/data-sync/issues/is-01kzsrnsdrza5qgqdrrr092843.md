---
type: is
id: is-01kzsrnsdrza5qgqdrrr092843
title: "PR #30 review S3: remove duplicated recent-window client setting"
kind: chore
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01kzsrn1678d07r42wx26b1kwh
created_at: 2026-08-12T01:16:34.104Z
updated_at: 2026-08-12T01:33:15.820Z
closed_at: 2026-08-12T01:33:15.820Z
close_reason: Removed the unused RECENT_WINDOWS client export and type; RECENT_WINDOW_SECONDS is the single ordered source.
---
PR #30 senior review suggestion, settings.py:186-188. RECENT_WINDOWS duplicates keys already shipped in RECENT_WINDOW_SECONDS and can drift.
