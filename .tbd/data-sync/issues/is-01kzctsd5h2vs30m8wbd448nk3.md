---
type: is
id: is-01kzctsd5h2vs30m8wbd448nk3
title: "git: swimlane layout and SVG row renderer (port of scmHistory.ts)"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctsqjdfn84ykr7cr4hzhxm
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:43:22.160Z
updated_at: 2026-08-07T00:43:32.812Z
---
Add static/git_graph.js: computeSwimlanes(commits, priorLanes) and renderCommitGraph(row), ported from attic/vscode src/vs/workbench/contrib/scm/browser/scmHistory.ts (MIT). Pure — no fetching, no DOM ownership beyond the returned SVG. priorLanes carries lane continuity across page boundaries. Replace the VS Code color registry with design-token references and carry the upstream attribution header.
