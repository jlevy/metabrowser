---
type: is
id: is-01m2f05dxk611gke0h7vgnr68w
title: "PR #112 review S2: manual real-browser check in the PR test plan is unticked"
kind: bug
status: closed
priority: 4
version: 3
labels: []
dependencies: []
parent_id: is-01m2f05257wwkdtjwanq4bd016
created_at: 2026-09-14T03:42:53.362Z
updated_at: 2026-09-14T04:35:25.694Z
closed_at: 2026-09-14T04:35:25.693Z
close_reason: "Verified in real Chromium against 684d6189: row clicked 33 ms after load before the tree keyboard module loaded; focus adopted, first J moved to next row, ArrowDown and K also worked."
resolution: null
duplicate_of: null
---
PR #112 suggestion. The PR body's manual real-browser check (click a row before initDeferredShellTools, then press Down) is unticked; the FakeDocument cannot prove the premise that no focusin is heard in a real browser.

## Notes

Deferred: the manual real-browser check needs a human (or a real-browser session) to click a row before initDeferredShellTools attaches, then press Down or J. The agent addressing the review did not start browsers, so the PR #112 test-plan item stays unticked; do it before merging PR #112.
