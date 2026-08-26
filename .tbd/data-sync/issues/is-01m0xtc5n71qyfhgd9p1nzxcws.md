---
type: is
id: is-01m0xtc5n71qyfhgd9p1nzxcws
title: Gate Git pending timing and row-anchor attribution
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T01:18:55.654Z
updated_at: 2026-08-26T01:22:11.618Z
closed_at: 2026-08-26T01:22:11.606Z
close_reason: The standard headed Git scenario now requires finite ordered pending onset/clear timing and the post-readiness gitRevision:rowAnchor phase. Focused regression tests cover missing onset, missing clearance, reversed timing, and missing anchor attribution; make verify passes.
resolution: null
duplicate_of: null
---
Pre-commit review finding: explorations/performance-loop/capture-browser.js records pending_onset_ms, pending_clear_ms, and gitRevision:rowAnchor, but assertGitTransitionHealth does not require them. Add explicit finite, ordered pending timing checks and require the row-anchor phase so a broken observer or skipped accessibility finalization cannot pass the standard headed Git scenario. Extend tests/test_browser_performance_capture.py with one failing case per field; run focused tests and make verify.
