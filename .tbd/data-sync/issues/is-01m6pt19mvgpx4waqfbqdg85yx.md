---
type: is
id: is-01m6pt19mvgpx4waqfbqdg85yx
title: Name the PR diff tab Changes
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex-pulls-ui
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-05T21:32:29.198Z
updated_at: 2026-11-05T23:44:54.464Z
started_at: 2026-11-05T21:34:05.258Z
closed_at: 2026-11-05T23:44:54.463Z
close_reason: "Implemented and reviewed in PR #304 at 48c2c079. Full local verification, three live GitHub PR smokes, and all nine GitHub CI jobs passed."
resolution: null
duplicate_of: null
---
Use Changes in the tab and its user-facing references while keeping existing deep links and the comparison behavior. Verify the visible and accessible tab names and keyboard navigation.

## Notes

Implemented on 6413b6bf. The label is Changes and the existing /pull/<n>/files route keeps its address. Verified in the built-in browser on a checkout and a URL-managed repository, with session coverage.

Published as PR #304 in native stack #302. Final head 48c2c079 passed make verify (4,850 tests, 380 transcripts), the normal pre-push gate, and GitHub Actions run 42129605966 (nine jobs). Startup transfers 178,929 compressed bytes across 20 requests. The verified 0.11.1.dev1170+48c2c079 wheel is installed as the default CLI.
