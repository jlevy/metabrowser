---
type: is
id: is-01m6pt46vbmx4qwd81mnvvfh4p
title: Use shared progress indicators for PR page refreshes
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
created_at: 2026-11-05T21:34:04.650Z
updated_at: 2026-11-05T23:44:56.930Z
started_at: 2026-11-05T21:34:05.292Z
closed_at: 2026-11-05T23:44:56.929Z
close_reason: "Implemented and reviewed in PR #304 at 48c2c079. Full local verification, three live GitHub PR smokes, and all nine GitHub CI jobs passed."
resolution: null
duplicate_of: null
---
Keep the shared gray skeleton for a cold PR page. With usable content present, show the standard neutral spinner for active page or section work and use static explanations for idle or failed sections. Cover cold, partial, ready, refreshing, failed, and idle states.

## Notes

Implemented on 6413b6bf. Initial PR paint keeps the skeleton. Refresh and explicit Changes acquisition use the shared spinner after the page renders. The managed browser run retained the selected Changes view and showed exactly one spinner during PR refresh.

Published as PR #304 in native stack #302. Final head 48c2c079 passed make verify (4,850 tests, 380 transcripts), the normal pre-push gate, and GitHub Actions run 42129605966 (nine jobs). Startup transfers 178,929 compressed bytes across 20 requests. The verified 0.11.1.dev1170+48c2c079 wheel is installed as the default CLI.
