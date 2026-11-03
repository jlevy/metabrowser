---
type: is
id: is-01m6g1xt4fq1vkwjyznmxnnkkh
title: "PR #285 (coordinator): after a bfcache restore the list poll shows HTTP 409 before the pin guard reloads"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
created_at: 2026-11-03T06:35:42.605Z
updated_at: 2026-11-03T06:35:42.605Z
---
From the coordinator, not a review. After Back restores a page from the back/forward cache, the Pulls list's onVisibilityChange poll (pulls-panel.js) runs before the pin guard's pageshow status check; when the pin changed the list gets a 409 pin_changed and 'The list is unavailable (HTTP 409).' enters the DOM for 5-25 ms before the guard reloads. Make the poll wait for the guard, or treat pin_changed as no change; add a session step. pull-page.js's poll and the pin guard are out of scope.
