---
type: is
id: is-01m6mt130svbg10hxkvkt62bhx
title: Prevent hover from refetching the currently rendered Git revision
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T02:53:53.559Z
updated_at: 2026-11-05T02:53:54.188Z
started_at: 2026-11-05T02:53:54.187Z
---
H78 / exp-046. Unchanged db52 trace measured two identical Git comparison requests for the selected full revision: initial preparation at 2061 ms and a second at 2512 ms after selectToReady cleared the preparation slot. Existing git-panel session explicitly expects this second request. Hypothesis: when the selected revision still owns the rendered preview, a later hover should read tooltip detail without preparing another comparison. Preserve speculation for another revision, prepare again when another preview owner replaces Git, cancellation and disposal. Primary metric: matching comparison request count and decoded bytes after selected-row reenter, measured before and after with identical corpus/cache/browser conditions. Also report trusted click-to-useful painted readiness, main-thread budgets, network concurrency and heap/RSS; do not claim this removes initial provider/render latency. Register before product changes; at least three admissible serial runs per condition, five interleaved pairs for sub-2x time claims.
