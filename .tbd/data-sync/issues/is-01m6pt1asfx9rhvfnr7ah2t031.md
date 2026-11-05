---
type: is
id: is-01m6pt1asfx9rhvfnr7ah2t031
title: Show exact counts on Open, Closed, and All PR filters
kind: feature
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
created_at: 2026-11-05T21:32:30.382Z
updated_at: 2026-11-05T23:44:56.109Z
started_at: 2026-11-05T21:34:05.286Z
closed_at: 2026-11-05T23:44:56.108Z
close_reason: "Implemented and reviewed in PR #304 at 48c2c079. Full local verification, three live GitHub PR smokes, and all nine GitHub CI jobs passed."
resolution: null
duplicate_of: null
---
Use small shared-style tallies and cached exact counts across filters. Keep unknown counts distinct from zero and avoid extra GitHub queries.

## Notes

Implemented on 6413b6bf. Exact Open, Closed, and All tallies use one cached catalog read. The selected count, repository summary, and refresh state agree after older cached pagination. Verified actual public repository tallies and browserless provider-failure pagination.

Published as PR #304 in native stack #302. Final head 48c2c079 passed make verify (4,850 tests, 380 transcripts), the normal pre-push gate, and GitHub Actions run 42129605966 (nine jobs). Startup transfers 178,929 compressed bytes across 20 requests. The verified 0.11.1.dev1170+48c2c079 wheel is installed as the default CLI.
