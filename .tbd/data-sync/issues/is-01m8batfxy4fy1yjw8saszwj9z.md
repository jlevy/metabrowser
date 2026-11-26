---
type: is
id: is-01m8batfxy4fy1yjw8saszwj9z
title: Relative links in pull request texts and Guided Review notes open broken github.com/<o>/<r>/pull/<path> pages
kind: bug
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8bathnhy6pkgn4hmjd87hb1
parent_id: is-01m8bat4973h1bjzvpkwd8qjdy
created_at: 2026-11-26T07:06:22.526Z
updated_at: 2026-11-26T07:06:24.304Z
---
Reported 2026-11-26 with [Trade Runner](docs/trade-runner/README.md). Reproduced on the guided fixture: [the guide](docs/new.md) opens https://github.com/octo/demo/pull/docs/new.md. Fix: pull-page inertProse, Guided Review loadDrawProse, and stack-page loadDrawProse call MetabrowserRepositoryLinks.enhance with the text context (pull page, head); same-repo pull/commit/blob links open in-app.
