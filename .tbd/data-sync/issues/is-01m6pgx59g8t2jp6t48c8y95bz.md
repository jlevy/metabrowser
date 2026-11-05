---
type: is
id: is-01m6pgx59g8t2jp6t48c8y95bz
title: Consolidate Pulls catalog status and loading feedback
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-pulls-status
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T18:52:56.494Z
updated_at: 2026-11-05T20:08:30.654Z
started_at: 2026-11-05T18:55:24.202Z
closed_at: 2026-11-05T20:08:30.653Z
close_reason: "Reviewed and verified in PR #303, installed locally, and all nine CI jobs passed."
resolution: null
duplicate_of: null
---
Show the repository once in bold, preserve the exact total and display-window context, and use one shared spinner status for Pulls loading and refresh. Keep failure guidance, muted freshness, and shared branch chips. Verify checkout and managed sources with the production browser session and a manual check.

## Notes

Implemented at 5c8cb75b above PR #301. The existing checkout and managed URL were checked in the built-in browser using the public Metabrowser repository. Verified one spinner and one accessible fetch message on cold load, the bold count and repository name, separate PR and mirror freshness, filters, and shared branch chips in the list and PR header. Independent review found that cached Fetch more after a rate limit needed its own activity indication. The existing browserless session reproduced the gap and now covers the fix. Full local gate is running.

Published as PR #303 above #301 in native stack #302. At 5c8cb75b the local gates passed with 4,850 tests and 380 CLI transcript cases, clean dependency audits, and wheel and sdist checks. Normal pre-push passed, GitHub Actions run 42098224800 passed all nine jobs, and Qodo reported no findings. Both default CLI commands now run 0.11.1.dev1165+5c8cb75b. The installed CLI passed doctor and a browser smoke on an existing checkout.
