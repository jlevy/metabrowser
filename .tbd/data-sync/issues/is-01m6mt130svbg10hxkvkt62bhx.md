---
type: is
id: is-01m6mt130svbg10hxkvkt62bhx
title: Prevent hover from refetching the currently rendered Git revision
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T02:53:53.559Z
updated_at: 2026-11-05T03:19:52.561Z
started_at: 2026-11-05T02:53:54.187Z
---
H78 / exp-046. Unchanged db52 trace measured two identical Git comparison requests for the selected full revision: initial preparation at 2061 ms and a second at 2512 ms after selectToReady cleared the preparation slot. Existing git-panel session explicitly expects this second request. Hypothesis: when the selected revision still owns the rendered preview, a later hover should read tooltip detail without preparing another comparison. Preserve speculation for another revision, prepare again when another preview owner replaces Git, cancellation and disposal. Primary metric: matching comparison request count and decoded bytes after selected-row reenter, measured before and after with identical corpus/cache/browser conditions. Also report trusted click-to-useful painted readiness, main-thread budgets, network concurrency and heap/RSS; do not claim this removes initial provider/render latency. Register before product changes; at least three admissible serial runs per condition, five interleaved pairs for sub-2x time claims.

## Notes

Three unchanged browser controls each issued exactly one new identical whole-comparison GET after explicit selected-row pointer reentry. The initial trace also contained a redundant postselection comparison, but it cannot distinguish a late original hover timer from a second mouseenter. Targeted live-preview-claim guard is applied with meaningful actual session RED(stock17requests when16expected) and GREEN(candidate),4focusedtests pass. Different-row speculation, tooltip detail reuse, cancellation and same-row preparation after another owner are pinned. Candidate browser acceptance pending. Git235ms-class LongTasks are separately H79/mb-envd; no claim this request guard fixes initial rendering.
