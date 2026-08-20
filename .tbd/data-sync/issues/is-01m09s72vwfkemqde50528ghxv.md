---
type: is
id: is-01m09s72vwfkemqde50528ghxv
title: "Diff: address a comparison in the /view/ URL grammar"
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-18T06:33:51.739Z
updated_at: 2026-08-20T17:41:04.857Z
---
Open decision from the spec. A rendered diff should be linkable and reloadable like every other selected thing since v0.5.0. Decide how a comparison is addressed — the Changes surface, a commit, and a single file within it — under the reserved _mb_ query namespace and the canonical /view/ route.

## Notes

Grammar decided and documented; /commit/<rev>[/<file>] implemented end to end (server shell + decoder, navigation commitHref/parseCommit, panel writes and restores). Remaining work moved to mb-hgus (/compare/, inner-file restore, panel-state audit).
