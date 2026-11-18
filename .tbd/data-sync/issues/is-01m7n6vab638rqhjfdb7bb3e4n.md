---
type: is
id: is-01m7n6vab638rqhjfdb7bb3e4n
title: "Diff summaries: show the gentle loading box promptly whenever a summary has not loaded"
kind: task
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
hold: null
hold_until: null
created_at: 2026-11-17T16:53:37.765Z
updated_at: 2026-11-18T17:44:09.908Z
started_at: 2026-11-17T17:00:54.958Z
closed_at: 2026-11-18T17:44:09.907Z
close_reason: "Merged in #532 (stack merge 86e083f35)."
resolution: null
duplicate_of: null
---
Reuse the existing pending placeholder (.tally-pending behind .mb-delayed-loading at --loading-state-delay) wherever a diff summary has not loaded, in Pulls rows and on the PR page, so it appears after the ~50 ms quiet period and never leaves an empty gap; today on the PR page it appears only after a long delay.
