---
type: is
id: is-01m74w0qtdh7grcbk8se6ngdw1
title: "PR #348 A9: viewing Conversation can create a comparison store, unmeasured"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:30.156Z
updated_at: 2026-11-11T10:57:49.704Z
started_at: 2026-11-11T09:24:55.908Z
closed_at: 2026-11-11T10:57:49.703Z
close_reason: "Fixed with D1: c5fc056d, 10b7dafa, 9163be07. Conversation never creates a store; the measurement A9 asked for is recorded in pull-page.js, the mirror-and-checkout plan, and reviewing-pull-requests.md."
resolution: null
duplicate_of: null
---
Medium. pull-page.js:89; pull_route.py:23-27; plan-2026-11-02-pr-review-mirror-and-checkout.md:391. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
