---
type: is
id: is-01m0xvd71f9wvm3127ewrytsjd
title: Standardize retained-navigation interaction attribution
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T01:36:58.412Z
updated_at: 2026-08-26T01:44:22.511Z
closed_at: 2026-08-26T01:44:22.510Z
close_reason: Standard performance-loop attribution procedure and evidence are documented and reconciled with the existing fail-closed scenarios; all focused and full validation passed.
resolution: null
duplicate_of: null
---
Files and surfaces: explorations/performance-loop/README.md interaction-scenario procedure and metric contract; docs/web-performance-framework.md stateful-navigation measurement contract; explorations/performance-loop/experiments/exp-018-git-revisions-swap-without-blanking.md follow-up evidence; docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md implementation map; CHANGELOG.md performance-loop summary; existing assertGitTransitionHealth and measureGitTransition coverage in explorations/performance-loop/capture-browser.js plus tests/test_browser_performance_capture.py. Document and reconcile a standard attribution ladder that freezes exact build/corpus/viewport, repeats visible trusted-input captures, separates synchronous acknowledgement from selection-to-painted-ready and Event Timing, uses pending mutation timing only as state onset, audits work elsewhere in the same input task, consults Long Animation Frame forced-layout attribution, requires exact route/selection/render/mount convergence and cancellation health, and reports residual costs without overstating the fix. Acceptance: the standard Git scenario's existing fail-closed phase, pending, continuity, request, and convergence checks are explicitly connected to the procedure; the experiment records the learned focus/default-action attribution trap and repeated exact-head evidence; durable docs remain concise and linked rather than duplicated; make format, focused performance/docs tests, and make verify pass.

## Notes

Documented the authoritative six-step stateful-navigation attribution procedure; connected it to the standard Git and file scenario gates; added the missing gitRevision:selectToReady metric contract; recorded the focus-handler/Tab-anchor Long Animation Frame finding and repeated evidence in exp-018; updated the framework, spec map, and changelog. Focused performance/docs tests pass (51), make format passes, and make verify passes (1556 pytest plus 48 tryscript, lint/type/audits/distribution).
