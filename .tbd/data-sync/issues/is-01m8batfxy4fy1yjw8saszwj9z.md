---
type: is
id: is-01m8batfxy4fy1yjw8saszwj9z
title: Relative links in pull request texts and Guided Review notes open broken github.com/<o>/<r>/pull/<path> pages
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bathnhy6pkgn4hmjd87hb1
parent_id: is-01m8bat4973h1bjzvpkwd8qjdy
hold: null
hold_until: null
created_at: 2026-11-26T07:06:22.526Z
updated_at: 2026-11-26T08:56:54.745Z
started_at: 2026-11-26T07:15:05.637Z
closed_at: 2026-11-26T08:56:54.745Z
close_reason: Implemented in https://github.com/jlevy/metabrowser/pull/874 (head 2bf458b8, CI green); merges with the epic mb-xdjt.
resolution: null
duplicate_of: null
---
Reported 2026-11-26 with [Trade Runner](docs/trade-runner/README.md). Reproduced on the guided fixture: [the guide](docs/new.md) opens https://github.com/octo/demo/pull/docs/new.md. Fix: pull-page inertProse, Guided Review loadDrawProse, and stack-page loadDrawProse call MetabrowserRepositoryLinks.enhance with the text context (pull page, head); same-repo pull/commit/blob links open in-app.
