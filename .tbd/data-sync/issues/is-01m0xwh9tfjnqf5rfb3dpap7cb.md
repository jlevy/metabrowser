---
type: is
id: is-01m0xwh9tfjnqf5rfb3dpap7cb
title: Exclude driver coordinate lookup from navigation timing
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T01:56:40.900Z
updated_at: 2026-08-26T02:02:08.520Z
closed_at: 2026-08-26T02:02:08.519Z
close_reason: The standard Git and file drivers exclude coordinate/layout preparation from interaction timing, tests pin the boundary, both headed scenarios pass, and full verification is green.
resolution: null
duplicate_of: null
---
Files and functions: pointForSelector, dispatchTrustedClickForFilePath, measureFileTransition, and measureGitTransition in explorations/performance-loop/capture-browser.js; focused ordering contract in tests/test_browser_performance_capture.py; procedure and implementation map in explorations/performance-loop/README.md and the active plan; PR exact-head evidence. Resolve and scroll the target plus compute its click coordinates before starting the application transition clock and pending/blank monitor. Dispatch the trusted click only after the common start timestamp and monitors are armed. Preserve true input-to-ready, phase, fetch, continuity, and convergence measurements while excluding driver-induced scroll/layout preparation. Acceptance: a focused test fails on the old ordering and passes after; both Git and file scenario paths share the invariant; exact-head headed Git capture against the settled trading corpus records pending onset from the trusted-input boundary rather than coordinate acquisition; focused tests, make format, and make verify pass.

## Notes

A failing focused regression test pinned that target scroll/coordinate preparation must precede both transition timing and pending/blank monitors. Extracted pointForFilePath and updated Git/file measurement paths to resolve coordinates before the common origin and dispatch trusted input afterwards. Corrected settled Git validation recorded 6.2–17.9 ms pending onset, 0.4–1.4 ms feedback, zero blank frames, exact convergence, bounded two-request hydration, two expected aborts, zero obsolete successes/exceptions/forced layout. File validation recorded 10.6–20.4 ms onset, one request per cold transition, zero cached requests, zero blank frames, exact convergence, one mount, zero exceptions, and 24 ms maximum Event Timing. Focused 52-test set and make verify (1557 pytest plus 48 tryscript, lint/types/audits/distribution) pass.
