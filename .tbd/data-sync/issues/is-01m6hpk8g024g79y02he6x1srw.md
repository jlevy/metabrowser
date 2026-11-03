---
type: is
id: is-01m6hpk8g024g79y02he6x1srw
title: Preserve expanded PR row geometry across virtualized remounts
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:56:11.392Z
updated_at: 2026-11-03T21:57:11.816Z
started_at: 2026-11-03T21:57:11.811Z
---
Real headless-browser probe expanded a noncurrent600-file PR row to15185.5px, scrolled it offscreen until its DOM was removed, then returned. The old PR-row content-visibility auto/41.5px intrinsic fallback replaced its measured expanded geometry, collapsing scrollHeight19704to4560 and clamping scrollTop. The new top-level window already bounds mounted rows near100, so remove redundant PR-row content-visibility/intrinsic-size CSS and recheck the unchanged browser remount assertion plus5000-row performance. Keep logical expanded state and bounded nested file rows.
