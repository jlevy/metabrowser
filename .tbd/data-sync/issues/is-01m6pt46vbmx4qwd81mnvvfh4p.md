---
type: is
id: is-01m6pt46vbmx4qwd81mnvvfh4p
title: Use shared progress indicators for PR page refreshes
kind: bug
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
created_at: 2026-11-05T21:34:04.650Z
updated_at: 2026-11-05T22:25:42.019Z
started_at: 2026-11-05T21:34:05.292Z
---
Keep the shared gray skeleton for a cold PR page. With usable content present, show the standard neutral spinner for active page or section work and use static explanations for idle or failed sections. Cover cold, partial, ready, refreshing, failed, and idle states.

## Notes

Implemented on 6413b6bf. Initial PR paint keeps the skeleton. Refresh and explicit Changes acquisition use the shared spinner after the page renders. The managed browser run retained the selected Changes view and showed exactly one spinner during PR refresh.
