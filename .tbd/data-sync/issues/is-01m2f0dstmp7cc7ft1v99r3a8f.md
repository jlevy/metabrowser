---
type: is
id: is-01m2f0dstmp7cc7ft1v99r3a8f
title: "PR #113 review R2: session stands in for app.js instead of running the real functions"
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m2f0dryv9qmyp9y6g1sc4gwq
created_at: 2026-09-14T03:47:27.699Z
updated_at: 2026-09-14T03:51:18.078Z
---
PR #113 review R2 (Medium). tests/dom/preview-pane-state-session.js:119-150 (panelSwitchDuringLoad no-op switch), :247-272 (recoveryOnReconnect claims itself), tests/golden/cli-ui-file-lifecycle.tryscript.md:152-153, tests/test_preview_pane_state_js.py:168-221 (substring asserts). Fix: extract activateNavPanel, retryUnreachablePreview, settleUnclaimedPreview, showNavigationLanding, applyNavigationTarget from app.js and run them in a vm sandbox with real navigation.js (pattern: tests/dom/catalog-feed-behavior.js:548); assert tab switch keeps claim, duplicate retry calls selectFile once, no retry after Git claim, R1 re-open claims loading; regex-pin claimPreview before the first await in selectFile. Or remove golden claims the test cannot fail.
