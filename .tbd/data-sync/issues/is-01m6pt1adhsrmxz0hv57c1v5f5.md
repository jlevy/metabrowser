---
type: is
id: is-01m6pt1adhsrmxz0hv57c1v5f5
title: Restore each main navigation tab’s own selection
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
created_at: 2026-11-05T21:32:30.000Z
updated_at: 2026-11-05T22:25:41.405Z
started_at: 2026-11-05T21:34:05.279Z
---
A deliberate Files, Pulls, or Git tab switch restores that tab’s last route and selection or opens its default on first visit. Preserve direct links, Back and Forward, request ownership, and independent tab filters and scrolling.

## Notes

Implemented on 6413b6bf. Verified independent file and PR Changes restoration in both source modes and an independently selected Git revision in a checkout. Session witnesses cover startup clicks, explicit PR navigation superseding a delayed click, and Back to neutral Git when discovery is unavailable.
