---
type: is
id: is-01m74w0xx6pazq3q41x1702xke
title: "PR #348 D3: Conversation polls every second during the idle job"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:36.389Z
updated_at: 2026-11-11T09:24:58.943Z
started_at: 2026-11-11T09:24:56.015Z
closed_at: 2026-11-11T09:24:58.942Z
close_reason: "Fixed in c5fc056d: pollsFast() polls at SLOW_POLL_MS on Conversation while only optional preparation runs; Changes stays fast. DOM session pollWhilePreparing {conversation: 30000, changes: 1000}; fails without the fix."
resolution: null
duplicate_of: null
---
Low. pull-page.js:1196-1209, 837. Review D https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855776380
