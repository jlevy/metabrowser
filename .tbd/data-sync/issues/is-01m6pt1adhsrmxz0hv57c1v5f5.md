---
type: is
id: is-01m6pt1adhsrmxz0hv57c1v5f5
title: Restore each main navigation tab’s own selection
kind: bug
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
created_at: 2026-11-05T21:32:30.000Z
updated_at: 2026-11-05T23:44:55.290Z
started_at: 2026-11-05T21:34:05.279Z
closed_at: 2026-11-05T23:44:55.289Z
close_reason: "Implemented and reviewed in PR #304 at 48c2c079. Full local verification, three live GitHub PR smokes, and all nine GitHub CI jobs passed."
resolution: null
duplicate_of: null
---
A deliberate Files, Pulls, or Git tab switch restores that tab’s last route and selection or opens its default on first visit. Preserve direct links, Back and Forward, request ownership, and independent tab filters and scrolling.

## Notes

Implemented on 6413b6bf. Verified independent file and PR Changes restoration in both source modes and an independently selected Git revision in a checkout. Session witnesses cover startup clicks, explicit PR navigation superseding a delayed click, and Back to neutral Git when discovery is unavailable.

Published as PR #304 in native stack #302. Final head 48c2c079 passed make verify (4,850 tests, 380 transcripts), the normal pre-push gate, and GitHub Actions run 42129605966 (nine jobs). Startup transfers 178,929 compressed bytes across 20 requests. The verified 0.11.1.dev1170+48c2c079 wheel is installed as the default CLI.
