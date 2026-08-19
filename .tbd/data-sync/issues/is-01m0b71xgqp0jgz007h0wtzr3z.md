---
type: is
id: is-01m0b71xgqp0jgz007h0wtzr3z
title: "PR view: open a GitHub PR URL as a merge-base comparison"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-18T19:54:56.918Z
updated_at: 2026-08-19T18:12:17.726Z
---
Composition, not a silo: derive the repo URL and clone or reuse the purgeable cache; fetch refs/pull/<n>/head and refs/pull/<n>/merge over plain git transport (verified live — no API, no token; the merge ref is the provider-computed synthetic merge the research names); resolve mergeBase(base, head) through the core Git adapter; render with the standard renderer. Diff bodies never touch the GitHub API. PR metadata (title, state, checks) is a thin header call and can land after the diff works.

## Notes

The PR mirror is a nav container (arch-nav-containers.md): children = changed files, outer = PR summary overview. Compose acquisition (mb-2f7r) + merge-base comparison (git source) + container presentation (mb-um0p), materialized through the shared cache discipline (mb-z335).
