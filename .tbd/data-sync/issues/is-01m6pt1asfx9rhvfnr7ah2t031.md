---
type: is
id: is-01m6pt1asfx9rhvfnr7ah2t031
title: Show exact counts on Open, Closed, and All PR filters
kind: feature
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex-pulls-ui
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-05T21:32:30.382Z
updated_at: 2026-11-05T22:25:41.721Z
started_at: 2026-11-05T21:34:05.286Z
---
Use small shared-style tallies and cached exact counts across filters. Keep unknown counts distinct from zero and avoid extra GitHub queries.

## Notes

Implemented on 6413b6bf. Exact Open, Closed, and All tallies use one cached catalog read. The selected count, repository summary, and refresh state agree after older cached pagination. Verified actual public repository tallies and browserless provider-failure pagination.
