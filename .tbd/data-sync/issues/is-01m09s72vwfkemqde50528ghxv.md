---
type: is
id: is-01m09s72vwfkemqde50528ghxv
title: "Diff: address a comparison in the /view/ URL grammar"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-18T06:33:51.739Z
updated_at: 2026-09-20T15:40:28.367Z
closed_at: 2026-09-20T15:40:28.366Z
close_reason: |
  Closed 2026-09-20: this bead's own notes record that the /view/ comparison grammar was decided and documented and that /commit/<rev>[/<file>] is implemented end to end, with the remaining work (/compare/, inner-file restore, panel-state audit) moved to mb-hgus. Confirmed mb-hgus exists and is status open (tbd show mb-hgus, 2026-09-20).
resolution: null
duplicate_of: null
---
Open decision from the spec. A rendered diff should be linkable and reloadable like every other selected thing since v0.5.0. Decide how a comparison is addressed — the Changes surface, a commit, and a single file within it — under the reserved _mb_ query namespace and the canonical /view/ route.

## Notes

Grammar decided and documented; /commit/<rev>[/<file>] implemented end to end (server shell + decoder, navigation commitHref/parseCommit, panel writes and restores). Remaining work moved to mb-hgus (/compare/, inner-file restore, panel-state audit).
