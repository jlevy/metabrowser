---
type: is
id: is-01m7nnxsky2r2jf9d5n3ac3vty
title: "App: clone progress, GitHub failure states with Copy and Retry, recheck on activation"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-17T21:17:07.581Z
updated_at: 2026-11-18T20:21:17.207Z
---
Phase 1, apps/macos. Status view shows the clone report from stderr; failure states show the reason and command (SetupGuide pattern); re-read GitHub status when the app becomes active.

## Notes

2026-11-18, checked against main a1100bca6. Not built. Related pieces from jlevy/metabrowser#539: a repository start is given up only after StartupDeadline sees no output growth for startupTimeout or repositoryStartupLimit passes, so a long clone is not abandoned; StartingView says when a start waits behind another repository's; the clone confirmation names the gh sign-in. Remaining as scoped: StatusView shows no clone progress line while starting, FailureView shows generic recent output with Retry but no GitHub failure state or copyable command, and nothing rechecks GitHub status on activation (needs mb-si2g).
