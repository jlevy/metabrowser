---
type: is
id: is-01m6hn9r6c5ky1jek345fd78mz
title: Keep known PR totals during catalog identity and cursor restart
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:33:31.209Z
updated_at: 2026-11-03T21:34:50.755Z
started_at: 2026-11-03T21:34:50.754Z
---
Independent review reproduced an identity/cursor restart publishing exact zero totals even though its query already reported17 PRs. Publish known totals with a reset, or retain an explicitly unknown count; do not claim a false zero while a legitimate replacement catalog warms. Recheck the independent reset probe.
