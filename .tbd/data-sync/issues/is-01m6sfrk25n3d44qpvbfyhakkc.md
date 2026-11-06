---
type: is
id: is-01m6sfrk25n3d44qpvbfyhakkc
title: Give pull request checks a dedicated tab
kind: feature
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-06T22:30:41.465Z
updated_at: 2026-11-06T23:45:05.604Z
started_at: 2026-11-06T22:32:13.774Z
closed_at: 2026-11-06T23:45:05.603Z
close_reason: "#310 a513ecaf is clean with nine green CI jobs and no review findings. Verified direct Checks routes, nine check links, alignment, browser history, and stack navigation in both modes."
resolution: null
duplicate_of: null
---
Move check runs, status contexts, and check-specific notices into Checks beside Conversation and Changes. Support a stable direct address, Back and Forward, and CLI inspection on checkout and managed servers. Reuse the PR record and normal refresh.

## Notes

Implemented a dedicated Checks tab with /pull/<n>/checks. CLI, browserless, and built-in browser verification covered the existing checkout and managed repository, direct entry, reload, Back/Forward, stack navigation, and nine linked check runs. Awaiting exact full gate and publication.
