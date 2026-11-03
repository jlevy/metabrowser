---
type: is
id: is-01m6hp3t5dhsp43qbz15j8k31h
title: Measure catalog list rendering and interaction at 5000 PRs
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: independent_ui_review
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
created_at: 2026-11-03T21:47:45.196Z
updated_at: 2026-11-03T22:04:59.184Z
---
Run isolated real-browser scaling checks at100/500/1000/5000 metadata rows with exact production list code, bounded mounted DOM, held-key responsiveness, expanded tree height, resize/focus/history/filter transitions and no external fixture requests. Preserve source pin/hashes, harness and raw evidence; reconcile final commit before claiming readiness. Interactive orchestration uses built-in browser; automated performance process stays headless and separate from owner testing servers.

## Notes

Independent headless Chrome matrix passed: three runs each at 100, 500, 1000, and 5000 catalog rows; actual Fetch more reached all 5000. Maximum mounted PR rows 103. Noncurrent 600-file tree remount, 60 trusted held keys per run, actual 800/1600 CSS-pixel alignment, stable scroll restoration, and delayed-response cancellation passed. No runtime errors or observed main-thread tasks over 50 ms. Descriptive loaded-host measurements, not a speedup or input-delay claim. Geometry defect mb-h5ti reproduced and independently fixed with unchanged probe. All 337 frozen source hashes unchanged; final commit reconciliation pending. Evidence: catalog-browser-ea771741/REPORT.json. Owned ports 8870-8874 stopped; user servers untouched.
